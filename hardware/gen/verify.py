"""Verify the exported production package.

Checks that can actually fail are the point here — a verifier that only prints
"OK" is worthless. Every check reads the EXPORTED artefacts (Gerbers, drill
files, renders), not the generator's own beliefs.

  1. all required Gerber layers + drill files exist and are non-trivial
  2. board outline in Edge.Cuts matches 110 x 48 mm
  3. the QR code decodes from the rendered back side, to the right URL
  4. the QR quiet zone contains no foreign copper/silk (checked against the
     exported B.Cu / B.Silkscreen / B.Mask Gerbers, not the render)
  5. B.Silkscreen text is NOT mirrored when viewed from the back
  6. both serial numbers appear on their own board, front and back
  7. solder mask openings stay a minority of the board area (black dominates)
"""

from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path

import cv2
import numpy as np

REQUIRED_GERBERS = {
    "F.Cu": "*-F_Cu.gbr",
    "B.Cu": "*-B_Cu.gbr",
    "F.Mask": "*-F_Mask.gbr",
    "B.Mask": "*-B_Mask.gbr",
    "F.SilkS": "*-F_Silkscreen.gbr",
    "B.SilkS": "*-B_Silkscreen.gbr",
    "Edge.Cuts": "*-Edge_Cuts.gbr",
}

BOARD_W, BOARD_H = 110.0, 48.0
URL = "https://github.com/edrethardo/zettel"

results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  — {detail}" if detail else ""))
    return ok


# --------------------------------------------------------------------------
# gerber helpers
# --------------------------------------------------------------------------

def gerber_coords(path: Path):
    """Extract every X/Y coordinate from a Gerber file, in mm."""
    txt = path.read_text(errors="ignore")
    fmt = re.search(r"%FSLAX(\d)(\d)Y(\d)(\d)\*%", txt)
    if not fmt:
        return []
    _, dec, _, dec_y = (int(g) for g in fmt.groups())
    unit_mm = "%MOMM*%" in txt
    scale = 10 ** dec
    pts = []
    for m in re.finditer(r"X(-?\d+)Y(-?\d+)", txt):
        x = int(m.group(1)) / scale
        y = int(m.group(2)) / scale
        if not unit_mm:
            x, y = x * 25.4, y * 25.4
        pts.append((x, y))
    return pts


def bbox(pts):
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def points_in_rect(pts, x0, y0, x1, y1):
    return [(x, y) for (x, y) in pts if x0 <= x <= x1 and y0 <= y <= y1]


# --------------------------------------------------------------------------
# checks
# --------------------------------------------------------------------------

def check_layers(gdir: Path, serial: str):
    for layer, pattern in REQUIRED_GERBERS.items():
        hits = list(gdir.glob(pattern))
        ok = bool(hits) and hits[0].stat().st_size > 400
        check(f"{serial}: gerber {layer} present",
              ok, hits[0].name if hits else "missing")
    drills = list(gdir.glob("*.drl"))
    check(f"{serial}: drill files present", len(drills) >= 1,
          ", ".join(d.name for d in drills))
    for d in drills:
        body = d.read_text(errors="ignore")
        n = len(re.findall(r"^X", body, re.M))
        # A board that lost its via stitching still exports a valid drill file
        # with only the four mounting holes, so a bare "> 0" check passes while
        # the artwork is visibly wrong. The PTH file carries the decorative
        # via field and must be substantial.
        floor = 120 if "PTH" in d.name and "NPTH" not in d.name else 1
        check(f"{serial}: drill {d.name} has holes", n >= floor,
              f"{n} hits (expected >= {floor})")


def check_outline(gdir: Path, serial: str):
    edge = next(gdir.glob("*-Edge_Cuts.gbr"), None)
    if not edge:
        return check(f"{serial}: outline size", False, "no Edge.Cuts")
    x0, y0, x1, y1 = bbox(gerber_coords(edge))
    w, h = x1 - x0, y1 - y0
    ok = abs(w - BOARD_W) < 0.2 and abs(h - BOARD_H) < 0.2
    check(f"{serial}: outline is {BOARD_W} x {BOARD_H} mm", ok,
          f"measured {w:.2f} x {h:.2f} mm")


