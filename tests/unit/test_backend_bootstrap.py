"""Smoke tests for the framework-free Backend Lambda package boundary."""

import importlib
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "apps" / "backend"
PROBE_MODULE = "apps.backend.handlers._bootstrap_probe"


class BackendBootstrapTest(unittest.TestCase):
    """Verify imports and invocation without selecting an API Gateway contract."""

    def test_private_probe_is_invocable(self) -> None:
        module = importlib.import_module(PROBE_MODULE)

        self.assertIsNone(module.invoke(object(), object()))

    def test_private_probe_is_invocable_from_staged_zip_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            stage_root = Path(temporary_directory)
            staged_backend = stage_root / "apps" / "backend"
            shutil.copytree(
                BACKEND_ROOT,
                staged_backend,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
            )

            environment = os.environ.copy()
            environment.pop("PYTHONPATH", None)
            result = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    (
                        f"from {PROBE_MODULE} import invoke; "
                        "assert invoke(object(), object()) is None"
                    ),
                ],
                cwd=stage_root,
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(0, result.returncode, result.stderr)


if __name__ == "__main__":
    unittest.main()
