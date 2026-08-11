"""Transform interface: text in, text out."""

from abc import ABC, abstractmethod


class Transform(ABC):
    name = "transform"

    def __init__(self, cfg: dict):
        self.cfg = cfg

    @abstractmethod
    def apply(self, gcode_text: str, job_opts: dict) -> str: ...
