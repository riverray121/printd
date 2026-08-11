from .base import Slicer
from .orca import OrcaSlicer

_SLICERS = {"orca": OrcaSlicer}


def make_slicer(cfg: dict) -> Slicer:
    name = cfg.get("adapter", "orca")
    try:
        return _SLICERS[name](cfg)
    except KeyError:
        raise ValueError(f"unknown slicer adapter {name!r}") from None
