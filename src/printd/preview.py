"""Render sliced G-code to a PNG preview.

Isometric projection colored by height, with the bed outline for context, so
the reviewer sees the actual shape of what will print, not its footprint.
"""

import math
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection

_AXIS_RE = re.compile(r"([XYZE])(-?\d*\.?\d+)")

_COS30 = math.cos(math.radians(30))
_SIN30 = math.sin(math.radians(30))


def _iso(x: float, y: float, z: float) -> tuple[float, float]:
    return ((x - y) * _COS30, (x + y) * _SIN30 + z)


def render(gcode_path: Path, out_png: Path, bed_mm: tuple[float, float]) -> Path:
    segments, colors = [], []
    x = y = z = 0.0
    max_z = 0.1
    with open(gcode_path, errors="replace") as f:
        for line in f:
            code = line.split(";", 1)[0].strip()
            if not code.startswith(("G0", "G1")):
                continue
            axes = dict(_AXIS_RE.findall(code))
            nx = float(axes["X"]) if "X" in axes else x
            ny = float(axes["Y"]) if "Y" in axes else y
            nz = float(axes["Z"]) if "Z" in axes else z
            extruding = "E" in axes and float(axes["E"]) > 0
            if extruding and (nx != x or ny != y):
                segments.append([_iso(x, y, nz), _iso(nx, ny, nz)])
                colors.append(nz)
                max_z = max(max_z, nz)
            x, y, z = nx, ny, nz

    fig, ax = plt.subplots(figsize=(9, 8), dpi=110)

    bx, by = bed_mm
    bed_corners = [(0, 0), (bx, 0), (bx, by), (0, by), (0, 0)]
    bed_pts = [_iso(cx, cy, 0) for cx, cy in bed_corners]
    ax.plot([p[0] for p in bed_pts], [p[1] for p in bed_pts],
            color="#999999", linewidth=1.0, linestyle="--", zorder=0)

    if segments:
        # G-code is layer-ordered, so later (higher) segments naturally draw on top.
        lc = LineCollection(segments, cmap="viridis", linewidths=0.5)
        lc.set_array([c / max_z for c in colors])
        ax.add_collection(lc)

    ax.autoscale()
    ax.set_aspect("equal")
    ax.set_title(f"{gcode_path.stem}  (height {max_z:.1f} mm)")
    ax.set_axis_off()
    fig.tight_layout()
    fig.savefig(out_png, facecolor="white")
    plt.close(fig)
    return out_png
