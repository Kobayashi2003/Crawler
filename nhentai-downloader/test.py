import unittest

from src.downloader import AsyncImageCrawler


class TestDownloader(unittest.TestCase):

    def test_get_image_url(self):
        crawler = AsyncImageCrawler(base_url="https://example.com/", file_ext="jpg")
        self.assertEqual(crawler.get_image_url(1), "https://example.com/1.jpg")
        self.assertEqual(crawler.get_image_url(42), "https://example.com/42.jpg")

    def test_download_dir_created(self):
        crawler = AsyncImageCrawler(download_dir="test_output_tmp")
        self.assertTrue(crawler.download_dir.exists())
        crawler.download_dir.rmdir()


if __name__ == '__main__':
    unittest.main()
