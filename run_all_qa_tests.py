"""
run_all_qa_tests.py - Zbiorczy runner testów QA dla wtyczki dyktowania.
Uruchamia w izolowanych procesach:
1. test_deadlock_and_concurrency.py
2. test_injection_and_typing.py
3. test_overlay_new_design.py
4. test_v2_features.py
"""

import sys
import subprocess
import os

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    scripts = [
        "test_deadlock_and_concurrency.py",
        "test_injection_and_typing.py",
        "test_overlay_new_design.py",
        "test_v2_features.py"
    ]

    total_runs = 0
    failures = 0
    print("=" * 60)
    print(" ROZPOCZĘCIE PEŁNEGO PAKIETU TESTÓW QA & INTEGRACYJNYCH")
    print("=" * 60)

    for script in scripts:
        script_path = os.path.join(base_dir, script)
        print(f"\n--- URUCHAMIANIE: {script} ---")
        res = subprocess.run([sys.executable, script_path], cwd=base_dir)
        total_runs += 1
        if res.returncode != 0:
            print(f"[BŁĄD] Moduł {script} zakończony kodem błędu {res.returncode}")
            failures += 1
        else:
            print(f"[SUKCES] Moduł {script} zakończony sukcesem (kod 0).")

    print("\n" + "=" * 60)
    print(" PODSUMOWANIE PAKIETU TESTÓW QA")
    print("=" * 60)
    print(f"Liczba uruchomionych pakietów: {total_runs}")
    print(f"Pakiety zakończone sukcesem:    {total_runs - failures}")
    print(f"Pakiety z błędami:             {failures}")
    print("=" * 60)

    if failures > 0:
        sys.exit(1)
    print("Wszystkie testy QA i weryfikacje zaliczone w 100%!")

if __name__ == "__main__":
    main()
