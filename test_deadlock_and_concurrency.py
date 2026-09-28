"""
test_deadlock_and_concurrency.py - Testy weryfikujące blokady i współbieżność (QA & Concurrency Audit)

Cel:
1. Weryfikacja samouśmiercenia wątku (self-deadlock) w app.py przy użyciu threading.Lock():
   - self.committer.commit_segment(...) wewnątrz 'with self._type_lock:'
   - self.committer.process_hypothesis(...) wewnątrz 'with self._type_lock:'
   - self.committer.finalize(...) wewnątrz 'with self._type_lock:'
2. Inspekcja stosu wywołań (call stack) zablokowanego wątku potwierdzająca reentrancy lock contention.
3. Weryfikacja działania z threading.RLock() (Reentrant Lock) oraz weryfikacja poprawności przepływu danych.
4. Test współbieżności wielowątkowej (streaming worker vs focus monitor).
"""

import sys
import time
import threading
import traceback
import unittest

from injector import ForwardStreamCommitter


class MockDictationApp:
    """Minimalna makieta DictationApp odwzorowująca mechanizm blokad z app.py."""
    def __init__(self, lock_factory=threading.Lock):
        self._type_lock = lock_factory()
        self.state = "recording"
        self.target_hwnd = 0x12345
        self.buffered_untyped_text = ""
        self.typed_chunks = []
        self.committer = ForwardStreamCommitter(type_callback=self._type_stream_chunk)

    def _type_stream_chunk(self, chunk: str):
        """Metoda odpowiadająca dokładnie implementacji z app.py:224-248."""
        if not chunk:
            return

        with self._type_lock:
            # W testach symulujemy, że jesteśmy w oknie docelowym lub w procesie przetwarzania
            if self.buffered_untyped_text:
                full_chunk = self.buffered_untyped_text + chunk
                self.buffered_untyped_text = ""
            else:
                full_chunk = chunk
            self.typed_chunks.append(full_chunk)


