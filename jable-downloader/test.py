import unittest

from src.downloader import isJableVideoUrl


class TestDownloader(unittest.TestCase):

    def test_valid_video_url(self):
        self.assertTrue(isJableVideoUrl('https://jable.tv/videos/mukc-032/'))

    def test_invalid_url(self):
        self.assertFalse(isJableVideoUrl('https://example.com/'))

    def test_model_url_is_not_video(self):
        self.assertFalse(isJableVideoUrl('https://jable.tv/models/hikaru-emo/'))


if __name__ == '__main__':
    unittest.main()
