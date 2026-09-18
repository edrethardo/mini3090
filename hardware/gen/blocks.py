"""Reusable "looks like a real GPU board" building blocks.

Each helper places a decorative footprint: real pads on real layers, with the
pitch/size ratios of the part it imitates, so the exported Gerbers carry
genuine artwork rather than a picture of one.
"""

from __future__ import annotations

import math
import random

import pcbnew

from kicadlib import (
    MM, V, arc, circle, gold_rect, gold_stroke, new_fp, poly, polyline,
    rect, rect_c, seg, size, smd_pad, track, track_path, via,
)

CU = {False: pcbnew.F_Cu, True: pcbnew.B_Cu}
MASK = {False: pcbnew.F_Mask, True: pcbnew.B_Mask}
SILK = {False: pcbnew.F_SilkS, True: pcbnew.B_SilkS}
FAB = {False: pcbnew.F_Fab, True: pcbnew.B_Fab}

# --------------------------------------------------------------------------
# placement guard
# --------------------------------------------------------------------------
# A generated board has no router to resolve conflicts, so every small object
# asks the occupancy map whether its area is free before it is placed. Set by
# build.py; when it is None the helpers place unconditionally (useful for
# unit-testing a single block in isolation).

_GUARD = None

# Copper clearance KiCad enforces by default. Pads are reserved with half of
# it on each side so two neighbouring parts end up a full clearance apart.
CLEARANCE = 0.22


def set_guard(occ):
    global _GUARD
    _GUARD = occ


def guard():
    return _GUARD


def _side(back):
    return "back" if back else "front"


def reserve(cx, cy, w, h, back=False, margin=0.0):
    """Mark an area as occupied without placing anything."""
    if _GUARD is None:
        return
    _GUARD.take(cx - w / 2 - margin, cy - h / 2 - margin,
                cx + w / 2 + margin, cy + h / 2 + margin, _side(back))


def area_free(cx, cy, w, h, back=False, margin=CLEARANCE / 2):
    if _GUARD is None:
        return True
    return _GUARD.free(cx - w / 2 - margin, cy - h / 2 - margin,
                       cx + w / 2 + margin, cy + h / 2 + margin, _side(back))


def package_site(cx, cy, w, h, back=False, nudge=0.0):
    """Claim a site, optionally searching nearby when the exact spot is taken.

    Returns the accepted (x, y) or None.
    """
    if _GUARD is None:
        return cx, cy
    site = find_site(cx, cy, w, h, back, radius=nudge) if nudge else (
        (cx, cy) if (inside_board(cx, cy, w, h)
                     and area_free(cx, cy, w, h, back, margin=0.0)) else None)
    if site is None:
        return None
    cx, cy = site
    rs, cs = _GUARD._slice(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)
    if _GUARD.holes[rs, cs].any():
        return None
    reserve(cx, cy, w, h, back)
    return cx, cy


def inside_board(cx, cy, w, h):
    """True when the whole rectangle is inside the copper-safe board area."""
    if _GUARD is None:
        return True
    rs, cs = _GUARD._slice(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)
    if rs.start >= rs.stop or cs.start >= cs.stop:
        return False
    return not _GUARD.forbidden[rs, cs].any()


def find_site(cx, cy, w, h, back=False, radius=6.0, step=0.5):
    """Nearest free site to (cx, cy), or None.

    Fixed coordinates are brittle: move one block and a dozen unrelated parts
    silently vanish because their hardcoded spot is now taken. Callers state
    where a part SHOULD go; this nudges it to where it CAN go, searching
    outward in rings so the result stays close to the intent.
    """
    if _GUARD is None:
        return cx, cy
    if inside_board(cx, cy, w, h) and area_free(cx, cy, w, h, back, margin=0.0):
        return cx, cy
    r = step
    while r <= radius:
        n = max(8, int(2 * math.pi * r / step))
        for i in range(n):
            a = 2 * math.pi * i / n
            x, y = cx + r * math.cos(a), cy + r * math.sin(a)
            if inside_board(x, y, w, h) and area_free(x, y, w, h, back, margin=0.0):
                return x, y
        r += step
    return None


