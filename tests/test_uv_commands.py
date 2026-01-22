from __future__ import annotations

from packaging.version import Version

from uv_lens.models import CheckStatus, DependencyKind
from uv_lens.report import Report, ReportItem
from uv_lens.uv_commands import generate_uv_add_commands


def _make_report() -> Report:
    """
    构造包含多类依赖的报告，用于 uv add 命令生成测试。
    """
    items = [
        ReportItem(
            kind=DependencyKind.PROJECT,
            group="project",
            name="foo",
            raw="foo",
            latest=Version("1.2.3"),
            status=CheckStatus.UNPINNED,
            suggestion="foo==1.2.3",
            index_url="https://pypi.org/pypi",
            error=None,
        ),
        ReportItem(
            kind=DependencyKind.DEV_GROUP,
            group="dev",
            name="devpkg",
            raw="devpkg>=0",
            latest=Version("2.0.0"),
            status=CheckStatus.UPGRADE_AVAILABLE,
            suggestion="devpkg==2.0.0",
            index_url="https://pypi.org/pypi",
            error=None,
        ),
        ReportItem(
            kind=DependencyKind.DEV_GROUP,
            group="lint",
            name="ruff",
            raw="ruff",
            latest=Version("0.6.0"),
            status=CheckStatus.UNPINNED,
            suggestion="ruff==0.6.0",
            index_url="https://pypi.org/pypi",
            error=None,
        ),
        ReportItem(
            kind=DependencyKind.OPTIONAL,
            group="extra",
            name="bar",
            raw="bar",
            latest=Version("3.0.0"),
            status=CheckStatus.UNPINNED,
            suggestion="bar==3.0.0",
            index_url="https://pypi.org/pypi",
            error=None,
        ),
        ReportItem(
            kind=DependencyKind.BUILD_SYSTEM,
            group="build-system",
            name="buildpkg",
            raw="buildpkg>=0",
            latest=Version("9.9.9"),
            status=CheckStatus.UPGRADE_AVAILABLE,
            suggestion="buildpkg==9.9.9",
            index_url="https://pypi.org/pypi",
            error=None,
        ),
    ]
    return Report(pyproject_path="pyproject.toml", items=items, cache_hits=0, fetched=0)


def test_generate_uv_add_commands_respects_kinds_and_flags() -> None:
    """
    uv add 命令生成应区分 project/dev/optional，并跳过 build-system 依赖。
    """
    report = _make_report()
    commands = generate_uv_add_commands(report, pin="exact", use_dev_flag=True)
    assert commands == [
        'uv add "foo==1.2.3"',
        'uv add --dev "devpkg==2.0.0"',
        'uv add --group lint "ruff==0.6.0"',
        'uv add --optional extra "bar==3.0.0"',
    ]


def test_generate_uv_add_commands_dev_group_uses_group_when_no_dev_flag() -> None:
    """
    use_dev_flag=False 时 dev 组也应使用 --group dev。
    """
    report = _make_report()
    commands = generate_uv_add_commands(report, pin="exact", use_dev_flag=False)
    assert 'uv add --group dev "devpkg==2.0.0"' in commands


def test_generate_uv_add_commands_pin_none_keeps_original_requirement() -> None:
    """
    pin=none 时应保留原始 requirement，而不是强制替换为建议版本。
    """
    report = _make_report()
    commands = generate_uv_add_commands(report, pin="none", use_dev_flag=True)
    assert commands[0] == 'uv add "foo"'

