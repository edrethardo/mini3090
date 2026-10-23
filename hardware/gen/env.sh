# Sourced by the build scripts: repo root, Python interpreter, tool checks.
# Works from any checkout location — nothing here is machine-specific.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
GEN="$ROOT/hardware/gen"

# Python: $PYTHON if set, else the repo venv (see setup.sh), else python3.
if [[ -n "${PYTHON:-}" ]]; then PY="$PYTHON"
elif [[ -x "$ROOT/.venv/bin/python" ]]; then PY="$ROOT/.venv/bin/python"
else PY="$(command -v python3)"; fi

need() { command -v "$1" >/dev/null 2>&1 || { echo "error: '$1' not found. $2" >&2; exit 1; }; }
need kicad-cli "Install KiCad 9 (https://www.kicad.org/download/)."
need zip "Install zip (e.g. 'sudo apt install zip')."

if ! "$PY" -c 'import pcbnew, segno, cv2, numpy, pygerber' 2>/dev/null; then
    echo "error: $PY lacks pcbnew or the Python deps. Run ./setup.sh first." >&2
    exit 1
fi
