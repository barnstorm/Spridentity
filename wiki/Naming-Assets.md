# Naming assets

Naming is separate from finding. Whatever names an asset is shown candidates that already
have exact outlines, and answers by candidate number.

## Labelers (`--labeler`)

| Labeler | What it does |
|---|---|
| `ollama` | A vision model on your own machine through [Ollama](https://ollama.com). Free, no account, nothing leaves the computer. Default model `minicpm-v`; `--model qwen2.5vl:7b` is an alternative |
| `anthropic` | The Claude API. One request per crop of roughly 40 candidates; it can also merge candidates into one asset and ask for finer cuts |
| `manual` | Writes each request to `label_requests/` and reads answers back from files. For any other model, or a person |
| `none` | No names |
| `auto` | `anthropic` when credentials exist, otherwise `none` |

Local models are too weak to regroup dozens of numbered outlines, so with `ollama` each
candidate is shown alone, plus once in its surroundings, and only named. Which pieces form
one asset is decided by the pixel pass alone.

Local models also report high confidence whether right or wrong, so on their own their
identity confidence is capped at 0.6.

## CLIP hints (`--hints clip`)

CLIP is a different kind of model: it cannot write a name, it scores how well a picture
matches each word in a list. That gives two things the local vision model lacks: a short
list of plausible names, and a score that means something.

With `--labeler ollama --hints clip`:

1. Every candidate is rendered alone, enlarged with hard pixel edges, on three plain
   backgrounds, and scored against the vocabulary (317 words built in, or your own with
   `--vocab`).
2. The top five words and their scores are added to the local model's prompt as guesses it
   may use or ignore.
3. The local model's name is compared with CLIP's top three words:

| CLIP's top score | Local model's name | Result |
|---|---|---|
| 0.6 or higher | matches | The name is kept; identity confidence 0.8 |
| below 0.6 | matches | The name is kept; identity confidence 0.7 |
| 0.6 or higher | does not match | **CLIP's top word becomes the name**; confidence 0.6; a note records what the local model called it |
| below 0.6 | does not match | The local model's name is kept; confidence at most 0.45 |

Every asset keeps the full ranking under `second_opinion`, including which model the name
came from. See [Output format](Output-Format).

The thresholds and the override rule come from the trial described in
[Naming evaluation](Naming-Evaluation). They were chosen on the same three sheets they
were measured on, so expect them to do somewhat worse elsewhere.

### Vocabulary

CLIP can only suggest words that are in the list. An ironing board can never be named
"ironing board" unless the list has it. If you know roughly what a sheet contains, a short
list of your own will beat the general one:

```
chair, armchair, stool, table, desk, bed, bookshelf, rug, lamp, potted plant
```

### Models

`--hints-model` takes an open_clip model as `ARCH/PRETRAINED`.

| Model | Size | Notes |
|---|---|---|
| `ViT-H-14/laion2b_s32b_b79k` (default) | about 4 GB | Best of the two tried; slow without a GPU |
| `ViT-L-14/openai` | about 1.7 GB | In the trial (run through a different loader, not through this option) it was better on furniture and worse on characters, where it tends to name the held item ("shotgun" for a soldier) |

Other open_clip models should work but have not been tried.
