"""Render sliced G-code to a PNG preview: top view colored by height."""

import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection

_AXIS_RE = re.compile(r"([XYZE])(-?\d*\.?\d+)")


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
                segments.append([(x, y), (nx, ny)])
                colors.append(nz)
                max_z = max(max_z, nz)
            x, y, z = nx, ny, nz

    fig, ax = plt.subplots(figsize=(8, 8), dpi=110)
    if segments:
        lc = LineCollection(segments, cmap="viridis", linewidths=0.4)
        lc.set_array([c / max_z for c in colors])
        ax.add_collection(lc)
    ax.set_xlim(0, bed_mm[0])
    ax.set_ylim(0, bed_mm[1])
    ax.set_aspect("equal")
    ax.set_title(gcode_path.stem)
    ax.set_xlabel("X mm")
    ax.set_ylabel("Y mm")
    ax.grid(True, alpha=0.2)
    fig.tight_layout()
    fig.savefig(out_png)
    plt.close(fig)
    return out_png
