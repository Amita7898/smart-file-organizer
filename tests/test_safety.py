import concurrent.futures
import os
import shutil
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from organizer_core import Organizer

class SafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "fixtures"
        self.root.mkdir()
        suffix = ".dylib" if sys.platform == "darwin" else ".so"
        library = Path(__file__).resolve().parents[1] / "native" / ("libfileorg" + suffix)
        isolated_library = Path(self.tmp.name) / ("test-native" + suffix)
        shutil.copy2(library, isolated_library)
        self.app = Organizer(isolated_library)
    def file(self, name, content="synthetic"):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return path
    def test_empty_undo_reports_no_action(self):
        self.assertEqual(0, self.app.undo())
    def test_manual_move_and_undo(self):
        source = self.file("note.txt")
        self.assertEqual(1, self.app.move(source, "Documents"))
        self.assertEqual(1, self.app.undo())
        self.assertEqual("synthetic", source.read_text())
    def test_collision_preserves_both_contents(self):
        source = self.file("note.txt", "incoming")
        dest = self.file("Documents/note.txt", "existing")
        self.assertEqual(0, self.app.move(source, "Documents"))
        self.assertEqual("incoming", source.read_text())
        self.assertEqual("existing", dest.read_text())
    def test_automatic_collision_preserves_both(self):
        source = self.file("note.pdf", "incoming")
        dest = self.file("Documents/note.pdf", "existing")
        self.assertEqual(0, self.app.scan(self.root))
        self.assertEqual("incoming", source.read_text())
        self.assertEqual("existing", dest.read_text())
    def test_auto_moves_and_progress(self):
        self.file("note.PDF"); self.file("picture.jpg")
        progress = []
        self.assertEqual(2, self.app.scan(self.root, progress.append))
        self.assertEqual([100], progress)
        self.assertTrue((self.root / "Documents/note.PDF").exists())
        self.assertTrue((self.root / "Images/picture.jpg").exists())
    def test_auto_ignores_directories_and_symlinks(self):
        (self.root / "folder").mkdir()
        target = self.file("folder/target.txt")
        (self.root / "link.txt").symlink_to(target)
        self.assertEqual(0, self.app.scan(self.root))
        self.assertTrue(target.exists())
        self.assertTrue((self.root / "link.txt").is_symlink())
    def test_refuses_symlink_category(self):
        source = self.file("note.txt")
        (self.root / "elsewhere").mkdir()
        (self.root / "Documents").symlink_to(self.root / "elsewhere")
        self.assertEqual(-1, self.app.move(source, "Documents"))
        self.assertTrue(source.exists())
    def test_refuses_symlink_input(self):
        target = self.file("target.txt")
        source = self.root / "link.txt"; source.symlink_to(target)
        self.assertEqual(-1, self.app.move(source, "Documents"))
        self.assertTrue(target.exists())
    def test_undo_original_path_occupied_and_retry(self):
        source = self.file("note.txt", "original")
        self.assertEqual(1, self.app.move(source, "Documents"))
        source.write_text("new file")
        self.assertEqual(0, self.app.undo())
        self.assertEqual("new file", source.read_text())
        source.unlink()  # disposable fixture only
        self.assertEqual(1, self.app.undo())
        self.assertEqual("original", source.read_text())
    def test_undo_refuses_replaced_destination(self):
        source = self.file("note.txt")
        self.app.move(source, "Documents")
        dest = self.root / "Documents/note.txt"
        dest.rename(self.root / "saved")
        dest.write_text("replacement")
        self.assertEqual(-1, self.app.undo())
        self.assertEqual("replacement", dest.read_text())
    def test_missing_source_reports_failure(self):
        self.assertEqual(-1, self.app.move(self.root / "missing", "Others"))
    def test_missing_folder_reports_failure(self):
        self.assertEqual(-1, self.app.scan(self.root / "missing"))
    def test_undo_stack_keeps_latest_hundred_moves(self):
        for i in range(101):
            self.assertEqual(1, self.app.move(self.file(f"item-{i}.txt"), "Documents"))
        for _ in range(100): self.assertEqual(1, self.app.undo())
        self.assertEqual(0, self.app.undo())
        self.assertTrue((self.root / "Documents/item-0.txt").exists())
        self.assertTrue((self.root / "item-100.txt").exists())
    def test_unicode_and_spaces(self):
        source = self.file("sample café.txt")
        self.assertEqual(1, self.app.move(source, "Documents"))
        self.assertEqual(1, self.app.undo())
        self.assertTrue(source.exists())
    def test_invalid_category_rejected(self):
        with self.assertRaises(ValueError): self.app.move(self.file("a"), "../escape")
    def test_existing_directory_not_overwritten(self):
        source = self.file("note.txt")
        (self.root / "Documents/note.txt").mkdir(parents=True)
        self.assertEqual(0, self.app.move(source, "Documents"))
        self.assertTrue(source.exists())
    def test_long_path_fails_safely(self):
        self.assertEqual(-1, self.app.move(self.root / ("x" * 5000), "Documents"))
    def test_atomic_competing_moves(self):
        source = self.file("note.txt")
        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            results = list(pool.map(lambda _: self.app.move(source, "Documents"), range(2)))
        self.assertEqual(1, results.count(1))
        self.assertEqual("synthetic", (self.root / "Documents/note.txt").read_text())
    def test_auto_repeat_leaves_collision_untouched(self):
        source = self.file("note.txt", "first")
        self.app.scan(self.root)
        source.write_text("second")
        self.assertEqual(0, self.app.scan(self.root))
        self.assertEqual("first", (self.root / "Documents/note.txt").read_text())
        self.assertEqual("second", source.read_text())

if __name__ == "__main__": unittest.main()
