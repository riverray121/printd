"""Preview approval: start requires the token minted at slice time, unless the
job carries an explicit per-job override."""

from pathlib import Path

from ..gcode import GcodeReport
from ..models import GateFailure
from .base import Gate


class ApprovalGate(Gate):
    name = "approval"

    def check(self, gcode_path: Path, report: GcodeReport, context: dict) -> str | None:
        # Slice-time: nothing to check; the token is minted by the pipeline.
        return None

    def verify_start(self, expected_token: str, given_token: str | None, override: bool) -> None:
        if not self.cfg.get("required", True):
            return
        if override:
            if not self.cfg.get("per_job_override", True):
                raise GateFailure("approval override is disabled in config")
            return
        if given_token != expected_token:
            raise GateFailure(
                "preview not approved: pass the approval token from slice, or request an explicit override"
            )
