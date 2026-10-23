# mini3090 — ZETTEL3090

**English** · [Deutsch](README.de.md)

A decorative miniature circuit board in the style of an RTX 3090, made as a
gift for Jensen Huang at NVIDIA GTC Berlin 2026.

The back carries the Berlin skyline in gold-plated copper and a scannable QR
code pointing to [github.com/edrethardo/zettel](https://github.com/edrethardo/zettel) —
the project that ran locally with NVIDIA Nemotron 3.5 on an RTX 3090.

    RTX 3090 → Nemotron 3.5 → Zettel → GTC Berlin 2026

**One design, one Gerber set.** All boards are identical. The front only
shows `/03` in white silkscreen, preceded by a blank 10 × 5 mm field of matte
black solder mask. The individual number (`01`, `02`, `03`) is written in by
hand with a paint marker after fabrication. At PCBWay: Different Designs 1.
The edition size lives in exactly one place — `TOTAL` in
`hardware/gen/release.sh`.

## The key idea

The board is **generated, not drawn**: Python uses KiCad's own `pcbnew` API to
build a real `.kicad_pcb`, and `kicad-cli` exports the Gerbers, drill files and
preview images from it. There are no hand-made Gerbers and no renders showing
anything that is not in the layout.

| | |
|---|---|
| Size | 110 × 48 mm, 2 layers, FR-4 1.6 mm |
| Surface finish | ENIG — the skyline is real gold-plated copper |
| Colours | black solder mask, white silkscreen |
| Function | none. No schematic, no netlist, no components. |

## Building

Requirements:

- **KiCad 9** with `kicad-cli` and the `pcbnew` Python bindings
  (Ubuntu/Debian: `sudo add-apt-repository ppa:kicad/kicad-9.0-releases &&
  sudo apt install kicad`; other systems: [kicad.org/download](https://www.kicad.org/download/))
- `python3` with `venv`, `bash`, `zip`

```bash
git clone https://github.com/edrethardo/mini3090.git
cd mini3090
./setup.sh                    # once: .venv with the Python dependencies
./hardware/gen/release.sh     # -> ZETTEL3090_FINAL/
```

`setup.sh` looks for the Python that KiCad was installed for (the only one
that can import `pcbnew`), creates `.venv` from it with
`--system-site-packages` and installs `requirements.txt`. If KiCad's Python
lives somewhere else: `KICAD_PYTHON=/path/to/python3 ./setup.sh`. The scripts
work from any checkout location; set `PYTHON=...` to use a different
interpreter.

A full run takes a few minutes (measured: just under 7 min).
Tested with KiCad 9.0.9 on Ubuntu 24.04. macOS and Windows are untested.

For a quick design iteration without the full export:

```bash
./hardware/gen/iterate.sh     # -> build/iterate/: board, both sides rendered, QR checked
```

## Output

`ZETTEL3090_FINAL/` — `ZETTEL3090_PCBWAY_STANDARD.zip` (the only fabrication
file), KiCad sources, `PCBWAY_ORDER_SETTINGS.md`,
`PCBWAY_MANUFACTURING_NOTES.md`, `DRC_6MIL_REPORT.txt`, `DRC_4MIL_REPORT.txt`,
`SAME_NET_CLEARANCE_REPORT.txt`, renders, Gerber views, a close-up of the
number field and `verification/REPORT.txt`.

## Generator layout

```
hardware/gen/
  layout.py      All dimensions in one place: outline, component grid, keepouts
  kicadlib.py    Thin wrapper around pcbnew: shapes, pads, text, gold helpers
  occupancy.py   Occupancy map (0.05 mm/cell) — the placement guard
  blocks.py      Building blocks: BGA, GDDR6X, QFN, choke, bus, via field …
  skyline.py     Berlin skyline made of copper traces
  qr.py          QR code as copper + solder-mask openings
  build.py       Assembles the board
  stackup.py     Writes colours/surface finish into the board file
  project.py     .kicad_pro with DRC severities and net class
  clearance.py   Copper clearances without a netlist: islands, near-contacts
  strict_drc.py  DRC WITHOUT suppressions — aborts on real errors
  gerber_raster.py / gerber_drc.py / gerber_report.py
                 Geometric DRC on the exported Gerbers (6/4 mil)
  gerber_views.py  Gerber views + number-field close-up
  verify.py      Checks the EXPORTED data (not the intent)
  env.sh         Shared script setup: repo root, Python, tool checks
  docs/          PCBWay order settings and manufacturing notes (English)
  release.sh     The full production run
  iterate.sh     Short design loop
```

### Two design decisions that carry everything

**The placement guard.** A generated board has no router to resolve
conflicts. So before placing anything, every object asks an occupancy map
whether its area is free — including the drill grid and the board edge. This
replaces loosening the design rules afterwards: instead of ignoring errors,
they never arise.

**Two phases.** All real components are placed first, decoration (traces,
vias, scattered parts) only afterwards. The other way round, the fanout of one
memory chip takes the space of the next, and the guard silently drops exactly
the components that make the design.

### Why the DRC has exceptions

Without a netlist some rules can never be satisfied: every trace is
decoration and ends in nothing (`track_dangling`), and every solder-mask
opening by definition sits over "different nets" (`solder_mask_bridge`).
These rules are deliberately disabled in `project.py`, with the reasons
given there.

So that this list cannot grow unnoticed and hide real errors, `strict_drc.py`
runs the same check **without** suppressions and aborts as soon as a rule is
violated that describes actual manufacturability — clearances, drills, edge
clearance, trace width, annular ring, text height.

## License

[MIT](LICENSE) — generator, scripts and documentation.

## Legal

NVIDIA, GeForce, RTX and GA102 are trademarks of NVIDIA Corporation. This
project is unofficial and non-functional, and it is not affiliated with
NVIDIA. No NVIDIA schematics or layout data were used; the look is freely
modelled on publicly visible board photos. No NVIDIA logos or protected
design elements are shown.
