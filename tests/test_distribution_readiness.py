from __future__ import annotations

from pathlib import Path


def test_distribution_guidance_entrypoints_exist() -> None:
    required = [
        Path("README.md"),
        Path("docs/agent-usage.md"),
        Path("skills/computer-use/SKILL.md"),
        Path(".agents/examples/clients/agent-prompt.md"),
    ]

    for path in required:
        assert path.exists(), path


def test_docs_reference_mcp_prompt_name() -> None:
    docs = "\n".join(
        path.read_text(encoding="utf-8")
        for path in [
            Path("README.md"),
            Path("docs/agent-usage.md"),
            Path("docs/deployment.md"),
        ]
    )

    assert "computer_use_guidance" in docs
    assert "saved_path" in docs or "读取" in docs or "read" in docs.lower()
    assert "doctor" in docs


def test_examples_do_not_hardcode_kimi_as_only_client() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "Generic MCP" in readme or "Generic MCP client" in readme
    before_first_run = readme
    for header in ("First run", "快速开始", "Get started"):
        if header in readme:
            before_first_run = readme.split(header, 1)[0]
            break
    assert "Kimi" not in before_first_run


def test_skill_copies_are_identical() -> None:
    """The canonical SKILL.md and its .agents distribution copy must not drift."""
    import hashlib

    source = Path("skills/computer-use/SKILL.md")
    dist = Path(".agents/skills/computer-use/SKILL.md")
    assert source.exists(), source
    assert dist.exists(), dist
    assert (
        hashlib.sha256(source.read_bytes()).hexdigest()
        == hashlib.sha256(dist.read_bytes()).hexdigest()
    ), "skills/computer-use/SKILL.md and .agents copy have drifted; run: Copy-Item skills/computer-use/SKILL.md .agents/skills/computer-use/SKILL.md"
