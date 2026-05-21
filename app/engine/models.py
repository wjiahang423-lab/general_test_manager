"""
Core data models for the EOL test framework.

Each dataclass provides:
  - to_dict()           -> plain dict suitable for JSON/YAML serialisation
  - from_dict(d: dict)  -> reconstructed dataclass instance  (staticmethod)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


# ---------------------------------------------------------------------------
# StepLimit
# ---------------------------------------------------------------------------

@dataclass
class StepLimit:
    """Numeric pass/fail limits for a measurement step.

    expression
        What to compare against the limits.  Three forms:
          ""            → use r["value"] from the function return dict (default)
          "voltage"     → use r["voltage"] (any other key in the return dict)
          "{{varname}}" → look up the variable store at runtime
        Supports mixed strings too: "{{v}}" alone is most common.

    low / high
        The bounds.  Can be a literal float, or "{{varname}}" resolved at runtime.
    """

    low: float | str | None   # Lower bound
    high: float | str | None  # Upper bound
    unit: str = ""
    expression: str = ""      # What to judge; empty → r["value"]

    def to_dict(self) -> dict:
        d: dict = {
            "low":  self.low,
            "high": self.high,
            "unit": self.unit,
        }
        if self.expression:
            d["expression"] = self.expression
        return d

    @staticmethod
    def from_dict(d: dict) -> StepLimit:
        def _coerce(v):
            if v is None:
                return None
            if isinstance(v, str):
                return v
            try:
                return float(v)
            except (TypeError, ValueError):
                return v
        return StepLimit(
            low=_coerce(d.get("low")),
            high=_coerce(d.get("high")),
            unit=d.get("unit", ""),
            expression=str(d.get("expression", "") or ""),
        )


# ---------------------------------------------------------------------------
# TestStep
# ---------------------------------------------------------------------------

@dataclass
class TestStep:
    """A single step inside a test sequence."""

    name: str
    step_type: str          # "script" | "measurement" | "prompt" | "delay"
    script: str             # Path relative to test_scripts/; empty for prompt/delay
    function: str           # Name of the callable inside *script*
    params: dict            # Extra parameters forwarded to the script function
    limits: StepLimit | None  # Only meaningful for measurement steps
    on_fail: str            # "abort" | "continue"
    timeout: float          # Seconds; 0 means unlimited
    retry_count: int = 0    # Extra attempts on failure (0 = no retry)
    breakpoint: bool = False  # Pause before executing this step
    # Maps return-dict keys to variable names, e.g. {"value": "measured_V"}
    return_map: dict = field(default_factory=dict)
    # Loop step fields (only used when step_type == "loop")
    loop_source: str = ""            # Path to YAML data file, relative to scripts_root
    loop_key: str = ""               # Top-level key in the YAML to iterate over
    loop_item_type: str = "measurement"  # step_type assigned to each expanded item
    # Skip: when True the step is not executed; a SKIP StepResult is emitted instead
    skip: bool = False

    def to_dict(self) -> dict:
        d = {
            "name": self.name,
            "step_type": self.step_type,
            "script": self.script,
            "function": self.function,
            "params": dict(self.params),
            "limits": self.limits.to_dict() if self.limits is not None else None,
            "on_fail": self.on_fail,
            "timeout": self.timeout,
            "retry_count": self.retry_count,
            "breakpoint": self.breakpoint,
            "return_map": dict(self.return_map),
        }
        if self.loop_source:
            d["loop_source"] = self.loop_source
        if self.loop_key:
            d["loop_key"] = self.loop_key
        if self.step_type == "loop":
            d["loop_item_type"] = self.loop_item_type
        if self.skip:
            d["skip"] = True
        return d

    @staticmethod
    def from_dict(d: dict) -> TestStep:
        raw_limits = d.get("limits")
        limits = StepLimit.from_dict(raw_limits) if isinstance(raw_limits, dict) else None
        return TestStep(
            name=d["name"],
            step_type=d.get("step_type", d.get("type", "")),
            script=d.get("script", ""),
            function=d.get("function", ""),
            params=d.get("params") or {},
            limits=limits,
            on_fail=d.get("on_fail", "continue"),
            timeout=float(d.get("timeout", 0)),
            retry_count=int(d.get("retry_count", 0)),
            breakpoint=bool(d.get("breakpoint", False)),
            return_map=d.get("return_map") or {},
            loop_source=d.get("loop_source", ""),
            loop_key=d.get("loop_key", ""),
            loop_item_type=d.get("loop_item_type", "measurement"),
            skip=bool(d.get("skip", False)),
        )


# ---------------------------------------------------------------------------
# TestSequence
# ---------------------------------------------------------------------------

@dataclass
class TestSequence:
    """An ordered collection of steps executed as a logical group."""

    name: str
    steps: list[TestStep] = field(default_factory=list)
    skip: bool = False  # When True, all steps in this sequence emit SKIP

    def to_dict(self) -> dict:
        d: dict = {
            "name": self.name,
            "steps": [s.to_dict() for s in self.steps],
        }
        if self.skip:
            d["skip"] = True
        return d

    @staticmethod
    def from_dict(d: dict) -> TestSequence:
        steps = [TestStep.from_dict(s) for s in d.get("steps", [])]
        return TestSequence(name=d["name"], steps=steps, skip=bool(d.get("skip", False)))


# ---------------------------------------------------------------------------
# TestPlan
# ---------------------------------------------------------------------------

@dataclass
class TestPlan:
    """Top-level container that groups sequences and global configuration."""

    name: str
    version: str
    description: str
    global_params: dict                  # Merged into every step's params at runtime
    sequences: list[TestSequence] = field(default_factory=list)
    # Named variables available to all steps; can be referenced as {{varname}}
    # in params values, limit values, and populated by steps via return_map.
    variables: dict = field(default_factory=dict)
    # Declared type for each variable: "Number" | "String" | "Boolean"
    variable_types: dict = field(default_factory=dict)
    # Optional sequences run before / after the normal sequences
    setup_sequence: Optional[TestSequence] = None
    teardown_sequence: Optional[TestSequence] = None

    def to_dict(self) -> dict:
        d: dict = {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "global_params": dict(self.global_params),
            "variables": dict(self.variables),
            "variable_types": dict(self.variable_types),
            "sequences": [seq.to_dict() for seq in self.sequences],
        }
        if self.setup_sequence:
            d["setup_sequence"] = self.setup_sequence.to_dict()
        if self.teardown_sequence:
            d["teardown_sequence"] = self.teardown_sequence.to_dict()
        return d

    @staticmethod
    def from_dict(d: dict) -> TestPlan:
        sequences = [TestSequence.from_dict(s) for s in d.get("sequences", [])]
        raw_setup = d.get("setup_sequence")
        raw_teardown = d.get("teardown_sequence")
        return TestPlan(
            name=d["name"],
            version=str(d["version"]),
            description=d.get("description", ""),
            global_params=d.get("global_params") or {},
            sequences=sequences,
            variables=d.get("variables") or {},
            variable_types=d.get("variable_types") or {},
            setup_sequence=TestSequence.from_dict(raw_setup) if isinstance(raw_setup, dict) else None,
            teardown_sequence=TestSequence.from_dict(raw_teardown) if isinstance(raw_teardown, dict) else None,
        )


# ---------------------------------------------------------------------------
# StepResult
# ---------------------------------------------------------------------------

@dataclass
class StepResult:
    """Result produced by executing a single TestStep."""

    step_name: str
    seq_name: str
    result: str          # "PASS" | "FAIL" | "ERROR" | "SKIP"
    value: Any           # Measured value (any type)
    unit: str
    message: str         # Script-provided message or exception info
    duration_ms: int     # Wall-clock execution time in milliseconds

    def to_dict(self) -> dict:
        return {
            "step_name": self.step_name,
            "seq_name": self.seq_name,
            "result": self.result,
            "value": self.value,
            "unit": self.unit,
            "message": self.message,
            "duration_ms": self.duration_ms,
        }

    @staticmethod
    def from_dict(d: dict) -> StepResult:
        return StepResult(
            step_name=d["step_name"],
            seq_name=d.get("seq_name", ""),
            result=d["result"],
            value=d.get("value"),
            unit=d.get("unit", ""),
            message=d.get("message", ""),
            duration_ms=int(d.get("duration_ms", 0)),
        )


# ---------------------------------------------------------------------------
# TestRecord
# ---------------------------------------------------------------------------

@dataclass
class TestRecord:
    """Complete record of a single DUT test run."""

    id: int | None           # Database primary key; None before first save
    sn: str                  # Device serial number
    plan_name: str
    plan_version: str
    start_time: str          # ISO 8601
    end_time: str            # ISO 8601
    overall_result: str      # "PASS" | "FAIL" | "ABORT"
    step_results: list[StepResult] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "sn": self.sn,
            "plan_name": self.plan_name,
            "plan_version": self.plan_version,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "overall_result": self.overall_result,
            "step_results": [r.to_dict() for r in self.step_results],
        }

    @staticmethod
    def from_dict(d: dict) -> TestRecord:
        step_results = [StepResult.from_dict(r) for r in d.get("step_results", [])]
        return TestRecord(
            id=d.get("id"),
            sn=d["sn"],
            plan_name=d["plan_name"],
            plan_version=d["plan_version"],
            start_time=d["start_time"],
            end_time=d["end_time"],
            overall_result=d["overall_result"],
            step_results=step_results,
        )


# ---------------------------------------------------------------------------
# UserRecord
# ---------------------------------------------------------------------------

@dataclass
class UserRecord:
    """A user account with a role."""

    id: int | None
    username: str
    role: str        # "admin" | "operator"
    created_at: str

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "username": self.username,
            "role": self.role,
            "created_at": self.created_at,
        }

    @staticmethod
    def from_dict(d: dict) -> "UserRecord":
        return UserRecord(
            id=d.get("id"),
            username=d["username"],
            role=d.get("role", "operator"),
            created_at=d.get("created_at", ""),
        )
