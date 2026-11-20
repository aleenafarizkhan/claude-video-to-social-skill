import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from shorts_cutter import crop_filter, hook_ass

class CutterTests(unittest.TestCase):
    def test_left_offset(self):
        f = crop_filter("character", 300)
        self.assertIn(r"min(300\,iw-1080)", f)
        self.assertIn("crop=1080:1920", f)
    def test_center_offset(self):
        self.assertIn("(iw-1080)/2", crop_filter("center", 300))
    def test_negative_offset(self):
        with self.assertRaises(ValueError): crop_filter("character", -1)
    def test_hook(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as d:
            p = Path(d) / "hook.ass"
            hook_ass(p, "WOW {this}", 3)
            s = p.read_text(encoding="utf-8")
            self.assertIn("WOW (this)", s)
            self.assertIn("0:00:03.00", s)

if __name__ == "__main__": unittest.main()
