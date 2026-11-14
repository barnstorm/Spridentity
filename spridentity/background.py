"""Decide which pixels are background (not part of any asset)."""
from __future__ import annotations

import numpy as np
from scipy import ndimage as ndi

S4 = ndi.generate_binary_structure(2, 1)


def _border_mask(shape):
    m = np.zeros(shape, bool)
    m[0, :] = m[-1, :] = m[:, 0] = m[:, -1] = True
    return m


def detect_background(rgba: np.ndarray, spec="auto", min_area: int = 16):
    """Return (bg_mask, info).

    spec: "auto", "alpha", "none", or an (r, g, b) colour key.
    A colour-keyed region only counts as background when it reaches the image
    border or is at least `min_area` pixels; smaller enclosed patches of the key
    colour (highlights, eye glints) stay with the asset that surrounds them.
    """
    h, w = rgba.shape[:2]
    alpha = rgba[..., 3]
    notes = []

    if spec == "none":
        return np.zeros((h, w), bool), {"mode": "none", "color": None, "confidence": 1.0, "notes": ["set by user"]}

    transparent = alpha == 0
    if spec == "alpha" or (spec == "auto" and transparent.mean() > 0.002):
        conf = 1.0 if spec == "alpha" else float(min(1.0, 0.6 + transparent.mean() * 4))
        return transparent, {"mode": "alpha", "color": None, "confidence": round(conf, 2), "notes": notes}

    code = (rgba[..., 0].astype(np.int32) << 16) | (rgba[..., 1].astype(np.int32) << 8) | rgba[..., 2]
    border = _border_mask((h, w))

    if spec == "auto":
        colors, counts = np.unique(code, return_counts=True)
        top = colors[np.argsort(-counts)[:6]]
        big_thresh = max(min_area * 4, 64)
        scored = []
        for c in top:
            lab, n = ndi.label(code == c, S4)
            if n == 0:
                continue
            areas = np.bincount(lab.ravel())[1:]
            scored.append((int(areas[areas >= big_thresh].sum()), int(c)))
        scored.sort(reverse=True)
        if not scored or scored[0][0] < 0.02 * h * w:
            return np.zeros((h, w), bool), {
                "mode": "none", "color": None,
                "confidence": round(1.0 - (scored[0][0] / (0.02 * h * w) if scored else 0) * 0.5, 2),
                "notes": ["no transparent pixels and no large flat colour region found; treating every pixel as content"],
            }
        best, key = scored[0]
        second = scored[1][0] if len(scored) > 1 else 0
        border_frac = float((code[border] == key).mean())
        conf = (best / (best + second)) * min(1.0, 0.5 + border_frac)
        if second > 0.5 * best:
            notes.append("another flat colour covers a comparable area; the background colour is a guess")
    else:
        key = (int(spec[0]) << 16) | (int(spec[1]) << 8) | int(spec[2])
        conf = 1.0

    lab, n = ndi.label(code == key, S4)
    if n == 0:
        return np.zeros((h, w), bool), {"mode": "none", "color": None, "confidence": 0.5,
                                        "notes": ["requested colour key does not occur in the image"]}
    areas = np.bincount(lab.ravel(), minlength=n + 1)
    keep = areas >= min_area
    keep[np.unique(lab[border])] = True
    keep[0] = False
    bg = keep[lab]
    color = [(key >> 16) & 255, (key >> 8) & 255, key & 255]
    return bg, {"mode": "color_key", "color": color, "confidence": round(float(conf), 2), "notes": notes}
