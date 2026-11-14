# Naming assets

The tool finds the assets first. Then a labeler gives the names. The labeler sees
candidates that already have exact outlines, and it answers with candidate numbers.

## Labelers (`--labeler`)

| Labeler | Function |
|---|---|
| `ollama` | A vision model on your computer through [Ollama](https://ollama.com). It is free and needs no account. No data goes out of the computer. The default model is `minicpm-v`. `--model qwen2.5vl:7b` is an alternative |
| `anthropic` | The Claude API. The tool sends one request for each crop of approximately 40 candidates. This labeler can also join candidates into one asset and ask for smaller cuts |
| `manual` | The tool writes each request to `label_requests/` and reads the answers from files. Use it for a different model, or to give the answers yourself |
| `none` | No names |
| `auto` | `anthropic` when credentials are available. If they are not available, `none` |

Local models cannot put many numbered outlines into groups correctly. Thus, with `ollama`,
the tool shows each candidate alone, and one time with the area around it. The model only
gives a name. The pixel pass alone decides which pieces make one asset.

Local models also report high confidence for correct names and for incorrect names. Thus,
without CLIP hints, the maximum identity confidence is 0.6.

## CLIP hints (`--hints clip`)

CLIP is a different type of model. It cannot write a name. It gives a score that shows how
well a picture agrees with each word in a list. This gives two things that the local
vision model does not have:

- A short list of possible names.
- A score that agrees with the results.

With `--labeler ollama --hints clip`, the tool does these steps:

1. The tool draws each candidate alone on three plain backgrounds. It makes the candidate
   larger and keeps the pixel edges sharp.
2. The CLIP model gives a score to each word in the vocabulary. The vocabulary has 317
   words. Use `--vocab` to give your own words.
3. The tool adds the five best words and their scores to the prompt of the local model.
   The local model can use them or ignore them.
4. The tool compares the name from the local model with the three best words from CLIP:

| Best score from CLIP | Name from the local model | Result |
|---|---|---|
| 0.6 or more | Agrees | The name stays. The identity confidence is 0.8 |
| Less than 0.6 | Agrees | The name stays. The identity confidence is 0.7 |
| 0.6 or more | Does not agree | **The best word from CLIP becomes the name.** The confidence is 0.6. A note records the name from the local model |
| Less than 0.6 | Does not agree | The name from the local model stays. The maximum confidence is 0.45 |

Each asset keeps all the scores under `second_opinion`. This field also shows which model
gave the name. Refer to [Output format](Output-Format).

The limits and the replacement rule come from the trial in
[Naming evaluation](Naming-Evaluation). We set them and measured them on the same three
sheets. Thus the results on other sheets will probably be less good.

### Vocabulary

CLIP can only give words that are in the list. For example, CLIP cannot give the name
"ironing board" unless the list contains it.

If you know the contents of a sheet, a short list of your own gives better results than
the general list:

```
chair, armchair, stool, table, desk, bed, bookshelf, rug, lamp, potted plant
```

### Models

`--hints-model` takes an open_clip model as `ARCH/PRETRAINED`.

| Model | Size | Notes |
|---|---|---|
| `ViT-H-14/laion2b_s32b_b79k` (default) | Approximately 4 GB | The better of the two models in the trial. It is slow without a GPU |
| `ViT-L-14/openai` | Approximately 1.7 GB | Not tested through this option. The trial used a different loader for this model. It was better on furniture and worse on characters. On characters, it frequently gives the name of the item in the hand ("shotgun" for a soldier) |

Other open_clip models will probably operate, but they are not tested.
