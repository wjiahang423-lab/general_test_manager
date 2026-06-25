"""
Central path configuration for the general test manager.
All paths are resolved relative to the project root.
"""

from __future__ import annotations
import os
import shutil
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
      4. a resolved 'python' on the system PATH as last resort
    """
    def _candidate_path(raw: str) -> str:
        if not raw:
            return ""
        path = raw.strip()
        if not path or path.startswith("#"):
            return ""
        if not os.path.isabs(path):
            path = os.path.abspath(os.path.join(PROJECT_ROOT, path))
        if os.path.isfile(path):
            return path
        resolved = shutil.which(path)
        if resolved:
            return resolved
        return ""

    env = _candidate_path(os.environ.get("ATETEST_PYTHON", ""))
    if env:
        return env

    cfg = os.path.join(PROJECT_ROOT, "python_exe.txt")
    if os.path.isfile(cfg):
        with open(cfg, encoding="utf-8") as _f:
            for line in _f:
                candidate = _candidate_path(line)
                if candidate:
                    return candidate

    # sys.executable is the real interpreter only when NOT frozen by PyInstaller
    if not getattr(sys, "frozen", False):
        return sys.executable

    return shutil.which("python") or sys.executable


SCRIPT_PYTHON = _resolve_script_python()
