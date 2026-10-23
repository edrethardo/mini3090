# ZETTEL3090 — Manufacturing Notes (PCBWay)

Decorative, unpopulated 2-layer board: a miniature of an RTX 3090 PCB, Berlin
skyline in ENIG gold on the back, scannable QR code to the project.

    RTX 3090 → Nemotron 3.5 → Zettel → GTC Berlin 2026

Source of truth is the KiCad project in `source/`. All fabrication data was
exported by `kicad-cli` from exactly that board; nothing was edited by hand
afterwards.

## 1. One design, hand-numbered edition

| | |
|---|---|
| Designs | **1** — one layout, one Gerber set |
| Edition | 3 boards, numbered `01/03`, `02/03`, `03/03` |
| Printed by the fab | only **`/03`** (white silkscreen, top side) |
| Written by hand | the two digits in front of `/03` |

Gerber state of every board:

    [          ] /03

After hand-numbering:

    01/03    02/03    03/03

### The number field

| Property | Value |
|---|---|
| Size | **10.0 × 5.0 mm** (minimum asked: 8 × 4 mm) |
| Surface | bare **matte-black solder mask** over laminate |
| Inside the field | no silkscreen, no copper, no mask opening (no ENIG), no drill |
| Clear margin | ≥ 0.8 mm around the field: no copper, no mask opening |
| Back side behind the field | the QR copper plate lies on the reverse; invisible through 1.6 mm FR-4 + opaque mask, the front surface stays flat |
| Frame | none: the field is plain black mask, no marks |
| `/03` | white silkscreen, 2.0 mm high, 0.30 mm stroke, same stroke font as the other technical legends |
| Field → `/03` | 0.6 mm, so the written digits read as part of the marking |

All of the above is measured on the exported Gerbers by `verify.py` (see
`verification/REPORT.txt`), not taken from the generator's intent.

### Writing the number

- Use an **opaque white (or silver) paint marker**, fine tip 0.7–1.0 mm
  (e.g. uni Paint PX-21, edding 780). Matte mask takes paint well.
- Clean the field with isopropyl alcohol first and let it dry.
- Write the digits about 2.5 mm high, right-aligned to `/03`, on the
  baseline of `/03`, directly in front of it.
- Let it cure; optionally seal with a drop of clear lacquer.
- Boards 4 and 5 (spares from the minimum quantity) stay unnumbered or are
  marked `00`/`AP` — they are not part of the edition.

## 2. Contents of `ZETTEL3090_PCBWAY_STANDARD.zip`

| File | Layer |
|---|---|
| `ZETTEL3090-F_Cu.gbr` | top copper |
| `ZETTEL3090-B_Cu.gbr` | bottom copper |
| `ZETTEL3090-F_Mask.gbr` | top solder mask |
| `ZETTEL3090-B_Mask.gbr` | bottom solder mask |
| `ZETTEL3090-F_Silkscreen.gbr` | top silkscreen |
| `ZETTEL3090-B_Silkscreen.gbr` | bottom silkscreen |
| `ZETTEL3090-Edge_Cuts.gbr` | board outline |
| `ZETTEL3090-PTH.drl` | plated holes (vias, 0.3 mm) |
| `ZETTEL3090-NPTH.drl` | non-plated holes (4 mounting holes, 2.2 mm) |
| `ZETTEL3090-job.gbrjob` | Gerber job file (layer assignment, stackup) |

Format: Gerber X2, mm, absolute coordinates; drills Excellon, mm. The drill
map (`*-drl_map.gbr`) is documentation only and deliberately **not** in the
ZIP (online viewers would show it as an extra layer).

## 3. Design rules and what was checked

Target process: PCBWay standard, **6/6 mil**.

| Rule | Design value | PCBWay standard |
|---|---|---|
| min track width | 0.16 mm (6.3 mil) | 0.1524 mm (6 mil) |
| min copper spacing | 0.16 mm (6.3 mil) | 0.1524 mm (6 mil) |
| via drill / pad | 0.30 / 0.60 mm | ≥ 0.3 mm |
| annular ring | 0.15 mm | ≥ 0.15 mm |
| copper to board edge | ≥ 0.6 mm | ≥ 0.3 mm |
| silkscreen stroke | ≥ 0.15 mm | ≥ 0.15 mm |

Reports in this package:

- `DRC_6MIL_REPORT.txt`: geometric DRC measured on the **exported Gerbers**
  at 6 mil: spacing between separate copper features, track width, copper
  to edge, annular ring.
- `DRC_4MIL_REPORT.txt`: the same at 4 mil (margin check).
- `SAME_NET_CLEARANCE_REPORT.txt`: narrow gaps *inside* one connected
  copper feature (notches, slots).
- `verification/kicad_drc.txt`, `verification/strict_drc.txt`: KiCad's own
  DRC.

**Why the Gerber DRC exists.** The board has no schematic and therefore no
netlist. KiCad's clearance check only compares copper of *different* nets;
on a net-less board it would not report two traces 0.02 mm apart. The
generator therefore (a) resolves every near-miss between separate copper
features before export and (b) gives every connected copper island its own
net, so KiCad's clearance DRC actually applies. The Gerber DRC then measures
what the fab will etch, independent of any net logic.

KiCad DRC categories that remain by design (see `strict_drc.txt`):

- **net-dependent** (`track_dangling`, `via_dangling`, `solder_mask_bridge`):
  decorative tracks end nowhere by intent; unavoidable without a netlist.
- **cosmetic** (`silk_over_copper`, `silk_overlap`): component designators
  and outlines touching gold pads are intended. The GPU die itself is plain
  gold with no marking.

## 4. Other checks (`verification/REPORT.txt`)

- exactly one board, one Gerber set, one ZIP with exactly the 10 fab files
- outline 110.00 × 48.00 mm, measured from Edge.Cuts
- QR code decodes from the rendered back to `https://github.com/edrethardo/zettel`;
  error correction H, 4-module quiet zone, no hole or silk inside
- `/03` exactly once, in F.Silkscreen, 2.0 mm / 0.30 mm; no board-specific
  number anywhere in the artwork
- number field empty on front silk, copper and mask; no drill nearby
- back-side text is mirrored in the source, so it reads correctly from the back
- gold stays below 50 % of the board area, so black dominates

## 5. Previews

| File | Content |
|---|---|
| `preview/front.png`, `preview/back.png` | KiCad render, top/bottom |
| `preview/front_3d.png`, `preview/back_3d.png` | perspective renders |
| `preview/gerber_front.png`, `preview/gerber_back.png` | composited from the Gerbers (fab-viewer view) |
| `preview/gerber_layers_front.png`, `_back.png` | copper, mask and silk panels from the Gerbers |
| `preview/number_field_detail.png` | number field: Gerber state, dimensions, render, and a 01/02/03 hand-numbering illustration |

## 6. Rebuild

From the root of a checkout:

```bash
./setup.sh                           # once: .venv with the Python deps
./hardware/gen/release.sh            # -> ZETTEL3090_FINAL/
```

Needs KiCad 9 (`kicad-cli`, `pcbnew` Python bindings); see the repo README.

## 7. Legal

NVIDIA, GeForce, RTX and GA102 are trademarks of NVIDIA Corporation. This
project is unofficial and non-functional, and it is not affiliated with
NVIDIA. No NVIDIA schematics or layout data were used. The look is freely
modelled on publicly visible board photos, and no NVIDIA logos or protected
design elements are shown.
