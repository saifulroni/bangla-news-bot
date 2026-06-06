"""
rewrite.py - AI-powered Bangla rewriting using Groq free API.
Returns headline, caption, story in Bangla as JSON.
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

SYSTEM_PROMPT = """You are an experienced Bangladeshi journalist writing for a fast-moving political news platform on social media.

Your audience is Bangladeshi readers who want breaking international and domestic political news in clear, professional Bangla.

When given an English news update, produce three outputs:
1. headline - A single sharp, urgent line. No full stop at the end.
2. caption - 2-3 sentences for a social media post. Explain what happened, why it matters.
3. story - 3-5 sentences written like a real journalist. Include what happened, the context, and current situation.

Rules:
- Write in formal standard Bangla, not colloquial or mixed with English except for proper nouns
- Keep proper nouns in their common Bangla transliteration
- Do NOT translate literally - write naturally as a Bangla journalist would
- If recent context stories are provided, reference them naturally where relevant
- Never fabricate details not present in the source

Respond ONLY with a valid JSON object. No preamble, no explanation, no markdown.
Format: {"headline": "...", "caption": "...", "story": "..."}"""


def _build_user_message(article: dict, recent_context: list) -> str:
    parts = []
    if recent_context:
        context_lines = [f"- {ctx.get('headline', '')}" for ctx in recent_context[-5:]]
        parts.append("Recent published stories (for context only):\n" + "\n".join(context_lines))
        parts.append("")
    parts.append(f"Source: {article['source']}")
    parts.append(f"English headline: {article['headline']}")
    if article.get("snippet"):
        parts.append(f"Details: {article['snippet']}")
    parts.append("")
    parts.append("Now write the Bangla headline, caption, and story as JSON.")
    return "\n".join(parts)


def _call_groq(user_message: str) -> dict | None:
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
                max_tokens=1024,
                temperature=0.4,
     
            )
            raw = response.choices[0].message.content.strip()
            result = json.loads(raw)
            required_keys = {"headline", "caption", "story"}
            if not required_keys.issubset(result.keys()):
                continue
            return result
        except json.JSONDecodeError as e:
            logger.warning(f"Attempt {attempt}: JSON parse error: {e}")
        except Exception as e:
            logger.warning(f"Attempt {attempt}: Groq API error: {e}")
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
        "hf_score":           article.get("hf_score"),
    }


def rewrite_all(articles: list, recent_context: list) -> list:
    results = []
    for i, article in enumerate(articles):
        logger.info(f"Rewriting {i+1}/{len(articles)}: {article['headline'][:60]}")
        result = rewrite_article(article, recent_context)
        if result:
            results.append(result)
            recent_context.append({"headline": result["headline"]})
        if i < len(articles) - 1:
            time.sleep(2.5)
    logger.info(f"Rewriting complete: {len(results)}/{len(articles)} succeeded")
    return results
