"""Berlin skyline on the back side, drawn as PCB copper.

Design intent: the skyline must not read as a clipart sticker. Every landmark
is built from stroked copper paths of trace-like width plus a few solid
polygons, so it looks like routing that happens to form a city. The copper is
exposed through matching B.Mask openings, so ENIG plates it gold.

Coordinates: helper functions take (x, h) with h measured UPWARD from the
skyline baseline; conversion to board coordinates happens in `_p`.
"""

from __future__ import annotations

import math

import pcbnew

from kicadlib import GOLD_BLEED, circle, gold_poly, gold_stroke, polyline
from layout import SKY_BASE

TRACE = 0.22        # nominal skyline stroke width
THIN = 0.16
BOLD = 0.3


def _p(x, h):
    return (x, SKY_BASE - h)


def stroke(board, pts, width=TRACE, close=False):
    gold_stroke(board, True, [_p(x, h) for (x, h) in pts], width, close=close)


def fill(board, pts):
    gold_poly(board, True, [_p(x, h) for (x, h) in pts])


def box(board, x0, x1, h0, h1, width=TRACE):
    stroke(board, [(x0, h0), (x0, h1), (x1, h1), (x1, h0)], width, close=True)


def _sphere(board, cx, h, r):
    """Solid gold disc: the Fernsehturm sphere is the one element that should
    read as a filled shape rather than an outline."""
    cy = SKY_BASE - h
    gold_poly(board, True, _circle_pts(cx, cy, r, 32))


def _circle_pts(cx, cy, r, n=24):
    return [(cx + r * math.cos(2 * math.pi * i / n),
             cy + r * math.sin(2 * math.pi * i / n)) for i in range(n)]


# --------------------------------------------------------------------------
# landmarks
# --------------------------------------------------------------------------

def fernsehturm(board, cx, total_h=23.0):
    """Berliner Fernsehturm, proportioned from the real tower.

    Real dimensions: 368 m to the tip, sphere centre at ~207 m, sphere
    diameter 32 m, shaft base diameter 16 m. Scaled to `total_h` those give
    sphere at 0.562 h, sphere radius 0.0435 h, base half-width 0.022 h — the
    shaft is far more slender than a naive drawing suggests, and that
    slenderness is what makes the silhouette recognisable.
    """
    sphere_h = total_h * 0.562
    sphere_r = total_h * 0.062        # slightly enlarged for legibility at 1:1
    base_w = total_h * 0.092
    neck_w = total_h * 0.030

    def flank(sign):
        pts = []
        steps = 16
        top = sphere_h - sphere_r * 0.35
        for i in range(steps + 1):
            t = i / steps
            h = t * top
            w = base_w * (1 - t) ** 2.2 + neck_w
            pts.append((cx + sign * w / 2.0, h))
        return pts

    stroke(board, flank(-1), TRACE)
    stroke(board, flank(+1), TRACE)
    # a few floor lines only near the base — dense rungs would turn the shaft
    # into a lattice tower and destroy the smooth concrete silhouette
    for i in range(1, 4):
        t = i / 8.0
        h = t * (sphere_h - sphere_r)
        w = (base_w * (1 - t) ** 2.2 + neck_w) / 2.0
        stroke(board, [(cx - w, h), (cx + w, h)], 0.08)

    # plinth / entrance building
    stroke(board, [(cx - 3.2, 0.0), (cx - 2.4, 1.3), (cx + 2.4, 1.3), (cx + 3.2, 0.0)],
           TRACE)
    stroke(board, [(cx - 2.4, 1.3), (cx + 2.4, 1.3)], THIN)
    for i in range(1, 5):
        x = cx - 2.4 + 4.8 * i / 5.0
        stroke(board, [(x, 0.15), (x, 1.15)], 0.08)

    # sphere with the observation deck ring
    _sphere(board, cx, sphere_h, sphere_r)
    stroke(board, [(cx - sphere_r - 0.8, sphere_h - sphere_r * 0.35),
                   (cx + sphere_r + 0.8, sphere_h - sphere_r * 0.35)], 0.22)

    # antenna: a short tapering mast, then the long thin rod to the tip
    mast_base = sphere_h + sphere_r * 0.7
    mast_top = sphere_h + (total_h - sphere_h) * 0.42
    stroke(board, [(cx - neck_w * 0.5, mast_base), (cx - 0.13, mast_top)], 0.16)
    stroke(board, [(cx + neck_w * 0.5, mast_base), (cx + 0.13, mast_top)], 0.16)
    stroke(board, [(cx, mast_top), (cx, total_h)], 0.12)
    for h in (mast_top + 0.6, mast_top + 1.6):
        stroke(board, [(cx - 0.3, h), (cx + 0.3, h)], 0.08)
    circle(board, pcbnew.B_Cu, cx, SKY_BASE - total_h, 0.18)
    circle(board, pcbnew.B_Mask, cx, SKY_BASE - total_h, 0.18 + GOLD_BLEED)


