"""Write DRC_6MIL_REPORT.txt, DRC_4MIL_REPORT.txt and
SAME_NET_CLEARANCE_REPORT.txt from ONE rasterisation of the exported Gerbers.

Usage:  gerber_report.py GERBER_DIR OUT_DIR [--scratch DIR]
Exit 1 if the 6 mil check fails (6/6 mil is the ordered process).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import gerber_drc as D
import gerber_raster as R


def same_net_report(gdir, results):
    L = [
        "ZETTEL3090 — same-net clearance report (exported Gerbers)",
        "=" * 72,
        f"Gerber set : {gdir}",
        "",
        "Why this report exists",
        "  The board carries no netlist: every copper object is net-less. KiCad's",
        "  clearance DRC only compares copper of DIFFERENT nets, so for this board",
        "  it cannot see a gap at all. The generator therefore assigns every",
        "  connected copper island its own net before KiCad's DRC runs (so KiCad",
        "  DOES check island-to-island clearance), and this report measures the",
        "  Gerbers directly, which is what the fab etches.",
        "",
        "  'same-net' here = background narrower than the rule INSIDE one",
        "  connected copper feature (slot, notch, acid trap between two parts of",
        "  the same island). Such gaps cannot short anything, but a fab may flag",
        "  them as sub-minimum features. Corner crumbs shorter than max(2 x rule,",
        "  0.25 mm) are not notches and are not listed.",
        "",
    ]
    for rule, (viol, same, info) in results.items():
        L.append(f"Rule {rule} mil ({rule * D.MIL:.4f} mm): {len(same)} same-net gaps below the rule")
        L += D.fmt(same) or ["  (none)"]
        sp = [v for v in viol if v["kind"] == "spacing"]
        L.append(f"  for comparison — gaps between DIFFERENT copper features: {len(sp)}")
        L.append("")
    total6 = len(results[6][1])
    L.append("RESULT: " + ("PASS — no same-net gap below 6 mil" if total6 == 0
                           else f"REVIEW — {total6} same-net gaps below 6 mil"))
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("gdir")
    ap.add_argument("out")
    ap.add_argument("--scratch", default=None)
    a = ap.parse_args()
    gdir, out = Path(a.gdir), Path(a.out)
    scratch = Path(a.scratch or out / ".raster")
    layers = R.load_layers(gdir, scratch, R.DPMM)
    results = {}
    for rule in (6, 4):
        viol, same, info, _ = D.run(gdir, rule, scratch, layers=layers)
        results[rule] = (viol, same, info)
        txt = D.report(gdir.name, rule, viol, same, info)
        (out / f"DRC_{rule}MIL_REPORT.txt").write_text(txt)
        print(f"{rule} mil: {len(viol)} violations, {len(same)} same-net gaps -> "
              f"{'PASS' if not viol else 'FAIL'}")
    (out / "SAME_NET_CLEARANCE_REPORT.txt").write_text(same_net_report(gdir.name, results))
    print("same-net report written")
    sys.exit(1 if results[6][0] else 0)


if __name__ == "__main__":
    main()