# --------------------------------------------------------------------------
# large packages
# --------------------------------------------------------------------------

def bga(board, ref, cx, cy, sub, pitch, pad, die=0.0, back=False,
        outline=True, corner_marks=True):
    """A flip-chip BGA: substrate outline, dense ball field, die keepout."""
    # Claim only the substrate itself: the stitching rings around it place
    # themselves via area_free and must not push the memory sites away.
    package_site(cx, cy, sub + 0.8, sub + 0.8, back)
    fp = new_fp(board, ref, cx, cy, back=back)
    half = sub / 2.0
    n = int((sub - 2.2) / pitch)
    if n % 2 == 0:
        n -= 1
    span = (n - 1) * pitch
    x0 = cx - span / 2.0
    y0 = cy - span / 2.0
    k = 0
    for iy in range(n):
        for ix in range(n):
            px = x0 + ix * pitch
            py = y0 + iy * pitch
            if die and abs(px - cx) < die / 2.0 and abs(py - cy) < die / 2.0:
                continue
            k += 1
            smd_pad(fp, px, py, pad, pad, shape=pcbnew.PAD_SHAPE_CIRCLE,
                    number=str(k), back=back)
    if outline:
        # substrate edge on silkscreen
        polyline(board, SILK[back],
                 [(cx - half, cy - half), (cx + half, cy - half),
                  (cx + half, cy + half), (cx - half, cy + half)],
                 0.15, close=True)
    if die:
        # exposed-die window rendered in gold
        d = die / 2.0
        gold_stroke(board, back,
                    [(cx - d, cy - d), (cx + d, cy - d),
                     (cx + d, cy + d), (cx - d, cy + d)], 0.25, close=True)
    if corner_marks:
        m = half + 0.55
        polyline(board, SILK[back],
                 [(cx - m, cy - m + 1.4), (cx - m, cy - m), (cx - m + 1.4, cy - m)], 0.2)
        circle(board, SILK[back], cx - half + 0.9, cy - half + 0.9, 0.28, filled=True)
    return fp, k


def gddr6x(board, ref, cx, cy, back=False, w=6.6, h=5.6, pitch=0.5, pad=0.27,
           nudge=2.5):
    """A GDDR6X-style fine-pitch BGA module."""
    site = package_site(cx, cy, w + 0.7, h + 0.7, back, nudge=nudge)
    if site is None:
        return None
    cx, cy = site
    fp = new_fp(board, ref, cx, cy, back=back)
    ncols = int((w - 1.0) / pitch)
    nrows = int((h - 1.0) / pitch)
    sx = (ncols - 1) * pitch
    sy = (nrows - 1) * pitch
    k = 0
    for iy in range(nrows):
        for ix in range(ncols):
            px = cx - sx / 2.0 + ix * pitch
            py = cy - sy / 2.0 + iy * pitch
            k += 1
            smd_pad(fp, px, py, pad, pad, shape=pcbnew.PAD_SHAPE_CIRCLE,
                    number=str(k), back=back)
    polyline(board, SILK[back],
             [(cx - w / 2, cy - h / 2), (cx + w / 2, cy - h / 2),
              (cx + w / 2, cy + h / 2), (cx - w / 2, cy + h / 2)],
             0.13, close=True)
    circle(board, SILK[back], cx - w / 2 + 0.45, cy - h / 2 + 0.45, 0.22, filled=True)
    return fp


