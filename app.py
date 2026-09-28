import time
import threading
import winsound
import subprocess
import ctypes
from ctypes import wintypes
import os
import sys
import logging

if sys.stdout is not None:
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
if sys.stderr is not None:
    try:
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

try:
    ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass
import numpy as np
from PIL import Image, ImageDraw
import pystray
from pynput import keyboard

from config import load_config, save_config, CONFIG_FILE
from recorder import AudioRecorder
from transcriber import Transcriber
from injector import inject_text, sync_text, send_unicode_string, ForwardStreamCommitter
from overlay import FloatingOverlay, THEMES
from focus_detector import is_text_field_focused, NON_EDITABLE_WINDOW_CLASSES, get_proc_name_from_hwnd
from meeting_manager import MeetingManager

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

def safe_bring_to_foreground(hwnd: int) -> bool:
    """
    Bezpieczne, błyskawiczne i bezblokujące przywrócenie okna docelowego w Windows.
    Brak AttachThreadInput = ZERO ryzyka deadlocka / zawieszenia wątku GUI!
    """
    if not hwnd or not user32.IsWindow(hwnd):
        return False
    cur = user32.GetForegroundWindow()
    if cur == hwnd:
        return True

    # 1. Próba przez AllowSetForegroundWindow + SwitchToThisWindow
    try:
        user32.AllowSetForegroundWindow(-1)
    except Exception:
        pass

    user32.ShowWindow(hwnd, 5)  # SW_SHOW
    user32.SwitchToThisWindow(hwnd, True)
    res = user32.SetForegroundWindow(hwnd)
    user32.BringWindowToTop(hwnd)

    if user32.GetForegroundWindow() == hwnd:
        return True

    # 2. Jeśli Windows nadal blokuje pierwszy plan, użyj Alt-key bypass
    user32.keybd_event(0x12, 0, 0, 0)
    user32.keybd_event(0x12, 0, 2, 0)
    res = user32.SetForegroundWindow(hwnd)
    user32.BringWindowToTop(hwnd)

    for _ in range(5):
        if user32.GetForegroundWindow() == hwnd:
            return True
        time.sleep(0.02)

    return res != 0

def get_window_title(hwnd: int) -> str:
    if not hwnd or not user32.IsWindow(hwnd):
        return ""
    length = user32.GetWindowTextLengthW(hwnd)
    if length > 0:
        buff = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buff, length + 1)
        return buff.value
    return ""

def is_mouse_down() -> bool:
    """Zwraca True jeśli lewy, prawy lub środkowy przycisk myszy jest obecnie fizycznie wciśnięty."""
    for vk in (0x01, 0x02, 0x04):  # VK_LBUTTON, VK_RBUTTON, VK_MBUTTON
        if (user32.GetAsyncKeyState(vk) & 0x8000) != 0:
            return True
    return False

LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.log")
handlers = [logging.FileHandler(LOG_FILE, encoding='utf-8')]
if sys.stdout is not None:
    handlers.append(logging.StreamHandler(sys.stdout))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=handlers,
    force=True
)
logger = logging.getLogger("DictationApp")

