"""Optional second opinion on names: a CLIP model ranks a word list against each candidate.

CLIP cannot write a name. It scores how well a picture matches each entry of a fixed
vocabulary, which gives two things the vision-language model lacks: a short list of
plausible names to choose from, and a number that says how sure the match is. The
ranking is passed to the local model as a hint and kept in the inventory.

Needs `torch` and `open_clip_torch` (pip install spridentity[clip]); nothing here is
imported unless hints are asked for.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

import numpy as np
from PIL import Image

DEFAULT_MODEL = "ViT-H-14/laion2b_s32b_b79k"
TEMPLATES = ["pixel art of a {}", "a pixel art sprite of a {}", "a {} in a 16-bit top-down RPG video game", "a {}"]
BACKGROUNDS = [(255, 255, 255), (128, 128, 128), (40, 40, 40)]
STRONG = 0.6  # a top score at or above this was right about four times in five in our trial
FILLER = {"pixel", "art", "sprite", "tile", "tiles", "block", "a", "of", "the", "wooden", "wood", "small", "large",
          "old", "red", "blue", "green", "brown", "purple", "yellow", "orange", "white", "black", "grey", "gray"}


def load_vocab(path=None):
    text = Path(path or Path(__file__).with_name("vocab.txt")).read_text(encoding="utf-8")
    words = [w.strip() for w in re.split(r"[,\n]", text) if w.strip() and not w.lstrip().startswith("#")]
    return list(dict.fromkeys(words))


def _tokens(text):
    return {t[:-1] if len(t) > 3 and t.endswith("s") else t
            for t in re.split(r"[^a-z0-9]+", text.lower()) if t and t not in FILLER}


def agrees(name, words):
    """Does a free-form name say the same thing as one of the vocabulary words?"""
    a = _tokens(name)
    for w in words:
        b = _tokens(w)
        if a and b and (a <= b or b <= a):
            return True
    return False


class ClipHinter:
    name = "clip"

    def __init__(self, model=DEFAULT_MODEL, vocab=None, top=5, device=None, log=lambda m: None):
        try:
            import open_clip
            import torch
        except ImportError as e:
            raise RuntimeError("CLIP hints need PyTorch and open_clip: pip install torch open_clip_torch") from e
        self.torch, self.model_name, self.top = torch, model, top
        arch, _, tag = model.partition("/")
        weights = tag or None
        cfg = open_clip.get_pretrained_cfg(arch, tag) if tag else None
        if cfg and cfg.get("hf_hub"):
            # reuse weights already in the Hugging Face cache, whichever file format they were saved in
            from huggingface_hub import try_to_load_from_cache
            for fn in ("open_clip_model.safetensors", "open_clip_pytorch_model.bin"):
                hit = try_to_load_from_cache(cfg["hf_hub"].rstrip("/"), fn)
                if isinstance(hit, str):
                    weights = hit
                    break
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        log(f"loading CLIP {model} on {self.device}...")
        self.clip = open_clip.create_model(arch, pretrained=weights).to(self.device).eval()
        self.tokenize = open_clip.get_tokenizer(arch)
        self.size = self.clip.visual.image_size
        self.size = self.size[0] if isinstance(self.size, (tuple, list)) else self.size
        self.mean = np.array(self.clip.visual.image_mean, np.float32)
        self.std = np.array(self.clip.visual.image_std, np.float32)
        self.vocab = load_vocab(vocab)
        self.text = self._text_vectors(log)

    def _text_vectors(self, log):
        torch = self.torch
        key = hashlib.sha1("\n".join([self.model_name] + TEMPLATES + self.vocab).encode()).hexdigest()[:16]
        cache = Path.home() / ".cache" / "spridentity" / f"clip_text_{key}.npy"
        if cache.exists():
            return torch.from_numpy(np.load(cache)).to(self.device)
        log(f"embedding {len(self.vocab)} vocabulary words (once per model and word list)...")
        rows = []
        with torch.no_grad():
            for w in self.vocab:
                f = self.clip.encode_text(self.tokenize([t.format(w) for t in TEMPLATES]).to(self.device))
                f = torch.nn.functional.normalize(f.float(), dim=-1).mean(0)
                rows.append(torch.nn.functional.normalize(f, dim=-1))
        tv = torch.stack(rows)
        try:
            cache.parent.mkdir(parents=True, exist_ok=True)
            np.save(cache, tv.cpu().numpy())
        except OSError:
            pass
        return tv

    def _render(self, rgba, mask, bgc):
        """The candidate alone, enlarged with hard pixel edges, centred on a plain square."""
        h, w = mask.shape
        px = np.dstack([rgba[..., :3], np.where(mask, 255, 0).astype(np.uint8)])
        im = Image.fromarray(px, "RGBA")
        k = max(1, int(self.size * 0.8) // max(w, h))
        im = im.resize((w * k, h * k), Image.NEAREST)
        if max(im.size) > self.size * 0.9:
            im.thumbnail((int(self.size * 0.9),) * 2, Image.NEAREST)
        canvas = Image.new("RGBA", (self.size, self.size), bgc + (255,))
        canvas.alpha_composite(im, ((self.size - im.width) // 2, (self.size - im.height) // 2))
        return (np.asarray(canvas.convert("RGB"), np.float32) / 255 - self.mean) / self.std

    def suggest(self, sprites, batch=16):
        """sprites: list of (rgba crop HxWx4, mask HxW). Returns one [(word, score), ...] list each,
        best first; scores are a softmax over the vocabulary, so they sum to 1 across it."""
        torch = self.torch
        acc = 0
        with torch.no_grad():
            for bgc in BACKGROUNDS:
                feats = []
                for i in range(0, len(sprites), batch):
                    x = np.stack([self._render(c, m, bgc) for c, m in sprites[i:i + batch]])
                    f = self.clip.encode_image(torch.from_numpy(x).permute(0, 3, 1, 2).to(self.device))
                    feats.append(torch.nn.functional.normalize(f.float(), dim=-1))
                acc = acc + torch.cat(feats)
            prob = (torch.nn.functional.normalize(acc, dim=-1) @ self.text.T * 100).softmax(-1).cpu().numpy()
        out = []
        for p in prob:
            order = np.argsort(-p)[:self.top]
            out.append([(self.vocab[j], round(float(p[j]), 2)) for j in order])
        return out
