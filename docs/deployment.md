# 部署与环境配置

> 记录部署方式、环境差异和启动约定。

## 环境变量

| 变量 | 用途 | 必填 | 备注 |
|------|------|------|------|
| `PYTHONUTF8` | 强制 Python UTF-8 模式 | ❌ | Windows 中文环境下建议设为 `1`，避免终端乱码 |
| `COMPUTER_USE_CONFIG` | 覆盖默认配置文件路径 | ❌ | 显式代码参数优先；否则读取该变量；最后读取 `~/.computer-use/config.yaml`；若新默认文件不存在但旧 `~/.kimi-code/mcp/computer-use/config.yaml` 存在，则兼容读取旧路径 |

## 启动方式

### 模型能力要求

本 MCP 不内置视觉模型，默认不返回截图 base64。`screenshot` 保存 PNG 到本地并返回路径，Agent 读取该文件即可观察界面。如果 Agent 无法读取图像内容，可回退到结构化 UIA、trace/task 审计和维护类工具。

#### 何时开启 `screenshot include_image`

`screenshot` 支持可选 `include_image=true`，把全分辨率截图作为独立 `ImageContent` 块随结果内联返回，省去"截图→读盘"两个往返中的读盘那次。开启前提与权衡：

- **客户端必须会渲染 MCP 工具结果里的 `ImageContent`**。Agent 无标准机制动态探测宿主能力，因此这是**运维侧判断**：仅在已确认支持的客户端上启用（已验证 OpenCode + Kimi 支持渲染）；不支持的客户端开了等于白传几 MB、零收益。
- **仅 stdio 传输**。当前为 stdio-only，无 SSE 消息体上限问题；若将来引入 SSE/HTTP 代理，大 base64 会撞上代理消息上限，需另行处理。
- **体积**：单屏 PNG 常 1–5MB；base64 超 3MB（约 2.25MB 原始 PNG，典型见于 `monitor=0` 全虚拟桌面）会自动退化为纯路径并加 `inline_image_skipped`。
- **粒度**：本期仅 per-call 开启（按需在 `screenshot` 调用上传参），不提供部署级全局默认。

### 安装 SKILL 供框架默认加载（分发安装关键步骤）

支持 `.agents/skills/` 约定的框架（如 codex、opencode）会**按 `SKILL.md` 顶部 frontmatter 的 `description` 自动发现并加载**用户全局 skills 目录下的技能。把本 MCP 的 SKILL 装到用户全局目录后，装好 MCP 的 agent 在**任意工作目录**都能拿到正确的 Computer Use 使用纪律，无需每次手动 `load skill`。**执行 MCP 安装的 agent 应在配置 server 的同时完成这一步。**

- **权威源文件**：仓库内 `skills/computer-use/SKILL.md`（`.agents/skills/computer-use/SKILL.md` 是项目内同步副本，内容逐字一致，二者皆可作为源）。
- **目标位置**：`C:\Users\<用户名>\.agents\skills\computer-use\SKILL.md`（即 `~/.agents/skills/computer-use/SKILL.md`）。

复制方式（Windows PowerShell，快照式，SKILL 更新后需重新复制）：

```powershell
$dest = "$env:USERPROFILE\.agents\skills\computer-use"
New-Item -ItemType Directory -Force $dest | Out-Null
Copy-Item "<仓库根目录>\skills\computer-use\SKILL.md" "$dest\SKILL.md" -Force
```

链接方式（符号链接，随仓库更新自动跟随；需管理员权限或开启开发者模式）：

```powershell
$dest = "$env:USERPROFILE\.agents\skills\computer-use"
New-Item -ItemType Directory -Force $dest | Out-Null
New-Item -ItemType SymbolicLink -Path "$dest\SKILL.md" -Target "<仓库根目录>\skills\computer-use\SKILL.md"
```

注意：

- **链接 vs 复制**：链接让全局技能始终跟随仓库内最新 SKILL；复制是快照，仓库 SKILL 更新后须重新复制。分发场景若仓库会随版本更新，优先用链接。
- **必须保留 frontmatter**：`SKILL.md` 顶部的 `name` / `description` 不能删，框架靠 `description` 判断何时加载该技能。
- **Claude Code 用户**：其全局技能路径是 `~/.claude/skills/computer-use/SKILL.md`，同样可复制或链接到该处。
- 安装后可在 agent 中确认该 skill 能被按需触发，再执行真实 GUI 任务。

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

支持 MCP prompts 的客户端应加载 `computer_use_guidance`。不支持 prompts 或 Skill 的客户端，应复制 [docs/agent-usage.md](agent-usage.md) 或 [.agents/examples/clients/agent-prompt.md](../.agents/examples/clients/agent-prompt.md) 的提示词。

安装后 smoke test 先用只读能力：

```text
1. get_monitors()
2. get_ui_snapshot(scope="foreground")
3. start_task(goal="smoke")
4. review_task_session(task_id)
5. finish_task(task_id, summary="smoke complete")
```

如果 Agent 读取截图后无法解析图像内容，不应执行需要截图理解、图标识别、颜色判断或坐标选择的视觉 GUI 任务；这些任务需要图像读取能力，可回退到结构化 UIA 工具或请求用户切换客户端。

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
- 新安装默认配置根目录为 `~/.computer-use/`：日志写入 `logs/`，截图写入 `screenshots/`，trace 写入 `traces/`，业务任务写入 `tasks/`，复盘报告写入 `reviews/`。
- **复盘报告收集**：用户在执行窗口说"复盘/总结复盘报告"时，agent 用 `save_review` 把规范化报告(单 `.md`，YAML frontmatter + 正文)写入 `review_dir`(默认 `~/.computer-use/reviews/`，可在 `config.yaml` 配置)。收集反馈时让用户把该目录下对应 `.md` 发回(聊天附件 / GitHub Issue / 邮件)。报告含 `doctor` 环境快照与用户名/路径，**不含密钥或 `config.yaml` 内容**;分享前可预览脱敏。
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
