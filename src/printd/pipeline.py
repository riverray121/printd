"""The job pipeline: place -> slice -> transform -> gate -> preview -> start."""

import time
from pathlib import Path

from . import gcode as gcode_mod
from . import preview as preview_mod
from .config import Config
from .drivers import make_driver
from .gates import enabled_gates, placement
from .gates.approval import ApprovalGate
from .light import make_light
from .models import GateFailure, SliceResult
from .power import make_power
from .slicers import make_slicer
from .storage import Storage
from .submit import submit as submit_model
from .transforms import build_transforms
from .transforms.fresh_mesh import FreshMeshPreamble


class Pipeline:
    def __init__(self, config: Config):
        self.config = config
        printer_cfg = config.section("printer")
        self.bed_mm = tuple(printer_cfg.get("bed_mm", [220, 220]))
        self.height_mm = printer_cfg.get("height_mm", 250)
        self.driver = make_driver(printer_cfg)
        self.slicer = make_slicer(config.section("slicer"))
        self.transforms = build_transforms(config.raw.get("transforms", []))
        self.gates = enabled_gates(config.section("gates"))
        self.storage = Storage(config.storage_root)
        self.approval = next((g for g in self.gates if isinstance(g, ApprovalGate)), None)
        self.power = make_power(config.section("power"))
        self.light = make_light(config.section("light"))

    # -- steps -------------------------------------------------------------

    def submit(self, source: str) -> Path:
        return submit_model(source, self.storage.inbox)

    def slice(self, model: str, process: str = "plain", filament: str = "default",
              job_opts: dict | None = None) -> SliceResult:
        job_opts = job_opts or {}
        src = Path(model).expanduser()
        if not src.is_absolute():
            src = self.storage.inbox / model
        notes = []

        placed = self.storage.inbox / f"{src.stem}.placed.stl"
        note = placement.place(src, placed, self.config.section("gates").get("placement_zone", {}), self.bed_mm)
        if note:
            notes.append(note)

        out = self.slicer.slice(placed, process, filament, self.storage.gcode)

        text = out.read_text(errors="replace")
        for transform in self.transforms:
            text = transform.apply(text, job_opts)
        out.write_text(text)

        preamble = next(
            (t.preamble() for t in self.transforms
             if isinstance(t, FreshMeshPreamble) and text.startswith(t.preamble()[:30])),
            None,
        )
        report = gcode_mod.analyze(out, skip_leading_lines_of=preamble)
        gate_reports = {}
        for gate in self.gates:
            result = gate.check(out, report, {"bed_mm": self.bed_mm, "height_mm": self.height_mm})
            if result:
                gate_reports[gate.name] = result

        png = self.storage.previews / f"{out.stem}.png"
        preview_mod.render(out, png, self.bed_mm)
        token = self.storage.file_hash(out)
        return SliceResult(
            gcode_path=str(out),
            preview_path=str(png),
            approval_token=token,
            notes=notes,
            gate_reports=gate_reports,
        )

    def start(self, gcode_path: str, approval_token: str | None = None,
              skip_approval: bool = False) -> str:
        path = Path(gcode_path).expanduser()
        if not path.is_absolute():
            path = self.storage.gcode / gcode_path
        if not path.exists():
            raise FileNotFoundError(f"{gcode_path} not found")
        if self.approval:
            self.approval.verify_start(self.storage.file_hash(path), approval_token, skip_approval)

        if self.power and self.power.on_before_start:
            self.power.on()
            # The printer needs a moment on mains before its USB serial
            # device exists; connect() below retries over ~60 s.
            time.sleep(5)

        self.driver.connect()
        remote = f"printd_{path.stem}.gcode"
        self.driver.upload(path, remote)

        # Preheat before starting: a cold start leaves the head parked on the
        # model area while heating, and some watchdog-style plugins misread it.
        first_layer = self.config.section("printer").get("first_layer_temps", {})
        nozzle = first_layer.get("nozzle", 215)
        bed = first_layer.get("bed", 65)
        self.driver.preheat_and_wait(nozzle, bed)

        # The camera view is clear right now; once the print starts, probing
        # and leveling park the head in front of the lens. The watcher uses
        # this shot for its "Print started" notification.
        try:
            snap = self.driver.snapshot()
            if snap:
                (self.storage.root / "prestart.jpg").write_bytes(snap)
        except Exception:
            pass

        self.driver.start(remote)
        self.storage.log_job(event="start", file=remote, source=str(path))
        return remote

    # -- passthroughs ------------------------------------------------------

    def status(self):
        return self.driver.status()

    def snapshot(self) -> bytes | None:
        return self.driver.snapshot()

    def pause(self):
        self.driver.pause()

    def resume(self):
        self.driver.resume()

    def cancel(self):
        self.driver.cancel()
        self.storage.log_job(event="cancel", ts=time.strftime("%Y-%m-%dT%H:%M:%S%z"))
