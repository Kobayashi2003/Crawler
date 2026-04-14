import unittest

from src.downloader import PjsekaiDownloader


class TestDownloader(unittest.TestCase):

    def test_sanitize_filename(self):
        d = PjsekaiDownloader()
        self.assertEqual(d.sanitize_filename('test:file'), 'test_file')
        self.assertEqual(d.sanitize_filename('a<b>c'), 'a_b_c')

    def test_output_dir_default(self):
        d = PjsekaiDownloader()
        self.assertEqual(str(d.output_dir), 'downloads')


if __name__ == '__main__':
    unittest.main()
