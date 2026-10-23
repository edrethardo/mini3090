"""Primitive helpers on top of the pcbnew Python API.

Everything in this project is decorative: no netlist, no schematic. We still
build real board objects (pads, tracks, vias, copper polygons, mask openings)
so that KiCad itself produces the manufacturing data.

Coordinate convention: millimetres, x to the right, y downward, board origin at
the top-left corner of the 110 x 48 mm bounding box.
"""

from __future__ import annotations

import math

import pcbnew

MM = pcbnew.FromMM


def V(x: float, y: float) -> "pcbnew.VECTOR2I":
    return pcbnew.VECTOR2I(MM(x), MM(y))


def size(w: float, h: float) -> "pcbnew.VECTOR2I":
    return pcbnew.VECTOR2I(MM(w), MM(h))


# --------------------------------------------------------------------------
# graphic primitives
# --------------------------------------------------------------------------

def seg(board, layer, a, b, width):
    s = pcbnew.PCB_SHAPE(board)
    s.SetShape(pcbnew.SHAPE_T_SEGMENT)
    s.SetStart(V(*a))
    s.SetEnd(V(*b))
    s.SetLayer(layer)
    s.SetWidth(MM(width))
    board.Add(s)
    return s


def polyline(board, layer, pts, width, close=False):
    out = []
    for i in range(len(pts) - 1):
        out.append(seg(board, layer, pts[i], pts[i + 1], width))
    if close:
        out.append(seg(board, layer, pts[-1], pts[0], width))
    return out


def poly(board, layer, pts, filled=True, width=0.0):
    """Filled polygon (copper artwork, mask opening, silkscreen blob)."""
    s = pcbnew.PCB_SHAPE(board)
    s.SetShape(pcbnew.SHAPE_T_POLY)
    v = pcbnew.VECTOR_VECTOR2I()
    for (x, y) in pts:
        v.append(V(x, y))
    s.SetPolyPoints(v)
    s.SetLayer(layer)
    s.SetFilled(filled)
    s.SetWidth(MM(width))
    board.Add(s)
    return s


def rect(board, layer, x, y, w, h, filled=True, width=0.0):
    """Axis aligned rectangle given by its top-left corner."""
    return poly(
        board, layer,
        [(x, y), (x + w, y), (x + w, y + h), (x, y + h)],
        filled=filled, width=width,
    )


def rect_c(board, layer, cx, cy, w, h, **kw):
    """Axis aligned rectangle given by its centre."""
    return rect(board, layer, cx - w / 2.0, cy - h / 2.0, w, h, **kw)


def circle(board, layer, cx, cy, r, filled=True, width=0.1):
    s = pcbnew.PCB_SHAPE(board)
    s.SetShape(pcbnew.SHAPE_T_CIRCLE)
    s.SetCenter(V(cx, cy))
    s.SetEnd(V(cx + r, cy))
    s.SetLayer(layer)
    s.SetFilled(filled)
    s.SetWidth(MM(0.0 if filled else width))
    board.Add(s)
    return s


def arc(board, layer, centre, start, angle_deg, width):
    s = pcbnew.PCB_SHAPE(board)
    s.SetShape(pcbnew.SHAPE_T_ARC)
    s.SetCenter(V(*centre))
    s.SetStart(V(*start))
    s.SetArcAngleAndEnd(pcbnew.EDA_ANGLE(angle_deg, pcbnew.DEGREES_T), True)
    s.SetLayer(layer)
    s.SetWidth(MM(width))
    board.Add(s)
    return s


