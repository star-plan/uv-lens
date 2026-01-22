from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.screen import ModalScreen
from textual.widgets import DataTable, Footer, Header, Label, Static, TextArea

from uv_lens.app import check_pyproject
from uv_lens.config import load_config
from uv_lens.models import PinMode
from uv_lens.report import Report, ReportItem
from uv_lens.updater import apply_updates_to_pyproject
from uv_lens.uv_commands import generate_uv_add_commands


class TextPreview(ModalScreen[bool]):
    """
    用于展示文本并确认的弹窗。
    """

    def __init__(self, title: str, text: str, *, confirm_label: str) -> None:
        super().__init__()
        self._title = title
        self._text = text
        self._confirm_label = confirm_label

    BINDINGS = [
        Binding("escape", "dismiss(False)", "取消"),
        Binding("enter", "dismiss(True)", "确认"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield Label(self._title)
        area = TextArea(text=self._text, read_only=True)
        yield area
        yield Footer()


class UvLensApp(App[None]):
    """
    uv-lens 的 TUI 应用。
    """

    CSS = """
    DataTable {
        height: 1fr;
    }
    #details {
        height: 12;
        border: solid $primary;
        padding: 1;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "退出"),
        Binding("r", "refresh", "刷新"),
        Binding("e", "export_uv", "导出 uv 命令"),
        Binding("u", "update_preview", "更新预览/写回"),
    ]

    def __init__(self, pyproject_path: Path) -> None:
        super().__init__()
        self._pyproject_path = pyproject_path
        self._report: Report | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            yield DataTable(id="table")
        yield Static(id="details")
        yield Footer()

    async def on_mount(self) -> None:
        table = self.query_one("#table", DataTable)
        table.add_columns("分组", "包", "当前", "最新", "状态")
        self.query_one("#details", Static).update("按 r 刷新；e 导出 uv 命令；u 预览/写回更新。")
        await self._load_report(refresh=False)

    async def _load_report(self, *, refresh: bool) -> None:
        cfg = load_config(None)
        cfg = replace(cfg, pin="compatible", refresh=refresh)
        self.query_one("#details", Static).update("正在检查依赖，请稍候…")
        report = await check_pyproject(self._pyproject_path, config=cfg)
        self._report = report
        self._render_table(report)
        self.query_one("#details", Static).update(
            f"完成：缓存命中 {report.cache_hits}，发起查询 {report.fetched}。"
        )

    def _render_table(self, report: Report) -> None:
        table = self.query_one("#table", DataTable)
        table.clear()
        for item in report.items:
            group = f"{item.kind.value}:{item.group}"
            latest = str(item.latest) if item.latest else "-"
            table.add_row(group, item.name or "-", item.raw, latest, item.status.value, key=item.raw)

    def _selected_item(self) -> ReportItem | None:
        table = self.query_one("#table", DataTable)
        if table.cursor_row is None or self._report is None:
            return None
        row_index = table.cursor_row
        if row_index < 0 or row_index >= len(self._report.items):
            return None
        return self._report.items[row_index]

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        item = self._selected_item()
        if not item:
            return
        details = [
            f"分组：{item.kind.value}:{item.group}",
            f"包：{item.name or '-'}",
            f"当前：{item.raw}",
            f"最新：{item.latest or '-'}",
            f"状态：{item.status.value}",
            f"建议：{item.suggestion or '-'}",
            f"索引：{item.index_url or '-'}",
            f"错误：{item.error or '-'}",
        ]
        self.query_one("#details", Static).update("\n".join(details))

    async def action_refresh(self) -> None:
        await self._load_report(refresh=True)

    async def action_export_uv(self) -> None:
        if self._report is None:
            return
        pin: PinMode = "exact"
        commands = generate_uv_add_commands(self._report, pin=pin, use_dev_flag=True)
        text = "\n".join(commands) + ("\n" if commands else "")
        ok = await self.push_screen_wait(TextPreview("uv add 命令（Enter 关闭）", text, confirm_label="关闭"))
        _ = ok

    async def action_update_preview(self) -> None:
        if self._report is None:
            return
        pin: PinMode = "compatible"
        changes = apply_updates_to_pyproject(self._pyproject_path, report=self._report, pin=pin, write=False)
        if not changes:
            await self.push_screen_wait(TextPreview("更新预览", "没有可写回的变更。\n", confirm_label="关闭"))
            return
        preview = "\n".join(
            f"{c.kind.value}:{c.group} {c.name} {c.before} -> {c.after}" for c in changes
        )
        confirm = await self.push_screen_wait(
            TextPreview("更新预览（Enter 写回 / Esc 取消）", preview + "\n", confirm_label="写回")
        )
        if confirm:
            apply_updates_to_pyproject(self._pyproject_path, report=self._report, pin=pin, write=True)
            await self._load_report(refresh=True)


def run_tui(pyproject_path: Path) -> int:
    """
    运行 TUI（无参数时默认入口）。
    """
    app = UvLensApp(pyproject_path)
    app.run()
    return 0
