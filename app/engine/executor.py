"""
StepExecutor — runs a single TestStep and returns a StepResult.

Responsibilities
----------------
- Merge global_params with step-level params before passing to sandbox.
- Resolve {{variable}} references in params and limit values.
- Dispatch to the correct handler based on step_type:
    measurement  → sandbox + numeric limit check
    script       → sandbox only (pass/fail from script return)
    prompt       → block until operator responds via on_prompt callback
    delay        → sleep for params['seconds'], honour abort
- Apply return_map: store return-dict fields into the variable store.
- Record wall-clock duration in milliseconds.
- Always return a StepResult; never raise.

Variable reference syntax
--------------------------
Any string value in params or limit low/high that matches  {{varname}}
is replaced with the current value of that variable from the store.
Mixed strings are also supported: "prefix_{{v}}_suffix".
"""

from __future__ import annotations

import re
import time
import threading
from typing import Callable, Any

from app.engine.models import TestStep, StepResult, StepLimit
from app.engine.sandbox import ScriptSandbox


class StepExecutor:
    """
    Parameters
    ----------
    sandbox        : ScriptSandbox
    on_prompt      : Callable[[str, dict], bool]
    abort_event    : threading.Event
    variable_store : dict
        Shared mutable dict.  {{varname}} references are resolved from here,
        and return_map results are written back into it.
    """

    def __init__(
        self,
        sandbox: ScriptSandbox,
        on_prompt: Callable[[str, dict], bool] | None = None,
        abort_event: threading.Event | None = None,
        variable_store: dict | None = None,
    ):
        self._sandbox = sandbox
        self._on_prompt = on_prompt or (lambda msg, p: True)
        self._abort_event = abort_event or threading.Event()
        self._vars: dict = variable_store if variable_store is not None else {}

    # ------------------------------------------------------------------
    # Variable helpers
    # ------------------------------------------------------------------

    def _resolve(self, value: Any) -> Any:
        """Replace {{varname}} tokens in a string value with store contents.
        Non-string values are returned unchanged.

        Pure references (the entire string is one {{varname}}) return the
        stored value in its original type (int, float, etc.) so that script
        functions receive the correct Python type rather than a string.
        Mixed strings such as 'prefix_{{v}}_suffix' are substituted and
        returned as a string, as before.
        """
        if not isinstance(value, str) or "{{" not in value:
            return value
        # Pure reference — return original typed value from the variable store
        m_pure = re.fullmatch(r"\{\{(.+?)\}\}", value.strip())
        if m_pure:
            v = self._vars.get(m_pure.group(1).strip())
            return v if v is not None else value
        # Mixed string — substitute each token and return a string
        def _sub(m: re.Match) -> str:
            v = self._vars.get(m.group(1).strip())
            return str(v) if v is not None else m.group(0)
        return re.sub(r"\{\{(.+?)\}\}", _sub, value)

    def _resolve_number(self, value: Any) -> float | None:
        """Resolve a limit value to float, or None if unresolvable."""
        if value is None:
            return None
        resolved = self._resolve(value)
        if resolved is None:
            return None
        try:
            return float(resolved)
        except (TypeError, ValueError):
            return None

    def _apply_return_map(self, return_map: dict, raw: dict) -> None:
        """Store raw result fields into variable_store per return_map.

        var_name is normalised: if the user accidentally typed '{{result}}'
        instead of 'result' in the variable-name column, the {{}} wrapper is
        stripped so the correct key is written into the store.
        """
        for result_key, var_name in return_map.items():
            if var_name and isinstance(var_name, str):
                m = re.fullmatch(r"\{\{(.+?)\}\}", var_name.strip())
                if m:
                    var_name = m.group(1).strip()
            if var_name and result_key in raw:
                self._vars[var_name] = raw[result_key]

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def run(self, step: TestStep, global_params: dict, seq_name: str = "") -> StepResult:
        """Execute *step* and return a StepResult.  Never raises.

        Retries up to step.retry_count extra times on FAIL/ERROR before
        applying on_fail policy.  Each retry is preceded by a 0.5 s pause.
        """
        # Merge then resolve {{variable}} references in every param value
        raw_params = {**global_params, **step.params}
        merged_params = {k: self._resolve(v) for k, v in raw_params.items()}
        t0 = time.monotonic()
        max_tries = max(1, step.retry_count + 1)
        last: tuple = ("ERROR", None, "", "Not executed")

        for attempt in range(max_tries):
            if self._abort_event.is_set():
                last = ("ERROR", None, "", "Aborted before step executed.")
                break
            if attempt > 0:
                time.sleep(0.5)
            try:
                if step.step_type == "measurement":
                    last = self._run_measurement(step, merged_params)
                elif step.step_type == "script":
                    last = self._run_script(step, merged_params)
                elif step.step_type == "prompt":
                    last = self._run_prompt(step, merged_params)
                elif step.step_type == "delay":
                    last = self._run_delay(step, merged_params)
                else:
                    last = ("ERROR", None, "", f"Unknown step_type: '{step.step_type}'")
            except Exception as exc:
                last = ("ERROR", None, "", str(exc))

            if last[0] == "PASS" or self._abort_event.is_set():
                break

        status, value, unit, message = last
        if attempt > 0:
            message = f"[第{attempt + 1}次尝试] {message or ''}".rstrip()
        duration_ms = int((time.monotonic() - t0) * 1000)

        return StepResult(
            step_name=step.name,
            seq_name=seq_name,
            result=status,
            value=value,
            unit=unit,
            message=message,
            duration_ms=duration_ms,
        )

    # ------------------------------------------------------------------
    # Step-type handlers
    # ------------------------------------------------------------------

    def _run_measurement(
        self, step: TestStep, params: dict
    ) -> tuple[str, Any, str, str]:
        """Run sandbox, apply return_map, then check numeric limits."""
        r = self._sandbox.run(
            step.script, step.function, params, timeout=step.timeout
        )
        # Apply return_map before evaluating limits
        self._apply_return_map(step.return_map, r)

        value = r["value"]
        unit = r.get("unit", "")
        message = r.get("message", "")
        stdout = r.get("stdout", "")
        if stdout:
            message = (message + "\n" + stdout).strip()

        if not r["pass"]:
            return ("FAIL", value, unit, message)

        # Apply YAML limits (with variable resolution)
        if step.limits is not None:
            # Determine the value to judge
            expr = (step.limits.expression or "").strip()
            if not expr:
                judge_value = value                          # default: r["value"]
            elif expr.startswith("{{"):
                # {{varname}} — if not already updated by return_map, auto-store
                # r["value"] into that variable so a scalar-returning function
                # works without requiring an explicit return_map entry.
                m = re.match(r"\{\{(.+?)\}\}", expr)
                if m:
                    var_name = m.group(1).strip()
                    if var_name not in step.return_map.values():
                        self._vars[var_name] = value
                judge_value = self._resolve(expr)
            elif expr in r:
                judge_value = r[expr]                        # named return-dict key
            else:
                judge_value = self._vars.get(expr, value)

            limit_pass, limit_msg = self._check_limits(judge_value, step.limits)
            if not limit_pass:
                return ("FAIL", judge_value, step.limits.unit or unit, limit_msg)
            unit = step.limits.unit or unit
            value = judge_value   # report the judged value

        return ("PASS", value, unit, message)

    def _run_script(
        self, step: TestStep, params: dict
    ) -> tuple[str, Any, str, str]:
        """Run sandbox, apply return_map; pass/fail from script return."""
        r = self._sandbox.run(
            step.script, step.function, params, timeout=step.timeout
        )
        self._apply_return_map(step.return_map, r)

        value = r["value"]
        unit = r.get("unit", "")
        message = r.get("message", "")
        stdout = r.get("stdout", "")
        if stdout:
            message = (message + "\n" + stdout).strip()

        status = "PASS" if r["pass"] else "FAIL"
        if not r["pass"] and not message:
            message = "Script returned pass=False with no message."
        return (status, value, unit, message)

    def _run_prompt(
        self, step: TestStep, params: dict
    ) -> tuple[str, Any, str, str]:
        """Block until operator confirms or cancels."""
        message_text = params.get("message", step.name)
        confirmed = self._on_prompt(message_text, params)
        if self._abort_event.is_set():
            return ("ERROR", None, "", "Aborted during operator prompt.")
        if confirmed:
            return ("PASS", None, "", "Operator confirmed.")
        return ("FAIL", None, "", "Operator cancelled.")

    def _run_delay(
        self, step: TestStep, params: dict
    ) -> tuple[str, Any, str, str]:
        """Sleep for params['seconds'], waking early on abort."""
        seconds = float(params.get("seconds", 0.0))
        deadline = time.monotonic() + seconds
        interval = 0.05  # poll interval
        while time.monotonic() < deadline:
            if self._abort_event.is_set():
                return ("ERROR", None, "", f"Delay aborted after {seconds}s.")
            remaining = deadline - time.monotonic()
            time.sleep(min(interval, max(0.0, remaining)))
        return ("PASS", seconds, "s", f"Waited {seconds}s")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _check_limits(self, value: Any, limits: StepLimit) -> tuple[bool, str]:
        """Return (passed, message).

        limit.low / .high are resolved through the variable store, so they
        can be literal floats or {{varname}} references.
        """
        try:
            v = float(value)
        except (TypeError, ValueError):
            return (False, f"Value {value!r} is not numeric; cannot compare against limits.")

        low  = self._resolve_number(limits.low)
        high = self._resolve_number(limits.high)

        lo_ok = low  is None or v >= low
        hi_ok = high is None or v <= high

        lo_str = str(low)  if low  is not None else "-∞"
        hi_str = str(high) if high is not None else "+∞"

        if lo_ok and hi_ok:
            return (True,  f"{v} {limits.unit} in [{lo_str}, {hi_str}]")
        return (False, f"{v} {limits.unit} out of range [{lo_str}, {hi_str}]")
