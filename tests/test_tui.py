from __future__ import annotations

from pathlib import Path

import pytest

from uv_lens.tui import run_tui


def test_run_tui_does_not_start_real_ui_when_run_patched(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """
    通过 patch UvLensApp.run，可在不启动真实界面的前提下验证 run_tui 的行为。
    """
    called: dict[str, Path] = {}

    def fake_run(self) -> None:
        """
        替换 Textual 的 run，避免实际进入事件循环。
        """
        called["pyproject_path"] = self._pyproject_path

    monkeypatch.setattr("uv_lens.tui.UvLensApp.run", fake_run)

    pyproject_path = tmp_path / "pyproject.toml"
    pyproject_path.write_text("[project]\nname='x'\n", encoding="utf-8")
    rc = run_tui(pyproject_path)
    assert rc == 0
    assert called["pyproject_path"] == pyproject_path

