from __future__ import annotations


def test_smoke_script_import_does_not_load_pyautogui() -> None:
    import importlib.util
    import sys
    from pathlib import Path

    sys.modules.pop("pyautogui", None)
    script_path = Path(__file__).resolve().parents[1] / "tools" / "smoke_mcp_client.py"
    spec = importlib.util.spec_from_file_location(
        "smoke_mcp_client",
        script_path,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    assert "pyautogui" not in sys.modules


def test_smoke_script_parser_accepts_server_args_without_separator() -> None:
    import importlib.util
    from pathlib import Path

    script_path = Path(__file__).resolve().parents[1] / "tools" / "smoke_mcp_client.py"
    spec = importlib.util.spec_from_file_location("smoke_mcp_client", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    parser = module._build_parser()
    args = parser.parse_args(
        ["--server", "python.exe", "--args", "-m", "computer_use.mcp_server"]
    )

    assert args.server == "python.exe"
    assert args.args == ["-m", "computer_use.mcp_server"]
