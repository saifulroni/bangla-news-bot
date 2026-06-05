"""
main.py — Master orchestration script.

Run manually:   python main.py
Run via cron:   set up in GitHub Actions (see .github/workflows/pipeline.yml)

Flow:
  1. Fetch all RSS sources
  2. Filter out already-seen URLs (from storage)
  3. Run importance + classification + deduplication filters
  4. Rewrite surviving articles into Bangla
  5. Save raw + output to storage
  6. (Optional) Publish to Telegram
  7. Log summary
"""

import os
import sys
import logging
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

# Load .env file (local dev only — GitHub Actions uses repo secrets)
load_dotenv()

from pipeline.ingest  import fetch_all_sources
from pipeline.filter  import run_filter_pipeline
from pipeline.rewrite import rewrite_all
from pipeline.storage import save_raw_articles, save_output_stories, get_recent_outputs, get_seen_urls
from pipeline.publish import publish_all


# ── Logging setup ─────────────────────────────────────────────────────────
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
    logger.info(f"Pipeline run started at {start_time.isoformat()}")
    logger.info("=" * 60)

    # ── Step 1: Fetch all RSS sources ─────────────────────────────────────
    logger.info("Step 1: Fetching RSS feeds...")
    all_articles = fetch_all_sources()
    logger.info(f"  Fetched: {len(all_articles)} total articles")

    if not all_articles:
        logger.warning("No articles fetched — check network or feed URLs")
        return

    # ── Step 2: Remove already-processed articles ──────────────────────────
    logger.info("Step 2: Filtering already-seen URLs...")
    seen_urls = get_seen_urls()
    new_articles = [a for a in all_articles if a["url"] not in seen_urls]
    logger.info(f"  New (unseen): {len(new_articles)} articles")

    if not new_articles:
        logger.info("No new articles — nothing to process this run")
        return

    # Save all new raw articles regardless of whether they pass filtering
    save_raw_articles(new_articles)

    # ── Step 3: Run smart filter pipeline ─────────────────────────────────
    logger.info("Step 3: Running filter pipeline...")
    filtered_articles = run_filter_pipeline(new_articles)
    logger.info(f"  Passed filters: {len(filtered_articles)} articles")

    if not filtered_articles:
        logger.info("No articles passed filters — run complete")
        _log_summary(start_time, len(all_articles), len(new_articles), 0, 0)
        return

    # ── Step 4: Load recent context for richer AI output ──────────────────
    logger.info("Step 4: Loading recent stories for context...")
    recent_context = get_recent_outputs(limit=8)
    logger.info(f"  Loaded {len(recent_context)} recent stories as context")

    # ── Step 5: AI rewriting into Bangla ──────────────────────────────────
    logger.info("Step 5: Rewriting articles into Bangla...")
    output_stories = rewrite_all(filtered_articles, recent_context)
    logger.info(f"  Generated: {len(output_stories)} Bangla stories")

    if not output_stories:
        logger.warning("Rewriting produced no output — check GROQ_API_KEY")
        return

    # ── Step 6: Save output stories ───────────────────────────────────────
    logger.info("Step 6: Saving output stories...")
    save_output_stories(output_stories)

    # ── Step 7: Publish to Telegram (optional) ────────────────────────────
    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if telegram_token:
        logger.info("Step 7: Publishing to Telegram...")
        published_count = publish_all(output_stories)
        logger.info(f"  Published: {published_count} stories to Telegram")
    else:
        logger.info("Step 7: Telegram not configured — skipping publish")

    # ── Summary ───────────────────────────────────────────────────────────
    _log_summary(start_time, len(all_articles), len(new_articles),
                 len(filtered_articles), len(output_stories))


def _log_summary(start_time, total_fetched, new_articles, filtered, generated):
    end_time = datetime.now(timezone.utc)
    duration = (end_time - start_time).total_seconds()

    logger.info("=" * 60)
    logger.info("PIPELINE SUMMARY")
    logger.info(f"  Total fetched:    {total_fetched}")
    logger.info(f"  New (unseen):     {new_articles}")
    logger.info(f"  Passed filters:   {filtered}")
    logger.info(f"  Stories generated:{generated}")
    logger.info(f"  Duration:         {duration:.1f}s")
    logger.info("=" * 60)


if __name__ == "__main__":
    run_pipeline()
