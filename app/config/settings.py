"""
Central path configuration for the general test manager.
All paths are resolved relative to the project root.
"""

from __future__ import annotations
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))

REPORTS_DIR      = os.path.join(PROJECT_ROOT, "reports")
TEST_PLANS_DIR   = os.path.join(PROJECT_ROOT, "test_plans")
TEST_SCRIPTS_DIR = os.path.join(PROJECT_ROOT, "test_scripts")

for _d in (REPORTS_DIR, TEST_PLANS_DIR, TEST_SCRIPTS_DIR):
    os.makedirs(_d, exist_ok=True)


def _resolve_script_python() -> str:
    """Return the Python interpreter used to execute test scripts.

    Priority:
      1. ATETEST_PYTHON environment variable
      2. python_exe.txt file in the project root (one path per line, first wins)
      3. sys.executable when running from source (not frozen)
      4. 'python' on the system PATH as last resort
    """
    env = os.environ.get("ATETEST_PYTHON", "").strip()
    if env and os.path.isfile(env):
        return env

    cfg = os.path.join(PROJECT_ROOT, "python_exe.txt")
    if os.path.isfile(cfg):
        with open(cfg, encoding="utf-8") as _f:
            for line in _f:
                val = line.strip()
                if val and not val.startswith("#") and os.path.isfile(val):
                    return val

    # sys.executable is the real interpreter only when NOT frozen by PyInstaller
    if not getattr(sys, "frozen", False):
        return sys.executable

    return "python"  # fallback: hope it's on PATH


SCRIPT_PYTHON = _resolve_script_python()
