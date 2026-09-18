"""Real, scannable QR code as PCB artwork.

Polarity: the whole QR area is solid copper on B.Cu. Solder mask openings are
cut for the *light* modules only, so light modules come out as bright ENIG gold
and dark modules stay under black solder mask. Quiet zone is light (gold).
"""

from __future__ import annotations

import segno

import pcbnew

from kicadlib import poly, rect

URL = "https://github.com/edrethardo/zettel"
QUIET = 4          # modules of quiet zone on every side
ERROR = "h"        # highest error correction


def qr_matrix(url: str = URL, error: str = ERROR, quiet: int = QUIET):
    q = segno.make(url, error=error, mode="byte", boost_error=False)
    rows = [list(r) for r in q.matrix]
    n = len(rows)
    total = n + 2 * quiet
    grid = [[0] * total for _ in range(total)]
    for y in range(n):
        for x in range(n):
            grid[y + quiet][x + quiet] = 1 if rows[y][x] else 0
    return grid, total, q.version, q.error


def place_qr(board, cx, cy, target_size, url: str = URL, back: bool = True):
    """Place the QR centred on (cx, cy); returns (module_mm, extent_mm, info)."""
    grid, n, version, error = qr_matrix(url)
    module = target_size / n
    extent = module * n
    x0 = cx - extent / 2.0
    y0 = cy - extent / 2.0

    cu = pcbnew.B_Cu if back else pcbnew.F_Cu
    mask = pcbnew.B_Mask if back else pcbnew.F_Mask

    # solid copper backing for the whole symbol (+0.3 mm frame)
    rect(board, cu, x0 - 0.3, y0 - 0.3, extent + 0.6, extent + 0.6)

    # mask openings for light modules, merged per run to keep the file small
    opened = 0
    for row in range(n):
        y = y0 + row * module
        col = 0
        while col < n:
            if grid[row][col] == 0:
                start = col
                while col < n and grid[row][col] == 0:
                    col += 1
                w = (col - start) * module
                x = x0 + start * module
                # tiny bleed so adjacent runs merge cleanly in the plot
                rect(board, mask, x, y, w, module)
                opened += col - start
            else:
                col += 1

    # gold frame edge around the symbol so the quiet zone is unambiguous
    info = {
        "version": version,
        "error": error,
        "modules": n,
        "module_mm": round(module, 4),
        "extent_mm": round(extent, 3),
        "light_modules": opened,
        "url": url,
        "quiet_zone_modules": QUIET,
        "origin_mm": (round(x0, 3), round(y0, 3)),
    }
    return module, extent, info
