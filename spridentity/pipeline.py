"""End-to-end analysis: image in, inventory out."""
from __future__ import annotations

import hashlib
import math
import os
import re
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

from . import label as lab
from .background import detect_background
from .grid import infer_unit, lattice_fit, native_scale
from .segment import MERGE_T, S8, Region, Segmentation

SCHEMA_VERSION = "1.0"


def _runs(mask, x0, y0):
    """Row runs [y, x, length] in sheet coordinates."""
    padded = np.zeros((mask.shape[0], mask.shape[1] + 2), np.int8)
    padded[:, 1:-1] = mask
    d = np.diff(padded, axis=1)
    ys, starts = np.nonzero(d == 1)
    _, ends = np.nonzero(d == -1)
    return [[int(y + y0), int(s + x0), int(e - s)] for y, s, e in zip(ys, starts, ends)]


def _pick_backend(labeler, model, manual_dir, log, ollama_host="http://localhost:11434", hinter=None):
    if labeler == "none":
        return None
    if labeler == "ollama":
        return lab.OllamaBackend(model=model or lab.OllamaBackend().model, host=ollama_host, hinter=hinter)
    model = model or lab.DEFAULT_MODEL
    if labeler == "manual":
        return lab.ManualBackend(manual_dir)
    have_creds = (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")
                  or (Path.home() / ".config" / "anthropic").exists())
    if labeler == "auto" and not have_creds:
        log("no Anthropic credentials found: skipping identification (boundaries only). "
            "Set ANTHROPIC_API_KEY, or use --labeler manual.")
        return None
    try:
        return lab.AnthropicBackend(model=model)
    except Exception as e:
        if labeler == "anthropic":
            raise
        log(f"could not set up the Anthropic client ({e}): skipping identification")
        return None


def _units_from_regions(seg, regions, evidence):
    units = []
    for i, r in enumerate(regions):
        mask, x0, y0 = seg.region_mask(r)
        hints = list(r.reasons)
        ev = evidence[i]
        if ev["internal_min"] is not None and ev["internal_min"] < MERGE_T + 0.15:
            hints.append("pieces joined on weak evidence")
        units.append(lab.Unit(i, list(r.atoms), mask, x0, y0, hints, splittable=len(r.atoms) > 1,
                              near=dict(ev["external"])))
    return units


def _label(seg, backend, unit_px, log):
    """Returns (final assets as dicts with 'atoms' + label fields, problems)."""
    evidence = seg.boundary_evidence()
    units = _units_from_regions(seg, seg.regions, evidence)
    if getattr(backend, "per_candidate", False):
        log(f"identifying {len(units)} candidates one at a time with {backend.name} ({backend.model})...")
        assets, problems = backend.label_each(seg.rgba, seg.bg, units, unit_px, log)
        for a in assets:
            a["atoms"] = [at for u in a["units"] for at in u.atoms]
            a["n_units"] = 1
        return assets, problems
    log(f"identifying {len(units)} candidates with {backend.name} "
        f"({len(lab.make_chunks(units, seg.w, seg.h))} requests)...")
    assets, problems = lab.label_units(backend, seg.rgba, seg.bg, units, unit_px)

    # refinement: re-cut what the model said holds more than one thing, and ask again
    redo = [a for a in assets if a.get("split_suggested") and any(u.splittable for u in a["units"])]
    if redo:
        keep = [a for a in assets if not any(a is r for r in redo)]
        atoms = [at for a in redo for u in a["units"] for at in u.atoms]
        fine, ev = [], seg.boundary_evidence([Region([at]) for at in atoms])
        for i, at in enumerate(atoms):
            mask, x0, y0 = seg.region_mask(Region([at]))
            fine.append(lab.Unit(i, [at], mask, x0, y0, [], splittable=False, near=dict(ev[i]["external"])))
        log(f"re-cutting {len(redo)} candidates into {len(fine)} pieces and asking again...")
        if isinstance(backend, lab.ManualBackend):
            backend = lab.ManualBackend(backend.folder, tag="pass2")
        again, more = lab.label_units(backend, seg.rgba, seg.bg, fine, unit_px)
        if all(not a["labelled"] for a in again):
            problems += more + ["refinement pass produced nothing; kept the first-pass grouping"]
        else:
            for a in again:
                a["refined"] = True
            assets, problems = keep + again, problems + more
    for a in assets:
        a["atoms"] = [at for u in a["units"] for at in u.atoms]
        a["n_units"] = len(a["units"])
    return assets, problems


