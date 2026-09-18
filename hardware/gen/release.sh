#!/usr/bin/env bash
#
# Full production run for ZETTEL3090.
#
# Everything downstream of the KiCad board is produced BY KiCad: kicad-cli
# exports the Gerbers, the drill files and the renders. Nothing is hand-written
# and nothing is patched after export.
#
#   ./release.sh [OUTDIR]     default: <repo>/ZETTEL3090_FINAL
#
set -euo pipefail

ROOT=/data/projects/mini3090
PY=$ROOT/.venv/bin/python
GEN=$ROOT/hardware/gen
OUT=${1:-$ROOT/ZETTEL3090_FINAL}

rm -rf "$OUT"
mkdir -p "$OUT"/{source,preview,verification}

echo "==> KiCad: $(kicad-cli version)"

for S in 01 02; do
  DIR="$OUT/board_${S}_of_02"
  mkdir -p "$DIR/gerbers"
  PCB="$OUT/source/ZETTEL3090_${S}.kicad_pcb"

  echo "==> board $S/02: generating"
  "$PY" "$GEN/build.py" --serial "$S" --out "$PCB" \
      --info "$OUT/verification/board_${S}_stats.json" >/dev/null
  "$PY" "$GEN/stackup.py" "$PCB" >/dev/null
  "$PY" "$GEN/project.py" "$OUT/source/ZETTEL3090_${S}.kicad_pro" >/dev/null

  echo "==> board $S/02: DRC (strict: only net-dependent rules may remain)"
  "$PY" "$GEN/strict_drc.py" "$PCB" \
      | tee "$OUT/verification/strict_drc_${S}.txt"
  kicad-cli pcb drc --severity-error --severity-warning \
      -o "$OUT/verification/drc_${S}.txt" "$PCB" \
      > "$OUT/verification/drc_${S}.log" 2>&1 || true

  echo "==> board $S/02: gerbers + drill"
  kicad-cli pcb export gerbers \
      --layers F.Cu,B.Cu,F.Mask,B.Mask,F.Silkscreen,B.Silkscreen,Edge.Cuts \
      --no-protel-ext \
      -o "$DIR/gerbers/" "$PCB" > /dev/null
  kicad-cli pcb export drill --format excellon --excellon-separate-th \
      --generate-map --map-format gerberx2 --drill-origin absolute \
      --excellon-units mm --generate-report \
      --report-path "$OUT/verification/drill_report_${S}.txt" \
      -o "$DIR/gerbers/" "$PCB" > /dev/null

  ( cd "$DIR/gerbers" && zip -q -r "../ZETTEL3090_${S}_of_02_gerbers.zip" . )
  cp "$DIR/gerbers"/*.drl "$DIR/" 2>/dev/null || true

  echo "==> board $S/02: renders"
  kicad-cli pcb render --side top    -o "$OUT/preview/board_${S}_front_3d.png" \
      -w 3000 --height 1400 --quality high --zoom 1.1 --rotate '-20,0,0' \
      --perspective "$PCB" > /dev/null
  kicad-cli pcb render --side bottom -o "$OUT/preview/board_${S}_back_3d.png" \
      -w 3000 --height 1400 --quality high --zoom 1.1 --rotate '-20,0,0' \
      --perspective "$PCB" > /dev/null
  kicad-cli pcb render --side top    -o "$OUT/preview/board_${S}_front.png" \
      -w 4400 --height 2000 --quality high --zoom 1.15 "$PCB" > /dev/null
  kicad-cli pcb render --side bottom -o "$OUT/preview/board_${S}_back.png" \
      -w 4400 --height 2000 --quality high --zoom 1.15 "$PCB" > /dev/null
done

echo "==> verification"
cp "$GEN/ORDER_README.md" "$OUT/ORDER_README.md"
"$PY" "$GEN/verify.py" "$OUT" | tee "$OUT/verification/REPORT.txt"

echo
echo "done -> $OUT"
