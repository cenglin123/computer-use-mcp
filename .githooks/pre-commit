#!/bin/bash
# Pre-commit hook — Python stack.
# Install: cp this to .githooks/pre-commit && chmod +x .githooks/pre-commit && git config core.hooksPath .githooks
set -e

echo "=== Pre-commit: Python ==="

STAGED=()
while IFS= read -r file; do
    [ -n "$file" ] && STAGED+=("$file")
done < <(git diff --cached --name-only --diff-filter=ACM | grep -E '\.py$' || true)

if [ ${#STAGED[@]} -gt 0 ]; then
    if command -v ruff >/dev/null 2>&1; then
        ruff check "${STAGED[@]}"
        ruff format --check "${STAGED[@]}"
    elif command -v flake8 >/dev/null 2>&1; then
        flake8 "${STAGED[@]}"
    else
        echo "[pre-commit] WARN — no ruff/flake8 on PATH; skipping Python lint" >&2
    fi
fi

# AGENTS.md / CLAUDE.md / GEMINI.md 一致性检查
# 优先使用 agent_links.py；不可用时 fallback 到内联 MD5（兼容 md5sum / md5）
AGENTS_FILE="AGENTS.md"
CLAUDE_FILE="CLAUDE.md"
GEMINI_FILE="GEMINI.md"

check_agents_sync() {
    PYTHON_CMD=""
    if command -v python >/dev/null 2>&1; then
        PYTHON_CMD="python"
    elif command -v python3 >/dev/null 2>&1; then
        PYTHON_CMD="python3"
    fi
    if [ -f scripts/agent_links.py ] && [ -n "$PYTHON_CMD" ]; then
        $PYTHON_CMD scripts/agent_links.py check
        return $?
    fi

    if [ ! -f "$AGENTS_FILE" ] || [ ! -f "$CLAUDE_FILE" ] || [ ! -f "$GEMINI_FILE" ]; then
        echo "[pre-commit] FAIL — AGENTS.md / CLAUDE.md / GEMINI.md 存在缺失文件" >&2
        return 1
    fi

    if command -v md5sum >/dev/null 2>&1; then
        AGENTS_MD5=$(md5sum "$AGENTS_FILE" | awk '{print $1}')
        CLAUDE_MD5=$(md5sum "$CLAUDE_FILE" | awk '{print $1}')
        GEMINI_MD5=$(md5sum "$GEMINI_FILE" | awk '{print $1}')
    elif command -v md5 >/dev/null 2>&1; then
        AGENTS_MD5=$(md5 -q "$AGENTS_FILE")
        CLAUDE_MD5=$(md5 -q "$CLAUDE_FILE")
        GEMINI_MD5=$(md5 -q "$GEMINI_FILE")
    else
        echo "[pre-commit] WARN — 无法检查 AGENTS.md 同步（未找到 python/md5sum/md5）" >&2
        return 0
    fi

    if [ "$AGENTS_MD5" != "$CLAUDE_MD5" ] || [ "$AGENTS_MD5" != "$GEMINI_MD5" ]; then
        return 1
    fi
    return 0
}

if ! check_agents_sync; then
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "AGENTS.md / CLAUDE.md / GEMINI.md 三个文件的内容不一致。"
    echo ""
    echo "这可能是因为："
    echo "  1. 你修改了 AGENTS.md 但忘记运行同步脚本"
    echo "  2. 你直接修改了 CLAUDE.md 或 GEMINI.md（这是错误的）"
    echo ""
    echo "正确的流程："
    echo "  1. 编辑 AGENTS.md（不要编辑 CLAUDE.md 或 GEMINI.md）"
    echo "  2. 运行：python3 scripts/agent_links.py repair（或 python）"
    echo "  3. 重新 stage 并提交"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    exit 1
fi

echo "=== OK ==="
