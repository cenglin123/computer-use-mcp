"""Allow `python -m computer_use` to run the debug CLI."""

from computer_use.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
