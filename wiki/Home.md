# spridentity

spridentity finds each asset on a pixel-art sprite sheet. It gives the exact pixels of
each asset, and it gives each asset a name. It does not need a game engine or a layout
rule. It can operate fully on your computer.

```bash
python -m spridentity sheet.png --unit 16 --labeler ollama --hints clip --extract
```

The result is a folder that contains these items:

- An inventory (`assets.json`). For each asset, it gives the name, the position, the
  exact pixels and the confidence.
- An overlay picture.
- An id map.
- Each asset as a PNG file.

## Pages

**How to use it**

- [Installation](Installation)
- [Command line](Command-Line)
- [Output format](Output-Format)

**How it works**

- [Finding assets](Finding-Assets): background, unit, pieces, candidates
- [Naming assets](Naming-Assets): local vision model, CLIP hints, other labelers
- [Limits](Limits)

**Evaluation**

- [Naming evaluation: results](Naming-Evaluation): five naming methods on 265 assets
- [Judging with another model](Judging-With-Another-Model): how to do an independent
  check of those results

## Status

| Subject | Status |
|---|---|
| Boundaries | Exact to the pixel. If the pixels do not show a difference between objects that touch, the tool reports one asset with a flag |
| Names, local model alone | Approximately 60% correct on three test sheets |
| Names, local model with CLIP | Approximately 71% correct on the same sheets. The confidence agrees with the results |
| Judge | One judge only: the model that made the tool |

## About this wiki

The source of these pages is the `wiki/` folder of the repository. Each page is one
Markdown file. `Home.md` is the front page. `_Sidebar.md` is the navigation.

The example output and the page images of the evaluation are not in the repository,
because they contain art that other persons made. To make them, use the tool on your own
sheets.
