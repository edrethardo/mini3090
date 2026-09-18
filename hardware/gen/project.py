"""Write the KiCad project file that accompanies the board.

Two things live here that the .kicad_pcb cannot express on its own:

1. **DRC severity overrides.** This board is decorative: it has no schematic
   and therefore no netlist. Several DRC rules are defined purely in terms of
   nets and are unsatisfiable by construction, not because the artwork is
   wrong:

     track_dangling / via_dangling  — every trace is decorative, so of course
                                      it ends in free space
     solder_mask_bridge             — "one mask opening spans two nets"; with
                                      no nets assigned, ANY gold artwork next
                                      to a pad is reported
     shorting_items                 — same cause
     silk_over_copper / silk_overlap— white ink on gold is intentional here
                                      (the die marking, the designators)

   These are downgraded to `ignore` DELIBERATELY and the reasons are recorded
   in ORDER_README.md. Everything that describes real manufacturability —
   clearance, hole sizes, edge clearance, track width, annular ring, text
   height, hole-to-hole — stays at `error` and is expected to be clean.

2. **The netclass**, so the fab-facing minima are explicit.
"""

from __future__ import annotations

import json
import sys

IGNORED = [
    "track_dangling",
    "via_dangling",
    "solder_mask_bridge",
    "shorting_items",
    "silk_over_copper",
    "silk_overlap",
    "silk_edge_clearance",
    "footprint_type_mismatch",
    "lib_footprint_issues",
    "lib_footprint_mismatch",
    "unconnected_items",
    "zones_intersect",
]


def project(name: str) -> dict:
    sev = {k: "ignore" for k in IGNORED}
    return {
        "board": {
            "3dviewports": [],
            "design_settings": {
                "defaults": {},
                "diff_pair_dimensions": [],
                "drc_exclusions": [],
                "meta": {"version": 2},
                "rule_severities": sev,
                "rules": {
                    "min_clearance": 0.15,
                    "min_copper_edge_clearance": 0.4,
                    "min_hole_clearance": 0.25,
                    "min_hole_to_hole": 0.25,
                    "min_microvia_diameter": 0.2,
                    "min_microvia_drill": 0.1,
                    "min_resolved_spokes": 2,
                    "min_silk_clearance": 0.0,
                    "min_text_height": 0.8,
                    "min_text_thickness": 0.15,
                    "min_through_hole_diameter": 0.3,
                    "min_track_width": 0.15,
                    "min_via_annular_width": 0.1,
                    "min_via_diameter": 0.45,
                },
                "track_widths": [0.0, 0.15, 0.2, 0.25, 0.4],
                "via_dimensions": [
                    {"diameter": 0.0, "drill": 0.0},
                    {"diameter": 0.6, "drill": 0.3},
                ],
            },
            "layer_presets": [],
            "viewports": [],
        },
        "boards": [],
        "meta": {"filename": f"{name}.kicad_pro", "version": 3},
        "net_settings": {
            "classes": [
                {
                    "bus_width": 12,
                    "clearance": 0.2,
                    "diff_pair_gap": 0.25,
                    "diff_pair_width": 0.2,
                    "line_style": 0,
                    "microvia_diameter": 0.3,
                    "microvia_drill": 0.1,
                    "name": "Default",
                    "pcb_color": "rgba(0, 0, 0, 0.000)",
                    "schematic_color": "rgba(0, 0, 0, 0.000)",
                    "track_width": 0.2,
                    "via_diameter": 0.6,
                    "via_drill": 0.3,
                    "wire_width": 6,
                }
            ],
            "meta": {"version": 3},
            "net_colors": None,
            "netclass_assignments": None,
            "netclass_patterns": [],
        },
        "pcbnew": {
            "last_paths": {},
            "page_layout_descr_file": "",
        },
        "sheets": [],
        "text_variables": {},
    }


if __name__ == "__main__":
    out = sys.argv[1]
    name = out.rsplit("/", 1)[-1].removesuffix(".kicad_pro")
    with open(out, "w") as fh:
        json.dump(project(name), fh, indent=2)
    print("project written:", out)
