"""Gate registry. A gate inspects a sliced job and either passes (returning a
note string or None) or raises GateFailure."""

from .approval import ApprovalGate
from .bounds import BoundsGate
from .brim import BrimGate

GATES = {
    "brim_skirt": BrimGate,
    "bounds": BoundsGate,
    "approval": ApprovalGate,
}


def enabled_gates(cfg: dict) -> list:
    gates = []
    for name, gate_cls in GATES.items():
        section = cfg.get(name)
        if section is None or section is False:
            continue
        gates.append(gate_cls(section if isinstance(section, dict) else {}))
    return gates
