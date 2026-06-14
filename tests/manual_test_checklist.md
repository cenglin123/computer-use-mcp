# Computer Use 手动测试清单

> 本清单覆盖 Computer Use 的常见任务场景，用于验证截图、键鼠控制、安全策略、多显示器等核心能力。
> 临时截图统一保存到 `~/.kimi-code/logs/`，避免污染桌面。

---

## 1. 环境自检

| # | 测试项 | 命令 | 预期结果 | 验收方式 |
|---|--------|------|----------|----------|
| 1.1 | 列出显示器 | `python -m computer_use monitors` | 正确显示所有显示器索引、分辨率、偏移、是否主屏 | 目视 |
| 1.2 | 获取虚拟屏幕尺寸 | `python -m computer_use size` | 输出虚拟桌面尺寸，如 `{"width": 3840, "height": 1089}` | 目视 |
| 1.3 | MCP Server 可启动 | `python -m computer_use.mcp_server` | 进程启动，无报错（stdio 模式下无输出即正常） | 进程存活 5 秒 |

---

## 2. 截图能力

| # | 测试项 | 命令 | 预期结果 | 验收方式 |
|---|--------|------|----------|----------|
| 2.1 | 截取虚拟桌面 | `python -m computer_use screenshot` | 输出 base64 PNG，尺寸等于虚拟屏幕 | 解码后检查尺寸 |
| 2.2 | 截取主显示器 | `python -m computer_use screenshot --monitor 1` | 输出主屏截图，尺寸 1920x1080 | 解码后检查尺寸 |
| 2.3 | 截取副显示器 | `python -m computer_use screenshot --monitor 2` | 输出副屏截图，尺寸正确 | 解码后检查尺寸 |
| 2.4 | 无效 monitor 索引 | `python -m computer_use screenshot --monitor 99` | 返回错误，不崩溃 | 检查退出码/错误信息 |

---

## 3. 鼠标操作

| # | 测试项 | 命令 | 预期结果 | 验收方式 |
|---|--------|------|----------|----------|
| 3.1 | 点击主屏中心 | `python -m computer_use click 960 540` | 鼠标移动到主屏中心并点击 | 目视 |
| 3.2 | 点击副屏中心 | `python -m computer_use click 2880 549` | 鼠标移动到副屏中心并点击 | 目视 |
| 3.3 | 越界坐标被拒绝 | `python -m computer_use click 99999 99999` | 返回 `SAFETY: Coordinate ... outside virtual screen bounds` | 检查退出码 2 |
| 3.4 | 移动到指定坐标 | `python -m computer_use move 100 100` | 鼠标移动到 (100,100) | 目视 |
| 3.5 | 间隙区域被拒绝 | `python -m computer_use click 2000 5` | 返回 `SAFETY: ... virtual screen gap` | 检查退出码 2 |

---

## 4. 键盘操作

| # | 测试项 | 命令 | 预期结果 | 验收方式 |
|---|--------|------|----------|----------|
| 4.1 | 输入普通文本 | 先打开记事本，再执行 `python -m computer_use type "Hello"` | 记事本中出现 Hello | 目视 |
| 4.2 | 输入中文文本 | 打开记事本，执行 `python -m computer_use type "你好世界"` | 记事本中出现 你好世界 | 目视 |
| 4.3 | 组合键复制 | 选中文本后执行 `python -m computer_use key ctrl c` | 文本被复制到剪贴板 | 粘贴验证 |
| 4.4 | 组合键粘贴 | 执行 `python -m computer_use key ctrl v` | 剪贴板内容被粘贴 | 目视 |
| 4.5 | 危险文本被拦截 | `python -m computer_use type "rm -rf /"` | 返回 `SAFETY: Refusing to type...` | 检查退出码 2 |
| 4.6 | 路径删除命令被拦截 | `python -m computer_use type "del file.txt"` | 返回 `SAFETY: Refusing to type...` | 检查退出码 2 |

---

## 5. 应用交互

| # | 测试项 | 步骤 | 预期结果 | 验收方式 |
|---|--------|------|----------|----------|
| 5.1 | 打开记事本并输入 | 1. `start notepad` 或 `python -m computer_use key win r` 后输入 notepad<br>2. `python -m computer_use type "test"` | 记事本中出现 test | 目视 |
| 5.2 | 点击任务栏图标 | `python -m computer_use click <任务栏图标坐标>` | 对应应用获得焦点 | 目视 |
| 5.3 | 截图 → 识别 → 操作 | 1. 截图<br>2. 模型识别按钮位置<br>3. 点击该位置 | 按钮被点击 | 目视 |

---

## 6. 多显示器

| # | 测试项 | 命令 | 预期结果 | 验收方式 |
|---|--------|------|----------|----------|
| 6.1 | 虚拟桌面截图覆盖所有显示器 | `python -m computer_use screenshot` | 截图包含主屏和副屏内容 | 目视 |
| 6.2 | 副屏单显示器截图 | `python -m computer_use screenshot --monitor 2` | 截图仅包含副屏 | 目视 |
| 6.3 | 副屏坐标点击 | `python -m computer_use click 2880 549` | 鼠标在副屏中心点击 | 目视 |
| 6.4 | 混合 DPI 检测 | 在混合 DPI 机器上启动任意工具 | 抛出 `RuntimeError: Mixed-DPI multi-monitor setup detected` | 检查错误信息 |

---

## 7. 安全策略

