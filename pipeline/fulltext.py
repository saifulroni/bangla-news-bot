"""
fulltext.py — Fetches full article text for filtered articles only.

Called AFTER filtering, so we only scrape the ~10 articles
that will actually be rewritten — not the 500+ raw fetches.

Uses newspaper4k for extraction. Falls back to RSS snippet gracefully
if the page is paywalled, bot-blocked, or times out.
"""

import logging
import time

import requests

logger = logging.getLogger(__name__)

FULL_TEXT_TIMEOUT = 10    # seconds per article
FULL_TEXT_MAX     = 3000  # max characters to send to AI (keeps tokens reasonable)
FETCH_DELAY       = 1.0   # seconds between article fetches (polite crawling)

# Sources known to be paywalled or bot-blocked — skip full fetch for these
SKIP_DOMAINS = [
    "nytimes.com",
    "wsj.com",
    "bloomberg.com",
    "washingtonpost.com",
    "ft.com",
    "economist.com",
    "reuters.com",   # Hard paywall after a few articles
]


def _is_skippable(url: str) -> bool:
    return any(domain in url for domain in SKIP_DOMAINS)


def fetch_full_text(url: str) -> str:
    """
    Fetch and extract full article text from a URL.
    Returns clean text string, or empty string if extraction fails.
    """
    if _is_skippable(url):
        logger.debug(f"Skipping paywalled source: {url[:60]}")
        return ""

    try:
        from newspaper import Article
        art = Article(url, fetch_images=False, request_timeout=FULL_TEXT_TIMEOUT)
        art.download()
        art.parse()
        text = art.text.strip()

        if len(text) < 150:
            # Too short — likely a paywall or JS-rendered page
            return ""

        # Clean up excessive whitespace
        import re
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = text[:FULL_TEXT_MAX]
        logger.debug(f"Fetched {len(text)} chars from {url[:60]}")
        return text

    except Exception as e:
        logger.debug(f"Full text fetch failed for {url[:60]}: {e}")
        return ""


def enrich_with_full_text(articles: list[dict]) -> list[dict]:
    """
    Fetch full article text for each article in the list.
    Adds 'full_text' field — falls back to 'snippet' if fetch fails.
    Returns the same list with full_text added.
    """
    logger.info(f"Fetching full text for {len(articles)} articles...")

    for i, article in enumerate(articles):
        full_text = fetch_full_text(article["url"])

        if full_text:
            article["full_text"] = full_text
            logger.info(f"  [{i+1}/{len(articles)}] Got {len(full_text)} chars — {article['headline'][:50]}")
        else:
            article["full_text"] = article.get("snippet", "")
            logger.info(f"  [{i+1}/{len(articles)}] Used snippet — {article['headline'][:50]}")

        # Polite delay between fetches
        if i < len(articles) - 1:
            time.sleep(FETCH_DELAY)

    return articles
