## uv-lens

解析 `pyproject.toml` 里的依赖项，并从（私有）PyPI JSON API 查询最新稳定版本，生成升级建议与 `uv add` 命令。

### 运行方式

- 发布后（推荐，无需 clone）：

```powershell
uvx uv-lens
uvx uv-lens check
uvx uv-lens check --format json
uvx uv-lens check --format md --output report.md
uvx uv-lens export-uv
uvx uv-lens update
uvx uv-lens update --write
```

- 从源码运行（开发/本地测试）：

- 直接进入 TUI（无参数）：

```powershell
uvx --from . uv-lens
```

- CLI 检查（表格/JSON/Markdown）：

```powershell
uvx --from . uv-lens check
uvx --from . uv-lens check --format json
uvx --from . uv-lens check --format md --output report.md
```

- 生成可执行的 `uv add` 命令列表：

```powershell
uvx --from . uv-lens export-uv
```

- 更新 `pyproject.toml`（默认只预览；加 `--write` 才写回）：

```powershell
uvx --from . uv-lens update
uvx --from . uv-lens update --write
```

### 解析范围

- 项目依赖：`[project].dependencies`
- 开发依赖：`[dependency-groups]`（PEP 735，含 `dev`）
- 可选依赖：`[project.optional-dependencies]`
- 构建依赖：`[build-system].requires`

### 私有索引与认证

- 主索引与回退索引：
  - `--index-url https://pypi.org/pypi`
  - `--extra-index-url https://your.index/pypi`（可重复）
- 环境变量：
  - `UV_LENS_INDEX_URL`
  - `UV_LENS_EXTRA_INDEX_URLS`（逗号分隔）
  - `UV_LENS_BEARER_TOKEN` 或 `UV_LENS_BASIC_USERNAME` / `UV_LENS_BASIC_PASSWORD`

### 缓存

- 默认使用“用户目录全局 SQLite 缓存”，避免每个项目创建数据库文件。
- 可通过 `--no-cache` 禁用，或用 `--cache-ttl` 调整 TTL，`--refresh` 强制重新查询。

### 配置文件

在项目根目录放置 `.uv-lens.toml`：

```toml
[uv_lens]
index_url = "https://pypi.org/pypi"
extra_index_urls = []
max_concurrency = 20
cache_ttl_s = 86400
pin = "compatible"
exclude = ["setuptools"]
```

### 发布到 PyPI

本仓库包含 GitHub Actions 工作流，会在打 tag（`v*`）时自动构建并发布到 PyPI。

- PyPI Trusted Publishing（推荐）：
  - 在 PyPI 项目设置里添加 Trusted Publisher，指向本仓库与工作流文件：`.github/workflows/publish.yml`
  - 无需在 GitHub Secrets 里保存 PyPI Token

- 发版步骤：
  - 更新版本号：`pyproject.toml` 的 `version` 与 `src/uv_lens/__init__.py` 的 `__version__`
  - 创建并推送 tag：`vX.Y.Z`（例如 `v0.1.0`）
  - Actions 自动跑测试、构建 `dist/` 并发布
