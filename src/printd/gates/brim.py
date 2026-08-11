"""Brim/skirt policy gate."""

from pathlib import Path

from ..gcode import GcodeReport
from ..models import GateFailure
from .base import Gate

_OFFENDERS = {"Brim", "Skirt"}


class BrimGate(Gate):
    name = "brim_skirt"

    def check(self, gcode_path: Path, report: GcodeReport, context: dict) -> str | None:
        mode = self.cfg.get("mode", "allow")
        found = sorted(t for t in report.feature_types if t in _OFFENDERS)
        if not found:
            return None
        msg = f"sliced output contains {', '.join(found)}"
        if mode == "forbid":
            raise GateFailure(f"{msg}; the active profile should not produce these. Fix the profile.")
        if mode == "warn":
            return f"warning: {msg}"
        return None
