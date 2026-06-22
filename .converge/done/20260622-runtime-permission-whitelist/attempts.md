# Attempt Log · 20260622-runtime-permission-whitelist

## Round 1 attempt · issue 1
- source: converge_loop
- reviewer_backend: opencode (×3 parallel)
- Issue: "check_target_window 执行顺序错误：运行时异常检查在硬编码敏感进程检查之前，导致 keepass/certmgr 可被绕过"
- Issue 归因（reviewer 判定）: plan_defect
- plan_amendment_required: true
- Approach: 修改 check_target_window 代码段，硬编码检查先于运行时检查
- Diff: plan updated — check_target_window code reordered (hardcoded first, runtime second)
- R1 verdict: Accepted
- **[Orchestrator Detection at R1 inner loop]** Verified fix: hardcoded checks at lines 548-555 raise SensitiveProcessError/SensitiveWindowError BEFORE runtime exception check at lines 557-559. keepass bypass blocked. ✓

## Round 1 attempt · issue 2
- source: converge_loop
- reviewer_backend: opencode (×3 parallel)
- Issue: "双重默认命令定义且内容不一致：safety.py 的 _BUILTIN_DEFAULT_COMMANDS (16项) vs config.py 的 _BUILTIN_COMMANDS (11项)"
- Issue 归因（reviewer 判定）: plan_defect
- plan_amendment_required: true
- Approach: 统一到 config.py 单一真值源，safety.py 从 config 读取
- Diff: (pending)

## Round 1 attempt · issue 3
- source: converge_loop
- reviewer_backend: opencode (×3 parallel)
- Issue: "consume 函数无集成点：consume_command_permission 和 consume_window_exception 定义了但从未被调用"
- Issue 归因（reviewer 判定）: plan_defect
- plan_amendment_required: true
- Approach: 在 launcher.py launch 成功后和 mcp_server.py 输入成功后调用 consume
- Diff: (pending)

## Round 1 attempt · issue 4
- source: converge_loop
- reviewer_backend: opencode (×3 parallel)
- Issue: "SafetyError regex 字符串耦合：mcp_server.py 用正则解析错误消息字符串区分敏感窗口/进程类型"
- Issue 归因（reviewer 判定）: plan_defect
- plan_amendment_required: true
- Approach: 定义 SafetyError 子类携带结构化字段，mcp_server.py 用 isinstance 检测
- Diff: (pending)

## Round 1 attempt · issue 5
- source: converge_loop
- reviewer_backend: opencode (×3 parallel)
- Issue: "_append_to_config negate 参数是死代码，save_permanent_window_exception 无实际效果"
- Issue 归因（reviewer 判定）: plan_defect
- plan_amendment_required: true
- Approach: 移除 negate 参数和 save_permanent_window_exception（窗口例外不支持 permanent），简化 API
- Diff: (pending)

## Round 1 attempt · issue 6
- source: converge_loop
- reviewer_backend: opencode (×3 parallel)
- Issue: "无法禁用内置默认命令：_allowed_commands() 永远返回非空列表，严格安全需求的用户无法选择只依赖运行时白名单"
- Issue 归因（reviewer 判定）: plan_defect
- plan_amendment_required: true
- Approach: 添加 use_builtin_defaults 配置开关，默认 true，可设为 false
- Diff: (pending)
