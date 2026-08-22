"""OctoPrint REST driver."""

import time
from pathlib import Path

import requests

from ..models import PrinterStatus
from .base import Driver


class OctoPrintDriver(Driver):
    def __init__(self, cfg: dict):
        super().__init__(cfg)
        self.base = cfg["url"].rstrip("/")
        self.session = requests.Session()
        self.session.headers["X-Api-Key"] = cfg["api_key"]
        self.camera_url = cfg.get("camera_snapshot_url")
        self.timeout = int(cfg.get("http_timeout_s", 15))

    def _post(self, path: str, **kwargs):
        r = self.session.post(f"{self.base}{path}", timeout=self.timeout, **kwargs)
        r.raise_for_status()
        return r

    def _get(self, path: str):
        r = self.session.get(f"{self.base}{path}", timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    # -- interface ---------------------------------------------------------

    def upload(self, gcode: Path, remote_name: str) -> None:
        with open(gcode, "rb") as f:
            self._post("/api/files/local", files={"file": (remote_name, f)})

    def start(self, remote_name: str) -> None:
        self._post(f"/api/files/local/{remote_name}", json={"command": "select", "print": True})

    def pause(self) -> None:
        self._post("/api/job", json={"command": "pause", "action": "pause"})

    def resume(self) -> None:
        self._post("/api/job", json={"command": "pause", "action": "resume"})

    def cancel(self) -> None:
        self._post("/api/job", json={"command": "cancel"})
        # OctoPrint's cancel freezes the head where it stopped and never runs
        # end-gcode: heaters off, present the bed, release steppers.
        park = self.cfg.get(
            "cancel_park_gcode",
            ["M104 S0", "M140 S0", "G91", "G1 Z25 F600", "G90", "G1 X10 Y220 F3000", "M84"],
        )
        self.gcode(park)

    def status(self) -> PrinterStatus:
        job = self._get("/api/job")
        st = PrinterStatus(
            state=job.get("state", "Unknown"),
            file=(job.get("job", {}).get("file") or {}).get("name"),
            completion=(job.get("progress") or {}).get("completion"),
            print_time_s=(job.get("progress") or {}).get("printTime"),
            time_left_s=(job.get("progress") or {}).get("printTimeLeft"),
        )
        try:
            printer = self._get("/api/printer")
            tool = printer.get("temperature", {}).get("tool0", {})
            bed = printer.get("temperature", {}).get("bed", {})
            st.nozzle_actual, st.nozzle_target = tool.get("actual"), tool.get("target")
            st.bed_actual, st.bed_target = bed.get("actual"), bed.get("target")
        except requests.RequestException:
            pass  # printer endpoint 409s when disconnected; job state still stands
        return st

    def snapshot(self) -> bytes | None:
        if not self.camera_url:
            return None
        try:
            # camera_url points at a snapshot endpoint that owns camera
            # wake-up, exposure settle, and night lighting (snaplight on
            # octopi); one request returns a ready frame, and a second
            # would fire the work light twice per photo.
            r = requests.get(self.camera_url, timeout=self.timeout)
            r.raise_for_status()
            return r.content
        except requests.RequestException:
            return None

    def gcode(self, commands: list[str]) -> None:
        self._post("/api/printer/command", json={"commands": commands})

    def preheat_and_wait(self, nozzle: float, bed: float, timeout_s: int = 600) -> None:
        self._post("/api/printer/tool", json={"command": "target", "targets": {"tool0": nozzle}})
        self._post("/api/printer/bed", json={"command": "target", "target": bed})
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            st = self.status()
            if (
                st.nozzle_actual is not None
                and st.bed_actual is not None
                and abs(st.nozzle_actual - nozzle) <= 3
                and abs(st.bed_actual - bed) <= 3
            ):
                return
            time.sleep(5)
        raise TimeoutError(f"preheat did not reach {nozzle}/{bed} within {timeout_s}s")

    def connect(self) -> None:
        """Serial connect with retries. The first attempt after a host reboot
        reliably fails while the serial device settles."""
        port = self.cfg.get("serial_port", "/dev/ttyUSB0")
        baud = int(self.cfg.get("serial_baud", 115200))
        for attempt in range(6):
            state = self._get("/api/connection").get("current", {}).get("state", "")
            if state not in ("Closed", "Error", "Offline"):
                return
            self._post(
                "/api/connection",
                json={"command": "connect", "port": port, "baudrate": baud},
            )
            time.sleep(10)
        raise ConnectionError("printer serial connect failed after retries")
