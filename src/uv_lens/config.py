from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib

from uv_lens.index_client import IndexAuth, IndexSettings
from uv_lens.models import PinMode


@dataclass(frozen=True, slots=True)
class AppConfig:
    """
    uv-lens 的运行配置（可来自配置文件、环境变量与 CLI 参数合并）。
    """

    index: IndexSettings
    max_concurrency: int = 20
    cache_ttl_s: int = 24 * 60 * 60
    use_cache: bool = True
    refresh: bool = False
    pin: PinMode = "none"
    exclude: tuple[str, ...] = ()


def _find_default_config_file(cwd: Path) -> Path | None:
    """
    在当前目录查找默认配置文件路径。
    """
    candidates = [
        ".uv-lens.toml",
        ".uv-lens.yaml",
        ".uv-lens.yml",
        "uv-lens.toml",
        "uv-lens.yaml",
        "uv-lens.yml",
    ]
    for name in candidates:
        p = cwd / name
        if p.exists() and p.is_file():
            return p
    return None


def _load_yaml(path: Path) -> dict[str, Any]:
    """
    读取 YAML 配置文件（需要 PyYAML）。
    """
    import yaml

    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        return {}
    return data


def _load_config_file(path: Path) -> dict[str, Any]:
    """
    读取 .toml 或 .yaml 配置文件，返回配置字典。
    """
    suffix = path.suffix.lower()
    if suffix == ".toml":
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    if suffix in {".yaml", ".yml"}:
        return _load_yaml(path)
    return {}


def _env_list(key: str) -> list[str]:
    """
    从环境变量读取列表（逗号分隔）。
    """
    value = os.environ.get(key)
    if not value:
        return []
    return [v.strip() for v in value.split(",") if v.strip()]


def load_config(config_path: str | None) -> AppConfig:
    """
    从配置文件与环境变量加载 AppConfig。
    """
    config_data: dict[str, Any] = {}
    if config_path:
        config_data = _load_config_file(Path(config_path))
    else:
        default = _find_default_config_file(Path.cwd())
        if default:
            config_data = _load_config_file(default)

    tool_cfg = config_data.get("uv_lens") if isinstance(config_data, dict) else {}
    if not isinstance(tool_cfg, dict):
        tool_cfg = {}

    index_url = (
        os.environ.get("UV_LENS_INDEX_URL")
        or str(tool_cfg.get("index_url") or "")
        or "https://pypi.org/pypi"
    )
    extra_index_urls = tuple(
        _env_list("UV_LENS_EXTRA_INDEX_URLS") or list(tool_cfg.get("extra_index_urls") or [])
    )

    bearer = os.environ.get("UV_LENS_BEARER_TOKEN") or str(tool_cfg.get("bearer_token") or "") or None
    basic_user = os.environ.get("UV_LENS_BASIC_USERNAME") or str(tool_cfg.get("basic_username") or "") or None
    basic_pass = os.environ.get("UV_LENS_BASIC_PASSWORD") or str(tool_cfg.get("basic_password") or "") or None
    auth = None
    if bearer or (basic_user is not None and basic_pass is not None):
        auth = IndexAuth(bearer_token=bearer, basic_username=basic_user, basic_password=basic_pass)

    include_prereleases = bool(tool_cfg.get("include_prereleases") or False)
    retries = int(tool_cfg.get("retries") or 2)
    timeout_s = float(tool_cfg.get("timeout_s") or 10.0)

    settings = IndexSettings(
        index_url=index_url,
        extra_index_urls=extra_index_urls,
        timeout_s=timeout_s,
        retries=retries,
        include_prereleases=include_prereleases,
        auth=auth,
    )

    max_concurrency = int(tool_cfg.get("max_concurrency") or 20)
    cache_ttl_s = int(tool_cfg.get("cache_ttl_s") or (24 * 60 * 60))
    use_cache = bool(tool_cfg.get("use_cache") if "use_cache" in tool_cfg else True)
    refresh = bool(tool_cfg.get("refresh") or False)
    pin = str(tool_cfg.get("pin") or "none")
    exclude = tuple(tool_cfg.get("exclude") or [])

    return AppConfig(
        index=settings,
        max_concurrency=max_concurrency,
        cache_ttl_s=cache_ttl_s,
        use_cache=use_cache,
        refresh=refresh,
        pin=pin if pin in {"none", "compatible", "exact"} else "none",
        exclude=exclude,
    )