def brandenburger_tor(board, cx, h=9.4):
    """Six columns, entablature, attic and an indicated quadriga."""
    w = 12.4
    x0, x1 = cx - w / 2, cx + w / 2
    plinth_h = 0.85
    col_top = h - 2.75
    arch_h = h - 2.05
    attic_h = h - 0.95

    # stylobate
    stroke(board, [(x0 - 0.5, 0.0), (x1 + 0.5, 0.0)], BOLD)
    stroke(board, [(x0 - 0.35, plinth_h), (x1 + 0.35, plinth_h)], TRACE)
    stroke(board, [(x0 - 0.5, 0.0), (x0 - 0.35, plinth_h)], THIN)
    stroke(board, [(x1 + 0.5, 0.0), (x1 + 0.35, plinth_h)], THIN)

    # six doric columns with fluting
    cols = 6
    span = w - 1.6
    for i in range(cols):
        x = x0 + 0.8 + span * i / (cols - 1)
        cw = 0.82
        stroke(board, [(x - cw / 2, plinth_h), (x - cw / 2, col_top)], TRACE)
        stroke(board, [(x + cw / 2, plinth_h), (x + cw / 2, col_top)], TRACE)
        stroke(board, [(x, plinth_h + 0.2), (x, col_top - 0.2)], 0.1)   # fluting
        # capital + base
        stroke(board, [(x - cw / 2 - 0.22, col_top), (x + cw / 2 + 0.22, col_top)], 0.22)
        stroke(board, [(x - cw / 2 - 0.18, plinth_h), (x + cw / 2 + 0.18, plinth_h)], 0.18)

    # entablature: architrave, frieze, cornice
    stroke(board, [(x0 - 0.45, col_top + 0.3), (x1 + 0.45, col_top + 0.3)], 0.26)
    stroke(board, [(x0 - 0.6, arch_h), (x1 + 0.6, arch_h)], 0.3)
    # frieze detail (triglyph ticks)
    for i in range(13):
        x = x0 + 0.3 + (w - 0.6) * i / 12.0
        stroke(board, [(x, col_top + 0.42), (x, arch_h - 0.12)], 0.1)

    # attic block
    stroke(board, [(x0 + 1.5, arch_h), (x0 + 1.5, attic_h),
                   (x1 - 1.5, attic_h), (x1 - 1.5, arch_h)], TRACE)
    stroke(board, [(x0 + 1.5, attic_h), (x1 - 1.5, attic_h)], 0.24)

    # quadriga: chariot + Victoria + four horses. At ~2 mm tall only the
    # big shapes survive, so the horses are drawn as solid bodies with a
    # single leg pair and a raised head — more legible than fine outlines.
    qy = attic_h
    qx = cx - 2.6
    # chariot wheel + platform
    circle(board, pcbnew.B_Cu, qx - 0.35, SKY_BASE - (qy + 0.45), 0.4,
           filled=False, width=0.13)
    circle(board, pcbnew.B_Mask, qx - 0.35, SKY_BASE - (qy + 0.45), 0.4 + GOLD_BLEED,
           filled=False, width=0.13 + 2 * GOLD_BLEED)
    stroke(board, [(qx - 0.8, qy + 0.9), (qx + 0.1, qy + 0.9)], 0.16)
    # Victoria with her staff
    stroke(board, [(qx - 0.35, qy + 0.9), (qx - 0.35, qy + 1.7)], 0.16)
    circle(board, pcbnew.B_Cu, qx - 0.35, SKY_BASE - (qy + 1.9), 0.19)
    circle(board, pcbnew.B_Mask, qx - 0.35, SKY_BASE - (qy + 1.9), 0.19 + GOLD_BLEED)
    stroke(board, [(qx - 0.05, qy + 2.2), (qx - 0.05, qy + 0.95)], 0.1)
    # four horses as filled bodies, slightly staggered
    for i in range(4):
        hx = qx + 0.55 + i * 0.72
        fill(board, [(hx, qy + 0.62), (hx + 0.78, qy + 0.62),
                     (hx + 0.78, qy + 1.02), (hx, qy + 1.02)])          # body
        stroke(board, [(hx + 0.78, qy + 1.02), (hx + 1.02, qy + 1.52)], 0.13)  # neck
        stroke(board, [(hx + 1.02, qy + 1.52), (hx + 1.34, qy + 1.44)], 0.12)  # head
        stroke(board, [(hx + 0.14, qy + 0.0), (hx + 0.14, qy + 0.62)], 0.11)   # hind leg
        stroke(board, [(hx + 0.68, qy + 0.0), (hx + 0.68, qy + 0.62)], 0.11)   # fore leg


