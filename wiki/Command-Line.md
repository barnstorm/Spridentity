# Command line

```bash
python -m spridentity sheet.png --unit 16 --labeler ollama --extract
```

The command writes a folder `sheet.spridentity/` adjacent to the image. Use `-o` to select
a different folder. [Output format](Output-Format) gives the contents of the folder.

## Options

| Option | Meaning |
|---|---|
| `-o`, `--out FOLDER` | The folder for the results |
| `--unit N` or `--unit WxH` | The tile size, for example `16` or `24x32`. It is the size that an asset usually needs. It is not a set of cut lines. If you do not give it, the tool calculates it, but not reliably. Give it when you know it |
| `--bg auto\|alpha\|none\|RRGGBB` | The background: automatic, transparent pixels only, none, or a colour key |
| `--min-bg-area N` | An enclosed area of the key colour that is smaller than N pixels stays in the asset. The default is 1/16 of a unit, or 16 pixels without a unit |
| `--labeler auto\|ollama\|anthropic\|manual\|none` | The labeler that gives the names. Refer to [Naming assets](Naming-Assets) |
| `--model NAME` | The model for the labeler. The defaults are `minicpm-v` for ollama and `claude-opus-5-5` for anthropic |
| `--ollama-host URL` | The address of the Ollama server. The default is `http://localhost:11434` |
| `--hints clip` | A CLIP model gives a score to each word in a word list for each asset. Use it with `--labeler ollama` |
| `--hints-model ARCH/PRETRAINED` | The open_clip model for the hints. The default is `ViT-H-14/laion2b_s32b_b79k` |
| `--vocab FILE` | Your word list for the hints. Put a comma or a new line between the words |
| `--extract` | The tool also writes each asset as a transparent PNG file |
| `--no-masks` | The JSON file does not contain the pixel masks. The id map continues to contain them |
| `--overlay-scale N` | The zoom of the overlay image |

## Examples

Outlines only, without names:

```bash
python -m spridentity sheet.png --unit 16 --labeler none
```

Local names with a second opinion from CLIP:

```bash
python -m spridentity sheet.png --unit 16 --labeler ollama --hints clip --extract
```

Your word list, for a sheet with contents that you know:

```bash
python -m spridentity sheet.png --unit 16 --labeler ollama --hints clip --vocab my_words.txt
```

Names from a different model, or from you:

```bash
python -m spridentity sheet.png --unit 16 --labeler manual
```

With the `manual` labeler, do these steps:

1. Do the command. The tool writes each request to `label_requests/`. A request has two
   images, a prompt, a system prompt and a JSON schema.
2. Put each answer in that folder as `passN_NN_response.json`.
3. Do the same command again.
