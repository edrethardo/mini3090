#!/usr/bin/env bash
# Iteration helper: rebuild one board, render both sides, crop review images.
#
#   ./iterate.sh [OUTDIR] [SERIAL] [TOTAL]
set -euo pipefail
ROOT=/data/projects/mini3090
PY=$ROOT/.venv/bin/python
GEN=$ROOT/hardware/gen
OUT=${1:-/tmp/z}
SERIAL=${2:-01}
TOTAL=${3:-03}
mkdir -p "$OUT"

"$PY" "$GEN/build.py" --serial "$SERIAL" --total "$TOTAL" \
    --out "$OUT/t.kicad_pcb" --info "$OUT/stats.json" >/dev/null
"$PY" "$GEN/stackup.py" "$OUT/t.kicad_pcb" >/dev/null

kicad-cli pcb render --side top    -o "$OUT/f_hi.png" -w 4400 --height 2000 \
    --quality high --zoom 1.15 "$OUT/t.kicad_pcb" >/dev/null
kicad-cli pcb render --side bottom -o "$OUT/b_hi.png" -w 4400 --height 2000 \
    --quality high --zoom 1.15 "$OUT/t.kicad_pcb" >/dev/null

"$PY" - "$OUT" <<'EOF'
import sys, cv2
out = sys.argv[1]
f = cv2.imread(f"{out}/f_hi.png"); b = cv2.imread(f"{out}/b_hi.png")
h, w, _ = f.shape
for tag, img in (("f", f), ("b", b)):
    cv2.imwrite(f"{out}/{tag}_small.png", cv2.resize(img, (w // 3, h // 3)))
cv2.imwrite(f"{out}/crop_sky.png",   b[int(h*.26):int(h*.76), int(w*.32):int(w*.72)])
cv2.imwrite(f"{out}/crop_gpu.png",   f[int(h*.25):int(h*.80), int(w*.28):int(w*.56)])
cv2.imwrite(f"{out}/crop_brand.png", f[int(h*.28):int(h*.80), int(w*.64):int(w*.94)])
cv2.imwrite(f"{out}/crop_qr.png",    b[int(h*.22):int(h*.82), int(w*.08):int(w*.34)])
g = cv2.cvtColor(b, cv2.COLOR_BGR2GRAY)
print("QR:", repr(cv2.QRCodeDetector().detectAndDecode(g)[0]))
EOF
echo "ok -> $OUT"
