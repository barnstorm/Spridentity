"""Drawing helpers: outlined/numbered overlays and per-asset extraction."""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage as ndi

PALETTE = [(255, 64, 64), (64, 200, 255), (255, 208, 0), (80, 255, 120), (255, 96, 255),
           (255, 150, 40), (150, 130, 255), (0, 230, 200)]


def _font(size):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # Pillow < 10.1
        return ImageFont.load_default()


def checker(w, h, cell=8):
    yy, xx = np.mgrid[0:h, 0:w]
    c = np.where(((yy // cell) + (xx // cell)) % 2 == 0, 150, 110).astype(np.uint8)
    return np.dstack([c, c, c])


def composite(rgba, bg, scale):
    """Nearest-neighbour upscale with background shown as a grey checkerboard."""
    big = np.kron(rgba, np.ones((scale, scale, 1), np.uint8))
    bgb = np.kron(bg.astype(np.uint8), np.ones((scale, scale), np.uint8)).astype(bool)
    out = big[..., :3].copy()
    out[bgb] = checker(big.shape[1], big.shape[0])[bgb]
    return out


def draw_overlay(rgba, bg, items, scale=3, crop=None, tag_names=False):
    """items: list of (tag_text, label_map_value_mask_fn) -> here (tag, mask, x0, y0).

    Each item's exact pixel outline is drawn, with its tag at the top-left of its box.
    `crop` = (x0, y0, x1, y1) in sheet pixels.
    """
    h, w = bg.shape
    cx0, cy0, cx1, cy1 = crop or (0, 0, w, h)
    base = composite(rgba[cy0:cy1, cx0:cx1], bg[cy0:cy1, cx0:cx1], scale)
    H, W = base.shape[:2]
    tags = []
    for n, (tag, mask, x0, y0) in enumerate(items):
        color = PALETTE[n % len(PALETTE)]
        mh, mw = mask.shape
        if x0 >= cx1 or y0 >= cy1 or x0 + mw <= cx0 or y0 + mh <= cy0:
            continue
        pad = np.zeros((mh + 2, mw + 2), bool)  # 1px margin so the outline closes at the mask's edge
        pad[1:-1, 1:-1] = mask
        big = np.kron(pad.astype(np.uint8), np.ones((scale, scale), np.uint8)).astype(bool)
        t = max(1, scale // 2)
        er = big.copy()
        for _ in range(t):  # erode by t px -> the outline sits just inside the mask
            er = er & np.roll(er, 1, 0) & np.roll(er, -1, 0) & np.roll(er, 1, 1) & np.roll(er, -1, 1)
        edge = (big & ~er)[scale:-scale, scale:-scale]
        ty, tx = (y0 - cy0) * scale, (x0 - cx0) * scale  # where the item's box lands in the crop
        ys = slice(max(0, ty), min(H, ty + mh * scale))
        xs = slice(max(0, tx), min(W, tx + mw * scale))
        base[ys, xs][edge[ys.start - ty:ys.stop - ty, xs.start - tx:xs.stop - tx]] = color
        # the tag goes on the candidate's own pixels (top-left of each separate piece), so it
        # cannot be mistaken for a neighbour's even when bounding boxes share a corner
        parts, n_parts = ndi.label(mask, np.ones((3, 3), bool))
        for sl in (ndi.find_objects(parts) if n_parts <= 4 else [(slice(0, mh), slice(0, mw))]):
            py = sl[0].start
            px = sl[1].start + int(np.argmax(mask[py, sl[1]]))
            tags.append((tag, (x0 + px - cx0) * scale, (y0 + py - cy0) * scale, color))
    img = Image.fromarray(base)
    d = ImageDraw.Draw(img)
    font = _font(max(9, min(13, scale * 2 + 1)))
    for tag, x, y, color in tags:
        if not tag:
            continue
        tw, th = d.textbbox((0, 0), tag, font=font)[2:]
        x, y = max(0, min(x, W - tw - 3)), max(0, min(y, H - th - 3))
        box = d.textbbox((x + 1, y), tag, font=font)
        d.rectangle((box[0] - 1, box[1] - 1, box[2] + 1, box[3] + 1), fill=(0, 0, 0))
        d.text((x + 1, y), tag, fill=color, font=font)
    return img


def extract(rgba, mask, x0, y0):
    """The asset alone on a transparent canvas the size of its bounding box."""
    h, w = mask.shape
    out = rgba[y0:y0 + h, x0:x0 + w].copy()
    out[~mask] = 0
    out[mask & (out[..., 3] == 0), 3] = 255
    return Image.fromarray(out, "RGBA")
