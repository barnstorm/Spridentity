# spridentity

Finds the individual assets on a pixel-art sprite sheet, outlines them to the pixel, and
names them. It does not depend on any engine or layout convention, and it can run entirely
on your own machine.

```bash
python -m spridentity sheet.png --unit 16 --labeler ollama --hints clip --extract
```

The result is a folder with an inventory (`assets.json`: what each asset is, where it is,
its exact pixels, and how sure the tool is), an overlay picture, an id map, and each asset
as its own PNG.

## Pages

**Using it**

- [Installation](Installation)
- [Command line](Command-Line)
- [Output format](Output-Format)

**How it works**

- [Finding assets](Finding-Assets): background, unit, pieces, candidates
- [Naming assets](Naming-Assets): local vision model, CLIP hints, other labelers
- [Limits](Limits)

**Evaluation**

- [Naming evaluation: results](Naming-Evaluation): five naming methods on 265 assets
- [Judging with another model](Judging-With-Another-Model): how to check those results
  independently

## Where things stand

| | |
|---|---|
| Boundaries | Exact to the pixel. Touching objects that the pixels cannot tell apart are reported as one flagged asset |
| Names, local model alone | About 60% judged correct on three test sheets |
| Names, local model with CLIP | About 71% on the same sheets, with a confidence that tracks correctness |
| Checked by | One judge so far, the same model that built the tool |

## About this wiki

These pages live in the `wiki/` folder of the repository and follow GitHub wiki
conventions: one Markdown file per page, `Home.md` as the front page, `_Sidebar.md` as the
navigation. To publish them, push the folder's contents to the repository's wiki
(`<repository>.wiki.git`).
