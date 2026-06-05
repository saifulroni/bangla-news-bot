"""
download_model.py — Run this ONCE locally to download the embedding model
into the repo so GitHub Actions never needs to reach huggingface.co at runtime.

Usage:
    python download_model.py

This saves the model to ./models/all-MiniLM-L6-v2/
Commit that folder to git — it's ~90MB but makes the pipeline fully offline.
"""

from sentence_transformers import SentenceTransformer
from pathlib import Path

MODEL_NAME = "all-MiniLM-L6-v2"
SAVE_PATH  = Path("models") / MODEL_NAME

print(f"Downloading {MODEL_NAME}...")
model = SentenceTransformer(MODEL_NAME)
model.save(str(SAVE_PATH))
print(f"Saved to {SAVE_PATH}")
print(f"Size: {sum(f.stat().st_size for f in SAVE_PATH.rglob('*') if f.is_file()) / 1e6:.1f} MB")
print()
print("Next steps:")
print("  git add models/")
print('  git commit -m "Add embedding model for offline deduplication"')
print("  git push")
