"""Synthetic sheets with known contents. Run: python -m pytest -q"""
import json

import numpy as np
import pytest
from PIL import Image

from spridentity import label as lab
from spridentity import pipeline
from spridentity.pipeline import analyze

U = 16


def make_sheet(bg_rgba=(0, 0, 0, 0)):
    """6x4 cells of 16px. Returns (rgba, truth) with truth = {name: (x, y, w, h)}."""
    rng = np.random.default_rng(7)
    img = np.zeros((4 * U, 8 * U, 4), np.uint8)
    img[:] = bg_rgba
    truth = {}

    def material(base):  # noisy flat texture, 4 shades
        shades = np.array([base, [c * 0.85 for c in base], [min(255, c * 1.1) for c in base], [c * 0.7 for c in base]])
        tex = shades[rng.integers(0, 4, (2 * U, 2 * U))]
        tex[U - 1::U, :] = tex[:, U - 1::U] = shades[3] * 0.8  # each tile has a darker bottom/right edge
        return tex.astype(np.uint8)

    # three 2x2-cell terrain blocks packed edge to edge
    for i, (name, base) in enumerate([("brick", (170, 70, 50)), ("grass", (60, 150, 60)), ("water", (50, 90, 200))]):
        img[0:2 * U, i * 2 * U:(i + 1) * 2 * U, :3] = material(base)
        img[0:2 * U, i * 2 * U:(i + 1) * 2 * U, 3] = 255
        truth[name] = (i * 2 * U, 0, 2 * U, 2 * U)

    def blob(x, y, w, h, color):
        img[y:y + h, x:x + w] = (*color, 255)

    # a "tree": canopy and trunk crossing a cell seam, 1x2 cells, not filling them
    blob(2, 2 * U + 3, 12, 14, (30, 120, 40))
    blob(6, 2 * U + 17, 4, 13, (110, 70, 30))
    truth["tree"] = (2, 2 * U + 3, 12, 27)
    # two posts in one cell: one asset in two disconnected parts
    blob(2 * U + 2, 2 * U + 2, 3, 12, (150, 150, 150))
    blob(2 * U + 10, 2 * U + 2, 3, 12, (150, 150, 150))
    truth["posts"] = (2 * U + 2, 2 * U + 2, 11, 12)
    # a gem, an exact duplicate, and a recoloured variant
    for i, color in enumerate([(200, 40, 40), (200, 40, 40), (40, 40, 200)]):
        x = (4 + i) * U + 3
        blob(x, 2 * U + 4, 10, 8, color)
        blob(x + 2, 2 * U + 6, 6, 4, (255, 255, 255))
        img[2 * U + 4, [x, x + 9]] = bg_rgba  # clipped top corners: not a plain rectangle
        truth[f"gem{i}"] = (x, 2 * U + 4, 10, 8)
    return img, truth


def boxes(inv):
    return {(a["bbox"]["x"], a["bbox"]["y"], a["bbox"]["w"], a["bbox"]["h"]): a for a in inv["assets"]}


@pytest.fixture(params=["alpha", "magenta"])
def sheet(request, tmp_path):
    img, truth = make_sheet((0, 0, 0, 0) if request.param == "alpha" else (255, 0, 255, 255))
    path = tmp_path / "sheet.png"
    Image.fromarray(img, "RGBA").save(path)
    return path, truth, request.param


def test_boundaries_without_labeler(sheet):
    path, truth, mode = sheet
    inv, id_map, _, _ = analyze(path, unit=(U, U), labeler="none", log=lambda m: None)
    assert inv["analysis"]["background"]["mode"] == ("alpha" if mode == "alpha" else "color_key")
    found = boxes(inv)
    for name, box in truth.items():
        assert box in found, f"{name} not found at {box}; got {sorted(found)}"
    assert len(inv["assets"]) == len(truth)
    assert len(found[truth["posts"]]["parts"]) == 2
    assert found[truth["brick"]]["shape"] == "rect" and found[truth["brick"]]["grid"]["aligned"]
    assert found[truth["tree"]]["grid"]["rows"] == 2
    rel = {(r["type"], r["target"]) for r in found[truth["gem1"]]["relationships"]}
    assert ("duplicate_of", found[truth["gem0"]]["id"]) in rel
    assert any(r["type"] == "similar_to" for r in found[truth["gem2"]]["relationships"])
    assert all(a["label"] is None and a["confidence"]["identity"] == 0 for a in inv["assets"])


