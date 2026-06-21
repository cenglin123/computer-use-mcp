# Design Review: screenshot-inline-image-return

> 收敛后设计审查 — ultraverge 强制触发，咨询式，不阻断。

## Highlights

1. **monitor=0 内联无退化路径风险最高**：全虚拟桌面截图 8-15MB PNG → base64 10-20MB，最可能在实际使用中抵消 round-trip 收益。解决方案：尺寸超限时静默退化（已纳入 §B）

2. **api.md 绝对陈述矛盾**：现有"绝不返回 base64 图像"与 opt-in 特性直接冲突，读者会丧失信任。已纳入 §D 修复项

3. **整体设计质量充分**：exit handler 是 ImageContent 注入的正确层次，dispatch 保持协议无关。无基础性问题

## 7 维评估

### DR1 一致性 — concerns_found

- `include_image` 与现有 `include_screenshot`（get_ui_snapshot）语义一致。无问题。
- api.md line 40 的绝对陈述与 opt-in 特性矛盾，**必须修复**。已纳入计划。
- exit handler 是 ImageContent 注入的正确层次，架构一致。

### DR2 完整性 — concerns_found

- monitor=0（虚拟桌面）可产生 7-20MB base64，无退化路径。**已修复**：加尺寸阈值 3MB 自动退化。
- 内联尺寸控制二元化（on/off），无渐进控制。**当前可接受**，将来可加 `inline_max_bytes` config。
- 错误恢复规格已三态覆盖。`inline_image` 标记已在成功/失败路径统一。
- 同步 I/O 在 async handler 中阻塞事件循环。**已修复**：使用 `asyncio.to_thread`。

### DR3 可维护性 — clean

- 双路径（inline on/off）在 exit handler gate 处干净分离，回归面极小。
- ImageContent 知识正确位于协议边界，dispatch 层永不学习 MCP 类型。

### DR4 职责边界 — concerns_found

- `dispatch_args` 含 `include_image` 但 dispatch 不消费。**已修复**：dispatch 层 pop 该参数。
- Exit handler 重新读盘做 base64。虽是小冗余(读→写→读→编)，但 ~1-5ms 可接受，生产者-消费者分离更干净。

### DR5 残留与冗余 — concerns_found

- 三份文档（SKILL/api/deployment）信息分区良好：agent 指引/契约/运维，无重叠。
- **api.md 绝对陈述必须改为默认表述**（已纳入）。

### DR6 可移植性 — concerns_found

- `ImageContent` 由 `mcp>=1.0.0` 支持（项目已锁定），无依赖问题。
- **设计隐含 stdio-only 假设**：SSE 传输对大 base64 不兼容。已在不做(范围外)中注明。
- Windows 匿名管道 4KB buffer 是红色鲱鱼，MCP stdio 使用匿名管道（~64KB buffer），SDK 已处理。

### DR7 可扩展性 — clean

- `name == "screenshot"` 硬编码门控是正确 Occam，将来可引入 content-type registry。
- 默认关 + per-call opt-in 设计自然管理累积风险，模型控制何时付费。
