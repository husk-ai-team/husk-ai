"""The debugger's strict output contract + a tolerant extractor.

The model must return JSON matching :class:`DebugReport`. ``extra="forbid"``
rejects hallucinated extra keys. Real models sometimes wrap JSON in prose or
```json fences, so :func:`extract_report` first isolates the outermost JSON
object before validating.
"""

from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Confidence = Literal["high", "medium", "low"]


class ReportParseError(ValueError):
    """The model's response could not be parsed/validated into a DebugReport."""


class FailureLocalization(BaseModel):
    model_config = ConfigDict(extra="forbid")
    node_id: str | None = None
    step_index: int | None = None
    also_implicated: list[str] = Field(default_factory=list)


class ProposedFix(BaseModel):
    model_config = ConfigDict(extra="forbid")
    summary: str
    diff: str | None = None
    rationale: str


class DebugReport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    failure_localization: FailureLocalization
    failure_class: str
    root_cause: str
    evidence: list[str] = Field(default_factory=list)
    proposed_fix: ProposedFix
    confidence: Confidence
    missing_information: list[str] = Field(default_factory=list)


def _strip_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        # Drop the opening fence (``` or ```json) and the trailing fence.
        first_nl = t.find("\n")
        if first_nl != -1:
            t = t[first_nl + 1 :]
        if t.rstrip().endswith("```"):
            t = t.rstrip()[: -3]
    return t.strip()


def _outermost_object(text: str) -> str | None:
    """Return the first balanced ``{...}`` block, ignoring braces inside strings."""
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_str = False
    escape = False
    for i in range(start, len(text)):
        c = text[i]
        if in_str:
            if escape:
                escape = False
            elif c == "\\":
                escape = True
            elif c == '"':
                in_str = False
            continue
        if c == '"':
            in_str = True
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def extract_report(raw: str) -> DebugReport:
    """Parse + validate a model response into a :class:`DebugReport`.

    Raises :class:`ReportParseError` (never a bare 500) on malformed output.
    """
    candidate = _strip_fences(raw)
    try:
        data = json.loads(candidate)
    except json.JSONDecodeError:
        block = _outermost_object(candidate)
        if block is None:
            raise ReportParseError("no JSON object found in model response") from None
        try:
            data = json.loads(block)
        except json.JSONDecodeError as e:
            raise ReportParseError(f"invalid JSON in model response: {e}") from e
    try:
        return DebugReport.model_validate(data)
    except Exception as e:  # noqa: BLE001 - pydantic ValidationError and friends
        raise ReportParseError(f"response did not match the report schema: {e}") from e
