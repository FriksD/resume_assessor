"""内存 MD5 缓存模块。

存储已解析的简历数据，避免重复处理相同的 PDF 文件。
每条记录以 MD5(file_bytes) 为键，存储：
  {"raw_text": str, "extracted": dict}

限制：
- 仅存在于当前 FC 实例进程中。
- 当缓存数量超过 MAX_SIZE 时，采用 FIFO 策略淘汰最旧的条目。
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
