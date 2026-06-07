"""
main.py — Master orchestration script.

Flow:
  1. Fetch all RSS sources (recent articles only)
  2. Skip already-seen URLs
  3. Run importance + deduplication filters
  4. Fetch full article text for surviving articles only  ← NEW
  5. Rewrite into Bangla (with full context)
  6. Save to storage
  7. (Optional) Publish to Telegram
"""

import os
import sys
import logging
from datetime import datetime, timezone

from dotenv import load_dotenv
load_dotenv()

from pipeline.ingest    import fetch_all_sources
from pipeline.filter    import run_filter_pipeline
from pipeline.fulltext  import enrich_with_full_text
from pipeline.rewrite   import rewrite_all
from pipeline.storage   import save_raw_articles, save_output_stories, get_recent_outputs, get_seen_urls
from pipeline.publish   import publish_all

# ── Logging ───────────────────────────────────────────────────────────────
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("pipeline.log", encoding="utf-8"),
    ]
)
logger = logging.getLogger(__name__)


def run_pipeline():
    start_time = datetime.now(timezone.utc)
    logger.info("=" * 60)
    logger.info(f"Pipeline started at {start_time.isoformat()}")
    logger.info("=" * 60)

    # ── Step 1: Fetch RSS feeds (last 2 hours only) ────────────────────────
    logger.info("Step 1: Fetching RSS feeds (last 2 hours)...")
    all_articles = fetch_all_sources()
    logger.info(f"  Fetched: {len(all_articles)} recent articles")

    if not all_articles:
        logger.info("No recent articles found — nothing to do")
        _log_summary(start_time, 0, 0, 0, 0)
        return

    # ── Step 2: Skip already-seen URLs ────────────────────────────────────
    logger.info("Step 2: Removing already-processed articles...")
    seen_urls    = get_seen_urls()
    new_articles = [a for a in all_articles if a["url"] not in seen_urls]
    logger.info(f"  New (unseen): {len(new_articles)} articles")

    if not new_articles:
        logger.info("All articles already processed — nothing new")
        _log_summary(start_time, len(all_articles), 0, 0, 0)
        return

    save_raw_articles(new_articles)

    # ── Step 3: Filter pipeline ────────────────────────────────────────────
    logger.info("Step 3: Running filter pipeline...")
    filtered = run_filter_pipeline(new_articles)
    logger.info(f"  Passed filters: {len(filtered)} articles")

    if not filtered:
        logger.info("No articles passed filters")
        _log_summary(start_time, len(all_articles), len(new_articles), 0, 0)
        return

    # ── Step 4: Cap rewrites per run ──────────────────────────────────────
    max_rewrites = int(os.getenv("MAX_REWRITES_PER_RUN", "10"))
    if len(filtered) > max_rewrites:
        logger.info(f"  Capping at {max_rewrites} (was {len(filtered)})")
        filtered = filtered[:max_rewrites]

    # ── Step 5: Fetch full article text for filtered articles only ─────────
    logger.info(f"Step 5: Fetching full text for {len(filtered)} filtered articles...")
    filtered = enrich_with_full_text(filtered)

    # ── Step 6: Load recent context ───────────────────────────────────────
    logger.info("Step 6: Loading recent stories for context...")
    recent_context = get_recent_outputs(limit=6)
    logger.info(f"  Loaded {len(recent_context)} recent stories")

    # ── Step 7: Rewrite into Bangla ───────────────────────────────────────
    logger.info("Step 7: Rewriting into Bangla...")
    output_stories = rewrite_all(filtered, recent_context)
    logger.info(f"  Generated: {len(output_stories)} Bangla stories")

    if not output_stories:
        logger.warning("No stories generated — check GROQ_API_KEY")
        return

    # ── Step 8: Save ──────────────────────────────────────────────────────
    logger.info("Step 8: Saving stories...")
    save_output_stories(output_stories)

    # ── Step 9: Publish to Telegram (optional) ────────────────────────────
    if os.getenv("TELEGRAM_BOT_TOKEN"):
        logger.info("Step 9: Publishing to Telegram...")
        published = publish_all(output_stories)
        logger.info(f"  Published: {published} stories")
    else:
        logger.info("Step 9: Telegram not configured — skipping")

    _log_summary(start_time, len(all_articles), len(new_articles), len(filtered), len(output_stories))


def _log_summary(start, fetched, new, filtered, generated):
    duration = (datetime.now(timezone.utc) - start).total_seconds()
    logger.info("=" * 60)
    logger.info("PIPELINE SUMMARY")
    logger.info(f"  Total fetched:     {fetched}")
    logger.info(f"  New (unseen):      {new}")
    logger.info(f"  Passed filters:    {filtered}")
    logger.info(f"  Stories generated: {generated}")
    logger.info(f"  Duration:          {duration:.1f}s")
    logger.info("=" * 60)


if __name__ == "__main__":
    run_pipeline()
