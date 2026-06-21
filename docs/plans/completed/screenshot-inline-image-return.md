# 计划:screenshot 可选内联返图(削减观察往返延迟)

## 背景与目标

当前每次"观察"是两个往返:`screenshot`(只回 `saved_path` + 坐标 metadata) → 模型再用 `Read` 读盘看图。对多模态客户端,这多出一个往返 + 一次 Read 生成,是单任务耗时的主要可削减项之一(实测一次 4 分钟的任务里约 2 次观察 = 约 2 个可省往返)。

目标:让 `screenshot` 能在工具结果里**直接内联返回图像**,把"screenshot + Read"两个往返合并为一个,同时**不回归**现有路径式流程和 text-only 客户端。

## 关键约束(来自链路评估)

1. **token 成本:传输不变,决策成本增加**:一张全屏图作为 `ImageContent` 的传输字节量与 `Read` 路径一致。但当前流程中,模型可以选择不 Read 某些中间截图(如验证性截图中跳过视觉推理,仅检查 metadata);`include_image=true` 后每次截图都被迫进入模型上下文,模型失去"跳过权衡"的机会。→ **不是严格中性**,应将此成本权衡告知 agent(SKILL 指引中建议:仅对需要视觉观察的截图开 inline,验证落点等截图保持默认关)。
2. **体积在"线"上**:游戏截图 PNG 常 1–5MB,base64 +33%。每张都塞进 stdio JSON-RPC 有序列化/传输延迟 → 必须 **per-call opt-in**,默认关。`monitor=0`(全虚拟桌面)可产生 8–15MB PNG → base64 10–20MB,不加防护会严重劣化体验。→ 实现时加尺寸阈值:base64 编码后 > 3MB 时静默退化为纯文本,TextContent 加 `inline_image_skipped: "payload_too_large"`。
3. **降采样仅作用于内联副本时安全**:**磁盘全图**始终全分辨率存储,供 `click_on_screenshot` 的坐标映射使用。内联副本理论上可降采样以减小传输体积——但为了保持一致的用户体验(不会得到一张缩图、一张原图造成混淆),**本期不做内联降采样,全分辨率内联更为稳妥**。这条仅在将来有显著传输瓶颈时才重新评估。
4. **客户端硬依赖**:目标客户端必须真的渲染工具结果里的 `ImageContent`,否则模型看不到、仍需 `Read`,纯负收益。→ 默认关 + 文档显式要求上线前确认。
5. **绝不把 base64 塞进 JSON 文本字段**:只走独立 `ImageContent` block;文本块保持现状(`saved_path`/metadata/sidecar 不变)。
6. **敏感窗口**:内联必须是打码后的 PNG(用结果里的 `saved_path`,已指向 redacted 文件)。

## 问题清单与影响文件

### A. `screenshot` 增加 `include_image` 参数

- `computer_use/tools/schemas.py` — `screenshot` 工具 inputSchema 增 `include_image: {type: boolean, default: false}`,描述写明:仅多模态客户端按需开启;全分辨率内联;默认关以保持上下文精简。
- 行为:`include_image` 仅控制"是否在工具结果里附带 ImageContent",**不改变**存盘、metadata、sidecar、返回 JSON 文本的任何现有字段。

### B. 出口 handler 追加 ImageContent

- `computer_use/mcp_server.py` `call_tool`(当前 `return [TextContent(...)]`,约 1578-1581):
  - 改为可返回 `list[TextContent | ImageContent]`;`mcp.types` 新增 `ImageContent` import。
  - 仅当 `name == "screenshot"` 且 `arguments.get("include_image")` 为真时:从结果 JSON 解析 `saved_path`,读字节 → base64 → 追加 `ImageContent(type="image", data=..., mimeType="image/png")`。
  - 成功时 TextContent 加 `inline_image: true` 标记,使模型可区分"内联成功"vs"静默退化"。
  - PNG 读取与 base64 编码要走 `asyncio.to_thread()`,避免同步 I/O 阻塞事件循环(大图编码可达 50-200ms)。
  - 文本块超限防护:若 `saved_path` 文件的 base64 编码后 > 3MB(约 2.25MB 原始 PNG),静默退化为纯文本,TextContent 加 `inline_image_skipped: "payload_too_large"`。
  - 解析失败 / 文件缺失 / 无 `saved_path`(如错误结果):静默退化为只回 TextContent,不抛错。
  - 读图与编码失败也要捕获,退化为纯文本 + 在文本块补一个 `inline_image: false` 标记,绝不让内联失败影响主结果。
