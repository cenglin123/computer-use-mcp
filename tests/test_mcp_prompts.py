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
