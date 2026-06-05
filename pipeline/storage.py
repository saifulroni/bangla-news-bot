"""
storage.py — Dual-backend storage: SQLite (default) or Google Sheets.

Set STORAGE_MODE=sheets in .env to use Google Sheets.
Default is SQLite (zero setup required).

SQLite schema:
  raw_articles   — everything fetched from RSS (before filtering)
  output_stories — final Bangla stories ready to publish

Google Sheets schema:
  Sheet "Raw"    — same as raw_articles table
  Sheet "Output" — same as output_stories table
"""

import os
import json
import sqlite3
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

STORAGE_MODE   = os.getenv("STORAGE_MODE", "sqlite").lower()
SQLITE_DB_PATH = Path("news_pipeline.sqlite")

# ── Google Sheets config (only used if STORAGE_MODE=sheets) ──────────────
GOOGLE_SHEET_ID              = os.getenv("GOOGLE_SHEET_ID", "")
GOOGLE_SERVICE_ACCOUNT_JSON  = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "service_account.json")


# ══════════════════════════════════════════════════════════════════════════════
# SQLite backend
# ══════════════════════════════════════════════════════════════════════════════

def _get_sqlite_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(SQLITE_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _init_sqlite():
    """Create tables if they don't exist."""
    conn = _get_sqlite_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS raw_articles (
            id            TEXT PRIMARY KEY,
            source        TEXT,
            tier          INTEGER,
            headline      TEXT,
            snippet       TEXT,
            url           TEXT UNIQUE,
            published_at  TEXT,
            fetched_at    TEXT,
            importance_score REAL,
            hf_score      REAL
        );

        CREATE TABLE IF NOT EXISTS output_stories (
            id                  TEXT PRIMARY KEY,
            original_update_id  TEXT,
            timestamp           TEXT,
            source              TEXT,
            url                 TEXT,
            original_headline   TEXT,
            headline            TEXT,
            caption             TEXT,
            story               TEXT,
            model               TEXT,
            published_at        TEXT,
            published_to        TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_output_timestamp
            ON output_stories(timestamp DESC);
    """)
    conn.commit()
    conn.close()


def sqlite_save_raw(articles: list[dict]):
    """Save raw articles to SQLite. Skips duplicates by URL."""
    _init_sqlite()
    conn = _get_sqlite_conn()
    inserted = 0
    for a in articles:
        try:
            conn.execute("""
                INSERT OR IGNORE INTO raw_articles
                (id, source, tier, headline, snippet, url, published_at, fetched_at, importance_score, hf_score)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                a["id"], a["source"], a.get("tier", 3),
                a["headline"], a.get("snippet", ""),
                a["url"], a.get("published_at"), a.get("fetched_at"),
                a.get("importance_score"), a.get("hf_score"),
            ))
            if conn.total_changes > inserted:
                inserted += 1
        except Exception as e:
            logger.warning(f"Failed to save raw article {a.get('id')}: {e}")
    conn.commit()
    conn.close()
    logger.info(f"Saved {inserted} new raw articles to SQLite")


