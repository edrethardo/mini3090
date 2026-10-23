"""Rasterise EXPORTED Gerber/Excellon files into one common board frame.

Everything that judges manufacturability or the look of the finished board
reads these rasters, never the generator's own geometry: what a fab receives
is the Gerber, so that is what gets measured.

Frame: board millimetres, x to the right, y downward, origin at the board's
top-left bounding-box corner (KiCad exports with absolute origin, so Gerber
X = x and Gerber Y = -y). One pixel = 1 / DPMM mm.
"""

from __future__ import annotations

import re
from pathlib import Path

import cv2
import numpy as np
from pygerber.common.rgba import RGBA
from pygerber.gerberx3.api.v2 import ColorScheme, GerberFile, PixelFormatEnum

DPMM = 100                      # 10 µm per pixel
BOARD_W, BOARD_H = 110.0, 48.0
MARGIN = 1.0                    # mm of canvas around the board

_WHITE = RGBA(r=255, g=255, b=255, a=255)
_BLACK = RGBA(r=0, g=0, b=0, a=255)
# dark polarity -> white, clear polarity -> black: a plain boolean image
_MONO = ColorScheme(background_color=_BLACK, clear_color=_BLACK,
                    solid_color=_WHITE, clear_region_color=_BLACK,
                    solid_region_color=_WHITE)


def canvas_shape(dpmm=DPMM):
    return (int(round((BOARD_H + 2 * MARGIN) * dpmm)),
            int(round((BOARD_W + 2 * MARGIN) * dpmm)))


def to_px(x, y, dpmm=DPMM):
    """Board mm -> (col, row) on the canvas."""
    return (int(round((x + MARGIN) * dpmm)), int(round((y + MARGIN) * dpmm)))


def to_mm(col, row, dpmm=DPMM):
    return (col / dpmm - MARGIN, row / dpmm - MARGIN)


def raster_gerber(path: Path, scratch: Path, dpmm=DPMM) -> np.ndarray:
    """Boolean image of one Gerber layer (True = dark/drawn)."""
    parsed = GerberFile.from_file(path).parse()
    info = parsed.get_info()
    scratch.mkdir(parents=True, exist_ok=True)
    png = scratch / (path.stem + f"_{dpmm}.png")
    parsed.render_raster(png, color_scheme=_MONO, dpmm=dpmm,
                         pixel_format=PixelFormatEnum.RGB)
    img = cv2.imread(str(png), cv2.IMREAD_GRAYSCALE) > 127
    out = np.zeros(canvas_shape(dpmm), dtype=bool)
    # pygerber's image starts at (min_x, max_y) of the file's own extent
    c0, r0 = to_px(float(info.min_x_mm), -float(info.max_y_mm), dpmm)
    h = min(img.shape[0], out.shape[0] - r0)
    w = min(img.shape[1], out.shape[1] - c0)
    out[r0:r0 + h, c0:c0 + w] = img[:h, :w]
    return out


def board_mask(edge: np.ndarray) -> np.ndarray:
    """Board interior from the Edge.Cuts outline raster."""
    closed = cv2.morphologyEx(edge.astype(np.uint8), cv2.MORPH_CLOSE,
                              np.ones((5, 5), np.uint8))
    flood = closed.copy()
    h, w = flood.shape
    ff = np.zeros((h + 2, w + 2), np.uint8)
    cv2.floodFill(flood, ff, (0, 0), 1)
    outside = (flood == 1) & (closed == 0)
    return ~outside


def read_drill(path: Path):
    """Excellon holes as (x_mm, y_mm, diameter_mm) in the board frame."""
    tools, holes, cur = {}, [], None
    metric = True
    for line in path.read_text(errors="ignore").splitlines():
        line = line.strip()
        if line.startswith("INCH"):
            metric = False
        m = re.fullmatch(r"T(\d+)C([\d.]+)", line)
        if m:
            tools[m.group(1)] = float(m.group(2))
            continue
        m = re.fullmatch(r"T(\d+)", line)
        if m:
            cur = m.group(1)
            continue
        m = re.fullmatch(r"X(-?[\d.]+)Y(-?[\d.]+)", line)
        if m and cur in tools:
            k = 1.0 if metric else 25.4
            holes.append((float(m.group(1)) * k, -float(m.group(2)) * k,
                          tools[cur] * k))
    return holes


def raster_holes(holes, dpmm=DPMM) -> np.ndarray:
    out = np.zeros(canvas_shape(dpmm), dtype=np.uint8)
    for (x, y, d) in holes:
        cv2.circle(out, to_px(x, y, dpmm), int(round(d / 2 * dpmm)), 1, -1)
    return out.astype(bool)


LAYER_FILES = {
    "F.Cu": "F_Cu", "B.Cu": "B_Cu", "F.Mask": "F_Mask", "B.Mask": "B_Mask",
    "F.Silk": "F_Silkscreen", "B.Silk": "B_Silkscreen", "Edge": "Edge_Cuts",
}


def load_layers(gdir: Path, scratch: Path, dpmm=DPMM) -> dict:
    """All layers of one Gerber set, plus drills and the board interior."""
    scratch.mkdir(parents=True, exist_ok=True)
    out = {}
    for key, suffix in LAYER_FILES.items():
        f = next(gdir.glob(f"*-{suffix}.gbr"))
        out[key] = raster_gerber(f, scratch, dpmm)
    out["board"] = board_mask(out["Edge"])
    holes = []
    for f in sorted(gdir.glob("*.drl")):
        holes += read_drill(f)
    out["holes"] = holes
    out["drill"] = raster_holes(holes, dpmm)
    return out
