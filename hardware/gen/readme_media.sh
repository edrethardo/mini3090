#!/usr/bin/env bash
# Regenerate the pictures and 3D models shown in the README.
#
# Same rule as the fab data: everything is rendered/exported BY KiCad from the
# generated board — no hand-made images.
#
#   ./readme_media.sh          -> docs/images/*.jpg, docs/3d/ZETTEL3090.{glb,stl}
#
# Extra requirement (only for this script): Node.js/npx, used to Draco-compress
# the GLB with @gltf-transform/cli (27 MB -> ~1 MB).
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/env.sh"

TMP="$ROOT/build/media"
IMG="$ROOT/docs/images"
M3D="$ROOT/docs/3d"
PCB="$TMP/ZETTEL3090.kicad_pcb"
rm -rf "$TMP"; mkdir -p "$TMP" "$IMG" "$M3D"

echo "==> generating board"
"$PY" "$GEN/build.py" --total 03 --out "$PCB" --info "$TMP/stats.json" >/dev/null
"$PY" "$GEN/stackup.py" "$PCB" >/dev/null

echo "==> renders"
R() { kicad-cli pcb render --use-board-stackup-colors --quality high "$@" "$PCB" > /dev/null; }
R --side top    -o "$TMP/front.png"    -w 3200 --height 1460 --zoom 1.15
R --side bottom -o "$TMP/back.png"     -w 3200 --height 1460 --zoom 1.15
R --side top    -o "$TMP/front_3d.png" -w 3200 --height 1500 --zoom 1.1 \
    --rotate '-30,0,-15' --perspective
R --side bottom -o "$TMP/back_3d.png"  -w 3200 --height 1500 --zoom 1.1 \
    --rotate '-30,0,15' --perspective

# Crop to the board, downscale (supersampled render -> sharp 1600 px JPEG).
"$PY" - "$TMP" "$IMG" <<'EOF'
import sys, cv2
src, dst = sys.argv[1], sys.argv[2]
for n in ("front", "back", "front_3d", "back_3d"):
    im = cv2.imread(f"{src}/{n}.png")
    x, y, w, h = cv2.boundingRect(cv2.findNonZero(
        (cv2.cvtColor(im, cv2.COLOR_BGR2GRAY) > 12).astype("uint8")))
    pad = round(0.04 * max(w, h))
    H, W = im.shape[:2]
    im = im[max(0, y - pad):min(H, y + h + pad), max(0, x - pad):min(W, x + w + pad)]
    h, w = im.shape[:2]
    im = cv2.resize(im, (1600, round(h * 1600 / w)), interpolation=cv2.INTER_AREA)
    cv2.imwrite(f"{dst}/{n}.jpg", im, [cv2.IMWRITE_JPEG_QUALITY, 88])
    print(f"   {dst}/{n}.jpg")
EOF

echo "==> 3D models"
# GLB: full colour (copper/ENIG, mask, silkscreen) for web viewers.
kicad-cli pcb export glb -f --include-tracks --include-pads --include-zones \
    --include-silkscreen --include-soldermask -o "$TMP/full.glb" "$PCB" > /dev/null
npx -y @gltf-transform/cli@4 optimize "$TMP/full.glb" "$M3D/ZETTEL3090.glb" \
    --compress draco --simplify false --texture-compress false > /dev/null
# STL: geometry only, for GitHub's built-in 3D viewer. Board, solder mask (its
# openings show the gold areas as relief) and silkscreen; full copper would be
# 139 MB. kicad-cli writes ASCII STL -> converted to binary (~5x smaller).
kicad-cli pcb export stl -f --include-soldermask --include-silkscreen \
    -o "$TMP/mask.stl" "$PCB" > /dev/null
"$PY" - "$TMP/mask.stl" "$M3D/ZETTEL3090.stl" <<'EOF'
import struct, sys
vals = [float(x) for line in open(sys.argv[1])
        if line.split()[:1] in (["facet"], ["vertex"])
        for x in line.split()[-3:]]
tris = [vals[i:i + 12] for i in range(0, len(vals), 12)]
with open(sys.argv[2], "wb") as f:
    f.write(b"ZETTEL3090 binary STL, exported by kicad-cli".ljust(80, b" "))
    f.write(struct.pack("<I", len(tris)))
    for t in tris:
        f.write(struct.pack("<12fH", *t, 0))
print(f"   {sys.argv[2]}: {len(tris)} triangles")
EOF
ls -la "$M3D"
echo "done"
