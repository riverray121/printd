"""Fresh-bed-probe preamble.

Prepends a hot re-level before the sliced file's own start sequence: heat the
bed to first-layer temp and the nozzle to a no-ooze probing temp, home, probe,
save. The saved mesh (M500) is required because the sliced file's own G28
disables active leveling; its M420 S1 (see MarlinStartPatches) then reloads
the mesh probed seconds earlier.

Per-job opt out: job_opts["fresh_mesh"] = False.
"""

from .base import Transform

MARKER = "; printd: fresh-mesh preamble"


class FreshMeshPreamble(Transform):
    name = "fresh_mesh_preamble"

    def preamble(self) -> str:
        bed = self.cfg.get("bed_temp", 65)
        nozzle = self.cfg.get("probe_nozzle_temp", 160)
        return "\n".join(
            [
                MARKER,
                f"M140 S{bed}",
                f"M104 S{nozzle}",
                f"M190 S{bed}",
                f"M109 S{nozzle}",
                "G28",
                "G29",
                "M500",
                "; printd: end fresh-mesh preamble",
            ]
        )

    def apply(self, gcode_text: str, job_opts: dict) -> str:
        default_on = str(self.cfg.get("default", True)).lower() in ("true", "on", "1")
        if not job_opts.get("fresh_mesh", default_on):
            return gcode_text
        return self.preamble() + "\n" + gcode_text
