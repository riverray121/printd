"""Binary STL bounding box and in-place translation."""

import struct
from dataclasses import dataclass
from pathlib import Path

_HEADER = 80
_TRI_SIZE = 50  # normal(12) + 3 vertices(36) + attr(2)


@dataclass
class Bbox:
    min_x: float
    min_y: float
    min_z: float
    max_x: float
    max_y: float
    max_z: float

    @property
    def size(self) -> tuple[float, float, float]:
        return (self.max_x - self.min_x, self.max_y - self.min_y, self.max_z - self.min_z)

    @property
    def center_xy(self) -> tuple[float, float]:
        return ((self.min_x + self.max_x) / 2, (self.min_y + self.max_y) / 2)


def _is_binary(path: Path) -> bool:
    with open(path, "rb") as f:
        head = f.read(_HEADER + 4)
    if len(head) < _HEADER + 4:
        return False
    (count,) = struct.unpack_from("<I", head, _HEADER)
    return path.stat().st_size == _HEADER + 4 + count * _TRI_SIZE


def bbox(path: Path) -> Bbox:
    if not _is_binary(path):
        raise ValueError(f"{path.name}: only binary STL is supported")
    lo = [float("inf")] * 3
    hi = [float("-inf")] * 3
    with open(path, "rb") as f:
        f.seek(_HEADER)
        (count,) = struct.unpack("<I", f.read(4))
        for _ in range(count):
            tri = f.read(_TRI_SIZE)
            for v in range(3):
                x, y, z = struct.unpack_from("<3f", tri, 12 + v * 12)
                for i, c in enumerate((x, y, z)):
                    lo[i] = min(lo[i], c)
                    hi[i] = max(hi[i], c)
    return Bbox(lo[0], lo[1], lo[2], hi[0], hi[1], hi[2])


def translate(src: Path, dst: Path, dx: float, dy: float, dz: float = 0.0) -> None:
    """Copy ``src`` to ``dst`` with every vertex shifted by (dx, dy, dz)."""
    with open(src, "rb") as f:
        data = bytearray(f.read())
    (count,) = struct.unpack_from("<I", data, _HEADER)
    off = _HEADER + 4
    for _ in range(count):
        for v in range(3):
            base = off + 12 + v * 12
            x, y, z = struct.unpack_from("<3f", data, base)
            struct.pack_into("<3f", data, base, x + dx, y + dy, z + dz)
        off += _TRI_SIZE
    with open(dst, "wb") as f:
        f.write(data)
