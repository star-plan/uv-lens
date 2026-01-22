from __future__ import annotations

from packaging.requirements import Requirement
from packaging.version import Version

from uv_lens.models import DependencyKind, PinMode
from uv_lens.report import Report, ReportItem
from uv_lens.versions import suggest_updated_requirement


def _pin_for_uv(req: Requirement, *, latest: Version, pin: PinMode) -> str:
    """
    将 requirement 按 pin 策略转换为适合 `uv add` 的 requirement 字符串。
    """
    if pin == "none":
        return str(req)
    suggested = suggest_updated_requirement(req, latest=latest, pin=pin)
    return suggested or str(req)


def generate_uv_add_commands(report: Report, *, pin: PinMode, use_dev_flag: bool = True) -> list[str]:
    """
    基于报告生成可执行的 `uv add ...` 命令列表。
    """
    commands: list[str] = []
    for item in report.items:
        if item.latest is None or not item.name:
            continue
        if item.kind == DependencyKind.BUILD_SYSTEM:
            continue

        req = Requirement(item.raw) if item.raw else Requirement(item.name)
        pinned = _pin_for_uv(req, latest=item.latest, pin=pin)

        if item.kind == DependencyKind.PROJECT:
            commands.append(f'uv add "{pinned}"')
            continue

        if item.kind == DependencyKind.DEV_GROUP:
            if use_dev_flag and item.group == "dev":
                commands.append(f'uv add --dev "{pinned}"')
            else:
                commands.append(f'uv add --group {item.group} "{pinned}"')
            continue

        if item.kind == DependencyKind.OPTIONAL:
            commands.append(f'uv add --optional {item.group} "{pinned}"')
            continue

    return commands
