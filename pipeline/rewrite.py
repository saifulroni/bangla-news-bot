"""
rewrite.py — AI-powered Bangla rewriting using Groq's free API.

Now uses full article text (from fulltext.py) when available,
falling back to snippet for paywalled/blocked sources.

Returns per article:
  headline — one punchy Bangla line
  caption  — 2-3 sentence social media post
  story    — 4-6 sentence journalistic writeup with full context
"""

import os
import json
import time
import logging
from datetime import datetime, timezone

from groq import Groq

logger = logging.getLogger(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL   = "llama-3.3-70b-versatile"
MAX_RETRIES  = 3
RETRY_DELAY  = 5

SYSTEM_PROMPT = """You are a senior Bangladeshi journalist at a major news agency. You write for a politically aware Bangladeshi audience that follows international geopolitics closely.

You will receive an English news article (headline + full text when available). Your job is to produce three outputs in Bangla:

1. headline — One sharp, urgent line. No full stop. Use active voice. Make it feel breaking.
2. caption — 2-3 sentences for Facebook/Telegram. State what happened, why it matters globally, and what happens next. Conversational but authoritative.
3. story — 4-6 sentences of proper journalism. Include: what happened, who is involved, what led to this (background), current situation, and significance or next steps. Use the full article text to include specific facts, quotes, numbers, and details. This should read like a wire service brief.

Strict rules:
- Write in formal standard Bangla (শুদ্ধ বাংলা) — no Banglish, no mixing English words except proper nouns
- Proper nouns: use standard Bangla transliteration (e.g. পুতিন, জেলেনস্কি, ট্রাম্প, বাইডেন)
- Do NOT fabricate any facts, quotes, or numbers not present in the source
- Do NOT start the story with "এই প্রতিবেদনে" or similar meta-phrases
- If full article text is provided, use specific details from it — don't just restate the headline
- Reference recent context stories naturally only when directly relevant

Respond ONLY with valid JSON — no markdown, no preamble:
{"headline": "...", "caption": "...", "story": "..."}"""


def _build_user_message(article: dict, recent_context: list) -> str:
    parts = []

    # Recent context for narrative continuity
    if recent_context:
        lines = [f"- {ctx.get('headline', '')}" for ctx in recent_context[-4:]]
        parts.append("Recent published stories (context only — do not repeat):\n" + "\n".join(lines))
        parts.append("")

    # Article details
    parts.append(f"Source: {article['source']}")
    parts.append(f"Headline: {article['headline']}")

    # Use full_text if available and substantially longer than snippet
    full_text = article.get("full_text", "")
    snippet   = article.get("snippet", "")

    if full_text and len(full_text) > len(snippet) + 100:
        parts.append(f"Full article text:\n{full_text}")
    elif snippet:
        parts.append(f"Article summary: {snippet}")

    parts.append("")
    parts.append("Write the Bangla headline, caption, and story as JSON.")
    return "\n".join(parts)


def _call_groq(user_message: str) -> dict | None:
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY not set")

    client = Groq(api_key=GROQ_API_KEY)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user",   "content": user_message},
                ],
                max_tokens=1024,
                temperature=0.3,
            )
            raw = response.choices[0].message.content.strip()

            # Strip markdown code fences if present
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            raw = raw.strip()

            result = json.loads(raw)
            required = {"headline", "caption", "story"}
            if not required.issubset(result.keys()):
                logger.warning(f"Missing keys in response: {result.keys()}")
                continue
            return result

        except json.JSONDecodeError as e:
            logger.warning(f"Attempt {attempt}: JSON parse error: {e}")
        except Exception as e:
            logger.warning(f"Attempt {attempt}: Groq API error: {e}")
            # If rate limited, wait longer
            if "429" in str(e) or "rate_limit" in str(e).lower():
                logger.info("Rate limited — waiting 60 seconds")
                time.sleep(60)
                continue

        if attempt < MAX_RETRIES:
            time.sleep(RETRY_DELAY * attempt)

    logger.error("All attempts failed")
    return None


def rewrite_article(article: dict, recent_context: list) -> dict | None:
    user_message = _build_user_message(article, recent_context)
    bangla = _call_groq(user_message)
    if not bangla:
        return None

    return {
        "id":                 f"out_{article['id']}",
        "original_update_id": article["id"],
        "timestamp":          datetime.now(timezone.utc).isoformat(),
        "source":             article["source"],
        "url":                article["url"],
        "original_headline":  article["headline"],
        "headline":           bangla["headline"],
        "caption":            bangla["caption"],
        "story":              bangla["story"],
        "model":              GROQ_MODEL,
        "importance_score":   article.get("importance_score"),
        "had_full_text":      len(article.get("full_text", "")) > len(article.get("snippet", "")),
    }


def rewrite_all(articles: list, recent_context: list) -> list:
    results = []
    for i, article in enumerate(articles):
        had_full = len(article.get("full_text", "")) > len(article.get("snippet", ""))
        logger.info(f"Rewriting {i+1}/{len(articles)} [{'full text' if had_full else 'snippet'}]: {article['headline'][:55]}")
        result = rewrite_article(article, recent_context)
        if result:
            results.append(result)
            recent_context.append({"headline": result["headline"]})
        if i < len(articles) - 1:
            time.sleep(2.5)

    logger.info(f"Rewriting complete: {len(results)}/{len(articles)} succeeded")
    return results
