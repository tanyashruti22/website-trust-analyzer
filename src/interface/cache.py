"""
Phase 6b: Simple result caching.

If multiple users check the same URL, we shouldn't re-run the full pipeline
(2 LLM calls + WHOIS + scraping) every single time - that wastes API quota
and slows things down under concurrent load. This caches results to disk
with a time-to-live, so popular URLs get answered instantly after the first
real analysis.
"""

import hashlib
import json
import time
from pathlib import Path

CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "cache"
CACHE_TTL_SECONDS = 60 * 60 * 6  # 6 hours - long enough to help under load, short enough to stay fresh


def _cache_path_for(url: str) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(url.encode()).hexdigest()
    return CACHE_DIR / f"{key}.json"


def get_cached(url: str) -> dict | None:
    """Return a cached result if one exists and hasn't expired, else None."""
    path = _cache_path_for(url)
    if not path.exists():
        return None

    try:
        with open(path, encoding="utf-8") as f:
            entry = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None

    age = time.time() - entry["cached_at"]
    if age > CACHE_TTL_SECONDS:
        return None  # expired

    return entry["result"]


def set_cached(url: str, result: dict) -> None:
    """Save a result to the cache."""
    path = _cache_path_for(url)
    entry = {"cached_at": time.time(), "url": url, "result": result}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(entry, f)