#!/bin/bash
# Sets up a local development environment for PDF Redactor.
#
# Why not plain /usr/bin/python3? macOS's built-in system Python links
# against an old system Tcl/Tk (8.5). On current macOS that combination
# crashes as soon as a Tk window is opened — a version-check bug inside
# AquaTk, not something this app can work around. Homebrew's python-tk
# formula provides a Python built against a modern, working Tcl/Tk, so
# that's what this script uses instead.
#
# (Non-technical users who just want to run the app should grab the
# prebuilt PDF Redactor.app from the Releases page instead of running
# this script — it doesn't depend on any of this.)

set -e

cd "$(dirname "$0")"

PY_FORMULA="python-tk@3.11"
PY_VERSION="3.11"

if ! command -v brew >/dev/null 2>&1; then
    cat <<'EOF'
Homebrew is required to set up a working dev environment for this project.

Install it from https://brew.sh, then re-run this script.

(Alternatively, install Python from https://www.python.org/downloads/macos/
-- the official installer bundles a working Tk -- and create the venv
yourself with that interpreter: `/path/to/python3.11 -m venv venv`.)
EOF
    exit 1
fi

PY_PREFIX="$(brew --prefix "python@${PY_VERSION}" 2>/dev/null || true)"
PY_BIN="${PY_PREFIX}/bin/python${PY_VERSION}"

if [ ! -x "$PY_BIN" ]; then
    echo "Installing $PY_FORMULA via Homebrew (Python ${PY_VERSION} + a working Tk)..."
    brew install "$PY_FORMULA"
fi

if [ ! -x "$PY_BIN" ]; then
    echo "Error: expected a Python interpreter at $PY_BIN after installing"
    echo "$PY_FORMULA, but it isn't there. Run 'brew info $PY_FORMULA' to see"
    echo "where Homebrew actually put it and adjust PY_BIN in setup.sh."
    exit 1
fi

echo "Creating virtual environment with $PY_BIN..."
"$PY_BIN" -m venv venv

echo "Activating virtual environment..."
# shellcheck disable=SC1091
source venv/bin/activate

echo "Upgrading pip..."
pip install --upgrade pip -q

echo "Installing dependencies..."
pip install -r requirements.txt -q

echo "Verifying Tk actually works in this environment..."
TK_CHECK_LOG="$(mktemp)"
if ! python -c "import tkinter; r = tkinter.Tk(); r.destroy()" >"$TK_CHECK_LOG" 2>&1; then
    echo ""
    echo "Error: Tk failed to initialize in the new venv. Details:"
    cat "$TK_CHECK_LOG"
    rm -f "$TK_CHECK_LOG"
    exit 1
fi
rm -f "$TK_CHECK_LOG"

echo ""
echo "Setup complete!"
echo "To run the application:"
echo "  source venv/bin/activate && python redactor.py"
echo ""
echo "To run the test suite:"
echo "  source venv/bin/activate && pip install -r requirements-dev.txt && pytest"
