from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any, TextIO

from rich.console import Console
from rich.table import Table

from uv_lens.report import Report


def report_to_json_obj(report: Report) -> dict[str, Any]:
    """
    将报告转换为可 JSON 序列化的字典结构。
    """
    data = asdict(report)
    for item in data.get("items", []):
        if item.get("latest") is not None:
            item["latest"] = str(item["latest"])
        if item.get("kind") is not None:
            item["kind"] = str(item["kind"])
        if item.get("status") is not None:
            item["status"] = str(item["status"])
    return data


def render_json(report: Report) -> str:
    """
    渲染 JSON 输出。
    """
    return json.dumps(report_to_json_obj(report), ensure_ascii=False, indent=2)


def render_markdown(report: Report) -> str:
    """
    渲染 Markdown 报告（表格 + 简要统计）。
    """
    lines: list[str] = []
    lines.append(f"# uv-lens 报告\n\n- 文件：`{report.pyproject_path}`\n- 缓存命中：{report.cache_hits}\n- 发起查询：{report.fetched}\n")
    lines.append("| 分组 | 包 | 当前 | 最新 | 状态 | 建议 | 错误 |")
    lines.append("|---|---|---|---|---|---|---|")
    for item in report.items:
        group = f"{item.kind.value}:{item.group}"
        name = item.name or "-"
        current = item.raw
        latest = str(item.latest) if item.latest else "-"
        status = item.status.value
        suggestion = item.suggestion or "-"
        error = item.error or "-"
        lines.append(f"| {group} | {name} | {current} | {latest} | {status} | {suggestion} | {error} |")
    return "\n".join(lines) + "\n"


def print_table(report: Report, *, file: TextIO | None = None) -> None:
    """
    以控制台表格形式输出报告。
    """
    console = Console(file=file)
    table = Table(title="uv-lens 依赖检查")
    table.add_column("分组", no_wrap=True)
    table.add_column("包", no_wrap=True)
    table.add_column("当前")
    table.add_column("最新", no_wrap=True)
    table.add_column("状态", no_wrap=True)
    table.add_column("建议")
    table.add_column("错误")
    for item in report.items:
        group = f"{item.kind.value}:{item.group}"
        latest = str(item.latest) if item.latest else "-"
        table.add_row(
            group,
            item.name or "-",
            item.raw,
            latest,
            item.status.value,
            item.suggestion or "-",
            item.error or "-",
        )
    console.print(table)
    console.print(f"缓存命中：{report.cache_hits}，发起查询：{report.fetched}")
