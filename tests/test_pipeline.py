import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"scripts"))
from pipeline import valid_youtube, candidates, ass_timestamp, ass_escape

class PipelineTests(unittest.TestCase):
    def test_youtube_hosts(self):
        self.assertTrue(valid_youtube("https://youtu.be/169ZzvPxvvM"))
        self.assertTrue(valid_youtube("https://www.youtube.com/watch?v=abc"))
        self.assertFalse(valid_youtube("https://youtube.com.evil.tld/test"))
        self.assertFalse(valid_youtube("http://youtu.be/abc"))
    def test_candidates(self):
        words=[{"start":i,"end":i+.5,"text":"wow!" if i>40 else "normal"} for i in range(80)]
        result=candidates(words, 90, 25, 2)
        self.assertEqual(len(result), 2)
        self.assertGreater(result[-1]["end"], result[-1]["start"])
    def test_ass(self):
        self.assertEqual(ass_timestamp(61.23),"0:01:01.23")
        self.assertEqual(ass_escape("test{foo}"),"test(foo)")
if __name__ == '__main__': unittest.main()
