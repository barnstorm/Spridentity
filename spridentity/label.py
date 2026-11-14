"""Semantic stage: a vision model names the candidates and decides what belongs together.

The model never produces coordinates. It is shown the sheet with each candidate's
exact outline and a number, and answers in terms of those numbers, so geometry in
the final inventory still comes from the pixels.

Backends:
  ollama     a vision model running on this machine (free, no account); it only
             names candidates one at a time -- see OllamaBackend
  anthropic  call the Claude API
  manual     write each request (images + prompt) to a folder and read answers back
             from response_NN.json files placed there -- for other models, or a human
"""
from __future__ import annotations

import base64
import io
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image

from .render import composite, draw_overlay

DEFAULT_MODEL = "claude-opus-5-5"
CATEGORIES = ["terrain", "structure", "vegetation", "decoration", "furniture", "item", "character",
              "creature", "vehicle", "effect", "ui", "text", "other", "unknown"]
GROUP_TYPES = ["none", "animation", "variant_set", "terrain_set", "composite", "kit", "other"]
LEVELS = {"high": 0.9, "medium": 0.6, "low": 0.3}

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["assets"],
    "properties": {
        "assets": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["candidate_ids", "name", "category", "description", "identity_confidence",
                             "grouping_confidence", "split_suggested", "group", "group_type", "notes"],
                "properties": {
                    "candidate_ids": {"type": "array", "items": {"type": "integer"}},
                    "name": {"type": "string"},
                    "category": {"type": "string", "enum": CATEGORIES},
                    "description": {"type": "string"},
                    "identity_confidence": {"type": "string", "enum": list(LEVELS)},
                    "grouping_confidence": {"type": "string", "enum": list(LEVELS)},
                    "split_suggested": {"type": "boolean"},
                    "group": {"type": "string"},
                    "group_type": {"type": "string", "enum": GROUP_TYPES},
                    "notes": {"type": "string"},
                },
            },
        }
    },
}

SYSTEM = """You are helping build an inventory of the assets on a pixel-art sprite sheet.

A segmentation pass has already cut the sheet into candidate regions with pixel-exact \
outlines. It works from pixels alone, so it cannot know what anything is, and it makes two \
kinds of mistake: it leaves one thing in several pieces (a house as roof, wall and door; a \
tree as canopy and trunk; a terrain set as separate tiles), and it leaves several things in \
one piece when they touch (furniture drawn against a wall, two props sharing an edge). Your \
part is the judgement it lacks: say what each thing is, and say which candidates together \
make one complete asset, the way an artist or level designer would count them.

"One asset" means one thing someone would place or reference as a unit: a whole tree, a whole \
building, a single prop, one frame of a character, or one terrain material with its edge and \
corner pieces. Animation frames and colour or state variants are separate assets that share a \
group, not one asset.

You answer only in terms of candidate numbers; you never give coordinates. Every candidate \
listed for the crop appears in exactly one asset. The coloured outline is the candidate; \
bounding boxes of different candidates can overlap, and a candidate in several separate \
pieces carries its number on each piece. Numbers are sheet-wide, so gaps are normal, and \
anything in the crop without a number belongs to a neighbouring crop: ignore it.

When a candidate holds more than one asset -- several unrelated tiles in a row, a strip of \
animation frames, furniture fused to a wall -- and it is marked splittable, set \
split_suggested. It will be re-cut into its finest pieces and shown to you again, so name it \
roughly and move on. If pieces of it belong with other candidates (a roof next to a wall that \
is fused to furniture), put those candidates in the same asset: everything listed in a \
split_suggested asset is re-cut and re-shown together, and you regroup the pieces then. Do \
not split a single terrain material into its tiles, or a single object into its cells, just \
because it is marked splittable. If a candidate holds several things and is not splittable, \
name it for what it mostly is and say so in notes.

The remarks beside each candidate come from pixel statistics and are often wrong; treat \
them as prompts to look, not as evidence. "touches" lists neighbours it shares an edge with, \
"may belong with" neighbours whose colours continue across that edge, and "joined on weak \
evidence" means the pass was unsure the candidate is a single thing.

Groups relate separate assets: frames of one animation, colour or state variants, a terrain \
set, parts of a composite, or pieces of a building kit (fence section and fence post). Use \
one only when at least two assets share it.

Be honest about doubt. Small pixel art is often ambiguous: when you are guessing what \
something depicts, use low identity_confidence and put the alternatives in notes; when you \
are unsure whether pieces belong together, use low grouping_confidence. A confident wrong \
label is worse for the user than an uncertain one."""


