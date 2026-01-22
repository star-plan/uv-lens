# 执行现有的发布计划

我将继续执行 `d:\Code\uv-lens\.trae\documents\发布 uv-lens 到 PyPI（GitHub Actions）.md` 中的剩余步骤。

## 状态确认
1.  **已完成**：`.github/workflows/publish.yml` 已创建。
2.  **已完成**：`pyproject.toml` 元数据已更新。
3.  **待修复**：`README.md` 的更新操作此前失败，残留了错误的文本内容，需要修复并正确补充 Trusted Publishing 说明。
4.  **待执行**：本地验证（运行测试、构建包）。

## 执行步骤

### 1. 修复 README.md
- **清理**：移除文件末尾残留的错误 Patch 文本（第 88 行及之后的内容）。
- **补充**：正确写入关于“PyPI Trusted Publishing”和“发版步骤”的说明章节。

### 2. 验证与构建
- **运行测试**：执行 `uv run pytest` 确保当前代码无误。
- **构建尝试**：执行 `uv build` 检查能否成功生成 `dist/` 产物（wheel 和 sdist）。

### 3. 完成
- 确认所有文件就绪，且本地构建验证通过。
- 提醒用户后续需在 PyPI 侧进行 Trusted Publishing 配置。
