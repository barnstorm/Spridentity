"""Pixel-exact segmentation of a sheet into candidate assets.

Three layers, each a partition of the content pixels:

  atoms    smallest pieces we can cut deterministically: a connected component,
           or (when a lattice is known) the part of a component inside one cell
  links    evidence that two touching atoms are the same asset (0..1 affinity)
  regions  unions of atoms -- the candidate assets

Later stages (the vision model, the user) only ever regroup atoms, so every mask
in the final inventory is exact to the pixel.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy import ndimage as ndi

S8 = np.ones((3, 3), bool)
MERGE_T = 0.5  # links at or above this affinity are merged
CLUSTER_T = 0.5  # palette overlap two tile clusters need before they may join
SIMILAR = 48     # L1 RGB distance under which two neighbouring pixels count as the same surface
EDGE_T = 0.75    # share of a seam that must show an outline on both sides to count as "two closed shapes"
REP_T = 0.85     # silhouette overlap (one unit apart) that counts as "the same shape again"
KEEP = 0.55      # affinity of touching pieces kept together only because nothing shows they are separate


@dataclass
class Link:
    a: int
    b: int
    affinity: float
    contact: int


@dataclass
class Region:
    atoms: list
    reasons: list = field(default_factory=list)  # why disconnected parts were grouped


class UnionFind:
    def __init__(self, n):
        self.p = list(range(n))

    def find(self, x):
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b):
        a, b = self.find(a), self.find(b)
        if a != b:
            self.p[max(a, b)] = min(a, b)


def _pairs(atom_map, rgb):
    """Touching pixel pairs between different atoms, per orientation.

    Returns {(a, b): rec} with a < b, where rec[o] for o = 0 (left/right neighbours,
    the seam runs vertically) and o = 1 (above/below) is
      [contact, summed colour step across, pairs whose colour carries on across,
       pairs with an outline just inside on both sides, summed seam coordinate,
       pairs where a is on the low-coordinate side]
    and per-atom mean colour step between neighbouring pixels inside the atom (h, v).
    """
    n = int(atom_map.max())
    out = {}
    internal = np.zeros((2, n + 1))
    for o in (0, 1):
        am = atom_map if o == 0 else atom_map.T
        c = rgb if o == 0 else rgb.transpose(1, 0, 2)
        A, B = am[:, :-1], am[:, 1:]
        d = np.abs(c[:, :-1].astype(np.int16) - c[:, 1:]).sum(-1)
        same = (A == B) & (A > 0)
        cnt = np.bincount(A[same], minlength=n + 1)
        internal[o] = np.bincount(A[same], weights=d[same].astype(np.float64), minlength=n + 1) / np.maximum(cnt, 1)
        m = (A != B) & (A > 0) & (B > 0)
        if not m.any():
            continue
        # an outline just inside the seam: one pixel further in is a different colour, or not this atom
        in_a = np.ones(m.shape, bool)
        in_b = np.ones(m.shape, bool)
        if am.shape[1] > 2:
            in_a[:, 1:] = (am[:, :-2] != am[:, 1:-1]) | (d[:, :-1] > SIMILAR)
            in_b[:, :-1] = (am[:, 2:] != am[:, 1:-1]) | (d[:, 1:] > SIMILAR)
        lo = np.minimum(A[m], B[m]).astype(np.int64)
        hi = np.maximum(A[m], B[m]).astype(np.int64)
        key, inv = np.unique(lo * (n + 1) + hi, return_inverse=True)
        pos = np.nonzero(m)[1] + 1
        cols = [np.bincount(inv),
                np.bincount(inv, weights=d[m].astype(np.float64)),
                np.bincount(inv, weights=(d[m] <= SIMILAR).astype(np.float64)),
                np.bincount(inv, weights=(in_a[m] & in_b[m]).astype(np.float64)),
                np.bincount(inv, weights=pos.astype(np.float64)),
                np.bincount(inv, weights=(A[m] < B[m]).astype(np.float64))]
        for i, k in enumerate(key):
            rec = out.setdefault((int(k // (n + 1)), int(k % (n + 1))), np.zeros((2, 6)))
            rec[o] = [col[i] for col in cols]
    return out, internal


class Segmentation:
    def __init__(self, rgba, bg, unit=None, group_parts=True):
        self.rgba, self.bg, self.unit = rgba, bg, unit
        self.h, self.w = bg.shape
        self.fg = ~bg
        self._build_atoms()
        self._build_links()
        uf = self._cluster()
        groups = {}
        for a in range(1, self.n_atoms + 1):
            groups.setdefault(uf.find(a), []).append(a)
        self.regions = [Region(atoms) for atoms in groups.values()]
        if group_parts:
            self._group_parts()
        self.sort_regions()

    # ---- atoms -----------------------------------------------------------
    def _build_atoms(self):
        comp, _ = ndi.label(self.fg, S8)
        if self.unit is None:
            atom_map = self._split_necks(comp.astype(np.int32))
        else:
            uw, uh = self.unit
            ys, xs = np.nonzero(self.fg)
            ncols, nrows = -(-self.w // uw), -(-self.h // uh)
            key = comp[ys, xs].astype(np.int64) * (ncols * nrows) + (ys // uh) * ncols + xs // uw
            _, inv = np.unique(key, return_inverse=True)
            atom_map = np.zeros((self.h, self.w), np.int32)
            atom_map[ys, xs] = inv + 1
            atom_map = self._absorb_slivers(atom_map, max(2, int(0.04 * uw * uh)))
        self.atom_map = atom_map
        self.n_atoms = int(atom_map.max())
        self.atom_area = np.bincount(atom_map.ravel(), minlength=self.n_atoms + 1)
        self.atom_slices = ndi.find_objects(atom_map)
        self.atom_full = np.zeros(self.n_atoms + 1, bool)
        if self.unit is not None:
            uw, uh = self.unit
            for a, sl in enumerate(self.atom_slices, start=1):
                y0, y1, x0, x1 = sl[0].start, sl[0].stop, sl[1].start, sl[1].stop
                aligned = (x0 % uw == 0 and y0 % uh == 0 and (x1 % uw == 0 or x1 == self.w)
                           and (y1 % uh == 0 or y1 == self.h) and x1 - x0 <= uw and y1 - y0 <= uh)
                self.atom_full[a] = aligned and self.atom_area[a] == (y1 - y0) * (x1 - x0)
        self.atom_framed = np.zeros(self.n_atoms + 1, bool)
        for a in np.nonzero(self.atom_full)[0]:
            self.atom_framed[a] = self._framed(self.atom_slices[a - 1])

    def _framed(self, sl):
        """A filled cell that is a picture on its own backing: one colour all the way
        round the rim, something else inside (an icon on a coloured square)."""
        px = self.rgba[sl]
        code = ((px[..., 0] >> 3).astype(np.int32) << 10) | ((px[..., 1] >> 3).astype(np.int32) << 5) | (px[..., 2] >> 3)
        if min(code.shape) < 4:
            return False
        rim = np.concatenate([code[0], code[-1], code[:, 0], code[:, -1]])
        return bool((rim == rim[0]).all() and (code != rim[0]).mean() >= 0.05)

    def _split_necks(self, comp):
        """Without a grid, the only pixel evidence that one blob is several objects is
        a narrow neck: shrink the blob a little and see whether it falls apart into
        comparable pieces. Each pixel then goes to the nearest piece. Whether the
        pieces are re-joined is decided by the link affinity like everything else."""
        out = comp.copy()
        next_id = int(comp.max()) + 1
        for c, sl in enumerate(ndi.find_objects(comp), start=1):
            sl = tuple(slice(max(0, d.start - 1), d.stop + 1) for d in sl)
            m = comp[sl] == c
            if m.sum() < 128:
                continue
            for r in (1, 2):
                cores, n = ndi.label(ndi.binary_erosion(m, S8, iterations=r), S8)
                if n < 2:
                    continue
                sizes = np.bincount(cores.ravel())[1:]
                big = np.nonzero(sizes >= max(24, 0.25 * sizes.max()))[0] + 1
                if len(big) < 2:
                    continue
                seeds = np.where(np.isin(cores, big), cores, 0)
                _, (iy, ix) = ndi.distance_transform_edt(seeds == 0, return_indices=True)
                owner = seeds[iy, ix]
                for k in big[1:]:
                    out[sl][m & (owner == k)] = next_id
                    next_id += 1
                break
        return out

    def _absorb_slivers(self, atom_map, thresh):
        """A few stray pixels of a sprite poking into the next cell are not an atom."""
        pairs, _ = _pairs(atom_map, self.rgba[..., :3])
        area = np.bincount(atom_map.ravel())
        nbrs = {}
        for (a, b), rec in pairs.items():
            nbrs.setdefault(a, {})[b] = rec[0][0] + rec[1][0]
            nbrs.setdefault(b, {})[a] = rec[0][0] + rec[1][0]
        remap = np.arange(len(area))
        for a in np.argsort(area):
            if a == 0 or area[a] >= thresh or a not in nbrs:
                continue
            target = max(nbrs[a], key=nbrs[a].get)
            while remap[target] != target:
                target = remap[target]
            if target != a:
                remap[a] = target
        for a in range(len(remap)):
            t = a
            while remap[t] != t:
                t = remap[t]
            remap[a] = t
        _, compact = np.unique(remap, return_inverse=True)
        return compact[atom_map].astype(np.int32)

    # ---- links -----------------------------------------------------------
    def _palette(self, a):
        sl = self.atom_slices[a - 1]
        px = self.rgba[sl][self.atom_map[sl] == a]
        code = ((px[:, 0] >> 3).astype(np.int32) << 10) | ((px[:, 1] >> 3).astype(np.int32) << 5) | (px[:, 2] >> 3)
        c, n = np.unique(code, return_counts=True)
        return c, n / n.sum()

    def _build_links(self):
        self.links, self._pal = [], {}
        pairs, internal = _pairs(self.atom_map, self.rgba[..., :3])
        pal = self._pal = {}
        for (a, b), rec in pairs.items():
            # o=0: left/right neighbours (the shared seam runs vertically)
            o = 0 if rec[0][0] >= rec[1][0] else 1
            contact, sdiff, n_flow, n_edge, pos_sum, a_low = rec[o]
            cross = sdiff / contact
            inner = (internal[o][a] + internal[o][b]) / 2
            continuity = float(np.clip(1 - max(0.0, cross - inner) / (inner + 40), 0, 1))
            for x in (a, b):
                if x not in pal:
                    pal[x] = self._palette(x)
            (ca, na), (cb, nb) = pal[a], pal[b]
            _, ia, ib = np.intersect1d(ca, cb, return_indices=True)
            palette = float(np.minimum(na[ia], nb[ib]).sum())
            if self.atom_full[a] and self.atom_full[b]:
                # two whole tiles: same material? Palette matters most -- different
                # terrains often share a seamless border strip (grass around everything).
                # A cell that is a picture on its own backing is never part of its neighbour.
                aff = 0.1 if self.atom_framed[a] or self.atom_framed[b] else 0.3 * continuity + 0.7 * palette
            elif self.unit is None:
                # no unit: pieces come from neck splits; does the seam cut through a body?
                ext = []
                for x in (a, b):
                    sl = self.atom_slices[x - 1]
                    ext.append(sl[0].stop - sl[0].start if o == 0 else sl[1].stop - sl[1].start)
                content = 0.5 * continuity + 0.5 * palette
                aff = min(1.0, contact / min(ext)) * (0.3 + 0.7 * content)
            else:
                # The seam is a unit line through one blob. A unit line is not a boundary
                # by itself: the pieces stay together unless the pixels show two things.
                flow = n_flow / contact
                aff = 0.3 + 0.7 * max(flow, 0.5 * continuity + 0.5 * palette)
                if not self.atom_full[a] and not self.atom_full[b]:
                    aff = max(aff, KEEP)
                low, high = (a, b) if a_low * 2 >= contact else (b, a)
                if self._pinched(low, high, o, int(round(pos_sum / contact)), int(contact)):
                    aff = 0.15           # the blob narrows to a neck exactly on the line
                elif n_edge / contact >= EDGE_T:
                    # an outline runs along both sides of the line: two closed shapes?
                    aff = 0.2 if self._repeats(a, b) >= REP_T else min(aff, KEEP)
            self.links.append(Link(a, b, round(float(aff), 3), int(rec[0][0] + rec[1][0])))

    def _pinched(self, low, high, o, pos, contact):
        """True when both pieces widen quickly away from the seam, i.e. they only touch."""
        along, across = (self.unit[1], self.unit[0]) if o == 0 else (self.unit[0], self.unit[1])
        if contact * 2 > along:
            return False
        am = self.atom_map if o == 0 else self.atom_map.T
        depth = max(2, across // 4)
        for atom, start, step in ((low, pos - 1, -1), (high, pos, 1)):
            sl = self.atom_slices[atom - 1]
            rows = sl[0] if o == 0 else sl[1]
            widest = 0
            for d in range(1, depth + 1):
                col = start + step * d
                if 0 <= col < am.shape[1]:
                    widest = max(widest, int(np.count_nonzero(am[rows, col] == atom)))
            if widest < max(2 * contact, contact + 2):
                return False
        return True

    def _repeats(self, a, b):
        """Silhouette overlap of two pieces when one is laid over the other, cell on cell."""
        uw, uh = self.unit
        wins = []
        for x in (a, b):
            sl = self.atom_slices[x - 1]
            ys, xs = np.nonzero(self.atom_map[sl] == x)
            cy, cx = int(np.median(ys) + sl[0].start) // uh, int(np.median(xs) + sl[1].start) // uw
            wins.append(self.atom_map[cy * uh:(cy + 1) * uh, cx * uw:(cx + 1) * uw] == x)
        if wins[0].shape != wins[1].shape:
            return 0.0
        return float((wins[0] & wins[1]).sum() / max(1, (wins[0] | wins[1]).sum()))

    def _cluster(self):
        """Merge along links, strongest first. Tiles join a cluster only while the
        cluster as a whole still looks like the same material, which stops long
        chains forming through shared border strips."""
        uf = UnionFind(self.n_atoms + 1)
        hist = {}

        def h(root):
            if root not in hist:
                c, n = self._pal[root] if root in self._pal else self._palette(root)
                hist[root] = dict(zip(c.tolist(), (n * self.atom_area[root]).tolist()))
            return hist[root]

        for l in sorted(self.links, key=lambda l: -l.affinity):
            if l.affinity < MERGE_T:
                break
            ra, rb = uf.find(l.a), uf.find(l.b)
            if ra == rb:
                continue
            ha, hb = h(ra), h(rb)
            if self.atom_full[l.a] and self.atom_full[l.b]:
                ta, tb = sum(ha.values()), sum(hb.values())
                if sum(min(v / ta, hb.get(c, 0) / tb) for c, v in ha.items()) < CLUSTER_T:
                    continue
            uf.union(ra, rb)
            keep, gone = (ra, rb) if ra < rb else (rb, ra)
            for c, v in hist.pop(gone).items():
                hist[keep][c] = hist[keep].get(c, 0) + v
        return uf

    # ---- grouping of disconnected parts -----------------------------------
    def region_map(self):
        lut = np.zeros(self.n_atoms + 1, np.int32)
        for i, r in enumerate(self.regions, start=1):
            lut[r.atoms] = i
        return lut[self.atom_map]

    def region_bbox(self, r):
        sls = [self.atom_slices[a - 1] for a in r.atoms]
        return (min(s[1].start for s in sls), min(s[0].start for s in sls),
                max(s[1].stop for s in sls), max(s[0].stop for s in sls))

    def region_area(self, r):
        return int(self.atom_area[r.atoms].sum())

    def region_mask(self, r):
        """(mask, x0, y0): boolean mask cropped to the region's bounding box."""
        x0, y0, x1, y1 = self.region_bbox(r)
        return np.isin(self.atom_map[y0:y1, x0:x1], r.atoms), x0, y0

    def _group_parts(self):
        rmap = self.region_map()
        n = len(self.regions)
        uf = UnionFind(n + 1)
        reason = {}
        boxes = [None] + [self.region_bbox(r) for r in self.regions]
        areas = [0] + [self.region_area(r) for r in self.regions]
        if self.unit is not None:
            uw, uh = self.unit
            cells = {}
            for i in range(1, n + 1):
                x0, y0, x1, y1 = boxes[i]
                if x0 // uw == (x1 - 1) // uw and y0 // uh == (y1 - 1) // uh:
                    cells.setdefault((x0 // uw, y0 // uh), []).append(i)
            for (cx, cy), members in cells.items():
                if len(members) < 2:
                    continue
                present = np.unique(rmap[cy * uh:(cy + 1) * uh, cx * uw:(cx + 1) * uw])
                if set(present[present > 0]) == set(members):
                    for m in members[1:]:
                        uf.union(members[0], m)
                        reason[m] = "separate parts sharing one grid cell"
            self._group_in_window(rmap, boxes, uf, reason)
        # tiny satellites (sparkles, detached specks) within 2px of a much larger body
        tiny = (self.unit[0] * self.unit[1]) // 8 if self.unit else 24
        for i in range(1, n + 1):
            if areas[i] > tiny:
                continue
            x0, y0, x1, y1 = boxes[i]
            X0, Y0, X1, Y1 = max(0, x0 - 2), max(0, y0 - 2), min(self.w, x1 + 2), min(self.h, y1 + 2)
            win = rmap[Y0:Y1, X0:X1]
            near = ndi.binary_dilation(win == i, S8, iterations=2)
            ids, cnt = np.unique(win[near & (win != i) & (win > 0)], return_counts=True)
            best = None
            for j, c in sorted(zip(ids, cnt), key=lambda t: -t[1]):
                if areas[j] < 20 * areas[i]:
                    continue
                if self.unit is not None:
                    uw, uh = self.unit
                    hx0, hy0, hx1, hy1 = boxes[j]
                    if not (x0 >= hx0 // uw * uw and y0 >= hy0 // uh * uh
                            and x1 <= -(-hx1 // uw) * uw and y1 <= -(-hy1 // uh) * uh):
                        continue
                best = j
                break
            if best is not None and uf.find(i) != uf.find(best):
                uf.union(i, best)
                reason[i] = "small detached part next to a larger body"
        merged = {}
        for i in range(1, n + 1):
            merged.setdefault(uf.find(i), []).append(i)
        out = []
        for members in merged.values():
            r = Region([a for m in members for a in self.regions[m - 1].atoms])
            r.reasons = sorted({reason[m] for m in members if m in reason})
            out.append(r)
        self.regions = out

    def _group_in_window(self, rmap, boxes, uf, reason):
        """Small pieces that sit off the lattice: a unit is the least an asset should
        need, so close pieces that together fit one unit, alone in that window, are one."""
        uw, uh = self.unit
        gap = max(1, min(uw, uh) // 8)
        n = len(boxes) - 1

        def is_small(b):
            return b[2] - b[0] <= uw and b[3] - b[1] <= uh

        def in_cell(b):
            return b[0] // uw == (b[2] - 1) // uw and b[1] // uh == (b[3] - 1) // uh

        members, gbox = {}, {}
        for i in range(1, n + 1):
            members.setdefault(uf.find(i), set()).add(i)
        for r, ms in members.items():
            bs = [boxes[m] for m in ms]
            gbox[r] = (min(q[0] for q in bs), min(q[1] for q in bs), max(q[2] for q in bs), max(q[3] for q in bs))
        for i in range(1, n + 1):
            if not is_small(boxes[i]):
                continue
            x0, y0, x1, y1 = boxes[i]
            win = rmap[max(0, y0 - gap):y1 + gap, max(0, x0 - gap):x1 + gap]
            for j in np.unique(win):
                j = int(j)
                if j <= i or not is_small(boxes[j]):
                    continue
                if in_cell(boxes[i]) and in_cell(boxes[j]):
                    continue                      # each in a cell of its own: the lattice keeps them apart
                ri, rj = uf.find(i), uf.find(j)
                if ri == rj:
                    continue
                bi, bj = gbox[ri], gbox[rj]
                u = (min(bi[0], bj[0]), min(bi[1], bj[1]), max(bi[2], bj[2]), max(bi[3], bj[3]))
                if u[2] - u[0] > uw or u[3] - u[1] > uh:
                    continue
                both = members[ri] | members[rj]
                present = np.unique(rmap[u[1]:u[3], u[0]:u[2]])
                if not set(present[present > 0].tolist()) <= both:
                    continue
                uf.union(ri, rj)
                root = uf.find(ri)
                gbox[root], members[root] = u, both
                reason[j] = reason[i] = "small separate parts that together fit one unit"

    def upscale(self, k, rgba, bg):
        """Carry a segmentation made on a k-times reduced image back to the full image."""
        self.atom_map = np.repeat(np.repeat(self.atom_map, k, axis=0), k, axis=1)
        self.rgba, self.bg, self.fg = rgba, bg, ~bg
        self.h, self.w = bg.shape
        if self.unit:
            self.unit = (self.unit[0] * k, self.unit[1] * k)
        self.atom_area = np.bincount(self.atom_map.ravel(), minlength=self.n_atoms + 1)
        self.atom_slices = ndi.find_objects(self.atom_map)
        self._pal = {}

    def sort_regions(self):
        band = self.unit[1] if self.unit else 16
        def key(r):
            x0, y0, _, _ = self.region_bbox(r)
            return (y0 // band, x0, y0)
        self.regions.sort(key=key)

    # ---- evidence about a region's boundary --------------------------------
    def boundary_evidence(self, regions=None):
        """For each region: weakest link inside it, strongest link leaving it.

        Returns a list of dicts {internal_min, external: [(other_index, affinity)]},
        indexed like `regions` (default self.regions).
        """
        regions = self.regions if regions is None else regions
        owner = np.zeros(self.n_atoms + 1, np.int32) - 1
        for i, r in enumerate(regions):
            owner[r.atoms] = i
        ev = [{"internal_min": None, "external": {}} for _ in regions]
        # "weakest link inside" = the bottleneck of the strongest spanning tree, so a
        # weak direct link between two atoms that are firmly joined via a third does not count
        uf = UnionFind(self.n_atoms + 1)
        for l in sorted(self.links, key=lambda l: -l.affinity):
            ra, rb = owner[l.a], owner[l.b]
            if ra < 0 or rb < 0:
                continue
            if ra == rb:
                if uf.find(l.a) != uf.find(l.b):
                    uf.union(l.a, l.b)
                    ev[ra]["internal_min"] = l.affinity  # links arrive strongest first
            else:
                for x, y in ((ra, rb), (rb, ra)):
                    ev[x]["external"][int(y)] = max(ev[x]["external"].get(int(y), 0.0), l.affinity)
        return ev
