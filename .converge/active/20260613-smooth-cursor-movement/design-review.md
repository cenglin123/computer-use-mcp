> 

# Design Review · 20260613-smooth-cursor-movement

> Single-round advisory review. Findings do NOT block convergence.

## Reviewer output

```yaml
design_review:
  dimensions:
    - name: consistency
      status: concerns_found
      findings:
        - 默认 duration 值 0.2 在 core.py、mcp_server.py、cli.py 中各自声明；未来若调整默认值，需要跨三层同步修改。
        - core.py 的 docstring 只写“一个小的正值”，未写明实际默认值 0.2，而 MCP Schema 描述和 CLI help 都明确写了 0.2，文档对齐度不均。
        - CLI 子命令名为 move，core 函数与 MCP 工具名为 move_to；该不一致在变更前已存在，但在两者同时增加 --duration/duration 后更容易被注意到。
    - name: completeness
      status: concerns_found
      findings:
        - duration 未定义取值边界或 Schema 约束（如最小值 0），负值或异常大值会直接透传给 pyautogui，行为未在文档中说明。
        - 项目已有 config 模块用于 display.default_monitor 等默认项，但未提供全局配置入口让用户统一修改默认 duration。
        - 规格层面未描述缺失/非法 duration 参数时的错误处理路径。
    - name: maintainability
      status: concerns_found
      findings:
        - 0.2 这一魔术数字和“提取 duration → 调用 → 返回 duration”的处理模式在多处重复，增加了未来漂移的风险。
        - mcp_server.py 中 click 与 move_to 的校验、检查、调用、JSON 响应构造结构高度相似；若后续再为鼠标类工具增加公共参数，需要重复修改两次。
    - name: boundary_clarity
      status: concerns_found
      findings:
        - core、MCP、CLI 三层各自定义了 duration 默认值，没有哪一层被明确为“权威源”。直接调用 core 得到 0.2，MCP 缺省也返回 0.2，CLI 默认同样是 0.2，但契约是分散的而非由 core 统一拥有。
    - name: residue_and_redundancy
      status: concerns_found
      findings:
        - 0.2 默认值与 click/move_to 中 duration 处理流程在 mcp_server.py 和 cli.py 中均重复出现。这是既有模式的延续，但本次变更没有减少反而扩展了这种重复。
    - name: portability
      status: clean
      findings: []
    - name: scalability
      status: concerns_found
      findings:
        - 当前采用“每个工具、每层接口分别加参”的方式；未来若新增 drag_to 等鼠标工具，需要再次在三处复制类似的改动。
        - 没有可配置的默认 duration，扩展到按用户或按环境调整行为时，只能依赖每个调用方显式传参。
  highlights:
    - finding: |
        默认 duration（0.2 秒）在 core.py、mcp_server.py、cli.py 中被独立硬编码，且未定义取值边界或全局配置覆盖。
      why_it_matters: |
        随着鼠标类工具增多或根据用户反馈调整默认值，三层之间很容易出现默认行为不一致；同时无法集中满足按环境/用户偏好调整默认速度的需求。
      suggested_direction: |
        在 core 或 config 中建立 duration 默认值的单一权威来源，让 MCP 与 CLI 从该来源派生默认值；同时考虑补充文档化的取值范围与可选的配置级覆盖项。
```

## Highlights for user

1. **Centralize the default duration**: The literal `0.2` is repeated in `core.py`, `mcp_server.py`, and `cli.py`. Establish a single source of truth (e.g., a constant in `core.py` or a config key) so MCP and CLI derive their defaults from it.
2. **Document/validate acceptable range**: Negative or extremely large `duration` values are passed straight to `pyautogui`. Consider adding a documented valid range and optionally a guard.
3. **Reduce repetition for mouse tools**: `click` and `move_to` dispatch paths in `mcp_server.py` / `cli.py` are nearly identical. If more mouse tools are added, factor out common handling to avoid triplicating changes.
