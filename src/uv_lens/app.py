from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Callable

from packaging.version import Version
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn

from uv_lens.cache import CacheDB, default_cache_path
from uv_lens.config import AppConfig
from uv_lens.models import CheckStatus, DependencyItem
from uv_lens.names import normalize_project_name
from uv_lens.pyproject import extract_dependencies, load_pyproject_data
from uv_lens.report import Report, ReportItem
from uv_lens.resolver import resolve_latest_versions
from uv_lens.versions import evaluate_requirement_against_latest


def _collect_dependency_items(dep_sets: list[list[DependencyItem]]) -> list[DependencyItem]:
    """
    将多个依赖列表拼接为单个列表。
    """
    items: list[DependencyItem] = []
    for deps in dep_sets:
        items.extend(deps)
    return items


def _all_items_from_pyproject(pyproject_path: Path) -> list[DependencyItem]:
    """
    读取 pyproject.toml 并抽取所有依赖项列表。
    """
    data = load_pyproject_data(pyproject_path)
    deps = extract_dependencies(data)
    dev_items = _collect_dependency_items(list(deps.dev_groups.values()))
    opt_items = _collect_dependency_items(list(deps.optional.values()))
    return _collect_dependency_items([deps.project, dev_items, opt_items, deps.build_system])


async def check_pyproject(
    pyproject_path: Path,
    *,
    config: AppConfig,
    on_fetch_start: Callable[[int], Any] | None = None,
    on_fetch_complete: Callable[[], Any] | None = None,
) -> Report:
    """
    检查 pyproject.toml 中的依赖版本并生成报告。
    """
    items = _all_items_from_pyproject(pyproject_path)
    exclude = {normalize_project_name(n) for n in config.exclude}

    normalized_names: list[str] = []
    for item in items:
        if item.requirement is None:
            continue
        normalized = normalize_project_name(item.requirement.name)
        if normalized in exclude:
            continue
        normalized_names.append(normalized)

    unique_names = sorted(set(normalized_names))

    cache_db: CacheDB | None = None
    if config.use_cache:
        cache_db = CacheDB(default_cache_path())

    try:
        lookups, stats = await resolve_latest_versions(
            unique_names,
            settings=config.index,
            max_concurrency=config.max_concurrency,
            cache=cache_db,
            cache_ttl_s=config.cache_ttl_s,
            refresh=config.refresh,
            on_fetch_start=on_fetch_start,
            on_fetch_complete=on_fetch_complete,
        )

        report_items: list[ReportItem] = []
        for item in items:
            if item.requirement is None:
                report_items.append(
                    ReportItem(
                        kind=item.kind,
                        group=item.group,
                        name="",
                        raw=item.raw,
                        latest=None,
                        status=CheckStatus.INVALID_REQUIREMENT,
                        suggestion=None,
                        index_url=None,
                        error=item.error,
                    )
                )
                continue

            normalized = normalize_project_name(item.requirement.name)
            if normalized in exclude:
                continue

            lookup = lookups.get(normalized)
            latest: Version | None = lookup.latest if lookup else None
            evaluation = evaluate_requirement_against_latest(
                item.requirement,
                latest=latest,
                not_found=bool(lookup.not_found) if lookup else False,
                network_error=lookup.error if lookup and not lookup.not_found else None,
                pin=config.pin,
            )
            report_items.append(
                ReportItem(
                    kind=item.kind,
                    group=item.group,
                    name=item.requirement.name,
                    raw=item.raw,
                    latest=evaluation.latest,
                    status=evaluation.status,
                    suggestion=evaluation.suggestion,
                    index_url=lookup.index_url if lookup else None,
                    error=item.error or (lookup.error if lookup else None),
                )
            )

        return Report(
            pyproject_path=str(pyproject_path),
            items=report_items,
            cache_hits=stats.cache_hits,
            fetched=stats.fetched,
        )
    finally:
        if cache_db is not None:
            cache_db.close()


def run_check(pyproject_path: Path, *, config: AppConfig) -> Report:
    """
    同步入口：运行依赖检查（内部使用 asyncio）。
    """
    console = Console(stderr=True)
    state = {"progress": None, "task_id": None}

    def on_start(total: int) -> None:
        if total > 0:
            progress = Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                "({task.completed}/{task.total})",
                console=console,
                transient=True,
            )
            progress.start()
            task_id = progress.add_task("查询 PyPI...", total=total)
            state["progress"] = progress
            state["task_id"] = task_id

    def on_complete() -> None:
        progress = state["progress"]
        task_id = state["task_id"]
        if progress and task_id is not None:
            progress.advance(task_id)

    try:
        return asyncio.run(
            check_pyproject(
                pyproject_path,
                config=config,
                on_fetch_start=on_start,
                on_fetch_complete=on_complete,
            )
        )
    finally:
        if state["progress"]:
            state["progress"].stop()
