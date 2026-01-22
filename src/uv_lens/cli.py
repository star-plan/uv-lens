from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path
import sys

from uv_lens.config import AppConfig, load_config
from uv_lens.index_client import IndexAuth, IndexSettings
from uv_lens.models import PinMode


def build_parser() -> argparse.ArgumentParser:
    """
    构建 uv-lens 的命令行参数解析器。
    """
    parser = argparse.ArgumentParser(prog="uv-lens")
    parser.add_argument(
        "--version",
        action="store_true",
        help="输出版本号并退出",
    )
    parser.add_argument("--config", help="配置文件路径（.toml 或 .yaml）")
    parser.add_argument(
        "--pyproject",
        default="pyproject.toml",
        help="pyproject.toml 路径（默认：pyproject.toml）",
    )
    parser.add_argument("--index-url", help="主索引 URL（PyPI JSON API 基址）")
    parser.add_argument(
        "--extra-index-url",
        action="append",
        default=[],
        help="额外索引 URL（可重复）",
    )
    parser.add_argument("--bearer-token", help="私有索引 Bearer Token（谨慎使用）")
    parser.add_argument("--basic-username", help="私有索引 Basic 用户名（谨慎使用）")
    parser.add_argument("--basic-password", help="私有索引 Basic 密码（谨慎使用）")
    parser.add_argument("--exclude", action="append", default=[], help="排除不检查的包名（可重复）")
    parser.add_argument("--no-cache", action="store_true", help="禁用本地缓存")
    parser.add_argument("--refresh", action="store_true", help="忽略缓存并强制重新查询")
    parser.add_argument("--cache-ttl", type=int, help="缓存 TTL 秒数（0 表示永不过期）")
    parser.add_argument("--max-concurrency", type=int, help="最大并发请求数")
    parser.add_argument(
        "--pin",
        choices=["none", "compatible", "exact"],
        help="生成建议/命令/写回时的 pin 策略",
    )

    subparsers = parser.add_subparsers(dest="command")

    check = subparsers.add_parser("check", help="检查依赖版本并输出报告")
    check.add_argument("--format", choices=["table", "json", "md"], default="table", help="输出格式")
    check.add_argument("--output", help="输出到文件（默认 stdout）")

    export_uv = subparsers.add_parser("export-uv", help="生成可直接执行的 uv add 命令列表")
    export_uv.add_argument("--output", help="输出到文件（默认 stdout）")
    export_uv.add_argument(
        "--no-dev-flag",
        action="store_true",
        help="对 dev 组也使用 --group dev（不使用 --dev）",
    )

    update = subparsers.add_parser("update", help="按策略更新 pyproject.toml 中的版本约束")
    update.add_argument("--write", action="store_true", help="写回 pyproject.toml（默认仅预览）")
    update.add_argument("--output", help="将变更预览输出到文件（默认 stdout）")

    return parser


def _merge_cli_overrides(cfg: AppConfig, args: argparse.Namespace) -> AppConfig:
    """
    将 CLI 参数覆盖合并到 AppConfig。
    """
    index = cfg.index
    index_url = args.index_url or index.index_url
    extra_index_urls = tuple(args.extra_index_url or index.extra_index_urls)

    auth: IndexAuth | None = index.auth
    if args.bearer_token or args.basic_username or args.basic_password:
        auth = IndexAuth(
            bearer_token=args.bearer_token,
            basic_username=args.basic_username,
            basic_password=args.basic_password,
        )

    index = IndexSettings(
        index_url=index_url,
        extra_index_urls=extra_index_urls,
        timeout_s=index.timeout_s,
        retries=index.retries,
        include_prereleases=index.include_prereleases,
        auth=auth,
    )

    exclude = tuple([*cfg.exclude, *(args.exclude or [])])
    use_cache = cfg.use_cache and not bool(args.no_cache)
    refresh = cfg.refresh or bool(args.refresh)
    cache_ttl_s = cfg.cache_ttl_s if args.cache_ttl is None else int(args.cache_ttl)
    max_concurrency = cfg.max_concurrency if args.max_concurrency is None else int(args.max_concurrency)
    pin: PinMode = cfg.pin if args.pin is None else args.pin

    return AppConfig(
        index=index,
        max_concurrency=max_concurrency,
        cache_ttl_s=cache_ttl_s,
        use_cache=use_cache,
        refresh=refresh,
        pin=pin,
        exclude=exclude,
    )


def main(argv: list[str] | None = None) -> int:
    """
    uv-lens 命令行入口。
    """
    args = build_parser().parse_args(argv)

    if args.version:
        from uv_lens import __version__

        print(__version__)
        return 0

    if args.command is None:
        try:
            from uv_lens.tui import run_tui
        except Exception:
            print("uv-lens: TUI 依赖未安装或启动失败，请使用子命令。", file=sys.stderr)
            return 2
        return run_tui(Path(args.pyproject))

    cfg = _merge_cli_overrides(load_config(args.config), args)
    pyproject_path = Path(args.pyproject)

    if args.command == "check":
        from uv_lens.app import run_check
        from uv_lens.formatters import print_table, render_json, render_markdown

        try:
            report = run_check(pyproject_path, config=cfg)
        except Exception as exc:
            print(f"uv-lens: 解析或检查失败：{exc}", file=sys.stderr)
            return 1
        output_path = getattr(args, "output", None)
        if args.format == "table":
            if output_path:
                with open(output_path, "w", encoding="utf-8") as f:
                    print_table(report, file=f)
            else:
                print_table(report)
            return 0
        if args.format == "json":
            text = render_json(report)
        else:
            text = render_markdown(report)
        if output_path:
            Path(output_path).write_text(text, encoding="utf-8")
        else:
            print(text)
        return 0

    if args.command == "export-uv":
        from uv_lens.app import run_check
        from uv_lens.uv_commands import generate_uv_add_commands

        export_pin: PinMode = cfg.pin if cfg.pin != "none" else "exact"
        try:
            report = run_check(pyproject_path, config=replace(cfg, pin=export_pin))
        except Exception as exc:
            print(f"uv-lens: 解析或检查失败：{exc}", file=sys.stderr)
            return 1
        commands = generate_uv_add_commands(report, pin=export_pin, use_dev_flag=not bool(args.no_dev_flag))
        text = "\n".join(commands) + ("\n" if commands else "")
        output_path = getattr(args, "output", None)
        if output_path:
            Path(output_path).write_text(text, encoding="utf-8")
        else:
            print(text, end="")
        return 0

    if args.command == "update":
        from uv_lens.app import run_check
        from uv_lens.updater import apply_updates_to_pyproject

        update_pin: PinMode = cfg.pin if cfg.pin != "none" else "compatible"
        try:
            report = run_check(pyproject_path, config=replace(cfg, pin=update_pin))
            changes = apply_updates_to_pyproject(
                pyproject_path,
                report=report,
                pin=update_pin,
                write=bool(args.write),
            )
        except Exception as exc:
            print(f"uv-lens: 更新失败：{exc}", file=sys.stderr)
            return 1
        lines = []
        for ch in changes:
            lines.append(f"{ch.kind.value}:{ch.group} {ch.name} {ch.before} -> {ch.after}")
        if not lines:
            lines.append("没有可写回的变更。")
        text = "\n".join(lines) + "\n"
        output_path = getattr(args, "output", None)
        if output_path:
            Path(output_path).write_text(text, encoding="utf-8")
        else:
            print(text, end="")
        return 0

    print(f"uv-lens: 未知子命令 {args.command!r}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
