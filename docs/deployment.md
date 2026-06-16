# 部署与环境配置

> 记录部署方式、环境差异和启动约定。

## 环境变量

| 变量 | 用途 | 必填 | 备注 |
|------|------|------|------|
| `PYTHONUTF8` | 强制 Python UTF-8 模式 | ❌ | Windows 中文环境下建议设为 `1`，避免终端乱码 |
| `COMPUTER_USE_CONFIG` | 覆盖默认配置文件路径 | ❌ | 显式代码参数优先；否则读取该变量；最后回退到 `~/.kimi-code/mcp/computer-use/config.yaml` |

## 启动方式

### 开发环境

```bash
# 创建虚拟环境
python -m venv .venv
.venv\Scripts\activate  # Windows

# 安装依赖与 editable 安装
pip install -r requirements.txt
pip install -e .

# 运行测试
pytest tests/ -v

# 本地调试 CLI
python -m computer_use screenshot
python -m computer_use click 100 100
```

### 作为 MCP 服务器使用

`pyproject.toml` 已定义入口。在 MCP 客户端配置中指定：

```json
{
  "command": ["python", "-m", "computer_use.mcp_server"]
}
```

具体启动参数和传输方式以 `mcp_server.py` 当前实现为准。

## 持久化与备份

- 本项目无持久化数据库。截图保存到配置的 `screenshot_dir`，MCP 响应只返回本地路径，不返回 base64。
- `screenshot.save_path` 只能指向 `screenshot_dir` 内已存在的父目录，不能写入任意文件系统位置。
- trace 保存到配置的 `trace_dir`，默认 `~/.computer-use/traces/`。`batch`、`run_task_plan` 和 `review_task` 响应中的 `trace_path`、`artifact_root`、`artifacts` 是审计入口；不要依赖目录名推断产物。
- 新 trace 写入 `trace_dir/YYYY/MM/DD/<trace_id>/`。目录分区使用创建时的本地系统日期；JSON 时间字段使用带时区的 ISO 8601。旧 `<trace_dir>/<trace_id>/` 扁平 trace 保持只读兼容，不自动迁移。
- 业务任务会话保存到配置的 `task_dir`，默认 `~/.computer-use/tasks/`。显式 task 可跨 Agent 回合归属多个 trace；未传 `task_id` 的旧调用会生成 standalone task。
- `trace_dir/.index/` 和 `task_dir/.index/` 是可重建 locator 索引，用于按自定义 ID 定位分区目录。备份时应同时包含 `traces/` 和 `tasks/`；`.index/` 可通过维护命令重建，但不要只备份索引。
- trace 上下文内的自动截图 PNG 位于 `<trace_id>/screenshots/`，UI-tree JSON 位于 `<trace_id>/snapshots/`。无 trace 上下文的独立 snapshot 截图仍使用全局 `<trace_dir>/snapshots/` 回退目录，历史文件不迁移。
- `config.yaml` 若包含敏感配置，应通过环境变量或本地 `.env` 覆盖，不要提交到版本库。

## 部署陷阱

- 运行本服务的机器必须有真实显示器或虚拟显示器；无头环境需要配合虚拟显示驱动（如 `IddSampleDriver`、Parsec VDD）。
- 多显示器混合 DPI 场景下，`CoordinateSystem` 会拒绝启动。统一各显示器缩放比例后再运行。
- 输入只允许 mss 枚举中的主显示器范围；副屏仍可截图和检查，但不能接收鼠标或键盘输入。
- 显示器拓扑由进程内 `CoordinateSystem` 缓存。主屏切换、热插拔或分辨率变化后应重启 MCP 服务，使安全边界与当前桌面一致。
