"""Gerber-viewer screenshots and the number-field detail view.

All images are composited from the EXPORTED Gerbers/drills (what PCBWay's
viewer shows), not from the KiCad board:

  gerber_front.png / gerber_back.png   whole board, fab-viewer colours
  gerber_layers_front.png / _back.png  copper | mask | silk, one per panel
  number_field_detail.png              Gerber state "[      ] /03", the 3D
                                       render crop, and an illustration of the
                                       field after hand-numbering (01/02/03)

Usage: gerber_views.py GERBER_DIR PREVIEW_DIR STATS.json FRONT_RENDER.png [--scratch DIR]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np

import gerber_raster as R

DP = 40                                  # 25 µm/px: 4.5k px wide board image
BG = (40, 40, 40)                        # outside the board
MASK = (22, 22, 22)                      # matte black mask
MASK_CU = (48, 48, 48)                   # copper under mask (visible relief)
GOLD = (60, 190, 230)                    # BGR ENIG
SILK = (245, 245, 245)
HOLE = (0, 0, 0)


def composite(L, side):
    f = side == "front"
    cu, mask, silk = (L["F.Cu"], L["F.Mask"], L["F.Silk"]) if f else \
                     (L["B.Cu"], L["B.Mask"], L["B.Silk"])
    img = np.zeros(cu.shape + (3,), np.uint8)
    img[:] = BG
    b = L["board"]
    img[b] = MASK
    img[b & cu] = MASK_CU
    img[b & mask & cu] = GOLD
    img[b & mask & ~cu] = (95, 110, 120)             # bare laminate opening
    img[b & silk & ~mask] = SILK                     # silk is clipped by mask
    img[L["drill"]] = HOLE
    edge = L["Edge"]
    img[edge] = (200, 200, 200)
    if not f:
        img = np.ascontiguousarray(img[:, ::-1])       # viewed from the back
    return img


def label(img, txt, org, scale=1.4, col=(255, 255, 255), th=2):
    cv2.putText(img, txt, org, cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 0, 0), th + 4,
                cv2.LINE_AA)
    cv2.putText(img, txt, org, cv2.FONT_HERSHEY_SIMPLEX, scale, col, th, cv2.LINE_AA)


def layer_strip(L, side):
    f = side == "front"
    names = [("F.Cu", "F.Mask", "F.Silk") if f else ("B.Cu", "B.Mask", "B.Silk")][0]
    panels = []
    for n in names:
        p = np.where(L[n][..., None], np.uint8(235), np.uint8(20)).repeat(3, 2)
        p[L["Edge"]] = (0, 0, 255)
        if not f:
            p = np.ascontiguousarray(p[:, ::-1])
        p = cv2.resize(p, None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA)
        label(p, f"{n}  (Gerber, {'top' if f else 'bottom'} view)", (20, 45), 1.0)
        panels.append(p)
    return np.vstack(panels)


def number_detail(L, stats, render_path, out):
    nf = stats["number_field"]
    x0, y0, x1, y1 = nf["field_mm"]
    lx0, ly0, lx1, ly1 = nf["label_bbox_mm"]
    pad = 3.0
    ax0, ay0, ax1, ay1 = x0 - pad, y0 - pad, lx1 + pad, y1 + pad
    dp = 120                                          # ~8 µm/px close-up
    Lz = {k: R.raster_gerber(next(Path(out["gdir"]).glob(f"*-{s}.gbr")),
                             out["scratch"], dp)
          for k, s in (("F.Cu", "F_Cu"), ("F.Mask", "F_Mask"), ("F.Silk", "F_Silkscreen"),
                       ("Edge", "Edge_Cuts"))}
    Lz["board"] = R.board_mask(Lz["Edge"])
    holes = [h for f in Path(out["gdir"]).glob("*.drl") for h in R.read_drill(f)]
    Lz["drill"] = R.raster_holes(holes, dp)
    Lz["B.Cu"] = Lz["F.Cu"]; Lz["B.Mask"] = Lz["F.Mask"]; Lz["B.Silk"] = Lz["F.Silk"]
    img = composite(Lz, "front")
    c0, r0 = R.to_px(ax0, ay0, dp)
    c1, r1 = R.to_px(ax1, ay1, dp)
    crop = img[r0:r1, c0:c1].copy()

    def px(x, y):
        return (int(round((x - ax0) * dp)), int(round((y - ay0) * dp)))

    # dimension overlay (annotation colour, NOT part of the artwork)
    ann = crop.copy()
    red = (80, 80, 255)
    cv2.rectangle(ann, px(x0, y0), px(x1, y1), red, 2, cv2.LINE_AA)
    yb = y1 + 1.2
    cv2.arrowedLine(ann, px(x0, yb), px(x1, yb), red, 3, tipLength=0.03)
    cv2.arrowedLine(ann, px(x1, yb), px(x0, yb), red, 3, tipLength=0.03)
    label(ann, f"{x1 - x0:.1f} mm", (px((x0 + x1) / 2 - 1.2, yb - 0.25)), 1.3, red, 3)
    xh = x0 - 1.2
    cv2.arrowedLine(ann, px(xh, y0), px(xh, y1), red, 3, tipLength=0.08)
    cv2.arrowedLine(ann, px(xh, y1), px(xh, y0), red, 3, tipLength=0.08)
    label(ann, f"{y1 - y0:.1f}", (px(xh - 2.6, (y0 + y1) / 2)), 1.2, red, 3)
    label(ann, f"'/{stats['total']}' h={nf['label_height_mm']} mm, "
               f"stroke {nf['label_stroke_mm']} mm", px(lx0 - 3.5, ly0 - 1.0), 1.1, red, 2)

    # illustration of hand-numbering: white paint-marker digits in the field
    fills = []
    for n in ("01", "02", "03"):
        im = crop.copy()
        h_mm = nf["label_height_mm"] * 1.25           # 2.5 mm, as the notes advise
        (_, th1), _ = cv2.getTextSize("0", cv2.FONT_HERSHEY_SIMPLEX, 1.0, 1)
        scale = h_mm * dp / th1
        (tw, th), _ = cv2.getTextSize(n, cv2.FONT_HERSHEY_SIMPLEX, scale, 1)
        cx = px(x1 - 0.6, 0)[0] - tw
        cy = px(0, (ly0 + ly1) / 2 + nf["label_height_mm"] / 2)[1]  # "/03" baseline
        cv2.putText(im, n, (cx, cy), cv2.FONT_HERSHEY_SIMPLEX, scale, (238, 238, 238),
                    max(2, int(0.3 * dp)), cv2.LINE_AA)
        label(im, f"after hand-numbering: {n}/{stats['total']} (illustration)", (15, 45),
              1.1, (0, 220, 255), 2)
        fills.append(im)

    label(crop, "Gerber state, identical on ALL boards", (15, 45), 1.1, (0, 220, 255), 2)
    label(ann, "dimensions (annotation only)", (15, 45), 1.1, (0, 220, 255), 2)

    # matching crop of the KiCad render (scale from board bbox in the render)
    rend = cv2.imread(str(render_path))
    panels = [crop, ann]
    if rend is not None:
        hsv = cv2.cvtColor(rend, cv2.COLOR_BGR2HSV)
        board = cv2.inRange(hsv, (0, 0, 12), (180, 255, 255))
        ys, xs = np.nonzero(board)
        bx0, bx1, by0, by1 = xs.min(), xs.max(), ys.min(), ys.max()
        sx = (bx1 - bx0) / R.BOARD_W
        sy = (by1 - by0) / R.BOARD_H
        rc = rend[int(by0 + ay0 * sy):int(by0 + ay1 * sy), int(bx0 + ax0 * sx):int(bx0 + ax1 * sx)]
        rc = cv2.resize(rc, (crop.shape[1], crop.shape[0]), interpolation=cv2.INTER_CUBIC)
        label(rc, "KiCad 3D render", (15, 45), 1.1, (0, 220, 255), 2)
        panels.append(rc)
    top = np.hstack(panels[:2])
    mid = np.hstack([panels[2] if len(panels) > 2 else crop, fills[0]])
    bot = np.hstack(fills[1:])
    sep = lambda w: np.full((8, w, 3), 90, np.uint8)
    full = np.vstack([top, sep(top.shape[1]), mid, sep(top.shape[1]), bot])
    return full


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("gdir")
    ap.add_argument("outdir")
    ap.add_argument("stats")
    ap.add_argument("front_render")
    ap.add_argument("--scratch", default=None)
    a = ap.parse_args()
    gdir, outdir = Path(a.gdir), Path(a.outdir)
    scratch = Path(a.scratch or outdir / ".raster")
    stats = json.loads(Path(a.stats).read_text())
    L = R.load_layers(gdir, scratch, DP)
    for side in ("front", "back"):
        img = composite(L, side)
        label(img, f"ZETTEL3090 — Gerber view, {side} "
                   f"({'top' if side == 'front' else 'bottom'} side as seen)", (30, 60))
        cv2.imwrite(str(outdir / f"gerber_{side}.png"), img)
        cv2.imwrite(str(outdir / f"gerber_layers_{side}.png"), layer_strip(L, side))
    det = number_detail(L, stats, a.front_render, {"gdir": gdir, "scratch": scratch})
    cv2.imwrite(str(outdir / "number_field_detail.png"), det)
    print("views written:", ", ".join(sorted(p.name for p in outdir.glob("gerber_*.png"))),
          "number_field_detail.png")


if __name__ == "__main__":
    main()
