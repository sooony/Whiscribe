"""
run_all_qa_tests.py - Zbiorczy runner testów QA dla wtyczki dyktowania.
Uruchamia:
1. test_deadlock_and_concurrency.py
2. test_injection_and_typing.py
"""

import sys
import unittest

import test_deadlock_and_concurrency
import test_injection_and_typing

def main():
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromModule(test_deadlock_and_concurrency))
    suite.addTests(loader.loadTestsFromModule(test_injection_and_typing))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "="*60)
    print(" PODSUMOWANIE TESTÓW QA & INTEGRACYJNYCH")
    print("="*60)
    print(f"Liczba wykonanych testów: {result.testsRun}")
    print(f"Sukcesy:                 {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Niepowodzenia (Failures): {len(result.failures)}")
    print(f"Błędy krytyczne (Errors): {len(result.errors)}")
    print("="*60)

    if not result.wasSuccessful():
        sys.exit(1)

if __name__ == "__main__":
    main()
