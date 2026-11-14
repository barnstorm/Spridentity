# Judging with another model

The results on [Naming evaluation](Naming-Evaluation) come from one judge: Claude, which
also made the tool. This page tells you how to use a different judge (a model or a
person). The new judge gives its verdicts without the first verdicts. Then you compare the
two.

The judge must be able to read images. The work takes some minutes for each sheet. The
judge does not run code.

## Before you start

The page images (`eval/naming/pages/`) and the example output (`examples/`) are not in the
repository, because they contain art that other persons made. Thus you need a copy of the
project that has the `examples/` folder. Without that folder, you cannot do this
procedure.

## What to give to the judge

Give these items to the judge:

| File | Function |
|---|---|
| `eval/naming/JUDGE_PROMPT.md` | The instructions and the answer format |
| `eval/naming/names.csv` | One row for each sprite, with five names under the letters A to E |
| `eval/naming/pages/<sheet>_<n>.png` | The sprites at a larger size, each with its id |
| `examples/<sheet>/overlay.png` (optional) | The full sheet, for context |

Do not give these items to the judge:

| File | Reason |
|---|---|
| `eval/naming/key.json` | It shows the method for each letter |
| `eval/naming/methods.json` | It shows the same data |
| `eval/naming/verdicts_claude.csv` | It contains the answers of the first judge |
| The results page of the wiki | It gives the expected result |

If the judge is an agent that can read the repository, copy the four permitted items into
an empty folder. Then let the agent read only that folder.

## Procedure

### 1. Make the pack again (only if the examples changed)

```bash
python eval/naming/build_pack.py
```

### 2. Use the judge on one sheet at a time

Start a new conversation for each sheet. Thus the judge does not hold 265 rows at the same
time.

1. Paste the contents of `JUDGE_PROMPT.md`.
2. Attach the page images of that sheet:
   - `furniture_1.png` and `furniture_2.png`
   - `town_1.png` and `town_2.png`
   - `apocalypse_1.png` to `apocalypse_4.png`
3. Paste the rows of that sheet from `names.csv`. Include the header line.
4. Ask for the CSV.

The apocalypse sheet has 159 rows. For this sheet, it is safer to give one page at a time.
The `page` column of `names.csv` shows the image for each row.

### 3. Save the answers

1. Put the three replies into one file with only one header line:

```
eval/naming/verdicts_<model>.csv
```

2. Make sure that the file has 265 rows.
3. Make sure that the judge did not omit rows or add rows.

`score.py` ignores rows that it cannot read. Thus a file with missing rows gives a smaller
sample and no warning.

### 4. Compare the file with the first judge

```bash
python eval/naming/score.py eval/naming/verdicts_<model>.csv eval/naming/verdicts_claude.csv
```

For each judge, the script shows the number of correct names for each method and each
sheet. Then it shows how frequently the two judges gave the same verdict. This part uses
only the assets that have a verdict from each of the two judges.

## How to read the comparison

The two judges will not agree fully. There are two causes:

- The first judge used only `yes` and `no`. The prompt also gives `partial` to the new
  judge. `score.py` shows a strict number (`yes` only). In brackets, it shows a second
  number, where `partial` has the value of one half. Compare the numbers of the first
  judge with the two numbers.
- The first judge gave `unclear` to 73 assets. A new judge can use a different limit,
  which changes the sample. The last line of the output shows how many assets have a
  verdict from only one judge.

Look for the answers to these questions:

| Question | Where to look |
|---|---|
| Is the sequence of the methods the same? | The TOTAL row of each table. For the first judge, `combined` and `clip-vit-h14` are the best. `minicpm-v` and `clip-vit-l14` are the worst |
| Is the pattern on each sheet the same? | For the first judge, minicpm-v is the best on town, CLIP ViT-H/14 on apocalypse, and CLIP ViT-L/14 on furniture |
| Do the judges agree on each asset? | The agreement block. A value below approximately 80% for a method shows that the judges read the sprites or the rule differently. Then examine the rows |
| Did the first judge prefer its own method? | Compare the `combined` column of the two judges with the other columns. A decrease in `combined` only is the sign |

Change your opinion of the results if you see one of these:

- The new judge gives plain `minicpm-v` the same score as `combined`, or a better score.
- The two judges agree on fewer than approximately three rows in four.

## More tests

### A sheet that was not used to set the rule

This test is stronger, because the 0.6 limit and the replacement rule came from these
three sheets.

1. Run the tool on a new sheet without hints:

```bash
python -m spridentity new_sheet.png -o out/plain --unit 16 --labeler ollama --extract
```

2. Run the tool on the same sheet with hints:

```bash
python -m spridentity new_sheet.png -o out/combined --unit 16 --labeler ollama --hints clip --extract
```

3. Get the names of the methods. `out/plain/assets.json` gives the plain minicpm-v names.
   `out/combined/assets.json` gives the other names for each asset:
   - `second_opinion.vision_model_name` is the minicpm-v name with hints.
   - `second_opinion.guesses[0].name` is the word from CLIP ViT-H/14.
   - `name` is the combined result.
4. Add the sheet to `methods.json`. Use the same structure as the other entries.
5. Put the `assets/` folder of the sheet in `examples/<sheet>/`.
6. Make the pack again.

### A different labeler

You can also let a frontier model give the names, and not only the verdicts.

1. Run the tool with the `manual` labeler:

```bash
python -m spridentity sheet.png --unit 16 --labeler manual
```

2. Find the requests in `label_requests/`. Each request has two images, a prompt, a system
   prompt and a JSON schema.
3. Save the reply of the model as the related `passN_NN_response.json` file.
4. Do the command again.
5. Add the names to `methods.json` as one more method.

### Boundaries

This evaluation is about names only. It does not show that the outlines are correct. To
examine the outlines, look at `examples/<sheet>/overlay.png`. [Limits](Limits) gives the
known faults.