def qfn(board, ref, cx, cy, body, pitch=0.5, pad_l=0.75, pad_w=0.25,
        back=False, epad=True, silk=True, nudge=4.0):
    """QFN / DrMOS style package with a thermal pad.

    Pads sit fully OUTSIDE the thermal pad: the lead pads span
    [half - pad_l, half] measured from the body centre, and the e-pad is sized
    so a full clearance remains between them. Getting this wrong produces
    dozens of pad-to-pad clearance errors inside a single part.
    """
    site = package_site(cx, cy, body + 1.6, body + 1.6, back, nudge=nudge)
    if site is None:
        return None
    cx, cy = site
    fp = new_fp(board, ref, cx, cy, back=back)
    per_side = max(2, int((body - 0.8) / pitch))
    span = (per_side - 1) * pitch
    half = body / 2.0
    lead_centre = half - pad_l / 2.0
    # e-pad must clear the inner edge of the lead pads by one clearance
    epad_half = max(0.3, lead_centre - pad_l / 2.0 - CLEARANCE)
    k = 0
    for i in range(per_side):
        off = -span / 2.0 + i * pitch
        k += 1
        smd_pad(fp, cx - lead_centre, cy + off, pad_l, pad_w,
                shape=pcbnew.PAD_SHAPE_ROUNDRECT, number=str(k), back=back)
        k += 1
        smd_pad(fp, cx + lead_centre, cy + off, pad_l, pad_w,
                shape=pcbnew.PAD_SHAPE_ROUNDRECT, number=str(k), back=back)
    for i in range(per_side):
        off = -span / 2.0 + i * pitch
        # Skip the corner columns. The side pads occupy x in
        # [half - pad_l, half]; a top/bottom pad at `off` must clear that
        # band by a full clearance, otherwise the corners of the package
        # collide with each other (a classic generated-footprint bug).
        if abs(off) + pad_w / 2.0 > half - pad_l - CLEARANCE:
            continue
        k += 1
        smd_pad(fp, cx + off, cy - lead_centre, pad_w, pad_l,
                shape=pcbnew.PAD_SHAPE_ROUNDRECT, number=str(k), back=back)
        k += 1
        smd_pad(fp, cx + off, cy + lead_centre, pad_w, pad_l,
                shape=pcbnew.PAD_SHAPE_ROUNDRECT, number=str(k), back=back)
    if epad and epad_half > 0.35:
        smd_pad(fp, cx, cy, 2 * epad_half, 2 * epad_half,
                shape=pcbnew.PAD_SHAPE_ROUNDRECT, number="EP", back=back,
                roundratio=0.08)
    if silk:
        s = half + 0.35
        polyline(board, SILK[back],
                 [(cx - s, cy - s), (cx + s, cy - s), (cx + s, cy + s), (cx - s, cy + s)],
                 0.13, close=True)
        circle(board, SILK[back], cx - s - 0.28, cy - s + 0.25, 0.2, filled=True)
    return fp


def soic(board, ref, cx, cy, npins=8, pitch=1.27, body_w=3.9, pad_l=1.5,
         pad_w=0.6, back=False, nudge=4.0):
    per = npins // 2
    span = (per - 1) * pitch
    site = package_site(cx, cy, body_w + 2 * pad_l + 1.0, span + 2.4, back,
                        nudge=nudge)
    if site is None:
        return None
    cx, cy = site
    fp = new_fp(board, ref, cx, cy, back=back)
    for i in range(per):
        y = cy - span / 2.0 + i * pitch
        smd_pad(fp, cx - body_w / 2 - pad_l / 2 + 0.2, y, pad_l, pad_w,
                shape=pcbnew.PAD_SHAPE_ROUNDRECT, number=str(i + 1), back=back)
        smd_pad(fp, cx + body_w / 2 + pad_l / 2 - 0.2, y, pad_l, pad_w,
                shape=pcbnew.PAD_SHAPE_ROUNDRECT, number=str(npins - i), back=back)
    polyline(board, SILK[back],
             [(cx - body_w / 2, cy - span / 2 - 0.8), (cx + body_w / 2, cy - span / 2 - 0.8),
              (cx + body_w / 2, cy + span / 2 + 0.8), (cx - body_w / 2, cy + span / 2 + 0.8)],
             0.13, close=True)
    return fp


# --------------------------------------------------------------------------
# discretes
# --------------------------------------------------------------------------

_CHIP = {
    "0201": (0.32, 0.36, 0.28),   # pad w, pad h, gap between pad centres offset
    "0402": (0.55, 0.60, 0.50),
    "0603": (0.80, 0.85, 0.75),
    "0805": (1.00, 1.25, 0.95),
    "1206": (1.15, 1.70, 1.50),
}


