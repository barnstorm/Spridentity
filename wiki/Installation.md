# Installation

spridentity needs Python 3.10 or a later version.

```bash
pip install -e .
```

This command installs the core: `numpy`, `scipy` and `pillow`. The core is sufficient to
find the assets and their outlines. To give names to the assets, install one of the
optional parts below.

## Local names with Ollama

This part is free. No data goes out of the computer.

1. Install [Ollama](https://ollama.com).
2. Download a vision model one time (approximately 5.5 GB):

```bash
ollama pull minicpm-v
```

On recent Ollama versions, `qwen2.5vl:7b` is an alternative (`--model qwen2.5vl:7b`).

## CLIP hints

This part is optional. It gives a second opinion on the names.

```bash
pip install -e .[clip]
```

This command adds `torch` and `open_clip_torch`.

The default model is ViT-H/14 (LAION-2B). The first use downloads approximately 4 GB,
unless the model is already in your Hugging Face cache. Use `--hints-model` to select a
smaller model. Refer to [Naming assets](Naming-Assets).

### If PyTorch does not operate in your Python

CLIP hints need a PyTorch installation that operates correctly. If
`python -c "import torch"` gives an error, use a virtual environment.

1. Make the virtual environment:

```bash
python -m venv .venv
```

2. Install the tool into it:

```bash
.venv/Scripts/pip install -e .[clip]
```

On Linux and macOS, the path is `.venv/bin/pip`.

### How to use an NVIDIA GPU on Windows

On Windows, `pip install torch` installs the CPU version. The CPU version operates
correctly, but it is slow with the default model.

1. Install the GPU version of PyTorch from the PyTorch index:

```bash
.venv/Scripts/pip install torch --index-url https://download.pytorch.org/whl/cu126
```

2. Install the tool:

```bash
.venv/Scripts/pip install -e .[clip]
```

3. Make sure that PyTorch finds the GPU. The command must show `True`:

```bash
.venv/Scripts/python -c "import torch; print(torch.cuda.is_available())"
```

4. Use that Python to start the tool (`.venv/Scripts/python -m spridentity ...`).

The tool uses the GPU when PyTorch finds one. The log line `loading CLIP ... on cuda`
shows that the GPU is in use.

We did a test of this procedure on Windows 11 with an RTX 3080 Laptop GPU (16 GB). The
minicpm-v model of Ollama was in the GPU memory at the same time.

## Names from the Claude API

```bash
pip install -e .[label]
```

The credentials come from `ANTHROPIC_API_KEY` or from an `ant auth login` profile.

## Tests

1. Install the test tools:

```bash
pip install -e .[dev]
```

2. Do the tests:

```bash
python -m pytest -q
```
