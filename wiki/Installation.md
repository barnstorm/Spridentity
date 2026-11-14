# Installation

spridentity needs Python 3.10 or newer.

```bash
pip install -e .
```

That installs the core: `numpy`, `scipy` and `pillow`. It is enough to find and outline
assets. Naming them needs one of the optional parts below.

## Local naming with Ollama (free, nothing leaves the machine)

1. Install [Ollama](https://ollama.com).
2. Pull a vision model once (about 5.5 GB):

```bash
ollama pull minicpm-v
```

`qwen2.5vl:7b` also works on recent Ollama versions (`--model qwen2.5vl:7b`).

## CLIP hints (optional second opinion on names)

```bash
pip install -e .[clip]
```

This adds `torch` and `open_clip_torch`. The default model, ViT-H/14 trained on LAION-2B,
is a download of about 4 GB the first time it is used, unless it is already in your
Hugging Face cache. A smaller model can be chosen with `--hints-model`; see
[Naming assets](Naming-Assets).

A working PyTorch install is required. If `python -c "import torch"` fails in your main
Python, use a separate virtual environment:

```bash
python -m venv .venv
```

```bash
.venv/Scripts/pip install -e .[clip]
```

(On Linux and macOS the path is `.venv/bin/pip`.)

### Using an NVIDIA GPU on Windows

On Windows, `pip install torch` gives the CPU-only build, which works but is slow with
the default model. For the GPU build, install PyTorch from its own index first, then the
rest:

```bash
.venv/Scripts/pip install torch --index-url https://download.pytorch.org/whl/cu126
```

```bash
.venv/Scripts/pip install -e .[clip]
```

Check it:

```bash
.venv/Scripts/python -c "import torch; print(torch.cuda.is_available())"
```

Then run the tool with that Python (`.venv/Scripts/python -m spridentity ...`). It uses
the GPU whenever PyTorch can see one; the log line `loading CLIP ... on cuda` confirms it.
Tested on Windows 11 with an RTX 3080 Laptop (16 GB), with Ollama's minicpm-v loaded at
the same time.

## Claude API naming

```bash
pip install -e .[label]
```

Credentials come from `ANTHROPIC_API_KEY` or an `ant auth login` profile.

## Tests

```bash
pip install -e .[dev]
```

```bash
python -m pytest -q
```