def _similarity(entries, rgba):
    """Pairs of same-sized assets with matching pixels: (i, j, score)."""
    buckets = {}
    for i, e in enumerate(entries):
        buckets.setdefault(e["_mask"].shape, []).append(i)
    pairs = []
    for (h, w), idx in buckets.items():
        if len(idx) < 2:
            continue
        if len(idx) > 400:  # too many to compare pairwise: exact duplicates only
            seen = {}
            for i in idx:
                e = entries[i]
                key = hashlib.sha1(e["_mask"].tobytes() + rgba[e["_y0"]:e["_y0"] + h, e["_x0"]:e["_x0"] + w, :3][e["_mask"]].tobytes()).digest()
                if key in seen:
                    pairs.append((seen[key], i, 1.0))
                else:
                    seen[key] = i
            continue
        masks = np.stack([entries[i]["_mask"] for i in idx])
        px = np.stack([rgba[entries[i]["_y0"]:entries[i]["_y0"] + h, entries[i]["_x0"]:entries[i]["_x0"] + w, :3]
                       for i in idx]).astype(np.int16)
        for a in range(len(idx) - 1):
            both = masks[a] & masks[a + 1:]
            same = both & (np.abs(px[a] - px[a + 1:]).sum(-1) == 0)
            union = (masks[a] | masks[a + 1:]).sum((1, 2))
            score = same.sum((1, 2)) / np.maximum(union, 1)
            # an identical silhouette counts too (recolours), unless it is just a filled rectangle
            shape = (both.sum((1, 2)) / np.maximum(union, 1) >= 0.95) & (not masks[a].all())
            for off in np.nonzero((score >= 0.5) | shape)[0]:
                pairs.append((idx[a], idx[a + 1 + off], float(score[off])))
    return pairs


