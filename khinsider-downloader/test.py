import unittest

from src.config import Config


class TestConfig(unittest.TestCase):

    def test_default_output_dir(self):
        config = Config()
        self.assertEqual(config.output_dir, 'downloads')

    def test_default_format(self):
        config = Config()
        self.assertEqual(config.audio_format, 'both')

    def test_custom_config(self):
        config = Config(output_dir='my_dir', audio_format='flac')
        self.assertEqual(config.output_dir, 'my_dir')
        self.assertEqual(config.audio_format, 'flac')


if __name__ == '__main__':
    unittest.main()
