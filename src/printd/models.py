"""Shared data shapes."""

from dataclasses import dataclass, field


@dataclass
class SliceResult:
    gcode_path: str
    preview_path: str
    approval_token: str
    notes: list[str] = field(default_factory=list)
    gate_reports: dict[str, str] = field(default_factory=dict)


@dataclass
class PrinterStatus:
    state: str
    file: str | None = None
    completion: float | None = None
    print_time_s: int | None = None
    time_left_s: int | None = None
    nozzle_actual: float | None = None
    nozzle_target: float | None = None
    bed_actual: float | None = None
    bed_target: float | None = None

    def as_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if v is not None}


class GateFailure(Exception):
    """A gate rejected the job; message is user-facing."""
