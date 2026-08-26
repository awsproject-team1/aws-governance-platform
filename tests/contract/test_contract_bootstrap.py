"""Guard the repository state before executable contracts are introduced."""

import unittest
from pathlib import Path


class ContractBootstrapTest(unittest.TestCase):
    def test_contract_package_contains_only_the_placeholder(self) -> None:
        repository_root = Path(__file__).resolve().parents[2]
        contract_entries = {
            path.name
            for path in (repository_root / "packages" / "contracts").iterdir()
            if path.name not in {".gitkeep", "__pycache__"}
        }

        self.assertEqual(
            contract_entries,
            set(),
            "replace the bootstrap guard with executable contract tests",
        )


if __name__ == "__main__":
    unittest.main()
