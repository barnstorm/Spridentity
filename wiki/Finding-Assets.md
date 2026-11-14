# Finding assets

Where an asset is and what it is are decided separately. Boundaries come from the pixels
alone and are exact; a model only ever refers to a candidate by its number, so it cannot
move a boundary.

## 1. Background

Transparent pixels, or a colour key found automatically. `--bg` overrides.

## 2. Unit

The tile size, from `--unit 16` or `--unit 24x32`, or inferred when the sheet shows one.

The unit is the size an asset is expected to need. It is **not** a set of cut lines:
sheets are often only partly laid out on a lattice, and a lamp two tiles tall must not be
cut in half because it crosses a line. A stated unit is checked against the sheet and the
result is reported under `analysis.unit.check`.

## 3. Pieces

Art that was enlarged 2x, 3x and so on is first reduced to the size it was drawn at, so
the same sheet gives the same answer at every scale.

Content is then split into connected blobs. A blob that spans several cells is divided at
unit lines into pieces, but those pieces are only candidates for a cut. Without a unit,
pieces come from narrow necks in the blob.

## 4. Candidates

Pieces of one blob stay together unless the pixels show two things:

- the blob narrows to a neck exactly on the unit line (two shapes that merely touch);
- an outline runs along both sides of the line and the two sides are the same shape again
  (a row of crates);
- both sides are filled cells of different material, or a filled cell is a picture on its
  own backing colour (an icon sheet).

Pieces joined without positive evidence either way are reported as **one asset, flagged
"may be more than one asset"**. Detached specks, parts sharing a cell, and small parts
that together fit one unit are grouped.

## 5. Identification

See [Naming assets](Naming-Assets). Without it you still get boundaries, masks, duplicates
and look-alike groups; assets are just unnamed.

## Measured behaviour

On 199 sheets run with the unit given, comparing the earlier "cut at every unit line"
behaviour with the current one:

| | Before | Now |
|---|---|---|
| Same sheet at 1x, 2x and 3x gives the same asset count | 5 of 40 sets | 40 of 40 |
| Assets flagged uncertain | 5,509 of 19,269 | 2,894 of 19,058 |
| Icon sheets (icons drawn on filled cells) | 12 assets | 1,728 assets |

Some wrong joins remain (a plate with a banner, a counter with a cabinet); the intent is
that those are flagged rather than silently split. See [Limits](Limits).
