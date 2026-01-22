from __future__ import annotations

from pathlib import Path

import pytest
from packaging.version import Version

from uv_lens.cache import CacheDB, index_scope_key


def test_cache_ttl_expiry(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """
    ttl_s > 0 且超过过期时间时应返回 None；ttl_s=0 表示永不过期。
    """
    db = CacheDB(tmp_path / "cache.sqlite3")
    try:
        scope = index_scope_key("https://pypi.org/pypi", ())
        monkeypatch.setattr("uv_lens.cache.time.time", lambda: 1000.0)
        db.set(
            scope=scope,
            normalized_name="demo",
            latest=Version("1.0.0"),
            resolved_index_url="https://pypi.org/pypi",
            not_found=False,
            error=None,
        )

        monkeypatch.setattr("uv_lens.cache.time.time", lambda: 1000.0 + 4000.0)
        assert db.get(scope=scope, normalized_name="demo", ttl_s=3600) is None
        entry = db.get(scope=scope, normalized_name="demo", ttl_s=0)
        assert entry is not None
        assert entry.latest == Version("1.0.0")
    finally:
        db.close()


def test_cache_invalid_version_string_is_treated_as_none(tmp_path: Path) -> None:
    """
    缓存中若存在无法解析的 latest 字符串，应返回 latest=None 而不是抛异常。
    """
    db = CacheDB(tmp_path / "cache.sqlite3")
    try:
        scope = index_scope_key("https://pypi.org/pypi", ())
        db.set(
            scope=scope,
            normalized_name="demo",
            latest=Version("1.0.0"),
            resolved_index_url="https://pypi.org/pypi",
            not_found=False,
            error=None,
        )
        db._conn.execute(
            "UPDATE package_cache SET latest = ? WHERE scope = ? AND name = ?",
            ("bad!!!", scope, "demo"),
        )
        db._conn.commit()

        entry = db.get(scope=scope, normalized_name="demo", ttl_s=0)
        assert entry is not None
        assert entry.latest is None
    finally:
        db.close()


def test_index_scope_key_normalizes_urls() -> None:
    """
    index_scope_key 应去掉空白与尾部斜杠，确保同配置生成同一缓存 scope。
    """
    key = index_scope_key(" https://primary.test/pypi/ ", ("https://extra.test/pypi///",))
    assert key == "https://primary.test/pypi|https://extra.test/pypi"

