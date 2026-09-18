"""Placement guard: a coarse occupancy map that keeps the artwork DRC-clean.

A decorative board is generated, not routed by hand, so nothing stops two
generators from dropping a 0201 pad on top of a stitching via. Rather than
relaxing the design rules afterwards, every small object asks this map whether
its footprint is free before it is placed.

Resolution is 0.05 mm per cell — fine enough for the clearances we care about
(0.2 mm copper, 0.25 mm hole, 0.5 mm board edge) and cheap enough to rebuild
for every run (110 x 48 mm -> 2200 x 960 cells per side).
"""

from __future__ import annotations

import math

import numpy as np

CELL = 0.05


class Occupancy:
    def __init__(self, w, h, outline=None, edge_clearance=0.55):
        self.w, self.h = w, h
        self.nx = int(w / CELL) + 2
        self.ny = int(h / CELL) + 2
        self.front = np.zeros((self.ny, self.nx), dtype=bool)
        self.back = np.zeros((self.ny, self.nx), dtype=bool)
        self.holes = np.zeros((self.ny, self.nx), dtype=bool)
        # cells too close to the board edge (or outside it) for copper
        self.forbidden = np.ones((self.ny, self.nx), dtype=bool)
        if outline:
            self._mark_inside(outline, edge_clearance)

    # -- internals ---------------------------------------------------------

    def _idx(self, x, y):
        return int(round(y / CELL)), int(round(x / CELL))

    def _slice(self, x0, y0, x1, y1):
        r0 = max(0, int(math.floor(y0 / CELL)))
        r1 = min(self.ny, int(math.ceil(y1 / CELL)) + 1)
        c0 = max(0, int(math.floor(x0 / CELL)))
        c1 = min(self.nx, int(math.ceil(x1 / CELL)) + 1)
        return slice(r0, r1), slice(c0, c1)

    def _mark_inside(self, outline, clearance):
        """forbidden = outside the outline, or within `clearance` of it."""
        ys = (np.arange(self.ny) * CELL)[:, None]
        xs = (np.arange(self.nx) * CELL)[None, :]
        inside = self._point_in_poly(xs, ys, outline)
        dist = self._dist_to_poly(xs, ys, outline)
        self.forbidden = ~(inside & (dist >= clearance))

    @staticmethod
    def _point_in_poly(xs, ys, poly):
        n = len(poly)
        inside = np.zeros((ys.shape[0], xs.shape[1]), dtype=bool)
        X = np.broadcast_to(xs, inside.shape)
        Y = np.broadcast_to(ys, inside.shape)
        for i in range(n):
            x1, y1 = poly[i]
            x2, y2 = poly[(i + 1) % n]
            cond = ((y1 > Y) != (y2 > Y))
            with np.errstate(divide="ignore", invalid="ignore"):
                xint = (x2 - x1) * (Y - y1) / (y2 - y1 + 1e-12) + x1
            inside ^= cond & (X < xint)
        return inside

    @staticmethod
    def _dist_to_poly(xs, ys, poly):
        shape = (ys.shape[0], xs.shape[1])
        X = np.broadcast_to(xs, shape).astype(np.float32)
        Y = np.broadcast_to(ys, shape).astype(np.float32)
        best = np.full(shape, 1e9, dtype=np.float32)
        n = len(poly)
        for i in range(n):
            x1, y1 = poly[i]
            x2, y2 = poly[(i + 1) % n]
            dx, dy = x2 - x1, y2 - y1
            L2 = dx * dx + dy * dy
            if L2 < 1e-12:
                d = np.hypot(X - x1, Y - y1)
            else:
                t = np.clip(((X - x1) * dx + (Y - y1) * dy) / L2, 0.0, 1.0)
                d = np.hypot(X - (x1 + t * dx), Y - (y1 + t * dy))
            np.minimum(best, d, out=best)
        return best

    def _plane(self, side):
        return self.back if side == "back" else self.front

    # -- public API --------------------------------------------------------

    def free(self, x0, y0, x1, y1, side="front", check_edge=True):
        rs, cs = self._slice(x0, y0, x1, y1)
        if rs.start >= rs.stop or cs.start >= cs.stop:
            return False
        if check_edge and self.forbidden[rs, cs].any():
            return False
        return not self._plane(side)[rs, cs].any()

    def take(self, x0, y0, x1, y1, side="front"):
        rs, cs = self._slice(x0, y0, x1, y1)
        self._plane(side)[rs, cs] = True

    def take_both(self, x0, y0, x1, y1):
        self.take(x0, y0, x1, y1, "front")
        self.take(x0, y0, x1, y1, "back")

    def rect(self, cx, cy, w, h, margin=0.0):
        return (cx - w / 2 - margin, cy - h / 2 - margin,
                cx + w / 2 + margin, cy + h / 2 + margin)

    # holes need their own clearance to every other hole and to copper
    def hole_free(self, x, y, r, clearance=0.3):
        rr = r + clearance
        rs, cs = self._slice(x - rr, y - rr, x + rr, y + rr)
        if rs.start >= rs.stop or cs.start >= cs.stop:
            return False
        if self.forbidden[rs, cs].any():
            return False
        return not self.holes[rs, cs].any()

    def take_hole(self, x, y, r):
        rs, cs = self._slice(x - r, y - r, x + r, y + r)
        self.holes[rs, cs] = True
