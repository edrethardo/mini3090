"""Copper clearance on a netlist-free board: find and resolve near misses.

KiCad's clearance DRC only compares copper of DIFFERENT nets. On this board
nothing has a net, so two features 0.02 mm apart are never reported (measured:
two 0.2 mm tracks 0.05 mm apart -> zero clearance violations). A fab has no
nets either: it etches whatever gap the artwork contains.

This module applies the fab's view to the pcbnew board itself:

  island     copper items that touch or overlap form one connected feature;
             touching is harmless, the fab simply etches one shape
  violation  two items of DIFFERENT islands closer than the clearance —
             a sliver of laminate the fab cannot hold open
  same-net   two items of the SAME island that do not touch but come closer
             than the clearance (a notch inside one feature). Reported only.

`resolve()` removes the lower-priority item of every violating pair until the
board is clean. Only decoration is removable (filler discretes, stitching
vias, decorative tracks, test pads); packages, gold artwork, the QR code and
the mounting rings are not. Two non-removable items in conflict are a design
error and are returned for the build to fail on.
"""

from __future__ import annotations

import re
from collections import defaultdict

import pcbnew

LAYERS = (pcbnew.F_Cu, pcbnew.B_Cu)
GRID = 1.0            # mm, spatial hash cell


def _mm(v):
    return v / 1e6


class Item:
    __slots__ = ("obj", "fp", "layer", "shape", "bbox", "prio", "kind", "id")

    def __init__(self, obj, fp, layer, prio, kind, idx):
        self.obj, self.fp, self.layer = obj, fp, layer
        self.shape = obj.GetEffectiveShape(layer)
        self.bbox = obj.GetBoundingBox()
        self.prio, self.kind, self.id = prio, kind, idx

    def where(self):
        c = self.bbox.GetCenter()
        return _mm(c.x), _mm(c.y)

    def label(self):
        x, y = self.where()
        ref = self.fp.GetReference() if self.fp else ""
        return f"{self.kind}{(' ' + ref) if ref else ''} @({x:.2f},{y:.2f})"


# Priority: lower is removed first; FIXED items are never removed.
FIXED = 100


def _fp_priority(ref: str) -> tuple:
    if re.fullmatch(r"R\d+", ref):
        return 0, "filler"
    if re.fullmatch(r"S\d+", ref):
        return 1, "stitch-pad"
    if re.fullmatch(r"C\d+", ref):
        return 3, "cap"
    if ref.startswith("TP"):
        return 3, "testpad"
    if ref.startswith("FR"):
        return 2, "ring-pad"
    return FIXED, "package"


def collect(board):
    items = []
    for t in board.GetTracks():
        if isinstance(t, pcbnew.PCB_VIA):
            for L in LAYERS:
                items.append(Item(t, None, L, 1, "via", len(items)))
        else:
            items.append(Item(t, None, t.GetLayer(), 2, "track", len(items)))
    for fp in board.GetFootprints():
        prio, kind = _fp_priority(fp.GetReference())
        for p in fp.Pads():
            for L in LAYERS:
                if p.IsOnLayer(L) and p.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH:
                    items.append(Item(p, fp, L, prio, kind, len(items)))
    for d in board.GetDrawings():
        if d.GetLayer() in LAYERS:
            items.append(Item(d, None, d.GetLayer(), FIXED, "artwork", len(items)))
    return items


