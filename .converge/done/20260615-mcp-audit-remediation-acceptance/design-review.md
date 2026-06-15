# Design Review · MCP Audit Remediation

本审查为收敛后的单轮咨询，不改变主循环验收结论。

```yaml
design_review:
  dimensions:
    - name: consistency
      status: concerns_found
      findings:
        - finding: "check_target_window 的参数表达范围大于当前实际策略；主屏由列表位置隐式表达。"
          location: "computer_use/safety.py; docs/api.md; computer_use/core.py"
          impact: "调用方可能误判策略覆盖范围，主屏正确性依赖未编码的排序约定。"
    - name: completeness
      status: concerns_found
      findings:
        - finding: "缺少新输入入口接入安全策略的统一机制；trace/report 观测失败没有统一任务语义。"
          location: "computer_use/mcp_server.py; computer_use/cli.py; computer_use/composite.py; computer_use/snapshot.py; computer_use/trace.py"
          impact: "新增入口或失败类型时容易遗漏校验并形成不同事实视图。"
    - name: maintainability
      status: concerns_found
      findings:
        - finding: "入口重复组合坐标、inspect、目标检查；runner 依赖 mcp_server 私有执行语义。"
          location: "computer_use/mcp_server.py; computer_use/runner.py"
          impact: "安全策略与传输层演化需要跨模块同步。"
    - name: boundary_clarity
      status: concerns_found
      findings:
        - finding: "core 是最终坐标边界，但不是完整目标安全边界；snapshot 检查与动作间仍有 TOCTOU。"
          location: "computer_use/core.py; computer_use/snapshot.py"
          impact: "新调用方可能把坐标安全误认为完整授权。"
    - name: residue_and_redundancy
      status: concerns_found
      findings:
        - finding: "core.py 存在两个 scroll 定义；转发层和默认值存在重复。"
          location: "computer_use/core.py; computer_use/composite.py; computer_use/snapshot.py"
          impact: "增加审阅成本与行为漂移概率。"
    - name: portability
      status: concerns_found
      findings:
        - finding: "主屏授权依赖 mss 枚举顺序，CoordinateSystem 进程级缓存不响应拓扑变化。"
          location: "computer_use/core.py; computer_use/safety.py"
          impact: "主屏切换、热插拔或替代后端可能使边界过期。"
    - name: scalability
      status: concerns_found
      findings:
        - finding: "失败语义由返回对象形状推断；每个新输入入口需复制安全组合。"
          location: "computer_use/mcp_server.py; computer_use/runner.py; computer_use/trace.py; computer_use/review.py"
          impact: "工具和错误类型增长会线性扩大安全审计面。"
  highlights:
    - finding: "完整安全执行边界没有单一可识别入口。"
      why_it_matters: "直接调用 core 可获得坐标保护，但可能遗漏目标检查。"
      suggested_direction: "区分低层原语与安全执行边界，并统一公开入口的授权机制。"
    - finding: "主屏安全语义由显示器列表顺序和进程级缓存共同决定。"
      why_it_matters: "拓扑变化可能让授权边界与当前桌面脱节。"
      suggested_direction: "显式建模主屏身份并定义拓扑刷新策略。"
    - finding: "失败分类、trace 与 report 语义耦合返回形状和 MCP 私有函数。"
      why_it_matters: "扩展后容易出现 unknown 分类与观测不一致。"
      suggested_direction: "建立独立于传输层的结构化执行结果与失败分类契约。"
```