def test_masks_match_id_map(sheet):
    path, _, _ = sheet
    inv, id_map, _, _ = analyze(path, unit=(U, U), labeler="none", log=lambda m: None)
    rebuilt = np.zeros_like(id_map)
    for n, a in enumerate(inv["assets"], start=1):
        if a["mask"] is None:
            b = a["bbox"]
            rebuilt[b["y"]:b["y"] + b["h"], b["x"]:b["x"] + b["w"]] = n
        else:
            for y, x, length in a["mask"]["runs"]:
                rebuilt[y, x:x + length] = n
    assert (rebuilt == id_map).all()
    json.dumps(inv)


def test_user_unit_is_context_not_a_cookie_cutter(sheet):
    path, truth, _ = sheet
    inv, *_ = analyze(path, unit=(8, 8), labeler="none", log=lambda m: None)
    found = boxes(inv)
    assert truth["tree"] in found and truth["gem0"] in found  # not diced into 8x8 pieces


class FakeBackend:
    """Merges the first two candidates of the first pass and asks to split nothing."""
    name = "fake"

    def __init__(self, split_first=False):
        self.calls, self.split_first = [], split_first

    def run(self, requests):
        out = []
        for content, _ in requests:
            ids = [int(l.split(":")[0]) for l in content[-1]["text"].splitlines() if l.startswith("  ")]
            self.calls.append(ids)
            first_pass = len(self.calls) == 1
            groups = [ids[:2]] + [[i] for i in ids[2:]] if first_pass and not self.split_first else [[i] for i in ids]
            out.append({"assets": [{
                "candidate_ids": g, "name": "thing", "category": "item", "description": "",
                "identity_confidence": "low" if n == 0 else "high", "grouping_confidence": "medium",
                "split_suggested": self.split_first and first_pass and n == 0, "group": "", "group_type": "none",
                "notes": "",
            } for n, g in enumerate(groups)]})
        return out


def test_model_regroups_only_whole_candidates(sheet, monkeypatch):
    path, truth, _ = sheet
    fake = FakeBackend()
    monkeypatch.setattr(pipeline, "_pick_backend", lambda *a: fake)
    inv, id_map, _, _ = analyze(path, unit=(U, U), labeler="anthropic", log=lambda m: None)
    assert len(inv["assets"]) == len(truth) - 1
    merged = [a for a in inv["assets"] if a["confidence"]["model_grouping"] is not None and a["bbox"]["w"] > 2 * U]
    assert merged and merged[0]["uncertain"]  # low identity confidence is surfaced
    assert sorted(a["name"] for a in inv["assets"])[:2] == ["thing", "thing_2"]
    assert (id_map > 0).sum() == sum(a["pixel_count"] for a in inv["assets"])


def test_split_suggestion_triggers_a_finer_second_pass(sheet, monkeypatch):
    path, truth, _ = sheet
    fake = FakeBackend(split_first=True)
    monkeypatch.setattr(pipeline, "_pick_backend", lambda *a: fake)
    inv, *_ = analyze(path, unit=(U, U), labeler="anthropic", log=lambda m: None)
    assert len(fake.calls) == 2 and len(fake.calls[1]) == 4  # the 2x2 brick block re-cut into its 4 tiles
    assert len(inv["assets"]) == len(truth) + 3


