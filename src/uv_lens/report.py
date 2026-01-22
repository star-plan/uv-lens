from __future__ import annotations

from dataclasses import dataclass

from packaging.version import Version

from uv_lens.models import CheckStatus, DependencyKind


@dataclass(frozen=True, slots=True)
class ReportItem:
    """
    单条依赖检查结果。
    """

    kind: DependencyKind
    group: str
    name: str
    raw: str
    latest: Version | None
    status: CheckStatus
    suggestion: str | None
    index_url: str | None
    error: str | None


@dataclass(frozen=True, slots=True)
class Report:
    """
    一次检查的完整报告。
    """

    pyproject_path: str
    items: list[ReportItem]
    cache_hits: int
    fetched: int
