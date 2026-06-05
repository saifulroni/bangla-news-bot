"""
filter.py — Three-stage filter pipeline:

Stage 1: Keyword + source scoring  → fast, eliminates ~80% of noise
Stage 2: Zero-shot classification  → HuggingFace BART (free tier)
Stage 3: Vector deduplication      → sentence-transformers cosine similarity

Only articles passing all three stages proceed to AI rewriting.
"""

import os
import json
import time
import logging
import sqlite3
from pathlib import Path

import numpy as np
import requests

from .sources import KEYWORD_WEIGHTS, TIER_BONUSES

logger = logging.getLogger(__name__)

# ── Config (override via environment variables) ────────────────────────────
IMPORTANCE_THRESHOLD = float(os.getenv("IMPORTANCE_SCORE_THRESHOLD", "3.0"))
HF_THRESHOLD         = float(os.getenv("HF_CLASSIFICATION_THRESHOLD", "0.55"))
DEDUP_THRESHOLD      = float(os.getenv("DEDUP_SIMILARITY_THRESHOLD", "0.85"))
HF_API_TOKEN         = os.getenv("HF_API_TOKEN", "")
DEDUP_BUFFER_SIZE    = 200   # How many recent embeddings to keep in memory
DEDUP_DB_PATH        = Path("dedup_cache.sqlite")

# HuggingFace Inference API endpoint
HF_ENDPOINT = "https://api-inference.huggingface.co/models/facebook/bart-large-mnli"
<<<<<<< HEAD
# Sentence transformer model (runs locally on CPU)
EMBED_MODEL_NAME = "all-MiniLM-L6-v2"
=======

# Sentence transformer model — loaded from local path (committed to repo).
# Fall back to HuggingFace download only if local path doesn't exist.
LOCAL_MODEL_PATH = Path("models/all-MiniLM-L6-v2")
EMBED_MODEL_NAME = str(LOCAL_MODEL_PATH) if LOCAL_MODEL_PATH.exists() else "all-MiniLM-L6-v2"

# When running in GitHub Actions, skip the HuggingFace Inference API entirely
# (network access to huggingface.co is blocked on GH runners).
# Zero-shot classification still works fine locally.
IS_GITHUB_ACTIONS = os.getenv("GITHUB_ACTIONS") == "true"
>>>>>>> eb8ab960a4d2e032a6364395b31b39d8712a3e02

# Lazy-loaded globals (loaded once per process, not per article)
_embed_model = None
_dedup_store: list[tuple[str, np.ndarray]] = []   # list of (article_id, embedding)


# ══════════════════════════════════════════════════════════════════════════════
# STAGE 1: Keyword + source importance scoring
# ══════════════════════════════════════════════════════════════════════════════

def _importance_score(article: dict) -> float:
    """
    Calculate an importance score for an article based on:
    - Keyword matches in headline and snippet
    - Source tier bonus
    Returns a float; articles below IMPORTANCE_THRESHOLD are filtered out.
    """
    text = (article["headline"] + " " + article["snippet"]).lower()
    keyword_score = 0.0

    for keyword, weight in KEYWORD_WEIGHTS.items():
        if keyword in text:
            keyword_score += weight

    tier_bonus = TIER_BONUSES.get(article.get("tier", 3), 0.0)
    total = keyword_score + tier_bonus

    logger.debug(f"Score {total:.1f} | {article['headline'][:60]}")
    return total


def filter_by_importance(articles: list[dict]) -> list[dict]:
    """Stage 1: Keep only articles above the importance score threshold."""
    passed = []
    for article in articles:
        score = _importance_score(article)
        article["importance_score"] = round(score, 2)
        if score >= IMPORTANCE_THRESHOLD:
            passed.append(article)

    logger.info(f"Stage 1 (keyword): {len(passed)}/{len(articles)} passed")
    return passed


