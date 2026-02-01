#!/usr/bin/env python3
"""
Arma Launcher entrypoint (compat wrapper).

Your old stack started everything via launcher.py.
This file keeps that convention while delegating to the refactored package.

Usage:
  python launcher.py run [--no-start] [--dry-run]
  python launcher.py plan
  python launcher.py api --host 0.0.0.0 --port 8000

Environment:
  LAUNCHER_MODE=run|api|plan   (optional, if no args are provided)
"""

from __future__ import annotations

import os
import sys


def _main() -> int:
    # If no CLI args are given (only script name), allow env-driven mode selection.
    # This is useful for Docker ENTRYPOINT usage.
    if len(sys.argv) == 1:
        mode = os.environ.get("LAUNCHER_MODE", "api").strip().lower()
        if mode not in ("run", "api", "plan"):
            mode = "api"
        sys.argv = [sys.argv[0], mode, "--host", "0.0.0.0", "--port", "8000"]

    # Delegate to the actual launcher CLI inside the package
    # Pass only argv[1:] to skip the script name
    from arma_launcher.cli import main as pkg_main
    return int(pkg_main(sys.argv[1:]))


if __name__ == "__main__":
    raise SystemExit(_main())
