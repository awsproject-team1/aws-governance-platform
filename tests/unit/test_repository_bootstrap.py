"""Smoke tests for the repository's Python bootstrap."""

import importlib
import unittest


class RepositoryBootstrapTest(unittest.TestCase):
    """Verify that the shared Python package is importable."""

    def test_common_package_is_importable(self) -> None:
        module = importlib.import_module("packages.common")

        self.assertEqual(module.__name__, "packages.common")


if __name__ == "__main__":
    unittest.main()
