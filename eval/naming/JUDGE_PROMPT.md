You are judging names that were given to pixel-art game sprites.

You have:

- **Page images** (`pages/<sheet>_<n>.png`). Each cell shows one sprite, enlarged with hard
  pixel edges, under its id (for example `a0012`). Pale blue is transparent background. Most
  sprites are 16 to 64 pixels across in the original, so they are small and stylised.
- **`names.csv`**. One row per sprite: `sheet`, `id`, `page` (the image it is on), `size`
  (original pixels), and five candidate names in columns `A` to `E`. Each letter is
  one naming method; the same letter is the same method on every row. You are not told which
  method is which.
- Optionally, **the sheet overlays** (`examples/<sheet>/overlay.png`): the whole sheet with
  every sprite outlined and numbered (`12` is `a0012`), to see a sprite among its neighbours
  when it is ambiguous alone.

For every row of `names.csv`:

1. Look at the sprite and decide for yourself what it depicts **before** reading the
   names. Write that in `what_it_is` in a few words ("wooden chair, front view").
2. If you cannot tell what it is, or it is a fragment of something, or it is several
   different things merged into one sprite, write `unclear` in `what_it_is` (you may add a
   reason after it) and leave `A` to `E` empty.
3. Otherwise mark each of `A` to `E`:
   - `yes`: a person looking for this sprite would accept the name. Synonyms and close
     kinds count ("sofa" for a couch, "dresser" for a chest of drawers). A generic but true
     name counts ("character" or "man" for a human figure; "tree" for a pine tree).
   - `partial`: related but imprecise or misleading. It names only a held or attached item
     ("shotgun" for a soldier holding one), the wrong member of the right family ("stool"
     for a chair, "sand" for dirt), or a much vaguer thing than the sprite ("brown square"
     for a table top).
   - `no`: a different thing ("suitcase" for a chair), or not a name for anything
     ("pixel art sprite").
   Ignore filler words such as "pixel", "sprite" or "tile" when the rest of the name is right
   ("pixel soldier" for a soldier is `yes`), and ignore spelling and underscores.

Judge each name on its own: several letters can be `yes` on the same row, or none.
Do not let one name change your reading of the sprite; if a name makes you realise what the
sprite is, that is fine, but then apply the same reading to all five.

Answer with a CSV with exactly these columns, one row per sprite, in the order of
`names.csv`, and nothing else:

```
sheet,id,what_it_is,A,B,C,D,E
furniture,a0001,nightstand with one drawer,yes,no,partial,yes,no
furniture,a0012,unclear: fragment of a table base,,,,,
```

Work through one page at a time and do not skip rows.
