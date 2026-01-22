from __future__ import annotations

from pathlib import Path

import pytest
from packaging.version import Version

from uv_lens.app import check_pyproject
from uv_lens.config import AppConfig
from uv_lens.index_client import IndexSettings, PackageLookupResult
from uv_lens.models import CheckStatus


@pytest.mark.asyncio
async def test_check_pyproject_builds_report_and_respects_exclude(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """
    check_pyproject 应组合解析/过滤/查询/评估流程，生成完整 Report，并正确处理 exclude。
    """
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """
[project]
name = "demo"
dependencies = [
  "validpkg==1.0.0",
  "range>=1",
  "unpinned",
  "not a requirement !!!",
]

[project.optional-dependencies]
extra = ["optpkg"]

[dependency-groups]
dev = ["devpkg>=0"]

[build-system]
requires = ["buildpkg>=0"]
        """.strip()
        + "\n",
        encoding="utf-8",
    )

    expected_query = ["buildpkg", "optpkg", "range", "unpinned", "validpkg"]

    async def fake_resolve_latest_versions(
        normalized_names: list[str],
        *,
        settings: IndexSettings,
        max_concurrency: int,
        cache,
        cache_ttl_s: int,
        refresh: bool,
        **kwargs,
    ):
        """
        替换真实 resolver，返回混合场景（成功/404/网络错误）。
        """
        assert normalized_names == expected_query
        assert settings.index_url == "https://primary.test/pypi"
        assert max_concurrency == 5
        assert cache is None
        assert refresh is False

        results = {
            "validpkg": PackageLookupResult(
                normalized_name="validpkg",
                index_url=settings.index_url,
                latest=Version("1.0.0"),
                not_found=False,
                error=None,
            ),
            "range": PackageLookupResult(
                normalized_name="range",
                index_url=settings.index_url,
                latest=Version("2.0.0"),
                not_found=False,
                error=None,
            ),
            "unpinned": PackageLookupResult(
                normalized_name="unpinned",
                index_url=settings.index_url,
                latest=Version("3.0.0"),
                not_found=False,
                error=None,
            ),
            "optpkg": PackageLookupResult(
                normalized_name="optpkg",
                index_url=None,
                latest=None,
                not_found=True,
                error=None,
            ),
            "buildpkg": PackageLookupResult(
                normalized_name="buildpkg",
                index_url=settings.index_url,
                latest=None,
                not_found=False,
                error="timeout",
            ),
        }
        stats = type("Stats", (), {"cache_hits": 0, "fetched": len(normalized_names)})
        return results, stats

    monkeypatch.setattr("uv_lens.app.resolve_latest_versions", fake_resolve_latest_versions)

    cfg = AppConfig(
        index=IndexSettings(index_url="https://primary.test/pypi"),
        max_concurrency=5,
        cache_ttl_s=0,
        use_cache=False,
        refresh=False,
        pin="exact",
        exclude=("devpkg",),
    )

    report = await check_pyproject(pyproject, config=cfg)
    assert report.pyproject_path == str(pyproject)
    assert report.cache_hits == 0
    assert report.fetched == len(expected_query)

    statuses = [i.status for i in report.items]
    assert CheckStatus.INVALID_REQUIREMENT in statuses
    assert CheckStatus.UP_TO_DATE in statuses
    assert CheckStatus.UPGRADE_AVAILABLE in statuses
    assert CheckStatus.UNPINNED in statuses
    assert CheckStatus.NOT_FOUND in statuses
    assert CheckStatus.NETWORK_ERROR in statuses

    names = [i.name for i in report.items if i.name]
    assert "devpkg" not in names

    unpinned_item = next(i for i in report.items if i.name == "unpinned")
    assert unpinned_item.suggestion == "unpinned==3.0.0"