def _pairs(items, clr_iu):
    """Candidate pairs per layer whose inflated bounding boxes overlap."""
    grid = defaultdict(list)
    g = pcbnew.FromMM(GRID)
    for it in items:
        b = it.bbox
        for cx in range((b.GetLeft() - clr_iu) // g, (b.GetRight() + clr_iu) // g + 1):
            for cy in range((b.GetTop() - clr_iu) // g, (b.GetBottom() + clr_iu) // g + 1):
                grid[(it.layer, cx, cy)].append(it)
    seen = set()
    for cell in grid.values():
        for i in range(len(cell)):
            a = cell[i]
            for j in range(i + 1, len(cell)):
                b = cell[j]
                key = (a.id, b.id) if a.id < b.id else (b.id, a.id)
                if key in seen:
                    continue
                seen.add(key)
                yield a, b


class _UF:
    def __init__(self):
        self.p = {}

    def find(self, x):
        self.p.setdefault(x, x)
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b):
        self.p[self.find(a)] = self.find(b)


def analyse(board, clearance_mm):
    """Return (violations, same_net) as lists of (item_a, item_b, dist_mm)."""
    clr = pcbnew.FromMM(clearance_mm)
    items = collect(board)
    uf = _UF()
    near = []
    for a, b in _pairs(items, clr):
        if not a.shape.Collide(b.shape, clr):
            continue
        if a.shape.Collide(b.shape, 0):
            uf.union(a.id, b.id)
        else:
            near.append((a, b))
    viol, same = [], []
    for a, b in near:
        rec = (a, b)
        if uf.find(a.id) == uf.find(b.id):
            same.append(rec)
        else:
            viol.append(rec)
    return viol, same


_WHOLE_FP = ("filler", "cap", "testpad", "stitch-pad")


def _uid(obj):
    # SWIG returns a new proxy per lookup; id() of a proxy is not an identity
    return obj.m_Uuid.AsString()


def _keys(it):
    """Identity of what removing `it` would delete (a whole part or one item)."""
    return {("fp", _uid(it.fp))} if it.kind in _WHOLE_FP else {("obj", _uid(it.obj))}


def _touches(it, gone):
    return (("obj", _uid(it.obj)) in gone
            or (it.fp is not None and ("fp", _uid(it.fp)) in gone))


def _remove(board, it):
    if it.kind in _WHOLE_FP:
        board.Remove(it.fp)
    elif it.kind == "ring-pad":
        it.fp.Remove(it.obj)
    else:
        board.Remove(it.obj)


def resolve(board, clearance_mm, max_rounds=8):
    """Remove decoration until no two separate copper features are closer
    than `clearance_mm`. Returns (removed_labels, unresolved_pairs).

    Each round re-analyses from scratch: removing a part can merge or split
    islands, so a pair's verdict is only valid for the board it was computed
    on. Within a round, anything touching an already-removed item is skipped.
    """
    removed = []
    for _ in range(max_rounds):
        viol, _same = analyse(board, clearance_mm)
        if not viol:
            return removed, []
        gone = set()
        progress = False
        for a, b in viol:
            if _touches(a, gone) or _touches(b, gone):
                continue
            victim = min((a, b), key=lambda it: (it.prio, it.id))
            if victim.prio >= FIXED:
                continue
            gone |= _keys(victim)
            removed.append(victim.label())
            _remove(board, victim)
            progress = True
        if not progress:
            break
    viol, _ = analyse(board, clearance_mm)
    return removed, viol


def assign_island_nets(board):
    """Give every connected copper feature its own net.

    With nets, KiCad's own clearance DRC compares the islands against each
    other exactly the way the fab sees them — without, it skips netless copper
    entirely. Touching items share an island and therefore a net, so this
    cannot introduce shorts. Copper text cannot carry a net and stays netless;
    the Gerber-level check covers it.
    """
    items = collect(board)
    uf = _UF()
    for a, b in _pairs(items, 0):
        if a.shape.Collide(b.shape, 0):
            uf.union(a.id, b.id)
    nets = {}
    for it in items:
        if isinstance(it.obj, pcbnew.PCB_TEXT):
            continue
        root = uf.find(it.id)
        if root not in nets:
            n = pcbnew.NETINFO_ITEM(board, f"ISL{len(nets) + 1}")
            board.Add(n)
            nets[root] = n
        it.obj.SetNet(nets[root])
    return len(nets)
