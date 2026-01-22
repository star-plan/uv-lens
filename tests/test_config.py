from __future__ import annotations

from pathlib import Path

import pytest

from uv_lens.config import load_config


def test_load_config_finds_default_toml_in_cwd(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """
    未显式指定 config_path 时，应在当前目录自动探测默认配置文件。
    """
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".uv-lens.toml").write_text(
        """
[uv_lens]
index_url = "https://primary.test/pypi"
extra_index_urls = ["https://extra.test/pypi"]
max_concurrency = 3
cache_ttl_s = 10
use_cache = false
refresh = true
pin = "compatible"
exclude = ["a", "b"]
        """.strip()
        + "\n",
        encoding="utf-8",
    )

    cfg = load_config(None)
    assert cfg.index.index_url == "https://primary.test/pypi"
    assert cfg.index.extra_index_urls == ("https://extra.test/pypi",)
    assert cfg.max_concurrency == 3
    assert cfg.cache_ttl_s == 10
    assert cfg.use_cache is False
    assert cfg.refresh is True
    assert cfg.pin == "compatible"
    assert cfg.exclude == ("a", "b")


def test_load_config_default_yaml_when_toml_missing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """
    TOML 不存在时，应能探测并读取默认 YAML 配置文件。
    """
    monkeypatch.chdir(tmp_path)
    (tmp_path / "uv-lens.yaml").write_text(
        """
uv_lens:
  index_url: "https://yaml.test/pypi"
  retries: 5
  timeout_s: 1.5
        """.strip()
        + "\n",
        encoding="utf-8",
    )

    cfg = load_config(None)
    assert cfg.index.index_url == "https://yaml.test/pypi"
    assert cfg.index.retries == 5
    assert cfg.index.timeout_s == 1.5


def test_load_config_yaml_non_dict_is_ignored(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """
    YAML 顶层非 dict 时应被忽略并回退到默认值。
    """
    monkeypatch.chdir(tmp_path)
    (tmp_path / "uv-lens.yaml").write_text("- 1\n- 2\n", encoding="utf-8")
    cfg = load_config(None)
    assert cfg.index.index_url == "https://pypi.org/pypi"


def test_load_config_env_overrides_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """
    环境变量的配置应覆盖配置文件中的同名字段。
    """
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".uv-lens.toml").write_text(
        """
[uv_lens]
index_url = "https://file.test/pypi"
extra_index_urls = ["https://file-extra.test/pypi"]
bearer_token = "file-token"
        """.strip()
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("UV_LENS_INDEX_URL", "https://env.test/pypi")
    monkeypatch.setenv("UV_LENS_EXTRA_INDEX_URLS", "https://env-extra.test/pypi, https://env-extra2.test/pypi")
    monkeypatch.setenv("UV_LENS_BEARER_TOKEN", "env-token")

    cfg = load_config(None)
    assert cfg.index.index_url == "https://env.test/pypi"
    assert cfg.index.extra_index_urls == ("https://env-extra.test/pypi", "https://env-extra2.test/pypi")
    assert cfg.index.auth is not None
    assert cfg.index.auth.bearer_token == "env-token"


def test_load_config_basic_auth_from_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """
    basic 认证在环境变量提供 user/pass 时应被启用。
    """
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("UV_LENS_BASIC_USERNAME", "u")
    monkeypatch.setenv("UV_LENS_BASIC_PASSWORD", "p")
    cfg = load_config(None)
    assert cfg.index.auth is not None
    assert cfg.index.auth.basic_username == "u"
    assert cfg.index.auth.basic_password == "p"


def test_load_config_invalid_pin_falls_back_to_none(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """
    pin 配置非法值时应回退为 none。
    """
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".uv-lens.toml").write_text(
        """
[uv_lens]
pin = "bad"
        """.strip()
        + "\n",
        encoding="utf-8",
    )
    cfg = load_config(None)
    assert cfg.pin == "none"