def sqlite_save_output(stories: list[dict]):
    """Save output Bangla stories to SQLite."""
    _init_sqlite()
    conn = _get_sqlite_conn()
    for s in stories:
        try:
            conn.execute("""
                INSERT OR REPLACE INTO output_stories
                (id, original_update_id, timestamp, source, url, original_headline,
                 headline, caption, story, model)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                s["id"], s["original_update_id"], s["timestamp"],
                s["source"], s["url"], s["original_headline"],
                s["headline"], s["caption"], s["story"], s["model"],
            ))
        except Exception as e:
            logger.warning(f"Failed to save output story {s.get('id')}: {e}")
    conn.commit()
    conn.close()
    logger.info(f"Saved {len(stories)} stories to SQLite output")


def sqlite_get_recent_outputs(limit: int = 10) -> list[dict]:
    """Get the most recent output stories for use as context."""
    _init_sqlite()
    conn = _get_sqlite_conn()
    rows = conn.execute(
        "SELECT * FROM output_stories ORDER BY timestamp DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def sqlite_get_seen_urls() -> set[str]:
    """Get all URLs already in the raw_articles table."""
    _init_sqlite()
    conn = _get_sqlite_conn()
    rows = conn.execute("SELECT url FROM raw_articles").fetchall()
    conn.close()
    return {row["url"] for row in rows}


# ══════════════════════════════════════════════════════════════════════════════
# Google Sheets backend
# ══════════════════════════════════════════════════════════════════════════════

def _get_sheets_client():
    """Authenticate and return a gspread client."""
    import gspread
    from google.oauth2.service_account import Credentials

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_file(GOOGLE_SERVICE_ACCOUNT_JSON, scopes=scopes)
    return gspread.authorize(creds)


def sheets_save_raw(articles: list[dict]):
    """Append raw articles to 'Raw' sheet. Skips already-seen URLs."""
    gc = _get_sheets_client()
    sh = gc.open_by_key(GOOGLE_SHEET_ID)

    try:
        ws = sh.worksheet("Raw")
    except Exception:
        ws = sh.add_worksheet("Raw", rows=10000, cols=12)
        ws.append_row(["id", "source", "tier", "headline", "snippet",
                       "url", "published_at", "fetched_at", "importance_score", "hf_score"])

    # Get existing URLs to avoid duplicates
    try:
        existing = set(ws.col_values(6)[1:])  # Column F = url
    except Exception:
        existing = set()

    new_rows = []
    for a in articles:
        if a["url"] not in existing:
            new_rows.append([
                a["id"], a["source"], a.get("tier", 3),
                a["headline"], a.get("snippet", ""),
                a["url"], a.get("published_at", ""), a.get("fetched_at", ""),
                a.get("importance_score", ""), a.get("hf_score", ""),
            ])

    if new_rows:
        ws.append_rows(new_rows)
        logger.info(f"Appended {len(new_rows)} rows to Google Sheets 'Raw'")


def sheets_save_output(stories: list[dict]):
    """Append output stories to 'Output' sheet."""
    gc = _get_sheets_client()
    sh = gc.open_by_key(GOOGLE_SHEET_ID)

    try:
        ws = sh.worksheet("Output")
    except Exception:
        ws = sh.add_worksheet("Output", rows=10000, cols=12)
        ws.append_row(["id", "timestamp", "source", "url", "original_headline",
                       "headline", "caption", "story", "model"])

    rows = []
    for s in stories:
        rows.append([
            s["id"], s["timestamp"], s["source"], s["url"],
            s["original_headline"], s["headline"], s["caption"],
            s["story"], s["model"],
        ])

    if rows:
        ws.append_rows(rows)
        logger.info(f"Appended {len(rows)} stories to Google Sheets 'Output'")


def sheets_get_recent_outputs(limit: int = 10) -> list[dict]:
    """Get recent output stories from the 'Output' sheet."""
    gc = _get_sheets_client()
    sh = gc.open_by_key(GOOGLE_SHEET_ID)
    ws = sh.worksheet("Output")
    records = ws.get_all_records()
    return records[-limit:] if len(records) > limit else records


# ══════════════════════════════════════════════════════════════════════════════
# Unified API (routes to correct backend based on STORAGE_MODE)
# ══════════════════════════════════════════════════════════════════════════════

def save_raw_articles(articles: list[dict]):
    if STORAGE_MODE == "sheets":
        sheets_save_raw(articles)
    else:
        sqlite_save_raw(articles)


def save_output_stories(stories: list[dict]):
    if STORAGE_MODE == "sheets":
        sheets_save_output(stories)
    else:
        sqlite_save_output(stories)


def get_recent_outputs(limit: int = 10) -> list[dict]:
    if STORAGE_MODE == "sheets":
        return sheets_get_recent_outputs(limit)
    else:
        return sqlite_get_recent_outputs(limit)


def get_seen_urls() -> set[str]:
    """Only SQLite tracks this locally. Sheets backend relies on dedup."""
    if STORAGE_MODE == "sqlite":
        return sqlite_get_seen_urls()
    return set()
