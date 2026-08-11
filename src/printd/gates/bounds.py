"""Motion bounds gate: every move must stay inside the machine envelope."""

from pathlib import Path

from ..gcode import GcodeReport
from ..models import GateFailure
from .base import Gate


class BoundsGate(Gate):
    name = "bounds"

    def check(self, gcode_path: Path, report: GcodeReport, context: dict) -> str | None:
        if not self.cfg.get("enabled", True) or not report.has_moves:
            return None
        bed_x, bed_y = context["bed_mm"]
        height = context["height_mm"]
        margin = float(self.cfg.get("margin_mm", 0.0))
        problems = []
        if report.min_x < -margin or report.max_x > bed_x + margin:
            problems.append(f"X {report.min_x:.1f}..{report.max_x:.1f} outside 0..{bed_x}")
        if report.min_y < -margin or report.max_y > bed_y + margin:
            problems.append(f"Y {report.min_y:.1f}..{report.max_y:.1f} outside 0..{bed_y}")
        if report.max_z > height:
            problems.append(f"Z {report.max_z:.1f} above {height}")
        if problems:
            raise GateFailure("G-code exceeds machine envelope: " + "; ".join(problems))
        return None
