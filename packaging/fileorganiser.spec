# Build from repository root: python -m PyInstaller packaging/fileorganiser.spec
from pathlib import Path
import sys
from PyInstaller.utils.hooks import collect_all
root = Path(SPECPATH).parent
library = root / "native" / ("libfileorg.dylib" if sys.platform == "darwin" else "libfileorg.so")
datas, binaries, hidden = collect_all("tkinterdnd2")
a = Analysis([str(root / "src/fileorganiser.py")], pathex=[str(root / "src")],
             binaries=[(str(library), "native")] + binaries, datas=datas, hiddenimports=hidden)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="Smart File Organizer", console=False)
coll = COLLECT(exe, a.binaries, a.datas, name="Smart File Organizer")
if sys.platform == "darwin":
    app = BUNDLE(coll, name="Smart File Organizer.app", bundle_identifier="io.github.amita7898.smart-file-organizer")
