"""Inject the physical stackup (colours, finish, thickness) into a saved board.

The pcbnew SWIG bindings do not expose BOARD_STACKUP, but the stackup is plain
s-expression data in the .kicad_pcb file — and the .kicad_pcb file IS our
source of truth, so writing it here is a source edit, not a Gerber patch.

Colours matter for this board: black solder mask, white silkscreen, ENIG gold.
`kicad-cli pcb render --use-board-stackup-colors` reads exactly this block.
"""

from __future__ import annotations

import re
import sys

STACKUP = """\t\t(stackup
\t\t\t(layer "F.SilkS"
\t\t\t\t(type "Top Silk Screen")
\t\t\t\t(color "White")
\t\t\t)
\t\t\t(layer "F.Paste"
\t\t\t\t(type "Top Solder Paste")
\t\t\t)
\t\t\t(layer "F.Mask"
\t\t\t\t(type "Top Solder Mask")
\t\t\t\t(color "Black")
\t\t\t\t(thickness 0.01)
\t\t\t)
\t\t\t(layer "F.Cu"
\t\t\t\t(type "copper")
\t\t\t\t(thickness 0.035)
\t\t\t)
\t\t\t(layer "dielectric 1"
\t\t\t\t(type "core")
\t\t\t\t(thickness 1.51)
\t\t\t\t(material "FR4")
\t\t\t\t(epsilon_r 4.5)
\t\t\t\t(loss_tangent 0.02)
\t\t\t)
\t\t\t(layer "B.Cu"
\t\t\t\t(type "copper")
\t\t\t\t(thickness 0.035)
\t\t\t)
\t\t\t(layer "B.Mask"
\t\t\t\t(type "Bottom Solder Mask")
\t\t\t\t(color "Black")
\t\t\t\t(thickness 0.01)
\t\t\t)
\t\t\t(layer "B.Paste"
\t\t\t\t(type "Bottom Solder Paste")
\t\t\t)
\t\t\t(layer "B.SilkS"
\t\t\t\t(type "Bottom Silk Screen")
\t\t\t\t(color "White")
\t\t\t)
\t\t\t(copper_finish "ENIG")
\t\t\t(dielectric_constraints no)
\t\t)
"""


def apply(path: str) -> None:
    with open(path, "r", encoding="utf-8") as fh:
        src = fh.read()

    if "(stackup" in src:
        return

    m = re.search(r"\n\t\(setup\n", src)
    if not m:
        raise SystemExit(f"no (setup block found in {path}")
    at = m.end()
    src = src[:at] + STACKUP + src[at:]

    with open(path, "w", encoding="utf-8") as fh:
        fh.write(src)


if __name__ == "__main__":
    for p in sys.argv[1:]:
        apply(p)
        print("stackup applied:", p)
