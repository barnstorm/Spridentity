# Output format

| File | What it is |
|---|---|
| `assets.json` | The inventory: one entry per asset, plus groups and analysis notes |
| `overlay.png` | The sheet with every asset outlined and numbered (`?` = flagged uncertain) |
| `id_map.png` | 16-bit image; pixel value N belongs to the Nth asset, 0 is background |
| `assets/*.png` | With `--extract`: each asset alone on a transparent canvas |

## `assets.json`

Top level: `schema_version`, `source` (file name, size, checksum), `analysis`, `summary`,
`assets`, `groups`.

### One asset

```json
{
  "id": "a0029",
  "name": "grandfather_clock",
  "label": "grandfather_clock",
  "category": "furniture",
  "description": "A tall wooden clock with a pendulum.",
  "bbox": {"x": 64, "y": 96, "w": 21, "h": 46},
  "unit_box": {"x": 64, "y": 96, "w": 32, "h": 48, "on_lattice": true},
  "grid": {"col": 4, "row": 6, "cols": 2, "rows": 3, "aligned": false},
  "shape": "mask",
  "pixel_count": 702,
  "parts": [],
  "mask": {"encoding": "row_runs", "runs": [[96, 70, 9], [97, 68, 13]]},
  "confidence": {"boundary": 0.85, "identity": 0.8, "pixel_evidence": 0.85, "model_grouping": null},
  "uncertain": false,
  "uncertainty": [],
  "second_opinion": {
    "model": "ViT-H-14/laion2b_s32b_b79k",
    "guesses": [{"name": "grandfather clock", "score": 0.99}, {"name": "wall clock", "score": 0.01}],
    "agrees_with_name": true
  },
  "relationships": [{"type": "touches", "target": "a0030"}]
}
```

(The numbers above are illustrative.)

| Field | Meaning |
|---|---|
| `id` | Stable within one run: `a0001` is pixel value 1 in `id_map.png` |
| `name` | Unique on the sheet (`chair`, `chair_2`, ...). `label` is the same without the counter. Both are `null` when nothing named the asset |
| `category` | One of terrain, structure, vegetation, decoration, furniture, item, character, creature, vehicle, effect, ui, text, other, unknown |
| `bbox` | Tight box in sheet pixels |
| `unit_box` | When a unit is known: the box of whole units the asset needs, never smaller than one unit. `on_lattice` is true when it lies on cell lines, false when it was fitted round a freely placed sprite |
| `grid` | The cells the asset touches |
| `shape`, `mask` | `rect` for a filled rectangle; otherwise `mask.runs` lists `[y, x, length]` rows of pixels |
| `parts` | Boxes of the separate pieces, when the asset is not one connected blob |
| `confidence.boundary` | 0 to 1: how sure the outline is. `pixel_evidence` and `model_grouping` show where it came from |
| `confidence.identity` | 0 to 1: how sure the name is |
| `uncertain` | True when the boundary confidence is below 0.6 or the identity is a guess |
| `uncertainty` | The specific doubts, in words |
| `second_opinion` | With `--hints clip`: the classifier's ranked guesses and whether the chosen name matches one of the top three. `null` otherwise |
| `relationships` | `touches`, `duplicate_of`, `similar_to`, `member_of` |

### Groups

`groups` collects animations, variant sets, terrain sets, composites and kits named by the
model, and `similar_pixels` sets found by comparing same-sized assets.

### Analysis

`analysis.unit` records the unit used, whether it was given or inferred, and a `check` of
how well the sheet fits it. `analysis.pixel_scale` is the enlargement factor found (2 for
art drawn at half size). `analysis.labeler` names the backend, the model, the hints model
and any problems. `analysis.notes` holds warnings about the sheet as a whole.
