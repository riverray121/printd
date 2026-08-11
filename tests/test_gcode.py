from pathlib import Path

from printd import gcode

SAMPLE = """\
;TYPE:Skirt
G28 ;Home
G1 X10.5 Y20 Z0.2 E.056
G1 X-2.1 Y210.0 E1.2
G0 Z250.5
"""


def write(tmp_path: Path, text: str) -> Path:
    p = tmp_path / "t.gcode"
    p.write_text(text)
    return p


def test_extents_and_types(tmp_path):
    r = gcode.analyze(write(tmp_path, SAMPLE))
    assert r.feature_types == {"Skirt"}
    assert r.min_x == -2.1 and r.max_x == 10.5
    assert r.max_y == 210.0
    assert r.max_z == 250.5


def test_leading_dot_decimals_do_not_crash(tmp_path):
    r = gcode.analyze(write(tmp_path, "G1 X.5 Y.25 E.056\n"))
    assert r.max_x == 0.5 and r.max_y == 0.25


def test_skip_preamble_lines(tmp_path):
    pre = "; pre\nG28\nG29"
    r = gcode.analyze(write(tmp_path, pre + "\nG1 X50 Y50 E1\n"), skip_leading_lines_of=pre)
    assert r.max_x == 50


def test_insert_after_line():
    out = gcode.insert_after_line("G28 ;Home\nG1 X1", "G28", "M420 S1")
    assert out.split("\n")[1] == "M420 S1"
