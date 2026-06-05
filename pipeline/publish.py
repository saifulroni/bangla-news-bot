"""
publish.py — Optional Telegram publishing.

Sends output stories to a Telegram channel.
Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHANNEL_ID in .env to enable.

Format sent to Telegram:
  📰 [BANGLA HEADLINE]

  [CAPTION]

  [STORY]

  🔗 Source: [URL]
"""

import os
import time
import logging
import requests

logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN  = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID", "")
TELEGRAM_API_URL    = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


def _format_message(story: dict) -> str:
    """Format a story dict into a Telegram message string."""
    parts = [
        f"📰 *{story['headline']}*",
        "",
        story["caption"],
        "",
        story["story"],
        "",
        f"🔗 [সূত্র: {story['source']}]({story['url']})",
    ]
    return "\n".join(parts)


def send_to_telegram(story: dict) -> bool:
    """
    Send one story to the configured Telegram channel.
    Returns True on success, False on failure.
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHANNEL_ID:
        logger.debug("Telegram not configured — skipping publish")
        return False

    message = _format_message(story)

    try:
        resp = requests.post(
            f"{TELEGRAM_API_URL}/sendMessage",
            json={
                "chat_id":    TELEGRAM_CHANNEL_ID,
                "text":       message,
                "parse_mode": "Markdown",
                "disable_web_page_preview": False,
            },
            timeout=10,
        )
        resp.raise_for_status()
        logger.info(f"Published to Telegram: {story['headline'][:50]}")
        return True

    except Exception as e:
        logger.error(f"Telegram publish failed: {e}")
        return False


def publish_all(stories: list[dict]) -> int:
    """
    Publish all stories to Telegram.
    Returns count of successfully published stories.
    Adds 3s delay between posts to avoid flooding.
    """
    published = 0
    for i, story in enumerate(stories):
        if send_to_telegram(story):
            published += 1
        if i < len(stories) - 1:
            time.sleep(3)

    return published
