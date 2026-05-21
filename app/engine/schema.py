"""
YAML serialisation layer for TestPlan.

Public API
----------
load_plan(path: str) -> TestPlan
    Load and validate a YAML test-plan file.
    Raises ValueError with a descriptive message when required fields are
    absent or structurally invalid.

save_plan(plan: TestPlan, path: str) -> None
    Serialise a TestPlan to a YAML file (creates parent directories if needed).
"""

from __future__ import annotations

import os

import yaml

from app.engine.models import TestPlan, TestSequence, TestStep, StepLimit


# ---------------------------------------------------------------------------
# Internal validation helpers
# ---------------------------------------------------------------------------

def _require(d: dict, *keys: str, context: str = "") -> None:
    """Raise ValueError if any of *keys* are missing from *d*."""
    for key in keys:
        if key not in d or d[key] is None:
            prefix = f"[{context}] " if context else ""
            raise ValueError(
                f"{prefix}Required field '{key}' is missing or null."
            )


def _validate_step(raw: dict, seq_name: str, step_index: int) -> None:
    """Validate a raw step dict; raise ValueError on any violation."""
    ctx = f"sequence '{seq_name}', step #{step_index + 1}"

    _require(raw, "name", "on_fail", context=ctx)

    # Accept both 'type' (YAML-friendly) and 'step_type' (internal)
    if "type" not in raw and "step_type" not in raw:
        raise ValueError(
            f"[{ctx}] Required field 'type' is missing."
        )

    step_type = raw.get("type") or raw.get("step_type")
    valid_types = {"script", "measurement", "prompt", "delay", "loop"}
    if step_type not in valid_types:
        raise ValueError(
            f"[{ctx}] Invalid step type '{step_type}'. "
            f"Must be one of: {sorted(valid_types)}."
        )

    valid_on_fail = {"abort", "continue"}
    if raw.get("on_fail") not in valid_on_fail:
        raise ValueError(
            f"[{ctx}] Invalid on_fail value '{raw.get('on_fail')}'. "
            f"Must be one of: {sorted(valid_on_fail)}."
        )

    # measurement / script steps must have a script path
    if step_type in {"script", "measurement"}:
        if not raw.get("script"):
            raise ValueError(
                f"[{ctx}] Step of type '{step_type}' requires a 'script' path."
            )
        if not raw.get("function"):
            raise ValueError(
                f"[{ctx}] Step of type '{step_type}' requires a 'function' name."
            )

    # loop steps must have script, function, loop_source, and loop_key
    if step_type == "loop":
        if not raw.get("script"):
            raise ValueError(f"[{ctx}] Loop step requires a 'script' path.")
        if not raw.get("function"):
            raise ValueError(f"[{ctx}] Loop step requires a 'function' name.")
        if not raw.get("loop_source"):
            raise ValueError(f"[{ctx}] Loop step requires a 'loop_source' path.")
        if not raw.get("loop_key"):
            raise ValueError(f"[{ctx}] Loop step requires a 'loop_key'.")
        valid_item_types = {"measurement", "script"}
        item_type = raw.get("loop_item_type", "measurement")
        if item_type not in valid_item_types:
            raise ValueError(
                f"[{ctx}] Invalid loop_item_type '{item_type}'. "
                f"Must be one of: {sorted(valid_item_types)}."
            )


def _validate_sequence(raw: dict, seq_index: int) -> None:
    ctx = f"sequence #{seq_index + 1}"
    _require(raw, "name", context=ctx)
    if "steps" not in raw or not isinstance(raw["steps"], list):
        raise ValueError(f"[{ctx}] 'steps' must be a non-empty list.")
    for i, step in enumerate(raw["steps"]):
        if not isinstance(step, dict):
            raise ValueError(
                f"[{ctx}, step #{i + 1}] Each step must be a YAML mapping."
            )
        _validate_step(step, raw["name"], i)


