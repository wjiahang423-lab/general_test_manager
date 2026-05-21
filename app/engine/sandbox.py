"""
ScriptSandbox — dynamically loads and executes user-provided Python scripts
in an isolated namespace with timeout protection and stdout capture.

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

import contextlib
import importlib.util
import inspect
import io
import os
import sys
import threading
import traceback
import time
from typing import Any


class ScriptSandbox:
    """Executes a named function from a .py script file with isolation and timeout."""

    def __init__(self, scripts_root: str):
        """
        Parameters
        ----------
        scripts_root : str
            Absolute path to the directory that contains test scripts.
            Script paths in test plans are resolved relative to this root.
        """
        self._scripts_root = scripts_root

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
        Load *script_path* (relative to scripts_root), call *function_name*
        with *params*, and return a normalised result dict.

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
            return self._error(
                f"Script not found: {abs_path!r}", value=None, unit=""
            )

        # Container shared between calling thread and worker thread
        result_holder: list[dict] = []
        exc_holder: list[str] = []
        stdout_holder: list[str] = []

        def _worker():
            buf = io.StringIO()
            try:
                with contextlib.redirect_stdout(buf):
                    module = self._load_module(abs_path)
                    fn = getattr(module, function_name, None)
                    if fn is None or not callable(fn):
                        exc_holder.append(
                            f"Function '{function_name}' not found in {abs_path!r}"
                        )
                        return
                    raw = self._call_fn(fn, params)

                    # Normalise return value to a dict
                    if isinstance(raw, dict):
                        result_holder.append(raw)
                    else:
                        # Plain scalar return → wrap as {"value": raw, "pass": True}
                        result_holder.append({
                            "value": raw,
                            "unit": "",
                            "pass": True,
                            "message": "",
                        })
            except Exception:
                exc_holder.append(traceback.format_exc())
            finally:
                stdout_holder.append(buf.getvalue())

        t = threading.Thread(target=_worker, daemon=True)
        t.start()
        wait = timeout if timeout and timeout > 0 else None
        t.join(wait)

        captured_stdout = stdout_holder[0] if stdout_holder else ""

        if t.is_alive():
            # Thread timed out; it will finish eventually on its own.
            return {
                "value": None,
                "unit": "",
                "pass": False,
                "message": f"Timeout after {timeout}s — function '{function_name}' did not return.",
                "stdout": captured_stdout,
            }

        if exc_holder:
            return self._error(exc_holder[0], value=None, unit="", stdout=captured_stdout)

        if not result_holder:
            return self._error(
                f"Function '{function_name}' returned None.",
                value=None, unit="", stdout=captured_stdout
            )

        raw = result_holder[0]
        return {
            "value": raw.get("value"),
            "unit": raw.get("unit", ""),
            "pass": bool(raw.get("pass", False)),
            "message": raw.get("message", ""),
            "stdout": captured_stdout,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _call_fn(fn, params: dict):
        """Smart dispatch: inspect signature and call appropriately.

        Priority order
        --------------
        1. If the function accepts **kwargs or has no parameters → fn(**params)
        2. If it has a single positional parameter named 'params' → fn(params)
        3. Otherwise: filter params to only known parameter names → fn(**filtered)
           This handles global_params overflow gracefully.
        """
        try:
            sig = inspect.signature(fn)
        except (ValueError, TypeError):
            # Can't inspect — fall back to kwargs, then dict
            try:
                return fn(**params)
            except TypeError:
                return fn(params)

        parameters = sig.parameters

        # Case 1: accepts **kwargs — pass everything
        has_var_kw = any(
            p.kind == inspect.Parameter.VAR_KEYWORD
            for p in parameters.values()
        )
        if has_var_kw:
            return fn(**params)

        # Case 2: old-style single dict param (fn(params) or fn(p: dict))
        positional = [
            p for p in parameters.values()
            if p.kind in (
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
            )
        ]
        if len(positional) == 1 and positional[0].name == "params":
            return fn(params)

        # Case 3: keyword args — filter to only what the function accepts
        accepted = {p.name for p in positional}
        filtered = {k: v for k, v in params.items() if k in accepted}
        return fn(**filtered)

    @staticmethod
    def _load_module(abs_path: str):
        """Load a .py file as a fresh module each call (no caching)."""
        module_name = f"_eol_script_{os.path.basename(abs_path)}_{time.time_ns()}"
        spec = importlib.util.spec_from_file_location(module_name, abs_path)
        module = importlib.util.module_from_spec(spec)
        # Ensure the script's directory is on sys.path so relative imports work
        script_dir = os.path.dirname(abs_path)
        if script_dir not in sys.path:
            sys.path.insert(0, script_dir)
        spec.loader.exec_module(module)
        return module

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
    import tempfile, textwrap

    ROOT = tempfile.mkdtemp()

    # --- helper to write a temp script ---
    def _write(filename: str, src: str) -> str:
        p = os.path.join(ROOT, filename)
        with open(p, "w") as f:
            f.write(textwrap.dedent(src))
        return filename

    sb = ScriptSandbox(ROOT)

    # Test 1: normal execution
    _write("t1.py", """
        def run(params):
            return {"value": params["x"] * 2, "unit": "V", "pass": True, "message": "ok"}
    """)
    r = sb.run("t1.py", "run", {"x": 5}, timeout=2.0)
    assert r["value"] == 10 and r["pass"] is True, f"Test 1 failed: {r}"
    print("Test 1 PASS — normal execution")

    # Test 2: timeout
    _write("t2.py", """
        import time
        def run(params):
            time.sleep(10)
            return {"value": 1, "unit": "", "pass": True, "message": ""}
    """)
    r = sb.run("t2.py", "run", {}, timeout=0.5)
    assert r["pass"] is False and "Timeout" in r["message"], f"Test 2 failed: {r}"
    print("Test 2 PASS — timeout detected")

    # Test 3: exception inside script
    _write("t3.py", """
        def run(params):
            x = 1 / 0
    """)
    r = sb.run("t3.py", "run", {}, timeout=2.0)
    assert r["pass"] is False and "ZeroDivisionError" in r["message"], f"Test 3 failed: {r}"
    print("Test 3 PASS — exception captured")

    print("\nAll sandbox self-tests passed.")
