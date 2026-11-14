# spridentity

Finds the individual assets on a pixel-art sprite sheet, outlines them to the pixel, and
(with a vision model) names them. The goal is described in [GOAL.md](GOAL.md).
Fuller documentation is in the [wiki](wiki/Home.md).

```bash
python -m spridentity sheet.png --extract
```

This writes a folder `sheet.spridentity/` next to the image:

| File | What it is |
|---|---|
| `assets.json` | The inventory: one entry per asset, plus groups and analysis notes |
| `overlay.png` | The sheet with every asset outlined and numbered (`?` = flagged uncertain) |
| `id_map.png` | 16-bit image; pixel value N belongs to the Nth asset, 0 is background |
| `assets/*.png` | With `--extract`: each asset alone on a transparent canvas |

## How it works

Geometry and meaning are handled separately, so that boundaries are always exact.

1. **Background.** Transparent pixels, or a colour key found automatically (`--bg` overrides).
2. **Unit.** The tile size, from `--unit 16` / `--unit 24x32`, or inferred when the sheet
   shows one. It is the size an asset is expected to need, not a set of cut lines: sheets are
   often only partly laid out on a lattice. A stated unit is checked against the sheet and the
   result is reported under `analysis.unit.check`.
3. **Pieces.** Art that was enlarged 2x, 3x, ... is first reduced to the size it was drawn at,
   so the same sheet gives the same answer at every scale. Content is then split into
   connected blobs. A blob that spans several cells is divided at unit lines into pieces, but
   those pieces are only candidates for a cut (without a unit: pieces come from narrow necks).
4. **Candidates.** Pieces of one blob stay together unless the pixels show two things:
   - the blob narrows to a neck exactly on the unit line (two shapes that merely touch);
   - an outline runs along both sides of the line and the two sides are the same shape again
     (a row of crates);
   - both sides are filled cells of different material, or a filled cell is a picture on its
     own backing colour (an icon sheet).

   Pieces joined without positive evidence either way are reported as one asset and flagged
   "may be more than one asset". Detached specks, parts sharing a cell, and small parts that
   together fit one unit are grouped.
5. **Identification.** A vision model sees each candidate outlined and numbered. It names
   them, merges candidates that form one asset (roof + wall + door), and asks for a finer
   cut where one candidate holds several things. It only ever refers to candidates by
   number, never by coordinates, so it cannot move a boundary off the pixels.

Without step 5 you still get boundaries, masks, duplicates and look-alike groups; assets
are just unnamed.

## Identification backends

- `--labeler ollama` uses a vision model running on your own machine through
  [Ollama](https://ollama.com): free, no account, nothing leaves the computer. Run
  `ollama pull minicpm-v` once (about 5.5 GB); `--model qwen2.5vl:7b` is an alternative on
  recent Ollama versions. Local models are too weak to regroup dozens of numbered outlines,
  so each candidate is shown alone plus once in its surroundings, and only named; which
  pieces form one asset is decided by the pixel pass alone. On the example town sheet both
  models named roughly two thirds of 56 candidates correctly (about 4 s per candidate on an
  RTX 3080), and both report high confidence whether right or wrong, so identity confidence
  is capped at 0.6 and every name is marked as unverified.
- `--hints clip`, with `--labeler ollama`, adds a second opinion: a CLIP model ranks a word
  list for each candidate (`pip install torch open_clip_torch`; the default model is about
  4 GB). The local model sees the ranking, CLIP's word replaces the name when CLIP is
  confident and the two disagree, and each asset records the ranking under
  `second_opinion`. On three test sheets this took names judged correct from 60% to 71%;
  see [wiki/Naming-Evaluation.md](wiki/Naming-Evaluation.md).
- `--labeler anthropic` calls the Claude API (`pip install anthropic`, credentials via
  `ANTHROPIC_API_KEY` or an `ant auth login` profile). Default model `claude-opus-5-5`;
  change with `--model`. One request per crop of roughly 40 candidates. Requests opt in to
  the API's server-side refusal fallback.
- `--labeler manual` writes each request (two images, prompt, system prompt, JSON schema) to
  `label_requests/` and applies any `passN_NN_response.json` it finds there on the next
  run. Use it to try another model, or to answer by hand.
- `--labeler none` skips identification. `auto` (default) picks `anthropic` when
  credentials exist, otherwise `none`.

## Reading `assets.json`

Each asset has `id`, `name` (unique), `label`, `category`, `description`, `bbox`
(`x, y, w, h` in sheet pixels, tight), `unit_box` (when a unit is known: the box of whole
units the asset needs, never smaller than one unit; `on_lattice` says whether it lies on
cell lines or was fitted round a freely placed sprite), `grid` (cells it touches), `shape`
(`rect` or `mask`), `mask.runs` (`[y, x, length]` rows, omitted for plain rectangles),
`parts` (boxes of disconnected pieces), `relationships` (`touches`, `duplicate_of`,
`similar_to`, `member_of`) and:

- `confidence.boundary` and `confidence.identity`, 0 to 1. `pixel_evidence` and
  `model_grouping` show where the boundary figure came from.
- `uncertain`: true when either is low.
- `uncertainty`: the specific doubts, e.g. "touches a0012 and may belong with it", "touching
  pieces kept together because nothing in the pixels shows they are separate", "identification is a guess", or the model's own note.

`groups` collects animations, variant sets, terrain sets, composites and kits named by the
model, and `similar_pixels` sets found by comparing same-sized assets.

## Limits

- Different objects drawn touching at full width, with nothing in the pixels to tell them
  apart, are reported as one flagged asset. The vision model can still split them, because
  the pieces on each side of the unit line are kept as separate candidates.
- Unit inference is unreliable. On 173 sheets with a known tile size it was right on 65,
  wrong on 37 and declined to guess on 71. Pass `--unit` when you
  know it. A wrong unit no longer slices sprites, but it changes which filled cells count as
  tiles and what `unit_box` reports.
- The unit check can refute a unit that is too small or shifted, but not one that is a
  multiple of the true size.
- Lattices are assumed to start at pixel 0 with no gutters. Sheets with gutters work through
  background separation instead.
- On edge-to-edge tiles, which tiles form one terrain set is a judgement call. The pixel pass
  groups by material and flags weak joins; the model has the final say.
- An object with a narrow waist exactly on a unit line would be cut there.
- The files under `examples/` were made with `--unit 16 --labeler ollama --hints clip`
  (minicpm-v with CLIP ViT-H/14). About 7 names in 10 were judged correct, by one judge;
  [wiki/Judging-With-Another-Model.md](wiki/Judging-With-Another-Model.md) explains how to
  check that independently with the pack in `eval/naming/`.

## Tests

```bash
python -m pytest -q
```
