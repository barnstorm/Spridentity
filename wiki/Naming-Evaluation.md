# Naming evaluation: results

**Status: one judge, three sheets.** Claude gave each verdict on this page. Claude also
wrote the code. It looked at each sprite and made a decision. There was no independent
check. [Judging with another model](Judging-With-Another-Model) tells you how to do one.

## The methods

The evaluation compares five methods that give names to the same 265 assets. spridentity
cut the assets with `--unit 16` from three sheets of 16-pixel art:

- House furniture (52 assets).
- A town tile set (54 assets).
- A post-apocalypse sheet with characters, vehicles and terrain (159 assets).

| Method | Description |
|---|---|
| `minicpm-v` | The local vision model alone (`--labeler ollama`) |
| `clip-vit-l14` | The best word from OpenAI CLIP ViT-L/14 in the 317-word vocabulary |
| `clip-vit-h14` | The best word from LAION CLIP ViT-H/14 in the same vocabulary |
| `minicpm-v+clip-hints` | minicpm-v with the five best words from ViT-H/14 in its prompt |
| `combined` | The same as `minicpm-v+clip-hints`, with one rule. If the best word from ViT-H/14 has a score of 0.6 or more and minicpm-v does not agree, that word replaces the name. This is the current function of `--labeler ollama --hints clip` |

## Results

The table shows the number of correct names. The judge did not include 73 of the 265
assets. For these assets, the judge was not able to identify the object, or the asset was a
fragment, or it contained more than one object.

| Sheet | Assets with a verdict | minicpm-v | CLIP ViT-L/14 | CLIP ViT-H/14 | minicpm-v + hints | combined |
|---|---|---|---|---|---|---|
| furniture | 44 | 22 | **30** | 26 | 23 | 28 |
| town | 47 | **36** | 29 | 29 | 34 | 32 |
| apocalypse | 101 | 58 | 52 | **77** | 62 | **77** |
| **Total** | 192 | 116 (60%) | 111 (58%) | 132 (69%) | 119 (62%) | **137 (71%)** |

A minimum of one method was correct on 176 of 192 assets (92%).

## What the numbers show

- **No model is the best on all sheets.**
  - minicpm-v is the best on terrain tiles. There, CLIP gave "keyboard" for stone walls
    and "blanket" for water.
  - CLIP ViT-H/14 is the best on characters. There, minicpm-v gave names such as "pixel
    hoodie" and "pixel bulldozer".
  - CLIP ViT-L/14 is the best on furniture.
- **Hints alone help only a small quantity.** With the CLIP words, minicpm-v went from
  116 to 119. It usually kept its own answer.
- **The replacement rule gives most of the increase.** In 39 cases, ViT-H/14 had a score
  of 0.6 or more and minicpm-v did not agree. CLIP was correct in 28 of them and minicpm-v
  in 10.
- **The combined method is only a small quantity better than CLIP ViT-H/14 alone** (137
  and 132). It adds a description, a category, and names that are not in the vocabulary.

## Does the confidence agree with the results?

The table shows the combined method, by the `confidence.identity` value that it reports.

| Identity confidence | Cause | Assets with a verdict | Correct |
|---|---|---|---|
| 0.8 | The two models agree. The CLIP score is 0.6 or more | 48 | 39 (81%) |
| 0.7 | The two models agree. The CLIP score is less than 0.6 | 50 | 43 (86%) |
| 0.6 | CLIP gave the name. minicpm-v did not agree | 39 | 28 (72%) |
| 0.45 | The two models do not agree. The CLIP score is less than 0.6 | 55 | 27 (49%) |

Thus agreement between the models is a good sign (82 of 98 correct). In the lowest band,
only half of the names are correct. This data does not show a difference between the 0.8
band and the 0.7 band.

## Why you must be careful with these numbers

- **One judge, not blind.** The judge saw each sprite together with the names. The judge
  knew which method gave each name.
- **Verdicts were yes or no only.** There was no written rule. The judge accepted words
  with almost the same meaning ("dresser" for a chest of drawers, "sand" for dirt). The
  judge did not accept words that were only near ("stool" for a chair).
- **The rule came from the test sheets.** The 0.6 limit and the replacement rule came
  from these same three sheets. A fourth sheet is the true test.
- **The judge did not examine the `combined` names again.** Each `combined` name was the
  same as a name from one of the other methods. Thus it got the verdict of that name.
- **The judge wrote the vocabulary.** The vocabulary is general. The judge wrote it after
  the furniture sheet, and before the town sheet and the apocalypse sheet.
- **There are only three sheets, and all are 16-pixel art.** The numbers do not apply to
  larger sprites, other styles or icon sheets.
- **Boundary errors are in the data.** The judge was not able to give a verdict on a quarter of
  the assets. The primary cause was the result of the cut stage.

## Files

All the data for this page is in `eval/naming/`:

| File | Contents |
|---|---|
| `methods.json` | The name that each method gave to each asset |
| `names.csv` | The same names, with the letters A to E in the place of the method names |
| `key.json` | The method for each letter |
| `verdicts_claude.csv` | The verdicts that this page summarizes |
| `pages/*.png` | The sprites with their numbers. These files are not in the repository. Refer to [Judging with another model](Judging-With-Another-Model) |
| `score.py` | The script that makes the tables |

```bash
python eval/naming/score.py eval/naming/verdicts_claude.csv
```
