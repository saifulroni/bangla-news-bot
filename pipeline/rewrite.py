"""
rewrite.py — AI-powered Bangla rewriting using Groq's free API.

For each filtered article, makes one Groq API call that returns:
  - headline: one-line Bangla headline
  - caption:  2-3 line social media caption
  - story:    3-5 sentence journalistic story

Recent published stories are prepended as context so the model can
write connective phrases like "following yesterday's protests..."
"""

import os
import json
import time
import logging
from datetime import datetime, timezone

from groq import Groq

logger = logging.getLogger(__name__)

GROQ_API_KEY  = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL    = "llama-3.3-70b-versatile"   # Best free-tier model for Bangla
MAX_RETRIES   = 3
RETRY_DELAY   = 5   # seconds between retries

# System prompt — the core of your journalism quality
SYSTEM_PROMPT = """You are an experienced Bangladeshi journalist writing for a fast-moving political news platform on social media.

Your audience is Bangladeshi readers who want breaking international and domestic political news in clear, professional Bangla.

When given an English news update, you will produce three outputs:
1. headline — A single sharp, urgent line. No full stop at the end. Make it punchy.
2. caption — 2-3 sentences for a social media post. Explain what happened, why it matters. End with an engaging hook if relevant.
3. story — 3-5 sentences written like a real journalist. Include what happened, the context (what led to this), and the current situation or likely next step.

Rules:
- Write in formal standard Bangla (শুদ্ধ বাংলা), not colloquial or mixed with English except for proper nouns
- Keep proper nouns (names of people, countries, organisations) in their common Bangla transliteration
- Do NOT translate literally — write naturally as a Bangla journalist would
- If recent context stories are provided, reference them naturally where relevant
- Never fabricate details not present in the source

Respond ONLY with a valid JSON object. No preamble, no explanation, no markdown. Example format:
{"headline": "...", "caption": "...", "story": "..."}"""


def _build_user_message(article: dict, recent_context: list[dict]) -> str:
    """
    Build the user message for Groq, including the article to rewrite
    and optional recent story context.
    """
    parts = []

    # Prepend recent stories as context (keeps model grounded in ongoing narrative)
    if recent_context:
        context_lines = []
        for ctx in recent_context[-5:]:  # Last 5 stories max
            context_lines.append(f"- {ctx.get('headline', '')}")
        context_block = "\n".join(context_lines)
        parts.append(f"Recent published stories (for context only — do not repeat these):\n{context_block}")
        parts.append("")

    # The article to rewrite
    parts.append(f"Source: {article['source']}")
    parts.append(f"English headline: {article['headline']}")
    if article.get("snippet"):
        parts.append(f"Details: {article['snippet']}")
    parts.append("")
    parts.append("Now write the Bangla headline, caption, and story as JSON.")

    return "\n".join(parts)


def _call_groq(user_message: str) -> dict | None:
    """
    Make one Groq API call. Returns parsed JSON dict or None on failure.
    Retries up to MAX_RETRIES times on transient errors.
    """
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY environment variable is not set")

    client = Groq(api_key=GROQ_API_KEY)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user",   "content": user_message},
                ],
                max_tokens=1200,
                temperature=0.4,   # Lower = more consistent, journalist-like output
               # response_format={"type": "json_object"},
            )
            raw = response.choices[0].message.content.strip()
            result = json.loads(raw)

            # Validate all required keys exist
            required_keys = {"headline", "caption", "story"}
            if not required_keys.issubset(result.keys()):
                missing = required_keys - result.keys()
                logger.warning(f"Response missing keys {missing}: {raw[:100]}")
                continue

            return result

        except json.JSONDecodeError as e:
            logger.warning(f"Attempt {attempt}: JSON parse error: {e}")
        except Exception as e:
            logger.warning(f"Attempt {attempt}: Groq API error: {e}")

        if attempt < MAX_RETRIES:
            time.sleep(RETRY_DELAY * attempt)  # Exponential backoff

    logger.error(f"All {MAX_RETRIES} attempts failed for article")
    return None


def rewrite_article(article: dict, recent_context: list[dict]) -> dict | None:
    """
    Rewrite a single article into Bangla journalism.

    Returns a result dict:
    {
        "id":                 str  (new UUID),
        "original_update_id": str  (source article ID),
        "timestamp":          str  (ISO UTC),
        "source":             str,
        "original_headline":  str,
        "url":                str,
        "headline":           str  (Bangla),
        "caption":            str  (Bangla),
        "story":              str  (Bangla),
        "model":              str,
    }
    Or None if rewriting failed.
    """
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
        "hf_score":           article.get("hf_score"),
    }


def rewrite_all(articles: list[dict], recent_context: list[dict]) -> list[dict]:
    """
    Rewrite all filtered articles. Respects Groq free-tier rate limit
    of ~30 requests/min by adding a small delay between calls.
    """
    results = []
    for i, article in enumerate(articles):
        logger.info(f"Rewriting {i+1}/{len(articles)}: {article['headline'][:60]}")
        result = rewrite_article(article, recent_context)
        if result:
            results.append(result)
            # Add this to context for subsequent rewrites in same run
            recent_context.append({"headline": result["headline"]})
        # 2.5s delay = ~24 req/min, safely under the 30/min free limit
        if i < len(articles) - 1:
            time.sleep(2.5)

    logger.info(f"Rewriting complete: {len(results)}/{len(articles)} succeeded")
    return results
