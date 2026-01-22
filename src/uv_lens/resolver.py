from __future__ import annotations

import asyncio
from dataclasses import dataclass

from uv_lens.cache import CacheDB, CacheEntry, index_scope_key
from uv_lens.index_client import IndexSettings, PackageLookupResult, create_async_client, fetch_latest_from_indexes


@dataclass(frozen=True, slots=True)
class ResolveStats:
    """
    版本查询统计信息。
    """

    total: int
    cache_hits: int
    fetched: int


def _result_from_cache(normalized_name: str, entry: CacheEntry) -> PackageLookupResult:
    """
    将缓存条目转换为查询结果结构。
    """
    return PackageLookupResult(
        normalized_name=normalized_name,
        index_url=entry.resolved_index_url,
        latest=entry.latest,
        not_found=entry.not_found,
        error=entry.error,
    )


async def resolve_latest_versions(
    normalized_names: list[str],
    *,
    settings: IndexSettings,
    max_concurrency: int,
    cache: CacheDB | None,
    cache_ttl_s: int,
    refresh: bool,
) -> tuple[dict[str, PackageLookupResult], ResolveStats]:
    """
    并行解析多个包的最新版本，支持用户目录全局缓存与增量更新。
    """
    scope = index_scope_key(settings.index_url, settings.extra_index_urls)
    results: dict[str, PackageLookupResult] = {}

    cache_hits = 0
    to_fetch: list[str] = []
    for name in normalized_names:
        if cache is None or refresh:
            to_fetch.append(name)
            continue

        entry = cache.get(scope=scope, normalized_name=name, ttl_s=cache_ttl_s)
        if entry is None:
            to_fetch.append(name)
            continue

        cache_hits += 1
        results[name] = _result_from_cache(name, entry)

    sem = asyncio.Semaphore(max(1, max_concurrency))
    async with create_async_client(settings) as client:

        async def worker(n: str) -> None:
            async with sem:
                res = await fetch_latest_from_indexes(n, settings=settings, client=client)
                results[n] = res
                if cache is not None:
                    cache.set(
                        scope=scope,
                        normalized_name=n,
                        latest=res.latest,
                        resolved_index_url=res.index_url,
                        not_found=res.not_found,
                        error=res.error,
                    )

        await asyncio.gather(*(worker(n) for n in to_fetch))

    stats = ResolveStats(total=len(normalized_names), cache_hits=cache_hits, fetched=len(to_fetch))
    return results, stats