def berliner_dom(board, cx, h=11.2):
    """Cathedral: central drum + dome + lantern, flanked by corner turrets."""
    body_h = h - 5.6
    drum_h = h - 3.4
    x0, x1 = cx - 4.6, cx + 4.6
    box(board, x0, x1, 0.0, body_h)
    # facade bays
    for i in range(1, 5):
        x = x0 + (x1 - x0) * i / 5.0
        stroke(board, [(x, 0.4), (x, body_h - 0.4)], 0.1)
    stroke(board, [(x0 - 0.3, body_h), (x1 + 0.3, body_h)], 0.24)

    # corner turrets with small cupolas
    for s in (-1, 1):
        tx = cx + s * 3.9
        box(board, tx - 0.75, tx + 0.75, body_h, body_h + 1.5, THIN)
        fill(board, [(tx - 0.75, body_h + 1.5), (tx, body_h + 2.5), (tx + 0.75, body_h + 1.5)])

    # drum
    box(board, cx - 2.5, cx + 2.5, body_h, drum_h, TRACE)
    for i in range(1, 5):
        x = cx - 2.5 + 5.0 * i / 5.0
        stroke(board, [(x, body_h + 0.25), (x, drum_h - 0.25)], 0.1)

    # dome (half circle from strokes) + lantern + cross
    r = 2.5
    cy = SKY_BASE - drum_h
    pts = [(cx + r * math.cos(math.pi * i / 22), cy - r * math.sin(math.pi * i / 22))
           for i in range(23)]
    gold_stroke(board, True, pts, 0.24)
    for k in (0.3, 0.6):
        gold_stroke(board, True,
                    [(cx + r * k * math.cos(math.pi * i / 16),
                      cy - r * k * math.sin(math.pi * i / 16)) for i in range(17)], 0.1)
    stroke(board, [(cx - 0.55, drum_h + r), (cx - 0.55, drum_h + r + 0.9),
                   (cx + 0.55, drum_h + r + 0.9), (cx + 0.55, drum_h + r)], THIN)
    stroke(board, [(cx, drum_h + r + 0.9), (cx, drum_h + r + 1.8)], 0.12)
    stroke(board, [(cx - 0.3, drum_h + r + 1.5), (cx + 0.3, drum_h + r + 1.5)], 0.12)


def reichstag(board, cx, h=7.4):
    """Classical block with the modern glass dome."""
    x0, x1 = cx - 5.4, cx + 5.4
    body_h = h - 2.6
    box(board, x0, x1, 0.0, body_h)
    # portico columns
    for i in range(6):
        x = cx - 2.5 + i * 1.0
        stroke(board, [(x, 0.3), (x, body_h - 0.9)], 0.12)
    stroke(board, [(cx - 3.2, body_h - 0.9), (cx + 3.2, body_h - 0.9)], 0.18)
    stroke(board, [(cx - 3.2, body_h - 0.9), (cx, body_h + 0.7), (cx + 3.2, body_h - 0.9)], 0.16)
    # corner towers
    for s in (-1, 1):
        tx = cx + s * 4.6
        box(board, tx - 0.85, tx + 0.85, body_h, body_h + 1.15, THIN)
    # glass dome: half circle + meridians + spiral ramp hint
    r = 1.85
    cy = SKY_BASE - (body_h + 0.7)
    gold_stroke(board, True,
                [(cx + r * math.cos(math.pi * i / 20), cy - r * math.sin(math.pi * i / 20))
                 for i in range(21)], 0.2)
    for k in range(-2, 3):
        xx = cx + k * r * 0.42
        hh = math.sqrt(max(r * r - (k * r * 0.42) ** 2, 0.0))
        gold_stroke(board, True, [(xx, cy), (xx, cy - hh)], 0.1)
    gold_stroke(board, True, [(cx - r, cy), (cx + r, cy)], 0.18)