def test_unit_is_inferred_from_a_regular_sheet(tmp_path):
    rng = np.random.default_rng(3)
    img = np.zeros((8 * 24, 10 * 24, 4), np.uint8)
    for r in range(8):
        for c in range(10):
            if r < 3:  # edge-to-edge tiles with a darker rim
                base = rng.integers(60, 200, 3)
                img[r * 24:(r + 1) * 24, c * 24:(c + 1) * 24] = (*base, 255)
                img[r * 24 + 1:(r + 1) * 24 - 1, c * 24 + 1:(c + 1) * 24 - 1, :3] = np.minimum(255, base + 30)
            elif (r + c) % 3:  # sprites centred in their cells
                w, h = rng.integers(8, 20, 2)
                x, y = c * 24 + (24 - w) // 2, r * 24 + (24 - h) // 2
                img[y:y + h, x:x + w] = (*rng.integers(60, 200, 3), 255)
    path = tmp_path / "regular.png"
    Image.fromarray(img, "RGBA").save(path)
    inv, *_ = analyze(path, labeler="none", log=lambda m: None)
    assert (inv["analysis"]["unit"]["width"], inv["analysis"]["unit"]["height"]) == (24, 24)
    assert inv["analysis"]["unit"]["source"] == "inferred"


def test_touching_objects_without_a_grid_are_split_at_the_neck(tmp_path):
    img = np.zeros((40, 100, 4), np.uint8)
    img[5:35, 5:40] = (200, 60, 60, 255)
    img[5:35, 55:95] = (60, 60, 200, 255)
    img[18:21, 40:55] = (20, 20, 20, 255)  # a thin bridge joins the two bodies
    path = tmp_path / "necks.png"
    Image.fromarray(img, "RGBA").save(path)
    inv, *_ = analyze(path, labeler="none", log=lambda m: None)
    assert inv["analysis"]["unit"]["source"] == "none"
    assert len(inv["assets"]) == 2
    assert all(any(r["type"] == "touches" for r in a["relationships"]) for a in inv["assets"])


def test_local_backend_names_each_candidate_once_per_distinct_sprite(sheet, monkeypatch):
    path, truth, _ = sheet
    backend = lab.OllamaBackend(model="fake")
    calls = []

    def fake_call(payload, path="/api/chat"):
        calls.append(payload)
        assert len(payload["messages"][0]["images"]) == 2
        return {"message": {"content": json.dumps({"name": "Thing", "category": "item", "description": "x",
                                                   "confidence": "high", "multiple_objects": False})}}
    monkeypatch.setattr(backend, "_call", fake_call)
    monkeypatch.setattr(pipeline, "_pick_backend", lambda *a: backend)
    inv, *_ = analyze(path, unit=(U, U), labeler="ollama", log=lambda m: None)
    assert len(calls) == len(truth) - 1  # the duplicated gem is asked about once
    assert len(inv["assets"]) == len(truth) and all(a["label"] == "thing" for a in inv["assets"])
    assert all(a["confidence"]["identity"] == 0.6 and a["confidence"]["model_grouping"] is None for a in inv["assets"])


# ---- the unit is an expected size, not a set of cut lines ------------------------------

def _save(tmp_path, img, name="s.png"):
    path = tmp_path / name
    Image.fromarray(img, "RGBA").save(path)
    return path


def _run(path, unit=U):
    return analyze(path, unit=(unit, unit) if unit else None, labeler="none", log=lambda m: None)[0]


def test_one_object_crossing_unit_lines_is_not_cut(tmp_path):
    img = np.zeros((4 * U, 4 * U, 4), np.uint8)
    img[4:14, 3:13] = (240, 220, 120, 255)      # lamp head in the top cell
    img[14:44, 7:9] = (90, 60, 30, 255)         # a thin pole of another colour down two more cells
    img[44:47, 4:12] = (60, 40, 20, 255)        # foot
    inv = _run(_save(tmp_path, img))
    assert len(inv["assets"]) == 1
    a = inv["assets"][0]
    assert (a["unit_box"]["w"], a["unit_box"]["h"], a["unit_box"]["on_lattice"]) == (U, 3 * U, True)


