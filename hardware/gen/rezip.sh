#!/usr/bin/env bash
# Rebuild the single upload ZIP from the already-exported Gerbers.
# Same file list as release.sh, without re-running the whole export.
#
#   ./rezip.sh [OUTDIR]     default: <repo>/ZETTEL3090_FINAL
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT=${1:-$ROOT/ZETTEL3090_FINAL}
ZIP="$OUT/ZETTEL3090_PCBWAY_STANDARD.zip"
N=ZETTEL3090

rm -f "$ZIP"
cd "$OUT/gerbers"
zip -q "$ZIP" \
    "$N-F_Cu.gbr" "$N-B_Cu.gbr" \
    "$N-F_Mask.gbr" "$N-B_Mask.gbr" \
    "$N-F_Silkscreen.gbr" "$N-B_Silkscreen.gbr" \
    "$N-Edge_Cuts.gbr" \
    "$N-PTH.drl" "$N-NPTH.drl" \
    "$N-job.gbrjob"
unzip -l "$ZIP"
