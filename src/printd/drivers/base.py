"""Printer driver interface. Implement these seven methods to add a backend."""

from abc import ABC, abstractmethod
from pathlib import Path

from ..models import PrinterStatus


class Driver(ABC):
    def __init__(self, cfg: dict):
        self.cfg = cfg

    @abstractmethod
    def upload(self, gcode: Path, remote_name: str) -> None: ...

    @abstractmethod
    def start(self, remote_name: str) -> None: ...

    @abstractmethod
    def pause(self) -> None: ...

    @abstractmethod
    def resume(self) -> None: ...

    @abstractmethod
    def cancel(self) -> None: ...

    @abstractmethod
    def status(self) -> PrinterStatus: ...

    @abstractmethod
    def snapshot(self) -> bytes | None: ...

    def preheat_and_wait(self, nozzle: float, bed: float, timeout_s: int = 600) -> None:
        """Optional: drivers that can preheat before start override this."""

    def connect(self) -> None:
        """Optional: establish the printer link (with retries) if not live."""
