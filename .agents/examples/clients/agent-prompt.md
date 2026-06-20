# Computer Use MCP Agent Prompt

Load the MCP prompt `computer_use_guidance` if your client supports MCP prompts.
If not, use the guidance below.

Visual GUI tasks require a multimodal model or client-side local PNG reading. Text-only models must not perform screenshot-based clicking.

Operate with: observe -> semantic/UIA targeting -> action -> verify -> trace/task review.
Do not bypass MCP safety with pyautogui scripts.

## Verification rule

Every `screenshot` includes a red crosshair and center dot at the current cursor position. After any coordinate-based click, drag, scroll, or key action that depends on cursor position, take a fresh screenshot and confirm the red marker landed on the intended target before proceeding. If the marker is off target, re-measure coordinates from the screenshot or switch to UIA/semantic targeting.