def chip(board, ref, cx, cy, kind="0402", rot=0.0, back=False, silk=False):
    """Two-terminal discrete. Returns the footprint, or None if the area was
    already occupied (the guard refuses rather than creating a DRC error)."""
    pw, ph, off = _CHIP[kind]
    a = math.radians(rot)
    dx, dy = math.cos(a) * off, math.sin(a) * off
    ext_w = abs(2 * dx) + pw
    ext_h = abs(2 * dy) + ph
    if not area_free(cx, cy, ext_w, ext_h, back):
        return None
    reserve(cx, cy, ext_w, ext_h, back, margin=CLEARANCE / 2)
    fp = new_fp(board, ref, cx, cy, back=back)
    for i, s in enumerate((-1, 1)):
        p = smd_pad(fp, cx + s * dx, cy + s * dy, pw, ph,
                    shape=pcbnew.PAD_SHAPE_ROUNDRECT, number=str(i + 1), back=back)
        if rot:
            p.SetOrientationDegrees(-rot)
    if silk:
        rect_c(board, SILK[back], cx, cy, off * 2 + pw + 0.3, ph + 0.3,
               filled=False, width=0.12)
    return fp


def chip_row(board, prefix, x0, y0, n, dx, dy=0.0, kind="0402", rot=0.0,
             back=False, start=1):
    placed = 0
    for i in range(n):
        if chip(board, f"{prefix}{start + i}", x0 + i * dx, y0 + i * dy,
                kind=kind, rot=rot, back=back):
            placed += 1
    return start + n


def cap_array(board, prefix, x0, y0, cols, rows, dx, dy, kind="0402",
              rot=0.0, back=False, start=1):
    k = start
    for r in range(rows):
        for c in range(cols):
            chip(board, f"{prefix}{k}", x0 + c * dx, y0 + r * dy,
                 kind=kind, rot=rot, back=back)
            k += 1
    return k


def choke(board, ref, cx, cy, w=3.2, h=3.0, back=False, nudge=2.5):
    """Power inductor: two large terminations plus a silk body."""
    site = package_site(cx, cy, w + 0.9, h + 0.9, back, nudge=nudge)
    if site is None:
        return None
    cx, cy = site
    fp = new_fp(board, ref, cx, cy, back=back)
    tw = w * 0.34
    for i, s in enumerate((-1, 1)):
        smd_pad(fp, cx + s * (w / 2 - tw / 2), cy, tw, h * 0.86,
                shape=pcbnew.PAD_SHAPE_ROUNDRECT, number=str(i + 1), back=back)
    polyline(board, SILK[back],
             [(cx - w / 2 - 0.15, cy - h / 2 - 0.15), (cx + w / 2 + 0.15, cy - h / 2 - 0.15),
              (cx + w / 2 + 0.15, cy + h / 2 + 0.15), (cx - w / 2 - 0.15, cy + h / 2 + 0.15)],
             0.13, close=True)
    seg(board, SILK[back], (cx - w / 2 - 0.15, cy), (cx + w / 2 + 0.15, cy), 0.13)
    return fp


def polymer_cap(board, ref, cx, cy, w=3.5, h=2.8, back=False, nudge=2.5):
    site = package_site(cx, cy, w + 0.8, h + 0.8, back, nudge=nudge)
    if site is None:
        return None
    cx, cy = site
    fp = new_fp(board, ref, cx, cy, back=back)
    for i, s in enumerate((-1, 1)):
        smd_pad(fp, cx + s * (w / 2 - 0.45), cy, 0.9, h * 0.8,
                shape=pcbnew.PAD_SHAPE_ROUNDRECT, number=str(i + 1), back=back)
    rect_c(board, SILK[back], cx, cy, w + 0.3, h + 0.3, filled=False, width=0.13)
    seg(board, SILK[back], (cx - w / 2 + 0.1, cy - h / 2), (cx - w / 2 + 0.1, cy + h / 2), 0.25)
    return fp


def testpad(board, ref, cx, cy, d=0.9, back=False, ring=True):
    if not area_free(cx, cy, d, d, back):
        return None
    reserve(cx, cy, d, d, back, margin=CLEARANCE / 2)
    fp = new_fp(board, ref, cx, cy, back=back)
    smd_pad(fp, cx, cy, d, d, shape=pcbnew.PAD_SHAPE_CIRCLE, number="1", back=back)
    if ring:
        circle(board, SILK[back], cx, cy, d / 2 + 0.28, filled=False, width=0.12)
    return fp


