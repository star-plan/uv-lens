from __future__ import annotations

import argparse
import builtins
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from packaging.version import Version

from uv_lens.cli import _merge_cli_overrides, main
from uv_lens.config import AppConfig
from uv_lens.index_client import IndexSettings
from uv_lens.models import CheckStatus, DependencyKind
from uv_lens.report import Report, ReportItem


def _make_base_config(*, pin: str = "none") -> AppConfig:
    """
    构造一份用于 CLI 单测的基础配置，避免依赖外部文件与环境变量。
    """
    return AppConfig(index=IndexSettings(index_url="https://pypi.org/pypi"), pin=pin)


def _make_report() -> Report:
    """
    构造一个最小可用的 Report，供 CLI 子命令测试复用。
    """
    return Report(
        pyproject_path="pyproject.toml",
        items=[
            ReportItem(
                kind=DependencyKind.PROJECT,
                group="project",
                name="httpx",
                raw="httpx>=0.27",
                latest=Version("0.28.0"),
                status=CheckStatus.UPGRADE_AVAILABLE,
                suggestion="httpx>=0.28.0,<1",
                index_url="https://pypi.org/pypi",
                error=None,
            )
        ],
        cache_hits=1,
        fetched=2,
    )


def test_cli_version_flag_prints_version(capsys: pytest.CaptureFixture[str]) -> None:
    """
    --version 应输出版本号并以 0 退出。
    """
    rc = main(["--version"])
    out = capsys.readouterr().out.strip()
    assert rc == 0
    assert out


