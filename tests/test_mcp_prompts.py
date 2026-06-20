from __future__ import annotations


def test_guidance_prompt_registry_contains_distribution_prompts() -> None:
    from computer_use import guidance

    names = {prompt.name for prompt in guidance.PROMPTS}

    assert names == {
        "computer_use_guidance",
        "computer_use_visual_task",
        "computer_use_text_only_limits",
        "computer_use_safety_checklist",
    }


def test_guidance_mentions_multimodal_and_no_pyautogui_bypass() -> None:
    from computer_use import guidance

    text = guidance.prompt_text("computer_use_guidance")

    assert "multimodal" in text.lower()
    assert "text-only" in text.lower()
    assert "Do not bypass" in text
    assert "pyautogui" in text
    assert "start_task" in text
    assert "batch" in text
    assert "review_task_session" in text


def test_mcp_prompt_objects_are_registered() -> None:
    from computer_use import mcp_server

    names = {prompt.name for prompt in mcp_server.PROMPTS}

    assert "computer_use_guidance" in names
    prompt = next(
        item for item in mcp_server.PROMPTS if item.name == "computer_use_guidance"
    )
    assert "Windows GUI" in prompt.description


def test_get_prompt_result_contains_text_message() -> None:
    from computer_use import mcp_server

    result = mcp_server._get_prompt("computer_use_guidance")

    assert result.description
    assert len(result.messages) == 1
    assert result.messages[0].role == "user"
    assert "Computer Use MCP" in result.messages[0].content.text


def test_guidance_contains_task_id_rejection_rule() -> None:
    from computer_use import guidance

    text = guidance.prompt_text("computer_use_guidance")

    assert "task_id" in text
    assert "rejected" in text or "missing_task_id" in text


def test_guidance_contains_blocked_desktop_snapshot_rule() -> None:
    from computer_use import guidance

    text = guidance.prompt_text("computer_use_guidance")

    assert "desktop" in text
    assert "include_screenshot" in text
    assert "blocked" in text


def test_guidance_contains_png_and_long_response_rule() -> None:
    from computer_use import guidance

    text = guidance.prompt_text("computer_use_guidance")

    assert "60s" in text or "60 seconds" in text
    assert "PNG" in text or "png" in text.lower()


def test_visual_task_prompt_contains_blocked_snapshot_and_task_id_rules() -> None:
    from computer_use import guidance

    text = guidance.prompt_text("computer_use_visual_task")

    assert "blocked" in text
    assert "task_id" in text
    assert "rejected" in text or "missing_task_id" in text


def test_get_ui_snapshot_schema_description_contains_blocked_phrase() -> None:
    from computer_use.tools.schemas import TOOLS

    tool = next(t for t in TOOLS if t.name == "get_ui_snapshot")
    assert "blocked" in tool.description.lower()


def test_start_task_schema_description_contains_rejected_phrase() -> None:
    from computer_use.tools.schemas import TOOLS

    tool = next(t for t in TOOLS if t.name == "start_task")
    assert "rejected" in tool.description or "must" in tool.description.lower()
