# Judging with another model

The results on [Naming evaluation](Naming-Evaluation) rest on one judge: Claude, which
also built the tool. This page is how to have a different model (or a person) redo the
judging without seeing those verdicts, and compare.

You need a model that can read images and a few minutes per sheet. No code runs on the
judge's side.

## What the judge gets, and what it must not get

Give it:

| File | Why |
|---|---|
| `eval/naming/JUDGE_PROMPT.md` | The instructions and the answer format |
| `eval/naming/names.csv` | One row per sprite with five candidate names under letters A to E |
| `eval/naming/pages/<sheet>_<n>.png` | The sprites, enlarged, each under its id |
| `examples/<sheet>/overlay.png` (optional) | The whole sheet, for context |

Keep back:

| File | Why |
|---|---|
| `eval/naming/key.json` | Says which letter is which method |
| `eval/naming/methods.json` | The same information |
| `eval/naming/verdicts_claude.csv` | The first judge's answers |
| The wiki's results page | States the expected outcome |

If the judge is an agent with access to the repository, copy the four allowed items into
an empty folder and point it there instead.

## Steps

### 1. Rebuild the pack (only if the examples changed)

```bash
python eval/naming/build_pack.py
```

### 2. Run the judge, one sheet at a time

Start a new conversation for each sheet, so the judge is not carrying 265 rows at once.

1. Paste the contents of `JUDGE_PROMPT.md`.
2. Attach that sheet's page images: `furniture_1.png` and `furniture_2.png`; `town_1.png`
   and `town_2.png`; `apocalypse_1.png` to `apocalypse_4.png`.
3. Paste that sheet's rows of `names.csv`, including the header line.
4. Ask for the CSV.

For the apocalypse sheet (159 rows) it is safer to go page by page: the `page` column of
`names.csv` says which rows belong to which image.

### 3. Save the answers

Join the three replies into one file, with a single header line:

```
eval/naming/verdicts_<model>.csv
```

Check that it has 265 rows and that no row was skipped or invented. `score.py` ignores
rows it cannot read, so a short file gives a quietly smaller sample.

### 4. Score it against the first judge

```bash
python eval/naming/score.py eval/naming/verdicts_<model>.csv eval/naming/verdicts_claude.csv
```

This prints, for each judge, how many names each method got right per sheet, and then how
often the two judges made the same call on the assets both of them judged.

## Reading the comparison

The two judges will not match exactly, and should not be expected to:

- The first judge used only `yes` and `no`. The prompt gives the new judge `partial` as
  well. `score.py` prints a strict count (`yes` only) and, in brackets, a lenient one
  (`partial` counts half). Compare the first judge's numbers with both.
- The first judge marked 73 assets `unclear`. A new judge may set that line elsewhere,
  which changes the sample. The last line of the output says how many assets only one
  judge scored.

What to look for:

| Question | Where to look |
|---|---|
| Is the ranking of methods the same? | The TOTAL row of each table. The first judge has `combined` and `clip-vit-h14` on top, `minicpm-v` and `clip-vit-l14` at the bottom |
| Is the per-sheet pattern the same? | minicpm-v best on town, CLIP ViT-H/14 best on apocalypse, CLIP ViT-L/14 best on furniture |
| Do the judges agree asset by asset? | The agreement block. Below about 80% on a method means the two are reading the sprites or the rule differently, and the individual rows are worth a look |
| Was the first judge too generous to its own build? | Compare the `combined` column between judges with the others. A drop that only `combined` shows would be the sign |

A result that should change your mind: the new judge puts plain `minicpm-v` level with or
ahead of `combined`, or agrees with the first judge on fewer than about three rows in four.

## Going further

**A sheet nobody tuned on.** This is the stronger test, because the 0.6 threshold and the
override rule were chosen on these three sheets. Run a new sheet both ways:

```bash
python -m spridentity new_sheet.png -o out/plain --unit 16 --labeler ollama --extract
```

```bash
python -m spridentity new_sheet.png -o out/combined --unit 16 --labeler ollama --hints clip --extract
```

`out/combined/assets.json` holds everything needed for all the methods: each asset's
`second_opinion.vision_model_name` is the hinted minicpm-v name, `guesses[0].name` is CLIP
ViT-H/14's pick, and `name` is the combined result. Add the sheet to `methods.json` in the
same shape as the existing entries, put its `assets/` folder under `examples/<sheet>/`,
and rebuild the pack.

**A different labeler altogether.** To see how a frontier model names the sprites itself,
rather than judging names:

```bash
python -m spridentity sheet.png --unit 16 --labeler manual
```

Each request lands in `label_requests/` as two images, a prompt, a system prompt and a
JSON schema. Save the model's reply as the matching `passN_NN_response.json` and run the
command again. Its names can then be added to `methods.json` as one more method.

**Boundaries.** This evaluation is about names only. Whether the outlines are right is a
separate question; `examples/<sheet>/overlay.png` is the picture to judge that from, and
the known faults are listed under [Limits](Limits).
