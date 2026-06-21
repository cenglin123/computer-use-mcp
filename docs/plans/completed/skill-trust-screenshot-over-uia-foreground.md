# 计划:SKILL 纪律 — 截图已确认即不复核窗口,UIA 前台=宿主是自指信号

## 背景

又一轮原神 MCP 测试(MiniMax-M3,会话 `ses_115c72eb5ffea524MBpenT82JP`)任务做成了,但思维过程暴露一类**现有 SKILL 未覆盖**的失败模式:

- 截图已清楚显示原神在前台,模型仍去 `get_ui_snapshot(scope=foreground)`,拿回的是**自己的宿主终端**(标题 `OC | 原神对话回顾点击与读取`)。
- 随后用 7.2s+6.2s 两段长思考 + 3 次 `wait_for_window`(原神/Genshin/云·原神全失败)去"破解"截图与 UIA 的矛盾。**3 个 failed trace 全部来自这一段。**
- 模型给自己总结了**错误教训**:"云·原神不能用 `wait_for_window`,建议写进 AGENTS.md"——抓错点;正确教训是截图已确认时根本不需要查窗口。

现有 SKILL 的自指规则(Safety Rules 里"Verify window ownership before acting on a desktop-scope UIA match")只覆盖 `find_control`/`click_by_text` 的 **desktop 命中**,没覆盖:
1. `get_ui_snapshot(scope=foreground)` 返回宿主终端这一入口;
2. "截图已确认目标即不必再用 UIA/wait_for_window 复核窗口"这条更上游的纪律。

## 目标

加入一条收敛性纪律,使模型在"截图已显示目标 App"后直接进入视觉定位,不再用 UIA/wait_for_window/find_control 复核窗口或定位游戏/云/自绘 App 的内部控件,并把"UIA 前台=自己的终端/IDE"识别为自指信号而非矛盾。

预期消除本轮问题 1(绕圈)、2(错误教训根因)、5(部分:减少无谓 UIA 探测分支)。

## 改动方案

只编辑 `skills/computer-use/SKILL.md`,改完 `Copy-Item` 同步 `.agents/skills/computer-use/SKILL.md`(`test_skill_copies_are_identical` 防漂移)。

### 改动点 A:Standard Loop 第 2 步收紧(截图即确认)

**替换**现有第 2 步尾部的"Use get_ui_snapshot(scope='foreground') or find_control for supplementary structured info"为带条件的版本:

> If the screenshot **does NOT clearly show** the target app's UI (blurry, partial, ambiguous), use `get_ui_snapshot(scope="foreground")` or `find_control` for supplementary structured info. **If screenshot clearly shows the target**, this is itself confirmation that the target is in the foreground — proceed directly to visual positioning; do not use `get_ui_snapshot`/`wait_for_window`/`find_control` to verify window state.

前提条件:截图分辨率/亮度足够辨识目标、目标占据画面可识别部分、模型处于多模态能力可用状态(非 text-only fallback)。条件不满足时 UIA 辅助仍可用。

### 改动点 B:新增一条 Failure Handling 纪律(UIA 前台=宿主)

新增条目,放在 Failure Handling 现有"UIA cannot see custom-drawn control"之后(与已有的"自绘界面回退视觉"放在同一位置,职责上都是错误恢复模式,而非 Safety Rules 的预防性检查)。大意:

> **`get_ui_snapshot(foreground)` 返回宿主终端是自指信号(而非矛盾)**
>
> 部分 App 不向 UIA 暴露内部控件(包括但不限于:游戏、云游戏、Electron 无辅助功能、控制台 UI、自绘安装界面)。对于这类 App,`get_ui_snapshot(scope="foreground")` 返回的"前台窗口"往往是你的宿主终端/IDE(标题甚至正带着任务文本)。这与现有 Safety Rules 中 `scope=desktop` `find_control` 命中宿主属同一类"false match"模式,只是入口不同。
>
> **前提条件**:以下判定仅在"截图已清楚显示目标 App 画面"(即已按 Standard Loop A 确认目标在前台)时才成立,否则"UIA 前台=宿主"意味着目标确实不在前台。
>
> 当条件满足时:
> - 看到 `get_ui_snapshot(foreground)` 返回宿主终端,识别为**自指信号**,不是需要破解的矛盾。
> - 不要反复换 App 名重试 `wait_for_window`——能看到目标画面即说明问题不在窗口标题匹配。
> - 直接走截图视觉定位 + `click_on_screenshot`,它不依赖 UIA 认为谁是前台。

### 改动点 C:不做(已由评议确认)

本轮开场有一条与任务无关的 `Get-Date` shell 调用。**跳过**——不为此单列规则,原因:
- 一次实例不构成足够高频的失败模式(防 SKILL 过拟合)
- 该行为是 Agent 通用试探惯性,不是 computer-use SKILL 的特有缺口
- 现有 Capability Boundary 的"禁 shell 探测桌面状态"已覆盖同类高风险行为;`Get-Date` 钻的是低风险空子,不配一条纪律

三路 Reviewer 中 2 票 skip、1 票 modify_existing(扩展现有规则 scope 以包含环境探针)。**按多数裁决 skip**。若将来 `Get-Date`/`whoami`/`hostname` 类无谓 shell 调用反复出现,可考慮在 Capability Boundary 末尾加一句通用规则"也不要为与任务无关的环境信息调用 shell",但当前不预做。

## 不做(范围外)

- **问题 3(角色错位)**:模型把"用 MCP 干 GUI 活"当成"开发 computer-use 仓库",读了 `docs/CURRENT.md`、权衡复杂任务闭环。根因是 opencode 跑在仓库目录、项目 AGENTS.md 被加载并与 MCP 任务串味,**不在 SKILL 能管辖范围**,本计划不处理(可另行讨论部署/目录隔离)。
- 不改任何代码、不动工具行为;纯 SKILL 文档纪律。
- 不新增 OCR/工具。

## 验收标准

- [ ] `skills/` 与 `.agents/` 两份 SKILL 一致:`pytest tests/test_distribution_readiness.py -v` 通过。
- [ ] A:Step 2 尾部替换为条件版本——"截图清晰显示目标→不复核窗口;不清晰→UIA 辅助"的二元分支逻辑正确,不产生二义性。
- [ ] B:自指信号判定显式前置"截图已确认目标在前台"条件,避免模型在截图未显示目标时也跳过窗口激活。
- [ ] B:"自指信号"与 Safety Rules 现有"false match"(desktop-scope)建立引用关系或用语统一,不引入孤立术语。
- [ ] B 放在 Failure Handling(而非 Safety Rules),与已有的"UIA cannot see custom-drawn control"比邻。
- [ ] 新纪律措辞不与现有"读图优先""自指核对""自绘界面回退视觉"重复或冲突(逐条核對)。
- [ ] 纪律明确截图"清晰可辨"的定性标准(分辨率/亮度/目标可见度/模型能力状态)作为跳 UIA 检查的前置条件。
- [ ] CHANGELOG 当天节追加一条 `docs:` 记录,注明来源会话与失败模式。
- [ ] 不引入对游戏/UIA 的任务枚举或硬编码 App 名(遵循 Bitter Lesson:讲通用判定,不写"云·原神"白名单)。

## 验证来源(本轮失败模式存档,便于评议)

- 截图已显示原神 → 仍 `get_ui_snapshot(foreground)` → 命中宿主终端 → 长思考纠结矛盾 → 3×`wait_for_window` 失败。
- 自我总结错误教训("云·原神不能 wait_for_window")。
