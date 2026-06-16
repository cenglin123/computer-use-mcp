from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from typing import Any


TIMEOUT_SECONDS = 30


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read-only MCP smoke test client.")
    parser.add_argument(
        "--server",
        default=sys.executable,
        help=(
            "Path to the Python interpreter used to launch the MCP server "
            "(default: sys.executable)."
        ),
    )
    parser.add_argument(
        "--args",
        nargs=argparse.REMAINDER,
        default=["-m", "computer_use.mcp_server"],
        help=(
            "Arguments passed to --server to start the MCP server "
            "(default: -m computer_use.mcp_server)."
        ),
    )
    return parser


def _send(proc: subprocess.Popen[str], msg: dict[str, Any]) -> None:
    if proc.stdin is None:
        raise RuntimeError("server stdin is not available")
    line = json.dumps(msg, ensure_ascii=False)
    proc.stdin.write(line + "\n")
    proc.stdin.flush()


def _read_response(proc: subprocess.Popen[str], expected_id: int) -> dict[str, Any]:
    if proc.stdout is None:
        raise RuntimeError("server stdout is not available")
    deadline = time.monotonic() + TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(f"server exited early with code {proc.returncode}")
        line = proc.stdout.readline()
        if not line:
            time.sleep(0.05)
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"invalid JSON from server: {line!r}") from exc
        if msg.get("id") == expected_id:
            if "error" in msg:
                raise RuntimeError(f"server error: {msg['error']}")
            return msg.get("result", {})
    raise TimeoutError(
        f"did not receive response for id={expected_id} within {TIMEOUT_SECONDS}s"
    )


def _stop_process(proc: subprocess.Popen[str]) -> str:
    if proc.poll() is None:
        proc.kill()
    try:
        _, stderr = proc.communicate(timeout=5)
    except Exception:
        stderr = ""
    return stderr or ""


def run(server: str, args: list[str]) -> dict[str, Any]:
    proc = subprocess.Popen(
        [server, *args],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    try:
        _send(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "computer-use-smoke",
                        "version": "0.1.0",
                    },
                },
            },
        )
        _read_response(proc, 1)

        _send(proc, {"jsonrpc": "2.0", "method": "notifications/initialized"})

        _send(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        tools_result = _read_response(proc, 2)

        _send(proc, {"jsonrpc": "2.0", "id": 3, "method": "prompts/list"})
        prompts_result = _read_response(proc, 3)

        _send(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {"name": "get_monitors", "arguments": {}},
            },
        )
        monitors_result = _read_response(proc, 4)

        return {
            "status": "ok",
            "tools": tools_result.get("tools", []),
            "prompts": prompts_result.get("prompts", []),
            "monitors": monitors_result.get("content", []),
        }
    except Exception as exc:
        stderr = _stop_process(proc)
        return {"status": "failed", "error": str(exc), "stderr": stderr}
    finally:
        if proc.poll() is None:
            _stop_process(proc)


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    result = run(args.server, args.args)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
