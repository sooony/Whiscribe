"""
notepad_manager.py - Moduł automatyzacji i synchronizacji transkrypcji spotkań z Notatnikiem Windows.

Funkcjonalności:
1. Automatyczne uruchamianie okna Notepad.exe z nową sesją spotkania.
2. Tworzenie bezpiecznego pliku kopii zapasowej w folderze 'transkrypcje/spotkanie_YYYY-MM-DD_HH-MM-SS.txt'.
3. Płynne, bezopóźnieniowe dopisywanie nowych wypowiedzi z formatem: [HH:MM] Uczestnik: treść.
4. Niekradnący fokusu mechanizm (UIAutomation ValuePattern + Win32 Fallback).
5. Dołączanie podsumowania końcowego (czas trwania, data, liczba uczestników).
"""

import os
import sys
import time
import subprocess
import threading
import datetime
import logging
import ctypes
from ctypes import wintypes

logger = logging.getLogger("NotepadManager")

class NotepadManager:
    def __init__(self, output_dir: str = "transkrypcje"):
        self.output_dir = os.path.abspath(output_dir)
        os.makedirs(self.output_dir, exist_ok=True)
        
        self.filepath = None
        self.process = None
        self.hwnd = None
        self._doc_control = None
        self._val_pattern = None
        self._lock = threading.Lock()
        self._all_text = ""
        self.start_dt = None

    def start_meeting_session(self) -> str:
        """
        Tworzy plik transkrypcji, uruchamia Notatnik Windows i przygotowuje nagłówek.
        Zwraca ścieżkę do utworzonego pliku.
        """
        self.start_dt = datetime.datetime.now()
        timestamp_str = self.start_dt.strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"spotkanie_{timestamp_str}.txt"
        self.filepath = os.path.join(self.output_dir, filename)

        header = (
            "======================================================================\n"
            f" TRANSKRYPCJA SPOTKANIA (AI MEETING TRANSCRIPTION)\n"
            f" Data: {self.start_dt.strftime('%Y-%m-%d')}\n"
            f" Rozpoczęcie: {self.start_dt.strftime('%H:%M:%S')}\n"
            " Separacja mówców: Ja (Mikrofon) | Uczestnicy zewnętrzni (Głośniki/System)\n"
            "======================================================================\n\n"
        )
        self._all_text = header

        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                f.write(header)
        except Exception as e:
            logger.error(f"Nie udało się utworzyć pliku {self.filepath}: {e}")

        # Uruchomienie Notatnika Windows z plikiem
        try:
            self.process = subprocess.Popen(["notepad.exe", self.filepath])
            logger.info(f"Uruchomiono Notatnik: PID={self.process.pid}, plik='{self.filepath}'")
        except Exception as e:
            logger.error(f"Błąd uruchamiania notepad.exe: {e}")

        # Podłączenie UIAutomation w tle
        threading.Thread(target=self._connect_ui_automation, daemon=True).start()
        return self.filepath

    def _connect_ui_automation(self):
        """Wyszukuje kontrolkę edytora w otwartym Notatniku."""
        time.sleep(0.8)
        for attempt in range(10):
            try:
                import uiautomation as auto
                # Znajdź okno Notatnika
                np_window = auto.WindowControl(searchDepth=1, ClassName="Notepad")
                if np_window.Exists(maxSearchSeconds=1):
                    doc = np_window.DocumentControl()
                    if doc.Exists(maxSearchSeconds=1):
                        val_pat = doc.GetValuePattern()
                        if val_pat:
                            with self._lock:
                                self._doc_control = doc
                                self._val_pattern = val_pat
                            logger.info("Pomyślnie podpięto UIAutomation pod Notatnik Windows 11.")
                            return
            except Exception as e:
                logger.debug(f"Próba podpięcia uiautomation ({attempt+1}/10): {e}")
            time.sleep(0.4)
        logger.warning("Nie udało się podpiąć UIAutomation. Transkrypcja będzie zapisywana bezpośrednio do pliku.")

    def append_utterance(self, speaker: str, text: str, timestamp: datetime.datetime = None):
        """
        Dopisuje wypowiedź w formacie: [HH:MM] Uczestnik: treść.
        Zapisuje natychmiast do pliku na dysku i aktualizuje okno Notatnika.
        """
        if not text or not text.strip():
            return

        ts = timestamp or datetime.datetime.now()
        time_tag = ts.strftime("%H:%M")
        line = f"[{time_tag}] {speaker}: {text.strip()}\n"

        with self._lock:
            self._all_text += line

            # 1. Zapis natychmiastowy do pliku dyskowego
            if self.filepath:
                try:
                    with open(self.filepath, "a", encoding="utf-8") as f:
                        f.write(line)
                        f.flush()
                except Exception as e:
                    logger.error(f"Błąd zapisu do pliku: {e}")

            # 2. Aktualizacja otwartego okna Notatnika
            self._update_notepad_display()

    def append_summary(self, end_dt: datetime.datetime, total_participants: int, participant_details: list[str] = None):
        """
        Dopisuje ustrukturyzowane podsumowanie spotkania po jego zakończeniu.
        """
        if not self.start_dt:
            self.start_dt = end_dt

        duration_sec = int((end_dt - self.start_dt).total_seconds())
        mins, secs = divmod(duration_sec, 60)
        hours, mins = divmod(mins, 60)
        dur_str = f"{hours}h {mins}m {secs}s" if hours > 0 else f"{mins} min {secs} s"

        details_block = ""
        if participant_details:
            details_block = "\n".join([f"  • {item}" for item in participant_details])

        summary = (
            "\n"
            "======================================================================\n"
            " PODSUMOWANIE SPOTKANIA:\n"
            f" Data: {self.start_dt.strftime('%Y-%m-%d')}\n"
            f" Czas trwania: {self.start_dt.strftime('%H:%M:%S')} - {end_dt.strftime('%H:%M:%S')} ({dur_str})\n"
            f" Sugerowana liczba osób biorących udział: {total_participants}\n"
        )
        if details_block:
            summary += f" Wykryci rozmówcy:\n{details_block}\n"
        summary += "======================================================================\n"

        with self._lock:
            self._all_text += summary
            if self.filepath:
                try:
                    with open(self.filepath, "a", encoding="utf-8") as f:
                        f.write(summary)
                        f.flush()
                except Exception as e:
                    logger.error(f"Błąd zapisu podsumowania: {e}")

            self._update_notepad_display()

    def _update_notepad_display(self):
        """Aktualizuje zawartość dokumentu w Notatniku bez zabierania fokusu."""
        if self._val_pattern:
            try:
                self._val_pattern.SetValue(self._all_text)
                return
            except Exception as e:
                logger.debug(f"Błąd aktualizacji przez ValuePattern: {e}")
                self._val_pattern = None

        # Fallback: próba ponownego wyszukania lub Win32
        try:
            import uiautomation as auto
            np_window = auto.WindowControl(searchDepth=1, ClassName="Notepad")
            if np_window.Exists(maxSearchSeconds=0.5):
                doc = np_window.DocumentControl()
                val = doc.GetValuePattern()
                if val:
                    self._val_pattern = val
                    val.SetValue(self._all_text)
        except Exception:
            pass

    def get_full_text(self) -> str:
        with self._lock:
            return self._all_text
