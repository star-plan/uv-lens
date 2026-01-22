from __future__ import annotations

from pathlib import Path

import pytest
from packaging.version import Version

from uv_lens.cache import CacheDB, index_scope_key
from uv_lens.index_client import IndexSettings, PackageLookupResult
from uv_lens.resolver import resolve_latest_versions


@pytest.mark.asyncio
async def test_resolve_latest_uses_cache_when_available(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """
    refresh=False 且缓存命中时，应直接使用缓存并减少网络查询次数。
    """
    settings = IndexSettings(index_url="https://primary.test/pypi", extra_index_urls=("https://extra.test/pypi",))
    scope = index_scope_key(settings.index_url, settings.extra_index_urls)
    db = CacheDB(tmp_path / "cache.sqlite3")
    try:
        db.set(
            scope=scope,
            normalized_name="pkg1",
            latest=Version("1.0.0"),
            resolved_index_url=settings.index_url,
            not_found=False,
            error=None,
        )

        called: list[str] = []

        async def fake_fetch_latest_from_indexes(
            normalized_name: str, *, settings: IndexSettings, client
        ) -> PackageLookupResult:
            """
            替换真实网络查询，返回固定版本并记录调用次数。
            """
            called.append(normalized_name)
            return PackageLookupResult(
                normalized_name=normalized_name,
                index_url=settings.index_url,
                latest=Version("2.0.0"),
                not_found=False,
                error=None,
            )

        monkeypatch.setattr("uv_lens.resolver.fetch_latest_from_indexes", fake_fetch_latest_from_indexes)

        results, stats = await resolve_latest_versions(
            ["pkg1", "pkg2"],
            settings=settings,
            max_concurrency=10,
            cache=db,
            cache_ttl_s=3600,
            refresh=False,
        )

        assert stats.total == 2
        assert stats.cache_hits == 1
        assert stats.fetched == 1
        assert called == ["pkg2"]
        assert results["pkg1"].latest == Version("1.0.0")
        assert results["pkg2"].latest == Version("2.0.0")

        cached_pkg2 = db.get(scope=scope, normalized_name="pkg2", ttl_s=0)
        assert cached_pkg2 is not None
        assert cached_pkg2.latest == Version("2.0.0")
    finally:
        db.close()


@pytest.mark.asyncio
async def test_resolve_latest_refresh_bypasses_cache(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """
    refresh=True 时应忽略缓存并重新查询所有包。
    """
    settings = IndexSettings(index_url="https://primary.test/pypi")
    scope = index_scope_key(settings.index_url, settings.extra_index_urls)
    db = CacheDB(tmp_path / "cache.sqlite3")
    try:
        db.set(
            scope=scope,
            normalized_name="pkg1",
            latest=Version("1.0.0"),
            resolved_index_url=settings.index_url,
            not_found=False,
            error=None,
        )

        called: list[str] = []

        async def fake_fetch_latest_from_indexes(
            normalized_name: str, *, settings: IndexSettings, client
        ) -> PackageLookupResult:
            """
            用于验证 refresh 时无论是否有缓存都会发起查询。
            """
            called.append(normalized_name)
            return PackageLookupResult(
                normalized_name=normalized_name,
                index_url=settings.index_url,
                latest=Version("9.9.9"),
                not_found=False,
                error=None,
            )

        monkeypatch.setattr("uv_lens.resolver.fetch_latest_from_indexes", fake_fetch_latest_from_indexes)

        results, stats = await resolve_latest_versions(
            ["pkg1", "pkg2"],
            settings=settings,
            max_concurrency=0,
            cache=db,
            cache_ttl_s=3600,
            refresh=True,
        )

        assert stats.cache_hits == 0
        assert stats.fetched == 2
        assert sorted(called) == ["pkg1", "pkg2"]
        assert results["pkg1"].latest == Version("9.9.9")
        assert results["pkg2"].latest == Version("9.9.9")
    finally:
        db.close()

