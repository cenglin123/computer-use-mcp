# 部署与环境配置

> 记录部署方式、环境差异和启动约定。

## 环境变量

| 变量 | 用途 | 必填 | 备注 |
|------|------|------|------|
| `PYTHONUTF8` | 强制 Python UTF-8 模式 | ❌ | Windows 中文环境下建议设为 `1`，避免终端乱码 |
| `COMPUTER_USE_CONFIG` | 覆盖默认配置文件路径 | ❌ | 显式代码参数优先；否则读取该变量；最后读取 `~/.computer-use/config.yaml`；若新默认文件不存在但旧 `~/.kimi-code/mcp/computer-use/config.yaml` 存在，则兼容读取旧路径 |

## 启动方式

### 模型能力要求

本 MCP 不内置视觉模型，也不返回截图 base64。需要完成视觉 GUI 操作时，MCP 客户端必须搭配能读取本地 PNG 文件的多模态模型；纯文本模型只能可靠使用结构化 UIA、trace/task 审计和维护类工具。

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
python -m computer_use doctor
python -m computer_use screenshot
python -m computer_use click 100 100
```

### 安装后自检

先运行：

```powershell
python -m computer_use doctor
```

`doctor` 输出 JSON，检查平台、依赖、配置目录和模型能力提醒。它会创建/验证日志、截图、trace、task 目录是否可写，但不会发送鼠标或键盘输入。

- `uiautomation` 检查为 `warning` 时表示未安装该可选依赖；缺少它时 `get_ui_snapshot`、`find_control` 等工具不可用，但 `screenshot` 和纯坐标输入仍可工作。
- `model_capability` 始终为 `warning`，提醒视觉 GUI 任务需要客户端/模型能读取本地 PNG 路径，MCP server 本身不内置视觉模型。

支持 MCP prompts 的客户端应加载 `computer_use_guidance`。不支持 prompts 或 Skill 的客户端，应复制 [docs/agent-usage.md](agent-usage.md) 或 [examples/clients/agent-prompt.md](../examples/clients/agent-prompt.md) 的提示词。

安装后 smoke test 先用只读能力：

```text
1. get_monitors()
2. get_ui_snapshot(scope="foreground")
3. start_task(goal="smoke")
4. review_task_session(task_id)
5. finish_task(task_id, summary="smoke complete")
```

纯文本模型不得执行需要截图理解、图标识别、颜色判断或坐标选择的视觉 GUI 任务；这些任务必须交给能读取本地 PNG 截图的多模态模型。

### 作为 MCP 服务器使用

`pyproject.toml` 已定义入口。在 MCP 客户端配置中指定：

```json
{
  "command": "C:\\Project\\computer-use-mcp\\.venv\\Scripts\\python.exe",
  "args": ["-m", "computer_use.mcp_server"]
}
```

具体启动参数和传输方式以 `mcp_server.py` 当前实现为准。

只读 MCP smoke 脚本：

```powershell
python tools\smoke_mcp_client.py --server .\.venv\Scripts\python.exe --args -m computer_use.mcp_server
```

该脚本只验证协议、`tools/list`、`prompts/list` 和只读 `get_monitors`，不点击、不输入。

## 持久化与备份

- 本项目无持久化数据库。截图保存到配置的 `screenshot_dir`，MCP 响应只返回本地路径，不返回 base64。
- 新安装默认配置根目录为 `~/.computer-use/`：日志写入 `logs/`，截图写入 `screenshots/`，trace 写入 `traces/`，业务任务写入 `tasks/`。
- `screenshot.save_path` 只能指向 `screenshot_dir` 内已存在的父目录，不能写入任意文件系统位置。
- 当 `safety.screenshot_sensitive_window_check` 为 `true` 时，`screenshot` 会尝试检测捕获区域内是否存在敏感进程/窗口类，命中后将整张截图替换为空白图并在响应中标记 `redacted: true`。该机制仅作为辅助保护，不能替代用户审慎选择截图范围。
- 对于 `launch_app` 启动的应用，目标路径必须在 `safety.allowed_commands` 白名单中；否则会被拒绝并提示参考 `config.example.yaml`。敏感进程（如 KeePass、certmgr）即使在白名单中也会被额外拦截。
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