def test_two_shapes_that_only_touch_on_a_unit_line_are_separate(tmp_path):
    img = np.zeros((2 * U, 4 * U, 4), np.uint8)
    yy, xx = np.mgrid[0:U, 0:U]
    disc = (yy - 7.5) ** 2 + (xx - 7.5) ** 2 <= 8.2 ** 2
    for i, colour in enumerate([(200, 60, 60), (60, 200, 60), (60, 60, 200)]):
        img[0:U, i * U:(i + 1) * U][disc] = (*colour, 255)
    inv = _run(_save(tmp_path, img))
    assert len(inv["assets"]) == 3


def test_touching_shapes_without_evidence_stay_one_flagged_asset(tmp_path):
    img = np.zeros((2 * U, 4 * U, 4), np.uint8)
    img[2:U, 2:14] = (200, 60, 60, 255)         # two plain slabs meeting on the line at full width
    img[U:30, 2:14] = (60, 60, 200, 255)
    inv = _run(_save(tmp_path, img))
    assert len(inv["assets"]) == 1
    assert inv["assets"][0]["uncertain"]
    assert any("may be more than one asset" in u["note"] for u in inv["assets"][0]["uncertainty"])


def test_icons_on_filled_cells_are_one_asset_per_cell(tmp_path):
    rng = np.random.default_rng(1)
    img = np.zeros((3 * U, 5 * U, 4), np.uint8)
    img[:] = (200, 80, 120, 255)                # every cell filled with the same backing colour
    for r in range(3):
        for c in range(5):
            w, h = rng.integers(4, 11, 2)
            img[r * U + 3:r * U + 3 + h, c * U + 3:c * U + 3 + w, :3] = 255
    inv = analyze(_save(tmp_path, img), unit=(U, U), bg="none", labeler="none", log=lambda m: None)[0]
    assert len(inv["assets"]) == 15
    assert all(a["bbox"]["w"] == U and a["bbox"]["h"] == U for a in inv["assets"])


def test_same_answer_at_every_enlargement(sheet, tmp_path):
    path, _, _ = sheet
    base = np.array(Image.open(path).convert("RGBA"))
    for unit in (U, None):
        ref = _run(path, unit)
        for k in (2, 3):
            big = np.repeat(np.repeat(base, k, axis=0), k, axis=1)
            inv = _run(_save(tmp_path, big, f"x{k}.png"), unit * k if unit else None)
            assert inv["analysis"]["pixel_scale"] == k
            assert [(a["bbox"]["x"], a["bbox"]["y"], a["bbox"]["w"], a["bbox"]["h"]) for a in inv["assets"]] == \
                   [(a["bbox"]["x"] * k, a["bbox"]["y"] * k, a["bbox"]["w"] * k, a["bbox"]["h"] * k) for a in ref["assets"]]


def test_sprite_off_the_lattice_gets_a_fitted_unit_box(tmp_path):
    img = np.zeros((4 * U, 4 * U, 4), np.uint8)
    img[10:22, 10:22] = (200, 160, 60, 255)     # 12x12, straddling four cells
    img[10, 10] = img[21, 21] = 0
    a = _run(_save(tmp_path, img))["assets"]
    assert len(a) == 1
    assert a[0]["unit_box"] == {"x": 8, "y": 8, "w": U, "h": U, "on_lattice": False}


def test_a_stated_unit_that_does_not_fit_is_reported(sheet):
    path, _, _ = sheet
    inv = _run(path, 5)
    assert any("does not divide" in n for n in inv["analysis"]["notes"])
    assert inv["analysis"]["unit"]["check"]["divides_sheet"] is False


def test_hint_agreement():
    from spridentity.hints import agrees, load_vocab
    assert agrees("wooden_table", ["table", "desk"])
    assert agrees("pixel_soldier", ["man", "soldier"])
    assert agrees("chest", ["chest of drawers"])
    assert agrees("grass_tile", ["grass"])
    assert not agrees("suitcase", ["chair", "stool", "armchair"])
    assert not agrees("pixel_art_sprite", ["chair"])
    words = load_vocab()
    assert len(words) > 200 and len(words) == len(set(words)) and "chair" in words
