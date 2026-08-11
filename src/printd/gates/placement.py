"""Pre-slice placement: center the model, preferring the configured zone.

Runs on the STL before slicing (unlike the post-slice gates): translates the
model so its footprint center sits at the preferred zone's center. A model
whose footprint cannot fit the preferred zone is centered on the full bed
instead and the job carries a note for the preview reviewer.
"""

from pathlib import Path

from .. import stl


def place(src: Path, dst: Path, cfg: dict, bed_mm: tuple[float, float]) -> str | None:
    box = stl.bbox(src)
    w, d, _ = box.size
    zone = cfg.get("preferred")
    note = None
    if zone:
        zx0, zy0, zx1, zy1 = zone
        if w <= (zx1 - zx0) and d <= (zy1 - zy0):
            tx, ty = (zx0 + zx1) / 2, (zy0 + zy1) / 2
        else:
            tx, ty = bed_mm[0] / 2, bed_mm[1] / 2
            note = (
                f"part footprint {w:.0f}x{d:.0f} mm exceeds the preferred zone; "
                "placed on full bed (edge adhesion is weaker, check the preview)"
            )
    else:
        tx, ty = bed_mm[0] / 2, bed_mm[1] / 2
    cx, cy = box.center_xy
    stl.translate(src, dst, tx - cx, ty - cy, -box.min_z)
    return note
