"""
tests/test_setup.py — Smoke tests to verify your setup before going live.

Run with:  python -m pytest tests/ -v
Or:        python tests/test_setup.py
"""

import os
import sys
import json
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_env_variables():
    """Check required environment variables are set."""
    print("\n--- Checking environment variables ---")
    from dotenv import load_dotenv
    load_dotenv()

    required = ["GROQ_API_KEY"]
    optional = ["HF_API_TOKEN", "TELEGRAM_BOT_TOKEN", "GOOGLE_SHEET_ID"]

    all_good = True
    for var in required:
        val = os.getenv(var, "")
        if val:
            print(f"  ✓ {var} is set")
        else:
            print(f"  ✗ {var} is MISSING — required!")
            all_good = False

    for var in optional:
        val = os.getenv(var, "")
        status = "set" if val else "not set (optional)"
        print(f"  {'✓' if val else '○'} {var}: {status}")

    assert all_good, "Missing required environment variables"


def test_rss_fetch():
    """Fetch one feed and verify we get articles back."""
    print("\n--- Testing RSS fetch ---")
    from pipeline.ingest import fetch_feed
    from pipeline.sources import RSS_SOURCES

    # Use BBC World as the test feed (reliable, no auth)
    bbc_source = next(s for s in RSS_SOURCES if "BBC" in s["name"])
    articles = fetch_feed(bbc_source)

    print(f"  Fetched {len(articles)} articles from {bbc_source['name']}")
    assert len(articles) > 0, "No articles fetched from BBC World"

    # Spot-check the schema
    a = articles[0]
    for field in ["id", "source", "headline", "url", "published_at"]:
        assert field in a and a[field], f"Missing field: {field}"

    print(f"  Sample headline: {articles[0]['headline'][:80]}")
    print("  ✓ RSS fetch working")


def test_importance_filter():
    """Verify keyword scoring works."""
    print("\n--- Testing importance filter ---")
    from pipeline.filter import _importance_score

    high_importance = {
        "headline": "BREAKING: President resigns amid coup crisis",
        "snippet": "Urgent: Military forces have seized control",
        "source": "Reuters", "tier": 1
    }
    low_importance = {
        "headline": "Local council approves new bus route",
        "snippet": "The council voted 5-3 in favour",
        "source": "Local Paper", "tier": 3
    }

    high_score = _importance_score(high_importance)
    low_score  = _importance_score(low_importance)

    print(f"  High importance score: {high_score:.1f} (expect > 5)")
    print(f"  Low importance score:  {low_score:.1f} (expect < 3)")

    assert high_score > 5, f"High importance score too low: {high_score}"
    assert low_score < high_score, "Scoring not distinguishing importance"
    print("  ✓ Importance filter working")


def test_groq_connection():
    """Make a minimal Groq API call to verify the key works."""
    print("\n--- Testing Groq API connection ---")
    from dotenv import load_dotenv
    load_dotenv()

    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key:
        print("  ○ Skipping — GROQ_API_KEY not set")
        return

    from groq import Groq
    client = Groq(api_key=api_key)

    response = client.chat.completions.create(
<<<<<<< HEAD
        model="llama3-70b-8192",
=======
        model="llama-3.3-70b-versatile",
>>>>>>> eb8ab960a4d2e032a6364395b31b39d8712a3e02
        messages=[{"role": "user", "content": 'Reply with just the word "OK" in Bangla.'}],
        max_tokens=20,
    )
    result = response.choices[0].message.content
    print(f"  Groq response: {result}")
    print("  ✓ Groq API connection working")


def test_sqlite_storage():
    """Verify SQLite storage initialises and reads/writes correctly."""
    print("\n--- Testing SQLite storage ---")
    import sqlite3

    # Use a temp database for testing
    os.environ["STORAGE_MODE"] = "sqlite"
    # Monkey-patch the path for testing
    import pipeline.storage as storage_mod
    original_path = storage_mod.SQLITE_DB_PATH
    storage_mod.SQLITE_DB_PATH = Path("test_pipeline.sqlite")

    test_article = {
        "id": "test001", "source": "Test", "tier": 1,
        "headline": "Test headline", "snippet": "Test snippet",
        "url": "https://example.com/test001",
        "published_at": "2024-01-01T00:00:00+00:00",
        "fetched_at": "2024-01-01T00:00:00+00:00",
        "importance_score": 5.0, "hf_score": 0.9,
    }

    storage_mod.sqlite_save_raw([test_article])
    seen = storage_mod.sqlite_get_seen_urls()
    assert "https://example.com/test001" in seen
    print("  ✓ SQLite save/read working")

    # Cleanup
    storage_mod.SQLITE_DB_PATH = original_path
    Path("test_pipeline.sqlite").unlink(missing_ok=True)


def test_full_pipeline_dry_run():
    """Run the full pipeline with a mock article (no real API calls)."""
    print("\n--- Full pipeline dry run (mock data) ---")
    from pipeline.filter import filter_by_importance
    from pipeline.sources import KEYWORD_WEIGHTS

    mock_articles = [
        {
            "id": "mock001",
            "source": "Reuters",
            "tier": 1,
            "headline": "BREAKING: Prime Minister resigns following election protests",
            "snippet": "The Prime Minister announced resignation amid developing crisis",
            "url": "https://reuters.com/mock001",
            "published_at": "2024-06-01T12:00:00+00:00",
            "fetched_at":   "2024-06-01T12:00:00+00:00",
        },
        {
            "id": "mock002",
            "source": "Local Blog",
            "tier": 3,
            "headline": "Five tips for better gardening",
            "snippet": "Gardening tips for your backyard",
            "url": "https://localblog.com/mock002",
            "published_at": "2024-06-01T12:00:00+00:00",
            "fetched_at":   "2024-06-01T12:00:00+00:00",
        },
    ]

    passed = filter_by_importance(mock_articles)
    assert len(passed) == 1, f"Expected 1 article to pass, got {len(passed)}"
    assert passed[0]["id"] == "mock001"
    print(f"  Filter correctly kept 1/2 articles")
    print("  ✓ Pipeline logic working")


if __name__ == "__main__":
    tests = [
        test_env_variables,
        test_rss_fetch,
        test_importance_filter,
        test_sqlite_storage,
        test_full_pipeline_dry_run,
        test_groq_connection,  # Last — makes real API call
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"  ✗ FAILED: {e}")
            failed += 1

    print(f"\n{'='*40}")
    print(f"Results: {passed} passed, {failed} failed")
    if failed == 0:
        print("All tests passed — you're ready to go live!")
    else:
        print("Fix the failures above before deploying.")
