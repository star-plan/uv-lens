from __future__ import annotations

import base64
import json

import httpx
import pytest
from packaging.version import Version

from uv_lens.index_client import IndexAuth, pick_latest_version


def test_build_headers_accept_and_auth_variants() -> None:
    """
    认证 header 构造应支持无认证/bearer/basic 三种情况，并始终带 Accept。
    """
    from uv_lens import index_client

    assert index_client._build_headers(None) == {"Accept": "application/json"}

    bearer = index_client._build_headers(IndexAuth(bearer_token="t"))
    assert bearer["Accept"] == "application/json"
    assert bearer["Authorization"] == "Bearer t"

    basic = index_client._build_headers(IndexAuth(basic_username="u", basic_password="p"))
    token = base64.b64encode(b"u:p").decode("ascii")
    assert basic["Accept"] == "application/json"
    assert basic["Authorization"] == f"Basic {token}"


def test_pick_latest_when_only_prereleases_returns_max_prerelease() -> None:
    """
    仅存在预发布版本时，默认策略仍应返回最大版本（无稳定版可选）。
    """
    data = {"releases": {"1.0.0rc1": [], "1.0.0rc2": []}, "info": {"version": "1.0.0rc2"}}
    assert pick_latest_version(data, include_prereleases=False) == Version("1.0.0rc2")


def test_pick_latest_ignores_invalid_versions() -> None:
    """
    无法解析的版本字符串应被跳过，不影响最终选择。
    """
    data = {"releases": {"bad!!!": [], "1.2.3": []}, "info": {"version": "bad!!!"}}
    assert pick_latest_version(data, include_prereleases=False) == Version("1.2.3")


@pytest.mark.asyncio
async def test_request_json_returns_404_without_error() -> None:
    """
    404 应返回 (None,404,None)，上层可将其视为 not found 回退。
    """
    from uv_lens.index_client import _request_json

    transport = httpx.MockTransport(lambda _req: httpx.Response(404, text="not found"))
    async with httpx.AsyncClient(transport=transport) as client:
        data, status, error = await _request_json(client, "https://x.test/pypi/demo/json", retries=0)
    assert data is None
    assert status == 404
    assert error is None


@pytest.mark.asyncio
async def test_request_json_http_error_status() -> None:
    """
    HTTP >= 400（非 404）应返回 error= http <code>。
    """
    from uv_lens.index_client import _request_json

    transport = httpx.MockTransport(lambda _req: httpx.Response(500, text="boom"))
    async with httpx.AsyncClient(transport=transport) as client:
        data, status, error = await _request_json(client, "https://x.test/pypi/demo/json", retries=0)
    assert data is None
    assert status == 500
    assert error == "http 500"


@pytest.mark.asyncio
async def test_request_json_invalid_json_returns_error() -> None:
    """
    JSON 解析失败时应返回 invalid json 错误信息。
    """
    from uv_lens.index_client import _request_json

    transport = httpx.MockTransport(
        lambda _req: httpx.Response(200, text="not json", headers={"Content-Type": "application/json"})
    )
    async with httpx.AsyncClient(transport=transport) as client:
        data, status, error = await _request_json(client, "https://x.test/pypi/demo/json", retries=0)
    assert data is None
    assert status is None
    assert error is not None
    assert error.startswith("invalid json:")


@pytest.mark.asyncio
async def test_request_json_retries_on_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    超时/网络错误应按 retries 重试，并在成功后返回数据。
    """
    from uv_lens.index_client import _request_json

    async def fake_sleep(_s: float) -> None:
        """
        避免真实 sleep，让重试测试更快更稳定。
        """
        return None

    monkeypatch.setattr("uv_lens.index_client.asyncio.sleep", fake_sleep)
    monkeypatch.setattr("uv_lens.index_client.random.random", lambda: 0.0)

    calls = {"n": 0}

    def handler(_req: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.TimeoutException("timeout")
        body = json.dumps({"releases": {"1.2.3": []}, "info": {"version": "1.2.3"}})
        return httpx.Response(200, text=body, headers={"Content-Type": "application/json"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        data, status, error = await _request_json(client, "https://x.test/pypi/demo/json", retries=2)

    assert calls["n"] == 2
    assert error is None
    assert status == 200
    assert data is not None
    assert data["info"]["version"] == "1.2.3"

