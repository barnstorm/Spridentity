"""Command line: python -m spridentity sheet.png [options]"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

from .label import DEFAULT_MODEL, OllamaBackend
from .pipeline import analyze
from .render import draw_overlay, extract


def _unit(text):
    parts = text.lower().split("x")
    try:
        vals = [int(p) for p in parts]
    except ValueError:
        raise argparse.ArgumentTypeError("use N or WxH, e.g. 16 or 24x32")
    if len(vals) == 1:
        vals *= 2
    if len(vals) != 2 or min(vals) < 1:
        raise argparse.ArgumentTypeError("use N or WxH, e.g. 16 or 24x32")
    return tuple(vals)


def _bg(text):
    if text in ("auto", "alpha", "none"):
        return text
    t = text.lstrip("#")
    if len(t) != 6:
        raise argparse.ArgumentTypeError("use auto, alpha, none or a hex colour like ff00ff")
    return tuple(int(t[i:i + 2], 16) for i in (0, 2, 4))


def main(argv=None):
    ap = argparse.ArgumentParser(prog="spridentity", description="Find, outline and name the assets on a sprite sheet.")
    ap.add_argument("image", type=Path)
    ap.add_argument("-o", "--out", type=Path, help="output folder (default: <image name>.spridentity next to the image)")
    ap.add_argument("--unit", type=_unit, help="minimum pixel unit as context, e.g. 16 or 24x32 (default: inferred)")
    ap.add_argument("--bg", type=_bg, default="auto", help="background: auto, alpha, none, or a hex colour key")
    ap.add_argument("--min-bg-area", type=int, default=None,
                    help="enclosed patches of the key colour smaller than this stay part of the asset "
                         "(default: 1/16 of a unit, or 16 pixels when no unit is given)")
    ap.add_argument("--labeler", choices=["auto", "ollama", "anthropic", "manual", "none"], default="auto",
                    help="who identifies the assets: ollama = local model, anthropic = Claude API "
                         "(default: anthropic if credentials exist, else none)")
    ap.add_argument("--model", help=f"model name (default: {OllamaBackend().model} for ollama, {DEFAULT_MODEL} for anthropic)")
    ap.add_argument("--ollama-host", default="http://localhost:11434", help="Ollama server address")
    ap.add_argument("--hints", choices=["none", "clip"], default="none",
                    help="clip = a CLIP model ranks a word list for each asset; the ollama labeler gets the ranking "
                         "as a hint and the inventory keeps it as a second opinion (needs torch and open_clip_torch)")
    ap.add_argument("--hints-model", help="open_clip model as ARCH/PRETRAINED (default: ViT-H-14/laion2b_s32b_b79k)")
    ap.add_argument("--vocab", type=Path, help="word list for --hints, comma or line separated (default: built in)")
    ap.add_argument("--extract", action="store_true", help="also write each asset as its own transparent PNG")
    ap.add_argument("--no-masks", action="store_true", help="leave per-pixel masks out of the JSON (the id map still has them)")
    ap.add_argument("--overlay-scale", type=int, default=0, help="zoom of the overlay image (default: auto)")
    args = ap.parse_args(argv)

    if not args.image.exists():
        ap.error(f"no such file: {args.image}")
    out = args.out or args.image.with_name(args.image.stem + ".spridentity")
    out.mkdir(parents=True, exist_ok=True)

    inv, id_map, rgba, bg = analyze(args.image, unit=args.unit, bg=args.bg, labeler=args.labeler, model=args.model,
                                    manual_dir=out / "label_requests", min_bg_area=args.min_bg_area,
                                    ollama_host=args.ollama_host, hints=args.hints, hints_model=args.hints_model,
                                    vocab=args.vocab,
                                    include_masks=not args.no_masks, log=lambda m: print(m, file=sys.stderr))

    (out / "assets.json").write_text(json.dumps(inv, indent=1), encoding="utf-8")
    Image.fromarray(id_map).save(out / "id_map.png")  # 16-bit: pixel value N = Nth asset, 0 = background
    scale = args.overlay_scale or int(max(1, min(6, 2400 // max(rgba.shape[:2]))))
    items = []
    for n, a in enumerate(inv["assets"], start=1):
        b = a["bbox"]
        m = id_map[b["y"]:b["y"] + b["h"], b["x"]:b["x"] + b["w"]] == n
        items.append((a["id"][1:].lstrip("0") + ("?" if a["uncertain"] else ""), m, b["x"], b["y"]))
        if args.extract:
            (out / "assets").mkdir(exist_ok=True)
            extract(rgba, m, b["x"], b["y"]).save(out / "assets" / f"{a['id']}{'_' + a['name'] if a['name'] else ''}.png")
    draw_overlay(rgba, bg, items, scale=scale).save(out / "overlay.png")

    s = inv["summary"]
    print(f"{s['assets']} assets ({s['identified']} identified, {s['uncertain']} flagged uncertain, "
          f"{s['groups']} groups) -> {out}")
    for p in inv["analysis"]["labeler"]["problems"][:10]:
        print("  labeler:", p, file=sys.stderr)
    for n in inv["analysis"]["notes"]:
        print("  note:", n, file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
