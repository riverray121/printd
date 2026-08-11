import struct

from printd import stl
from printd.gates import placement


def make_cube(path, size=10.0, offset=(0.0, 0.0, 0.0)):
    """Minimal binary STL: two triangles spanning the bbox corners."""
    ox, oy, oz = offset
    tris = [
        [(ox, oy, oz), (ox + size, oy + size, oz + size), (ox + size, oy, oz)],
        [(ox, oy, oz), (ox, oy + size, oz + size), (ox + size, oy + size, oz + size)],
    ]
    with open(path, "wb") as f:
        f.write(b"\0" * 80)
        f.write(struct.pack("<I", len(tris)))
        for tri in tris:
            f.write(struct.pack("<3f", 0, 0, 1))
            for v in tri:
                f.write(struct.pack("<3f", *v))
            f.write(struct.pack("<H", 0))


def test_bbox(tmp_path):
    p = tmp_path / "cube.stl"
    make_cube(p, 10, (5, 5, 0))
    b = stl.bbox(p)
    assert b.size == (10, 10, 10)
    assert b.center_xy == (10, 10)


def test_placement_centers_in_zone(tmp_path):
    src, dst = tmp_path / "a.stl", tmp_path / "b.stl"
    make_cube(src, 20, (0, 0, 0))
    note = placement.place(src, dst, {"preferred": [55, 55, 165, 165]}, (220, 220))
    assert note is None
    assert stl.bbox(dst).center_xy == (110, 110)


def test_placement_oversize_full_bed_with_note(tmp_path):
    src, dst = tmp_path / "a.stl", tmp_path / "b.stl"
    make_cube(src, 200, (0, 0, 0))
    note = placement.place(src, dst, {"preferred": [55, 55, 165, 165]}, (220, 220))
    assert note and "full bed" in note
    assert stl.bbox(dst).center_xy == (110, 110)
