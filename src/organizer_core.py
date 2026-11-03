"""Shared no-overwrite native operations for manual, drop and automatic modes."""
import ctypes
import sys
import threading
from pathlib import Path

CALLBACK = ctypes.CFUNCTYPE(None, ctypes.c_int)

class Organizer:
    def __init__(self, library=None):
        suffix = ".dylib" if sys.platform == "darwin" else ".so"
        base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
        library = Path(library) if library else base / "native" / ("libfileorg" + suffix)
        self.lib = ctypes.CDLL(str(library))
        self.lock = threading.RLock()
        self.lib.moveFile.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
        self.lib.moveFile.restype = ctypes.c_int
        self.lib.organizeFolder.argtypes = [ctypes.c_char_p, CALLBACK]
        self.lib.organizeFolder.restype = ctypes.c_int
        self.lib.undoLastMove.argtypes = []
        self.lib.undoLastMove.restype = ctypes.c_int

    def move(self, source, category):
        source = Path(source).absolute()
        if Path(category).name != category or category in (".", ".."):
            raise ValueError("Invalid category")
        with self.lock:
            return self.lib.moveFile(bytes(source), bytes(source.parent / category))

    def scan(self, folder, progress=lambda value: None):
        with self.lock:
            return self.lib.organizeFolder(bytes(Path(folder).absolute()), CALLBACK(progress))

    def undo(self):
        with self.lock:
            return self.lib.undoLastMove()