def siegessaeule(board, cx, h=12.0):
    """Victory column: stepped base, fluted shaft, Victoria on top."""
    stroke(board, [(cx - 2.0, 0.0), (cx + 2.0, 0.0)], BOLD)
    box(board, cx - 1.5, cx + 1.5, 0.0, 1.5, THIN)
    box(board, cx - 1.05, cx + 1.05, 1.5, 2.4, THIN)
    shaft_top = h - 2.4
    for s in (-1, 1):
        stroke(board, [(cx + s * 0.62, 2.4), (cx + s * 0.45, shaft_top)], TRACE)
    for i in range(1, 6):
        hh = 2.4 + (shaft_top - 2.4) * i / 6.0
        stroke(board, [(cx - 0.55, hh), (cx + 0.55, hh)], 0.1)
    stroke(board, [(cx - 0.95, shaft_top), (cx + 0.95, shaft_top)], 0.22)
    box(board, cx - 0.8, cx + 0.8, shaft_top, shaft_top + 0.75, THIN)
    # Victoria
    stroke(board, [(cx, shaft_top + 0.75), (cx, shaft_top + 1.45)], 0.14)
    circle(board, pcbnew.B_Cu, cx, SKY_BASE - (shaft_top + 1.65), 0.18)
    circle(board, pcbnew.B_Mask, cx, SKY_BASE - (shaft_top + 1.65), 0.18 + GOLD_BLEED)
    stroke(board, [(cx, shaft_top + 1.25), (cx + 0.7, shaft_top + 1.7)], 0.1)   # wing
    stroke(board, [(cx, shaft_top + 1.25), (cx - 0.55, shaft_top + 1.6)], 0.1)


def rotes_rathaus(board, cx, h=8.6):
    x0, x1 = cx - 3.6, cx + 3.6
    box(board, x0, x1, 0.0, h - 4.2)
    for i in range(1, 4):
        stroke(board, [(x0 + (x1 - x0) * i / 4, 0.4), (x0 + (x1 - x0) * i / 4, h - 4.6)], 0.1)
    box(board, cx - 1.15, cx + 1.15, h - 4.2, h - 1.1, TRACE)
    for i in range(1, 3):
        stroke(board, [(cx - 1.15, h - 4.2 + (3.1) * i / 3), (cx + 1.15, h - 4.2 + (3.1) * i / 3)], 0.1)
    fill(board, [(cx - 1.3, h - 1.1), (cx, h - 0.1), (cx + 1.3, h - 1.1)])
    stroke(board, [(cx, h - 0.1), (cx, h + 0.55)], 0.12)


def kollhoff_tower(board, cx, h=13.5):
    """Potsdamer Platz: stepped brick tower."""
    steps = [(3.3, 0.0), (2.7, h * 0.52), (2.0, h * 0.74), (1.35, h * 0.9)]
    prev_h = 0.0
    for i, (w, hh) in enumerate(steps):
        top = steps[i + 1][1] if i + 1 < len(steps) else h
        box(board, cx - w / 2, cx + w / 2, hh, top, TRACE if i < 2 else THIN)
        prev_h = top
    # window grid as fine lines
    for i in range(1, 10):
        hh = h * i / 10.0
        w = 3.3 if hh < h * 0.52 else (2.7 if hh < h * 0.74 else (2.0 if hh < h * 0.9 else 1.35))
        stroke(board, [(cx - w / 2 + 0.12, hh), (cx + w / 2 - 0.12, hh)], 0.08)
    stroke(board, [(cx, h), (cx, h + 0.8)], 0.1)