# ══════════════════════════════════════════════════════════════════════════════
# STAGE 2: Zero-shot classification via HuggingFace Inference API
# ══════════════════════════════════════════════════════════════════════════════

def _classify_batch(headlines: list[str]) -> list[float]:
    """
    Send a batch of headlines to HuggingFace zero-shot classification.
    Returns a list of confidence scores for "breaking political news".
<<<<<<< HEAD
    Falls back to 1.0 (pass all) if the API is unavailable.
    """
=======
    Falls back to 1.0 (pass all) if the API is unavailable or blocked.
    """
    if IS_GITHUB_ACTIONS:
        # HuggingFace API is unreachable from GitHub Actions runners.
        # Keyword scoring (Stage 1) already handled filtering — pass all through.
        return [1.0] * len(headlines)

>>>>>>> eb8ab960a4d2e032a6364395b31b39d8712a3e02
    if not HF_API_TOKEN:
        logger.warning("HF_API_TOKEN not set — skipping zero-shot classification")
        return [1.0] * len(headlines)

    headers = {"Authorization": f"Bearer {HF_API_TOKEN}"}
    payload = {
        "inputs": headlines,
        "parameters": {
            "candidate_labels": [
                "breaking political news",
                "opinion or analysis",
                "sports or entertainment",
                "business or economics",
                "other news"
            ],
            "multi_label": False,
        }
    }

    try:
        resp = requests.post(HF_ENDPOINT, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        results = resp.json()

        # Handle both single result (dict) and batch result (list)
        if isinstance(results, dict):
            results = [results]

        scores = []
        for r in results:
            labels = r.get("labels", [])
            label_scores = r.get("scores", [])
            score_map = dict(zip(labels, label_scores))
            scores.append(score_map.get("breaking political news", 0.0))
        return scores

    except Exception as e:
        logger.warning(f"HuggingFace API error: {e} — passing all articles through")
        return [1.0] * len(headlines)


def filter_by_classification(articles: list[dict]) -> list[dict]:
    """
    Stage 2: Use zero-shot classification to catch important stories
    that keyword scoring might miss. Processes in batches of 8.
    """
    if not articles:
        return []

    BATCH_SIZE = 8
    passed = []

    for i in range(0, len(articles), BATCH_SIZE):
        batch = articles[i:i + BATCH_SIZE]
        headlines = [a["headline"] for a in batch]
        scores = _classify_batch(headlines)

        for article, score in zip(batch, scores):
            article["hf_score"] = round(score, 3)
            if score >= HF_THRESHOLD:
                passed.append(article)

        # Respect free tier rate limits
        if i + BATCH_SIZE < len(articles):
            time.sleep(1.5)

    logger.info(f"Stage 2 (zero-shot): {len(passed)}/{len(articles)} passed")
    return passed


# ══════════════════════════════════════════════════════════════════════════════
# STAGE 3: Vector deduplication
# ══════════════════════════════════════════════════════════════════════════════

def _load_embed_model():
<<<<<<< HEAD
    """Lazy-load the sentence transformer model (only once per process)."""
    global _embed_model
    if _embed_model is None:
        from sentence_transformers import SentenceTransformer
        logger.info("Loading embedding model all-MiniLM-L6-v2...")
=======
    """
    Lazy-load the sentence transformer model (only once per process).
    Uses the local ./models/ copy if present; otherwise downloads from HuggingFace.
    On GitHub Actions the local copy MUST exist (run download_model.py first).
    """
    global _embed_model
    if _embed_model is None:
        from sentence_transformers import SentenceTransformer
        source = f"local repo ({EMBED_MODEL_NAME})" if LOCAL_MODEL_PATH.exists() else "HuggingFace (downloading...)"
        logger.info(f"Loading embedding model from {source}")
>>>>>>> eb8ab960a4d2e032a6364395b31b39d8712a3e02
        _embed_model = SentenceTransformer(EMBED_MODEL_NAME)
    return _embed_model


def _load_dedup_cache():
    """Load recent embeddings from SQLite into the in-memory buffer."""
    global _dedup_store
    if DEDUP_DB_PATH.exists():
        conn = sqlite3.connect(DEDUP_DB_PATH)
        rows = conn.execute(
            "SELECT article_id, embedding FROM dedup_cache ORDER BY created_at DESC LIMIT ?",
            (DEDUP_BUFFER_SIZE,)
        ).fetchall()
        conn.close()
        _dedup_store = [(row[0], np.frombuffer(row[1], dtype=np.float32)) for row in rows]
        logger.info(f"Loaded {len(_dedup_store)} embeddings from dedup cache")


def _save_to_dedup_cache(article_id: str, embedding: np.ndarray):
    """Save a new embedding to the SQLite dedup cache."""
    conn = sqlite3.connect(DEDUP_DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS dedup_cache (
            article_id TEXT PRIMARY KEY,
            embedding BLOB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute(
        "INSERT OR IGNORE INTO dedup_cache (article_id, embedding) VALUES (?, ?)",
        (article_id, embedding.tobytes())
    )
    # Keep cache from growing indefinitely
    conn.execute("""
        DELETE FROM dedup_cache WHERE article_id NOT IN (
            SELECT article_id FROM dedup_cache ORDER BY created_at DESC LIMIT ?
        )
    """, (DEDUP_BUFFER_SIZE * 2,))
    conn.commit()
    conn.close()


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two embedding vectors."""
    dot = np.dot(a, b)
    norm = np.linalg.norm(a) * np.linalg.norm(b)
    return float(dot / norm) if norm > 0 else 0.0


