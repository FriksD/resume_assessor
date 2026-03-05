"""In-memory MD5-keyed cache.

Stores parsed resume data so the same PDF is not re-processed.
Each entry is keyed by MD5(file_bytes) and holds:
  {"raw_text": str, "extracted": dict}

Limitations:
- Lives only in the current FC instance process.
- Eviction is FIFO when size exceeds MAX_SIZE.
- For production, swap get_cache/set_cache to Redis calls.
"""

MAX_SIZE = 500
_cache: dict = {}


def get_cache(file_hash: str) -> dict | None:
    return _cache.get(file_hash)


def set_cache(file_hash: str, data: dict) -> None:
    if len(_cache) >= MAX_SIZE:
        oldest_key = next(iter(_cache))
        del _cache[oldest_key]
    _cache[file_hash] = data
