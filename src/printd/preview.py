"""Render sliced G-code to a PNG preview a human can judge.

Three angles in one image (two isometric views 90 degrees apart and a front
elevation), line-based with per-feature colors and transparency: walls read as
translucent so supports, bridges, and overhangs behind them stay visible.
Infill is deliberately not drawn; it would fill the silhouette and hide
everything that matters for approval.
"""

import math
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.lines import Line2D

_MOVE_RE = re.compile(r"^G[0123]\b")
_NUM = r"(-?\d*\.?\d+)"

# type -> (color, linewidth, alpha, legend label)
_STYLE = {
    "Outer wall": ("#555555", 0.7, 0.75, "part walls"),
    "Inner wall": ("#aaaaaa", 0.5, 0.35, None),
    "Bottom surface": ("#777777", 0.5, 0.5, None),
    "Top surface": ("#777777", 0.5, 0.5, None),
    "Overhang wall": ("#cc2288", 0.9, 0.9, "overhangs"),
    "Bridge": ("#3366cc", 0.9, 0.9, "bridges"),
    "Internal Bridge": ("#3366cc", 0.7, 0.6, None),
    "Brim": ("#88bb88", 0.7, 0.8, "brim"),
    "Skirt": ("#88bb88", 0.7, 0.8, "skirt"),
    "Support": ("#f08a24", 1.2, 0.85, "supports"),
    "Support interface": ("#c34a00", 1.2, 0.95, "support interface"),
}
_DRAW_ORDER = [
    "Brim", "Skirt", "Bottom surface", "Top surface", "Inner wall",
    "Outer wall", "Overhang wall", "Internal Bridge", "Bridge",
    "Support", "Support interface",
]


def _parse(gcode_path: Path):
    """Yield (x0, y0, x1, y1, z, feature_type) for every extruding move."""
    segs = []
    cur_type = None
    x = y = z = 0.0
    e_prev = 0.0
    abs_e = True
    for ln in open(gcode_path, errors="replace"):
        if ln.startswith(";TYPE:"):
            cur_type = ln.strip().split(":", 1)[1]
            continue
        if ln.startswith("M82"):
            abs_e = True
        elif ln.startswith("M83"):
            abs_e = False
        elif ln.startswith("G92"):
            m = re.search("E" + _NUM, ln)
            if m:
                e_prev = float(m.group(1))
        elif _MOVE_RE.match(ln):
            mx = re.search("X" + _NUM, ln)
            my = re.search("Y" + _NUM, ln)
            mz = re.search("Z" + _NUM, ln)
            me = re.search("E" + _NUM, ln)
            nx = float(mx.group(1)) if mx else x
            ny = float(my.group(1)) if my else y
            if mz:
                z = float(mz.group(1))
            extruding = False
            if me:
                ev = float(me.group(1))
                if abs_e:
                    de = ev - e_prev
                    e_prev = ev
                else:
                    de = ev
                extruding = de > 0.0001
            if extruding and (mx or my) and cur_type:
                segs.append((x, y, nx, ny, z, cur_type))
            x, y = nx, ny
    return segs


_C30 = math.cos(math.radians(30))
_S30 = math.sin(math.radians(30))


def _proj_iso(px, py, pz):
    return (px - py) * _C30, (px + py) * _S30 + pz


def _proj_front(px, py, pz):
    return px, pz


def render(gcode_path: Path, out_png: Path, bed_mm: tuple[float, float]) -> Path:
    segs = _parse(gcode_path)
    max_z = max((s[4] for s in segs), default=0.0)
    bx, by = bed_mm

    views = [
        ("isometric", _proj_iso),
        ("isometric, rotated 90\N{DEGREE SIGN}", lambda px, py, pz: _proj_iso(py, bx - px, pz)),
        ("front elevation", _proj_front),
    ]

    fig, axes = plt.subplots(1, len(views), figsize=(16, 7), dpi=110)
    present_types = []

    for ax, (label, proj) in zip(axes, views):
        for t in _DRAW_ORDER:
            color, lw, alpha, _ = _STYLE[t]
            lines = [
                [proj(x0, y0, z), proj(x1, y1, z)]
                for (x0, y0, x1, y1, z, st) in segs
                if st == t
            ]
            if not lines:
                continue
            if t not in present_types:
                present_types.append(t)
            ax.add_collection(LineCollection(lines, colors=color, linewidths=lw, alpha=alpha))

        bed = [(0, 0), (bx, 0), (bx, by), (0, by), (0, 0)]
        pts = [proj(cx, cy, 0) for cx, cy in bed]
        ax.plot([p[0] for p in pts], [p[1] for p in pts],
                color="#bbbbbb", linewidth=1.0, linestyle="--")
        ax.autoscale()
        ax.set_aspect("equal")
        ax.set_title(label, fontsize=11)
        ax.set_axis_off()

    handles = [
        Line2D([], [], color=_STYLE[t][0], linewidth=2, label=_STYLE[t][3])
        for t in present_types if _STYLE[t][3]
    ]
    if handles:
        fig.legend(handles=handles, loc="lower center", ncol=len(handles), frameon=False)
    fig.suptitle(f"{gcode_path.stem}   |   height {max_z:.1f} mm", fontsize=13)
    fig.tight_layout(rect=(0, 0.05, 1, 0.96))
    fig.savefig(out_png, facecolor="white")
    plt.close(fig)
    return out_png