def testpad_row(board, prefix, x0, y0, n, dx, dy=0.0, back=False, d=0.9,
                ring=False, start=1):
    for i in range(n):
        testpad(board, f"{prefix}{start + i}", x0 + i * dx, y0 + i * dy,
                d=d, back=back, ring=ring)
    return start + n


def via_field(board, x0, y0, x1, y1, pitch=1.0, drill=0.3, dia=0.6,
              stagger=True, skip=None):
    n = 0
    rows = int((y1 - y0) / pitch) + 1
    cols = int((x1 - x0) / pitch) + 1
    for r in range(rows):
        for c in range(cols):
            x = x0 + c * pitch + (pitch / 2 if (stagger and r % 2) else 0)
            y = y0 + r * pitch
            if x > x1:
                continue
            if skip and skip(x, y):
                continue
            if guarded_via(board, x, y, drill, dia):
                n += 1
    return n


def guarded_via(board, x, y, drill=0.3, dia=0.6):
    """Place a through via only where both sides and the drill map are free."""
    g = guard()
    if g is not None:
        if not g.hole_free(x, y, drill / 2.0):
            return None
        if not (area_free(x, y, dia, dia, False) and area_free(x, y, dia, dia, True)):
            return None
        g.take_hole(x, y, drill / 2.0)
        reserve(x, y, dia, dia, False, margin=CLEARANCE / 2)
        reserve(x, y, dia, dia, True, margin=CLEARANCE / 2)
    return via(board, x, y, drill, dia)


def via_ring(board, cx, cy, r, count, drill=0.3, dia=0.6, arcs=None):
    """Stitching ring around a package.

    `arcs` limits placement to the given (start_deg, end_deg) sectors. Through
    vias show up on BOTH sides, so a full ring here would draw a large dotted
    circle straight across the skyline on the back; the front-side rings are
    therefore restricted to the top and bottom sectors.
    """
    for i in range(count):
        adeg = 360.0 * i / count
        if arcs and not any(a0 <= adeg <= a1 for (a0, a1) in arcs):
            continue
        a = math.radians(adeg)
        guarded_via(board, cx + r * math.cos(a), cy + r * math.sin(a), drill, dia)


def pad_ring(board, cx, cy, r, count, d=0.5, back=False, ref="FR", arcs=None):
    """Same look as a via ring but front-only (plain SMD pads)."""
    fp = new_fp(board, ref, cx, cy, back=back)
    k = 0
    for i in range(count):
        adeg = 360.0 * i / count
        if arcs and not any(a0 <= adeg <= a1 for (a0, a1) in arcs):
            continue
        a = math.radians(adeg)
        px, py = cx + r * math.cos(a), cy + r * math.sin(a)
        if not area_free(px, py, d, d, back):
            continue
        reserve(px, py, d, d, back, margin=CLEARANCE / 2)
        k += 1
        smd_pad(fp, px, py, d, d, shape=pcbnew.PAD_SHAPE_CIRCLE,
                number=str(k), back=back)
    return fp


# --------------------------------------------------------------------------
# routing artwork
# --------------------------------------------------------------------------

def diff_bus(board, layer, x0, y0, x1, y1, pairs, spacing, width=0.14,
             gap=0.16, wiggle=0.0, horizontal=True, rng=None):
    """A bundle of differential-pair style traces with serpentine tuning."""
    rng = rng or random
    for i in range(pairs):
        if horizontal:
            base = y0 + i * spacing
            if base > y1:
                break
            for s in (0, gap):
                pts = [(x0, base + s)]
                if wiggle:
                    steps = max(2, int((x1 - x0) / 2.4))
                    for k in range(1, steps):
                        xx = x0 + (x1 - x0) * k / steps
                        dy = wiggle * (1 if k % 2 else -1) * rng.uniform(0.5, 1.0)
                        pts += [(xx - 0.5, base + s), (xx - 0.2, base + s + dy),
                                (xx + 0.2, base + s + dy), (xx + 0.5, base + s)]
                pts.append((x1, base + s))
                safe_track_path(board, layer, pts, width)
        else:
            base = x0 + i * spacing
            if base > x1:
                break
            for s in (0, gap):
                safe_track_path(board, layer, [(base + s, y0), (base + s, y1)], width)


