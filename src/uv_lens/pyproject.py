from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from packaging.requirements import InvalidRequirement, Requirement

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib

from uv_lens.models import DependencyItem, DependencyKind


@dataclass(frozen=True, slots=True)
class PyprojectDependencies:
    """
    从 pyproject.toml 抽取出的各类依赖集合。
    """

    project: list[DependencyItem]
    dev_groups: dict[str, list[DependencyItem]]
    optional: dict[str, list[DependencyItem]]
    build_system: list[DependencyItem]


def load_pyproject_data(pyproject_path: Path) -> dict[str, Any]:
    """
    读取并解析 pyproject.toml，返回 TOML 数据字典。
    """
    content = pyproject_path.read_bytes()
    return tomllib.loads(content.decode("utf-8"))


def parse_requirement(raw: str, *, kind: DependencyKind, group: str) -> DependencyItem:
    """
    解析 requirement 字符串为 Requirement 对象，失败时保留错误信息。
    """
    try:
        req = Requirement(raw)
    except InvalidRequirement as exc:
        return DependencyItem(kind=kind, group=group, raw=raw, requirement=None, error=str(exc))
    return DependencyItem(kind=kind, group=group, raw=raw, requirement=req, error=None)


def extract_dependencies(pyproject_data: dict[str, Any]) -> PyprojectDependencies:
    """
    从 pyproject TOML 数据中提取项目/开发/可选/构建依赖。
    """
    project_table = pyproject_data.get("project") or {}
    project_deps_raw = list(project_table.get("dependencies") or [])
    project_deps = [
        parse_requirement(raw, kind=DependencyKind.PROJECT, group="project") for raw in project_deps_raw
    ]

    optional_table = project_table.get("optional-dependencies") or {}
    optional: dict[str, list[DependencyItem]] = {}
    if isinstance(optional_table, dict):
        for extra, deps_raw in optional_table.items():
            deps_list = list(deps_raw or [])
            optional[str(extra)] = [
                parse_requirement(raw, kind=DependencyKind.OPTIONAL, group=str(extra)) for raw in deps_list
            ]

    dev_groups_table = pyproject_data.get("dependency-groups") or {}
    dev_groups: dict[str, list[DependencyItem]] = {}
    if isinstance(dev_groups_table, dict):
        for group, deps_raw in dev_groups_table.items():
            deps_list = list(deps_raw or [])
            dev_groups[str(group)] = [
                parse_requirement(raw, kind=DependencyKind.DEV_GROUP, group=str(group)) for raw in deps_list
            ]

    tool_uv = (pyproject_data.get("tool") or {}).get("uv") or {}
    tool_uv_dev_deps = tool_uv.get("dev-dependencies")
    if tool_uv_dev_deps and "dev" not in dev_groups:
        deps_list = list(tool_uv_dev_deps or [])
        dev_groups["dev"] = [
            parse_requirement(raw, kind=DependencyKind.DEV_GROUP, group="dev") for raw in deps_list
        ]

    build_system_table = pyproject_data.get("build-system") or {}
    build_requires_raw = list(build_system_table.get("requires") or [])
    build_system = [
        parse_requirement(raw, kind=DependencyKind.BUILD_SYSTEM, group="build-system") for raw in build_requires_raw
    ]

    return PyprojectDependencies(
        project=project_deps,
        dev_groups=dev_groups,
        optional=optional,
        build_system=build_system,
    )
