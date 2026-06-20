# 原始评审材料

外部评审 agent 对 computer-use-mcp 项目的综合评价。

## 一、总体定位

computer-use-mcp 是一个面向多模态 AI Agent 的 Windows 桌面自动化 MCP Server。它不是简单的"让 AI 操作鼠标键盘"，而是试图构建一个可审计、可复盘、有安全边界的桌面操作基础设施。
项目当前版本 0.1.0，代码量约 5200 行 Python，测试约 4300 行，测试/源码比 0.83，说明团队对测试投入较高。

## 二、架构设计：A

这是项目最强的部分。几个关键设计决策都体现了对真实落地场景的深刻理解：
1. 物理像素坐标系（mss 坐标）是正确选择
2. 感知跨屏、输入只限主屏
3. 截图只返回文件路径，不返回 base64
4. 安全分层设计
5. task + trace 两级审计模型

## 三、工程实现：B+

优势：模块化、错误处理、测试覆盖、配置管理、Agent 文档、审计存储。
可改进之处：
1. 对 pyautogui 的强依赖
2. UIA 的"可选但关键"位置
3. mcp_server.py 过大
4. 异常吞没较多

## 四、产品可用性：B

优势：多模态设计、标准工作流清晰、show 仪表盘式能力、应用启动工具。
局限：Windows only、多屏/Mixed-DPI 直接 fail-fast、需要多模态模型、真实 GUI 场景的鲁棒性待验证。

## 五、安全与治理：A-

做得好的：确定性规则、纵深防御、输入坐标限制主屏、敏感窗口阻止、密码控件检测、审计追踪。
潜在风险：
1. 危险命令正则可能绕过
2. allowed_commands 默认空列表
3. 截图可能泄露敏感信息

## 六、测试策略：B+

优势：测试/源码比 0.83、test_core.py 多显示器模拟、test_ui_automation.py mock control tree、test_mcp_server.py schema/batch 覆盖、test_safety.py 参数化。
不足：
1. 缺少真实 GUI 集成测试
2. 没有性能/压力测试
3. 安全规则的 fuzz 测试

## 七、文档与 Agent 协作：A

AGENTS.md / CLAUDE.md / GEMINI.md / STRUCTURE.md / docs/overview.md / skills/computer-use/SKILL.md / guidance / CHANGELOG.md / doctor 命令。

## 八、综合评分与总结

维度：架构设计 A、工程实现 B+、产品可用性 B、安全治理 A-、测试覆盖 B+、文档/Agent 协作 A。
总体评价：B+ / A- 之间，是一个很有潜力的 MVP。

## 九、优先级改进建议

1. P0：混合 DPI 多显示器支持
2. P0：增加真实 GUI 集成测试
3. P1：强化 allowed_commands 首次使用体验
4. P1：拆分 mcp_server.py
5. P2：引入视觉 fallback 和 OCR
6. P2：操作取消和超时机制
