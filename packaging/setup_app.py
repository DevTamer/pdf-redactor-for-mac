"""py2app build script for PDF Redactor.

Run via build_app.sh, or manually from this directory:

    python setup_app.py py2app

Produces dist/PDF Redactor.app.

Bundling note: py2app correctly relocates the Tcl/Tk *dylibs* themselves
(libtcl8.6.dylib / libtk8.6.dylib land in Contents/Frameworks, linked via
@executable_path so they work from any install location). What it does
*not* do is bundle Tcl/Tk's script library (init.tcl, tk.tcl, and friends)
that those dylibs need at startup — Homebrew's tcl-tk isn't a macOS
.framework, so py2app has no recipe for it, and Tcl instead falls back to
a hardcoded build-machine path (the Homebrew Cellar) baked into the dylib.
That works on the machine that built it and nowhere else. So this script
also copies Tcl/Tk's `lib/tcl8.6` and `lib/tk8.6` directories into the app
bundle, and redactor.py points TCL_LIBRARY/TK_LIBRARY at them when frozen.
"""

import os
import subprocess
import sys

from setuptools import setup

APP = ["../redactor.py"]


def brew_prefix(formula: str) -> str:
    try:
        return subprocess.check_output(
            ["brew", "--prefix", formula], text=True
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        sys.exit(
            f"Could not resolve Homebrew prefix for '{formula}' ({exc}).\n"
            f"Install it with: brew install {formula}"
        )


def bundle_dir_as_data_files(src_root: str, dest_root: str):
    """Build py2app data_files entries that recreate src_root's directory
    tree under dest_root (relative to Contents/Resources) in the bundle."""
    if not os.path.isdir(src_root):
        sys.exit(f"Expected Tcl/Tk library directory not found: {src_root}")
    entries = []
    for dirpath, _dirnames, filenames in os.walk(src_root):
        if not filenames:
            continue
        rel = os.path.relpath(dirpath, src_root)
        dest = dest_root if rel == "." else os.path.join(dest_root, rel)
        files = [os.path.join(dirpath, f) for f in filenames]
        entries.append((dest, files))
    return entries


TCL_TK_PREFIX = brew_prefix("tcl-tk@8")

DATA_FILES = []
DATA_FILES += bundle_dir_as_data_files(
    os.path.join(TCL_TK_PREFIX, "lib", "tcl8.6"), "tcl/tcl8.6")
DATA_FILES += bundle_dir_as_data_files(
    os.path.join(TCL_TK_PREFIX, "lib", "tk8.6"), "tcl/tk8.6")

OPTIONS = {
    "argv_emulation": False,
    "iconfile": "icon.icns",
    "packages": ["fitz", "PIL"],
    "plist": {
        "CFBundleName": "PDF Redactor",
        "CFBundleDisplayName": "PDF Redactor",
        "CFBundleIdentifier": "com.devtamer.pdfredactor",
        "CFBundleVersion": "0.1.0",
        "CFBundleShortVersionString": "0.1.0",
        "NSHumanReadableCopyright": "PDF Redactor",
        "LSMinimumSystemVersion": "11.0",
        "NSHighResolutionCapable": True,
        "CFBundleDocumentTypes": [
            {
                "CFBundleTypeName": "PDF Document",
                "CFBundleTypeRole": "Editor",
                "LSItemContentTypes": ["com.adobe.pdf"],
                "LSHandlerRank": "Alternate",
            }
        ],
    },
}

setup(
    app=APP,
    name="PDF Redactor",
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
