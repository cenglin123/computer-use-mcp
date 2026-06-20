---
type: retrospective
object_slug: 20260621-coordinate-scaling-multiscreen
generated_at: 2026-06-21T02:00:00+08:00
---

# Retrospective · 20260621-coordinate-scaling-multiscreen

## 1. 结束模式

收敛（终止-a 严格通过变体）。R2 verdict=可执行 + blind1 verdict=可执行（零阻断）。

## 2. 阻断轨迹

R1=4(structural+implementation: 安全错误schema/安全链路跨层/tool_contract未指定/字段冗余) → R2=可执行 → blind1=pass

## 3. 经验教训

1. **安全链路跨层职责是高风险区**：core.click() 不做 inspect_point/check_target_window，这些在 dispatch 层。新工具如果直接调 core.click 会静默绕过 sensitive window 检查。R1 的 issue #2 是本计划最重要的发现。
2. **字段去重需显式决策**：image_width/height 与现有 width/height 语义等价但命名不同，会导致消费者困惑。
3. **盲审 A1 痕迹判定**：负面决策记录（"不需要 X 字段"）不是 archaeology——它们防止后续轮次重新争论，是合法设计rationale。

## blind_recheck

```yaml
blind_recheck:
  status: pass
  traces_reported: 0
  rounds_used: 1
  findings_count: 0
  escalated_to_main_loop: false
```

预算 config: max_blind_rechecks=1（用户指定），仅用 1 次即通过。
