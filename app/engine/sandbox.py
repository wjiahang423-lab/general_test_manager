"""
ScriptSandbox — executes user-provided Python scripts via subprocess.

Each invocation spawns a fresh system-Python process, so test scripts have
access to whatever packages are installed in the system Python environment.
No third-party packages need to be bundled into the ATETest executable.

Public API
----------
ScriptSandbox.run(script_path, function_name, params, timeout) -> dict

Return value dict keys
----------------------
value   : any    – measurement or result value (None if not set)
unit    : str    – unit string
pass    : bool   – True = script considers the result acceptable
message : str    – human-readable note or exception traceback
stdout  : str    – captured stdout from the script function
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from typing import Any


# ---------------------------------------------------------------------------
# Subprocess runner — injected as -c code into the child Python process.
# Reads a JSON params file, calls the target function, writes a JSON result.
# ---------------------------------------------------------------------------
_RUNNER = """\
import sys, json, importlib.util, os, traceback, inspect
def _call(fn, params):
    try:
        sig = inspect.signature(fn)
    except (ValueError, TypeError):
        try:
            return fn(**params)
        except TypeError:
            return fn(params)
    pms = sig.parameters
    # no parameters at all
    if not pms:
        return fn()
    # accepts **kwargs
    if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in pms.values()):
        return fn(**params)
    positional = [p for p in pms.values()
                  if p.kind in (inspect.Parameter.POSITIONAL_ONLY,
                                inspect.Parameter.POSITIONAL_OR_KEYWORD)]
    # single param named 'params' → pass dict directly
    if len(positional) == 1 and positional[0].name == 'params':
        return fn(params)
    # keyword args → filter to known names
    accepted = {p.name for p in positional}
    return fn(**{k: v for k, v in params.items() if k in accepted})
def _main():
    with open(sys.argv[1], encoding='utf-8') as _f:
        _d = json.load(_f)
    _script_dir = os.path.dirname(_d['abs_path'])
    _scripts_root = _d['scripts_root']
    for _p in (_script_dir, _scripts_root):
        if _p not in sys.path:
            sys.path.insert(0, _p)
    try:
        _spec = importlib.util.spec_from_file_location('_sandbox_script', _d['abs_path'])
        _mod  = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)
        _fn = getattr(_mod, _d['function_name'], None)
        if _fn is None:
            raise AttributeError(f"Function '{_d['function_name']}' not found")
        _r = _call(_fn, _d['params'])
        if not isinstance(_r, dict):
            _r = {'value': _r, 'unit': '', 'pass': True, 'message': ''}
    except Exception:
        _r = {'value': None, 'unit': '', 'pass': False, 'message': traceback.format_exc()}
    with open(sys.argv[2], 'w', encoding='utf-8') as _f:
        json.dump(_r, _f, default=str)
