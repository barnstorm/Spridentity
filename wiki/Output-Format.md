# Output format

| File | Contents |
|---|---|
| `assets.json` | The inventory. It has one entry for each asset, the groups and the analysis notes |
| `overlay.png` | The sheet with an outline and a number on each asset. A `?` shows an uncertain asset |
| `id_map.png` | A 16-bit image. Pixel value N is the Nth asset. Value 0 is the background |
| `assets/*.png` | With `--extract`: each asset alone on a transparent canvas |

## `assets.json`

The top level has these fields: `schema_version`, `source` (file name, size, checksum),
`analysis`, `summary`, `assets`, `groups`.

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
    "vision_model_name": "grandfather_clock",
    "agrees_with_name": true,
    "name_from": "vision model"
  },
  "relationships": [{"type": "touches", "target": "a0030"}]
}
```

The numbers in this example are not from a real sheet.

| Field | Meaning |
|---|---|
| `id` | The identifier. It is stable in one run. `a0001` is pixel value 1 in `id_map.png` |
| `name` | The name. It is unique on the sheet (`chair`, `chair_2`). It is `null` when the asset has no name |
| `label` | The name without the counter. It is `null` when the asset has no name |
| `category` | One of: terrain, structure, vegetation, decoration, furniture, item, character, creature, vehicle, effect, ui, text, other, unknown |
| `bbox` | The smallest box around the asset, in sheet pixels |
| `unit_box` | When there is a unit: the box of full units that the asset needs. The minimum is one unit. `on_lattice` is true when the box is on cell lines. It is false when the tool put the box around a sprite that is not on the lattice |
| `grid` | The cells that the asset touches |
| `shape`, `mask` | `rect` is a full rectangle. For other shapes, `mask.runs` gives rows of pixels as `[y, x, length]` |
| `parts` | The boxes of the pieces, when the asset is not one connected blob |
| `confidence.boundary` | 0 to 1: the confidence in the outline. `pixel_evidence` and `model_grouping` show the source of the value |
| `confidence.identity` | 0 to 1: the confidence in the name |
| `uncertain` | True when the boundary confidence is less than 0.6, or when the name is not reliable |
| `uncertainty` | The reasons, as text |
| `second_opinion` | With `--hints clip`: the words from the CLIP model with their scores. `agrees_with_name` shows if the name from the vision model agrees with one of the three best words. `name_from` shows which model gave the name. Without `--hints clip`, the value is `null` |
| `relationships` | `touches`, `duplicate_of`, `similar_to`, `member_of` |

### Groups

`groups` contains the sets that the model found: animations, variants, terrain sets,
composites and kits. It also contains `similar_pixels` sets. The tool finds these when it
compares assets of the same size.

### Analysis

| Field | Contents |
|---|---|
| `analysis.unit` | The unit, its source (you or the tool), and a `check` that shows how well the sheet agrees with it |
| `analysis.pixel_scale` | The scale of the art. The value is 2 when each drawn pixel is 2 x 2 pixels on the sheet |
| `analysis.labeler` | The labeler, the model, the hints model and the problems |
| `analysis.notes` | The warnings about the full sheet |