def text(board, layer, txt, x, y, height, thickness, *, mirrored=None,
         angle=0.0, hjustify=pcbnew.GR_TEXT_H_ALIGN_CENTER, knockout=False):
    """Board text.

    Silkscreen has a manufacturable floor: fabs quote ~0.8 mm character height
    and ~0.15 mm stroke width for legible white ink, and KiCad's default rules
    flag anything smaller. Sizes are clamped here rather than at every call
    site, so a designator can never silently fall below what a fab can print.
    """
    if layer in (pcbnew.F_SilkS, pcbnew.B_SilkS):
        height = max(height, 0.8)
        thickness = max(thickness, 0.15)
    t = pcbnew.PCB_TEXT(board)
    t.SetText(txt)
    t.SetPosition(V(x, y))
    t.SetLayer(layer)
    t.SetTextSize(size(height * 0.78, height))
    t.SetTextThickness(MM(thickness))
    t.SetHorizJustify(hjustify)
    t.SetVertJustify(pcbnew.GR_TEXT_V_ALIGN_CENTER)
    if angle:
        t.SetTextAngle(pcbnew.EDA_ANGLE(angle, pcbnew.DEGREES_T))
    if mirrored is None:
        mirrored = pcbnew.IsBackLayer(layer)
    t.SetMirrored(mirrored)
    if knockout:
        t.SetIsKnockout(True)
    board.Add(t)
    return t


# --------------------------------------------------------------------------
# gold (ENIG) artwork: copper + a matching solder mask opening
# --------------------------------------------------------------------------

GOLD_BLEED = 0.05  # mask opening grows slightly so copper is fully exposed


def _grow(pts, d):
    cx = sum(p[0] for p in pts) / len(pts)
    cy = sum(p[1] for p in pts) / len(pts)
    out = []
    for (x, y) in pts:
        dx, dy = x - cx, y - cy
        n = math.hypot(dx, dy) or 1.0
        out.append((x + dx / n * d, y + dy / n * d))
    return out


def gold_poly(board, back, pts):
    cu = pcbnew.B_Cu if back else pcbnew.F_Cu
    mask = pcbnew.B_Mask if back else pcbnew.F_Mask
    poly(board, cu, pts)
    poly(board, mask, _grow(pts, GOLD_BLEED))


def gold_rect(board, back, x, y, w, h):
    gold_poly(board, back, [(x, y), (x + w, y), (x + w, y + h), (x, y + h)])


def gold_circle(board, back, cx, cy, r):
    cu = pcbnew.B_Cu if back else pcbnew.F_Cu
    mask = pcbnew.B_Mask if back else pcbnew.F_Mask
    circle(board, cu, cx, cy, r)
    circle(board, mask, cx, cy, r + GOLD_BLEED)


def gold_stroke(board, back, pts, width, close=False):
    """A stroked path in exposed gold (copper + mask).

    Copper narrower than the fab's track floor is not etched reliably, so
    decorative strokes are clamped to MIN_TRACK like real tracks.
    """
    width = max(width, MIN_TRACK)
    cu = pcbnew.B_Cu if back else pcbnew.F_Cu
    mask = pcbnew.B_Mask if back else pcbnew.F_Mask
    polyline(board, cu, pts, width, close=close)
    polyline(board, mask, pts, width + 2 * GOLD_BLEED, close=close)


def gold_text(board, back, txt, x, y, height, thickness, **kw):
    cu = pcbnew.B_Cu if back else pcbnew.F_Cu
    mask = pcbnew.B_Mask if back else pcbnew.F_Mask
    text(board, cu, txt, x, y, height, thickness, **kw)
    text(board, mask, txt, x, y, height, thickness + 2 * GOLD_BLEED, **kw)


