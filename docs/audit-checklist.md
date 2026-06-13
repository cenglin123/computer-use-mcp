# 文档一致性审计清单

> **何时触发**：`python scripts/audit.py check` 报告发现后，或每 ~20 次任务 / 每月主动执行一次。

## 1. 机械检查结果复核

运行 `python scripts/audit.py check`，对每个非 OK 项逐条复核。

- [ ] 死链：文件被移动还是指针过时？
- [ ] STRUCTURE 索引偏差：`docs/` 下是否有多余或缺失文件？
- [ ] 同步断裂：运行 `python scripts/agent_links.py repair` 修复。
- [ ] 行数警告：`AGENTS.md` 是否超过 200 行 / 400 词？
- [ ] 依赖漂移：文档声明的技术栈与 `pyproject.toml` / `requirements.txt` 是否一致？
- [ ] 出生档案：是否已创建？

## 2. 关键设计决策仍成立？

重新读取 `docs/overview.md` 中“关键设计决策”段：

- [ ] 每条决策中提到的技术栈是否仍在 manifest 中？
- [ ] 约束条件（如“统一 DPI”）是否仍然有效？
- [ ] 最近 CHANGELOG 中的架构级变更是否已反映到 `docs/overview.md`？

## 3. 环境与部署仍准确？

- [ ] 环境变量列表与 `config.yaml` / 代码一致？
- [ ] 启动命令仍能执行？
- [ ] 多显示器 / DPI 相关说明是否仍然准确？

## 4. 未记录的重要变更

- [ ] 浏览 CHANGELOG 最近 ~30 天：是否有架构级变更未反映到 docs/？
- [ ] `git log --oneline --since="1 month ago"` 中是否有遗漏的重大改动？

## 5. 完工

- [ ] 审计期间的修改已通过 `python scripts/agent_links.py check`
- [ ] 审计结果写入 CHANGELOG：
  ```bash
  python scripts/changelog.py add \
    --title "文档一致性审计" \
    --body "机械检查 + 手动裁决完成。修复项：<列出>；确认为误报：<列出>；仍待处理：<列出>"
  ```
- [ ] 将审计日期记录到本文件末尾的“审计记录”中

## 审计记录

<!-- 每次完成审计后在此追加一条记录，格式：YYYY-MM-DD — 审计摘要 -->
