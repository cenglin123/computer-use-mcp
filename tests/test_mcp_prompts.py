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
