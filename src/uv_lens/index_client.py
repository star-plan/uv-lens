from __future__ import annotations

import asyncio
import base64
import random
from dataclasses import dataclass
from typing import Any

import httpx
from packaging.version import InvalidVersion, Version


@dataclass(frozen=True, slots=True)
class IndexAuth:
    """
    私有索引认证配置。
    """

    bearer_token: str | None = None
    basic_username: str | None = None
    basic_password: str | None = None


@dataclass(frozen=True, slots=True)
class IndexSettings:
    """
    包索引查询配置。
    """

    index_url: str
    extra_index_urls: tuple[str, ...] = ()
    timeout_s: float = 10.0
    retries: int = 2
    include_prereleases: bool = False
    auth: IndexAuth | None = None


@dataclass(frozen=True, slots=True)
class PackageLookupResult:
    """
    单个包的查询结果（最新版本或错误信息）。
    """

    normalized_name: str
    index_url: str | None
    latest: Version | None
    not_found: bool
    error: str | None


def _build_headers(auth: IndexAuth | None) -> dict[str, str]:
    """
    基于认证配置构造 HTTP Header。
    """
    headers: dict[str, str] = {"Accept": "application/json"}
    if not auth:
        return headers

    if auth.bearer_token:
        headers["Authorization"] = f"Bearer {auth.bearer_token}"
        return headers

    if auth.basic_username is not None and auth.basic_password is not None:
        token = f"{auth.basic_username}:{auth.basic_password}".encode("utf-8")
        headers["Authorization"] = f"Basic {base64.b64encode(token).decode('ascii')}"
        return headers

    return headers


def _candidate_versions_from_pypi_json(data: dict[str, Any]) -> list[Version]:
    """
    从 PyPI JSON API 响应中提取所有可解析的版本列表。
    """
    versions: list[Version] = []
    releases = data.get("releases")
    if isinstance(releases, dict):
        for raw_version in releases.keys():
            try:
                versions.append(Version(str(raw_version)))
            except InvalidVersion:
                continue

    info = data.get("info")
    if isinstance(info, dict) and "version" in info:
        try:
            versions.append(Version(str(info["version"])))
        except InvalidVersion:
            pass

    return versions


def pick_latest_version(data: dict[str, Any], *, include_prereleases: bool) -> Version | None:
    """
    从 PyPI JSON API 响应中选择“最新稳定版本”（默认过滤 pre-release）。
    """
    candidates = _candidate_versions_from_pypi_json(data)
    if not candidates:
        return None

    if include_prereleases:
        return max(candidates)

    stable = [v for v in candidates if not v.is_prerelease and not v.is_devrelease]
    return max(stable) if stable else max(candidates)


async def _request_json(
    client: httpx.AsyncClient,
    url: str,
    *,
    retries: int,
) -> tuple[dict[str, Any] | None, int | None, str | None]:
    """
    请求 JSON 并返回 (data, status_code, error)。
    """
    attempt = 0
    while True:
        try:
            resp = await client.get(url)
            if resp.status_code == 404:
                return None, 404, None
            if resp.status_code >= 400:
                return None, resp.status_code, f"http {resp.status_code}"
            return resp.json(), resp.status_code, None
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            if attempt >= retries:
                return None, None, str(exc)
            backoff = (2**attempt) * 0.25 + random.random() * 0.25
            attempt += 1
            await asyncio.sleep(backoff)
        except ValueError as exc:
            return None, None, f"invalid json: {exc}"


def _build_pypi_json_url(index_url: str, normalized_name: str) -> str:
    """
    生成 PyPI JSON API 的请求 URL。
    """
    base = index_url.rstrip("/")
    return f"{base}/{normalized_name}/json"


async def fetch_latest_from_indexes(
    normalized_name: str,
    *,
    settings: IndexSettings,
    client: httpx.AsyncClient,
) -> PackageLookupResult:
    """
    依次从 index_url 与 extra_index_urls 查询包的最新版本。
    """
    urls = (settings.index_url, *settings.extra_index_urls)
    last_error: str | None = None

    for base in urls:
        url = _build_pypi_json_url(base, normalized_name)
        data, status, error = await _request_json(client, url, retries=settings.retries)
        if status == 404:
            last_error = None
            continue
        if data is None:
            last_error = error or "request failed"
            continue
        if status is not None and status >= 400:
            last_error = f"http {status}"
            continue

        latest = pick_latest_version(data, include_prereleases=settings.include_prereleases)
        return PackageLookupResult(
            normalized_name=normalized_name,
            index_url=base,
            latest=latest,
            not_found=False,
            error=None if latest else "no version found",
        )

    return PackageLookupResult(
        normalized_name=normalized_name,
        index_url=None,
        latest=None,
        not_found=last_error is None,
        error=last_error,
    )


def create_async_client(settings: IndexSettings) -> httpx.AsyncClient:
    """
    创建用于访问索引的 AsyncClient。
    """
    headers = _build_headers(settings.auth)
    timeout = httpx.Timeout(settings.timeout_s)
    return httpx.AsyncClient(headers=headers, timeout=timeout, follow_redirects=True)
