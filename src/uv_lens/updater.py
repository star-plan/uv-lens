from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from packaging.requirements import InvalidRequirement, Requirement
from packaging.version import Version
from tomlkit import dumps, parse

from uv_lens.models import DependencyKind, PinMode
from uv_lens.names import normalize_project_name
from uv_lens.report import Report
from uv_lens.versions import suggest_updated_requirement


@dataclass(frozen=True, slots=True)
class UpdateChange:
    """
    一条写回变更（旧值→新值）。
    """

    kind: DependencyKind
    group: str
    name: str
    before: str
    after: str


def _suggest_from_report_item(raw: str, *, latest: Version, pin: PinMode) -> str | None:
    """
    根据 raw requirement 与 latest 生成建议的写回字符串。
    """
    try:
        req = Requirement(raw)
    except InvalidRequirement:
        return None
    return suggest_updated_requirement(req, latest=latest, pin=pin)


def _build_change_map(report: Report, *, pin: PinMode) -> dict[tuple[str, str, str], str]:
    """
    从报告构建 (kind, group, normalized_name) -> new_requirement 的映射。
    """
    mapping: dict[tuple[str, str, str], str] = {}
    for item in report.items:
        if item.latest is None or not item.name:
            continue
        suggested = _suggest_from_report_item(item.raw, latest=item.latest, pin=pin)
        if not suggested:
            continue
        key = (item.kind.value, item.group, normalize_project_name(item.name))
        mapping[key] = suggested
    return mapping


def apply_updates_to_pyproject(
    pyproject_path: Path,
    *,
    report: Report,
    pin: PinMode,
    write: bool,
) -> list[UpdateChange]:
    """
    根据报告与 pin 策略更新 pyproject.toml 中的版本约束。
    """
    change_map = _build_change_map(report, pin=pin)
    doc = parse(pyproject_path.read_text(encoding="utf-8"))
    changes: list[UpdateChange] = []

    def update_list(kind: DependencyKind, group: str, arr: Any) -> None:
        if not isinstance(arr, list):
            return
        for i, raw in enumerate(list(arr)):
            if not isinstance(raw, str):
                continue
            try:
                req = Requirement(raw)
            except InvalidRequirement:
                continue
            key = (kind.value, group, normalize_project_name(req.name))
            new_raw = change_map.get(key)
            if new_raw and new_raw != raw:
                arr[i] = new_raw
                changes.append(
                    UpdateChange(
                        kind=kind,
                        group=group,
                        name=req.name,
                        before=raw,
                        after=new_raw,
                    )
                )

    project = doc.get("project") if isinstance(doc, dict) else None
    if isinstance(project, dict):
        update_list(DependencyKind.PROJECT, "project", project.get("dependencies"))

        optional = project.get("optional-dependencies")
        if isinstance(optional, dict):
            for extra, arr in optional.items():
                update_list(DependencyKind.OPTIONAL, str(extra), arr)

    dev_groups = doc.get("dependency-groups") if isinstance(doc, dict) else None
    if isinstance(dev_groups, dict):
        for group, arr in dev_groups.items():
            update_list(DependencyKind.DEV_GROUP, str(group), arr)

    build_system = doc.get("build-system") if isinstance(doc, dict) else None
    if isinstance(build_system, dict):
        update_list(DependencyKind.BUILD_SYSTEM, "build-system", build_system.get("requires"))

    if write and changes:
        pyproject_path.write_text(dumps(doc), encoding="utf-8")

    return changes
