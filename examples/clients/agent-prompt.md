# Computer Use MCP Agent Prompt

Load the MCP prompt `computer_use_guidance` if your client supports MCP prompts.
If not, use the guidance below.

Visual GUI tasks require a multimodal model or client-side local PNG reading. Text-only models must not perform screenshot-based clicking.

Operate with: observe -> semantic/UIA targeting -> action -> verify -> trace/task review.
Do not bypass MCP safety with pyautogui scripts.