- `computer_use/mcp_server.py` `_call_tool`(约 251 行):在构造 `dispatch_args` 后、传入 `_dispatch_tool` 前,`pop("include_image", None)` 移除非 dispatch 参数——参数由 exit handler 消费,dispatch 层不关心,不应出现在 trace 记录中。
- 注意:`call_tool` 是 MCP 出口,内层 `batch`/`run_task_plan` 通过 `_call_tool` 复用 dispatch、**不经过**这个出口 → 内联只在顶层单次 `screenshot` 生效,batch 内的 screenshot 仍走路径式(符合预期,避免 batch 里多图灌爆)。需在计划里确认 `_establish_context`/`_handle_tool_call` 链路不会吞掉 `include_image` 参数(它在 `_TASK_CONTEXT_EXCLUDED` 之外,会被透传)。

### C. 部署级配置(本期做 per-call,留后续接口)

- `config.yaml` 可选项:
  - `screenshot.default_inline_image` (bool):供已确认客户端支持 ImageContent 的多模态部署全局开。本期只设计接口,不实现默认逻辑。
  - `screenshot.inline_max_bytes` (int, 默认 3_000_000):base64 编码后超限时静默退化。本期实现 hard-coded 值,后续可迁移至此。
- 客户端的动态判断:**agent 无标准 MCP 机制查询宿主是否渲染 ImageContent**。部署决策应转运维配置锁死(在 `deployment.md` 中记录:已知支持 X 客户端时可在配置中开启)。

### D. SKILL / 文档

- `skills/computer-use/SKILL.md`(改后 `Copy-Item` 同步 `.agents/`):
  - 在 Screenshot 流程说明 `include_image`:**仅当确认当前客户端会渲染 MCP 工具结果图像时**才开;开了就不必再 `Read` 该截图;坐标点击仍走 `click_on_screenshot`(内联是全分辨率,坐标空间与磁盘文件一致)。
  - **调和 Context Budget 矛盾**:现有 §Context Budget 第 2 条(约 175 行)写"Use the MCP screenshot tool instead; it returns only saved_path"及第 5 条(约 193 行)"Do not include screenshot base64 in responses"。必须在这两处加 opt-in 例外说明——"除非显式传 `include_image=true`,此时 base64 在独立的 ImageContent block 中,不在 JSON 文本内"。
  - 在"验证落点"和"中间验证截图"场景中特别注明不建议开 `include_image`(节省 vision token 和传输体积)。
  - 不改"默认 Read 读盘"为主路径的现有指引(默认关)。
- `docs/api.md` — `screenshot` 增 `include_image` 说明 + 客户端依赖与体积权衡。
  - **必须修改**第 33 行(约)"上下文保护原则:screenshot 始终将 PNG 保存到本地目录,上下文只保留文件路径引用,绝不返回 base64 图像"→ 改为带 opt-in 例外:默认不返回,`include_image=true` 时以 `ImageContent` 块返回。
  - **必须修改**第 40 行"图像从不会以 base64 形式进入上下文"→ 改为"默认不包含 base64;启用 `include_image` 后,全分辨率 base64 在独立的 ImageContent 块中"。 
- `docs/deployment.md` — 增"何时开启内联返图"的部署判断(客户端能力、stdio 体积)。
- `CHANGELOG.md` — 当天节追加。

## 验收标准

