"""Marlin start-gcode fixes.

1. Insert the saved-mesh activation command after the sliced file's own G28
   (Marlin disables leveling on home; without this the printer runs as if the
   bed were flat).
2. Literal coordinate replacements for stock purge lines that start off-bed.

The insert targets the first G28 after any fresh-mesh preamble, not the
preamble's own G28 (probing must run without a stale mesh loaded).
"""

from ..gcode import insert_after_line
from .base import Transform
from .fresh_mesh import MARKER as PREAMBLE_MARKER


class MarlinStartPatches(Transform):
    name = "marlin_start_patches"

    def apply(self, gcode_text: str, job_opts: dict) -> str:
        mesh_cmd = self.cfg.get("saved_mesh_cmd", "M420 S1")
        if mesh_cmd:
            head, sep, tail = gcode_text.partition("; printd: end fresh-mesh preamble\n")
            target = tail if sep else gcode_text
            patched = insert_after_line(target, "G28", f"{mesh_cmd} ; printd: use saved mesh")
            gcode_text = head + sep + patched if sep else patched
        for old, new in (self.cfg.get("purge_x_replacements") or {}).items():
            gcode_text = gcode_text.replace(old, new)
        return gcode_text
