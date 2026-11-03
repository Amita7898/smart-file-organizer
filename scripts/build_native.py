"""Build the original native organizer with platform no-overwrite protection."""
import os
import subprocess
import sys
from pathlib import Path
root = Path(__file__).resolve().parents[1]
if sys.platform not in ("darwin", "linux"):
    raise SystemExit("Native builds currently support macOS and Linux only.")
name = "libfileorg.dylib" if sys.platform == "darwin" else "libfileorg.so"
flags = ["-dynamiclib"] if sys.platform == "darwin" else ["-shared", "-fPIC"]
subprocess.run([os.environ.get("CC", "cc"), "-std=c11", "-Wall", "-Wextra", "-Werror", "-O2", *flags,
                str(root / "native/fileorg2.c"), "-o", str(root / "native" / name)], check=True)
print("Built", name)
