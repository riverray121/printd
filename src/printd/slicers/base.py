"""Slicer adapter interface."""

from abc import ABC, abstractmethod
from pathlib import Path


class Slicer(ABC):
    def __init__(self, cfg: dict):
        self.cfg = cfg

    @abstractmethod
    def slice(self, stl: Path, process: str, filament: str, out_dir: Path) -> Path:
        """Slice ``stl`` with the named process/filament profiles; return the
        G-code path. Profile names resolve via config."""
