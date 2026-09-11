#!/bin/bash
# Builds PDF Redactor.app and a distributable PDF Redactor.dmg.
#
# Requires the same Homebrew Python that setup.sh uses (python-tk@3.11),
# plus its tcl-tk@8 dependency — setup_app.py bundles that Tcl/Tk's script
# library into the app so the built .app works on Macs that don't have
# Homebrew installed at all. See setup_app.py's module docstring for why
# that's necessary.

set -e

cd "$(dirname "$0")/.."  # project root

APP_NAME="PDF Redactor"
BUILD_VENV=".build-venv"

PY_PREFIX="$(brew --prefix python@3.11 2>/dev/null || true)"
PY_BIN="${PY_PREFIX}/bin/python3.11"
if [ ! -x "$PY_BIN" ]; then
    echo "Error: Homebrew's python-tk@3.11 wasn't found."
    echo "Run ./setup.sh first (or: brew install python-tk@3.11)."
    exit 1
fi

echo "Setting up an isolated build environment ($BUILD_VENV)..."
"$PY_BIN" -m venv "$BUILD_VENV"
"$BUILD_VENV/bin/pip" install --upgrade pip -q
"$BUILD_VENV/bin/pip" install -q -r requirements.txt py2app

echo "Building $APP_NAME.app..."
cd packaging
rm -rf build dist
"../$BUILD_VENV/bin/python3" setup_app.py py2app

echo "Packaging into a DMG..."
DMG_STAGING="$(mktemp -d)"
trap 'rm -rf "$DMG_STAGING"' EXIT
cp -R "dist/$APP_NAME.app" "$DMG_STAGING/"
ln -s /Applications "$DMG_STAGING/Applications"

rm -f "$APP_NAME.dmg"
hdiutil create -volname "$APP_NAME" -srcfolder "$DMG_STAGING" -ov -format UDZO "$APP_NAME.dmg"

echo ""
echo "Built: packaging/$APP_NAME.dmg"
echo ""
echo "Before publishing, actually test it:"
echo "  open \"packaging/$APP_NAME.dmg\""
echo "then drag the app to Applications and right-click -> Open it (it's"
echo "unsigned, so a plain double-click will be refused the first time)."
