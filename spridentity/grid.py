"""Infer a tile lattice period from the image, when the user did not supply one.

Two profiles per axis: edge energy (how much colour changes from one pixel column
to the next) and continuity (how often neighbouring pixels are both content and
similar). Lattice lines starting at pixel 0 must fall between things rather than
through them (continuity), and the sheet must actually repeat at that period
(autocorrelation of the edge profile). Before that, a simpler clue is tried:
where tiles are packed edge to edge, long straight content/background boundaries
lie only on lattice lines. Periods must divide the sheet size. Sheets with margins or gutters between
cells are not modelled -- on those, background separation does the work instead.
"""
from __future__ import annotations

import numpy as np

SIMILAR = 48  # L1 RGB distance under which two neighbouring pixels count as continuous


def _continuity(rgb: np.ndarray, fg: np.ndarray, axis: int) -> np.ndarray:
    """K[i] = share of positions where pixel i-1 and i (along `axis`) are continuous."""
    if axis == 1:
        rgb, fg = rgb.transpose(1, 0, 2), fg.T
    d = np.abs(rgb[1:].astype(np.int16) - rgb[:-1]).sum(-1)
    cont = fg[1:] & fg[:-1] & (d <= SIMILAR)
    k = np.zeros(rgb.shape[0])
    k[1:] = cont.mean(1)
    return k


def _edge_energy(rgb: np.ndarray, fg: np.ndarray, axis: int) -> np.ndarray:
    """E[i] = mean colour step between pixel i-1 and i; content/background steps count fully."""
    if axis == 1:
        rgb, fg = rgb.transpose(1, 0, 2), fg.T
    d = np.abs(rgb[1:].astype(np.int16) - rgb[:-1]).sum(-1).astype(np.float64)
    d[fg[1:] != fg[:-1]] = 765
    d[~fg[1:] & ~fg[:-1]] = 0
    e = np.zeros(rgb.shape[0])
    e[1:] = d.mean(1)
    return e


