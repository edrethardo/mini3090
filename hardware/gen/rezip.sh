#!/usr/bin/env bash
# Rebuild one board's upload ZIP from the already-exported Gerbers.
# Same file list as release.sh, without re-running the whole export.
set -euo pipefail
S=${1:-01}
DIR="/data/projects/mini3090/ZETTEL3090_FINAL/board_${S}_of_02"
ZIP="$DIR/ZETTEL3090_${S}_of_02_gerbers.zip"

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
