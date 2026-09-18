"""Entry point invoked via `python -m ts_agent_helper` from the launchers."""

from __future__ import annotations

import sys

from .cli import main


if __name__ == "__main__":
    sys.exit(main())
