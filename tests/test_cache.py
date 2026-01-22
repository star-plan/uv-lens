from __future__ import annotations

from pathlib import Path

from packaging.version import Version

from uv_lens.cache import CacheDB, index_scope_key


def test_cache_set_get_with_ttl(tmp_path: Path) -> None:
    """
    缓存写入后，在 TTL 内应可读取；TTL=0 表示不过期。
    """
    db = CacheDB(tmp_path / "cache.sqlite3")
    try:
        scope = index_scope_key("https://pypi.org/pypi", ())
        db.set(
            scope=scope,
            normalized_name="httpx",
            latest=Version("0.27.0"),
            resolved_index_url="https://pypi.org/pypi",
            not_found=False,
            error=None,
        )
        entry = db.get(scope=scope, normalized_name="httpx", ttl_s=3600)
        assert entry is not None
        assert entry.latest == Version("0.27.0")

        entry2 = db.get(scope=scope, normalized_name="httpx", ttl_s=0)
        assert entry2 is not None
    finally:
        db.close()
