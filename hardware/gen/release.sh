#!/usr/bin/env bash
#
# Full production run for ZETTEL3090 — ONE design, ONE Gerber set.
#
# Every board of the edition is fabricated from the same files. The front
# carries "/03" in silkscreen after a blank field of bare matte-black mask;
# the individual number (01, 02, 03) is written in by hand after
# fabrication. PCBWay therefore sees exactly one design (no multi-design or
# panel surcharge).
#
# Everything downstream of the KiCad board is produced BY KiCad (kicad-cli)
# or measured FROM the exported Gerbers. Nothing is patched after export.
#
#   ./release.sh [OUTDIR]     default: <repo>/ZETTEL3090_FINAL
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/env.sh"
OUT=${1:-$ROOT/ZETTEL3090_FINAL}

TOTAL=03            # printed edition size ("/03"); the ONLY place it lives
NAME=ZETTEL3090
ZIP=ZETTEL3090_PCBWAY_STANDARD.zip

rm -rf "$OUT"
mkdir -p "$OUT"/{source,gerbers,preview,verification}
PCB="$OUT/source/$NAME.kicad_pcb"
G="$OUT/gerbers"
V="$OUT/verification"

echo "==> KiCad: $(kicad-cli version)"
echo "==> one design, edition marking /$TOTAL (number written by hand)"

echo "==> generating"
"$PY" "$GEN/build.py" --total "$TOTAL" --out "$PCB" --info "$V/board_stats.json" >/dev/null
"$PY" "$GEN/stackup.py" "$PCB" >/dev/null
"$PY" "$GEN/project.py" "$OUT/source/$NAME.kicad_pro" >/dev/null

echo "==> KiCad DRC"
"$PY" "$GEN/strict_drc.py" "$PCB" | tee "$V/strict_drc.txt"
kicad-cli pcb drc --severity-error --severity-warning \
    -o "$V/kicad_drc.txt" "$PCB" > "$V/kicad_drc.log" 2>&1 || true

echo "==> gerbers + drill + job"
kicad-cli pcb export gerbers \
    --layers F.Cu,B.Cu,F.Mask,B.Mask,F.Silkscreen,B.Silkscreen,Edge.Cuts \
    --no-protel-ext -o "$G/" "$PCB" > /dev/null
kicad-cli pcb export drill --format excellon --excellon-separate-th \
    --generate-map --map-format gerberx2 --drill-origin absolute \
    --excellon-units mm --generate-report --report-path "$V/drill_report.txt" \
    -o "$G/" "$PCB" > /dev/null

# Explicit file list: the drill MAP is documentation, not fab data (a viewer
# shows it as a bogus extra layer), so it stays out of the upload. A glob
# with zip -x does not work: the shell expands it before zip sees the -x.
( cd "$G" && zip -q "../$ZIP" \
    "$NAME-F_Cu.gbr" "$NAME-B_Cu.gbr" \
    "$NAME-F_Mask.gbr" "$NAME-B_Mask.gbr" \
    "$NAME-F_Silkscreen.gbr" "$NAME-B_Silkscreen.gbr" \
    "$NAME-Edge_Cuts.gbr" \
    "$NAME-PTH.drl" "$NAME-NPTH.drl" \
    "$NAME-job.gbrjob" )

echo "==> geometric DRC on the exported Gerbers (6 mil, 4 mil, same-net)"
( cd "$GEN" && "$PY" gerber_report.py "$G" "$OUT" --scratch "$V/.raster" ) \
    | tee "$V/gerber_drc.log"

echo "==> renders"
R() { kicad-cli pcb render --use-board-stackup-colors "$@" "$PCB" > /dev/null; }
R --side top    -o "$OUT/preview/front.png" -w 4400 --height 2000 --quality high --zoom 1.15
R --side bottom -o "$OUT/preview/back.png"  -w 4400 --height 2000 --quality high --zoom 1.15
R --side top    -o "$OUT/preview/front_3d.png" -w 3000 --height 1400 --quality high \
    --zoom 1.1 --rotate '-20,0,0' --perspective
R --side bottom -o "$OUT/preview/back_3d.png"  -w 3000 --height 1400 --quality high \
    --zoom 1.1 --rotate '-20,0,0' --perspective

echo "==> gerber viewer screenshots + number field detail"
( cd "$GEN" && "$PY" gerber_views.py "$G" "$OUT/preview" "$V/board_stats.json" \
    "$OUT/preview/front.png" --scratch "$V/.raster" )

echo "==> docs"
cp "$GEN/docs/PCBWAY_ORDER_SETTINGS.md" "$GEN/docs/PCBWAY_MANUFACTURING_NOTES.md" "$OUT/"

echo "==> verification"
"$PY" "$GEN/verify.py" "$OUT" | tee "$V/REPORT.txt"
rm -rf "$V/.raster"

echo
echo "done -> $OUT"