- [ ] `include_image=false`(默认):结果与现状逐字段一致,仍只回一个 TextContent;现有测试全绿(零回归)。
- [ ] `include_image=true`:返回 `[TextContent, ImageContent]`,ImageContent 为全分辨率 PNG 的 base64,mimeType 正确;TextContent 仍含 `saved_path`/metadata。
- [ ] 内联图与磁盘文件同分辨率(断言宽高一致),保证 `click_on_screenshot` 坐标可用。
- [ ] 错误/缺文件/敏感打码:内联失败安全退化为纯文本;敏感场景内联的是 redacted PNG。
- [ ] base64 不出现在 TextContent 的 JSON 文本里(只在 ImageContent.data)。
- [ ] 成功时 TextContent 含 `inline_image: true`;失败时含 `inline_image: false` 或 `inline_image_skipped: "payload_too_large"`。
- [ ] `monitor=0`(全虚拟桌面)截图若 base64 > 3MB 自动退化,不进 ImageContent。
- [ ] `batch` 内的 screenshot 不内联(顶层出口才内联),验证 batch 行为不变。
- [ ] PNG 读 + base64 编码走 `asyncio.to_thread()`,不阻塞事件循环(中断单步 trace 验证:连续两次截图不会相互阻塞)。
- [ ] `include_image` 不出现在 trace 记录的 args 中(dispatch 层已 pop)。
- [ ] 新增单测覆盖:默认关、开启返双 block、解析失败退化、monitor=0 超限退化、redacted 内联;`pytest tests/` 全绿;SKILL 双副本一致。
- [ ] **上线前最小验证**:手工构造一个带 `ImageContent` 的工具结果,确认目标客户端(OpenCode + Kimi)确实渲染图像;若不支持,特性对该客户端为 no-op,不应在文档中推荐开启。
- [ ] reviewer 视角:确认 `include_image` 透传未被 task 上下文链路吞掉;确认出口改动不影响其它工具(仍单 TextContent);确认同步 I/O 已用 `asyncio.to_thread` 隔离。

## 风险与未决

- **客户端 ImageContent 渲染支持未知**(OpenCode + Kimi)。**这是前置判断**:上线前必须做一次最小验证(手工构造 mock ImageContent 工具结果,确认客户端渲染),而不应等全量实现完成后再验证。不支持则此特性对该客户端为 no-op,文档不应推荐开启。已验证支持后,agent 仍无机制动态判断客户端能力→部署决策转运维配置锁死(`deployment.md` 记录已知支持/不支持的客户端列表)。
- **全分辨率 base64 传输延迟**:stdio pipe 上 4MB base64 实测约 50-150ms(Windows 匿名管道 ~64KB buffer),省掉的 round-trip 约 2-5s,净收益大概率显著。但极端场景(超大游戏截图 + 慢 IO)可能反转。测量协议建议:(a) 同机同 monitor 对比 `include_image=false` vs `true` 的端到端耗时,(b) 至少测试 3 种分辨率(1080p/1440p/4K),(c) 产出明确 go/no-go 数据点。
- **SSE 传输不兼容**:当前 stdio-only,无问题。若将来加 SSE 传输,内联图的大 base64 会超过多数代理的 SSE 消息上限(nginx default 8KB, Cloudflare 1MB)。需额外处理。
- **API 文档矛盾**:现有 api.md 写"绝不返回 base64 图像",必须改为带 opt-in 例外的表述。已在 §D 中标明。
- **SKILL Context Budget 矛盾**:现有指引明确禁止 base64 入上下文,需调和。已在 §D 中标明。
- **同步 I/O 阻塞事件循环**:`call_tool` 是 `async def`,但 PNG 读 + base64 编码是同步操作。已在 §B 中用 `asyncio.to_thread` 解决。

## 不做(范围外)

- 不改默认行为、不动路径式主流程。
- 不做内联图降采样(仅做尺寸超限时的全量退化,不做部分降采样。理论上可只对内联副本降采样而保留磁盘全图,但本期为保持体验一致不做——将来若传输瓶颈显著可重评估)。
- 不在 `batch`/`run_task_plan` 内联截图。
- 本期不做 `get_ui_snapshot(include_screenshot=true)` 的 ImageContent 内联(scope 不符,单独评估)。
- 不做 SSE 传输适配(当前 stdio-only;SSE 消息大小限制与本特性不兼容,若将来加 SSE 需额外处理)。
- 本期不做部署级全局默认(仅留后续接口讨论)。