@dataclass
class Unit:
    """Something shown to the model under one number: a set of atoms."""
    id: int
    atoms: list
    mask: np.ndarray
    x0: int
    y0: int
    hints: list = field(default_factory=list)
    splittable: bool = False
    near: dict = field(default_factory=dict)  # touching unit id -> affinity

    @property
    def bbox(self):
        return self.x0, self.y0, self.x0 + self.mask.shape[1], self.y0 + self.mask.shape[0]


def make_chunks(units, sheet_w, sheet_h, window=256, max_units=40):
    """Group units into crops small enough to upscale legibly.

    Units that touch are kept in one crop where possible, since those are the ones
    the model may need to regroup; a touching cluster too big for one crop falls
    back to fixed windows.
    """
    parent = {u.id: u.id for u in units}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for u in units:
        for other in u.near:
            if other in parent:
                parent[find(other)] = find(u.id)
    clusters = {}
    for u in units:
        clusters.setdefault(find(u.id), []).append(u)

    def box(members):
        return (min(u.bbox[0] for u in members), min(u.bbox[1] for u in members),
                max(u.bbox[2] for u in members), max(u.bbox[3] for u in members))

    def bucket(b):
        return ((b[1] + b[3]) // 2 // window, (b[0] + b[2]) // 2 // window)
    buckets = {}
    for members in clusters.values():
        b = box(members)
        if len(members) <= max_units and b[2] - b[0] <= 1.5 * window and b[3] - b[1] <= 1.5 * window:
            buckets.setdefault((0,) + bucket(b), []).append(members)
        else:
            for u in members:
                buckets.setdefault((1,) + bucket(u.bbox), []).append([u])
    chunks = []
    for key in sorted(buckets):
        part = []
        for members in buckets[key] + [None]:
            if part and (members is None or len(part) + len(members) > max_units):
                x0, y0, x1, y1 = box(part)
                chunks.append(((max(0, x0 - 4), max(0, y0 - 4), min(sheet_w, x1 + 4), min(sheet_h, y1 + 4)), part))
                part = []
            if members:
                part = part + members
    return chunks


def _png_b64(img):
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return base64.standard_b64encode(buf.getvalue()).decode()


def build_request(rgba, bg, crop, units, unit_px, n_chunks, index):
    """Returns (content_blocks, images) for one crop."""
    x0, y0, x1, y1 = crop
    scale = int(max(1, min(8, 1400 // max(x1 - x0, y1 - y0))))
    clean = Image.fromarray(composite(rgba[y0:y1, x0:x1], bg[y0:y1, x0:x1], scale))
    marked = draw_overlay(rgba, bg, [(str(u.id), u.mask, u.x0, u.y0) for u in units], scale=scale, crop=crop)
    h, w = bg.shape
    lines = [
        f"Sheet: {w}x{h} px. This crop: x {x0}-{x1}, y {y0}-{y1}, shown at {scale}x "
        f"(crop {index + 1} of {n_chunks}). Grey checkerboard is background.",
        (f"Grid context: the sheet appears to use a {unit_px[0]}x{unit_px[1]} px unit. Assets may be "
         f"smaller or span several units." if unit_px else "No tile grid was detected on this sheet."),
        "First image: the crop as drawn. Second image: the same crop with each candidate outlined in colour and "
        "its number placed on the candidate's own top-left pixels.",
        "",
        "Candidates (id: x,y wxh in sheet px; remarks from the segmentation pass):",
    ]
    here = {v.id for v in units}
    for u in units:
        bx0, by0, bx1, by1 = u.bbox
        strong = [str(j) for j, a in sorted(u.near.items()) if j in here and a >= 0.3]
        weak = [str(j) for j, a in sorted(u.near.items()) if j in here and a < 0.3]
        extra = "; ".join(u.hints + (["may belong with " + ", ".join(strong)] if strong else [])
                          + (["touches " + ", ".join(weak)] if weak else []) + (["splittable"] if u.splittable else []))
        lines.append(f"  {u.id}: {bx0},{by0} {bx1 - bx0}x{by1 - by0}" + (f"  ({extra})" if extra else ""))
    lines += [
        "",
        "Return the assets in this crop. For each: the candidate_ids it is made of; a short snake_case name; "
        "a category; a one-line description; identity_confidence and grouping_confidence; split_suggested; "
        "group and group_type when it belongs with other assets (same group string for every member; empty string "
        "and \"none\" otherwise); "
        "and notes for anything a user should double-check (empty string if nothing).",
    ]
    content = [
        {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": _png_b64(clean)}},
        {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": _png_b64(marked)}},
        {"type": "text", "text": "\n".join(lines)},
    ]
    return content, {"clean": clean, "marked": marked}


class LabelError(Exception):
    pass


class AnthropicBackend:
    name = "anthropic"

    def __init__(self, model=DEFAULT_MODEL, effort="high", workers=4):
        import anthropic
        self.anthropic = anthropic
        self.client = anthropic.Anthropic()
        self.model, self.effort, self.workers = model, effort, workers

    def _one(self, content):
        a = self.anthropic
        try:
            # Server-side refusal fallback: if a safety classifier declines the request,
            # the API re-runs it on a fallback model instead of returning nothing.
            with self.client.beta.messages.stream(
                model=self.model,
                max_tokens=32000,
                system=SYSTEM,
                messages=[{"role": "user", "content": content}],
                output_config={"effort": self.effort, "format": {"type": "json_schema", "schema": SCHEMA}},
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            ) as stream:
                msg = stream.get_final_message()
        except a.AuthenticationError as e:
            raise LabelError(f"authentication failed: {e.message}") from e
        except a.RateLimitError as e:
            raise LabelError(f"rate limited after retries: {e.message}") from e
        except a.APIStatusError as e:
            raise LabelError(f"API error {e.status_code}: {e.message}") from e
        except a.APIConnectionError as e:
            raise LabelError(f"could not reach the API: {e}") from e
        if msg.stop_reason in ("refusal", "max_tokens"):
            raise LabelError(f"response stopped early ({msg.stop_reason})")
        text = next((b.text for b in msg.content if b.type == "text"), None)
        if text is None:
            raise LabelError("response contained no text")
        return json.loads(text)

    def run(self, requests):
        def safe(req):
            try:
                return self._one(req[0])
            except LabelError as e:
                return e
            except Exception as e:  # missing credentials surface here as a plain SDK error
                return LabelError(str(e))
        with ThreadPoolExecutor(self.workers) as pool:
            return list(pool.map(safe, requests))


class ManualBackend:
    """Write requests to disk; use whatever response_NN.json files are already there."""
    name = "manual"

    def __init__(self, folder, tag="pass1"):
        self.folder, self.tag = Path(folder), tag

    def run(self, requests):
        self.folder.mkdir(parents=True, exist_ok=True)
        (self.folder / "system_prompt.txt").write_text(SYSTEM, encoding="utf-8")
        (self.folder / "response_schema.json").write_text(json.dumps(SCHEMA, indent=1), encoding="utf-8")
        out = []
        for i, (content, images) in enumerate(requests):
            stem = f"{self.tag}_{i:02d}"
            images["clean"].save(self.folder / f"{stem}_clean.png")
            images["marked"].save(self.folder / f"{stem}_marked.png")
            (self.folder / f"{stem}_prompt.txt").write_text(content[-1]["text"], encoding="utf-8")
            resp = self.folder / f"{stem}_response.json"
            if resp.exists():
                out.append(json.loads(resp.read_text(encoding="utf-8")))
            else:
                out.append(LabelError(f"waiting for {resp.name}"))
        return out


LOCAL_PROMPT = """Two images from a pixel-art game sprite sheet. The first is one sprite, enlarged, on plain grey.
The second shows where it sits on the sheet, outlined in red, among its neighbours, which hints at its
scale and theme (the neighbours are other things: do not name them).
The sprite is {w}x{h} pixels in the original{tile}.

Say what the sprite depicts. Answer with JSON only, with exactly these keys:
  "name": short snake_case name, e.g. "wooden_barrel", "grass_tile", "pine_tree"
  "category": one of {cats}
  "description": one short sentence
  "confidence": "high", "medium" or "low" -- use "low" when you are guessing
  "multiple_objects": true if the image clearly shows several separate things, else false"""

HINT_PROMPT = """

A separate image classifier, which is often wrong, ranked these guesses for the sprite (score from 0 to 1):
  {guesses}
If one of them fits what you see, use it as the name (you may add a word, e.g. a colour or material).
If none fits, ignore them and give your own name."""


class OllamaBackend:
    """Local identification through an Ollama server (https://ollama.com).

    Small local vision models are not reliable at reading a crop with dozens of
    numbered outlines and regrouping them, so this backend asks a simpler question:
    each candidate is shown alone, plus once in its surroundings, and named. Grouping stays with the pixel pass.
    Identical candidates are asked about once.
    """
    name = "ollama"
    per_candidate = True
    LEVELS = {"high": 0.6, "medium": 0.45, "low": 0.3}  # small models say "high" for everything, right or wrong

    def __init__(self, model="minicpm-v", host="http://localhost:11434", timeout=180, hinter=None):
        self.model, self.host, self.timeout, self.hinter = model, host.rstrip("/"), timeout, hinter

    def _call(self, payload, path="/api/chat"):
        import urllib.error
        import urllib.request
        req = urllib.request.Request(self.host + path, data=json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            raise LabelError(f"Ollama error {e.code}: {e.read().decode(errors='replace')[:200]}") from e
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise LabelError(f"could not reach Ollama at {self.host} ({e}); is it running?") from e

    @staticmethod
    def _picture(rgba, unit):
        """The candidate alone, enlarged with hard pixel edges, on mid grey."""
        h, w = unit.mask.shape
        px = rgba[unit.y0:unit.y0 + h, unit.x0:unit.x0 + w, :3].copy()
        px[~unit.mask] = (128, 128, 128)
        pad = max(2, max(w, h) // 8)
        canvas = np.full((h + 2 * pad, w + 2 * pad, 3), 128, np.uint8)
        canvas[pad:pad + h, pad:pad + w] = px
        scale = int(max(1, min(16, 448 // max(canvas.shape[:2]))))
        return Image.fromarray(np.kron(canvas, np.ones((scale, scale, 1), np.uint8)))

    @staticmethod
    def _context(rgba, bg, unit, margin=40):
        """The candidate outlined in place, with some of the sheet around it."""
        x0, y0, x1, y1 = unit.bbox
        crop = (max(0, x0 - margin), max(0, y0 - margin), min(bg.shape[1], x1 + margin), min(bg.shape[0], y1 + margin))
        scale = int(max(1, min(4, 448 // max(crop[2] - crop[0], crop[3] - crop[1]))))
        return draw_overlay(rgba, bg, [("", unit.mask, unit.x0, unit.y0)], scale=scale, crop=crop)

    def label_each(self, rgba, bg, units, unit_px, log=lambda m: None):
        """Returns (assets, problems) in the same shape as label_units."""
        import hashlib
        assets, problems, cache = [], [], {}
        guesses = [None] * len(units)
        if self.hinter:
            log(f"ranking names for {len(units)} candidates with {self.hinter.name} ({self.hinter.model_name})...")
            guesses = self.hinter.suggest([(rgba[u.y0:u.y0 + u.mask.shape[0], u.x0:u.x0 + u.mask.shape[1]], u.mask)
                                           for u in units])
        for n, u in enumerate(units):
            h, w = u.mask.shape
            crop = rgba[u.y0:u.y0 + h, u.x0:u.x0 + w, :3]
            key = hashlib.sha1(u.mask.tobytes() + crop[u.mask].tobytes()).digest()
            if key not in cache:
                tile = ""
                if unit_px and u.mask.all() and w % unit_px[0] == 0 and h % unit_px[1] == 0:
                    tile = f" and fills {w // unit_px[0]}x{h // unit_px[1]} grid tiles edge to edge, so it is probably terrain, a wall or a floor"
                prompt = LOCAL_PROMPT.format(w=w, h=h, tile=tile, cats=", ".join(CATEGORIES))
                if guesses[n]:
                    prompt += HINT_PROMPT.format(guesses=", ".join(f"{g} ({s:.2f})" for g, s in guesses[n]))
                try:
                    out = self._call({"model": self.model, "stream": False, "format": "json",
                                      "options": {"temperature": 0, "num_predict": 300, "num_ctx": 8192},
                                      "messages": [{"role": "user", "content": prompt,
                                                    "images": [_png_b64(self._picture(rgba, u)),
                                                               _png_b64(self._context(rgba, bg, u))]}]})
                    cache[key] = json.loads(out["message"]["content"])
                    if not isinstance(cache[key], dict):
                        raise ValueError("answer is not a JSON object")
                except LabelError as e:
                    problems.append(str(e))
                    if not cache:  # the very first call failed: the server or model is not usable
                        return [{"units": [x], "labelled": False} for x in units], problems
                    cache[key] = None
                except (ValueError, KeyError) as e:
                    problems.append(f"candidate {u.id}: unusable answer ({e})")
                    cache[key] = None
                if (n + 1) % 10 == 0:
                    log(f"  {n + 1}/{len(units)}")
            a = cache[key]
            if not a or not str(a.get("name", "")).strip():
                assets.append({"units": [u], "labelled": False, "hints": guesses[n]})
                continue
            several = a.get("multiple_objects") is True
            assets.append({
                "units": [u], "name": str(a["name"]),
                "category": a.get("category") if a.get("category") in CATEGORIES else "unknown",
                "description": str(a.get("description", "")),
                "identity": self.LEVELS.get(str(a.get("confidence", "")).lower(), 0.3),
                "grouping": None, "split_suggested": several and u.splittable,
                "group": "", "group_type": "none",
                "notes": "the local model sees several separate things here" if several else "",
                "labelled": True, "hints": guesses[n],
            })
        return assets, problems


def label_units(backend, rgba, bg, units, unit_px):
    """Run one labelling pass. Returns (assets, problems).

    assets: list of dicts {units: [Unit], name, category, description, identity, grouping,
    split_suggested, group, group_type, notes, labelled: bool}; every unit appears exactly once.
    """
    h, w = bg.shape
    chunks = make_chunks(units, w, h)
    requests = [build_request(rgba, bg, crop, part, unit_px, len(chunks), i) for i, (crop, part) in enumerate(chunks)]
    responses = backend.run(requests)
    assets, problems = [], []
    for i, ((crop, part), resp) in enumerate(zip(chunks, responses)):
        by_id = {u.id: u for u in part}
        used = set()
        if isinstance(resp, Exception):
            problems.append(f"crop {i + 1}: {resp}")
            resp = {"assets": []}
        for a in resp.get("assets", []):
            ids = [c for c in a.get("candidate_ids", []) if c in by_id and c not in used]
            dropped = [c for c in a.get("candidate_ids", []) if c not in ids]
            if dropped:
                problems.append(f"crop {i + 1}: '{a.get('name')}' referenced unknown or already-used candidates {dropped}")
            if not ids:
                continue
            used.update(ids)
            assets.append({
                "units": [by_id[c] for c in ids],
                "name": a.get("name") or "unnamed",
                "category": a.get("category") if a.get("category") in CATEGORIES else "unknown",
                "description": a.get("description", ""),
                "identity": LEVELS.get(a.get("identity_confidence"), 0.3),
                "grouping": LEVELS.get(a.get("grouping_confidence"), 0.3),
                "split_suggested": bool(a.get("split_suggested")),
                "group": a.get("group", "") if a.get("group_type", "none") != "none" else "",
                "group_type": a.get("group_type", "none"),
                "notes": a.get("notes", ""),
                "labelled": True,
            })
        for u in part:
            if u.id not in used:
                assets.append({"units": [u], "labelled": False})
    return assets, problems
