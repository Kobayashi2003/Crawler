import unittest

from src.utils.helpers import is_video_url, is_artist_url


class TestHelpers(unittest.TestCase):

    def test_valid_video_url(self):
        self.assertTrue(is_video_url('https://jable.tv/videos/mukc-032/'))

    def test_invalid_url(self):
        self.assertFalse(is_video_url('https://example.com/'))

    def test_model_url_is_not_video(self):
        self.assertFalse(is_video_url('https://jable.tv/models/hikaru-emo/'))

    def test_valid_artist_url(self):
        self.assertTrue(is_artist_url('https://jable.tv/models/hikaru-emo/'))

    def test_video_url_is_not_artist(self):
        self.assertFalse(is_artist_url('https://jable.tv/videos/mukc-032/'))


if __name__ == '__main__':
    unittest.main()
