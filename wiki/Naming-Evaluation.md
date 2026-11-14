# Naming evaluation: results

**Status: one judge, three sheets.** Every verdict on this page was made by Claude, the
model that also wrote the code, looking at the sprites by eye. It has not been checked
independently. [Judging with another model](Judging-With-Another-Model) explains how to
check it.

## What was compared

Five ways of naming the same 265 assets, cut by spridentity with `--unit 16` from three
16-pixel sheets: house furniture (52 assets), a town tileset (54) and a post-apocalypse
sheet of characters, vehicles and terrain (159).

| Method | What it is |
|---|---|
| `minicpm-v` | The local vision model alone (`--labeler ollama`) |
| `clip-vit-l14` | The top word from OpenAI CLIP ViT-L/14 over the 317-word built-in list |
| `clip-vit-h14` | The top word from LAION CLIP ViT-H/14 over the same list |
| `minicpm-v+clip-hints` | minicpm-v with ViT-H/14's top five words added to its prompt |
| `combined` | The previous method, but ViT-H/14's top word replaces the name when it scores 0.6 or more and minicpm-v disagrees. This is what `--labeler ollama --hints clip` does now |

## Result

Names judged correct. 73 of the 265 assets were left out because the judge could not
tell what they were, or they were fragments or several things merged.

| Sheet | Judged | minicpm-v | CLIP ViT-L/14 | CLIP ViT-H/14 | minicpm-v + hints | combined |
|---|---|---|---|---|---|---|
| furniture | 44 | 22 | **30** | 26 | 23 | 28 |
| town | 47 | **36** | 29 | 29 | 34 | 32 |
| apocalypse | 101 | 58 | 52 | **77** | 62 | **77** |
| **Total** | 192 | 116 (60%) | 111 (58%) | 132 (69%) | 119 (62%) | **137 (71%)** |

At least one of the five was right on 176 of 192 (92%).

## What the numbers say

- **No single model wins everywhere.** minicpm-v is best on terrain tiles, where CLIP
  called stone walls "keyboard" and water "blanket". CLIP ViT-H/14 is best on characters,
  where minicpm-v produced names like "pixel hoodie" and "pixel bulldozer". CLIP ViT-L/14
  is best on furniture.
- **Hints alone barely help.** Giving minicpm-v the CLIP guesses moved it from 116 to 119.
  It mostly kept its own answer.
- **The override rule is where the gain comes from.** In the 39 judged cases where ViT-H/14
  scored 0.6 or more and minicpm-v disagreed, CLIP was right 28 times and minicpm-v 10.
- **The combined method is only slightly ahead of CLIP ViT-H/14 alone** (137 against 132).
  What it adds over plain CLIP is a written description, a category, and free-form names
  for things outside the word list.

## Does the confidence mean anything?

For the combined method, by the `confidence.identity` it reports:

| Identity confidence | How it arises | Judged | Right |
|---|---|---|---|
| 0.8 | Both agree, CLIP score 0.6 or more | 48 | 39 (81%) |
| 0.7 | Both agree, CLIP score below 0.6 | 50 | 43 (86%) |
| 0.6 | Named by CLIP over minicpm-v's objection | 39 | 28 (72%) |
| 0.45 | They disagree and CLIP is unsure | 55 | 27 (49%) |

So agreement is a real signal (82 of 98 right), and the lowest band is a coin toss. The
0.8 and 0.7 bands are not distinguishable on this data.

## Why to be careful with these numbers

- **One judge, not blind.** The judge saw each sprite with the names beside it and knew
  which method was which.
- **Yes or no only.** Near-synonyms were accepted ("dresser" for a chest of drawers, "sand"
  for dirt) and near misses rejected ("stool" for a chair), by feel rather than by a
  written rule.
- **Tuned on the test set.** The 0.6 threshold and the override rule were chosen after
  looking at these same three sheets. A fourth sheet is the real test.
- **The word list was general but written by the judge**, before the town and apocalypse
  sheets were looked at and after the furniture sheet.
- **Three sheets, all 16-pixel art.** Nothing here says how the methods do on larger
  sprites, other styles or icon sheets.
- **Boundary mistakes are mixed in.** A quarter of the assets could not be judged at all,
  mostly because of what the cutting stage produced.

## Files

Everything behind this page is in `eval/naming/`:

| File | Contents |
|---|---|
| `methods.json` | The name each method gave each asset |
| `names.csv` | The same, with methods hidden behind letters A to E |
| `key.json` | Which letter is which method |
| `verdicts_claude.csv` | The verdicts summarised above |
| `pages/*.png` | The sprites, numbered |
| `score.py` | Produces the tables |

```bash
python eval/naming/score.py eval/naming/verdicts_claude.csv
```