def test_cli_no_command_when_tui_import_fails_returns_2(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    无子命令时若 TUI 依赖缺失/启动失败，应提示并返回 2。
    """
    original_import = builtins.__import__

    def fake_import(name: str, globals=None, locals=None, fromlist=(), level: int = 0):
        if name == "uv_lens.tui":
            raise ImportError("tui disabled in tests")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    rc = main([])
    err = capsys.readouterr().err
    assert rc == 2
    assert "TUI" in err


def test_merge_cli_overrides_merges_auth_exclude_and_flags() -> None:
    """
    CLI 覆盖应正确合并：索引、认证、exclude、缓存与并发等参数。
    """
    cfg = _make_base_config(pin="none")
    args = argparse.Namespace(
        index_url="https://primary.test/pypi/",
        extra_index_url=["https://extra.test/pypi"],
        bearer_token="token",
        basic_username=None,
        basic_password=None,
        exclude=["A", "b"],
        no_cache=True,
        refresh=True,
        cache_ttl=123,
        max_concurrency=7,
        pin="exact",
    )
    merged = _merge_cli_overrides(cfg, args)
    assert merged.index.index_url == "https://primary.test/pypi/"
    assert merged.index.extra_index_urls == ("https://extra.test/pypi",)
    assert merged.index.auth is not None
    assert merged.index.auth.bearer_token == "token"
    assert merged.use_cache is False
    assert merged.refresh is True
    assert merged.cache_ttl_s == 123
    assert merged.max_concurrency == 7
    assert merged.pin == "exact"
    assert merged.exclude == ("A", "b")


def test_cli_check_table_writes_to_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """
    check --format table 且指定 --output 时，应写入文件并返回 0。
    """
    report = _make_report()
    monkeypatch.setattr("uv_lens.cli.load_config", lambda _: _make_base_config())
    monkeypatch.setattr("uv_lens.app.run_check", lambda *_args, **_kwargs: report)

    def fake_print_table(_report: Report, *, file=None) -> None:
        """
        替换真实 rich 输出，便于断言文件内容。
        """
        assert _report is report
        if file is None:
            raise AssertionError("expected file handle")
        file.write("TABLE\n")

    monkeypatch.setattr("uv_lens.formatters.print_table", fake_print_table)
    out_path = tmp_path / "out.txt"
    rc = main(["--pyproject", str(tmp_path / "p.toml"), "check", "--format", "table", "--output", str(out_path)])
    assert rc == 0
    assert out_path.read_text(encoding="utf-8") == "TABLE\n"


@pytest.mark.parametrize("fmt,renderer_attr", [("json", "render_json"), ("md", "render_markdown")])
def test_cli_check_json_and_md_write_text(
    fmt: str, renderer_attr: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """
    check 的 json/md 输出应走对应渲染函数，并可写入文件。
    """
    report = _make_report()
    monkeypatch.setattr("uv_lens.cli.load_config", lambda _: _make_base_config())
    monkeypatch.setattr("uv_lens.app.run_check", lambda *_args, **_kwargs: report)

    sentinel = f"{fmt.upper()}-TEXT\n"
    monkeypatch.setattr(f"uv_lens.formatters.{renderer_attr}", lambda _r: sentinel)

    out_path = tmp_path / "out.txt"
    rc = main(["--pyproject", str(tmp_path / "p.toml"), "check", "--format", fmt, "--output", str(out_path)])
    assert rc == 0
    assert out_path.read_text(encoding="utf-8") == sentinel


def test_cli_check_when_run_check_raises_returns_1(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """
    check 执行失败时应返回 1 并输出错误信息到 stderr。
    """
    monkeypatch.setattr("uv_lens.cli.load_config", lambda _: _make_base_config())

    def boom(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr("uv_lens.app.run_check", boom)
    rc = main(["--pyproject", str(tmp_path / "p.toml"), "check"])
    err = capsys.readouterr().err
    assert rc == 1
    assert "解析或检查失败" in err


def test_cli_export_uv_uses_exact_pin_when_config_none(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    export-uv 在 cfg.pin=none 时应强制使用 exact 生成命令。
    """
    base_cfg = _make_base_config(pin="none")
    observed: dict[str, str] = {}

    def fake_run_check(_path: Path, *, config: AppConfig) -> Report:
        """
        捕获 export-uv 对 pin 的覆盖结果。
        """
        observed["pin"] = config.pin
        return _make_report()

    monkeypatch.setattr("uv_lens.cli.load_config", lambda _: base_cfg)
    monkeypatch.setattr("uv_lens.app.run_check", fake_run_check)
    monkeypatch.setattr("uv_lens.uv_commands.generate_uv_add_commands", lambda *_a, **_k: ['uv add "x"\n'.strip()])

    rc = main(["--pyproject", "pyproject.toml", "export-uv"])
    assert rc == 0
    assert observed["pin"] == "exact"


def test_cli_update_uses_compatible_pin_when_config_none(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """
    update 在 cfg.pin=none 时应强制使用 compatible 并调用写回逻辑。
    """
    base_cfg = _make_base_config(pin="none")
    observed: SimpleNamespace = SimpleNamespace(pin=None, write=None)
    pyproject_path = tmp_path / "pyproject.toml"
    pyproject_path.write_text("[project]\nname='x'\n", encoding="utf-8")

    def fake_run_check(_path: Path, *, config: AppConfig) -> Report:
        """
        捕获 update 对 pin 的覆盖结果。
        """
        observed.pin = config.pin
        return _make_report()

    def fake_apply_updates_to_pyproject(_path: Path, *, report: Report, pin: str, write: bool):
        """
        替换真实写回，记录参数并返回一条变更。
        """
        observed.write = write
        return [
            SimpleNamespace(kind=DependencyKind.PROJECT, group="project", name="httpx", before="a", after="b")
        ]

    monkeypatch.setattr("uv_lens.cli.load_config", lambda _: base_cfg)
    monkeypatch.setattr("uv_lens.app.run_check", fake_run_check)
    monkeypatch.setattr("uv_lens.updater.apply_updates_to_pyproject", fake_apply_updates_to_pyproject)

    rc = main(["--pyproject", str(pyproject_path), "update", "--write"])
    assert rc == 0
    assert observed.pin == "compatible"
    assert observed.write is True