def _bridge_near_outlines(ps, min_gap, rnd, err, rounds=6):
    """Join separate outlines that still come closer than `min_gap`.

    A closing fills gaps narrower than its diameter, but where a gap is only
    slightly WIDER, the two grown shapes meet at a point and the shrink leaves
    a cusp pointing at the neighbour — closer than the original gap was.
    Those pairs are joined by the lens where both shapes, grown by half the
    gap, overlap: the result is one feature with no sliver between.
    """
    clr = MM(min_gap)
    grow = MM(min_gap / 2.0 + 0.01)
    for _ in range(rounds):
        # Each part is grown ONCE; two parts closer than min_gap are exactly
        # the pairs whose grown copies intersect, and that intersection is
        # the bridge. (SHAPE_POLY_SET.Collide on large holed outlines took
        # >40 s per call; Clipper booleans take milliseconds.)
        grown, boxes = [], []
        for k in range(ps.OutlineCount()):
            one = pcbnew.SHAPE_POLY_SET()
            one.AddOutline(ps.COutline(k))
            for h in range(ps.HoleCount(k)):
                one.AddHole(ps.CHole(k, h))
            b = one.BBox()
            boxes.append((b.GetLeft(), b.GetTop(), b.GetRight(), b.GetBottom()))
            one.Inflate(grow, rnd, err)
            grown.append(one)
        order = sorted(range(len(boxes)), key=lambda i: boxes[i][0])
        bridges = pcbnew.SHAPE_POLY_SET()
        for oi, i in enumerate(order):
            bi = boxes[i]
            for j in order[oi + 1:]:
                bj = boxes[j]
                if bj[0] > bi[2] + clr:
                    break
                if bi[1] > bj[3] + clr or bj[1] > bi[3] + clr:
                    continue
                a = grown[i].CloneDropTriangulation()
                a.BooleanIntersection(grown[j])
                if a.OutlineCount():
                    bridges.BooleanAdd(a)
        if bridges.OutlineCount() == 0:
            return
        ps.BooleanAdd(bridges)
        ps.Simplify()


def merge_gold(board, back, items, min_gap):
    """Fuse drawn gold artwork into one clean copper shape plus its mask.

    Line art drawn as many overlapping strokes leaves slivers of laminate
    narrower than the fab can etch wherever two strokes ALMOST meet (a window
    rung 0.05 mm short of a wall). A closing (grow by min_gap/2, shrink back)
    fills exactly the gaps narrower than min_gap and leaves the drawing
    otherwise untouched. The mask opening is derived from the merged copper,
    so copper and gold exposure can never disagree.

    `items` are the PCB_SHAPEs the artwork created on the copper and mask
    layers; they are replaced by the merged result.
    """
    cu = pcbnew.B_Cu if back else pcbnew.F_Cu
    mask = pcbnew.B_Mask if back else pcbnew.F_Mask
    err = MM(0.002)
    rnd = pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS
    ps = pcbnew.SHAPE_POLY_SET()
    for it in items:
        if it.GetLayer() == cu:
            if isinstance(it, pcbnew.PCB_TEXT):
                # TransformShapeToPolygon gives a text's BOUNDING BOX (zone
                # keep-out semantics); the glyph strokes come from this one.
                it.TransformTextToPolySet(ps, 0, err, pcbnew.ERROR_INSIDE)
            else:
                it.TransformShapeToPolygon(ps, cu, 0, err, pcbnew.ERROR_INSIDE)
    ps.Simplify()
    ps.Inflate(MM(min_gap / 2.0), rnd, err)
    ps.Simplify()
    ps.Inflate(MM(-min_gap / 2.0), rnd, err)
    ps.Simplify()
    _bridge_near_outlines(ps, min_gap, rnd, err)
    opening = ps.CloneDropTriangulation()
    opening.Inflate(MM(GOLD_BLEED), rnd, err)
    opening.Simplify()
    for it in items:
        board.Remove(it)
    out = []
    for layer, shape in ((cu, ps), (mask, opening)):
        # Fracture turns holes into slits so each outline is one simple
        # polygon; a saved gr_poly holds exactly ONE outline, so a multi-
        # outline set must become one PCB_SHAPE per outline or the rest is
        # silently dropped on save.
        shape.Fracture()
        for k in range(shape.OutlineCount()):
            one = pcbnew.SHAPE_POLY_SET()
            one.AddOutline(shape.COutline(k))
            s = pcbnew.PCB_SHAPE(board)
            s.SetShape(pcbnew.SHAPE_T_POLY)
            s.SetPolyShape(one)
            s.SetLayer(layer)
            s.SetFilled(True)
            s.SetWidth(0)
            board.Add(s)
            out.append(s)
    return out


