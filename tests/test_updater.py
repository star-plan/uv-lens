from __future__ import annotations

from pathlib import Path

from packaging.version import Version

from uv_lens.models import CheckStatus, DependencyKind
from uv_lens.report import Report, ReportItem
from uv_lens.updater import apply_updates_to_pyproject


def _make_report_for_updates() -> Report:
    """
    构造一份包含多种依赖来源的报告，用于 updater 写回测试。
    """
    items = [
        ReportItem(
            kind=DependencyKind.PROJECT,
            group="project",
            name="foo",
            raw="foo==1.0.0",
            latest=Version("1.0.1"),
            status=CheckStatus.CONSTRAINT_BLOCKS_LATEST,
            suggestion="foo==1.0.1",
            index_url="https://pypi.org/pypi",
            error=None,
        ),
        ReportItem(
            kind=DependencyKind.OPTIONAL,
            group="extra",
            name="optpkg",
            raw="optpkg",
            latest=Version("2.0.0"),
            status=CheckStatus.UNPINNED,
            suggestion="optpkg==2.0.0",
            index_url="https://pypi.org/pypi",
            error=None,
        ),
        ReportItem(
            kind=DependencyKind.DEV_GROUP,
            group="dev",
            name="devpkg",
            raw="devpkg>=0",
            latest=Version("3.0.0"),
            status=CheckStatus.UPGRADE_AVAILABLE,
            suggestion="devpkg==3.0.0",
            index_url="https://pypi.org/pypi",
            error=None,
        ),
        ReportItem(
            kind=DependencyKind.BUILD_SYSTEM,
            group="build-system",
            name="buildpkg",
            raw="buildpkg>=0",
            latest=Version("4.0.0"),
            status=CheckStatus.UPGRADE_AVAILABLE,
            suggestion="buildpkg==4.0.0",
            index_url="https://pypi.org/pypi",
            error=None,
        ),
        ReportItem(
            kind=DependencyKind.PROJECT,
            group="project",
            name="urlpkg",
            raw="urlpkg @ https://example.invalid/urlpkg-1.0.0.tar.gz",
            latest=Version("9.9.9"),
            status=CheckStatus.UPGRADE_AVAILABLE,
            suggestion=None,
            index_url="https://pypi.org/pypi",
            error=None,
        ),
    ]
    return Report(pyproject_path="pyproject.toml", items=items, cache_hits=0, fetched=0)


def test_apply_updates_preview_does_not_write(tmp_path: Path) -> None:
    """
    write=False 时应返回变更列表但不修改文件内容。
    """
    pyproject = tmp_path / "pyproject.toml"
    original = (
        """
[project]
name = "demo"
dependencies = [
  "foo==1.0.0",
  "urlpkg @ https://example.invalid/urlpkg-1.0.0.tar.gz",
  "not valid !!!",
]

[project.optional-dependencies]
extra = ["optpkg"]

[dependency-groups]
dev = ["devpkg>=0"]

[build-system]
requires = ["buildpkg>=0"]
        """.strip()
        + "\n"
    )
    pyproject.write_text(original, encoding="utf-8")

    report = _make_report_for_updates()
    changes = apply_updates_to_pyproject(pyproject, report=report, pin="exact", write=False)
    assert {c.name for c in changes} == {"foo", "optpkg", "devpkg", "buildpkg"}
    assert pyproject.read_text(encoding="utf-8") == original


def test_apply_updates_write_updates_expected_fields(tmp_path: Path) -> None:
    """
    write=True 且存在变更时应写回，并且仅更新可建议的版本约束。
    """
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """
[project]
name = "demo"
dependencies = [
  "foo==1.0.0",
  "urlpkg @ https://example.invalid/urlpkg-1.0.0.tar.gz",
  "not valid !!!",
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
    report = _make_report_for_updates()
    changes = apply_updates_to_pyproject(pyproject, report=report, pin="exact", write=True)

    assert {c.name for c in changes} == {"foo", "optpkg", "devpkg", "buildpkg"}

    updated = pyproject.read_text(encoding="utf-8")
    assert "foo==1.0.1" in updated
    assert "optpkg==2.0.0" in updated
    assert "devpkg==3.0.0" in updated
    assert "buildpkg==4.0.0" in updated
    assert "urlpkg @ https://example.invalid/urlpkg-1.0.0.tar.gz" in updated
    assert "not valid !!!" in updated

