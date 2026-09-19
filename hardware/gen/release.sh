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
# The edition size lives in SERIALS/TOTAL below and is threaded through to
# build.py, the directory names and the verifier — so growing the run from two
# boards to three means editing exactly one line.
set -euo pipefail

ROOT=/data/projects/mini3090
PY=$ROOT/.venv/bin/python
GEN=$ROOT/hardware/gen
OUT=${1:-$ROOT/ZETTEL3090_FINAL}

SERIALS=(01 02 03)
TOTAL=$(printf '%02d' "${#SERIALS[@]}")

rm -rf "$OUT"
mkdir -p "$OUT"/{source,preview,verification}

echo "==> KiCad: $(kicad-cli version)"
echo "==> edition: ${#SERIALS[@]} boards (01..$TOTAL)"

for S in "${SERIALS[@]}"; do
  DIR="$OUT/board_${S}_of_${TOTAL}"
  mkdir -p "$DIR/gerbers"
  PCB="$OUT/source/ZETTEL3090_${S}.kicad_pcb"

  echo "==> board $S/$TOTAL: generating"
  "$PY" "$GEN/build.py" --serial "$S" --total "$TOTAL" --out "$PCB" \
      --info "$OUT/verification/board_${S}_stats.json" >/dev/null
  "$PY" "$GEN/stackup.py" "$PCB" >/dev/null
  "$PY" "$GEN/project.py" "$OUT/source/ZETTEL3090_${S}.kicad_pro" >/dev/null

  echo "==> board $S/$TOTAL: DRC (strict: only net-dependent rules may remain)"
  "$PY" "$GEN/strict_drc.py" "$PCB" \
      | tee "$OUT/verification/strict_drc_${S}.txt"
  kicad-cli pcb drc --severity-error --severity-warning \
      -o "$OUT/verification/drc_${S}.txt" "$PCB" \
      > "$OUT/verification/drc_${S}.log" 2>&1 || true

  echo "==> board $S/$TOTAL: gerbers + drill"
  kicad-cli pcb export gerbers \
      --layers F.Cu,B.Cu,F.Mask,B.Mask,F.Silkscreen,B.Silkscreen,Edge.Cuts \
      --no-protel-ext \
      -o "$DIR/gerbers/" "$PCB" > /dev/null
  kicad-cli pcb export drill --format excellon --excellon-separate-th \
      --generate-map --map-format gerberx2 --drill-origin absolute \
      --excellon-units mm --generate-report \
      --report-path "$OUT/verification/drill_report_${S}.txt" \
      -o "$DIR/gerbers/" "$PCB" > /dev/null

  # The drill MAP is documentation (a plot of drill symbols plus a legend
  # table). Fabs read the .drl; an online viewer renders the map as a bogus
  # extra layer covering the board. It stays in gerbers/ as a reference and
  # out of the ZIP that gets uploaded.
  #
  # The file list is explicit: with `zip *.gbr -x '*-drl_map.gbr'` the shell
  # expands the glob first and zip's exclude no longer matches, so the maps
  # end up in the archive anyway.
  ( cd "$DIR/gerbers" && zip -q "../ZETTEL3090_${S}_of_${TOTAL}_gerbers.zip" \
      "ZETTEL3090_${S}-F_Cu.gbr" \
      "ZETTEL3090_${S}-B_Cu.gbr" \
      "ZETTEL3090_${S}-F_Mask.gbr" \
      "ZETTEL3090_${S}-B_Mask.gbr" \
      "ZETTEL3090_${S}-F_Silkscreen.gbr" \
      "ZETTEL3090_${S}-B_Silkscreen.gbr" \
      "ZETTEL3090_${S}-Edge_Cuts.gbr" \
      "ZETTEL3090_${S}-PTH.drl" \
      "ZETTEL3090_${S}-NPTH.drl" \
      "ZETTEL3090_${S}-job.gbrjob" )
  cp "$DIR/gerbers"/*.drl "$DIR/" 2>/dev/null || true

  echo "==> board $S/$TOTAL: renders"
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