def filter_by_deduplication(articles: list[dict]) -> list[dict]:
    """
    Stage 3: Generate embeddings for each article headline and compare
    against recent headlines. Skip if cosine similarity > DEDUP_THRESHOLD.
    """
    if not articles:
        return []

    model = _load_embed_model()
    _load_dedup_cache()

    headlines = [a["headline"] for a in articles]
    embeddings = model.encode(headlines, convert_to_numpy=True, show_progress_bar=False)

    passed = []
    for article, embedding in zip(articles, embeddings):
        # Check against all embeddings in the buffer
        max_sim = 0.0
        most_similar_id = None

        for cached_id, cached_emb in _dedup_store:
            sim = _cosine_similarity(embedding, cached_emb)
            if sim > max_sim:
                max_sim = sim
                most_similar_id = cached_id

        article["max_similarity"] = round(max_sim, 3)
        article["similar_to"] = most_similar_id

        if max_sim >= DEDUP_THRESHOLD:
            logger.info(f"DUPLICATE (sim={max_sim:.2f}): {article['headline'][:60]}")
            continue

        # New unique article — add to buffer and cache
        _dedup_store.append((article["id"], embedding))
        if len(_dedup_store) > DEDUP_BUFFER_SIZE:
            _dedup_store.pop(0)  # Remove oldest

        _save_to_dedup_cache(article["id"], embedding)
        passed.append(article)

    logger.info(f"Stage 3 (dedup): {len(passed)}/{len(articles)} passed")
    return passed


# ══════════════════════════════════════════════════════════════════════════════
# Combined filter pipeline
# ══════════════════════════════════════════════════════════════════════════════

def run_filter_pipeline(articles: list[dict]) -> list[dict]:
    """
    Run all three filter stages in sequence.
    Returns only articles that pass all stages.
    """
    logger.info(f"Starting filter pipeline with {len(articles)} articles")

    articles = filter_by_importance(articles)
    if not articles:
        logger.info("No articles passed importance filter — nothing to process")
        return []

    articles = filter_by_classification(articles)
    if not articles:
        logger.info("No articles passed classification filter")
        return []

    articles = filter_by_deduplication(articles)
    logger.info(f"Filter pipeline complete: {len(articles)} articles to rewrite")
    return articles
