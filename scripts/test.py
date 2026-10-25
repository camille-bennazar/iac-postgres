"""Afficher chaque scénario et un bilan sans dépendance de test supplémentaire."""

import sys
import unittest
from pathlib import Path


class ReadableResult(unittest.TextTestResult):
    def getDescription(self, test):
        return test.shortDescription() or test.id().split(".")[-1].removeprefix("test_").replace("_", " ")


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    suite = unittest.defaultTestLoader.discover(str(root / "tests"))
    result = unittest.TextTestRunner(verbosity=2, resultclass=ReadableResult).run(suite)
    failed = len(result.failures) + len(result.errors)
    print(
        f"\nBilan : {result.testsRun} scénarios ; "
        f"{result.testsRun - failed - len(result.skipped)} réussis ; "
        f"{failed} échecs ; {len(result.skipped)} ignorés.",
        flush=True,
    )
    sys.exit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
