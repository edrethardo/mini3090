"""Geometric DRC on the EXPORTED Gerbers — independent of KiCad's net logic.

Why this exists: the board has no netlist. KiCad's clearance check only
compares copper of DIFFERENT nets, so on a board where every object has no net
two traces 0.02 mm apart are not reported at all (measured: two 0.2 mm tracks
0.05 mm apart -> 0 clearance violations). A fab does not care about nets; it
etches whatever gap the Gerber contains. This checker therefore measures the
copper artwork itself, per layer, at a given rule (6 mil or 4 mil):

  spacing   background narrower than the rule between two SEPARATE copper
            features (would short or not etch)             -> violation
  same-net  background narrower than the rule inside ONE connected copper
            feature (slot, notch, acid trap). Reported separately; tiny
            corner crumbs of a morphological opening are not notches and are
            filtered by length.
  width     copper narrower than the rule (a track the fab cannot hold)
  edge      copper closer than EDGE_MIN to the board outline
  ring      PTH annular ring on both copper layers

Method: morphological opening with a disk of the rule's diameter. Background
that a disk of diameter s cannot pass through is a gap narrower than s.
Resolution 10 µm/px; every number reported is measured, not assumed.

Usage:  gerber_drc.py GERBER_DIR RULE_MIL REPORT.txt [--same-net SAME_NET.txt]
Exit 1 on any violation.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np

import gerber_raster as R

MIL = 0.0254
EDGE_MIN = 0.30          # PCBWay routing: copper to board edge >= 0.3 mm
RING_MIN = 0.15          # PCBWay: minimum annular ring for vias


def disk(d_px: int):
    d = max(3, d_px | 1)
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (d, d))


def _gap_width_per_component(bg, narrow, cu_lab_near, dist, n_comp, comp):
    """Min edge-to-edge gap (px) between different nearest copper features,
    per narrow component. A pair of adjacent background pixels whose nearest
    copper belongs to different features spans the gap: D[p] + D[q]."""
    best = np.full(n_comp, np.inf)
    for axis in (0, 1):
        a = [slice(None), slice(None)]
        b = [slice(None), slice(None)]
        a[axis] = slice(0, -1)
        b[axis] = slice(1, None)
        a, b = tuple(a), tuple(b)
        ok = narrow[a] & narrow[b] & (cu_lab_near[a] != cu_lab_near[b])
        if not ok.any():
            continue
        g = dist[a][ok] + dist[b][ok]
        c = comp[a][ok]
        np.minimum.at(best, c, g)
    return best


def check_spacing(cu, board, rule_mm, dpmm, layer):
    s_px = int(round(rule_mm * dpmm))
    bg = ~cu
    opened = cv2.morphologyEx(bg.astype(np.uint8), cv2.MORPH_OPEN, disk(s_px)) > 0
    narrow = bg & ~opened & board

    # label copper features, then the nearest copper feature of every
    # background pixel
    n_cu, cu_lab = cv2.connectedComponents(cu.astype(np.uint8), connectivity=8)
    dist, near_px = cv2.distanceTransformWithLabels(
        bg.astype(np.uint8), cv2.DIST_L2, cv2.DIST_MASK_5, labelType=cv2.DIST_LABEL_PIXEL)
    # map "index of nearest zero pixel" -> copper feature label
    zero_rc = np.argwhere(~bg)                      # row-major, same order
    lut = np.zeros(len(zero_rc) + 1, dtype=np.int32)
    lut[1:] = cu_lab[zero_rc[:, 0], zero_rc[:, 1]]
    near_feat = lut[near_px]

    n_comp, comp, stats, cent = cv2.connectedComponentsWithStats(
        narrow.astype(np.uint8), connectivity=8)
    gaps = _gap_width_per_component(bg, narrow, near_feat, dist, n_comp, comp)

    violations, same_net = [], []
    min_len = max(2 * s_px, int(0.25 * dpmm))
    for i in range(1, n_comp):
        x, y, w, h, area = stats[i]
        cx, cy = R.to_mm(*cent[i], dpmm)
        if np.isfinite(gaps[i]):
            violations.append({
                "layer": layer, "kind": "spacing", "x": cx, "y": cy,
                "gap_mm": gaps[i] / dpmm, "len_mm": max(w, h) / dpmm})
        elif max(w, h) >= min_len:
            # width of the notch: twice the largest inscribed radius
            wid = 2 * float(dist[comp == i].max()) / dpmm if area else 0
            same_net.append({
                "layer": layer, "kind": "same-net", "x": cx, "y": cy,
                "gap_mm": wid, "len_mm": max(w, h) / dpmm})
    return violations, same_net


def check_width(cu, rule_mm, dpmm, layer):
    w_px = int(round(rule_mm * dpmm))
    opened = cv2.morphologyEx(cu.astype(np.uint8), cv2.MORPH_OPEN, disk(w_px)) > 0
    thin = cu & ~opened
    n, lab, stats, cent = cv2.connectedComponentsWithStats(
        thin.astype(np.uint8), connectivity=8)
    inner = cv2.distanceTransform(cu.astype(np.uint8), cv2.DIST_L2, cv2.DIST_MASK_PRECISE)
    out = []
    # a convex corner leaves a crumb ~0.2 * rule long; a thin TRACK is long
    min_len = max(3 * w_px, int(0.3 * dpmm))
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        if max(w, h) < min_len:
            continue
        # width of the thin part: twice the largest inscribed radius in it
        wid = 2 * float(inner[lab == i].max()) / dpmm
        if wid >= rule_mm:
            continue
        cx, cy = R.to_mm(*cent[i], dpmm)
        out.append({"layer": layer, "kind": "width", "x": cx, "y": cy,
                    "gap_mm": wid, "len_mm": max(w, h) / dpmm})
    return out


def check_edge(cu, board, dpmm, layer):
    d_in = cv2.distanceTransform(board.astype(np.uint8), cv2.DIST_L2, cv2.DIST_MASK_PRECISE) / dpmm
    near = cu & board & (d_in < EDGE_MIN)
    outside = cu & ~board
    out = []
    if near.any() or outside.any():
        rr, cc = np.nonzero(near | outside)
        k = int(np.argmin(d_in[rr, cc]))
        x, y = R.to_mm(cc[k], rr[k], dpmm)
        out.append({"layer": layer, "kind": "edge", "x": x, "y": y,
                    "gap_mm": float(d_in[rr, cc].min()),
                    "len_mm": float(near.sum() + outside.sum()) / dpmm ** 2})
    return out, float(d_in[cu & board].min()) if (cu & board).any() else None


def check_rings(layers, pth, dpmm):
    """Every PTH hole needs a closed copper annulus of RING_MIN on both sides."""
    out, worst = [], np.inf
    for layer in ("F.Cu", "B.Cu"):
        # distance from each copper pixel to the nearest non-copper pixel:
        # at the hole centre this is the radius of the largest copper disc
        # around the hole, so ring = that radius - hole radius
        inner = cv2.distanceTransform(layers[layer].astype(np.uint8),
                                      cv2.DIST_L2, cv2.DIST_MASK_PRECISE) / dpmm
        for (x, y, d) in pth:
            cx, cy = R.to_px(x, y, dpmm)
            # the rasteriser places a layer to within ~2 px of the drill
            # file's frame; searching a 30 µm neighbourhood for the pad
            # centre removes that registration error from the measurement
            t = max(1, int(round(0.03 * dpmm)))
            ring = float(inner[cy - t:cy + t + 1, cx - t:cx + t + 1].max()) - d / 2
            worst = min(worst, ring)
            if ring < RING_MIN - 1.0 / dpmm:
                out.append({"layer": layer, "kind": "ring", "x": x, "y": y,
                            "gap_mm": ring, "len_mm": d})
    return out, worst


def run(gdir: Path, rule_mil: float, scratch: Path, dpmm=R.DPMM, layers=None):
    rule = rule_mil * MIL
    layers = layers or R.load_layers(gdir, scratch, dpmm)
    board = layers["board"]
    viol, same, info = [], [], {}
    for layer in ("F.Cu", "B.Cu"):
        cu = layers[layer]
        v, s = check_spacing(cu, board, rule, dpmm, layer)
        viol += v
        same += s
        viol += check_width(cu, rule, dpmm, layer)
        e, dmin = check_edge(cu, board, dpmm, layer)
        viol += e
        info[f"{layer} min copper-to-edge"] = dmin
    pth = [h for f in sorted(gdir.glob("*-PTH.drl")) for h in R.read_drill(f)]
    rv, worst = check_rings(layers, pth, dpmm)
    viol += rv
    info["PTH holes"] = len(pth)
    info["min annular ring"] = worst
    return viol, same, info, layers


def fmt(items):
    lines = []
    for it in sorted(items, key=lambda d: (d["layer"], d["kind"], d["gap_mm"])):
        lines.append(f"  {it['layer']:<5} {it['kind']:<9} at ({it['x']:7.2f}, "
                     f"{it['y']:6.2f}) mm   measured {it['gap_mm']:.3f} mm "
                     f"({it['gap_mm'] / MIL:4.1f} mil)   extent {it['len_mm']:.2f} mm")
    return lines


def report(gdir, rule_mil, viol, same, info):
    rule = rule_mil * MIL
    kinds = {}
    for v in viol:
        kinds[v["kind"]] = kinds.get(v["kind"], 0) + 1
    L = [
        f"ZETTEL3090 — geometric DRC on exported Gerbers, rule {rule_mil:g} mil "
        f"({rule:.4f} mm)",
        "=" * 72,
        f"Gerber set : {gdir}",
        f"Resolution : {1000 / R.DPMM:.0f} µm/px",
        "",
        "Rules checked (copper, both layers):",
        f"  min track width                    {rule:.4f} mm",
        f"  min spacing between copper features {rule:.4f} mm",
        f"  min copper to board edge           {EDGE_MIN:.2f} mm",
        f"  min PTH annular ring               {RING_MIN:.2f} mm",
        "",
        "Measured:",
    ]
    for k, v in info.items():
        L.append(f"  {k:<32} {v:.3f}" if isinstance(v, float) else f"  {k:<32} {v}")
    L += ["", f"Violations: {len(viol)}"]
    for k in ("spacing", "width", "edge", "ring"):
        L.append(f"  {k:<8} {kinds.get(k, 0)}")
    L += fmt(viol)
    L += ["", f"Same-net gaps narrower than the rule (informational): {len(same)}"]
    L += fmt(same)
    L += ["", "RESULT: " + ("PASS" if not viol else "FAIL")]
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("gdir")
    ap.add_argument("rule_mil", type=float)
    ap.add_argument("report")
    ap.add_argument("--scratch", default=None)
    args = ap.parse_args()
    gdir = Path(args.gdir)
    scratch = Path(args.scratch or gdir.parent / ".raster")
    viol, same, info, _ = run(gdir, args.rule_mil, scratch)
    txt = report(gdir, args.rule_mil, viol, same, info)
    Path(args.report).write_text(txt)
    print(txt)
    sys.exit(1 if viol else 0)


if __name__ == "__main__":
    main()
