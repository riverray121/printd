import pytest

from printd.gates.approval import ApprovalGate
from printd.gates.bounds import BoundsGate
from printd.gates.brim import BrimGate
from printd.gcode import GcodeReport
from printd.models import GateFailure

CTX = {"bed_mm": (220, 220), "height_mm": 250}


def report(**kw) -> GcodeReport:
    r = GcodeReport(min_x=10, max_x=100, min_y=10, max_y=100, max_z=50, move_count=5)
    for k, v in kw.items():
        setattr(r, k, v)
    return r


def test_brim_forbid_raises():
    with pytest.raises(GateFailure):
        BrimGate({"mode": "forbid"}).check(None, report(feature_types={"Brim"}), CTX)


def test_brim_warn_notes():
    note = BrimGate({"mode": "warn"}).check(None, report(feature_types={"Skirt"}), CTX)
    assert "Skirt" in note


def test_bounds_rejects_oversize():
    with pytest.raises(GateFailure):
        BoundsGate({"enabled": True}).check(None, report(max_x=225.0), CTX)


def test_bounds_passes_in_envelope():
    assert BoundsGate({"enabled": True}).check(None, report(), CTX) is None


def test_approval_token_and_override():
    g = ApprovalGate({"required": True, "per_job_override": True})
    g.verify_start("tok", "tok", False)
    g.verify_start("tok", None, True)
    with pytest.raises(GateFailure):
        g.verify_start("tok", "wrong", False)


def test_approval_override_can_be_disabled():
    g = ApprovalGate({"required": True, "per_job_override": False})
    with pytest.raises(GateFailure):
        g.verify_start("tok", None, True)