class TestLockDeadlock(unittest.TestCase):
    """Testy weryfikujące problem deadlocka na threading.Lock() vs threading.RLock()."""

    def _run_with_timeout(self, target, timeout=1.0):
        """Uruchamia target w osobnym wątku i czeka maksymalnie timeout sekund."""
        worker = threading.Thread(target=target)
        worker.daemon = True
        worker.start()
        worker.join(timeout=timeout)
        is_deadlocked = worker.is_alive()
        call_stack = ""
        if is_deadlocked:
            # Pobierz zrzut stosu zablokowanego wątku
            frames = sys._current_frames()
            if worker.ident in frames:
                frame = frames[worker.ident]
                call_stack = "".join(traceback.format_stack(frame))
        return is_deadlocked, call_stack, worker

    def test_01_commit_segment_self_deadlock_with_standard_lock(self):
        """
        WERYFIKACJA DEADLOCKA 1: commit_segment() wewnątrz 'with self._type_lock:'
        Oczekiwany rezultat przy threading.Lock(): natychmiastowy self-deadlock wątku.
        """
        app = MockDictationApp(lock_factory=threading.Lock)

        def worker_task():
            # Dokładna replika kodu z app.py:387-390
            with app._type_lock:
                app.committer.commit_segment("Pierwsze zdanie zatwierdzone.")

        is_deadlocked, call_stack, _ = self._run_with_timeout(worker_task, timeout=0.8)

        print("\n--- TEST 1: commit_segment z threading.Lock() ---")
        if is_deadlocked:
            print("[POTWIERDZONO BŁĄD] Wątek uległ samobójczemu zawieszeniu (Self-Deadlock)!")
            print("Stos zablokowanego wątku:")
            print(call_stack)
        else:
            print("[NIEOCZEKIWANE] Wątek zakończył się bez blokady.")

        self.assertTrue(is_deadlocked, "Wątek powienien ulec natychmiastowemu self-deadlockowi przy threading.Lock()")
        self.assertIn("_type_stream_chunk", call_stack)
        self.assertIn("with self._type_lock:", call_stack)

    def test_02_process_hypothesis_self_deadlock_with_standard_lock(self):
        """
        WERYFIKACJA DEADLOCKA 2: process_hypothesis() wewnątrz 'with self._type_lock:'
        Gdy hipoteza generuje ustabilizowane słowa, wywołuje type_callback.
        Oczekiwany rezultat przy threading.Lock(): natychmiastowy self-deadlock.
        """
        app = MockDictationApp(lock_factory=threading.Lock)

        def worker_task():
            # Najpierw ustawiamy poprzednie słowa, żeby pojawiły się słowa stabilne
            app.committer.last_hypothesis_words = ["To", "jest", "bardzo", "ważny"]
            # Dokładna replika kodu z app.py:394-395
            with app._type_lock:
                # Dłuższa fraza: słowa przed safe_tail_margin (2) staną się stabilne i wywołają type_callback
                app.committer.process_hypothesis("To jest bardzo ważny test weryfikacyjny systemowy")

        is_deadlocked, call_stack, _ = self._run_with_timeout(worker_task, timeout=0.8)

        print("\n--- TEST 2: process_hypothesis z threading.Lock() ---")
        if is_deadlocked:
            print("[POTWIERDZONO BŁĄD] Wątek uległ samobójczemu zawieszeniu (Self-Deadlock)!")
            print("Stos zablokowanego wątku:")
            print(call_stack)
        else:
            print("[NIEOCZEKIWANE] Wątek zakończył się bez blokady.")

        self.assertTrue(is_deadlocked, "Wątek streamingowy powienien ulec deadlockowi przy process_hypothesis")
        self.assertIn("_type_stream_chunk", call_stack)
        self.assertIn("with self._type_lock:", call_stack)

    def test_03_finalize_self_deadlock_with_standard_lock(self):
        """
        WERYFIKACJA DEADLOCKA 3: finalize() wewnątrz 'with self._type_lock:'
        Dokładna replika kodu z app.py:461-468 (_process_audio_worker).
        Oczekiwany rezultat przy threading.Lock(): natychmiastowy self-deadlock wątku finalizacji.
        """
        app = MockDictationApp(lock_factory=threading.Lock)

        def worker_task():
            app.state = "processing"
            # Dokładna replika kodu z app.py:461-463
            with app._type_lock:
                app.committer.finalize("To jest finalny ogon zdania.")

        is_deadlocked, call_stack, _ = self._run_with_timeout(worker_task, timeout=0.8)

        print("\n--- TEST 3: finalize z threading.Lock() ---")
        if is_deadlocked:
            print("[POTWIERDZONO BŁĄD] Wątek uległ samobójczemu zawieszeniu (Self-Deadlock)!")
            print("Stos zablokowanego wątku:")
            print(call_stack)
        else:
            print("[NIEOCZEKIWANE] Wątek zakończył się bez blokady.")

        self.assertTrue(is_deadlocked, "Wątek finalizujący powienien ulec deadlockowi przy finalize")
        self.assertIn("_type_stream_chunk", call_stack)
        self.assertIn("with self._type_lock:", call_stack)

    def test_04_rlock_solution_commit_segment(self):
        """
        WERYFIKACJA ROZWIĄZANIA: Zastosowanie threading.RLock() dla commit_segment.
        Oczekiwany rezultat: Płynne wykonanie bez deadlocka, poprawnie wpisany tekst.
        """
        app = MockDictationApp(lock_factory=threading.RLock)

        def worker_task():
            with app._type_lock:
                app.committer.commit_segment("Pierwsze zdanie zatwierdzone.")

        is_deadlocked, _, _ = self._run_with_timeout(worker_task, timeout=0.8)

        print("\n--- TEST 4: commit_segment z threading.RLock() ---")
        print(f"Deadlock wystąpił: {is_deadlocked} | Wpisany tekst: {app.typed_chunks}")
        self.assertFalse(is_deadlocked, "RLock nie powinien dopuścić do self-deadlocka!")
        self.assertEqual(len(app.typed_chunks), 1)
        self.assertIn("Pierwsze zdanie zatwierdzone.", app.typed_chunks[0])

    def test_05_rlock_solution_process_hypothesis(self):
        """
        WERYFIKACJA ROZWIĄZANIA: Zastosowanie threading.RLock() dla process_hypothesis.
        """
        app = MockDictationApp(lock_factory=threading.RLock)

        def worker_task():
            app.committer.last_hypothesis_words = ["To", "jest", "bardzo", "ważny"]
            with app._type_lock:
                app.committer.process_hypothesis("To jest bardzo ważny test weryfikacyjny systemowy")

        is_deadlocked, _, _ = self._run_with_timeout(worker_task, timeout=0.8)

        print("\n--- TEST 5: process_hypothesis z threading.RLock() ---")
        print(f"Deadlock wystąpił: {is_deadlocked} | Wpisany tekst: {app.typed_chunks}")
        self.assertFalse(is_deadlocked, "RLock nie powinien dopuścić do self-deadlocka!")
        self.assertGreater(len(app.typed_chunks), 0)

    def test_06_rlock_solution_finalize(self):
        """
        WERYFIKACJA ROZWIĄZANIA: Zastosowanie threading.RLock() dla finalize.
        """
        app = MockDictationApp(lock_factory=threading.RLock)

        def worker_task():
            app.state = "processing"
            with app._type_lock:
                app.committer.finalize("To jest finalny ogon zdania.")

        is_deadlocked, _, _ = self._run_with_timeout(worker_task, timeout=0.8)

        print("\n--- TEST 6: finalize z threading.RLock() ---")
        print(f"Deadlock wystąpił: {is_deadlocked} | Wpisany tekst: {app.typed_chunks}")
        self.assertFalse(is_deadlocked, "RLock nie powinien dopuścić do self-deadlocka!")
        self.assertEqual(len(app.typed_chunks), 1)
        self.assertIn("To jest finalny ogon zdania.", app.typed_chunks[0])

    def test_07_multithreaded_concurrency_stress(self):
        """
        TEST WSPÓŁBIEŻNOŚCI WIELOWĄTKOWEJ z RLock:
        Symulacja jednoczesnego działania:
        - Wątek 1: Streaming worker (generuje hipotezy i commity)
        - Wątek 2: Focus monitor / UI worker (próbuje opróżniać bufor lub sprawdzać stan)
        """
        app = MockDictationApp(lock_factory=threading.RLock)
        stop_event = threading.Event()
        errors = []

        def streaming_sim():
            try:
                for i in range(50):
                    if stop_event.is_set():
                        break
                    with app._type_lock:
                        app.committer.process_hypothesis(f"Słowo {i} kolejne słowo {i} ogon")
                        if i % 5 == 0:
                            app.committer.commit_segment(f"Segment numer {i}")
                    time.sleep(0.005)
            except Exception as e:
                errors.append(f"Streaming error: {e}")

        def ui_monitor_sim():
            try:
                for _ in range(50):
                    if stop_event.is_set():
                        break
                    with app._type_lock:
                        if app.buffered_untyped_text:
                            app.typed_chunks.append(app.buffered_untyped_text)
                            app.buffered_untyped_text = ""
                    time.sleep(0.005)
            except Exception as e:
                errors.append(f"UI monitor error: {e}")

        t1 = threading.Thread(target=streaming_sim)
        t2 = threading.Thread(target=ui_monitor_sim)

        t1.start()
        t2.start()

        t1.join(timeout=3.0)
        t2.join(timeout=3.0)

        is_stuck = t1.is_alive() or t2.is_alive()
        stop_event.set()

        print("\n--- TEST 7: Multi-threaded Stress Test z RLock ---")
        print(f"Zawieszenie wątków: {is_stuck} | Błędy: {errors} | Liczba wygenerowanych chunków: {len(app.typed_chunks)}")
        self.assertFalse(is_stuck, "Wątki nie powinny się zakleszczyć podczas jednoczesnej pracy!")
        self.assertEqual(len(errors), 0, f"Wystąpiły błędy współbieżności: {errors}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
