#!/usr/bin/env bash
# Rebuild one board's upload ZIP from the already-exported Gerbers.
# Same file list as release.sh, without re-running the whole export.
#
#   ./rezip.sh 03           # edition size is read from the directory name
set -euo pipefail
S=${1:-01}
ROOT="/data/projects/mini3090/ZETTEL3090_FINAL"
DIR=$(echo "$ROOT/board_${S}_of_"*)
if [ ! -d "$DIR" ]; then
  echo "no board directory for serial $S under $ROOT" >&2
  exit 1
fi
TOTAL=${DIR##*_of_}
ZIP="$DIR/ZETTEL3090_${S}_of_${TOTAL}_gerbers.zip"

rm -f "$ZIP"
cd "$DIR/gerbers"
zip -q "$ZIP" \
    "ZETTEL3090_${S}-F_Cu.gbr" \
    "ZETTEL3090_${S}-B_Cu.gbr" \
    "ZETTEL3090_${S}-F_Mask.gbr" \
    "ZETTEL3090_${S}-B_Mask.gbr" \
    "ZETTEL3090_${S}-F_Silkscreen.gbr" \
    "ZETTEL3090_${S}-B_Silkscreen.gbr" \
    "ZETTEL3090_${S}-Edge_Cuts.gbr" \
    "ZETTEL3090_${S}-PTH.drl" \
    "ZETTEL3090_${S}-NPTH.drl" \
    "ZETTEL3090_${S}-job.gbrjob"
unzip -l "$ZIP"
