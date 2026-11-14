# Command line

```bash
python -m spridentity sheet.png --unit 16 --labeler ollama --extract
```

This writes a folder `sheet.spridentity/` next to the image (or the folder given with `-o`).
What is in it is described in [Output format](Output-Format).

## Options

| Option | Meaning |
|---|---|
| `-o`, `--out FOLDER` | Where to write the results |
| `--unit N` or `--unit WxH` | The tile size, e.g. `16` or `24x32`. It is the size an asset is expected to need, not a set of cut lines. Inferred when omitted, but inference is unreliable: pass it when you know it |
| `--bg auto\|alpha\|none\|RRGGBB` | Background: found automatically, transparency only, none, or a colour key |
| `--min-bg-area N` | Enclosed patches of the key colour smaller than this stay part of the asset (default: 1/16 of a unit, or 16 pixels without a unit) |
| `--labeler auto\|ollama\|anthropic\|manual\|none` | Who names the assets. See [Naming assets](Naming-Assets) |
| `--model NAME` | Model for the labeler (`minicpm-v` for ollama, `claude-opus-5-5` for anthropic) |
| `--ollama-host URL` | Ollama server address (default `http://localhost:11434`) |
| `--hints clip` | A CLIP model ranks a word list for each asset; used with `--labeler ollama` |
| `--hints-model ARCH/PRETRAINED` | open_clip model for the hints (default `ViT-H-14/laion2b_s32b_b79k`) |
| `--vocab FILE` | Your own word list for the hints, separated by commas or new lines |
| `--extract` | Also write each asset as its own transparent PNG |
| `--no-masks` | Leave per-pixel masks out of the JSON (the id map still has them) |
| `--overlay-scale N` | Zoom of the overlay image |

## Typical runs

Outlines only, no naming:

```bash
python -m spridentity sheet.png --unit 16 --labeler none
```

Local naming with a second opinion from CLIP:

```bash
python -m spridentity sheet.png --unit 16 --labeler ollama --hints clip --extract
```

Your own vocabulary, for a sheet whose contents you roughly know:

```bash
python -m spridentity sheet.png --unit 16 --labeler ollama --hints clip --vocab my_words.txt
```

Hand the naming to any other model, or do it yourself:

```bash
python -m spridentity sheet.png --unit 16 --labeler manual
```

That writes each request (two images, a prompt, the system prompt and a JSON schema) to
`label_requests/`. Put the answers there as `passN_NN_response.json` and run the same
command again.
