# ZETTEL3090 — PCBWay Order Settings

**One design. One Gerber set. Every board is fabricated from the same files.**

Upload: `ZETTEL3090_PCBWAY_STANDARD.zip` (the only fabrication file).

| Option | Value |
|---|---|
| Board type | **Single pieces** |
| Different Designs | **1** |
| Quantity | **5** (PCBWay's cheapest standard quantity; 3 are numbered 01–03, 2 spares) |
| Size | **110 × 48 mm** (read from Edge.Cuts automatically) |
| Layers | **2** |
| Material | **FR-4** (TG 150–160, standard) |
| Thickness | **1.6 mm** |
| Min Track/Spacing | **6/6 mil** |
| Min Hole Size | **0.3 mm** |
| Solder Mask | **Matte Black** |
| Silkscreen | **White** |
| Edge connector / Gold fingers | **No** |
| Surface Finish | **Immersion Gold (ENIG)** |
| Gold Thickness | **Standard / 1U″** |
| Via Process | **Tenting vias** |
| Finished Copper | **1 oz Cu** |
| E-Test | **Standard** (flying probe / default) |
| Edge Plating | **No** |
| Impedance Control | **No** |
| Castellated Holes | **No** |
| Remove product No. | **Yes** (“Specify a location” is *not* wanted — nothing may be printed into the number field or the skyline) |
| Assembly / stencil | **No** (bare boards) |

## What “Different Designs: 1” means here

- The ZIP contains exactly **one** board outline, one set of copper, mask,
  silkscreen and drill files. There is no panel and no second design, so no
  multi-design or mixed-panel surcharge applies.
- All boards are **identical**: copper, mask, silkscreen, drills, outline, QR
  code and ENIG areas.
- The edition marking is printed as **`/03`** only. The board number (`01`,
  `02`, `03`) is written in by hand after delivery, in the blank field
  directly in front of `/03` (see `PCBWAY_MANUFACTURING_NOTES.md`).

## Notes for the order form / engineer

> Decorative, non-functional PCB. One design, no netlist. Please do not add an
> order number / product number anywhere. The blank 10 × 5 mm area of black
> solder mask in front of the white "/03" on the top side is intentional and
> must stay blank (hand-numbered by the customer). Isolated copper and tracks
> ending without connection are intentional artwork.
