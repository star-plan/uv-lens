from __future__ import annotations

from packaging.version import Version

from uv_lens.formatters import render_markdown, report_to_json_obj
from uv_lens.models import CheckStatus, DependencyKind
from uv_lens.report import Report, ReportItem


def _make_report() -> Report:
    """
    构造一份用于 formatter 测试的最小报告。
    """
    return Report(
        pyproject_path="pyproject.toml",
        items=[
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
            )
        ],
        cache_hits=1,
        fetched=2,
    )


def test_report_to_json_obj_converts_enums_and_versions_to_strings() -> None:
    """
    JSON 对象应可序列化：Version 与 Enum 字段需转换为字符串。
    """
    obj = report_to_json_obj(_make_report())
    item = obj["items"][0]
    assert item["latest"] == "1.2.3"
    assert isinstance(item["kind"], str)
    assert isinstance(item["status"], str)


def test_render_markdown_contains_stats_and_table_row() -> None:
    """
    Markdown 渲染应包含统计信息与表格内容。
    """
    md = render_markdown(_make_report())
    assert "uv-lens 报告" in md
    assert "缓存命中：1" in md
    assert "发起查询：2" in md
    assert "| 分组 | 包 | 当前 | 最新 | 状态 | 建议 | 错误 |" in md
    assert "| project:project | foo | foo | 1.2.3 | unpinned | foo==1.2.3 | - |" in md

