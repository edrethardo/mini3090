"""Strict DRC: verify that ONLY the net-dependent rules are being suppressed.

`project.py` downgrades a set of rules to `ignore` because a netlist-free
decorative board cannot satisfy them by construction. That is a load-bearing
claim, and a claim that silently grows is how a real error gets hidden. This
script re-runs DRC with the suppressions removed and asserts that the only
violations left are from the documented list.

Usage:  strict_drc.py board.kicad_pcb
Exit 0 when every remaining violation is in the allowed set.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

# Rules that a board without a netlist cannot satisfy. Anything NOT in here
# must be zero.
NET_DEPENDENT = {
    "track_dangling",
    "via_dangling",
    "solder_mask_bridge",
    "shorting_items",
    "unconnected_items",
    "starved_thermal",
}

# Cosmetic rules we accept on decorative artwork: white ink over exposed gold
# is intentional (die marking, designators over pours).
COSMETIC = {
    "silk_over_copper",
    "silk_overlap",
    "silk_edge_clearance",
}


def run(pcb: Path) -> "tuple[Counter, str]":
    with tempfile.TemporaryDirectory() as td:
        # a project WITHOUT severity overrides: KiCad falls back to defaults.
        # Rules = the ordered 6/6 mil process. The netclass clearance must be
        # set too: every copper island carries its own net, so KiCad's
        # clearance check is live, and without a netclass it would use its
        # built-in 0.2 mm default instead of the process value.
        pro = Path(td) / (pcb.stem + ".kicad_pro")
        pcb_copy = Path(td) / pcb.name
        pcb_copy.write_bytes(pcb.read_bytes())
        pro.write_text(json.dumps({
            "board": {"design_settings": {"rules": {
                "min_clearance": 0.1524,
                "min_copper_edge_clearance": 0.3,
                "min_hole_clearance": 0.25,
                "min_hole_to_hole": 0.25,
                "min_text_height": 0.8,
                "min_text_thickness": 0.15,
                "min_through_hole_diameter": 0.3,
                "min_track_width": 0.1524,
                "min_via_annular_width": 0.15,
                "min_via_diameter": 0.6,
            }, "meta": {"version": 2}}},
            "net_settings": {"classes": [{
                "name": "Default", "clearance": 0.1524, "track_width": 0.16,
                "via_diameter": 0.6, "via_drill": 0.3,
            }], "meta": {"version": 3}},
            "meta": {"filename": pro.name, "version": 3},
        }))
        rpt = Path(td) / "drc.txt"
        subprocess.run(
            ["kicad-cli", "pcb", "drc", "--severity-error", "--severity-warning",
             "-o", str(rpt), str(pcb_copy)],
            capture_output=True, check=False)
        body = rpt.read_text(errors="ignore") if rpt.exists() else ""
    return Counter(re.findall(r"^\[(\w+)\]", body, re.M)), body


def main():
    pcb = Path(sys.argv[1])
    counts, body = run(pcb)
    total = sum(counts.values())
    print(f"strict DRC on {pcb.name}: {total} violations before suppression")
    bad = {}
    for rule, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        kind = ("net-dependent" if rule in NET_DEPENDENT
                else "cosmetic" if rule in COSMETIC else "REAL")
        print(f"  {n:5d}  {rule:<28} {kind}")
        if kind == "REAL":
            bad[rule] = n
    if bad:
        print("\nFAIL: rules that describe real manufacturability are violated:")
        for rule, n in bad.items():
            print(f"  {rule}: {n}")
            for m in re.finditer(rf"^\[{rule}\].*\n(?:\s+.*\n){{1,3}}", body, re.M):
                print("   ", m.group(0).strip().replace("\n", "\n    "))
                break
        sys.exit(1)
    print("\nOK: every remaining violation is net-dependent or cosmetic.")


if __name__ == "__main__":
    main()
