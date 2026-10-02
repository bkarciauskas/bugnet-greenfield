import importlib
import io
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROWS = [f"B{number}" for number in range(1, 17) if number != 7] + ["U1", "U2"]


def main():
    sys.path.insert(0, HERE)
    suite = unittest.TestSuite()
    loader = unittest.TestLoader()
    for row in ROWS:
        suite.addTests(loader.loadTestsFromModule(importlib.import_module(row)))
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    failed = set()
    for test, _trace in list(result.failures) + list(result.errors):
        failed.add(test.id().split(".")[-1].replace("test_", ""))
    for row in ROWS:
        print(f"{row} {'FAIL' if row in failed else 'PASS'}")
    print(f"{result.testsRun - len(failed)} passed, {len(failed)} failed, {result.testsRun} ran")
    print("---")
    print(stream.getvalue())
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
