# 部署与环境配置

> 记录部署方式、环境差异和启动约定。

## 环境变量

| 变量 | 用途 | 必填 | 备注 |
|------|------|------|------|
| `PYTHONUTF8` | 强制 Python UTF-8 模式 | ❌ | Windows 中文环境下建议设为 `1`，避免终端乱码 |
| `COMPUTER_USE_CONFIG` | 覆盖默认配置文件路径 | ❌ | 默认读取项目根 `config.yaml` |

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

- 本项目无持久化数据库，截图均通过内存返回 base64。
- `config.yaml` 若包含敏感配置，应通过环境变量或本地 `.env` 覆盖，不要提交到版本库。

## 部署陷阱

- 运行本服务的机器必须有真实显示器或虚拟显示器；无头环境需要配合虚拟显示驱动（如 `IddSampleDriver`、Parsec VDD）。
- 多显示器混合 DPI 场景下，`CoordinateSystem` 会拒绝启动。统一各显示器缩放比例后再运行。
