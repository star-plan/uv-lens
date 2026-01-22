## 总体目标
- 以 pytest 为核心，把“纯函数单测 + 关键流程集成测 + CLI 行为测”补齐，覆盖核心功能：解析配置/pyproject、查询/缓存/并发、版本评估、输出格式、uv 命令生成、pyproject 写回、CLI 错误码。
- 所有测试默认离线：用 httpx.MockTransport 或 monkeypatch 替换网络请求与 TUI 启动，避免真实访问 PyPI、避免写入用户目录缓存。

## 测试分层与范围
- 单元测试（快速、离线）：names/versions/index_client/cache/uv_commands/formatters/updater/config 的纯逻辑。
- 集成测试（仍离线）：app.check_pyproject 组合路径（pyproject→依赖抽取→normalize/exclude→resolver→evaluation→report）。
- CLI 行为测试（离线）：cli.main 的参数解析、子命令分发、输出与错误码（通过 monkeypatch run_check / apply_updates_to_pyproject / formatters）。

## 计划新增/扩展的测试模块（按优先级）
### 1) CLI：参数解析、分支覆盖、错误码
- 新增 tests/test_cli.py
  - 覆盖 --version 输出与返回码。
  - 覆盖未知子命令返回 2。
  - 覆盖默认无子命令时：模拟导入 uv_lens.tui 失败→打印 stderr→返回 2。
  - 覆盖 check/export-uv/update 三个子命令：
    - monkeypatch uv_lens.app.run_check 返回固定 Report，验证不同 format（table/json/md）、输出到文件/stdout 的行为与返回码。
    - monkeypatch uv_lens.updater.apply_updates_to_pyproject，验证 update 的 preview 文本与 write=True/False 的分支。
  - 单测 _merge_cli_overrides：exclude 合并、no-cache/refresh 覆盖、cache-ttl/max-concurrency/pin 覆盖、auth（三种：无/ bearer / basic）。

### 2) Config：默认配置探测 + TOML/YAML + 环境变量覆盖
- 新增 tests/test_config.py
  - monkeypatch.chdir(tmp_path) + 创建 .uv-lens.toml / uv-lens.yaml，覆盖默认文件探测（_find_default_config_file）。
  - 测试 TOML/YAML 解析结构异常时回退为 {}。
  - 用 monkeypatch.setenv 覆盖：UV_LENS_INDEX_URL、UV_LENS_EXTRA_INDEX_URLS、UV_LENS_BEARER_TOKEN / BASIC_*，并验证优先级（env > file > default）。
  - pin 非法值回落到 none。

### 3) Resolver：缓存命中/刷新/并发分发
- 新增 tests/test_resolver.py（pytest-asyncio）
  - 用临时 CacheDB 或 stub cache：
    - refresh=False 时命中缓存→不触发 fetch；miss→触发 fetch；统计 cache_hits/fetched 正确。
    - refresh=True 时绕过缓存。
  - monkeypatch create_async_client 为返回带 MockTransport 的 AsyncClient 或自定义上下文对象；monkeypatch fetch_latest_from_indexes 为可控的 async 函数（返回固定 PackageLookupResult），确保离线稳定。

### 4) App：从 pyproject 到 Report 的整链路（离线集成测）
- 新增 tests/test_app.py（pytest-asyncio 或同步通过 asyncio.run）
  - 在 tmp_path 生成最小 pyproject.toml，包含 project/dev/optional/build-system + 一个无效 requirement。
  - monkeypatch resolve_latest_versions 返回指定版本、not_found/network_error 混合场景，验证：
    - INVALID_REQUIREMENT 行为（name 为空、status=invalid_requirement、error 保留）。
    - exclude 生效（被排除的包不在 report.items 中且不进入 resolver 输入）。
    - 评估状态与 suggestion（pin=compatible/exact）正确传递到 ReportItem。
  - 避免用户目录写缓存：用 config.use_cache=False，或 monkeypatch default_cache_path 指向 tmp_path。

### 5) Updater：写回/预览、kind/group 映射、忽略非法项
- 新增 tests/test_updater.py
  - 构造带多类依赖的 pyproject.toml（project/optional/dev-group/build-system），构造 Report（包含 latest）并 pin=exact/compatible，验证 changes 列表内容与顺序稳定性（以集合断言为主）。
  - write=False 不改文件；write=True 且 changes 非空才写回。
  - invalid requirement/URL requirement 等无法建议的行应被忽略。

### 6) Index client：认证头、版本挑选、错误路径与重试
- 扩展 tests/test_index_client.py 或新增 tests/test_index_client_more.py
  - _build_headers：无 auth/bearer/basic 三种 header。
  - pick_latest_version：
    - 只有 pre-release 时选择最大 pre-release；
    - releases 包含无效版本字符串应跳过；
    - 没有候选版本时返回 None。
  - _request_json：
    - 404 返回 (None,404,None)；
    - >=400 返回 error；
    - JSON 解析异常返回 invalid json。
    - 重试：用 MockTransport 先抛 TimeoutException 后成功；monkeypatch asyncio.sleep 为 no-op 保持测试快速。

### 7) Cache：TTL、异常版本、scope key 规范化
- 扩展 tests/test_cache.py 或新增 tests/test_cache_more.py
  - TTL 过期返回 None（通过 monkeypatch time.time 控制）。
  - 写入无法解析的 latest 字符串时读取 latest=None。
  - index_scope_key 去空格/去尾斜杠一致性。

### 8) 输出与命令生成：formatters / uv_commands
- 新增 tests/test_formatters.py
  - report_to_json_obj：Version/Enum 被序列化为字符串。
  - render_markdown：包含统计信息与表头；行内容按预期渲染。
- 新增 tests/test_uv_commands.py
  - project/dev(optional)/group/build_system 的命令生成规则（--dev/--group/--optional）。
  - use_dev_flag=False 时 dev 组使用 --group dev。
  - pin=none/exact/compatible 输出差异（含 extras/marker 的 requirement）。

### 9) TUI：最小化覆盖（不启动真实 UI）
- 新增 tests/test_tui.py
  - monkeypatch UvLensApp.run 为 no-op，验证 run_tui 返回 0 且不会真实启动界面。

## 测试数据与复用方式
- 在 tests/ 下新增轻量 fixture（可放在 tests/conftest.py）：构造 Report/ReportItem 的工厂函数，减少重复。
- 所有新增测试函数均按现有风格添加函数级 docstring（与当前 tests 一致）。

## 通过标准（完成验收）
- 新增测试覆盖 CLI/main 分支、配置加载、resolver 缓存逻辑、updater 写回逻辑、以及 index_client 的错误/重试路径。
- 本地直接运行 pytest 可通过，且不依赖外部网络、不污染用户目录缓存。

如果你确认该方案，我将按以上文件划分逐个补齐测试并在本地跑一遍 pytest 验证。