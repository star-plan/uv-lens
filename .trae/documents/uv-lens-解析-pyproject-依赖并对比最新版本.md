## 新增需求：默认进入 TUI
- `uv-lens` **无任何参数时**直接进入 TUI 交互模式；仍保留 `check / export-uv / update` 等 CLI 子命令，便于脚本化/CI。
- TUI 与 CLI 共享同一套核心逻辑（解析、查询、对比、缓存、更新），避免两套实现。

## TUI 交互设计（Windows 友好）
- 技术选型：使用 `textual`（基于 Rich、跨平台、支持全屏 TUI），并保留纯 CLI 作为降级路径。
- 主要页面/流程：
  - **选择文件**：默认 `./pyproject.toml`，可在 TUI 中切换路径。
  - **扫描与进度**：展示并行查询进度、成功/失败计数、缓存命中率。
  - **依赖列表**：按分组（project / dev / optional extras / build-system）展示；支持搜索、筛选状态（up_to_date / upgrade_available / constraint_blocks_latest / not_found）。
  - **详情面板**：展示原始约束、最新版本、建议约束、来源索引、错误信息（如网络失败）。
  - **生成 uv 命令**：一键复制（输出到屏幕与剪贴板可选）或导出到文件。
  - **更新向导**：选择更新策略（exact/compatible/none）、勾选要更新的包、预览变更，确认后写回。

## CLI 命令与无参数行为
- 无参数：进入 TUI。
- 有参数：走 CLI 子命令（用于自动化）：
  - `uv-lens check [--format table|json|md] [--output FILE] ...`
  - `uv-lens export-uv [--pin ...] [--group-strategy ...] ...`
  - `uv-lens update [--dry-run] [--write] ...`

## 依赖解析范围（pyproject.toml）
- 项目依赖：`[project].dependencies`
- 可选依赖：`[project.optional-dependencies]`
- 开发依赖：优先 ` [dependency-groups]`（PEP 735，含 `dev`），并兼容 `tool.uv` 的相关配置作为兜底
- 构建依赖：`[build-system].requires`
- 解析使用 `packaging.requirements.Requirement`，保留 extras 与 markers。

## PyPI / 私有仓库查询与缓存
- 支持索引顺序尝试：`index_url` + `extra_index_urls`（CLI/环境变量/配置文件三来源）。
- 支持认证（token/basic）但不输出敏感信息。
- 并行：`asyncio + httpx.AsyncClient`，`--max-concurrency` 控制。
- 缓存：SQLite（stdlib `sqlite3`）+ TTL + `--refresh`；默认增量查询。

## 最新稳定版本提取与版本建议
- 默认选最高非预发布版本；`--include-prereleases` 可放开。
- 状态分类：up_to_date / upgrade_available / constraint_blocks_latest / unpinned / not_found / invalid_requirement / network_error。
- 建议约束生成：按 `== / ~= / 上下界` 等规则输出 candidate specifier，供 CLI/TUI 展示与更新。

## 输出与 uv 集成
- 输出格式：JSON、Markdown、控制台表格（Rich）；TUI 中也可导出同样内容。
- uv 命令生成（与 uv 文档一致）：
  - 项目：`uv add "name==latest"`
  - dev：`uv add --dev ...` 或 `--group <group>`
  - optional extra：`uv add --optional <extra> ...`

## 自动更新 pyproject.toml（可选）
- 使用 `tomlkit` 写回，尽量保留格式与注释。
- `--dry-run` 预览、`--write` 执行；TUI 里对应“预览→确认→写回”。

## 打包与 uvx 运行
- 调整为标准 `src/uv_lens/` 包结构，提供脚本入口：`[project.scripts] uv-lens = "uv_lens.cli:main"`。
- 增加 `[build-system]`（采用 uv 推荐/模板的后端，例如 `uv_build`），确保目录被当作包处理。
- 运行依赖：`httpx`、`packaging`、`tomlkit`、`rich`、`textual`（以及 `pyyaml` 用于 yaml 配置；可做成可选依赖）。
- 使用示例：`uvx --from . uv-lens`（本地），或发布后 `uvx uv-lens`。

## 验证方式
- pytest 覆盖：解析各分组、版本选择逻辑、缓存命中/过期、404/超时等错误分支。
- 使用 httpx mock transport，避免真实网络依赖；TUI 核心逻辑单测覆盖，UI 只做轻量冒烟。

确认该方案后，我将开始实现：核心库（解析/查询/对比/缓存/更新）+ CLI + 默认 TUI + 测试与 README。