def _best_period(e: np.ndarray, k: np.ndarray, lo: int = 8, hi: int = 128):
    """Smallest period p that passes two tests.

    Lattice test: lines at p, 2p, 3p (from pixel 0) all cut through much less
    continuous content than average. Requiring the multiples too rejects periods
    that only work by luck, and taking the smallest finds the unit rather than a
    block of units.
    Repetition test: the edge profile repeats at about p. This rejects a
    half-height "unit" on sheets whose sprites happen to stay clear of the middle
    of their cells.
    """
    n = len(e)
    base = k[1:].mean()
    top = min(hi, n // 4)  # fewer than four cells across is too little to call a lattice
    if top < lo or base <= 0:
        return None, 0.0
    z = e - e.mean()
    var = (z * z).mean()
    r = np.zeros(top + 2)
    if var > 0:
        r = np.array([(z[:n - l] * z[l:]).mean() for l in range(top + 2)]) / var
    best_r = max(float(r[lo:top + 1].max()), 1e-6)

    def lattice(p):
        return 1.0 - k[np.arange(p, n, p)].mean() / base

    for p in range(lo, top + 1):
        if n % p:
            continue  # sheets are cut to a whole number of cells
        h = min(lattice(m * p) for m in (1, 2, 3) if m * p <= max(n // 2, p))
        if h < 0.25:
            continue
        rep = float(r[p - 1:p + 2].max()) / best_r if best_r > 0.15 else 0.5
        if rep < 0.5:
            continue
        return p, float(min(1.0, 0.5 * h + 0.5 * min(1.0, rep)))
    return None, 0.0


def _straight_edges(fg: np.ndarray, axis: int, min_run: int = 6) -> np.ndarray:
    """w[i] = total length of straight content/background boundary lying exactly
    between pixel i-1 and i (runs of at least `min_run`). Tiles packed edge to edge
    leave such boundaries only on lattice lines; sprites leave them anywhere."""
    if axis == 0:
        fg = fg.T
    b = fg[:, 1:] != fg[:, :-1]                     # boundary between column x and x+1
    pad = np.zeros((b.shape[0] + 2, b.shape[1]), np.int8)
    pad[1:-1] = b
    d = np.diff(pad, axis=0)
    xs, starts = np.nonzero((d == 1).T)             # column-major, so starts and ends pair up
    _, ends = np.nonzero((d == -1).T)
    length = ends - starts
    w = np.zeros(fg.shape[1])
    keep = length >= min_run
    np.add.at(w, xs[keep] + 1, length[keep])
    return w


def _period_from_edges(w: np.ndarray, lo: int = 8):
    """Largest divisor of the sheet size whose lattice carries nearly all straight edges."""
    n, total = len(w), w.sum()
    if total < n or np.count_nonzero(w) < 3:
        return None, 0.0
    for p in range(n // 2, lo - 1, -1):
        if n % p:
            continue
        cover = w[np.arange(p, n, p)].sum() / total
        if cover >= 0.85:
            return p, float(cover)
    return None, 0.0


def infer_unit(rgba: np.ndarray, bg: np.ndarray, min_period: int = 8):
    """Return ((unit_w, unit_h) or None, confidence). `min_period` is the smallest unit considered."""
    rgb, fg = rgba[..., :3], ~bg
    found = []
    for axis in (1, 0):
        p, c = _period_from_edges(_straight_edges(fg, axis, min_run=max(2, min_period * 3 // 4)), lo=min_period)
        if p is None:
            p, c = _best_period(_edge_energy(rgb, fg, axis), _continuity(rgb, fg, axis), lo=min_period)
        found.append((p, c))
    (pw, cw), (ph, ch) = found
    n_w, n_h = fg.shape[1], fg.shape[0]
    # one axis undecided: assume square cells if that fits the sheet
    if pw is None and ph is not None and n_w % ph == 0:
        pw, cw = ph, ch * 0.6
    if ph is None and pw is not None and n_h % pw == 0:
        ph, ch = pw, cw * 0.6
    if pw is None or ph is None:
        return None, round(min(cw, ch), 2)
    # very lopsided cells are almost always one axis locking onto a block of cells
    small, big = min(pw, ph), max(pw, ph)
    if big > 2 * small:
        if small >= 2 * min_period and big % small == 0 and n_w % small == 0 and n_h % small == 0:
            return (small, small), round(min(cw, ch) * 0.8, 2)
        return None, 0.0
    return (pw, ph), round(min(cw, ch), 2)


def native_scale(rgba: np.ndarray, limit: int = 8) -> int:
    """Largest k such that the image is an exact k-times enlargement of smaller art
    (every aligned k x k block is one colour). 1 when it is not enlarged."""
    h, w = rgba.shape[:2]
    for k in range(limit, 1, -1):
        if h % k or w % k:
            continue
        b = rgba.reshape(h // k, k, w // k, k, -1)
        if (b == b[:, :1, :, :1]).all():
            return k
    return 1


def lattice_fit(fg: np.ndarray, unit) -> dict:
    """How well the content sits on a lattice of `unit` starting at pixel 0.

    Looks at every separate blob small enough for one cell and counts those that
    lie inside one cell. A unit that is too small, or shifted, fails this; a unit
    that is a multiple of the true one passes, so this can refute but not prove."""
    from scipy import ndimage as ndi
    uw, uh = unit
    comp, n = ndi.label(fg, np.ones((3, 3), bool))
    small = fit = 0
    for sl in ndi.find_objects(comp):
        y0, y1, x0, x1 = sl[0].start, sl[0].stop, sl[1].start, sl[1].stop
        if x1 - x0 <= uw and y1 - y0 <= uh:
            small += 1
            fit += x0 // uw == (x1 - 1) // uw and y0 // uh == (y1 - 1) // uh
    h, w = fg.shape
    return {"divides_sheet": bool(w % uw == 0 and h % uh == 0), "small_blobs": int(small),
            "inside_one_cell": int(fit), "share": round(fit / small, 2) if small else None}
