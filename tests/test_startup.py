"""Startup ordering: the py2app Tcl/Tk fix-up must run before tkinter is
first imported, or a bundled app looks for Tcl's script library at the
build machine's Homebrew path and fails to start on anyone else's Mac.

Runs `import redactor` in a fresh interpreter (so sys.modules starts clean)
with configure_bundled_tcl_tk wrapped to record whether tkinter had already
been imported when it was called.
"""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

PROBE = """
import sys
import pdfcore.frozen as frozen

calls = []
real = frozen.configure_bundled_tcl_tk

def spy(*args, **kwargs):
    calls.append("tkinter" in sys.modules or "_tkinter" in sys.modules)
    return real(*args, **kwargs)

frozen.configure_bundled_tcl_tk = spy
import redactor  # noqa: E402
print(calls)
"""


def test_tcl_tk_fixup_runs_before_tkinter_is_imported():
    result = subprocess.run(
        [sys.executable, "-c", PROBE],
        cwd=str(REPO_ROOT), capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    # Called exactly once, and tkinter wasn't loaded yet at that point.
    assert result.stdout.strip() == "[False]"
