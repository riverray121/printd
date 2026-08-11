"""G-code analysis: motion bounds and feature markers.

Handles slicer quirks like leading-dot decimals (``E.056``) that break naive
number regexes.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

_MOVE_RE = re.compile(r"^G[01]\b")
_AXIS_RE = re.compile(r"([XYZ])(-?\d*\.?\d+)")
_TYPE_RE = re.compile(r"^;TYPE:(.+)$")


@dataclass
class GcodeReport:
    min_x: float = float("inf")
    max_x: float = float("-inf")
    min_y: float = float("inf")
    max_y: float = float("-inf")
    max_z: float = float("-inf")
    feature_types: set = field(default_factory=set)
    move_count: int = 0

    @property
    def has_moves(self) -> bool:
        return self.move_count > 0


def analyze(path: Path, skip_leading_lines_of: str | None = None) -> GcodeReport:
    """Single pass over the file collecting extents and ;TYPE: markers.

    ``skip_leading_lines_of``: exact text of an injected preamble whose moves
    (homing, purge) should not count against model bounds.
    """
    report = GcodeReport()
    skip_remaining = (
        skip_leading_lines_of.count("\n") + 1 if skip_leading_lines_of else 0
    )
    with open(path, errors="replace") as f:
        for line in f:
            if skip_remaining:
                skip_remaining -= 1
                continue
            line = line.strip()
            if not line:
                continue
            m = _TYPE_RE.match(line)
            if m:
                report.feature_types.add(m.group(1).strip())
                continue
            if line.startswith(";"):
                continue
            code = line.split(";", 1)[0]
            if not _MOVE_RE.match(code):
                continue
            axes = dict(_AXIS_RE.findall(code))
            if not axes:
                continue
            report.move_count += 1
            if "X" in axes:
                x = float(axes["X"])
                report.min_x = min(report.min_x, x)
                report.max_x = max(report.max_x, x)
            if "Y" in axes:
                y = float(axes["Y"])
                report.min_y = min(report.min_y, y)
                report.max_y = max(report.max_y, y)
            if "Z" in axes:
                report.max_z = max(report.max_z, float(axes["Z"]))
    return report


def insert_after_line(text: str, match_prefix: str, insert: str) -> str:
    """Insert ``insert`` on its own line after the first line starting with
    ``match_prefix``. Returns text unchanged if no line matches."""
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if line.strip().startswith(match_prefix):
            lines.insert(i + 1, insert)
            return "\n".join(lines)
    return text
