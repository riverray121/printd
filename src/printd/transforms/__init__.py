"""Transform registry: ordered G-code rewrites applied after slicing."""

from .fresh_mesh import FreshMeshPreamble
from .marlin_patches import MarlinStartPatches

_TRANSFORMS = {
    "fresh_mesh_preamble": FreshMeshPreamble,
    "marlin_start_patches": MarlinStartPatches,
}


def build_transforms(cfg_list: list) -> list:
    out = []
    for entry in cfg_list or []:
        name = entry.get("name")
        try:
            out.append(_TRANSFORMS[name](entry))
        except KeyError:
            raise ValueError(f"unknown transform {name!r}") from None
    return out
