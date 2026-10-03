import importlib
import io
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROWS = [f"B{number}" for number in range(1, 17) if number != 7] + ["U1"]


def main():
    base = os.environ.get("BUGNET_BASE_URL", "http://15.135.1.105").rstrip("/")
    prefix = os.environ.get("BUGNET_MAIL_PREFIX", "mail/")
    print(f"target {base} mail {prefix}")
    sys.path.insert(0, HERE)
    suite = unittest.TestSuite()
    loader = unittest.TestLoader()
    for row in ROWS:
        suite.addTests(loader.loadTestsFromModule(importlib.import_module(row)))
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    failed = {}
    for test, trace in list(result.failures) + list(result.errors):
        failed[test.id().split(".")[-1].replace("test_", "")] = trace
    skipped = {}
    for test, reason in result.skipped:
        skipped[test.id().split(".")[-1].replace("test_", "")] = reason
    for row in ROWS:
        if row in failed:
            print(f"{row} FAIL")
        elif row in skipped:
            print(f"{row} UNTESTABLE {skipped[row]}")
        else:
            print(f"{row} PASS")
    passed = len(ROWS) - len(failed) - len(skipped)
    print(
        f"{passed} passed, {len(failed)} failed, {len(skipped)} untestable, {result.testsRun} ran"
    )
    print("---")
    print(stream.getvalue())
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
