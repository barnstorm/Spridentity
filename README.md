# spridentity

spridentity finds each asset on a pixel-art sprite sheet. It gives the exact pixels of
each asset. With a vision model, it also gives each asset a name.

[GOAL.md](GOAL.md) gives the goal of the project. The
[wiki](https://github.com/barnstorm/Spridentity/wiki) gives the full documentation. The
`wiki/` folder contains the source of the wiki pages.

```bash
python -m spridentity sheet.png --extract
```

The command writes a folder `sheet.spridentity/` adjacent to the image:

| File | Contents |
|---|---|
| `assets.json` | The inventory. It has one entry for each asset, the groups and the analysis notes |
| `overlay.png` | The sheet with an outline and a number on each asset. A `?` shows an uncertain asset |
| `id_map.png` | A 16-bit image. Pixel value N is the Nth asset. Value 0 is the background |
| `assets/*.png` | With `--extract`: each asset alone on a transparent canvas |

## How it works

The tool finds the boundaries from the pixels only. A model gives the names. Thus a model
cannot move a boundary.

1. **Background.** The background is the transparent pixels or a colour key. The tool
   finds the colour key automatically. Use `--bg` to set it.
2. **Unit.** The unit is the tile size. Set it with `--unit 16` or `--unit 24x32`. If you
   do not set it, the tool calculates it when the sheet shows one. The unit is the size
   that an asset usually needs. It is not a set of cut lines, because many sheets follow a
   lattice only in some areas. The tool does a check of a given unit against the sheet.
   `analysis.unit.check` shows the result.
3. **Pieces.** If the art is 2 or 3 times its initial size (or more), the tool first
   decreases it to the initial size. Thus a sheet gives the same result at each scale.
   Then the tool divides the content into connected blobs. If a blob is in more than one
   cell, the tool divides it into pieces at the unit lines. These pieces are only possible
   cuts. Without a unit, the tool makes pieces at narrow necks.
4. **Candidates.** The pieces of one blob stay together unless the pixels show one of
   these conditions:
   - The blob becomes a narrow neck exactly on the unit line (two shapes that only touch).
   - An outline is along the two sides of the line, and the two sides have the same shape
     (a row of crates).
   - The two sides are full cells of different material.
   - A full cell is a picture on its own background colour (an icon sheet).

   If the pixels do not show one asset or two, the tool reports the pieces as one asset.
   It adds the flag "may be more than one asset". The tool also puts these items in one
   asset: separate specks, parts in the same cell, and small parts that together fit in
   one unit.
5. **Identification.** A vision model sees each candidate with an outline and a number. It
   gives the names. It joins candidates that make one asset (a roof, a wall and a door).
   It asks for a smaller cut when one candidate contains more than one object. It refers
   to candidates by number only, not by coordinates. Thus it cannot move a boundary.

Without step 5, the tool gives the boundaries, the masks, the duplicates and the groups of
similar assets. The assets have no names.

## Labelers

The `--labeler` option selects the model that gives the names.

### `--labeler ollama`

- This labeler uses a vision model on your computer through [Ollama](https://ollama.com).
  It is free. It does not need an account. No data goes out of the computer.
- Do `ollama pull minicpm-v` one time (approximately 5.5 GB). On recent Ollama versions,
  `--model qwen2.5vl:7b` is an alternative.
- Local models cannot put many numbered outlines into groups correctly. Thus the tool
  shows each candidate alone, and one time with the area around it. The model only gives
  a name. The pixel pass alone decides which pieces make one asset.
- On one town sheet, each of the two models gave a correct name to approximately two
  thirds of 56 candidates. The time was approximately 4 seconds for each candidate on an
  RTX 3080.
- The two models report high confidence for correct names and for incorrect names. Thus
  the tool limits the identity confidence to 0.6 and marks each name as not verified.

### `--hints clip`

- Use this option with `--labeler ollama`. A CLIP model gives a score to each word in a
  word list for each candidate.
- Install it with `pip install torch open_clip_torch`. The default model is approximately
  4 GB.
- The local model sees the best words. If CLIP has high confidence and the two models do
  not agree, the word from CLIP replaces the name.
- Each asset records the scores under `second_opinion`.
- On three test sheets, the correct names increased from 60% to 71%. Refer to
  [Naming evaluation](https://github.com/barnstorm/Spridentity/wiki/Naming-Evaluation).

### `--labeler anthropic`

- This labeler uses the Claude API. Install it with `pip install anthropic`.
- The credentials come from `ANTHROPIC_API_KEY` or from an `ant auth login` profile.
- The default model is `claude-opus-5-5`. Use `--model` to change it.
- The tool sends one request for each crop of approximately 40 candidates.
- The requests use the server-side refusal fallback of the API.

### `--labeler manual`

- The tool writes each request to `label_requests/`. A request has two images, a prompt,
  a system prompt and a JSON schema.
- On the subsequent run, the tool reads each `passN_NN_response.json` file in that folder.
- Use this labeler to do a test of a different model, or to give the answers yourself.

### `--labeler none` and `--labeler auto`

- `none` gives no names.
- `auto` is the default. It uses `anthropic` when credentials are available. If they are
  not available, it uses `none`.

## How to read `assets.json`

Each asset has these fields:

| Field | Meaning |
|---|---|
| `id`, `name`, `label` | The identifier and the name. The `name` is unique on the sheet |
| `category`, `description` | The type of the asset and a short text about it |
| `bbox` | The smallest box around the asset: `x, y, w, h` in sheet pixels |
| `unit_box` | When there is a unit: the box of full units that the asset needs. The minimum is one unit. `on_lattice` is true when the box is on cell lines |
| `grid` | The cells that the asset touches |
| `shape`, `mask.runs` | `rect` or `mask`. For a mask, `runs` gives rows as `[y, x, length]` |
| `parts` | The boxes of the pieces that are not connected |
| `relationships` | `touches`, `duplicate_of`, `similar_to`, `member_of` |
| `confidence.boundary`, `confidence.identity` | 0 to 1. `pixel_evidence` and `model_grouping` show the source of the boundary value |
| `uncertain` | True when one of the two confidence values is low |
| `uncertainty` | The reasons, as text. For example: "touches a0012 and may belong with it" |

`groups` contains the sets that the model found: animations, variants, terrain sets,
composites and kits. It also contains `similar_pixels` sets. The tool finds these when it
compares assets of the same size.

## Limits

- Different objects can touch along their full width. If the pixels do not show a
  difference, the tool reports them as one asset with a flag. The vision model can
  divide them, because the pieces on each side of the unit line stay as different
  candidates.
- The tool cannot calculate the unit reliably. On 173 sheets with a known tile size, the
  result was correct on 65 and incorrect on 37. On 71, the tool gave no result. Use
  `--unit` when you know the unit.
- An incorrect unit does not cut sprites. But it changes which full cells are tiles, and
  it changes the `unit_box` values.
- The unit check can find a unit that is too small or not aligned. It cannot find a unit
  that is a multiple of the correct size.
- The tool assumes that a lattice starts at pixel 0 and has no gutters. For sheets with
  gutters, the tool uses the background to divide the assets.
- On tiles that touch on all sides, it is not always clear which tiles make one terrain
  set. The pixel pass makes groups by material and adds a flag to weak joins. The model
  makes the final decision.
- If an object has a narrow part exactly on a unit line, the tool cuts the object there.
- The example output is not in this repository, because it contains art that other
  persons made. For those examples, one judge found that approximately 7 names in 10 were
  correct. Refer to
  [Judging with another model](https://github.com/barnstorm/Spridentity/wiki/Judging-With-Another-Model).

## Tests

```bash
python -m pytest -q
```
