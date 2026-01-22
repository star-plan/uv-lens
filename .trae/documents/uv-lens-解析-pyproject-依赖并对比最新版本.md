## 新增需求：全局缓存数据库（用户目录）
- 缓存默认放在**用户目录**，全局共用一个数据库，避免在每个项目下生成缓存文件。
- 默认路径（可覆盖）：
  - Windows：`%LOCALAPPDATA%\\uv-lens\\cache.sqlite3`（若缺失则回退到 `%APPDATA%`，再回退到 `~\\AppData\\Local`）
  - macOS：`~/Library/Caches/uv-lens/cache.sqlite3`
  - Linux：`$XDG_CACHE_HOME/uv-lens/cache.sqlite3`（否则 `~/.cache/uv-lens/cache.sqlite3`）
- 仍提供 `--cache-path` 覆盖与 `--no-cache` 禁用；并在数据库中加入 `schema_version` 与 `index_url` 维度，便于后续升级与多索引并存。

## 默认进入 TUI（无参数）
- `uv-lens` 无参数：进入 TUI 交互；有参数：保留 CLI 子命令用于脚本化。

## TUI 交互设计（Windows 友好）
- 技术选型：`textual`（跨平台全屏 TUI），与 `rich` 共用渲染能力。
- 页面：选择文件→扫描进度→依赖列表（分组/搜索/筛选）→详情→生成 uv 命令→更新向导（预览/确认/写回）。

## 依赖解析范围（pyproject.toml）
- 项目：`[project].dependencies`
- 可选：`[project.optional-dependencies]`
- 开发：优先 `[dependency-groups]`（PEP 735，含 dev），并兼容 `tool.uv` 相关字段兜底
- 构建：`[build-system].requires`
- 解析使用 `packaging.requirements.Requirement`，保留 extras 与 markers。

## PyPI / 私有仓库查询
- 支持 `index_url` + `extra_index_urls` 顺序尝试（来自 CLI / 环境变量 / 配置文件）。
- 支持 token/basic 认证；不输出敏感信息。

## 性能：并行 + 增量
- `asyncio + httpx.AsyncClient` 并行查询，`--max-concurrency` 控制。
- 增量：默认仅查询缓存未命中/已过期的包；`--refresh` 强制重查。

## 最新稳定版本提取与版本建议
- 默认选最高非预发布版本；`--include-prereleases` 可放开。
- 状态分类：up_to_date / upgrade_available / constraint_blocks_latest / unpinned / not_found / invalid_requirement / network_error。
- 建议约束：对 `== / ~= / 上下界` 等场景给出 candidate specifier，供展示与可选写回。

## uv 集成输出
- 生成可执行命令：
  - 项目：`uv add "name==latest"`
  - dev：`uv add --dev ...` 或 `--group <group>`
  - optional extra：`uv add --optional <extra> ...`
- 输出形式：TUI 一键复制/导出；CLI 输出为文本/JSON。

## 自动更新 pyproject.toml（可选）
- `tomlkit` 写回，尽量保留格式与注释。
- CLI：`--dry-run` 预览、`--write` 执行；TUI：预览→确认→写回。

## 配置与排除
- 配置文件支持 `.toml/.yaml`（YAML 可作为可选依赖）。
- 支持 `exclude` 列表与 CLI `--exclude`（可重复）。

## 打包与 uvx 运行
- 标准 `src/uv_lens/` 包结构 + `[project.scripts] uv-lens = "uv_lens.cli:main"`。
- 增加 `[build-system]`（采用 uv 模板推荐后端，如 `uv_build`），保证可被 uvx 安装运行。

## 验证
- pytest：解析覆盖、版本选择、缓存命中/过期、404/超时等错误分支；httpx mock transport 避免真实网络。

确认该方案后，我将开始实现：核心库 + CLI + 默认 TUI + 全局缓存 + 测试与 README。