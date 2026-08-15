"""Render sliced G-code to a PNG preview a human can judge.

Two engines:

- render_tubes: three.js tube rendering with per-feature colors via
  render3d/ (headless Chromium). Shaded 3D geometry, six views.
- render_lines: per-feature colored vector line projections built as an
  SVG (five stacked full-width views), rasterized with headless Chromium.

render() prefers tubes and falls back to lines.
"""

import glob
import math
import os
import re
import subprocess
from collections import defaultdict
from pathlib import Path

_MOVE_RE = re.compile(r"^G[0123]\b")
_NUM = r"(-?\d*\.?\d+)"

# type -> (color, stroke width, opacity)
_STYLE = {
    "Outer wall": ("#555555", 0.7, 0.75),
    "Inner wall": ("#aaaaaa", 0.5, 0.35),
    "Top surface": ("#777777", 0.5, 0.5),
    "Bottom surface": ("#777777", 0.5, 0.5),
    "Overhang wall": ("#cc2288", 0.9, 0.9),
    "Bridge": ("#3366cc", 0.9, 0.9),
    "Internal Bridge": ("#3366cc", 0.7, 0.6),
    "Brim": ("#88bb88", 0.7, 0.8),
    "Skirt": ("#88bb88", 0.7, 0.8),
    "Support": ("#f08a24", 1.2, 0.85),
    "Support interface": ("#c34a00", 1.2, 0.95),
}
_DRAW_ORDER = [
    "Brim", "Skirt", "Bottom surface", "Top surface", "Inner wall",
    "Outer wall", "Overhang wall", "Internal Bridge", "Bridge",
    "Support", "Support interface",
]
_LEGEND = [
    ("part walls", "#555555"),
    ("surfaces", "#777777"),
    ("brim/skirt", "#88bb88"),
    ("supports", "#f08a24"),
    ("support interface", "#c34a00"),
    ("bridges", "#3366cc"),
    ("overhangs", "#cc2288"),
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
    return (px - py) * _C30, (px + py) * _S30 - pz


def _proj_front(px, py, pz):
    return px, -pz


def _proj_side(px, py, pz):
    return py, -pz


def _proj_top(px, py, pz):
    return px, -py


def _find_chromium() -> str:
    env = os.environ.get("PRINTD_CHROMIUM")
    if env:
        return env
    for pat in ("~/.cache/ms-playwright/chromium-*/chrome-linux/chrome",
                "~/.cache/ms-playwright/chromium-*/chrome-linux/headless_shell"):
        hits = sorted(glob.glob(os.path.expanduser(pat)), reverse=True)
        if hits:
            return hits[0]
    raise FileNotFoundError("no Chromium found; set PRINTD_CHROMIUM")


_RENDER3D = Path(__file__).resolve().parent.parent.parent / "render3d" / "render.js"


def render(gcode_path: Path, out_png: Path, bed_mm: tuple[float, float]) -> Path:
    """Prefer the tube renderer; fall back to the line projection."""
    if _RENDER3D.exists():
        try:
            return render_tubes(gcode_path, out_png, bed_mm)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as e:
            detail = getattr(e, "stderr", "") or str(e)
            print(f"tube renderer unavailable ({detail.strip()[:200]}); using line renderer")
    return render_lines(gcode_path, out_png, bed_mm)


def render_tubes(gcode_path: Path, out_png: Path, bed_mm: tuple[float, float]) -> Path:
    node = os.environ.get("PRINTD_NODE", "node")
    subprocess.run(
        [node, str(_RENDER3D), str(gcode_path), str(out_png),
         "--bed", f"{bed_mm[0]}x{bed_mm[1]}", "--title", gcode_path.stem],
        check=True, capture_output=True, text=True, timeout=300,
    )
    return out_png


def render_lines(gcode_path: Path, out_png: Path, bed_mm: tuple[float, float]) -> Path:
    svg_path = out_png.with_suffix(".svg")
    width, height = _build_svg(gcode_path, svg_path, bed_mm)
    subprocess.run(
        [_find_chromium(), "--headless", "--no-sandbox", "--disable-gpu",
         f"--screenshot={out_png}", f"--window-size={width},{height}",
         f"file://{svg_path}"],
        check=True, capture_output=True, text=True, timeout=120,
    )
    svg_path.unlink(missing_ok=True)
    return out_png


def _build_svg(gcode_path: Path, svg_path: Path, bed_mm: tuple[float, float]) -> tuple[int, int]:
    segs = _parse(gcode_path)
    drawn = [s for s in segs if s[5] in _STYLE]
    if not drawn:
        drawn = segs
    xs = [v for s in drawn for v in (s[0], s[2])]
    ys = [v for s in drawn for v in (s[1], s[3])]
    zs = [s[4] for s in drawn]
    dims = (max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)) if drawn else (0, 0, 0)
    bx, by = bed_mm

    views = [
        ("Isometric", _proj_iso, False),
        ("Isometric, rotated 90\N{DEGREE SIGN}", lambda px, py, pz: _proj_iso(py, bx - px, pz), False),
        ("Front elevation (Z up)", _proj_front, False),
        ("Side elevation (Z up)", _proj_side, False),
        ("Top-down (bed outline dashed)", _proj_top, True),
    ]

    VW = 1600
    blocks = []
    total_h = 76
    for label, proj, with_bed in views:
        pts = []
        for (x0, y0, x1, y1, z, t) in drawn:
            u0, v0 = proj(x0, y0, z)
            u1, v1 = proj(x1, y1, z)
            pts.append((u0, v0, u1, v1, t))
        bed_pts = None
        if with_bed:
            corners = [(0, 0), (bx, 0), (bx, by), (0, by), (0, 0)]
            bed_pts = [proj(cx, cy, 0) for cx, cy in corners]
        allu = [p for q in pts for p in (q[0], q[2])] + ([p[0] for p in bed_pts] if bed_pts else [])
        allv = [p for q in pts for p in (q[1], q[3])] + ([p[1] for p in bed_pts] if bed_pts else [])
        minu, maxu = min(allu), max(allu)
        minv, maxv = min(allv), max(allv)
        scale = (VW - 80) / max(maxu - minu, 1e-6)
        h = int((maxv - minv) * scale) + 92
        blocks.append((label, pts, bed_pts, minu, minv, scale, h, total_h))
        total_h += h

    svg = []
    svg.append('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d">'
               % (VW, total_h + 20, VW, total_h + 20))
    svg.append('<rect width="100%" height="100%" fill="white"/>')
    title = gcode_path.stem
    svg.append(
        f'<text x="30" y="42" font-family="sans-serif" font-size="30" font-weight="bold" fill="#222">'
        f'{title} - sliced G-code preview | {dims[0]:.0f} x {dims[1]:.0f} x {dims[2]:.1f} mm</text>'
    )
    present = {s[5] for s in drawn}
    lx = 30
    for name, col in _LEGEND:
        if not any(_STYLE.get(t, ("",))[0] == col for t in present):
            continue
        svg.append('<rect x="%d" y="52" width="18" height="18" fill="%s"/>' % (lx, col))
        svg.append('<text x="%d" y="67" font-family="sans-serif" font-size="20" fill="#333">%s</text>'
                   % (lx + 24, name))
        lx += 24 + 11 * len(name) + 30

    for (label, pts, bed_pts, minu, minv, scale, h, oy) in blocks:
        svg.append('<text x="30" y="%d" font-family="sans-serif" font-size="24" fill="#444">%s</text>'
                   % (oy + 60, label))

        def tx(u):
            return (u - minu) * scale + 40

        def ty(v, _oy=oy):
            return (v - minv) * scale + _oy + 75

        if bed_pts:
            d = "M" + "L".join("%.1f %.1f" % (tx(u), ty(v)) for u, v in bed_pts)
            svg.append(f'<path d="{d}" stroke="#bbbbbb" stroke-width="1.5" '
                       f'stroke-dasharray="8,6" fill="none"/>')
        groups = defaultdict(list)
        for (u0, v0, u1, v1, t) in pts:
            groups[t].append("M%.1f %.1fL%.1f %.1f" % (tx(u0), ty(v0), tx(u1), ty(v1)))
        for t in _DRAW_ORDER:
            if t not in groups:
                continue
            col, w, op = _STYLE[t]
            svg.append('<path d="%s" stroke="%s" stroke-width="%s" fill="none" opacity="%s"/>'
                       % ("".join(groups[t]), col, w, op))

    svg.append("</svg>")
    svg_path.write_text("\n".join(svg))
    return VW, total_h + 20
