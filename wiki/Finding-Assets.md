# Finding assets

The tool makes two different decisions: where an asset is, and what it is. The boundaries
come from the pixels only, and they are exact. A model refers to a candidate by its number
only. Thus a model cannot move a boundary.

## 1. Background

The background is the transparent pixels or a colour key. The tool finds the colour key
automatically. Use `--bg` to set it.

## 2. Unit

The unit is the tile size. Set it with `--unit 16` or `--unit 24x32`. If you do not set
it, the tool calculates it when the sheet shows one.

The unit is the size that an asset usually needs. It is **not** a set of cut lines. Many
sheets follow a lattice only in some areas. For example, a lamp that is two tiles high
goes across a unit line, and the tool must not cut it there.

The tool does a check of a given unit against the sheet. `analysis.unit.check` shows the
result.

## 3. Pieces

If the art is 2 or 3 times its initial size (or more), the tool first decreases it to the
initial size. Thus a sheet gives the same result at each scale.

Then the tool divides the content into connected blobs. If a blob is in more than one
cell, the tool divides it into pieces at the unit lines. These pieces are only possible
cuts. Without a unit, the tool makes pieces at narrow necks in the blob.

## 4. Candidates

The pieces of one blob stay together unless the pixels show one of these conditions:

- The blob becomes a narrow neck exactly on the unit line (two shapes that only touch).
- An outline is along the two sides of the line, and the two sides have the same shape
  (a row of crates).
- The two sides are full cells of different material.
- A full cell is a picture on its own background colour (an icon sheet).

If the pixels do not show one asset or two, the tool reports the pieces as **one asset**.
It adds the flag **"may be more than one asset"**.

The tool also puts these items in one asset:

- Separate specks.
- Parts in the same cell.
- Small parts that together fit in one unit.

## 5. Identification

Refer to [Naming assets](Naming-Assets). Without identification, the tool gives the
boundaries, the masks, the duplicates and the groups of similar assets. The assets have no
names.

## Measured results

The table compares two versions of the tool on 199 sheets with a given unit. The earlier
version made a cut at each unit line.

| Measurement | Earlier version | Current version |
|---|---|---|
| Sets where one sheet at 1x, 2x and 3x gives the same number of assets | 5 of 40 | 40 of 40 |
| Assets with an uncertain flag | 5,509 of 19,269 | 2,894 of 19,058 |
| Assets on icon sheets (icons on full cells) | 12 | 1,728 |

Some incorrect joins stay. Examples are a plate with a banner, and a counter with a
cabinet. The aim is a flag on these assets, not a cut that you cannot see. Refer to
[Limits](Limits).
