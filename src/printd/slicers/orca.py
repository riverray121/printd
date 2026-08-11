"""OrcaSlicer CLI adapter.

Invocation shape (Orca 2.x): ``--load-settings "machine;process"
--load-filaments filament --arrange 0 --slice 0 --outputdir DIR model.stl``.
``--arrange 0`` keeps STL coordinates, so placement is the caller's job.
"""

import subprocess
from pathlib import Path

from .base import Slicer


class OrcaSlicer(Slicer):
    def _resolve(self, ref: str) -> str:
        """Profile paths may be absolute or ``bundled:<relpath>``, resolved
        against the Orca install's own profile tree (keeps inherit chains
        intact for system profiles)."""
        if ref.startswith("bundled:"):
            binary = Path(self.cfg["binary"]).resolve()
            root = self.cfg.get("bundled_profiles") or str(
                binary.parent / "resources" / "profiles"
            )
            return str(Path(root) / ref[len("bundled:"):])
        return ref

    def slice(self, stl: Path, process: str, filament: str, out_dir: Path) -> Path:
        machine = self._resolve(self.cfg["machine_profile"])
        process_path = self._resolve(self.cfg["process_profiles"][process])
        filament_path = self._resolve(self.cfg["filament_profiles"][filament])
        out_dir.mkdir(parents=True, exist_ok=True)
        cmd = [
            self.cfg["binary"],
            "--load-settings", f"{machine};{process_path}",
            "--load-filaments", filament_path,
            "--arrange", "0",
            "--slice", "0",
            "--outputdir", str(out_dir),
            str(stl),
        ]
        env = {"HOME": str(Path.home()), "PATH": "/usr/bin:/bin:/usr/local/bin"}
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=int(self.cfg.get("timeout_s", 600)), env=env
        )
        produced = out_dir / "plate_1.gcode"
        if proc.returncode != 0 or not produced.exists():
            tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-8:]
            raise RuntimeError("slicing failed:\n" + "\n".join(tail))
        final = out_dir / f"{stl.stem}.gcode"
        produced.rename(final)
        return final