def sony_center(board, cx, h=9.0):
    """Potsdamer Platz forum: a glass slab with the tent roof in front."""
    # slab behind
    box(board, cx - 2.6, cx + 2.6, 0.0, h - 2.6, THIN)
    for i in range(1, 7):
        stroke(board, [(cx - 2.45, (h - 2.6) * i / 7), (cx + 2.45, (h - 2.6) * i / 7)], 0.08)
    # elliptical tent roof: a low arc with radial cable lines to a centre mast
    peak = h
    stroke(board, [(cx - 3.2, h - 2.6), (cx - 2.0, h - 0.7),
                   (cx, peak), (cx + 2.0, h - 0.7), (cx + 3.2, h - 2.6)], 0.2)
    for k in (-0.62, -0.28, 0.28, 0.62):
        stroke(board, [(cx + k * 3.2, h - 2.6), (cx, peak)], 0.08)
    stroke(board, [(cx, peak), (cx, peak + 0.6)], 0.1)


def kaufhaus_block(board, x0, x1, h):
    """A plain commercial block: horizontal band windows, flat roof."""
    box(board, x0, x1, 0.0, h, THIN)
    n = max(3, int(h / 0.9))
    for i in range(1, n):
        stroke(board, [(x0 + 0.18, h * i / n), (x1 - 0.18, h * i / n)], 0.08)
    stroke(board, [(x0 - 0.2, h), (x1 + 0.2, h)], 0.16)


def plattenbau(board, x0, x1, h, rows=6, cols=5):
    box(board, x0, x1, 0.0, h, THIN)
    for i in range(1, rows):
        stroke(board, [(x0 + 0.15, h * i / rows), (x1 - 0.15, h * i / rows)], 0.08)
    for i in range(1, cols):
        x = x0 + (x1 - x0) * i / cols
        stroke(board, [(x, 0.2), (x, h - 0.2)], 0.08)


def oberbaum_hint(board, x0, x1, h=3.2):
    """A bridge arcade grounding the left edge of the skyline."""
    n = 5
    w = (x1 - x0) / n
    stroke(board, [(x0, h), (x1, h)], 0.2)
    stroke(board, [(x0, h + 0.55), (x1, h + 0.55)], 0.12)
    for i in range(n):
        cx = x0 + w * (i + 0.5)
        r = w * 0.42
        cy = SKY_BASE - h
        gold_stroke(board, True,
                    [(cx + r * math.cos(math.pi * k / 14), cy + r * math.sin(math.pi * k / 14))
                     for k in range(15)], 0.12)
    for i in range(n + 1):
        x = x0 + w * i
        stroke(board, [(x, 0.0), (x, h)], 0.12)


# --------------------------------------------------------------------------
# composition
# --------------------------------------------------------------------------

def draw_skyline(board, x0, x1):
    """Place the landmarks across [x0, x1]. No mountains — a city only.

    Slots are explicit and non-overlapping; heights are staged so the
    Fernsehturm dominates, the Gate and the Dom form the mid-ground, and low
    blocks fill the flanks. Positions are given as fractions of the band so the
    composition survives a width change.
    """
    w = x1 - x0

    def at(frac):
        return x0 + w * frac

    stroke(board, [(x0, 0.0), (x1, 0.0)], 0.3)          # horizon rail

    # left flank: quiet low city fabric, no fussy detail
    plattenbau(board, x0 + 0.3, x0 + 3.1, 4.4, rows=5, cols=2)
    kaufhaus_block(board, x0 + 3.8, x0 + 7.2, 5.6)
    plattenbau(board, x0 + 7.9, x0 + 10.2, 3.6, rows=4, cols=2)

    # the Gate is the second hero and needs clear air on both sides
    brandenburger_tor(board, at(0.30), 9.8)

    reichstag(board, at(0.475), 7.6)
    berliner_dom(board, at(0.60), 11.2)

    # hero: the tower, offset right of centre, nothing tall beside it
    fernsehturm(board, at(0.745), 24.0)
    rotes_rathaus(board, at(0.655), 8.2)

    # right flank
    siegessaeule(board, at(0.835), 12.4)
    sony_center(board, at(0.905), 8.8)
    kaufhaus_block(board, x1 - 4.2, x1 - 1.9, 6.2)
    plattenbau(board, x1 - 1.5, x1 - 0.2, 4.4, rows=5, cols=1)
