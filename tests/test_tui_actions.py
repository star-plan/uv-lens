from __future__ import annotations

from pathlib import Path

import pytest
from packaging.version import Version

from uv_lens.models import CheckStatus, DependencyKind
from uv_lens.report import Report, ReportItem
from uv_lens.tui import UvLensApp


def _make_report() -> Report:
    """
    构造用于 TUI action 测试的最小报告。
    """
    return Report(
        pyproject_path="pyproject.toml",
        items=[
            ReportItem(
                kind=DependencyKind.PROJECT,
                group="project",
                name="httpx",
                raw="httpx>=0.27",
                latest=Version("0.28.1"),
                status=CheckStatus.UPGRADE_AVAILABLE,
                suggestion="httpx==0.28.1",
                index_url="https://pypi.org/pypi",
                error=None,
            )
        ],
        cache_hits=0,
        fetched=0,
    )


@pytest.mark.asyncio
async def test_action_export_uv_does_not_use_push_screen_wait(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """
    action_export_uv 不应使用 push_screen_wait（否则可能触发 NoActiveWorker）。
    """
    app = UvLensApp(tmp_path / "pyproject.toml")
    app._report = _make_report()

    def boom(*_a, **_k):
        raise AssertionError("push_screen_wait should not be called")

    pushed = {"count": 0}

    def fake_push_screen(self, screen, callback=None):
        pushed["count"] += 1

    monkeypatch.setattr(UvLensApp, "push_screen_wait", boom, raising=True)
    monkeypatch.setattr(UvLensApp, "push_screen", fake_push_screen, raising=True)

    await app.action_export_uv()
    assert pushed["count"] == 1


@pytest.mark.asyncio
async def test_action_update_preview_uses_callback_instead_of_wait(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """
    action_update_preview 应使用 push_screen callback 获取结果，而不是 wait_for_dismiss。
    """
    app = UvLensApp(tmp_path / "pyproject.toml")
    app._report = _make_report()

    def boom(*_a, **_k):
        raise AssertionError("push_screen_wait should not be called")

    called = {"push": 0, "run_worker": 0}

    def fake_apply_updates_to_pyproject(*_a, **_k):
        return [type("C", (), {"kind": DependencyKind.PROJECT, "group": "project", "name": "httpx", "before": "a", "after": "b"})()]

    async def fake_load_report(*_a, **_k):
        return None

    def fake_run_worker(self, awaitable, exclusive: bool = False):
        called["run_worker"] += 1
        if hasattr(awaitable, "close"):
            awaitable.close()

    def fake_push_screen(self, screen, callback=None):
        called["push"] += 1
        assert callback is not None
        callback(True)

    monkeypatch.setattr("uv_lens.tui.apply_updates_to_pyproject", fake_apply_updates_to_pyproject)
    monkeypatch.setattr(UvLensApp, "_load_report", fake_load_report, raising=True)
    monkeypatch.setattr(UvLensApp, "push_screen_wait", boom, raising=True)
    monkeypatch.setattr(UvLensApp, "run_worker", fake_run_worker, raising=True)
    monkeypatch.setattr(UvLensApp, "push_screen", fake_push_screen, raising=True)

    await app.action_update_preview()
    assert called["push"] == 1
    assert called["run_worker"] == 1
