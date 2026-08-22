"""G-code analysis: motion bounds and feature markers.

Handles slicer quirks like leading-dot decimals (``E.056``) that break naive
number regexes.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

_MOVE_RE = re.compile(r"^G[01]\b")
_AXIS_RE = re.compile(r"([XYZ])(-?\d*\.?\d+)")
_E_RE = re.compile(r"\bE-?\d*\.?\d+")
_TYPE_RE = re.compile(r"^;TYPE:(.+)$")

# Advisory thresholds, from print-proven heuristics: bridges under 8 mm and
# short overhang runs print fine unsupported on this class of printer;
# longer spans and overhang walls stacking across many layers are the
# configurations that actually fail.
_BRIDGE_ADVISORY_MM = 8.0
_OVERHANG_ADVISORY_LAYERS = 5
_LAYER_STEP_MM = 0.31  # distinct Z values closer than this count as consecutive layers


@dataclass
class GcodeReport:
    min_x: float = float("inf")
    max_x: float = float("-inf")
    min_y: float = float("inf")
    max_y: float = float("-inf")
    max_z: float = float("-inf")
    feature_types: set = field(default_factory=set)
    move_count: int = 0
    max_bridge_mm: float = 0.0
    overhang_zs: set = field(default_factory=set)

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
    cur_type = None
    px = py = pz = None
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
                cur_type = m.group(1).strip()
                report.feature_types.add(cur_type)
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
            x = float(axes["X"]) if "X" in axes else px
            y = float(axes["Y"]) if "Y" in axes else py
            if "X" in axes:
                report.min_x = min(report.min_x, x)
                report.max_x = max(report.max_x, x)
            if "Y" in axes:
                report.min_y = min(report.min_y, y)
                report.max_y = max(report.max_y, y)
            if "Z" in axes:
                pz = float(axes["Z"])
                report.max_z = max(report.max_z, pz)
            extruding = ("X" in axes or "Y" in axes) and _E_RE.search(code)
            if extruding and cur_type == "Bridge" and None not in (px, py, x, y):
                seg = ((x - px) ** 2 + (y - py) ** 2) ** 0.5
                report.max_bridge_mm = max(report.max_bridge_mm, seg)
            if extruding and cur_type == "Overhang wall" and pz is not None:
                report.overhang_zs.add(round(pz, 2))
            px, py = x, y
    return report


def support_advisory(report: GcodeReport) -> str | None:
    """A note when the sliced result matches configurations that likely fail
    without supports; None when nothing crosses the thresholds."""
    reasons = []
    if report.max_bridge_mm > _BRIDGE_ADVISORY_MM:
        reasons.append(f"bridge span {report.max_bridge_mm:.0f} mm (over {_BRIDGE_ADVISORY_MM:.0f} mm)")
    zs = sorted(report.overhang_zs)
    streak = best = 1 if zs else 0
    for a, b in zip(zs, zs[1:]):
        streak = streak + 1 if (b - a) <= _LAYER_STEP_MM else 1
        best = max(best, streak)
    if best >= _OVERHANG_ADVISORY_LAYERS:
        reasons.append(f"overhang walls stacked across {best} consecutive layers")
    if not reasons:
        return None
    return ("supports advisory: " + "; ".join(reasons)
            + " — consider re-slicing with the supports process")


def insert_after_line(text: str, match_prefix: str, insert: str) -> str:
    """Insert ``insert`` on its own line after the first line starting with
    ``match_prefix``. Returns text unchanged if no line matches."""
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if line.strip().startswith(match_prefix):
            lines.insert(i + 1, insert)
            return "\n".join(lines)
    return text