# --------------------------------------------------------------------------
# footprints / pads
# --------------------------------------------------------------------------

def new_fp(board, ref, x, y, value="", back=False):
    fp = pcbnew.FOOTPRINT(board)
    fp.SetPosition(V(x, y))
    fp.SetReference(ref)
    fp.SetValue(value or ref)
    fp.Reference().SetVisible(False)
    fp.Value().SetVisible(False)
    fp.SetAttributes(pcbnew.FP_SMD | pcbnew.FP_EXCLUDE_FROM_BOM
                     | pcbnew.FP_EXCLUDE_FROM_POS_FILES)
    board.Add(fp)
    if back:
        fp.Flip(V(x, y), False)
    return fp


def smd_pad(fp, x, y, w, h, *, shape=pcbnew.PAD_SHAPE_RECT, number="",
            back=False, roundratio=0.15):
    p = pcbnew.PAD(fp)
    p.SetShape(shape)
    p.SetSize(size(w, h))
    p.SetAttribute(pcbnew.PAD_ATTRIB_SMD)
    lset = pcbnew.LSET()
    if back:
        lset.AddLayer(pcbnew.B_Cu)
        lset.AddLayer(pcbnew.B_Mask)
    else:
        lset.AddLayer(pcbnew.F_Cu)
        lset.AddLayer(pcbnew.F_Mask)
    p.SetLayerSet(lset)
    if shape == pcbnew.PAD_SHAPE_ROUNDRECT:
        p.SetRoundRectRadiusRatio(roundratio)
    p.SetNumber(number)
    p.SetPosition(V(x, y))
    fp.Add(p)
    return p


def npth(board, x, y, drill, ref="H"):
    fp = new_fp(board, ref, x, y)
    p = pcbnew.PAD(fp)
    p.SetAttribute(pcbnew.PAD_ATTRIB_NPTH)
    p.SetShape(pcbnew.PAD_SHAPE_CIRCLE)
    p.SetSize(size(drill, drill))
    p.SetDrillSize(size(drill, drill))
    p.SetLayerSet(p.UnplatedHoleMask())
    p.SetPosition(V(x, y))
    fp.Add(p)
    return fp


MIN_TRACK = 0.16   # 6 mil = 0.1524 mm is the fab floor; 0.16 keeps a margin
MIN_SPACE = 0.16   # same floor for the laminate gap between copper features


def track(board, layer, a, b, width):
    t = pcbnew.PCB_TRACK(board)
    t.SetStart(V(*a))
    t.SetEnd(V(*b))
    t.SetWidth(MM(max(width, MIN_TRACK)))
    t.SetLayer(layer)
    board.Add(t)
    return t


def track_path(board, layer, pts, width):
    return [track(board, layer, pts[i], pts[i + 1], width)
            for i in range(len(pts) - 1)]


MIN_DRILL = 0.3
MIN_RING = 0.15    # PCBWay standard annular ring
MIN_VIA = MIN_DRILL + 2 * MIN_RING


def via(board, x, y, drill=0.3, diameter=0.6):
    """Through via.

    Sizes are clamped to the fab floor (0.3 mm drill, 0.15 mm annular ring).
    Callers asking for smaller decorative vias silently get the legal minimum
    rather than a DRC error — the visual difference at 0.1 mm is nil.
    """
    drill = max(drill, MIN_DRILL)
    diameter = max(diameter, MIN_VIA, drill + 2 * MIN_RING)
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(V(x, y))
    v.SetViaType(pcbnew.VIATYPE_THROUGH)
    v.SetDrill(MM(drill))
    v.SetWidth(MM(diameter))
    v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    board.Add(v)
    return v
