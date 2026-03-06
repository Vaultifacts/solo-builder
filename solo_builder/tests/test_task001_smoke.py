import pathlib
import unittest


class Task001SmokeTest(unittest.TestCase):
    def test_required_project_files_exist(self):
        root = pathlib.Path(__file__).resolve().parents[2]
        required = [
            root / "solo_builder" / "__init__.py",
            root / "solo_builder" / "solo_builder_cli.py",
            root / "solo_builder" / "README.md",
        ]
        for path in required:
            self.assertTrue(path.exists(), "Missing required file: {0}".format(path))
            self.assertTrue(path.is_file(), "Expected file path: {0}".format(path))


if __name__ == "__main__":
    unittest.main()
