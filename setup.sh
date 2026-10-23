#!/usr/bin/env bash
# One-time setup: a .venv that sees KiCad's pcbnew module plus the pip deps.
#
#   ./setup.sh                 uses the first python3 that can import pcbnew
#   KICAD_PYTHON=/path ./setup.sh
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

command -v kicad-cli >/dev/null || { echo "error: kicad-cli not found — install KiCad 9 first." >&2; exit 1; }
echo "KiCad: $(kicad-cli version)"

# pcbnew is installed for the Python KiCad was built against — find it.
CANDIDATES=("${KICAD_PYTHON:-}" /usr/bin/python3 python3 \
    /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3)
BASE=""
for p in "${CANDIDATES[@]}"; do
    [[ -n "$p" ]] || continue
    if "$p" -c 'import pcbnew' 2>/dev/null; then BASE="$p"; break; fi
done
[[ -n "$BASE" ]] || { echo "error: no python3 can import pcbnew. Set KICAD_PYTHON to KiCad's Python." >&2; exit 1; }
echo "pcbnew via: $BASE ($("$BASE" -c 'import pcbnew; print(pcbnew.Version())'))"

# --system-site-packages: the venv must still see pcbnew.
"$BASE" -m venv --system-site-packages .venv
.venv/bin/python -m pip install -q --upgrade pip
.venv/bin/python -m pip install -q -r requirements.txt
.venv/bin/python -c 'import pcbnew, segno, cv2, numpy, pygerber; print("ok: .venv ready")'