def analyze(path, unit=None, bg="auto", labeler="auto", model=None, manual_dir=None,
            min_bg_area=None, include_masks=True, log=print, ollama_host="http://localhost:11434",
            hints="none", hints_model=None, vocab=None):
    """Analyse one sheet. Returns (inventory dict, id_map uint16 array, rgba array, bg mask)."""
    path = Path(path)
    rgba = np.array(Image.open(path).convert("RGBA"))
    h, w = rgba.shape[:2]

    # Enlarged pixel art is analysed at its drawn size, so the same sheet at 1x, 2x
    # and 3x gives the same answer; everything is carried back to full size below.
    k = native_scale(rgba)
    if unit:
        k = math.gcd(k, int(unit[0]), int(unit[1]))
    pixel_scale = k
    small = rgba[::k, ::k] if k > 1 else rgba
    notes = []

    if unit:
        u = (int(unit[0]) // k, int(unit[1]) // k)
        if min_bg_area is None:
            min_bg_area = max(4, u[0] * u[1] // 16)
        bg_small, bginfo = detect_background(small, bg, min_bg_area)
        fit = lattice_fit(~bg_small, u)
        unit_info = {"width": int(unit[0]), "height": int(unit[1]), "source": "user", "confidence": 1.0,
                     "check": fit}
        if not fit["divides_sheet"]:
            notes.append(f"The stated unit {unit[0]}x{unit[1]} does not divide the sheet size {w}x{h}.")
        if fit["small_blobs"] >= 8 and fit["share"] < 0.6:
            notes.append(f"Only {fit['inside_one_cell']} of {fit['small_blobs']} unit-sized pieces sit inside one "
                         f"{unit[0]}x{unit[1]} cell: the content is not laid out on that lattice (or the unit is "
                         "wrong). The unit is still used as the expected size of an asset.")
    else:
        bg_small, bginfo = detect_background(small, bg, 16 if min_bg_area is None else min_bg_area)
        guess, conf = infer_unit(small, bg_small, min_period=8 if k < 4 else max(2, 8 // k))
        fit = lattice_fit(~bg_small, guess) if guess else None
        usable = guess is not None and conf >= 0.3 and (fit["small_blobs"] < 5 or fit["share"] >= 0.9)
        u = guess if usable else None
        unit_info = {"width": guess[0] * k if usable else None, "height": guess[1] * k if usable else None,
                     "source": "inferred" if usable else "none", "confidence": conf, "check": fit if usable else None}
    unit_px = (u[0] * k, u[1] * k) if u else None
    log(f"{path.name}: {w}x{h}" + (f" (art enlarged {k}x)" if k > 1 else "") + f", background={bginfo['mode']}, unit="
        + (f"{unit_px[0]}x{unit_px[1]} ({unit_info['source']})" if unit_px else "none"))

    seg = Segmentation(small, bg_small, u)
    if k > 1:
        bgmask = np.repeat(np.repeat(bg_small, k, axis=0), k, axis=1)
        seg.upscale(k, rgba, bgmask)
    else:
        bgmask = bg_small
    log(f"segmentation: {seg.n_atoms} pieces -> {len(seg.regions)} candidates")
    if bginfo["mode"] == "none" and unit_px is None:
        notes.append("No background and no grid could be found, so there is nothing to cut along. "
                     "Pass --unit (and --bg if the sheet uses a colour key).")

    hinter = None
    if hints == "clip":
        if labeler != "ollama":
            notes.append("CLIP hints are only used with the ollama labeler; they were skipped.")
        else:
            from .hints import DEFAULT_MODEL, ClipHinter
            hinter = ClipHinter(model=hints_model or DEFAULT_MODEL, vocab=vocab, log=log)
    backend = _pick_backend(labeler, model, manual_dir, log, ollama_host, hinter)
    problems = []
    if backend:
        labelled, problems = _label(seg, backend, unit_px, log)
    else:
        labelled = [{"atoms": list(r.atoms), "labelled": False, "reasons": r.reasons, "n_units": 1}
                    for r in seg.regions]
    reasons_by_atom = {a: r.reasons for r in seg.regions for a in r.atoms}

    # ---- assemble ---------------------------------------------------------
    finals = [Region(a["atoms"]) for a in labelled]
    order = sorted(range(len(finals)), key=lambda i: (seg.region_bbox(finals[i])[1] // (unit_px[1] if unit_px else 16),
                                                      seg.region_bbox(finals[i])[0]))
    finals, labelled = [finals[i] for i in order], [labelled[i] for i in order]
    evidence = seg.boundary_evidence(finals)
    ids = [f"a{i + 1:04d}" for i in range(len(finals))]
    id_map = np.zeros((h, w), np.uint16)
    entries, used_names = [], {}
    for i, (r, a) in enumerate(zip(finals, labelled)):
        mask, x0, y0 = seg.region_mask(r)
        mh, mw = mask.shape
        id_map[y0:y0 + mh, x0:x0 + mw][mask] = i + 1
        area = int(mask.sum())
        parts_map, n_parts = ndi.label(mask, S8)
        ev = evidence[i]
        mi, ext = ev["internal_min"], ev["external"]
        me = max(ext.values()) if ext else None
        margin = min(mi - MERGE_T if mi is not None else 0.5, MERGE_T - me if me is not None else 0.5)
        pixel_conf = float(np.clip(0.5 + margin, 0.05, 1.0))
        unc = []
        reasons = sorted({x for at in r.atoms for x in reasons_by_atom.get(at, [])})
        if reasons and n_parts > 1:
            pixel_conf = min(pixel_conf, 0.7)
            unc.append({"kind": "boundary", "note": "disconnected parts grouped by rule: " + "; ".join(reasons)})
        if bginfo["mode"] == "none" and unit_px is None:
            pixel_conf = 0.05
        if mi is not None and mi < MERGE_T + 0.15:
            unc.append({"kind": "boundary", "note": "touching pieces kept together because nothing in the pixels "
                                                    f"shows they are separate (affinity {mi:.2f}); "
                                                    "this may be more than one asset"})
        for j, aff in sorted(ext.items(), key=lambda t: -t[1]):
            if aff >= MERGE_T - 0.2:
                unc.append({"kind": "boundary", "related": ids[j],
                            "note": f"touches {ids[j]} and may belong with it (affinity {aff:.2f})"})
        if unit_px and unit_info["source"] == "user" and area < unit_px[0] * unit_px[1] / 8 and n_parts == 1:
            unc.append({"kind": "boundary", "note": "much smaller than the stated minimum unit; may be a fragment"})

        cells = unit_box = None
        solid = area == mh * mw
        if unit_px:
            uw, uh = unit_px
            # the box an asset needs: whole units, never less than one. On the lattice
            # when the asset sits in as few cells as its size allows, else fitted round it.
            nc, nr = -(-mw // uw), -(-mh // uh)
            on = (x0 + mw - 1) // uw - x0 // uw + 1 == nc and (y0 + mh - 1) // uh - y0 // uh + 1 == nr
            if on:
                bx, by = x0 // uw * uw, y0 // uh * uh
            else:
                bx = int(np.clip(x0 - (nc * uw - mw) // 2, 0, max(0, w - nc * uw)))
                by = int(np.clip(y0 - (nr * uh - mh) // 2, 0, max(0, h - nr * uh)))
            unit_box = {"x": int(bx), "y": int(by), "w": int(nc * uw), "h": int(nr * uh), "on_lattice": bool(on)}
            cells = {"col": x0 // uw, "row": y0 // uh, "cols": -(-(x0 + mw) // uw) - x0 // uw,
                     "rows": -(-(y0 + mh) // uh) - y0 // uh,
                     "aligned": bool(x0 % uw == 0 and y0 % uh == 0 and (x0 + mw) % uw == 0 and (y0 + mh) % uh == 0)}

        if a["labelled"]:
            grouping = a["grouping"]
            if grouping is None:
                boundary = round(pixel_conf, 2)
            elif a["n_units"] > 1 or a.get("refined"):
                boundary = grouping  # the model drew this boundary; pixel evidence is kept alongside
                if mi is None or mi < MERGE_T:
                    unc.append({"kind": "boundary", "note": "grouped by the vision model; the pieces are weakly "
                                                            "connected or unconnected in the pixels"})
            else:
                boundary = round(0.5 * pixel_conf + 0.5 * grouping, 2)
            if grouping is not None and grouping <= 0.3:
                unc.append({"kind": "boundary", "note": "the vision model was unsure these pieces form one asset"})
            if a["split_suggested"] and not a.get("refined"):
                unc.append({"kind": "boundary", "note": "the vision model thinks this holds more than one asset, "
                                                        "but no finer cut was available"})
            second = None
            if a.get("hints"):
                # second opinion: the name the vision model chose against the classifier's ranking
                from .hints import STRONG, agrees
                top = a["hints"][:3]
                agree, strong = agrees(a["name"], [g for g, _ in top]), top[0][1] >= STRONG
                second = {"model": hinter.model_name, "guesses": [{"name": g, "score": s} for g, s in a["hints"]],
                          "vision_model_name": a["name"], "agrees_with_name": bool(agree),
                          "name_from": "vision model"}
                if agree:
                    a["identity"] = 0.8 if strong else 0.7
                elif strong:
                    # In our trial a strong classifier pick that the vision model contradicted was right
                    # about 7 times in 10 and the vision model about 1 in 4, so the classifier's word wins.
                    unc.append({"kind": "identity", "note": f"named by the classifier ({top[0][1]:.2f}); the vision "
                                                            f"model called it '{a['name']}', and its description "
                                                            "may not match the name"})
                    a["name"], a["identity"], second["name_from"] = top[0][0], 0.6, "classifier"
                else:
                    a["identity"] = min(a["identity"], 0.45)
            if a["identity"] <= 0.6:
                unc.append({"kind": "identity", "note": "identification is " + ("a guess" if a["identity"] <= 0.3
                                                                                 else "plausible but not certain")})
            if a["notes"]:
                unc.append({"kind": "note", "note": a["notes"]})
            label = re.sub(r"[^a-z0-9_]+", "_", a["name"].lower()).strip("_") or "unnamed"
            n = used_names[label] = used_names.get(label, 0) + 1
            name = label if n == 1 else f"{label}_{n}"
            ident = a["identity"]
        else:
            boundary, grouping, label, name, ident, second = round(pixel_conf, 2), None, None, None, 0.0, None
            unc.append({"kind": "identity", "note": "not identified: no vision model answer for this asset"})

        entries.append({
            "id": ids[i],
            "name": name,
            "label": label,
            "category": a.get("category", "unknown") if a["labelled"] else "unknown",
            "description": a.get("description", "") if a["labelled"] else "",
            "bbox": {"x": int(x0), "y": int(y0), "w": int(mw), "h": int(mh)},
            "unit_box": unit_box,
            "grid": cells,
            "shape": "rect" if solid else "mask",
            "pixel_count": area,
            "parts": [{"x": int(x0 + s[1].start), "y": int(y0 + s[0].start), "w": int(s[1].stop - s[1].start),
                       "h": int(s[0].stop - s[0].start)} for s in ndi.find_objects(parts_map)] if n_parts > 1 else [],
            "mask": None if solid or not include_masks else {"encoding": "row_runs", "runs": _runs(mask, x0, y0)},
            "confidence": {"boundary": round(float(boundary), 2), "identity": round(float(ident), 2),
                           "pixel_evidence": round(pixel_conf, 2), "model_grouping": grouping},
            "uncertain": bool(boundary < 0.6 or (a["labelled"] and ident <= 0.3)),
            "uncertainty": unc,
            "second_opinion": second,
            "relationships": [{"type": "touches", "target": ids[j]} for j in sorted(ext)],
            "_mask": mask, "_x0": x0, "_y0": y0,
            "_group": (a.get("group", ""), a.get("group_type", "none")) if a["labelled"] else ("", "none"),
        })

    # ---- relationships and groups ------------------------------------------
    groups = []
    named = {}
    for e in entries:
        g, t = e["_group"]
        if g:
            named.setdefault((g, t), []).append(e)
    pairs = _similarity(entries, rgba)
    parent = list(range(len(entries)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for i, j, score in pairs:
        if score >= 0.999:
            entries[j]["relationships"].append({"type": "duplicate_of", "target": entries[i]["id"]})
        else:
            entries[i]["relationships"].append({"type": "similar_to", "target": entries[j]["id"], "score": round(score, 2)})
            entries[j]["relationships"].append({"type": "similar_to", "target": entries[i]["id"], "score": round(score, 2)})
        parent[find(j)] = find(i)
    sets = {}
    for i in range(len(entries)):
        sets.setdefault(find(i), []).append(i)

    def add_group(gtype, name, members, note=""):
        gid = f"g{len(groups) + 1:03d}"
        groups.append({"id": gid, "type": gtype, "name": name, "members": [m["id"] for m in members], "note": note})
        for m in members:
            m["relationships"].append({"type": "member_of", "target": gid})
    for (g, t), members in named.items():
        add_group(t, g, members)
    for members in sets.values():
        if len(members) > 1:
            add_group("similar_pixels", None, [entries[i] for i in members],
                      "same size with matching pixels or silhouette: likely duplicates, animation frames or variants")
    for e in entries:
        for k in [k for k in e if k.startswith("_")]:
            del e[k]

    inventory = {
        "schema_version": SCHEMA_VERSION,
        "source": {"file": path.name, "width": w, "height": h,
                   "sha256": hashlib.sha256(path.read_bytes()).hexdigest()},
        "analysis": {
            "background": bginfo,
            "unit": unit_info,
            "pixel_scale": pixel_scale,
            "labeler": {"backend": backend.name if backend else "none",
                        "model": getattr(backend, "model", None),
                        "hints": hinter.model_name if hinter else None,
                        "problems": problems},
            "notes": notes,
        },
        "summary": {"assets": len(entries), "uncertain": sum(e["uncertain"] for e in entries),
                    "identified": sum(e["label"] is not None for e in entries), "groups": len(groups)},
        "assets": entries,
        "groups": groups,
    }
    return inventory, id_map, rgba, bgmask