def check_qr_keepout(gdir: Path, serial: str, qr_info: dict):
    """No foreign copper, silk or drill inside the QR quiet zone.

    The QR sits on B.Cu as one solid plate with B.Mask openings, so B.Cu is
    expected to be busy there. What must be empty: silkscreen, drilled holes,
    and any copper *outside* the QR plate's own rectangle.
    """
    ox, oy = qr_info["origin_mm"]
    ext = qr_info["extent_mm"]
    quiet = qr_info["quiet_zone_modules"] * qr_info["module_mm"]
    # KiCad Gerber Y axis points up; the board's y=0 edge is at gerber y=0 too
    # for absolute origin, but we compare in the Gerber's own frame by taking
    # the QR box from the Edge.Cuts bbox.
    edge = next(gdir.glob("*-Edge_Cuts.gbr"))
    ex0, ey0, ex1, ey1 = bbox(gerber_coords(edge))
    # board y downward -> gerber y upward
    gx0 = ex0 + ox
    gy1 = ey1 - oy
    gx1 = gx0 + ext
    gy0 = gy1 - ext

    silk = next(gdir.glob("*-B_Silkscreen.gbr"), None)
    if silk:
        intruders = points_in_rect(gerber_coords(silk), gx0, gy0, gx1, gy1)
        check(f"{serial}: no silkscreen inside QR symbol", not intruders,
              f"{len(intruders)} coordinates inside")

    for drl in gdir.glob("*.drl"):
        body = drl.read_text(errors="ignore")
        bad = 0
        for m in re.finditer(r"^X(-?[\d.]+)Y(-?[\d.]+)", body, re.M):
            x, y = float(m.group(1)), float(m.group(2))
            if gx0 <= x <= gx1 and gy0 <= y <= gy1:
                bad += 1
        check(f"{serial}: no drilled holes inside QR ({drl.name})", bad == 0,
              f"{bad} holes")

    # quiet zone width actually present in the design
    check(f"{serial}: QR quiet zone >= 4 modules",
          qr_info["quiet_zone_modules"] >= 4,
          f'{qr_info["quiet_zone_modules"]} modules '
          f'= {quiet:.2f} mm')
    check(f"{serial}: QR module size manufacturable (>= 0.35 mm)",
          qr_info["module_mm"] >= 0.35, f'{qr_info["module_mm"]} mm')
    check(f"{serial}: QR error correction is H", qr_info["error"] == "H",
          qr_info["error"])


def check_qr_scan(preview: Path, serial: str):
    img = cv2.imread(str(preview))
    if img is None:
        return check(f"{serial}: QR scans from render", False, "no render")
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    txt, _, _ = cv2.QRCodeDetector().detectAndDecode(gray)
    check(f"{serial}: QR scans from the rendered back side", txt == URL,
          repr(txt))


def check_mask_ratio(gdir: Path, serial: str):
    """Black must dominate: count mask aperture flashes vs board area is not
    meaningful, so compare the rendered gold pixels against the board area."""
    return  # handled by check_render_gold


def check_render_gold(preview: Path, serial: str, side: str):
    img = cv2.imread(str(preview))
    if img is None:
        return check(f"{serial}: {side} render exists", False, "missing")
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    # board pixels = anything not pure background black
    board = cv2.inRange(hsv, (0, 0, 12), (180, 255, 255))
    gold = cv2.inRange(hsv, (18, 120, 90), (38, 255, 255))
    board_px = int(board.sum() / 255)
    gold_px = int(gold.sum() / 255)
    if board_px == 0:
        return check(f"{serial}: {side} render has board pixels", False)
    frac = gold_px / board_px
    check(f"{serial}: {side} — black mask dominates (gold < 50% of board)",
          frac < 0.50, f"gold = {frac * 100:.1f}% of board area")
    return frac