def fanout(board, layer, cx, cy, half, count, out, width=0.12, side="left"):
    """Escape routing from one edge of a package to a bus channel."""
    for i in range(count):
        t = (i + 0.5) / count
        if side in ("left", "right"):
            y = cy - half + 2 * half * t
            sx = cx - half if side == "left" else cx + half
            ex = sx - out if side == "left" else sx + out
            mid = sx + (ex - sx) * 0.45
            safe_track_path(board, layer,
                            [(sx, y), (mid, y), (ex, cy - half * 0.75 + 1.5 * half * t)],
                            width)
        else:
            x = cx - half + 2 * half * t
            sy = cy - half if side == "top" else cy + half
            ey = sy - out if side == "top" else sy + out
            mid = sy + (ey - sy) * 0.45
            safe_track_path(board, layer,
                            [(x, sy), (x, mid), (cx - half * 0.75 + 1.5 * half * t, ey)],
                            width)


def copper_pour(board, layer, pts, net=None):
    """Static filled copper area (drawn as a filled polygon, not a live zone,
    so the plot is deterministic without a netlist)."""
    return poly(board, layer, pts)


def safe_track(board, layer, a, b, width, back=None):
    """A track that is clipped to the copper-safe board area.

    The outline is stepped, so a long horizontal bus drawn between two x
    coordinates will run off the board near the notches. Rather than
    hand-tuning every bus, the path is sampled and only the runs that lie
    fully inside are emitted.
    """
    if back is None:
        back = pcbnew.IsBackLayer(layer)
    x0, y0 = a
    x1, y1 = b
    length = math.hypot(x1 - x0, y1 - y0)
    steps = max(2, int(length / 0.25))
    run = []
    out = []
    for i in range(steps + 1):
        t = i / steps
        x = x0 + (x1 - x0) * t
        y = y0 + (y1 - y0) * t
        if inside_board(x, y, width + 0.1, width + 0.1):
            run.append((x, y))
        else:
            if len(run) >= 2:
                out.append(track(board, layer, run[0], run[-1], width))
            run = []
    if len(run) >= 2:
        out.append(track(board, layer, run[0], run[-1], width))
    return out


def safe_track_path(board, layer, pts, width):
    out = []
    for i in range(len(pts) - 1):
        out += safe_track(board, layer, pts[i], pts[i + 1], width)
    return out


def hatched_block(board, layer, x0, y0, x1, y1, pitch=0.5, width=0.18,
                  angle=45.0):
    """Cross-hatched copper texture used to suggest plane fills."""
    a = math.radians(angle)
    dx, dy = math.cos(a), math.sin(a)
    span = (x1 - x0) + (y1 - y0)
    n = int(span / pitch)
    for i in range(-n, n):
        c = i * pitch
        # line: p = (x0,y0) + c*normal + t*dir
        nx, ny = -dy, dx
        px, py = x0 + c * nx, y0 + c * ny
        pts = _clip_line(px, py, dx, dy, x0, y0, x1, y1)
        if pts:
            safe_track(board, layer, pts[0], pts[1], width)


def _clip_line(px, py, dx, dy, x0, y0, x1, y1):
    ts = []
    for (num, den) in (((x0 - px), dx), ((x1 - px), dx),
                       ((y0 - py), dy), ((y1 - py), dy)):
        if abs(den) > 1e-9:
            ts.append(num / den)
    if not ts:
        return None
    ts.sort()
    cand = []
    for t in ts:
        x, y = px + t * dx, py + t * dy
        if x0 - 1e-6 <= x <= x1 + 1e-6 and y0 - 1e-6 <= y <= y1 + 1e-6:
            cand.append((x, y))
    if len(cand) < 2:
        return None
    return cand[0], cand[-1]
