"""Gate interface."""

from abc import ABC, abstractmethod
from pathlib import Path

from ..gcode import GcodeReport


class Gate(ABC):
    name = "gate"

    def __init__(self, cfg: dict):
        self.cfg = cfg

    @abstractmethod
    def check(self, gcode_path: Path, report: GcodeReport, context: dict) -> str | None:
        """Return an informational note, or None; raise GateFailure to reject."""