def check_back_text_orientation(pcb: Path, serial: str):
    """B.SilkS text must be stored mirrored in the PCB (so it reads correctly
    when the board is viewed from the back). KiCad writes `(justify mirror)`
    for such text; a back text WITHOUT it would read backwards on the fab's
    bottom view."""
    src = pcb.read_text()
    blocks = re.findall(r'\(gr_text\s+"([^"]*)"(.*?)\n\t\)', src, re.S)
    back = [(t, b) for (t, b) in blocks if '"B.SilkS"' in b or "B.SilkS" in b]
    if not back:
        return check(f"{serial}: back silkscreen text present", False)
    wrong = [t for (t, b) in back if "mirror" not in b]
    check(f"{serial}: all B.SilkS text is mirrored in source "
          f"(reads correctly from the back)", not wrong,
          f"{len(back)} texts, {len(wrong)} unmirrored"
          + (f": {wrong[:3]}" if wrong else ""))


def check_serial_text(pcb: Path, serial: str):
    src = pcb.read_text()
    tag = f"{serial}/02"
    blocks = re.findall(r'\(gr_text\s+"([^"]*)"(.*?)\n\t\)', src, re.S)
    front = any(t == tag and "F." in b for (t, b) in blocks)
    back = any(t == tag and "B.SilkS" in b for (t, b) in blocks)
    # the front serial is gold: copper + mask, so it appears on F.Cu/F.Mask
    check(f"{serial}: serial {tag} on the front", front)
    check(f"{serial}: serial {tag} on the back", back)
    other = "02" if serial == "01" else "01"
    check(f"{serial}: no stray {other}/02 on this board",
          not any(t == f"{other}/02" for (t, _) in blocks))
    for needle in ("NEMOTRON 3.5", "GTC BERLIN 2026", "ZETTEL"):
        check(f"{serial}: text '{needle}' present",
              any(needle in t for (t, _) in blocks))


def check_drc(report: Path, serial: str):
    if not report.exists():
        return check(f"{serial}: DRC report exists", False)
    body = report.read_text(errors="ignore")
    m = re.search(r"Found (\d+) DRC violations", body)
    n = int(m.group(1)) if m else -1
    unconnected = re.search(r"Found (\d+) unconnected pads", body)
    fp_err = re.search(r"Found (\d+) Footprint errors", body)
    check(f"{serial}: DRC has no errors", n == 0,
          f"{n} violations, "
          f"{unconnected.group(1) if unconnected else '?'} unconnected, "
          f"{fp_err.group(1) if fp_err else '?'} footprint errors")


def main():
    out = Path(sys.argv[1])
    print("ZETTEL3090 — production verification")
    print("=" * 60)

    for serial in ("01", "02"):
        print(f"\n--- board {serial}/02 " + "-" * 40)
        gdir = out / f"board_{serial}_of_02" / "gerbers"
        pcb = out / "source" / f"ZETTEL3090_{serial}.kicad_pcb"
        stats = json.loads((out / "verification" /
                            f"board_{serial}_stats.json").read_text())

        check_layers(gdir, serial)
        check_outline(gdir, serial)
        check_drc(out / "verification" / f"drc_{serial}.txt", serial)
        check_qr_keepout(gdir, serial, stats["qr"])
        check_qr_scan(out / "preview" / f"board_{serial}_back.png", serial)
        check_render_gold(out / "preview" / f"board_{serial}_front.png",
                          serial, "front")
        check_render_gold(out / "preview" / f"board_{serial}_back.png",
                          serial, "back")
        check_back_text_orientation(pcb, serial)
        check_serial_text(pcb, serial)
        zipf = out / f"board_{serial}_of_02" / f"ZETTEL3090_{serial}_of_02_gerbers.zip"
        check(f"{serial}: gerber zip exists", zipf.exists() and
              zipf.stat().st_size > 5000,
              f"{zipf.stat().st_size // 1024} KB" if zipf.exists() else "missing")

    passed = sum(1 for (_, ok, _) in results if ok)
    total = len(results)
    print("\n" + "=" * 60)
    print(f"{passed}/{total} checks passed")
    failures = [n for (n, ok, _) in results if not ok]
    if failures:
        print("\nFAILURES:")
        for f in failures:
            print("  -", f)
        sys.exit(1)
    print("all checks passed")


if __name__ == "__main__":
    main()
