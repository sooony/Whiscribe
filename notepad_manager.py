"""
notepad_manager.py - Zarządzanie zapisem transkrypcji spotkań do pliku i Notatnika Windows.
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

logger = logging.getLogger("whiscribe.notepad")

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
            f" TRANSKRYPCJA SPOTKANIA\n"
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

        # Zapis do pliku tekstowego bez wywoływania zewnętrznego procesu Notepad.exe
        logger.info(f"Sesja spotkania przygotowana, plik='{self.filepath}'")
        return self.filepath

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
        """Aktualizuje zawartość powiązanego dokumentu Notatnika, jeśli został jawnie podpięty."""
        if self._val_pattern:
            try:
                self._val_pattern.SetValue(self._all_text)
            except Exception as e:
                logger.debug(f"Błąd aktualizacji przez ValuePattern: {e}")
                self._val_pattern = None


    def get_full_text(self) -> str:
        with self._lock:
            return self._all_text
