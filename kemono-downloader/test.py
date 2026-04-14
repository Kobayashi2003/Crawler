import unittest


class TestImports(unittest.TestCase):

    def test_import_cli(self):
        from src import cli

    def test_import_config(self):
        from src import config

    def test_import_api(self):
        from src import api

    def test_import_filter(self):
        from src import filter


if __name__ == '__main__':
    unittest.main()