_main()
"""


class ScriptSandbox:
    """Executes a named function from a .py script file via subprocess."""

    def __init__(self, scripts_root: str, python_exe: str = sys.executable):
        """
        Parameters
        ----------
        scripts_root : str
            Absolute path to the directory that contains test scripts.
        python_exe : str
            Path to the Python interpreter used to run scripts.
            Defaults to sys.executable (the interpreter running ATETest).
            Override via settings.SCRIPT_PYTHON or the python_exe.txt config file.
        """
        self._scripts_root = scripts_root
        self._python = python_exe

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(
        self,
        script_path: str,
        function_name: str,
        params: dict,
        timeout: float = 0.0,
    ) -> dict:
        """
        Spawn a subprocess running *python_exe*, load *script_path*, call
        *function_name* with *params*, and return a normalised result dict.

        Parameters
        ----------
        script_path   : str   Path relative to scripts_root.
        function_name : str   Callable to invoke inside the script.
        params        : dict  Forwarded to the callable as a single argument.
        timeout       : float Maximum wall-clock seconds; 0 means unlimited.

        Returns
        -------
        dict with keys: value, unit, pass, message, stdout
        """
        abs_path = os.path.join(self._scripts_root, script_path)
        if not os.path.isfile(abs_path):
            return self._error(f"Script not found: {abs_path!r}", value=None, unit="")

        # Write params to a temp file; result comes back via a second temp file.
        fd_p, params_file = tempfile.mkstemp(suffix="_params.json")
        fd_r, result_file = tempfile.mkstemp(suffix="_result.json")
        os.close(fd_p)
        os.close(fd_r)

        try:
            with open(params_file, "w", encoding="utf-8") as fh:
                json.dump(
                    {
                        "abs_path": abs_path,
                        "scripts_root": self._scripts_root,
                        "function_name": function_name,
                        "params": params,
                    },
                    fh,
                    default=str,
                )

            try:
                proc = subprocess.run(
                    [self._python, "-c", _RUNNER, params_file, result_file],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=timeout if timeout > 0 else None,
                )
                captured_stdout = proc.stdout or ""
                captured_stderr = proc.stderr or ""
            except subprocess.TimeoutExpired:
                return {
                    "value": None,
                    "unit": "",
                    "pass": False,
                    "message": f"Timeout after {timeout}s — '{function_name}' did not return.",
                    "stdout": "",
                }
            except FileNotFoundError:
                return self._error(
                    f"Python interpreter not found: {self._python!r}\n"
                    "Set the correct path in python_exe.txt or ATETEST_PYTHON env var.",
                    value=None, unit="",
                )

            # Read the result file written by the subprocess runner
            try:
                with open(result_file, "r", encoding="utf-8") as fh:
                    raw = json.load(fh)
            except Exception:
                # Runner crashed before writing the result file
                msg = captured_stderr or captured_stdout or "Subprocess exited with no result."
                return self._error(msg, value=None, unit="", stdout=captured_stdout)

            return {
                "value": raw.get("value"),
                "unit":  raw.get("unit", ""),
                "pass":  bool(raw.get("pass", False)),
                "message": raw.get("message", ""),
                "stdout": captured_stdout,
            }

        finally:
            for f in (params_file, result_file):
                try:
                    os.unlink(f)
                except OSError:
                    pass

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _error(msg: str, *, value: Any, unit: str, stdout: str = "") -> dict:
        return {
            "value": value,
            "unit": unit,
            "pass": False,
            "message": msg,
            "stdout": stdout,
        }


# ---------------------------------------------------------------------------
# Self-test (run with: python -m app.engine.sandbox)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import textwrap, shutil

    ROOT = tempfile.mkdtemp()

    def _write(filename: str, src: str) -> str:
        p = os.path.join(ROOT, filename)
        with open(p, "w", encoding="utf-8") as f:
            f.write(textwrap.dedent(src))
        return filename

    sb = ScriptSandbox(ROOT)

    # Test 1: normal execution (params["x"] arrives as int via JSON round-trip)
    _write("t1.py", """
        def run(params):
            return {"value": params["x"] * 2, "unit": "V", "pass": True, "message": "ok"}
    """)
    r = sb.run("t1.py", "run", {"x": 5}, timeout=10.0)
    assert r["value"] == 10 and r["pass"] is True, f"Test 1 failed: {r}"
    print("Test 1 PASS — normal execution")

    # Test 2: timeout
    _write("t2.py", """
        import time
        def run(params):
            time.sleep(30)
            return {"value": 1, "unit": "", "pass": True, "message": ""}
    """)
    r = sb.run("t2.py", "run", {}, timeout=1.0)
    assert r["pass"] is False and "Timeout" in r["message"], f"Test 2 failed: {r}"
    print("Test 2 PASS — timeout detected")

    # Test 3: exception inside script
    _write("t3.py", """
        def run(params):
            x = 1 / 0
    """)
    r = sb.run("t3.py", "run", {}, timeout=10.0)
    assert r["pass"] is False and "ZeroDivisionError" in r["message"], f"Test 3 failed: {r}"
    print("Test 3 PASS — exception captured")

    # Test 4: missing interpreter
    sb_bad = ScriptSandbox(ROOT, python_exe="no_such_python_xyz")
    r = sb_bad.run("t1.py", "run", {"x": 1}, timeout=5.0)
    assert r["pass"] is False and "not found" in r["message"], f"Test 4 failed: {r}"
    print("Test 4 PASS — bad interpreter error reported")

    shutil.rmtree(ROOT, ignore_errors=True)
    print("\nAll sandbox self-tests passed.")