| # | 测试项 | 命令 | 预期结果 | 验收方式 |
|---|--------|------|----------|----------|
| 7.1 | 危险 shell 命令被拦截 | `python -m computer_use type "format C:"` | 拦截 | 检查退出码 2 |
| 7.2 | 注册表操作被拦截 | `python -m computer_use type "reg add ..."` | 拦截 | 检查退出码 2 |
| 7.3 | 关机命令被拦截 | `python -m computer_use type "shutdown /s"` | 拦截 | 检查退出码 2 |
| 7.4 | 越界点击被拦截 | `python -m computer_use click -1 -1` | 拦截 | 检查退出码 2 |
| 7.5 | 敏感进程检测 | 打开 KeePass/1Password 后尝试输入 | 拦截（如实现） | 检查错误信息 |

---

## 8. MCP Server 工具接口

| # | 测试项 | 调用方式 | 预期结果 | 验收方式 |
|---|--------|----------|----------|----------|
| 8.1 | `screenshot` | Kimi Code CLI 调用（默认） | 返回 JSON 含 `saved_path`/`timestamp`，不含 base64 | 检查文件已保存 |
| 8.1a | `screenshot(save_path=...)` | Kimi Code CLI 调用 | PNG 保存到指定路径并返回路径 | 检查文件存在 |
| 8.2 | `get_monitors` | Kimi Code CLI 调用 | 返回显示器列表 JSON | 检查数组长度 |
| 8.3 | `batch`（默认） | Kimi Code CLI 调用 | 返回每步结果（含 `timestamp`），不含 `final_screenshot` | 检查返回值 |
| 8.4 | `batch(final_screenshot=true)` | Kimi Code CLI 调用 | 返回每步结果及最终截图路径引用 | 检查 `final_screenshot.saved_path` 存在 |
| 8.4 | `click` | Kimi Code CLI 调用 | 执行点击，返回成功 JSON | 检查返回值 |
| 8.5 | `type` 危险文本 | Kimi Code CLI 调用 | 返回 `{"error": "..."}` | 检查返回值 |
| 8.6 | `key_combo` | Kimi Code CLI 调用 | 执行组合键 | 目视 |
| 8.7 | `sleep(duration=2)` | Kimi Code CLI 调用 | 等待 2 秒后返回 `{"slept": true, "duration": 2}` | 检查耗时与返回值 |

---

## 9. 异常与边界

| # | 测试项 | 命令 | 预期结果 | 验收方式 |
|---|--------|------|----------|----------|
| 9.1 | 无效 monitor 参数 | `python -m computer_use screenshot --monitor -1` | 返回错误 | 检查退出码 |
| 9.2 | 空文本输入 | `python -m computer_use type ""` | 不报错，无操作 | 检查退出码 0 |
| 9.3 | 超长文本输入 | 输入 1000 字符文本 | 正常输入 | 目视 |
| 9.4 | 快速连续点击 | 连续 10 次 click | 无崩溃，坐标正确 | 目视 |

---

## 10. 回归测试

| # | 测试项 | 命令 | 预期结果 | 验收方式 |
|---|--------|------|----------|----------|
| 10.1 | pytest 全绿 | `python -m pytest tests/ -v` | 所有测试通过 | 检查输出 |
| 10.2 | 测试任务脚本 | `python test_task.py` | 正常执行，截图保存到 logs | 检查文件 |
| 10.3 | 总结任务脚本 | `python write_summary.py` | 桌面只生成 txt，截图在 logs | 检查目录 |

---

## 执行记录

| 日期 | 测试人 | 通过项 | 失败项 | 备注 |
|------|--------|--------|--------|------|
| 2026-06-13 | Kimi Code CLI | 1.1, 1.2, 2.1, 2.2, 2.3, 3.2, 3.3, 4.5, 6.1, 6.2, 6.3, 7.1, 10.1 | 无 | pytest 39 passed；截图尺寸正确；危险文本/越界坐标正确拦截；副屏点击和截图验证通过（check_monitor2.png 显示副屏内容） |

### 详细执行证据

#### 1. 环境自检

```
$ python -m computer_use monitors
[{"index": 1, "primary": true, "left": 0, "top": 0, "width": 1920, "height": 1080},
 {"index": 2, "primary": false, "left": 1920, "top": 9, "width": 1920, "height": 1080}]

$ python -m computer_use size
{"width": 3840, "height": 1089}
```

✅ 通过：2 个显示器，虚拟屏幕尺寸 3840x1089。

#### 2. 截图能力

```
virtual size: 1124004 bytes (decoded to 3840x1089)
monitor1 size: 670488 bytes (decoded to 1920x1080)
monitor2 size: 427250 bytes (decoded to 1920x1080)
```

✅ 通过：虚拟桌面和单显示器截图尺寸均正确。

#### 3. 鼠标操作（副屏点击）

```
secondary center: (2880, 549)
clicked secondary center
```

✅ 通过：副屏中心坐标被正确计算并点击。

#### 4. 键盘安全

```
$ python -m computer_use type "rm -rf /"
SAFETY: Refusing to type text that matches dangerous command patterns.
exit code 2
```

✅ 通过：危险文本被拦截。

#### 5. 坐标安全

```
$ python -m computer_use click 99999 99999
SAFETY: Coordinate (99999, 99999) is outside virtual screen bounds (3840x1089).
exit code 2
```

✅ 通过：越界坐标被拦截。

#### 6. 间隙区域

```
PASS: Coordinate (2000, 5) falls in a virtual screen gap and is not on any monitor.
```

✅ 通过：虚拟屏幕间隙区域坐标被拦截。

#### 7. 回归测试

```
39 passed in 0.68s
```

✅ 通过：所有单元测试通过。

---

## 注意事项

1. 所有临时截图保存到 `~/.kimi-code/logs/`，不要保存到桌面。
2. 涉及 GUI 操作的测试需要人工目视确认。
3. 安全拦截测试应使用无害但命中规则的文字，不要真的执行危险命令。
4. 多显示器测试需要在多屏环境下执行。
5. 混合 DPI 测试需要在混合 DPI 环境下执行。
