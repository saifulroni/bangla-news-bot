"""
ingest.py — Fetches all RSS feeds and normalises them into a standard schema.

Output schema for each article:
{
    "id":          str   (sha256 of URL, first 16 chars),
    "source":      str   (human-readable source name),
    "tier":        int   (1=wire, 2=major, 3=other),
    "tags":        list  (e.g. ["wire", "politics"]),
    "headline":    str   (original English headline),
    "snippet":     str   (first 300 chars of description),
    "url":         str   (canonical article URL),
    "published_at":str   (ISO 8601 UTC),
    "fetched_at":  str   (ISO 8601 UTC),
}
"""

import hashlib
import time
import logging
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import feedparser
import requests

from .sources import RSS_SOURCES

logger = logging.getLogger(__name__)

# How many seconds to wait between feed requests (polite crawling)
FETCH_DELAY_SECONDS = 0.5
# Timeout per feed request in seconds
FEED_TIMEOUT = 10


def _make_id(url: str) -> str:
    """Generate a stable short ID from the article URL."""
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def _parse_date(entry) -> str:
    """Extract publication date from a feedparser entry, return ISO UTC string."""
    # feedparser provides 'published_parsed' (time.struct_time in UTC)
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
        return dt.isoformat()

    # Fallback: try parsing the raw 'published' string
    if hasattr(entry, "published") and entry.published:
        try:
            dt = parsedate_to_datetime(entry.published)
            return dt.astimezone(timezone.utc).isoformat()
        except Exception:
            pass

    # Last resort: use current time
    return datetime.now(timezone.utc).isoformat()


def _clean_snippet(entry) -> str:
    """Extract a clean text snippet from the feed entry, max 300 chars."""
    raw = ""
    if hasattr(entry, "summary") and entry.summary:
        raw = entry.summary
    elif hasattr(entry, "description") and entry.description:
        raw = entry.description

    # Strip any HTML tags (feedparser often leaves some)
    import re
    clean = re.sub(r"<[^>]+>", " ", raw)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean[:300]


def fetch_feed(source: dict) -> list[dict]:
    """
    Fetch a single RSS source and return a list of normalised article dicts.
    Returns an empty list if the feed fails.
    """
    articles = []
    now_utc = datetime.now(timezone.utc).isoformat()

    try:
        # Use requests with timeout for reliability, then parse the content
        resp = requests.get(source["url"], timeout=FEED_TIMEOUT, headers={
            "User-Agent": "BanglaPoliticsBot/1.0 (news aggregator)"
        })
        resp.raise_for_status()
        feed = feedparser.parse(resp.content)
    except Exception as e:
        logger.warning(f"Failed to fetch {source['name']}: {e}")
        return []

    for entry in feed.entries:
        url = getattr(entry, "link", "")
        if not url:
            continue  # Skip entries without a URL

        headline = getattr(entry, "title", "").strip()
        if not headline or len(headline) < 10:
            continue  # Skip empty or very short headlines

        articles.append({
            "id":           _make_id(url),
            "source":       source["name"],
            "tier":         source.get("tier", 3),
            "tags":         source.get("tags", []),
            "headline":     headline,
            "snippet":      _clean_snippet(entry),
            "url":          url,
            "published_at": _parse_date(entry),
            "fetched_at":   now_utc,
        })

    logger.info(f"Fetched {len(articles)} articles from {source['name']}")
    return articles


def fetch_all_sources() -> list[dict]:
    """
    Fetch all configured RSS sources and return a deduplicated list of articles.
    Articles are deduplicated by URL at this stage (exact match only — 
    semantic deduplication happens later in the filter pipeline).
    """
    all_articles = []
    seen_urls = set()

    for source in RSS_SOURCES:
        articles = fetch_feed(source)
        for article in articles:
            if article["url"] not in seen_urls:
                seen_urls.add(article["url"])
                all_articles.append(article)
        time.sleep(FETCH_DELAY_SECONDS)

    logger.info(f"Total unique articles fetched: {len(all_articles)}")
    return all_articles
