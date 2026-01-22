from __future__ import annotations

import json

import httpx
import pytest
from packaging.version import Version

from uv_lens.index_client import IndexSettings, fetch_latest_from_indexes, pick_latest_version


def test_pick_latest_filters_prerelease_by_default() -> None:
    """
    默认应过滤预发布版本，优先选择最新稳定版。
    """
    data = {"releases": {"1.0.0": [], "2.0.0rc1": []}, "info": {"version": "2.0.0rc1"}}
    assert pick_latest_version(data, include_prereleases=False) == Version("1.0.0")
    assert pick_latest_version(data, include_prereleases=True) == Version("2.0.0rc1")


@pytest.mark.asyncio
async def test_fetch_latest_fallback_to_extra_index() -> None:
    """
    主索引 404 时，应回退到 extra index 并成功解析最新版本。
    """

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "primary.test":
            return httpx.Response(404, text="not found")
        body = json.dumps({"releases": {"1.2.3": []}, "info": {"version": "1.2.3"}})
        return httpx.Response(200, text=body, headers={"Content-Type": "application/json"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        settings = IndexSettings(index_url="https://primary.test/pypi", extra_index_urls=("https://extra.test/pypi",))
        res = await fetch_latest_from_indexes("demo", settings=settings, client=client)
    assert res.latest == Version("1.2.3")
    assert res.index_url == "https://extra.test/pypi"