def _validate_plan(raw: dict) -> None:
    """Top-level plan validation."""
    _require(raw, "name", "version", "sequences", context="plan")
    if not isinstance(raw["sequences"], list) or len(raw["sequences"]) == 0:
        raise ValueError("[plan] 'sequences' must be a non-empty list.")
    for i, seq in enumerate(raw["sequences"]):
        if not isinstance(seq, dict):
            raise ValueError(f"[plan] sequences[{i}] must be a YAML mapping.")
        _validate_sequence(seq, i)


# ---------------------------------------------------------------------------
# Step building (handles 'type' → 'step_type' alias)
# ---------------------------------------------------------------------------

def _build_step(raw: dict) -> TestStep:
    """Convert a raw YAML step dict to a TestStep, normalising key aliases."""
    # Normalise type → step_type
    normalised = dict(raw)
    if "type" in normalised and "step_type" not in normalised:
        normalised["step_type"] = normalised.pop("type")

    raw_limits = normalised.get("limits")
    limits = StepLimit.from_dict(raw_limits) if isinstance(raw_limits, dict) else None

    return TestStep(
        name=normalised["name"],
        step_type=normalised["step_type"],
        script=normalised.get("script", ""),
        function=normalised.get("function", ""),
        params=normalised.get("params") or {},
        limits=limits,
        on_fail=normalised["on_fail"],
        timeout=float(normalised.get("timeout", 0)),
        retry_count=int(normalised.get("retry_count", 0)),
        breakpoint=bool(normalised.get("breakpoint", False)),
        return_map=normalised.get("return_map") or {},
        loop_source=normalised.get("loop_source", ""),
        loop_key=normalised.get("loop_key", ""),
        loop_item_type=normalised.get("loop_item_type", "measurement"),
        skip=bool(normalised.get("skip", False)),
    )


def _build_sequence(raw: dict) -> TestSequence:
    steps = [_build_step(s) for s in raw.get("steps", [])]
    return TestSequence(name=raw["name"], steps=steps, skip=bool(raw.get("skip", False)))


def _build_plan(raw: dict) -> TestPlan:
    sequences = [_build_sequence(s) for s in raw.get("sequences", [])]
    raw_setup    = raw.get("setup_sequence")
    raw_teardown = raw.get("teardown_sequence")
    return TestPlan(
        name=raw["name"],
        version=str(raw["version"]),
        description=raw.get("description", ""),
        global_params=raw.get("global_params") or {},
        sequences=sequences,
        variables=raw.get("variables") or {},
        variable_types=raw.get("variable_types") or {},
        setup_sequence=_build_sequence(raw_setup) if isinstance(raw_setup, dict) else None,
        teardown_sequence=_build_sequence(raw_teardown) if isinstance(raw_teardown, dict) else None,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_plan(path: str) -> TestPlan:
    """
    Load a YAML test-plan file and return a validated TestPlan.

    Parameters
    ----------
    path : str
        Filesystem path to the ``.yaml`` file.

    Returns
    -------
    TestPlan

    Raises
    ------
    FileNotFoundError
        If *path* does not exist.
    ValueError
        If the YAML content fails validation (missing/invalid fields).
    yaml.YAMLError
        If the file contains invalid YAML syntax.
    """
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Test-plan file not found: {path!r}")

    with open(path, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)

    if not isinstance(raw, dict):
        raise ValueError(
            f"Test-plan file {path!r} must contain a YAML mapping at the top level."
        )

    _validate_plan(raw)
    return _build_plan(raw)


def save_plan(plan: TestPlan, path: str) -> None:
    """
    Serialise *plan* to a YAML file at *path*.

    Parent directories are created automatically if they do not exist.

    Parameters
    ----------
    plan : TestPlan
    path : str
    """
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)

    raw = plan.to_dict()

    # Convert internal key 'step_type' back to 'type' for human-friendly YAML
    all_seqs = list(raw.get("sequences", []))
    for special_key in ("setup_sequence", "teardown_sequence"):
        if raw.get(special_key):
            all_seqs.append(raw[special_key])
    for seq in all_seqs:
        for step in seq.get("steps", []):
            if "step_type" in step:
                step["type"] = step.pop("step_type")

    with open(path, "w", encoding="utf-8") as fh:
        yaml.dump(
            raw,
            fh,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
        )
