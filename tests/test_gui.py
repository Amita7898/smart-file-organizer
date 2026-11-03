"""Actual Tk workflow checks. Run with GUI_TESTS=1 on a graphical desktop."""
import os
from pathlib import Path
import runpy
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

@unittest.skipUnless(os.environ.get('GUI_TESTS') == '1', 'Set GUI_TESTS=1 with a graphical desktop')
class GuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import tkinter
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
        with patch.object(tkinter.Misc, 'mainloop', return_value=None):
            cls.app = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'src/fileorganiser.py'))
        cls.app['root'].update()
    @classmethod
    def tearDownClass(cls): cls.app['close_app']()
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.messages = []
        for method in ('showinfo', 'showerror'):
            patcher = patch.object(self.app['messagebox'], method, side_effect=lambda *args: self.messages.append(args))
            patcher.start(); self.addCleanup(patcher.stop)
    def test_manual_move_and_undo(self):
        source = self.folder / 'sample.txt'; source.write_text('synthetic')
        with patch.object(self.app['filedialog'], 'askopenfilename', return_value=str(source)):
            self.app['manual_mode']()
        self.assertTrue((self.folder / 'Documents/sample.txt').exists())
        self.app['undo_move']()
        self.assertTrue(source.exists())
        self.assertIn('restored', self.messages[-1][1])
    def test_manual_collision_reports_skipped(self):
        source = self.folder / 'sample.txt'; source.write_text('incoming')
        dest = self.folder / 'Documents/sample.txt'; dest.parent.mkdir(); dest.write_text('existing')
        with patch.object(self.app['filedialog'], 'askopenfilename', return_value=str(source)):
            self.app['manual_mode']()
        self.assertEqual('existing', dest.read_text()); self.assertEqual('incoming', source.read_text())
        self.assertEqual('Skipped', self.messages[-1][0])
    def test_automatic_start_stop_and_move(self):
        source = self.folder / 'sample.pdf'; source.write_text('synthetic')
        with patch.object(self.app['filedialog'], 'askdirectory', return_value=str(self.folder)):
            self.app['auto_mode']()
        deadline = time.monotonic() + 5
        while source.exists() and time.monotonic() < deadline:
            self.app['root'].update(); time.sleep(.05)
        self.app['stop_auto_mode']()
        self.app['root'].update()
        self.assertTrue((self.folder / 'Documents/sample.pdf').exists())
        self.assertFalse(self.app['watching_folders'])
    def test_drag_drop_collision_preserves_both(self):
        if not self.app['dnd_available']: self.skipTest('Optional tkinterdnd2 is unavailable')
        from types import SimpleNamespace
        source = self.folder / 'sample.txt'; source.write_text('incoming')
        dest = self.folder / 'Documents/sample.txt'; dest.parent.mkdir(); dest.write_text('existing')
        self.app['drop'](SimpleNamespace(data=self.app['root'].tk.call('list', str(source))))
        self.assertEqual('existing', dest.read_text()); self.assertEqual('incoming', source.read_text())
    def test_manual_keyword_categories_preserved(self):
        self.assertEqual('Work', self.app['categorize_file']('report.pdf'))
        self.assertEqual('Personal', self.app['categorize_file']('selfie.jpg'))
    def test_log_stays_in_memory(self):
        self.app['log_action']('Synthetic demo move')
        self.assertIn('Synthetic demo move', self.app['session_log'])
