"""Build ZETTEL3090.kicad_pcb.

The board is a decorative, unpopulated miniature of an RTX 3090 Founders
Edition PCB. Nothing is functional; every object exists so that KiCad's own
plotter produces manufacturing data that LOOKS like a bare GPU board:

  front : GA102-style flip-chip BGA, 12 GDDR6X sites, VRM bank, discretes,
          test points, via fields, fan-out routing, PCIe gold fingers, and a
          deliberately quiet branding area on the right.
  back  : backside memory sites and routing that resolve into a Berlin
          skyline in exposed ENIG gold, plus a real scannable QR code.

Colours are part of the deliverable: black solder mask, white silkscreen,
ENIG gold. These are written into the board stackup so `kicad-cli pcb render`
shows the real thing rather than KiCad's green default.

Usage:  python3 build.py --out /path/ZETTEL3090.kicad_pcb [--total 03]

There is exactly ONE board design. Every board of the edition is made from the
same Gerber set; the front carries "/03" in silkscreen after a blank field of
bare mask, and the individual number (01, 02, 03) is written in by hand after
fabrication. Nothing in the artwork differs between boards.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pcbnew

import layout as L
from blocks import (
    CLEARANCE, area_free, bga, cap_array, chip, chip_row, choke, copper_pour,
    diff_bus, fanout, gddr6x, guarded_via, hatched_block, inside_board,
    package_site, pad_ring, polymer_cap, qfn, reserve, safe_track,
    safe_track_path, set_guard, soic, testpad, testpad_row, via_field,
    via_ring,
)
from occupancy import Occupancy
from clearance import assign_island_nets, resolve
from kicadlib import (
    GOLD_BLEED, MIN_RING, MIN_SPACE, MIN_TRACK, MIN_VIA, MM, V, arc, circle,
    gold_circle, gold_poly, gold_rect, gold_stroke, gold_text, new_fp, npth,
    poly, polyline, rect, rect_c, seg, smd_pad, text, track, track_path, via,
)
from qr import place_qr
from skyline import draw_skyline

F_CU, B_CU = pcbnew.F_Cu, pcbnew.B_Cu
F_MASK, B_MASK = pcbnew.F_Mask, pcbnew.B_Mask
F_SILK, B_SILK = pcbnew.F_SilkS, pcbnew.B_SilkS
EDGE = pcbnew.Edge_Cuts

# Region of the back side reserved for the skyline and the QR code. A through
# via drilled here is visible on BOTH sides, so front-side stitching inside
# this band is replaced by front-only pads.
_PROTECTED = [
    (L.SKY_X0 - 1.0, L.SKY_TOP - 1.0, L.SKY_X1 + 1.0, L.SKY_BASE + 3.0),
    (L.QR_KEEPOUT[0] - 1.0, L.QR_KEEPOUT[1] - 1.0,
     L.QR_KEEPOUT[2] + 1.0, L.QR_KEEPOUT[3] + 1.0),
]

_stitch_seq = [0]
guard_ref = [None]


def protected(x, y):
    return any(x0 <= x <= x1 and y0 <= y <= y1 for (x0, y0, x1, y1) in _PROTECTED)


def stitch(board, x, y, drill=0.3, dia=0.6):
    """Place a stitching via, or a front-only pad where the back is reserved."""
    if not protected(x, y):
        return guarded_via(board, x, y, drill, dia)
    if not area_free(x, y, dia, dia, False):
        return None
    reserve(x, y, dia, dia, False, margin=0.11)
    _stitch_seq[0] += 1
    fp = new_fp(board, f"S{_stitch_seq[0]}", x, y)
    smd_pad(fp, x, y, dia, dia, shape=pcbnew.PAD_SHAPE_CIRCLE, number="1")
    return fp


def stitch_open_areas(board, target=260, pitch=1.1):
    """Scatter through vias wherever BOTH sides are genuinely free.

    Via barrels give a bare board much of its texture, and they are the one
    feature that reads identically from both sides. Hardcoded stitch
    rectangles are fragile — they silently empty out as soon as a neighbouring
    block grows — so this walks the whole board and takes what is actually
    available, after every package and trace has claimed its space.
    """
    placed = 0
    rows = int(L.BOARD_H / pitch)
    cols = int(L.BOARD_W / pitch)
    order = [(r, c) for r in range(rows) for c in range(cols)]
    rng = random.Random(4242)
    rng.shuffle(order)
    for (r, c) in order:
        if placed >= target:
            break
        x = 1.5 + c * pitch + (pitch / 2 if r % 2 else 0)
        y = 1.5 + r * pitch
        if protected(x, y):
            continue
        if guarded_via(board, x, y, 0.3, 0.6):
            placed += 1
    return placed


def stitch_field(board, x0, y0, x1, y1, pitch=1.0, drill=0.3, dia=0.6,
                 stagger=True, skip=None):
    rows = int((y1 - y0) / pitch) + 1
    cols = int((x1 - x0) / pitch) + 1
    for r in range(rows):
        for c in range(cols):
            x = x0 + c * pitch + (pitch / 2 if (stagger and r % 2) else 0)
            y = y0 + r * pitch
            if x > x1 or (skip and skip(x, y)):
                continue
            stitch(board, x, y, drill, dia)


# ==========================================================================
# outline, mounting, card edge
# ==========================================================================

def build_outline(board):
    pts = L.OUTLINE
    for i in range(len(pts)):
        seg(board, EDGE, pts[i], pts[(i + 1) % len(pts)], 0.1)

    g = guard_ref[0]
    for (x, y) in L.MOUNT_HOLES:
        # A gold annulus, not a gold disc: the copper must keep its distance
        # from the drilled hole (0.25 mm hole clearance), so it is drawn as a
        # thick ring stroke whose inner edge clears the barrel.
        inner = L.MOUNT_DRILL / 2.0 + 0.35
        ring_w = L.MOUNT_RING - inner
        mid = (L.MOUNT_RING + inner) / 2.0
        circle(board, F_CU, x, y, mid, filled=False, width=ring_w)
        circle(board, F_MASK, x, y, mid, filled=False, width=ring_w + 0.1)
        circle(board, B_CU, x, y, mid, filled=False, width=ring_w)
        circle(board, B_MASK, x, y, mid, filled=False, width=ring_w + 0.1)
        npth(board, x, y, L.MOUNT_DRILL)
        circle(board, F_SILK, x, y, L.MOUNT_RING + 0.4, filled=False, width=0.15)
        circle(board, B_SILK, x, y, L.MOUNT_RING + 0.4, filled=False, width=0.15)
        # the annulus and its hole own this area on both sides
        r = L.MOUNT_RING + 0.8
        g.take_hole(x, y, L.MOUNT_DRILL / 2.0 + 0.3)
        reserve(x, y, 2 * r, 2 * r, False)
        reserve(x, y, 2 * r, 2 * r, True)


def build_card_edge(board):
    """PCIe-style gold fingers along the bottom protrusion."""
    y0, y1 = L.FINGER_Y0, L.FINGER_Y1
    h = y1 - y0
    for (gx0, gx1) in L.FINGER_GROUPS:
        x = gx0
        while x + L.FINGER_W <= gx1:
            for back in (False, True):
                gold_rect(board, back, x, y0, L.FINGER_W, h)
            x += L.FINGER_PITCH
        # nothing else belongs on the contact area
        for back in (False, True):
            reserve((gx0 + gx1) / 2, (y0 + y1) / 2 - 0.3,
                    gx1 - gx0 + 0.6, h + 1.4, back)
    # chamfer guide + key slot marks on silk
    seg(board, F_SILK, (10.4, y0 - 0.55), (63.6, y0 - 0.55), 0.15)
    for x in (22.6, 24.6):
        seg(board, F_SILK, (x, y0 - 0.4), (x, 47.6), 0.15)


# ==========================================================================
# front side
# ==========================================================================

def place_packages(board, rng):
    """Phase 1: every real package on both sides, on an empty board.

    Packages define the layout; traces, stitching and filler only decorate it.
    Interleaving the two lets a via or a fan-out claim a package's site and the
    guard then silently drops the package — which is how memory modules and
    controller ICs went missing. Phase 1 runs before any decoration exists.

    Each helper may nudge a part to the nearest free spot, so the ACCEPTED
    position is recorded in `SITES`; phase 2 decorates the position a part
    actually got, never the position it was asked for.
    """
    cx, cy = L.GPU_CX, L.GPU_CY
    bga(board, "U1", cx, cy, L.GPU_SUB, pitch=0.8, pad=0.42, die=L.GPU_DIE)
    SITES["U1"] = (cx, cy)

    for i, (mx, my) in enumerate(L.FRONT_MEM, start=1):
        remember(f"U{10 + i}", gddr6x(board, f"U{10 + i}", mx, my))
    for i, (mx, my) in enumerate(L.BACK_MEM, start=1):
        remember(f"U{30 + i}", gddr6x(board, f"U{30 + i}", mx, my, back=True))

    # VRM power stages
    x0 = L.VRM_X0
    for i in range(6):
        y = 7.5 + i * 5.9
        if y > 41:
            break
        remember(f"Q{i + 1}", qfn(board, f"Q{i + 1}", x0 + 1.9, y, 3.0,
                                  pitch=0.65, pad_l=0.9, pad_w=0.3))
        remember(f"L{i + 1}", choke(board, f"L{i + 1}", x0 + 7.4, y, 4.2, 3.6))
        polymer_cap(board, f"C{200 + i}", x0 + 12.6, y - 1.35, 3.2, 2.0)
        polymer_cap(board, f"C{210 + i}", x0 + 12.6, y + 1.35, 3.2, 2.0)
    remember("U30", qfn(board, "U30", x0 + 16.8, 24.0, 4.4,
                        pitch=0.5, pad_l=0.9, pad_w=0.25))

    # support ICs, front and back
    for (x, y, body, ref) in [(16.5, 6.2, 2.4, "U50"), (16.5, 41.8, 2.4, "U51"),
                              (57.5, 6.2, 2.0, "U52"), (57.5, 41.8, 2.0, "U53"),
                              (11.5, 24.0, 2.6, "U54")]:
        remember(ref, qfn(board, ref, x, y, body, pitch=0.5, pad_l=0.8, pad_w=0.24))
    remember("U60", qfn(board, "U60", 12.0, 41.5, 2.6, pitch=0.5,
                        pad_l=0.8, pad_w=0.24, nudge=5.0))
    remember("U61", soic(board, "U61", 10.5, 36.0, npins=8, nudge=5.0))
    # Back-side controllers sit in the strip below the QR keepout (which ends
    # at y = 38.5) and above the card edge — the only back-side area that is
    # neither skyline band nor QR.
    # The usable strip is only ~4 mm tall (QR keepout ends at y = 38.5, the
    # copper-safe edge at y = 43.4), so these are small QFNs, not SOICs: an
    # 8-pin SOIC is 6.2 mm across its pad span and simply does not fit.
    remember("U70", qfn(board, "U70", 87.0, 40.9, 2.6, pitch=0.5, pad_l=0.8,
                        pad_w=0.24, back=True, nudge=2.0))
    remember("U71", qfn(board, "U71", 93.0, 40.9, 2.6, pitch=0.5, pad_l=0.8,
                        pad_w=0.24, back=True, nudge=2.0))
    remember("U72", qfn(board, "U72", 99.0, 40.9, 2.6, pitch=0.5, pad_l=0.8,
                        pad_w=0.24, back=True, nudge=2.0))

    build_power_input(board)
    build_display_connectors(board)


SITES = {}


def remember(ref, fp):
    """Record where a package actually landed (helpers may nudge)."""
    if fp is None:
        MISSING.append(ref)
        return None
    p = fp.GetPosition()
    SITES[ref] = (p.x / 1e6, p.y / 1e6)
    return fp


MISSING = []


def site(ref, fallback=None):
    return SITES.get(ref, fallback)


# ==========================================================================
# front side
# ==========================================================================

def build_front(board, total, rng):
    cx, cy = L.GPU_CX, L.GPU_CY
    half = L.GPU_SUB / 2.0

    # --- substrate plane under the GPU (dark, with a gold die window) -----
    rect_c(board, pcbnew.F_Fab, cx, cy, L.GPU_SUB, L.GPU_SUB, filled=False, width=0.12)

    # Package designators: the top edge is crowded by the U11..U14 memory
    # labels, so the part name sits below the substrate where there is air.
    text(board, F_SILK, "U1   GA102-Z", cx, cy + half + 1.3, 0.9, 0.16)

    # Exposed die: a plain solid gold plate, no marking on it.
    d = L.GPU_DIE / 2.0 - 0.55
    gold_rect(board, False, cx - d, cy - d, 2 * d, 2 * d)

    # substrate stiffener / bracket corners in silk
    for sx in (-1, 1):
        for sy in (-1, 1):
            x = cx + sx * (half + 1.25)
            y = cy + sy * (half + 1.25)
            polyline(board, F_SILK,
                     [(x - sx * 1.5, y), (x, y), (x, y - sy * 1.5)], 0.22)

    # stitching around the package: top and bottom sectors only, so the back
    # side keeps a clean sky above the skyline
    pad_ring(board, cx, cy, half + 1.9, 72, 0.5, ref="FR1",
             arcs=[(200, 340), (20, 160)])
    pad_ring(board, cx, cy, half + 2.6, 60, 0.5, ref="FR2",
             arcs=[(205, 335), (25, 155)])

    # --- GDDR6X decoration (phase 2: the packages already exist) ---------
    for i in range(1, len(L.FRONT_MEM) + 1):
        pos = site(f"U{10 + i}")
        if pos is None:
            continue
        mx, my = pos
        text(board, F_SILK, f"U{10 + i}", mx, my + L.MEM_H / 2 + 0.75, 0.8, 0.15)
        for row, dy in ((0, -(L.MEM_H / 2 + 1.25)), (1, L.MEM_H / 2 + 1.75)):
            cap_array(board, f"C{100 + i * 10 + row}", mx - 2.5, my + dy,
                      6, 1, 1.0, 0.0, kind="0201", start=1)
        side = "right" if mx < cx else "left"
        if abs(my - cy) > 8:
            side = "bottom" if my < cy else "top"
        fanout(board, F_CU, mx, my, L.MEM_H / 2, 11, 2.6, 0.15, side=side)

    # memory bus channels between GPU and memory
    rngs = [
        (24.0, 12.6, 52.0, 13.4),
        (24.0, 34.6, 52.0, 35.4),
    ]
    for (x0, y0, x1, y1) in rngs:
        diff_bus(board, F_CU, x0, y0, x1, y1, pairs=3, spacing=0.42,
                 width=0.13, gap=0.17, wiggle=0.22, rng=rng)
    diff_bus(board, F_CU, 15.0, 15.0, 19.4, 33.0, pairs=6, spacing=0.5,
             width=0.13, gap=0.18, horizontal=False)
    diff_bus(board, F_CU, 50.4, 15.0, 55.0, 33.0, pairs=6, spacing=0.5,
             width=0.13, gap=0.18, horizontal=False)

    # --- VRM bank (right of the GPU) -------------------------------------
    build_vrm(board, rng)

    # --- power input / NVLink style headers ------------------------------
    build_power_input(board)

    # --- display output area (left edge, bracket side) -------------------
    build_display_area(board, rng)

    # --- quiet branding area (claims its block before the filler runs) ---
    field = build_branding(board, total)

    # --- scattered detail: discretes, test points, small ICs -------------
    build_front_detail(board, rng)
    return field


def build_vrm(board, rng):
    """VRM decoration (phase 2). The DrMOS/choke/cap packages already exist.

    A real board pours a solid phase-output plane here, but a decorative board
    has no nets, so any pour touching two pads is reported as a short. The
    copper therefore stays in the channels BETWEEN the parts.
    """
    x0 = L.VRM_X0
    for i in range(6):
        lpos = site(f"L{i + 1}")
        qpos = site(f"Q{i + 1}")
        if lpos is None:
            continue
        lx, ly = lpos
        text(board, F_SILK, f"L{i + 1}", lx, ly + 2.6, 0.8, 0.15)
        cap_array(board, f"C{220 + i * 6}", x0 - 1.5, ly - 1.3, 1, 3, 1.0, 1.3,
                  kind="0402", rot=90)
        # phase interconnect: heavy traces in the gap between DrMOS and choke
        if qpos:
            qx, qy = qpos
            for k in range(3):
                safe_track(board, F_CU, (qx + 1.9, qy - 0.6 + k * 0.6),
                           (lx - 2.3, ly - 0.6 + k * 0.6), 0.4)
        for k in range(4):
            stitch(board, lx - 1.2 + k * 1.5, ly - 2.75, 0.3, 0.6)
            stitch(board, lx - 1.2 + k * 1.5, ly + 2.75, 0.3, 0.6)

    upos = site("U30")
    if upos:
        ux, uy = upos
        text(board, F_SILK, "U30", ux, uy + 3.3, 0.8, 0.15)
        cap_array(board, "C300", ux - 2.4, uy - 5.8, 2, 3, 1.1, 1.15, kind="0402")
        testpad_row(board, "TP", ux - 2.2, uy + 6.4, 5, 1.35, back=False, d=0.8)

    # input rail: hatched copper, which reads as a plane without shorting pads
    hatched_block(board, F_CU, x0 - 3.0, 4.4, x0 + 18.0, 5.8, pitch=0.55, width=0.16)
    hatched_block(board, F_CU, x0 - 3.0, 41.8, x0 + 18.0, 43.0, pitch=0.6, width=0.16)


def build_power_input(board):
    """12VHPWR-style connector footprint.

    The outline steps down at y = 6 for x > 72, so the connector body sits
    fully below that step (y >= 7.4) — placing it at the nominal top edge
    puts half its pads off the board.
    """
    spot = package_site(92.0, 10.4, 13.4, 6.4, False, nudge=4.0)
    if spot is None:
        return
    jx, cy = spot
    SITES["J1"] = (jx, cy)
    fp = new_fp(board, "J1", jx, cy)
    for i in range(6):
        for row in (0, 1):
            smd_pad(fp, jx - 4.0 + i * 1.6, cy - 1.1 + row * 2.2, 1.1, 1.5,
                    shape=pcbnew.PAD_SHAPE_ROUNDRECT, number=str(i + 1 + row * 6))
    for i in range(2):
        smd_pad(fp, jx - 5.4 + i * 10.8, cy, 0.9, 0.9,
                shape=pcbnew.PAD_SHAPE_CIRCLE, number=f"S{i}")
    polyline(board, F_SILK,
             [(jx - 6.2, cy - 3.0), (jx + 6.2, cy - 3.0),
              (jx + 6.2, cy + 3.0), (jx - 6.2, cy + 3.0)], 0.15, close=True)
    text(board, F_SILK, "J1  12V-HPWR", jx, cy + 3.9, 0.85, 0.15)


def build_display_connectors(board):
    """Phase 1: bracket-side connectors (three DP + one HDMI).

    The left mounting holes sit at y = 4.2 and 40.2, so the connector column
    runs between them rather than colliding with their gold annuli. Only pads
    and outlines here — the routing that leaves them is phase-2 decoration.
    """
    for i in range(3):
        spot = package_site(4.3, 11.0 + i * 7.6, 6.6, 7.0, False, nudge=3.0)
        if spot is None:
            continue
        jx, y = spot
        fp = new_fp(board, f"J{10 + i}", jx, y)
        for k in range(10):
            smd_pad(fp, jx - 1.9 + (k % 5) * 0.9, y - 2.0 + (k // 5) * 4.0, 0.45, 1.3,
                    shape=pcbnew.PAD_SHAPE_ROUNDRECT, number=str(k + 1))
        SITES[f"J{10 + i}"] = (jx, y)

    spot = package_site(5.0, 33.8, 8.2, 4.6, False, nudge=3.0)
    if spot is not None:
        jx, jy = spot
        fp = new_fp(board, "J20", jx, jy)
        for k in range(9):
            smd_pad(fp, jx - 2.8 + k * 0.7, jy, 0.4, 2.2,
                    shape=pcbnew.PAD_SHAPE_ROUNDRECT, number=str(k + 1))
        SITES["J20"] = (jx, jy)


def build_display_area(board, rng):
    """Phase 2: outlines, labels and escape routing for the connectors."""
    for i in range(3):
        pos = site(f"J{10 + i}")
        if pos is None:
            continue
        jx, y = pos
        polyline(board, F_SILK,
                 [(jx - 2.7, y - 3.0), (jx + 2.5, y - 3.0),
                  (jx + 2.5, y + 3.0), (jx - 2.7, y + 3.0)], 0.15, close=True)
        text(board, F_SILK, f"J{10 + i}", jx + 3.9, y, 0.8, 0.15)
        diff_bus(board, F_CU, jx + 5.1, y - 1.6, jx + 9.5, y + 1.6, pairs=4,
                 spacing=0.9, width=0.15, gap=0.18, wiggle=0.18, rng=rng)
        for k in range(6):
            stitch(board, jx + 9.9 + (k % 3) * 0.8, y - 1.2 + (k // 3) * 2.4, 0.3, 0.6)

    pos = site("J20")
    if pos:
        jx, jy = pos
        polyline(board, F_SILK,
                 [(jx - 3.4, jy - 1.8), (jx + 3.2, jy - 1.8),
                  (jx + 3.2, jy + 1.8), (jx - 3.4, jy + 1.8)], 0.15, close=True)
        text(board, F_SILK, "J20 HDMI", jx + 4.8, jy, 0.8, 0.15)


def build_front_detail(board, rng):
    """Density: the board should read as busy from arm's length.

    Real boards are dense but ORDERLY — parts sit on a fine grid in rows. A
    purely random scatter reads as noise, so the discretes are snapped to a
    1.6 mm grid with a per-row orientation.
    """
    # small support ICs — placed BEFORE the filler so they win their site
    for (x, y, body) in [(16.5, 6.2, 2.4), (16.5, 41.8, 2.4), (57.5, 6.2, 2.0),
                         (57.5, 41.8, 2.0), (11.5, 24.0, 2.6)]:
        qfn(board, f"U{40 + int(x)}", x, y, body, pitch=0.5, pad_l=0.8, pad_w=0.24)
    soic(board, "U60", 66.5, 41.2, npins=8, back=False)
    soic(board, "U61", 10.0, 36.5, npins=8, back=False)

    # test points along quiet corridors
    testpad_row(board, "TPA", 6.0, 45.4, 4, 1.4, d=0.8)
    testpad_row(board, "TPB", 70.0, 41.2, 4, 1.5, d=0.8)

    # stitching fields in the open copper areas
    stitch_field(board, 62.0, 44.8, 78.0, 46.6, pitch=1.2)
    stitch_field(board, 8.5, 20.0, 12.5, 30.0, pitch=1.3)

    # routing bundles that tie the board together — drawn BEFORE the filler
    # so the guard sees them as occupied
    diff_bus(board, F_CU, 16.5, 44.8, 60.0, 46.6, pairs=4, spacing=0.5,
             width=0.14, gap=0.18, wiggle=0.2, rng=rng)
    for i in range(12):
        y = 2.2 + i * 0.34
        safe_track_path(board, F_CU, [(22.0, y), (56.0, y)], 0.14)

    # Via stitching and the discrete filler run LAST, from main(), once both
    # sides are fully decorated — see fill_density().


def fill_density(board, rng):
    """Final phase: via stitching, then discrete filler.

    Runs after BOTH sides are complete. Vias go first because they need both
    sides free — the scarcest resource on the board — while a 0201 fits almost
    anywhere; the other order starves the via field, and via barrels are what
    make a bare board read as a bare board.
    """
    vias = stitch_open_areas(board, target=300)

    # Density filler last: it fills whatever space is genuinely left.
    #
    # The occupancy guard is the only arbiter here — the old hand-written
    # keepout rectangles are gone, because they blocked large regions that
    # were in fact free while missing the collisions that mattered. Grid pitch
    # must exceed the widest part plus a clearance (0603 is 2.3 mm long), or
    # horizontal neighbours reject each other and the board stays empty.
    kinds = ["0201", "0201", "0201", "0402", "0402", "0603"]
    placed = 0
    gx, gy = 1.35, 1.25
    cols = int((L.BOARD_W - 4.0) / gx)
    rows = int((L.BOARD_H - 4.0) / gy)
    order = [(r, c) for r in range(rows) for c in range(cols)]
    rng.shuffle(order)
    for (r, c) in order:
        if placed >= 900:
            break
        x = 2.0 + c * gx + (gx / 2 if r % 2 else 0)
        y = 2.0 + r * gy
        if rng.random() < 0.22:          # leave breathing room
            continue
        kind = rng.choice(kinds)
        if chip(board, f"R{800 + placed}", x, y, kind=kind,
                rot=90 if r % 2 else 0):
            placed += 1
    # a lighter back-side scatter: the skyline needs quiet around it
    back_placed = 0
    rng.shuffle(order)
    for (r, c) in order:
        if back_placed >= 260:
            break
        x = 2.0 + c * gx + (gx / 2 if r % 2 else 0)
        y = 2.0 + r * gy
        if protected(x, y) or rng.random() < 0.45:
            continue
        if chip(board, f"R{2000 + back_placed}", x, y,
                kind=rng.choice(kinds), rot=90 if r % 2 else 0, back=True):
            back_placed += 1
    return vias, placed, back_placed


def build_branding(board, total):
    """Quiet, high-value branding block on the right front side.

    Vertical rhythm is fixed here so nothing collides: rule, wordmark, rule,
    two caption lines, the edition marking, footnote. Every y is stated
    explicitly rather than derived, because this is the one area a reader
    looks at closely.

    Returns the geometry of the hand-numbering field for the verifier.
    """
    cx = (L.QUIET_X0 + L.QUIET_X1) / 2.0

    # the whole block is off limits to the density filler
    reserve(cx, (L.QUIET_Y0 + L.QUIET_Y1) / 2.0,
            L.QUIET_X1 - L.QUIET_X0 + 2.0, L.QUIET_Y1 - L.QUIET_Y0 + 2.0, False)

    # Framing rules. The right mounting holes sit at x = 103.6, y = 9.4 / 40.6,
    # so the rules stop short of them rather than running through the annulus.
    gold_stroke(board, False, [(L.QUIET_X0, 15.0), (L.QUIET_X1, 15.0)], 0.18)
    gold_stroke(board, False, [(L.QUIET_X0, 38.4), (100.6, 38.4)], 0.18)

    gold_text(board, False, "ZETTEL", cx, 20.3, 5.2, 0.82)
    seg(board, F_SILK, (cx - 8.5, 23.6), (cx + 8.5, 23.6), 0.15)

    text(board, F_SILK, "NEMOTRON 3.5", cx, 25.6, 1.45, 0.23)
    text(board, F_SILK, "GTC BERLIN 2026", cx, 27.8, 1.45, 0.23)

    field = build_number_field(board, cx, total)

    text(board, F_SILK, "RTX 3090   .   LOCAL   .   24 GB", cx, 36.2, 0.85, 0.15)
    return field


def build_number_field(board, cx, total):
    """"/03" in silkscreen, preceded by a blank field for a hand-written number.

    All boards come from one Gerber set, so the number cannot be in the
    artwork. The field is bare matt-black mask: no silk, no copper (copper
    under mask shows as a raised, glossier patch and would make the paint pen
    skip), no mask opening. The group [field]/03 is centred as a unit so the
    finished "01/03" sits on the block's axis like the lines above it.

    No frame or corner marks: the blank black field stays completely clean,
    so nothing competes with the number written into it.
    """
    fw, fh, cy = L.NUM_FIELD_W, L.NUM_FIELD_H, L.NUM_FIELD_CY

    # set "/03" once to measure its real ink width, then place the group
    label = text(board, F_SILK, f"/{total}", 0.0, cy, L.NUM_TEXT_H, L.NUM_TEXT_W,
                 hjustify=pcbnew.GR_TEXT_H_ALIGN_LEFT)
    bb = label.GetBoundingBox()
    ink_w = (bb.GetRight() - bb.GetLeft()) / 1e6
    group_w = fw + L.NUM_GAP + ink_w
    x0 = cx - group_w / 2.0
    x1 = x0 + fw
    y0, y1 = cy - fh / 2.0, cy + fh / 2.0
    # shift so the INK (not the anchor) starts exactly NUM_GAP after the field
    label.Move(pcbnew.VECTOR2I(MM(x1 + L.NUM_GAP) - bb.GetLeft(), 0))

    # nothing else may come near the writing surface. A front reservation also
    # keeps through vias out: guarded_via needs BOTH sides free.
    c = L.NUM_FIELD_CLEAR
    reserve((x0 + x1) / 2, cy, fw + 2 * c, fh + 2 * c, False)
    lb = label.GetBoundingBox()
    return {
        "field_mm": [round(x0, 3), round(y0, 3), round(x1, 3), round(y1, 3)],
        "label": f"/{total}",
        "label_bbox_mm": [round(lb.GetLeft() / 1e6, 3), round(lb.GetTop() / 1e6, 3),
                          round(lb.GetRight() / 1e6, 3), round(lb.GetBottom() / 1e6, 3)],
        "label_height_mm": L.NUM_TEXT_H,
        "label_stroke_mm": L.NUM_TEXT_W,
        "clear_margin_mm": c,
    }


# ==========================================================================
# back side
# ==========================================================================

def build_back(board, rng):
    """Back side: a technical GPU backside whose centre resolves into Berlin.

    Everything is kept OUT of two bands: the skyline band and the QR keepout.
    The memory sites therefore run along the top edge and the left flank, which
    is also where a real board carries its backside DRAM and caps.
    """
    # Phase 2 only: the packages were placed in place_packages().
    # Designators go ABOVE the top-row modules; the caption line below them
    # would otherwise collide with the NEMOTRON/GTC line at y = 10.6.
    for i in range(1, len(L.BACK_MEM) + 1):
        pos = site(f"U{30 + i}")
        if pos is None:
            continue
        mx, my = pos
        text(board, B_SILK, f"U{30 + i}", mx, my - L.MEM_H / 2 - 0.85, 0.8, 0.15)
        cap_array(board, f"C{400 + i * 8}", mx - 2.0, my + L.MEM_H / 2 + 1.1,
                  4, 1, 1.35, 1.0, kind="0201", back=True)

    # Capacitor banks along the free edges. They must clear the back branding
    # block at x = 96 (ZETTEL + serial, y = 8.4 .. 10.6), so they stay left of
    # x = 70.
    cap_array(board, "C500", 16.0, 12.6, 6, 1, 1.4, 0.0, kind="0603", back=True)
    cap_array(board, "C540", 16.0, 14.4, 6, 1, 1.4, 0.0, kind="0603", back=True)
    cap_array(board, "C560", 40.0, 12.6, 5, 1, 1.4, 0.0, kind="0603", back=True)
    cap_array(board, "C580", 40.0, 14.4, 5, 1, 1.4, 0.0, kind="0603", back=True)
    # U70..U72 stay UNLABELLED: they live in a ~4 mm strip between the QR's
    # URL caption and the card edge, and any designator there collides with
    # one or the other. Real boards leave small parts unlabelled too.
    testpad_row(board, "TPX", 20.0, 44.8, 10, 1.6, back=True, d=0.85)
    testpad_row(board, "TPY", 66.0, 45.4, 6, 1.5, back=True, d=0.85)

    # technical routing above the skyline: a horizon of fine traces. The bus
    # at y = 11.6 lies inside the protected skyline band, which exists to keep
    # vias and filler out — deliberate routing may enter it, so that bus is
    # unguarded; the final clearance pass still measures it.
    for i in range(8):
        y = 2.0 + i * 0.34
        safe_track_path(board, B_CU, [(20.0, y), (78.0, y)], 0.12)
    diff_bus(board, B_CU, 20.0, 11.6, 78.0, 12.6, pairs=2, spacing=0.46,
             width=0.13, gap=0.17, wiggle=0.2, rng=rng, guarded=False)
    diff_bus(board, B_CU, 20.0, 44.0, 62.0, 45.0, pairs=2, spacing=0.44,
             width=0.13, gap=0.17, wiggle=0.2, rng=rng)

    # the skyline itself, in exposed ENIG gold
    draw_skyline(board, L.SKY_X0, L.SKY_X1)

    # stitched ground rail below the skyline ties the city into the routing
    stitch_field(board, 20.0, L.SKY_BASE + 0.9, 78.0, L.SKY_BASE + 1.5, pitch=1.5,
                 drill=0.25, dia=0.5)
    # caption sits between the rail and the card-edge fingers (fingers start at
    # y = FINGER_Y0, so this line must stay clear of them)
    text(board, B_SILK, "BERLIN  52.5200 N  13.4050 E", 47.0,
         L.SKY_BASE + 4.0, 0.9, 0.16)

    # QR code + its keepout (nothing else may enter this rectangle)
    module, extent, info = place_qr(board, L.QR_CENTER[0], L.QR_CENTER[1],
                                    L.QR_TARGET_SIZE, back=True)
    text(board, B_SILK, "github.com/edrethardo/zettel", L.QR_CENTER[0],
         L.QR_CENTER[1] + extent / 2 + 1.5, 0.8, 0.14)

    # Back branding sits in the strip between the board's top step (y = 6 for
    # x > 72) and the QR keepout (y >= 11.5) — the only clear area on this
    # side of the back. The edition marking lives on the FRONT only: one
    # hand-numbered field per board, not two that could disagree.
    reserve(L.QR_CENTER[0], 9.5, 22.0, 4.6, True)
    text(board, B_SILK, "ZETTEL", L.QR_CENTER[0], 9.2, 2.0, 0.3)
    text(board, B_SILK, "NEMOTRON 3.5   .   GTC BERLIN 2026", 47.0,
         L.SKY_BASE + 2.2, 1.0, 0.18)
    return info


# ==========================================================================
# board setup: colours, stackup, design rules
# ==========================================================================

def apply_stackup_and_rules(board):
    """Board-level manufacturing settings.

    PCBWay standard 2-layer process at 6/6 mil: 0.1524 mm track and space,
    0.3 mm drill, 0.15 mm annular ring (0.6 mm via), 0.3 mm copper to edge.
    The board's own minimum is set a little above that (0.16 mm) so every
    number has margin; the Gerber-level checker proves both 6 and 4 mil.
    """
    ds = board.GetDesignSettings()
    ds.SetCopperLayerCount(2)
    ds.SetBoardThickness(MM(1.6))
    for key, val in [("m_TrackMinWidth", MM(MIN_TRACK)),
                     ("m_MinClearance", MM(MIN_SPACE)),
                     ("m_ViasMinSize", MM(MIN_VIA)),
                     ("m_ViasMinAnnularWidth", MM(MIN_RING)),
                     ("m_MinThroughDrill", MM(0.3)),
                     ("m_HoleClearance", MM(0.25)),
                     ("m_HoleToHoleMin", MM(0.25)),
                     ("m_CopperEdgeClearance", MM(0.4)),
                     ("m_MinSilkTextHeight", MM(0.8)),
                     ("m_MinSilkTextThickness", MM(0.15))]:
        setattr(ds, key, val)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--total", default=L.EDITION,
                    help='edition size printed after the slash, e.g. "03"')
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, default=30902026)
    ap.add_argument("--info", default="")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    board = pcbnew.BOARD()
    apply_stackup_and_rules(board)

    # Placement guard. Build order matters: the outline and the two reserved
    # bands are claimed first, then the large packages, and only afterwards
    # the density filler — so a filler part can never displace a landmark.
    occ = Occupancy(L.BOARD_W, L.BOARD_H, L.OUTLINE, edge_clearance=0.6)
    guard_ref[0] = occ
    set_guard(occ)

    # reserved bands on the back: skyline + QR keepout
    for (x0, y0, x1, y1) in _PROTECTED:
        occ.take(x0, y0, x1, y1, "back")

    build_outline(board)
    build_card_edge(board)
    place_packages(board, rng)
    field = build_front(board, args.total, rng)
    qr_info = build_back(board, rng)
    vias, front_chips, back_chips = fill_density(board, rng)

    # The occupancy guard works on rectangles and misses diagonal near-misses;
    # this pass measures the real copper shapes and drops decoration until no
    # two separate copper features are closer than the fab can etch.
    removed, unresolved = resolve(board, MIN_SPACE)
    if unresolved:
        for a, b in unresolved[:20]:
            print(f"UNRESOLVED clearance: {a.label()}  <->  {b.label()}",
                  file=sys.stderr)
        sys.exit(f"{len(unresolved)} clearance conflicts between fixed artwork")
    islands = assign_island_nets(board)

    pcbnew.SaveBoard(args.out, board)

    fps = list(board.GetFootprints())
    stats = {
        "total": args.total,
        "out": args.out,
        "footprints": len(fps),
        "pads": len(list(board.GetPads())),
        "tracks": len(list(board.GetTracks())),
        "drawings": len(list(board.GetDrawings())),
        "qr": qr_info,
        "number_field": field,
        "vias": vias,
        "filler_chips": {"front": front_chips, "back": back_chips},
        "clearance_removed": len(removed),
        "copper_islands": islands,
        "missing_packages": MISSING,
    }
    print(json.dumps(stats, indent=2))
    if args.info:
        with open(args.info, "w") as fh:
            json.dump(stats, fh, indent=2)


if __name__ == "__main__":
    main()