def create_tray_icon_image(state="idle") -> Image.Image:
    """Generuje dynamiczną ikonę dla paska zadań w zależności od stanu."""
    size = (64, 64)
    img = Image.new('RGBA', size, color=(0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    if state == "recording":
        # Czerwona pulsująca kropka
        d.ellipse((6, 6, 58, 58), fill='#f38ba8')
        d.ellipse((18, 18, 46, 46), fill='#d20f39')
    elif state == "meeting":
        # Fioletowo-indygo pulsująca kropka (spotkanie)
        d.ellipse((6, 6, 58, 58), fill='#a5b4fc')
        d.ellipse((18, 18, 46, 46), fill='#6366f1')
    elif state == "processing":
        # Żółta/pomarańczowa kropka
        d.ellipse((6, 6, 58, 58), fill='#fab387')
        d.ellipse((20, 20, 44, 44), fill='#fe640b')
    else:
        # Ciemne tło z niebieską/zieloną obwódką (czuwanie)
        d.ellipse((6, 6, 58, 58), fill='#1e1e2e', outline='#89b4fa', width=5)
        # Mała ikonka mikrofonu w środku
        d.rectangle((28, 20, 36, 36), fill='#89b4fa')
        d.ellipse((26, 16, 38, 26), fill='#89b4fa')
        d.arc((22, 26, 42, 42), start=0, end=180, fill='#89b4fa', width=3)
        d.line((32, 42, 32, 48), fill='#89b4fa', width=3)
        d.line((24, 48, 40, 48), fill='#89b4fa', width=3)

    return img

def format_hotkey(hk: str) -> str:
    """Konwertuje zwykły string skrótu (np. ctrl+alt+d lub f8) na format akceptowany przez pynput."""
    parts = hk.lower().replace(" ", "").split("+")
    formatted = []
    for p in parts:
        if not p.startswith("<") and (len(p) > 1 or p.startswith("f")):
            formatted.append(f"<{p}>")
        elif not p.startswith("<"):
            formatted.append(p)
        else:
            formatted.append(p)
    return "+".join(formatted)

class DictationApp:
    def __init__(self):
        self.config = load_config()
        self.recorder = AudioRecorder(sample_rate=16000)
        theme = self.config.get("theme", "light")
        self.overlay = FloatingOverlay(theme=theme) if self.config.get("show_overlay", True) else None
        
        logger.info("Inicjalizacja modułu rozpoznawania mowy Whisper...")
        self.transcriber = Transcriber(self.config)
        self.meeting_manager = MeetingManager(self.transcriber, self.config)

        if self.overlay:
            logger.info(f"FloatingOverlay utworzony: HWND={self.overlay.hwnd}, visible={self.overlay._visible}")
            self.overlay.on_theme_changed = self._on_overlay_theme_changed
            self.overlay.set_volume_getter(self.recorder.get_volume_level)
            self.overlay.set_meeting_volume_getter(self.meeting_manager.recorder.get_total_volume)
            self.overlay.set_callbacks(
                on_stop=self.stop_and_transcribe,
                on_close=self.cancel_dictation,
                on_toggle=self.toggle_dictation,
                on_meeting_toggle=self.toggle_meeting
            )
            self.overlay.set_settings_handler(self._show_settings_menu)
            self.overlay.show()
            self.overlay.show_idle()

        # Przyjemny krótki dźwięk gotowości
        self._play_beep(1200, 60)
        time.sleep(0.06)
        self._play_beep(1600, 70)
        
        self.state = "idle"  # "idle", "recording", "processing"
        self._lock = threading.RLock()
        self._type_lock = threading.RLock()
        self._stream_stop_event = threading.Event()
        self._streaming_thread = None
        self._recording_start_time = 0.0
        self.committed_text = ""
        self.committed_sample_offset = 0
        self.committer = ForwardStreamCommitter(type_callback=self._type_stream_chunk)

        self.target_hwnd = None
        self.target_proc = ""
        self.buffered_untyped_text = ""
        self.last_active_hwnd = 0

        try:
            user32.SystemParametersInfoW(0x2001, 0, ctypes.c_void_p(0), 2)
            user32.AllowSetForegroundWindow(-1)
        except Exception:
            pass

        self.tray_icon = None
        self.hotkey_listener = None
        self._running = True

        # Wątek monitorujący ciszę (opcjonalny auto-stop)
        self._silence_monitor_thread = threading.Thread(target=self._monitor_silence, daemon=True)
        self._silence_monitor_thread.start()

        # Wątek nasłuchujący sygnału pokazania widżetu (gdy użytkownik ponownie kliknie skrót/ikonę)
        self._show_event_thread = threading.Thread(target=self._listen_for_show_event, daemon=True)
        self._show_event_thread.start()

        # Wątek monitorujący stan skrótów klawiszowych (np. po Winlogon/Ctrl+Alt+Del)
        self._hotkey_watchdog_thread = threading.Thread(target=self._watchdog_hotkey, daemon=True)
        self._hotkey_watchdog_thread.start()

    def _type_stream_chunk(self, chunk: str):
        """Wpisuje słowa w przód (Forward-only) z ciągłym streamingiem do zablokowanego okna docelowego (nawet przy pracy na 2 monitorach)."""
        if not chunk:
            return

        with self._type_lock:
            cur_fg = user32.GetForegroundWindow()

            # 1. Okno docelowe jest aktywne na pierwszym planie (np. Antigravity) LUB trwa finalizacja (state == "processing")
            if (hasattr(self, 'target_hwnd') and self.target_hwnd and cur_fg == self.target_hwnd) or self.state == "processing":
                if self.buffered_untyped_text:
                    full_chunk = self.buffered_untyped_text + chunk
                    self.buffered_untyped_text = ""
                else:
                    full_chunk = chunk
                send_unicode_string(full_chunk)
                return

            # 2. Użytkownik przegląda drugie okno (np. Chrome na drugim monitorze)
            if hasattr(self, 'target_hwnd') and self.target_hwnd and user32.IsWindow(self.target_hwnd):
                # Jeśli użytkownik akurat fizycznie trzyma wciśnięty przycisk myszy (np. klika/zaznacza w Chrome),
                # buforujemy na ten moment, aby nie przerwać zaznaczania:
                if is_mouse_down():
                    self.buffered_untyped_text += chunk
                    return

                # Błyskawiczny mikro-impuls (Micro-Pulse):
                # Przekierowujemy wpisywanie do okna docelowego na Monitorze 1 i natychmiast wracamy do Chrome na Monitorze 2
                other_fg = cur_fg
                full_chunk = self.buffered_untyped_text + chunk if self.buffered_untyped_text else chunk
                self.buffered_untyped_text = ""

                safe_bring_to_foreground(self.target_hwnd)
                send_unicode_string(full_chunk)
                if other_fg and user32.IsWindow(other_fg) and other_fg != self.target_hwnd:
                    safe_bring_to_foreground(other_fg)
            else:
                send_unicode_string(chunk)

    def _listen_for_show_event(self):
        """Nasłuchuje sygnału IPC z kolejnej próby uruchomienia aplikacji i natychmiast przywraca widżet PIL."""
        EVENT_NAME = "DyktowanieAI_ShowOverlay_Event"
        h_event = ctypes.windll.kernel32.CreateEventW(None, False, False, EVENT_NAME)
        while self._running:
            res = ctypes.windll.kernel32.WaitForSingleObject(h_event, 500)
            if res == 0:  # WAIT_OBJECT_0
                logger.info("Odebrano sygnał wybudzenia/pokazania widżetu PIL.")
                if self.overlay:
                    self.overlay.show()
                    self.overlay.show_idle()
                self._play_beep(1400, 60)
        if h_event:
            ctypes.windll.kernel32.CloseHandle(h_event)

    def _play_start_chime(self):
        """Płynny, wzrastający dźwięk rozpoczęcia wpisywania głosowego (styl Windows 11)."""
        if self.config.get("sound_feedback", True):
            try:
                winsound.Beep(750, 60)
                winsound.Beep(1100, 80)
            except Exception:
                pass

    def _play_stop_chime(self):
        """Płynny, opadający dźwięk zakończenia wpisywania głosowego (styl Windows 11)."""
        if self.config.get("sound_feedback", True):
            try:
                winsound.Beep(1100, 60)
                winsound.Beep(750, 80)
            except Exception:
                pass

    def _play_error_chime(self):
        """Dźwięk ostrzegawczy przy próbie pisania bez zaznaczonego pola tekstowego."""
        if self.config.get("sound_feedback", True):
            try:
                winsound.Beep(450, 80)
                time.sleep(0.04)
                winsound.Beep(320, 110)
            except Exception:
                pass

    def _play_beep(self, freq, duration):
        if self.config.get("sound_feedback", True):
            try:
                winsound.Beep(freq, duration)
            except Exception:
                pass

    def start_recording(self):
        # 1. Rygorystyczny czujnik aktywnego pola tekstowego
        if self.config.get("require_text_field", True):
            is_focused, reason = is_text_field_focused()
            if not is_focused:
                logger.warning(f"Zablokowano start dyktowania – brak aktywnego pola tekstowego ({reason})")
                self._play_error_chime()
                if self.overlay:
                    self.overlay.show()
                    self.overlay.show_error_balloon()
                return

        # 2. Bezpieczna zmiana stanu pod lockiem PRZED startem mikrofonu
        with self._lock:
            if self.state != "idle":
                return
            self.state = "recording"

        # Ukryj ewentualny dymek ostrzegawczy
        if self.overlay:
            self.overlay.hide_balloon()

        # 3. Zapamiętanie i zablokowanie okna docelowego do wklejenia tekstu
        cur_fg = user32.GetForegroundWindow()
        if cur_fg and (not self.overlay or cur_fg != self.overlay.hwnd):
            self.target_hwnd = cur_fg
        elif hasattr(self, 'last_active_hwnd') and self.last_active_hwnd and user32.IsWindow(self.last_active_hwnd):
            self.target_hwnd = self.last_active_hwnd

        if hasattr(self, 'target_hwnd') and self.target_hwnd:
            self.target_proc = get_proc_name_from_hwnd(self.target_hwnd)
            win_title = get_window_title(self.target_hwnd)
            logger.info(f"Zablokowano okno docelowe transkrypcji: HWND={self.target_hwnd:#x} ({self.target_proc} - '{win_title}')")

        self.buffered_untyped_text = ""
        self.recorder.start()
        self._recording_start_time = time.time()

        logger.info("Rozpoczęto dyktowanie...")
        self.committed_text = ""
        self.committed_sample_offset = 0
        self.committer = ForwardStreamCommitter(type_callback=self._type_stream_chunk)
        self._stream_stop_event.clear()

        if self.overlay:
            self.overlay.show()
            self.overlay.show_recording()
        if self.tray_icon:
            self.tray_icon.icon = create_tray_icon_image("recording")

        self._play_start_chime()

        # Jeśli streaming na żywo jest włączony, uruchom wątek pisania w czasie rzeczywistym
        if self.config.get("stream_realtime", False):
            self._streaming_thread = threading.Thread(target=self._streaming_worker, daemon=True)
            self._streaming_thread.start()

    def _streaming_worker(self):
        """
        Wątek inteligentnego streamingu na żywo (styl Windows 11 Voice Typing):
        - Wyłącznie wpisywanie w przód (Forward-Only).
        - Zakończone segmenty są definitywnie zatwierdzane i przesuwają wskaźnik audio.
        - Trwające wypowiedzi zatwierdzają ustabilizowane słowa w przód.
        - Audio i transkrypcja Whisper działają nieprzerwanie, nawet gdy użytkownik przegląda Chrome lub inne okna!
        """
        while not self._stream_stop_event.is_set() and self.state == "recording":
            time.sleep(0.32)
            if self._stream_stop_event.is_set() or self.state != "recording":
                break

            audio = self.recorder.get_current_audio()
            if audio is None:
                continue

            # Pobieramy wyłącznie dźwięk od ostatniego zatwierdzonego segmentu
            uncommitted_audio = audio[self.committed_sample_offset:]

            if len(uncommitted_audio) < 16000 * 0.40:
                continue

            # Transkrypcja aktywnego fragmentu bez przerywania
            completed, tail_text = self.transcriber.transcribe_stream_chunk(uncommitted_audio)

            if self._stream_stop_event.is_set() or self.state != "recording":
                break

            # 1. ZATWIERDŹ ZAKOŃCZONE SEGMENTY (COMMIT) - NA ZAWSZE W DOKUMENCIE
            if completed:
                with self._type_lock:
                    for seg_text, end_sec in completed:
                        self.committer.commit_segment(seg_text)
                        self.committed_sample_offset += int(end_sec * 16000)

            # 2. ZAKTUALIZUJ BIEŻĄCY OGON (STABILNE SŁOWA WPISYWANE W PRZÓD)
            if tail_text:
                with self._type_lock:
                    self.committer.process_hypothesis(tail_text)
                if self.overlay:
                    self.overlay.update_live_text(tail_text)

            # 3. Jeśli użytkownik wrócił fokusem do okna docelowego, natychmiast opróżnij bufor
            cur_fg = user32.GetForegroundWindow()
            if hasattr(self, 'target_hwnd') and self.target_hwnd and cur_fg == self.target_hwnd:
                with self._type_lock:
                    if self.buffered_untyped_text:
                        send_unicode_string(self.buffered_untyped_text)
                        self.buffered_untyped_text = ""

    def stop_and_transcribe(self):
        with self._lock:
            if self.state != "recording":
                return
            self.state = "processing"

        logger.info("Zatrzymano nagrywanie, finalizowanie...")
        self._stream_stop_event.set()
        self._play_stop_chime()

        if self.overlay:
            self.overlay.show_processing()
        if self.tray_icon:
            self.tray_icon.icon = create_tray_icon_image("processing")

        # Bezpieczne odczekanie na zakończenie bieżącego kroku streamingu GPU
        if self._streaming_thread and self._streaming_thread.is_alive():
            self._streaming_thread.join(timeout=0.4)

        # Pobierz pełne nagranie
        audio_data = self.recorder.stop()

        # Uruchom finalizację w osobnym wątku
        threading.Thread(target=self._process_audio_worker, args=(audio_data,), daemon=True).start()

    def _process_audio_worker(self, audio_data):
        try:
            t0 = time.time()

            if self.config.get("stream_realtime", False):
                # Tryb streamingu:
                remaining_audio = audio_data[self.committed_sample_offset:] if len(audio_data) > self.committed_sample_offset else None
                final_tail = ""
                if remaining_audio is not None and len(remaining_audio) >= 16000 * 0.35:
                    rem_max = float(np.max(np.abs(remaining_audio))) if len(remaining_audio) > 0 else 0.0
                    if rem_max >= 0.022:
                        final_tail = self.transcriber.transcribe(remaining_audio)

                # 1. Przywróć definitywnie fokus do okna docelowego PRZED wpisaniem końcówki i opróżnieniem bufora
                if hasattr(self, 'target_hwnd') and self.target_hwnd and user32.IsWindow(self.target_hwnd):
                    cur_fg = user32.GetForegroundWindow()
                    if cur_fg != self.target_hwnd:
                        logger.info(f"Przywracanie fokusu do okna docelowego przed wpisaniem (HWND={self.target_hwnd:#x})")
                        safe_bring_to_foreground(self.target_hwnd)
                        for _ in range(15):
                            if user32.GetForegroundWindow() == self.target_hwnd:
                                break
                            time.sleep(0.02)

                # Opróżnij zaległy bufor jeśli cokolwiek zostało podczas przełączania okien
                with self._type_lock:
                    if self.buffered_untyped_text:
                        send_unicode_string(self.buffered_untyped_text)
                        self.buffered_untyped_text = ""

                    if final_tail:
                        self.committer.finalize(final_tail)
                    else:
                        self.committer.finalize()

                    # Upewnij się, że ogon (final_tail) lub jakiekolwiek zaległe znaki po finalize też zostały wpisane
                    if self.buffered_untyped_text:
                        send_unicode_string(self.buffered_untyped_text)
                        self.buffered_untyped_text = ""

                self._play_stop_chime()
                logger.info(f"Finalizacja streamingu: {time.time() - t0:.2f}s | Wpisano łącznie: '{self.committer.typed_text.strip()}'")

            else:
                # Czyste wklejenie po zatrzymaniu nagrywania (tryb batch)
                final_text = self.transcriber.transcribe(audio_data)
                duration = time.time() - t0
                logger.info(f"Finalny czas: {duration:.2f}s | Tekst: '{final_text}'")

                if final_text:
                    # Przywróć definitywnie fokus do okna docelowego BEZPOŚREDNIO przed wklejeniem
                    if hasattr(self, 'target_hwnd') and self.target_hwnd and user32.IsWindow(self.target_hwnd):
                        cur_fg = user32.GetForegroundWindow()
                        if cur_fg != self.target_hwnd:
                            logger.info(f"Przywracanie fokusu do okna docelowego przed wklejeniem (HWND={self.target_hwnd:#x})")
                            safe_bring_to_foreground(self.target_hwnd)
                            for _ in range(15):
                                if user32.GetForegroundWindow() == self.target_hwnd:
                                    break
                                time.sleep(0.02)

                    inject_text(final_text, restore_clipboard=self.config.get("restore_clipboard", False))
                    self._play_stop_chime()

        except Exception as e:
            logger.error(f"Błąd podczas finalizacji: {e}", exc_info=True)
        finally:
            self.committed_text = ""
            self.committed_sample_offset = 0
            self.buffered_untyped_text = ""
            with self._lock:
                self.state = "idle"
            if self.tray_icon:
                self.tray_icon.icon = create_tray_icon_image("idle")
            if self.overlay:
                self.overlay.show_idle()

    def toggle_dictation(self):
        """Obsługa naciśnięcia klawisza/przycisku myszy w trybie Toggle."""
        if self.state == "idle":
            self.start_recording()
        elif self.state == "recording":
            self.stop_and_transcribe()
        elif self.state == "meeting_recording":
            logger.info("Zatrzymywanie spotkania przed przełączeniem do trybu dyktowania...")
            self.stop_meeting()

    def cancel_dictation(self):
        """Anuluje nagrywanie bez wklejania tekstu (np. po kliknięciu krzyżyka ✕)."""
        with self._lock:
            if self.state != "recording":
                return
            self.state = "idle"
        logger.info("Anulowano dyktowanie przez użytkownika.")
        self._stream_stop_event.set()
        self.recorder.stop()
        self.committer.reset_for_new_segment()
        self.committed_sample_offset = 0
        self.committed_text = ""
        self.buffered_untyped_text = ""
        if self.overlay:
            self.overlay.show_idle()
        if self.tray_icon:
            self.tray_icon.icon = create_tray_icon_image("idle")
        self._play_error_chime()

    def _watchdog_hotkey(self):
        """Monitoruje żywotność globalnych skrótów klawiszowych (np. po Ctrl+Alt+Delete lub ekranie blokady Windows)."""
        while self._running:
            time.sleep(3.0)
            if self._running and (self.hotkey_listener is None or not self.hotkey_listener.is_alive()):
                logger.warning("Wykryto wyłączenie wątku nasłuchiwacza skrótów (np. po Winlogon/Ctrl+Alt+Del). Wznawianie nasłuchu...")
                try:
                    self.setup_hotkey()
                except Exception as e:
                    logger.error(f"Błąd ponownego uruchomienia skrótów: {e}")

    def _monitor_silence(self):
        """Automatyczne zatrzymanie po ciszy oraz śledzenie ostatniego aktywnego okna roboczego."""
        while self._running:
            time.sleep(0.2)
            if self.state == "idle":
                cur_fg = user32.GetForegroundWindow()
                if cur_fg and (not self.overlay or cur_fg != self.overlay.hwnd):
                    self.last_active_hwnd = cur_fg

            auto_stop_sec = float(self.config.get("auto_stop_silence_seconds", 4.5))
            if auto_stop_sec > 0 and self.state == "recording":
                # Okres karencji: minimum 3.0s od momentu włączenia nagrywania zanim cisza może zatrzymać
                if time.time() - self._recording_start_time < 3.0:
                    continue
                if self.recorder.seconds_since_last_voice >= auto_stop_sec:
                    logger.info(f"Wykryto {auto_stop_sec:.1f}s nieprzerwanej ciszy – automatyczne zatrzymanie nagrywania.")
                    self.stop_and_transcribe()

    def set_silence_timeout(self, seconds: int):
        def _handler(icon, item):
            self.config["auto_stop_silence_seconds"] = seconds
            save_config(self.config)
            logger.info(f"Ustawiono automatyczne zatrzymanie ciszy: {seconds}s")
        return _handler

    def start_meeting(self):
        """Rozpoczyna sesję nagrywania i transkrypcji spotkania z podziałem na mówców."""
        with self._lock:
            if self.state != "idle":
                return
            self.state = "meeting_recording"

        logger.info("Rozpoczęto tryb spotkania (Meeting Mode)...")
        if self.overlay:
            self.overlay.show_meeting_recording()
        if self.tray_icon:
            self.tray_icon.icon = create_tray_icon_image("meeting")

        self._play_start_chime()

        try:
            self.meeting_manager.start_meeting()
        except Exception as e:
            logger.error(f"Nie udało się uruchomić spotkania: {e}", exc_info=True)
            self.stop_meeting()

    def stop_meeting(self):
        """Zatrzymuje nagrywanie spotkania, przetwarza pozostałe segmenty i generuje podsumowanie."""
        with self._lock:
            if self.state != "meeting_recording":
                return
            self.state = "processing"

        logger.info("Zatrzymywanie spotkania i generowanie podsumowania...")
        if self.overlay:
            self.overlay.show_processing()
        if self.tray_icon:
            self.tray_icon.icon = create_tray_icon_image("processing")
        self._play_stop_chime()

        def _finalize_worker():
            try:
                summary = self.meeting_manager.stop_meeting()
                logger.info(f"Finalizacja spotkania zakończona: {summary}")
            except Exception as e:
                logger.error(f"Błąd finalizacji spotkania: {e}", exc_info=True)
            finally:
                with self._lock:
                    self.state = "idle"
                if self.tray_icon:
                    self.tray_icon.icon = create_tray_icon_image("idle")
                if self.overlay:
                    self.overlay.show_idle()
                logger.info("Aplikacja pomyślnie powróciła do stanu gotowości (idle).")

        threading.Thread(target=_finalize_worker, daemon=True).start()

    def toggle_meeting(self):
        """Przełącznik trybu spotkania (z poziomu skrótu Ctrl+Alt+M lub przycisku na widżecie)."""
        if self.state == "idle":
            self.start_meeting()
        elif self.state == "meeting_recording":
            self.stop_meeting()
        elif self.state == "recording":
            logger.info("Zatrzymywanie dyktowania przed rozpoczęciem spotkania...")
            self.stop_and_transcribe()
            def _wait_and_start_meeting():
                for _ in range(50):
                    time.sleep(0.1)
                    if self.state == "idle":
                        self.start_meeting()
                        break
            threading.Thread(target=_wait_and_start_meeting, daemon=True).start()

    def open_transcripts_folder(self):
        try:
            folder = os.path.abspath(self.config.get("meetings_folder", "transkrypcje"))
            os.makedirs(folder, exist_ok=True)
            os.startfile(folder)
        except Exception as e:
            logger.error(f"Błąd otwierania folderu transkrypcji: {e}")

    def setup_hotkey(self):
        try:
            h_def = ctypes.windll.user32.OpenDesktopW("Default", 0, False, 0x01FF)
            if h_def:
                ctypes.windll.user32.SetThreadDesktop(h_def)
        except Exception:
            pass

        if self.hotkey_listener is not None:
            try:
                self.hotkey_listener.stop()
            except Exception:
                pass
            self.hotkey_listener = None

        raw_hotkey = self.config.get("hotkey", "<ctrl>+<alt>+d")
        formatted = format_hotkey(raw_hotkey)
        raw_meeting = self.config.get("hotkey_meeting", "<ctrl>+<alt>+m")
        formatted_meeting = format_hotkey(raw_meeting)
        logger.info(f"Rejestracja globalnych skrótów: Dyktowanie={formatted}, Spotkanie={formatted_meeting}")

        def _async_toggle_dictation():
            threading.Thread(target=self.toggle_dictation, daemon=True).start()

        def _async_toggle_meeting():
            threading.Thread(target=self.toggle_meeting, daemon=True).start()

        hotkey_map = {
            formatted: _async_toggle_dictation,
            formatted_meeting: _async_toggle_meeting
        }

        try:
            self.hotkey_listener = keyboard.GlobalHotKeys(hotkey_map)
            self.hotkey_listener.start()
            logger.info("Globalne nasłuchiwacze skrótów uruchomione pomyślnie!")
        except Exception as e:
            logger.error(f"Nie udało się zarejestrować skrótów: {e}")

    def open_config_file(self):
        try:
            os.system(f'notepad.exe "{CONFIG_FILE}"')
        except Exception as e:
            logger.error(f"Błąd otwierania config: {e}")

    def toggle_sound_feedback(self):
        self.config["sound_feedback"] = not self.config.get("sound_feedback", True)
        save_config(self.config)
        logger.info(f"Dźwięki powiadomień: {'Włączone' if self.config['sound_feedback'] else 'Wyłączone'}")

    def toggle_require_text_field(self):
        self.config["require_text_field"] = not self.config.get("require_text_field", True)
        save_config(self.config)
        logger.info(f"Wymóg pola tekstowego: {'Włączony' if self.config['require_text_field'] else 'Wyłączony'}")

    def toggle_streaming_mode(self):
        self.config["stream_realtime"] = not self.config.get("stream_realtime", True)
        save_config(self.config)
        logger.info(f"Pisanie na żywo: {'Włączone' if self.config['stream_realtime'] else 'Wyłączone'}")

    def toggle_overlay_visibility(self):
        if not self.overlay:
            return
        if self.overlay._visible:
            self.overlay.hide()
        else:
            self.overlay.show()
            self.overlay.show_idle()

    def exit_app(self):
        logger.info("Zamykanie aplikacji...")
        self._running = False
        self._stream_stop_event.set()
        if hasattr(self, "meeting_manager") and self.meeting_manager:
            try:
                self.meeting_manager.close()
            except Exception:
                pass
        if self.hotkey_listener:
            try:
                self.hotkey_listener.stop()
            except Exception:
                pass
        if self.overlay:
            self.overlay.close()
        if self.tray_icon:
            self.tray_icon.stop()
        sys.exit(0)

    def _show_settings_menu(self, screen_x, screen_y):
        """Wyświetla natywne menu ustawień Windows 11 po kliknięciu koła zębatego ⚙."""
        user32 = ctypes.windll.user32
        
        h_menu = user32.CreatePopupMenu()
        h_silence_sub = user32.CreatePopupMenu()
        h_theme_sub = user32.CreatePopupMenu()
        
        MF_STRING = 0x0000
        MF_SEPARATOR = 0x0800
        MF_POPUP = 0x0010
        MF_CHECKED = 0x0008
        MF_UNCHECKED = 0x0000
        
        # 1. Pisanie na żywo (Streaming)
        chk_stream = MF_CHECKED if self.config.get("stream_realtime", False) else MF_UNCHECKED
        user32.AppendMenuW(h_menu, MF_STRING | chk_stream, 101, "🎙️ Pisanie na żywo (Streaming)")
        
        # 2. Wymagaj aktywnego pola tekstowego
        chk_field = MF_CHECKED if self.config.get("require_text_field", True) else MF_UNCHECKED
        user32.AppendMenuW(h_menu, MF_STRING | chk_field, 102, "🛡️ Wymagaj aktywnego pola tekstowego")
        
        # 3. Dźwięki powiadomień
        chk_sound = MF_CHECKED if self.config.get("sound_feedback", True) else MF_UNCHECKED
        user32.AppendMenuW(h_menu, MF_STRING | chk_sound, 103, "🔊 Dźwięki potwierdzenia")

        # 4. Spotkania (Notatnik)
        user32.AppendMenuW(h_menu, MF_SEPARATOR, 0, "")
        user32.AppendMenuW(h_menu, MF_STRING, 104, "👥 Transkrypcja spotkania (Notatnik)")
        user32.AppendMenuW(h_menu, MF_STRING, 105, "📁 Otwórz folder transkrypcji spotkań")
        
        user32.AppendMenuW(h_menu, MF_SEPARATOR, 0, "")
        
        # Podmenu: Automatyczne zatrzymanie ciszy
        cur_silence = self.config.get("auto_stop_silence_seconds", 4.5)
        user32.AppendMenuW(h_silence_sub, MF_STRING | (MF_CHECKED if cur_silence == 3.0 else 0), 201, "3.0 sekundy (Krótka pauza)")
        user32.AppendMenuW(h_silence_sub, MF_STRING | (MF_CHECKED if cur_silence == 4.5 else 0), 202, "4.5 sekundy (Zalecane)")
        user32.AppendMenuW(h_silence_sub, MF_STRING | (MF_CHECKED if cur_silence == 6.0 else 0), 203, "6.0 sekund (Spokojne)")
        user32.AppendMenuW(h_silence_sub, MF_STRING | (MF_CHECKED if cur_silence == 10.0 else 0), 204, "10 sekund (Długa pauza)")
        user32.AppendMenuW(h_silence_sub, MF_STRING | (MF_CHECKED if cur_silence == 0 else 0), 205, "Wyłączone (Tylko ręcznie)")
        user32.AppendMenuW(h_menu, MF_POPUP, h_silence_sub, "⏱️ Automatyczne zatrzymanie ciszy")
        
        # Podmenu: Styl widżetu
        cur_theme = self.config.get("theme", "light")
        if cur_theme not in ("light", "dark"):
            cur_theme = "light"
        user32.AppendMenuW(h_theme_sub, MF_STRING | (MF_CHECKED if cur_theme == "light" else 0), 301, "☀️ Windows 11 Jasny (Fluent)")
        user32.AppendMenuW(h_theme_sub, MF_STRING | (MF_CHECKED if cur_theme == "dark" else 0), 302, "🌙 Windows 11 Ciemny (Fluent Dark)")
        user32.AppendMenuW(h_menu, MF_POPUP, h_theme_sub, "🎨 Styl widżetu")
        
        user32.AppendMenuW(h_menu, MF_SEPARATOR, 0, "")
        user32.AppendMenuW(h_menu, MF_STRING, 401, "⚙️ Otwórz plik konfiguracyjny (config.json)")
        user32.AppendMenuW(h_menu, MF_STRING, 402, "❌ Zamknij aplikację")
        
        hwnd = self.overlay.hwnd if self.overlay else 0
        cmd = user32.TrackPopupMenuEx(h_menu, 0x0100 | 0x0002, screen_x, screen_y, hwnd, None)
        user32.DestroyMenu(h_menu)
        
        if cmd == 101:
            self.toggle_streaming_mode()
        elif cmd == 102:
            self.toggle_require_text_field()
        elif cmd == 103:
            self.toggle_sound_feedback()
        elif cmd == 104:
            self.toggle_meeting()
        elif cmd == 105:
            self.open_transcripts_folder()
        elif cmd == 201:
            self.config["auto_stop_silence_seconds"] = 3.0
            save_config(self.config)
        elif cmd == 202:
            self.config["auto_stop_silence_seconds"] = 4.5
            save_config(self.config)
        elif cmd == 203:
            self.config["auto_stop_silence_seconds"] = 6.0
            save_config(self.config)
        elif cmd == 204:
            self.config["auto_stop_silence_seconds"] = 10.0
            save_config(self.config)
        elif cmd == 205:
            self.config["auto_stop_silence_seconds"] = 0
            save_config(self.config)
        elif cmd == 301:
            self.config["theme"] = "light"
            save_config(self.config)
            if self.overlay: self.overlay.set_theme("light")
        elif cmd == 302:
            self.config["theme"] = "dark"
            save_config(self.config)
            if self.overlay: self.overlay.set_theme("dark")
        elif cmd == 401:
            self.open_config_file()
        elif cmd == 402:
            self.exit_app()

    def _on_overlay_theme_changed(self, new_theme):
        self.config["theme"] = new_theme
        save_config(self.config)
        logger.info(f"Zmieniono motyw graficzny na: {new_theme}")

    def run_tray(self):
        self.setup_hotkey()

        def set_theme_action(t_key):
            def handler(icon, item):
                self.config["theme"] = t_key
                save_config(self.config)
                if self.overlay:
                    self.overlay.set_theme(t_key)
            return handler

        theme_items = [
            pystray.MenuItem("☀️ Windows 11 Jasny (Fluent Light)", set_theme_action("light"), checked=lambda item: self.config.get("theme", "light") == "light"),
            pystray.MenuItem("🌙 Windows 11 Ciemny (Fluent Dark)", set_theme_action("dark"), checked=lambda item: self.config.get("theme", "light") == "dark")
        ]
        theme_menu = pystray.Menu(*theme_items)

        silence_menu = pystray.Menu(
            pystray.MenuItem("3.0 sekundy (Krótka pauza)", self.set_silence_timeout(3.0), checked=lambda item: self.config.get("auto_stop_silence_seconds", 4.5) == 3.0),
            pystray.MenuItem("4.5 sekundy (Zalecane)", self.set_silence_timeout(4.5), checked=lambda item: self.config.get("auto_stop_silence_seconds", 4.5) == 4.5),
            pystray.MenuItem("6.0 sekund (Spokojne)", self.set_silence_timeout(6.0), checked=lambda item: self.config.get("auto_stop_silence_seconds", 4.5) == 6.0),
            pystray.MenuItem("10 sekund (Długa pauza)", self.set_silence_timeout(10.0), checked=lambda item: self.config.get("auto_stop_silence_seconds", 4.5) == 10.0),
            pystray.MenuItem("Wyłączone (tylko ręcznie przyciskiem ⏹)", self.set_silence_timeout(0), checked=lambda item: self.config.get("auto_stop_silence_seconds", 4.5) == 0)
        )

        menu = pystray.Menu(
            pystray.MenuItem("🎙️ Dyktowanie & Spotkania AI (RTX 3060)", None, enabled=False),
            pystray.MenuItem(f"Dyktowanie: {self.config.get('hotkey', 'Ctrl+Alt+D')}", None, enabled=False),
            pystray.MenuItem(f"Spotkanie: {self.config.get('hotkey_meeting', 'Ctrl+Alt+M')}", None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "👥 Transkrypcja spotkania (Notatnik)",
                self.toggle_meeting,
                checked=lambda item: self.state == "meeting_recording"
            ),
            pystray.MenuItem("📁 Otwórz folder z transkrypcjami spotkań", self.open_transcripts_folder),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Pokaż widżet na ekranie (Win 11)",
                self.toggle_overlay_visibility,
                checked=lambda item: self.overlay._visible if self.overlay else False
            ),
            pystray.MenuItem(
                "Styl widżetu (Motyw)",
                theme_menu
            ),
            pystray.MenuItem(
                "Wymagaj aktywnego pola tekstowego",
                self.toggle_require_text_field,
                checked=lambda item: self.config.get("require_text_field", True)
            ),
            pystray.MenuItem(
                "Pisanie na żywo (Streaming)",
                self.toggle_streaming_mode,
                checked=lambda item: self.config.get("stream_realtime", False)
            ),
            pystray.MenuItem(
                "Automatyczne zatrzymanie ciszy",
                silence_menu
            ),
            pystray.MenuItem(
                "Dźwięk potwierdzenia",
                self.toggle_sound_feedback,
                checked=lambda item: self.config.get("sound_feedback", True)
            ),
            pystray.MenuItem("Otwórz plik konfiguracyjny (config.json)", self.open_config_file),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Zakończ", self.exit_app)
        )

        self.tray_icon = pystray.Icon(
            "DictationAI",
            create_tray_icon_image("idle"),
            "Dyktowanie Mowy AI (Windows 11 Voice Typing)",
            menu
        )

        logger.info("Aplikacja gotowa w zasobniku systemowym (obok zegara).")
        self.tray_icon.run()

if __name__ == "__main__":
    try:
        import ctypes
        try:
            h_def = ctypes.windll.user32.OpenDesktopW("Default", 0, False, 0x01FF)
            if h_def:
                ctypes.windll.user32.SetThreadDesktop(h_def)
        except Exception:
            pass
        ERROR_ALREADY_EXISTS = 183
        mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "DyktowanieAI_Whisper_SingleInstance_Mutex")
        if ctypes.windll.kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
            # Aplikacja już działa w tle! Wybudzamy i pokazujemy widżet PIL bez blokującego okna modalnego
            EVENT_NAME = "DyktowanieAI_ShowOverlay_Event"
            h_send = ctypes.windll.kernel32.OpenEventW(0x0002, False, EVENT_NAME)  # EVENT_MODIFY_STATE = 0x0002
            if h_send:
                ctypes.windll.kernel32.SetEvent(h_send)
                ctypes.windll.kernel32.CloseHandle(h_send)
            sys.exit(0)

        app = DictationApp()
        app.run_tray()
    except Exception as e:
        logger.critical("FATAL UNCAUGHT EXCEPTION in main: %s", e, exc_info=True)
        sys.exit(1)
