from printd.transforms.fresh_mesh import FreshMeshPreamble
from printd.transforms.marlin_patches import MarlinStartPatches

FILE = "M104 S215\nG28 ;Home\nG1 X-2.1 Y0 F3000\n"


def test_fresh_mesh_prepends_and_respects_opt_out():
    t = FreshMeshPreamble({"name": "fresh_mesh_preamble", "default": True, "bed_temp": 65})
    out = t.apply(FILE, {})
    assert out.startswith("; printd: fresh-mesh preamble")
    assert "G29" in out and "M500" in out
    assert t.apply(FILE, {"fresh_mesh": False}) == FILE


def test_marlin_patches_target_file_g28_not_preamble():
    fresh = FreshMeshPreamble({"name": "fresh_mesh_preamble", "default": True})
    patch = MarlinStartPatches(
        {"name": "marlin_start_patches", "saved_mesh_cmd": "M420 S1",
         "purge_x_replacements": {"X-2.1": "X0.4"}}
    )
    out = patch.apply(fresh.apply(FILE, {}), {})
    pre, _, body = out.partition("; printd: end fresh-mesh preamble\n")
    assert "M420 S1" not in pre, "preamble G28 must probe without a stale mesh"
    lines = body.split("\n")
    g28_idx = next(i for i, l in enumerate(lines) if l.startswith("G28"))
    assert lines[g28_idx + 1].startswith("M420 S1")
    assert "X-2.1" not in out and "X0.4" in out
