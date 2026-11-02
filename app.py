import time
import threading
import winsound
import subprocess
import ctypes
from ctypes import wintypes
import os
import sys
import logging
import io
import wave
import math
import re
import struct

import tempfile

def _generate_wav(samples, sr=22050):
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        frames = [struct.pack('<h', max(-32767, min(32767, int(s)))) for s in samples]
        wf.writeframes(b''.join(frames))
    return buf.getvalue()

def _make_sound_start_1():
    # Preset 1 (Bell Chime): 580Hz -> 720Hz
    sr, dur_s, vol = 22050, 0.052, 0.22
    n = int(sr * dur_s)
    samples = []
    for i in range(n):
        t = i / n
        env = (math.sin(math.pi * t) ** 1.3) * math.exp(-1.8 * t)
        f = 580.0 + 140.0 * t
        s = 0.8 * math.sin(2 * math.pi * f * i / sr) + 0.2 * math.sin(4 * math.pi * f * i / sr)
        samples.append(32767 * vol * env * s)
    return _generate_wav(samples, sr)

def _make_sound_start_2():
    # Preset 2 (Bubble Pop): 460Hz -> 860Hz
    sr, dur_s, vol = 22050, 0.034, 0.20
    n = int(sr * dur_s)
    samples = []
    for i in range(n):
        t = i / n
        env = math.sin(math.pi * t) ** 1.8
        f = 460.0 + 400.0 * (t ** 1.4)
        s = math.sin(2 * math.pi * f * i / sr)
        samples.append(32767 * vol * env * s)
    return _generate_wav(samples, sr)

def _make_sound_start_3():
    # Preset 3 (Arpeggio): C5 (523Hz) -> G5 (784Hz)
    sr, dur_s, vol = 22050, 0.065, 0.20
    n = int(sr * dur_s)
    samples = []
    mid = n // 2
    for i in range(n):
        if i < mid:
            t = i / mid
            env = math.sin(math.pi * t) ** 1.4
            f = 523.25
        else:
            t = (i - mid) / (n - mid)
            env = (math.sin(math.pi * t) ** 1.2) * math.exp(-1.2 * t)
            f = 783.99
        s = 0.85 * math.sin(2 * math.pi * f * i / sr) + 0.15 * math.sin(4 * math.pi * f * i / sr)
        samples.append(32767 * vol * env * s)
    return _generate_wav(samples, sr)

def _make_sound_start_4():
    # Preset 4 (Minimal): 940Hz
    sr, dur_s, vol = 22050, 0.019, 0.17
    n = int(sr * dur_s)
    samples = []
    for i in range(n):
        t = i / n
        env = math.exp(-6.5 * t)
        s = math.sin(2 * math.pi * 940.0 * i / sr)
        samples.append(32767 * vol * env * s)
    return _generate_wav(samples, sr)

def _make_sound_stop_1():
    # Preset 1: 480Hz -> 380Hz
    sr, dur_s, vol = 22050, 0.048, 0.20
    n = int(sr * dur_s)
    samples = []
    for i in range(n):
        t = i / n
        env = (math.sin(math.pi * t) ** 1.3) * math.exp(-1.5 * t)
        f = 480.0 - 100.0 * t
        s = 0.85 * math.sin(2 * math.pi * f * i / sr) + 0.15 * math.sin(4 * math.pi * f * i / sr)
        samples.append(32767 * vol * env * s)
    return _generate_wav(samples, sr)

def _make_sound_stop_2():
    # Preset 2: 680Hz -> 340Hz
    sr, dur_s, vol = 22050, 0.032, 0.18
    n = int(sr * dur_s)
    samples = []
    for i in range(n):
        t = i / n
        env = math.sin(math.pi * t) ** 1.8
        f = 680.0 - 340.0 * (t ** 1.2)
        s = math.sin(2 * math.pi * f * i / sr)
        samples.append(32767 * vol * env * s)
    return _generate_wav(samples, sr)

def _make_sound_stop_3():
    # Preset 3: G5 (784Hz) -> C5 (523Hz)
    sr, dur_s, vol = 22050, 0.065, 0.20
    n = int(sr * dur_s)
    samples = []
    mid = n // 2
    for i in range(n):
        if i < mid:
            t = i / mid
            env = math.sin(math.pi * t) ** 1.4
            f = 783.99
        else:
            t = (i - mid) / (n - mid)
            env = (math.sin(math.pi * t) ** 1.2) * math.exp(-1.2 * t)
            f = 523.25
        s = 0.85 * math.sin(2 * math.pi * f * i / sr) + 0.15 * math.sin(4 * math.pi * f * i / sr)
        samples.append(32767 * vol * env * s)
    return _generate_wav(samples, sr)

def _make_sound_stop_4():
    # Preset 4: 440Hz
    sr, dur_s, vol = 22050, 0.019, 0.17
    n = int(sr * dur_s)
    samples = []
    for i in range(n):
        t = i / n
        env = math.exp(-6.5 * t)
        s = math.sin(2 * math.pi * 440.0 * i / sr)
        samples.append(32767 * vol * env * s)
    return _generate_wav(samples, sr)

def _make_sound_ready():
    sr, dur_s, vol = 22050, 0.035, 0.16
    n = int(sr * dur_s)
    samples = []
    for i in range(n):
        t = i / n
        env = math.sin(math.pi * t) ** 1.5
        s = math.sin(2 * math.pi * 540.0 * i / sr)
        samples.append(32767 * vol * env * s)
    return _generate_wav(samples, sr)

def _make_sound_error():
    sr, dur_s, vol = 22050, 0.060, 0.20
    n = int(sr * dur_s)
    samples = []
    for i in range(n):
        t = i / n
        env = math.sin(math.pi * t) ** 1.3
        f = 380.0 if t < 0.5 else 320.0
        s = math.sin(2 * math.pi * f * i / sr)
        samples.append(32767 * vol * env * s)
    return _generate_wav(samples, sr)

_CHIME_FILES = {}
try:
    _temp_dir = tempfile.gettempdir()
    _generators = [
        ('start_1', _make_sound_start_1),
        ('start_2', _make_sound_start_2),
        ('start_3', _make_sound_start_3),
        ('start_4', _make_sound_start_4),
        ('stop_1', _make_sound_stop_1),
        ('stop_2', _make_sound_stop_2),
        ('stop_3', _make_sound_stop_3),
        ('stop_4', _make_sound_stop_4),
        ('ready', _make_sound_ready),
        ('error', _make_sound_error)
    ]
    for _name, _fn in _generators:
        _fpath = os.path.join(_temp_dir, f"voice_ui_chime_{_name}.wav")
        with open(_fpath, 'wb') as _f:
            _f.write(_fn())
        _CHIME_FILES[_name] = _fpath
except Exception as _e:
    logging.getLogger("App").debug(f"Błąd zapisu plików dźwiękowych: {_e}")

def _play_chime_file(name):
    p = _CHIME_FILES.get(name)
    if p and os.path.exists(p):
        try:
            winsound.PlaySound(p, winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
        except Exception:
            pass

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

try:
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Whiscribe.VoiceTyping.1.0")
except Exception:
    pass

import numpy as np
from PIL import Image, ImageDraw
import pystray
from pynput import keyboard

from config import load_config, save_config, save_secret_key, CONFIG_FILE, get_app_dir, APP_NAME, APP_VERSION, APP_RELEASE_DATE, GITHUB_URL
from recorder import AudioRecorder
from transcriber import Transcriber
from injector import inject_text, sync_text, send_unicode_string, send_enter, ForwardStreamCommitter
from overlay import FloatingOverlay, THEMES, THEME_MAP, draw_svg_mic
from focus_detector import is_text_field_focused, NON_EDITABLE_WINDOW_CLASSES, get_proc_name_from_hwnd, is_valid_target_window
from meeting_manager import MeetingManager

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetForegroundWindow.argtypes = []
user32.SetForegroundWindow.restype = wintypes.BOOL
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.IsWindow.restype = wintypes.BOOL
user32.IsWindow.argtypes = [wintypes.HWND]
user32.IsIconic.restype = wintypes.BOOL
user32.IsIconic.argtypes = [wintypes.HWND]
user32.BringWindowToTop.restype = wintypes.BOOL
user32.BringWindowToTop.argtypes = [wintypes.HWND]
user32.AttachThreadInput.restype = wintypes.BOOL
user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
try:
    user32.AllowSetForegroundWindow.restype = wintypes.BOOL
    user32.AllowSetForegroundWindow.argtypes = [wintypes.DWORD]
except Exception:
    pass

def safe_bring_to_foreground(hwnd: int) -> bool:
    """
    Bezpieczne przywrócenie okna docelowego w Windows bez animacji, migania czy zmian rozmiaru.
    """
    if not hwnd or not user32.IsWindow(hwnd):
        return False
    cur = user32.GetForegroundWindow() or 0
    if cur == hwnd:
        return True

    try:
        user32.AllowSetForegroundWindow(0xFFFFFFFF)  # ASFW_ANY
    except Exception:
        pass

    fg_thread = user32.GetWindowThreadProcessId(cur, None) if cur else 0
    target_thread = user32.GetWindowThreadProcessId(hwnd, None)
    app_thread = kernel32.GetCurrentThreadId()

    attached_fg = False
    attached_target = False

    if fg_thread and fg_thread != app_thread:
        try:
            attached_fg = user32.AttachThreadInput(app_thread, fg_thread, True)
        except Exception:
            attached_fg = False

    if target_thread and target_thread != app_thread and target_thread != fg_thread:
        try:
            attached_target = user32.AttachThreadInput(app_thread, target_thread, True)
        except Exception:
            attached_target = False

    try:
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, 9)  # SW_RESTORE (tylko i wyłącznie gdy okno było zminimalizowane do paska zadań)
        user32.SetForegroundWindow(hwnd)
        user32.BringWindowToTop(hwnd)
    finally:
        if attached_fg:
            try:
                user32.AttachThreadInput(app_thread, fg_thread, False)
            except Exception:
                pass
        if attached_target:
            try:
                user32.AttachThreadInput(app_thread, target_thread, False)
            except Exception:
                pass

    return user32.GetForegroundWindow() == hwnd

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

from logging.handlers import RotatingFileHandler
LOG_FILE = os.path.join(get_app_dir(), "app.log")
handlers = [RotatingFileHandler(LOG_FILE, maxBytes=2_000_000, backupCount=2, encoding='utf-8')]
if sys.stdout is not None:
    handlers.append(logging.StreamHandler(sys.stdout))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=handlers,
    force=True
)
logger = logging.getLogger("DictationApp")


def _log_thread_exception(args):
    if args.exc_type is SystemExit:
        return
    name = args.thread.name if args.thread else "?"
    logger.error(f"Nieobsłużony wyjątek w wątku {name}", exc_info=(args.exc_type, args.exc_value, args.exc_traceback))


threading.excepthook = _log_thread_exception

def create_tray_icon_image(state="idle", frame_idx=0, vol=0.0) -> Image.Image:
    """Tworzy obraz ikony traya w zaleznosci od stanu."""
    img_hi = Image.new('RGBA', (256, 256), color=(0, 0, 0, 0))
    d = ImageDraw.Draw(img_hi)
    navy_color = (18, 28, 58, 255)
    # Tlo ikony
    d.ellipse((10, 10, 246, 246), fill=navy_color)
    # Mikrofon wektorowy
    draw_svg_mic(img_hi, 128, 128, 124, color=(255, 255, 255, 255))

    if state == "recording":
        # Wskaznik nagrywania (czerwony)
        pulse = 0.5 + 0.5 * math.sin(frame_idx * 0.5)
        rec_r = int(22 + pulse * 8)
        d.ellipse((196 - rec_r, 60 - rec_r, 196 + rec_r, 60 + rec_r), fill=(255, 45, 65, 255))
    elif state == "meeting":
        # Wskaznik spotkania (niebieski)
        pulse = 0.5 + 0.5 * math.sin(frame_idx * 0.5)
        rec_r = int(22 + pulse * 8)
        d.ellipse((196 - rec_r, 60 - rec_r, 196 + rec_r, 60 + rec_r), fill=(99, 133, 248, 255))
    elif state == "processing":
        # Wskaznik przetwarzania (bursztynowy)
        pulse = 0.5 + 0.5 * math.sin(frame_idx * 0.5)
        rec_r = int(22 + pulse * 8)
        d.ellipse((196 - rec_r, 60 - rec_r, 196 + rec_r, 60 + rec_r), fill=(245, 158, 11, 255))

    return img_hi.resize((64, 64), Image.Resampling.LANCZOS)

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

class UniversalGlobalHotKeys(keyboard.Listener):
    """
    Globalny listener skrótów klawiszowych pynput:
    1. Obsługuje zdarzenia injected=True dla myszek (np. Logitech MX Master), makr i urządzeń wejściowych.
    2. Normalizuje klawisze modyfikatorów (alt_gr, alt_l, alt_r -> alt; ctrl_l, ctrl_r -> ctrl; shift_l, shift_r -> shift).
    """
    def __init__(self, hotkeys, *args, **kwargs):
        self._hotkeys = [
            keyboard.HotKey(keyboard.HotKey.parse(key), value) for key, value in hotkeys.items()
        ]
        super(UniversalGlobalHotKeys, self).__init__(
            on_press=self._on_press,
            on_release=self._on_release,
            *args,
            **kwargs,
        )

    def _normalize_key(self, key):
        if key in (keyboard.Key.alt_l, keyboard.Key.alt_r, keyboard.Key.alt_gr):
            return keyboard.Key.alt
        if key in (keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
            return keyboard.Key.ctrl
        if key in (keyboard.Key.shift_l, keyboard.Key.shift_r):
            return keyboard.Key.shift
        return self.canonical(key)

    def _on_press(self, key, injected=False):
        c = self._normalize_key(key)
        for hotkey in self._hotkeys:
            hotkey.press(c)

    def _on_release(self, key, injected=False):
        c = self._normalize_key(key)
        for hotkey in self._hotkeys:
            hotkey.release(c)


def is_autostart_enabled() -> bool:
    startup_dir = os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs\Startup")
    lnk = os.path.join(startup_dir, "Whiscribe.lnk")
    return os.path.exists(lnk)


def set_autostart(enable: bool) -> bool:
    startup_dir = os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs\Startup")
    lnk = os.path.join(startup_dir, "Whiscribe.lnk")
    if enable:
        if getattr(sys, 'frozen', False):
            target = sys.executable
            args = ""
            workdir = os.path.dirname(target)
            icon = f"{target},0"
        else:
            app_dir = get_app_dir()
            target = "wscript.exe"
            args = f'"{os.path.join(app_dir, "run_silent.vbs")}"'
            workdir = app_dir
            icon = f"{os.path.join(app_dir, 'icon.ico')},0"

        desc = f"Whiscribe v{APP_VERSION} - AI Voice Typing"
        ps_script = (
            "param($linkPath, $targetPath, $arguments, $workingDir, $iconLoc, $description) "
            "$sh = New-Object -ComObject WScript.Shell; "
            "$s = $sh.CreateShortcut($linkPath); "
            "$s.TargetPath = $targetPath; "
            "$s.Arguments = $arguments; "
            "$s.WorkingDirectory = $workingDir; "
            "$s.IconLocation = $iconLoc; "
            "$s.Description = $description; "
            "$s.Save()"
        )
        try:
            subprocess.run(
                ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps_script,
                 lnk, target, args, workdir, icon, desc],
                check=True, creationflags=0x08000000
            )
            return True
        except Exception as e:
            logger.error(f"Błąd włączania autostartu: {e}")
            return False
    else:
        try:
            if os.path.exists(lnk):
                os.remove(lnk)
            return True
        except Exception as e:
            logger.error(f"Błąd wyłączania autostartu: {e}")
            return False


# Maksymalna długość audio bez zakończonego segmentu w trybie streamingu (s)
STREAM_MAX_UNCOMMITTED_S = 30.0
# Po tylu sekundach bez wyniku ponowne naciśnięcie skrótu przerywa przetwarzanie
PROCESSING_ABANDON_AFTER_S = 15.0


class DictationApp:
    # pystray nie jest bezpieczny wątkowo: dwa równoległe przypisania ikony zwalniają ten sam
    # uchwyt (DestroyIcon) i drugie rzuca OSError. Wszystkie zmiany ikony idą przez ten lock.
    _tray_icon_lock = threading.Lock()
    def __init__(self):
        self.config = load_config()
        self.recorder = AudioRecorder(sample_rate=16000)
        self._last_toggle_time = 0.0
        self._last_meeting_toggle_time = 0.0
        theme = self.config.get("theme", "dark")
        self.overlay = FloatingOverlay(theme=theme, always_on_top=self.config.get("always_on_top", True)) if self.config.get("show_overlay", True) else None
        if self.overlay:
            self.overlay.show_live_preview = self.config.get("show_live_preview", False)
            self.overlay.stream_realtime = self.config.get("stream_realtime", False)
            self.overlay.ai_enabled = self.config.get("use_llm", False)
            self.overlay.set_widget_mode(self.config.get("widget_mode", "dictation"))
        
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
                on_meeting_toggle=self.toggle_meeting,
                on_minimize=self.minimize_to_tray,
                on_restore=self._on_overlay_restored,
                on_hotkey=self._on_system_hotkey,
                on_stream_toggle=self.toggle_streaming_mode,
                on_ai_toggle=self.toggle_gemini_correction
            )
            self.overlay.set_settings_handler(self._show_settings_menu)
            self.overlay.show()
            self.overlay.show_idle()

        # Krótki, łagodny dźwięk gotowości
        self._play_ready_chime()
        
        self.state = "idle"  # "idle", "recording", "processing"
        self._is_minimized_to_tray = False
        self._lock = threading.RLock()
        self._type_lock = threading.RLock()
        self._stream_stop_event = threading.Event()
        self._streaming_thread = None
        # Numer sesji streamingu: wątek z poprzedniego nagrania kończy się, gdy ruszy nowe
        self._stream_session = 0
        # Numer bieżącego zadania finalizacji. Zadanie porzucone (watchdog, ponowny skrót, X)
        # nie wkleja już tekstu i nie zmienia stanu aplikacji, nawet jeśli skończy się później.
        self._job_seq = 0
        self._processing_started = 0.0
        self._processing_deadline = 0.0
        self._recording_start_time = 0.0
        self.committed_text = ""
        self.committed_sample_offset = 0
        self.committer = ForwardStreamCommitter(type_callback=self._type_stream_chunk)

        self.target_hwnd = None
        self.target_proc = ""
        self.buffered_untyped_text = ""
        self.last_active_hwnd = 0

        self._orig_lock_timeout = None
        try:
            old_timeout = wintypes.DWORD()
            if user32.SystemParametersInfoW(0x2000, 0, ctypes.byref(old_timeout), 0):
                self._orig_lock_timeout = old_timeout.value
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

        # Wątek animacji ikony w pasku zadań (Windows 11 System Tray)
        self._tray_anim_thread = threading.Thread(target=self._tray_anim_worker, daemon=True)
        self._tray_anim_thread.start()

    @property
    def is_minimized_to_tray(self) -> bool:
        if self.overlay:
            return self.overlay.is_minimized()
        return getattr(self, '_is_minimized_to_tray', False)

    @is_minimized_to_tray.setter
    def is_minimized_to_tray(self, val: bool):
        self._is_minimized_to_tray = bool(val)

    def _on_overlay_restored(self):
        self._is_minimized_to_tray = False

    def _llm_active(self) -> bool:
        """Czy korekta AI jest realnie dostępna (podany klucz API lub skonfigurowany silnik lokalny)."""
        if not self.config.get("use_llm", False):
            return False
        provider = self.config.get("llm_provider", "gemini").lower()
        if provider in ("ollama", "local", "lmstudio"):
            return True
        return bool(self.config.get("llm_api_key", "").strip())

    def _preview_only_mode(self) -> bool:
        """
        Tryb podglądu (streaming + korekta AI jednocześnie):
        - transkrypcja na żywo trafia WYŁĄCZNIE do panelu widżetu,
        - do okna docelowego wpisujemy raz, dopiero po korekcie całej wypowiedzi.
        Dzięki temu nie trzeba cofać ani podmieniać tekstu już wpisanego w cudzym oknie.
        """
        return bool(self.config.get("stream_realtime", False)) and self._llm_active()

    def _type_stream_chunk(self, chunk: str):
        """Wpisuje słowa w przód (Forward-only) z ciągłym streamingiem bezpośrednio do aktywnego pola."""
        if not chunk:
            return

        # Tryb podglądu: na żywo nie wpisujemy nic do okna docelowego.
        # Tekst pojawia się tylko w widżecie, a po zakończeniu wklejamy skorygowaną całość.
        if getattr(self, "_preview_mode_active", False):
            return

        with self._type_lock:
            cur_fg = user32.GetForegroundWindow() or 0
            overlay_hwnd = self.overlay.hwnd if self.overlay else 0

            # Zabezpieczenie przed pisaniem do obcego okna podczas przełączania okien (Alt+Tab, kliknięcie poza target)
            # oraz przed pisaniem w ułamku sekundy, gdy użytkownik trzyma wciśnięty przycisk myszy (drag suwaka/scroll, zaznaczanie tekstu)
            target_inactive = bool(self.target_hwnd and user32.IsWindow(self.target_hwnd) and cur_fg != self.target_hwnd and cur_fg != overlay_hwnd)
            mouse_busy = is_mouse_down()

            if target_inactive or mouse_busy:
                self.buffered_untyped_text += chunk
                return

            if self.buffered_untyped_text:
                to_send = self.buffered_untyped_text + chunk
                self.buffered_untyped_text = ""
                send_unicode_string(to_send)
            else:
                send_unicode_string(chunk)

    def _set_tray_icon(self, state: str, expect_state: str = None, **kwargs):
        """Zmienia ikonę w zasobniku; błąd pystray nigdy nie przerywa wywołującego."""
        if not self.tray_icon:
            return
        with self._tray_icon_lock:
            # Klatka animacji nie może nadpisać ikony stanu, który już się zmienił
            if expect_state is not None and self.state != expect_state:
                return
            try:
                self.tray_icon.icon = create_tray_icon_image(state, **kwargs)
            except Exception as e:
                logger.debug(f"Nie udało się zmienić ikony w zasobniku ({state}): {e}")

    def _tray_anim_worker(self):
        """Animuje ikonę w pasku menu/zadań (obszarze powiadomień) podczas nagrywania lub spotkania."""
        frame = 0
        while self._running:
            if self.tray_icon and self.state in ("recording", "meeting_recording", "processing"):
                try:
                    vol = self.recorder.get_volume_level() if self.state == "recording" else (
                        self.meeting_manager.recorder.get_total_volume() if hasattr(self, "meeting_manager") and self.meeting_manager else 0.0
                    )
                except Exception:
                    vol = 0.0
                cur_state = self.state
                st = "recording" if cur_state == "recording" else ("meeting" if cur_state == "meeting_recording" else "processing")
                self._set_tray_icon(st, expect_state=cur_state, frame_idx=frame, vol=vol)
                frame += 1
                time.sleep(0.08)
            else:
                time.sleep(0.18)

    def minimize_to_taskbar(self):
        """Minimalizuje widżet (chowa go z ekranu do zasobnika systemowego)."""
        self.is_minimized_to_tray = True
        if self.overlay:
            self.overlay.minimize()
        logger.info("Widżet pomyślnie zminimalizowany do zasobnika systemowego.")

    def restore_from_taskbar(self):
        """Przywraca widżet z dolnego paska zadań na ekran."""
        self.is_minimized_to_tray = False
        if self.overlay:
            self.overlay.restore()
            if self.state == "recording":
                self.overlay.show_recording()
            elif self.state == "meeting_recording":
                self.overlay.show_meeting_recording()
            elif self.state == "processing":
                self.overlay.show_processing()
            else:
                self.overlay.show_idle()
        logger.info("Widżet przywrócony z dolnego paska zadań na ekran.")

    def toggle_overlay_visibility(self):
        if not self.overlay:
            return
        if self.overlay.is_minimized():
            self.restore_from_taskbar()
        else:
            self.minimize_to_taskbar()

    minimize_to_tray = minimize_to_taskbar
    restore_from_tray = restore_from_taskbar

    def _listen_for_show_event(self):
        """Nasłuchuje sygnałów IPC z kolejnych wywołań aplikacji (np. skrót na pulpicie, przycisk myszy)."""
        EVENT_SHOW = r"Local\Whiscribe_ShowOverlay_Event"
        EVENT_TOGGLE = r"Local\Whiscribe_Toggle_Event"
        # Ochrona obiektów IPC DACL-em ograniczonym do właściciela sesji
        sa_ptr = None
        p_sd = ctypes.c_void_p()
        try:
            class SECURITY_ATTRIBUTES(ctypes.Structure):
                _fields_ = [
                    ("nLength", wintypes.DWORD),
                    ("lpSecurityDescriptor", ctypes.c_void_p),
                    ("bInheritHandle", wintypes.BOOL)
                ]
            if ctypes.windll.advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW("D:(A;;GA;;;OW)", 1, ctypes.byref(p_sd), None):
                sa = SECURITY_ATTRIBUTES()
                sa.nLength = ctypes.sizeof(SECURITY_ATTRIBUTES)
                sa.lpSecurityDescriptor = p_sd
                sa.bInheritHandle = False
                sa_ptr = ctypes.byref(sa)
        except Exception:
            pass

        h_show = ctypes.windll.kernel32.CreateEventW(sa_ptr, False, False, EVENT_SHOW)
        h_toggle = ctypes.windll.kernel32.CreateEventW(sa_ptr, False, False, EVENT_TOGGLE)
        while self._running:
            res_t = ctypes.windll.kernel32.WaitForSingleObject(h_toggle, 200)
            if res_t == 0:
                logger.info("Odebrano sygnał IPC przełączenia dyktowania (--toggle).")
                _play_chime_file('start_1')
                self.toggle_dictation()
            res_s = ctypes.windll.kernel32.WaitForSingleObject(h_show, 200)
            if res_s == 0:
                logger.info("Odebrano sygnał wybudzenia/pokazania widżetu.")
                self.restore_from_tray()
                self._play_ready_chime()
        if h_show:
            ctypes.windll.kernel32.CloseHandle(h_show)
        if h_toggle:
            ctypes.windll.kernel32.CloseHandle(h_toggle)
        if p_sd and p_sd.value:
            try:
                ctypes.windll.kernel32.LocalFree(p_sd)
            except Exception:
                pass

    def _play_start_chime(self):
        """Dźwięk rozpoczęcia wpisywania głosowego wg wybranego presetu."""
        if self.config.get("sound_feedback", True):
            p = int(self.config.get("sound_start_preset", 1))
            if p > 0:
                _play_chime_file(f'start_{p}')

    def _play_stop_chime(self):
        """Dźwięk zakończenia wpisywania głosowego wg wybranego presetu."""
        if self.config.get("sound_feedback", True):
            p = int(self.config.get("sound_stop_preset", 1))
            if p > 0:
                _play_chime_file(f'stop_{p}')

    def set_sound_start_preset(self, preset_idx: int):
        self.config["sound_start_preset"] = preset_idx
        save_config(self.config)
        logger.info(f"Ustawiono preset dźwięku startu: {preset_idx}")
        if preset_idx > 0 and self.config.get("sound_feedback", True):
            _play_chime_file(f"start_{preset_idx}")

    def set_sound_stop_preset(self, preset_idx: int):
        self.config["sound_stop_preset"] = preset_idx
        save_config(self.config)
        logger.info(f"Ustawiono preset dźwięku stopu: {preset_idx}")
        if preset_idx > 0 and self.config.get("sound_feedback", True):
            _play_chime_file(f"stop_{preset_idx}")

    def _play_error_chime(self):
        """Dźwięk błędu przy braku aktywnego pola tekstowego."""
        if self.config.get("sound_feedback", True):
            _play_chime_file('error')

    def _play_ready_chime(self):
        """Sygnał dźwiękowy gotowości."""
        if self.config.get("sound_feedback", True):
            _play_chime_file('ready')

    def _play_beep(self, freq=None, duration=None):
        self._play_ready_chime()

    def start_recording(self):
        # Weryfikacja aktywnego okna docelowego
        cur_fg = user32.GetForegroundWindow() or 0
        overlay_hwnd = self.overlay.hwnd if self.overlay else 0

        target_hwnd = None
        if is_valid_target_window(cur_fg, overlay_hwnd):
            target_hwnd = cur_fg
        elif hasattr(self, 'last_active_hwnd') and self.last_active_hwnd and is_valid_target_window(self.last_active_hwnd, overlay_hwnd):
            target_hwnd = self.last_active_hwnd

        # Jeśli target_hwnd istnieje, ale w momencie kliknięcia w widżet fokus został utracony (cur_fg != target_hwnd):
        # przywróć fokus do okna docelowego PRZED weryfikacją pola tekstowego, aby kursor i kontrolka były aktywne!
        if target_hwnd and cur_fg != target_hwnd:
            safe_bring_to_foreground(target_hwnd)
            time.sleep(0.04)

        if self.config.get("require_text_field", True):
            is_focused, reason = is_text_field_focused(target_hwnd)
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
        self.target_hwnd = target_hwnd if target_hwnd else (user32.GetForegroundWindow() or 0)
        if self.target_hwnd:
            self.last_active_hwnd = self.target_hwnd
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
            if self.overlay.is_minimized():
                self.restore_from_taskbar()
            else:
                self.overlay.show()
                self.overlay.show_recording()
        if self.tray_icon:
            self._set_tray_icon("recording")

        self._play_start_chime()

        # Tryb pracy ustalamy raz na całą sesję nagrywania, żeby przełączenie opcji
        # w trakcie dyktowania nie rozdzieliło zachowania na pół wypowiedzi.
        self._preview_mode_active = self._preview_only_mode()

        # Jeśli streaming na żywo jest włączony, uruchom wątek transkrypcji w czasie rzeczywistym
        if self.config.get("stream_realtime", False):
            if self._preview_mode_active:
                logger.info("Tryb podglądu (streaming + korekta AI): tekst trafi do okna raz, po korekcie całości.")
            self._stream_session += 1
            self._streaming_thread = threading.Thread(target=self._streaming_worker, args=(self._stream_session,), daemon=True)
            self._streaming_thread.start()

    def _streaming_worker(self, session: int = 0):
        """
        Wątek inteligentnego streamingu na żywo (styl Windows 11 Voice Typing):
        - Wyłącznie wpisywanie w przód (Forward-Only).
        - Zakończone segmenty są definitywnie zatwierdzane i przesuwają wskaźnik audio.
        - Trwające wypowiedzi zatwierdzają ustabilizowane słowa w przód.
        - Audio i transkrypcja Whisper działają nieprzerwanie, nawet gdy użytkownik przegląda Chrome lub inne okna!
        """
        def _active():
            return (session == self._stream_session and not self._stream_stop_event.is_set()
                    and self.state == "recording")

        while _active():
            time.sleep(0.32)
            if not _active():
                break

            # Opróżnij bufor zgromadzony podczas przełączenia okien lub przeciągania myszą, gdy fokus powrócił do okna docelowego
            # (w trybie podglądu nic nie wpisujemy na żywo, więc bufor pozostaje pusty)
            if self.buffered_untyped_text and not getattr(self, "_preview_mode_active", False) and not is_mouse_down():
                cur_fg = user32.GetForegroundWindow() or 0
                if self.target_hwnd and cur_fg == self.target_hwnd:
                    with self._type_lock:
                        if self.buffered_untyped_text and not is_mouse_down():
                            send_unicode_string(self.buffered_untyped_text)
                            self.buffered_untyped_text = ""

            # Pobieramy wyłącznie dźwięk od ostatniego zatwierdzonego segmentu
            # (bez sklejania całego nagrania od początku przy każdym kroku)
            uncommitted_audio = self.recorder.get_current_audio(self.committed_sample_offset)
            if uncommitted_audio is None or len(uncommitted_audio) < 16000 * 0.40:
                continue

            # Transkrypcja aktywnego fragmentu bez przerywania
            completed, tail_text = self.transcriber.transcribe_stream_chunk(uncommitted_audio)

            if not _active():
                break

            # Bufor bez zatwierdzonego segmentu nie może rosnąć bez końca: każdy krok
            # transkrybowałby coraz dłuższe audio, a finalizacja czekałaby na zwolnienie GPU.
            if not completed and len(uncommitted_audio) >= int(STREAM_MAX_UNCOMMITTED_S * 16000):
                forced = tail_text
                if not forced and not getattr(self, "_preview_mode_active", False):
                    forced = self.transcriber.transcribe(uncommitted_audio)
                    if not _active():
                        break
                unc_s = len(uncommitted_audio) / 16000.0
                logger.info(f"Streaming: {unc_s:.0f}s audio bez zakończonego segmentu – wymuszone zatwierdzenie.")
                tail_text = ""
                if forced:
                    completed = [(forced, unc_s)]
                else:
                    self.committed_sample_offset += len(uncommitted_audio)
                    continue

            # 1. ZATWIERDŹ ZAKOŃCZONE SEGMENTY (COMMIT) - NA ZAWSZE W DOKUMENCIE
            if completed:
                with self._type_lock:
                    for seg_text, _ in completed:
                        self.committer.commit_segment(seg_text)
                        if self.overlay:
                            self.overlay.add_transcript_entry(seg_text)
                    self.committed_sample_offset += int(completed[-1][1] * 16000)

            # 2. ZAKTUALIZUJ BIEŻĄCY OGON (STABILNE SŁOWA WPISYWANE W PRZÓD)
            if tail_text:
                with self._type_lock:
                    self.committer.process_hypothesis(tail_text)
                if self.overlay:
                    self.overlay.update_live_text(tail_text)

    def stop_and_transcribe(self):
        with self._lock:
            if self.state != "recording":
                if self.overlay and self.overlay.mode != "idle":
                    self.overlay.show_idle()
                return
            self.state = "processing"
            self._job_seq += 1
            job = self._job_seq
            self._processing_started = time.time()
            # Wstępny limit na samo zatrzymanie nagrania; po pobraniu audio zostaje wydłużony
            self._processing_deadline = self._processing_started + 30.0

        try:
            self._begin_finalization(job)
        except Exception as e:
            # Bez tego wyjątek (np. z ikony w zasobniku) zostawiał stan "processing" na zawsze
            logger.error(f"Błąd przy zatrzymywaniu nagrywania: {e}", exc_info=True)
            try:
                self.recorder.stop()
            except Exception:
                pass
            self._abandon_processing("błąd przy zatrzymywaniu nagrywania")

    def _begin_finalization(self, job: int):
        logger.info("Zatrzymano nagrywanie, finalizowanie...")
        self._stream_stop_event.set()
        try:
            self._play_stop_chime()
        except Exception as e:
            logger.debug(f"Dźwięk stopu nie zadziałał: {e}")

        if self.overlay:
            self.overlay.show_processing()
        self._set_tray_icon("processing")

        # Bezpieczne odczekanie na zakończenie bieżącego kroku streamingu GPU
        if self._streaming_thread and self._streaming_thread.is_alive():
            self._streaming_thread.join(timeout=0.4)

        # Pobierz pełne nagranie
        audio_data = self.recorder.stop()

        # Limit czasu całej finalizacji: Whisper (proporcjonalnie do długości nagrania)
        # + maksymalny budżet korekty AI + zapas. Po nim watchdog wraca do stanu gotowości.
        audio_s = len(audio_data) / 16000.0 if audio_data is not None else 0.0
        llm_budget = 0.0
        if self._llm_active():
            is_local = self.config.get("llm_provider", "gemini").lower() in ("ollama", "local", "lmstudio")
            llm_budget = 90.0 if is_local else 45.0
        with self._lock:
            if job == self._job_seq:
                self._processing_deadline = time.time() + 60.0 + audio_s * 0.5 + llm_budget

        # Uruchom finalizację w osobnym wątku
        threading.Thread(target=self._process_audio_worker, args=(audio_data, job), daemon=True).start()

    def _is_current_job(self, job) -> bool:
        return job is None or job == self._job_seq

    def _abandon_processing(self, reason: str) -> bool:
        """
        Porzuca zawieszoną finalizację i wraca do stanu gotowości.
        Wątek finalizacji może dalej pracować, ale jego wynik trafi już tylko do widżetu.
        """
        with self._lock:
            if self.state != "processing":
                return False
            self._job_seq += 1
            self.state = "idle"
            elapsed = time.time() - self._processing_started
            self._processing_deadline = 0.0
        logger.warning(f"Przerwano przetwarzanie po {elapsed:.0f}s ({reason}). Aplikacja wraca do gotowości.")
        self._stream_stop_event.set()
        self.committed_text = ""
        self.committed_sample_offset = 0
        self.buffered_untyped_text = ""
        if self.tray_icon:
            self._set_tray_icon("idle")
        if self.overlay:
            self.overlay.show_idle()
            self.overlay.show_balloon("info", "Przetwarzanie przerwane — jeśli tekst dojdzie później, będzie w widżecie")
        return True

    def _process_audio_worker(self, audio_data, job=None):
        try:
            t0 = time.time()

            # Tryb podglądu (streaming + korekta AI) finalizuje się jak tryb wsadowy:
            # pełna transkrypcja całego nagrania -> korekta AI -> jedno wklejenie.
            preview_mode = getattr(self, "_preview_mode_active", False)

            if self.config.get("stream_realtime", False) and not preview_mode:
                # Tryb streamingu:
                remaining_audio = audio_data[self.committed_sample_offset:] if len(audio_data) > self.committed_sample_offset else None
                final_tail = ""
                if remaining_audio is not None and len(remaining_audio) >= 16000 * 0.35:
                    trimmed_rem = AudioRecorder.trim_silence(remaining_audio, sample_rate=16000, keep_lead_s=0.20, keep_tail_s=0.35)
                    if len(trimmed_rem) >= 16000 * 0.25:
                        final_tail = self.transcriber.transcribe(trimmed_rem)

                if not self._is_current_job(job):
                    logger.warning("Streaming: finalizacja porzucona – końcówka trafia tylko do widżetu.")
                    if final_tail and self.overlay:
                        self.overlay.add_transcript_entry(final_tail)
                    return

                # 1. Przywróć definitywnie fokus do okna docelowego PRZED wpisaniem końcówki i opróżnieniem bufora
                focus_ok = True
                if hasattr(self, 'target_hwnd') and self.target_hwnd and user32.IsWindow(self.target_hwnd):
                    cur_fg = user32.GetForegroundWindow()
                    if cur_fg != self.target_hwnd:
                        logger.info(f"Przywracanie fokusu do okna docelowego przed wpisaniem (HWND={self.target_hwnd:#x})")
                        safe_bring_to_foreground(self.target_hwnd)
                        for _ in range(15):
                            if user32.GetForegroundWindow() == self.target_hwnd:
                                break
                            time.sleep(0.02)
                    focus_ok = (user32.GetForegroundWindow() == self.target_hwnd)

                if focus_ok:
                    # Opróżnij zaległy bufor jeśli cokolwiek zostało podczas przełączania okien
                    with self._type_lock:
                        if self.buffered_untyped_text:
                            send_unicode_string(self.buffered_untyped_text)
                            self.buffered_untyped_text = ""

                        if final_tail:
                            self.committer.finalize(final_tail)
                            if self.overlay:
                                self.overlay.add_transcript_entry(final_tail)
                        else:
                            self.committer.finalize()

                        # Upewnij się, że ogon (final_tail) lub jakiekolwiek zaległe znaki po finalize też zostały wpisane
                        if self.buffered_untyped_text:
                            send_unicode_string(self.buffered_untyped_text)
                            self.buffered_untyped_text = ""

                    self._send_auto_enter()
                else:
                    logger.warning(f"Streaming: nie udało się przywrócić fokusu do okna docelowego. Wstrzymano wpisywanie.")
                    if final_tail and self.overlay:
                        self.overlay.add_transcript_entry(final_tail)
                    if self.overlay:
                        self.overlay.show_balloon("info", "Fokus okna utracony — końcówka tekstu zachowana w widżecie")

                logger.info(f"Finalizacja streamingu: {time.time() - t0:.2f}s | Wpisano znaków: {len(self.committer.typed_text)}")
                logger.debug(f"Streaming wpisany tekst: '{self.committer.typed_text.strip()}'")

            else:
                # Transkrypcja batch po zatrzymaniu nagrywania
                final_text = self.transcriber.transcribe(audio_data)
                duration = time.time() - t0
                logger.info(f"Finalny czas: {duration:.2f}s | Długość tekstu: {len(final_text)} znaków")
                logger.debug(f"Tekst transkrypcji: '{final_text}'")

                if not self._is_current_job(job):
                    # Użytkownik lub watchdog przerwał oczekiwanie – mógł już dyktować do innego okna,
                    # więc nie wklejamy, tylko zostawiamy tekst w widżecie.
                    logger.warning(f"Spóźniony wynik po {duration:.0f}s – nie wklejam, tekst zostaje w widżecie.")
                    if final_text and self.overlay:
                        self.overlay.add_transcript_entry(final_text)
                        self.overlay.show_balloon("info", "Spóźniony tekst jest w widżecie (nie wklejono)")
                    return

                # Jeśli korekta była oczekiwana, ale się nie udała, użytkownik musi o tym wiedzieć –
                # inaczej dostaje surowy tekst Whispera i nie ma pojęcia, że AI nie zadziałało.
                llm_status = getattr(self.transcriber, "last_llm_status", None)
                if self._llm_active() and llm_status in ("failed", "rejected") and self.overlay:
                    powod = ("model odrzucił wynik korekty" if llm_status == "rejected"
                             else "silnik AI niedostępny")
                    logger.warning(f"Korekta AI nieudana ({powod}) – wklejono surową transkrypcję.")
                    self.overlay.show_balloon("info", f"Korekta AI nieudana ({powod}) — tekst surowy")

                if final_text:
                    if self.overlay:
                        # W trybie podglądu surowe wiersze z nasłuchu zastępujemy skorygowaną całością,
                        # żeby w panelu nie zostały dwie wersje tego samego tekstu.
                        if preview_mode:
                            self.overlay.clear_transcript()
                        self.overlay.add_transcript_entry(final_text)

                    # Przywrocenie fokusu do okna docelowego przed wklejeniem
                    focus_ok = True
                    if hasattr(self, 'target_hwnd') and self.target_hwnd and user32.IsWindow(self.target_hwnd):
                        cur_fg = user32.GetForegroundWindow()
                        if cur_fg != self.target_hwnd:
                            logger.info(f"Przywracanie fokusu do okna docelowego przed wklejeniem (HWND={self.target_hwnd:#x})")
                            safe_bring_to_foreground(self.target_hwnd)
                            for _ in range(15):
                                if user32.GetForegroundWindow() == self.target_hwnd:
                                    break
                                time.sleep(0.02)
                        focus_ok = (user32.GetForegroundWindow() == self.target_hwnd)

                    if focus_ok:
                        inject_text(final_text, restore_clipboard=self.config.get("restore_clipboard", True))
                        self._send_auto_enter()
                    else:
                        logger.warning(f"Nie udało się przywrócić fokusu do okna docelowego (HWND={self.target_hwnd:#x}, aktywne={user32.GetForegroundWindow():#x}). Wstrzymano wklejanie dla ochrony danych.")
                        if self.overlay:
                            self.overlay.show_balloon("info", "Fokus okna utracony — tekst zachowano w widżecie")

        except Exception as e:
            logger.error(f"Błąd podczas finalizacji: {e}", exc_info=True)
        finally:
            with self._lock:
                if not self._is_current_job(job):
                    # Zadanie porzucone: stan należy już do nowej sesji
                    return
                self.state = "idle"
                self._processing_deadline = 0.0
            self.committed_text = ""
            self.committed_sample_offset = 0
            self.buffered_untyped_text = ""
            if self.tray_icon:
                self._set_tray_icon("idle")
            if self.overlay:
                self.overlay.show_idle()
                if self.config.get("always_on_top", True) and getattr(self.overlay, "hwnd", None):
                    try:
                        user32.SetWindowPos(self.overlay.hwnd, -1, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010)
                    except Exception:
                        pass

    def toggle_dictation(self):
        """Obsługa naciśnięcia klawisza/przycisku myszy w trybie Toggle."""
        now = time.time()
        if now - self._last_toggle_time < 0.35:
            return
        self._last_toggle_time = now

        if self.state == "idle":
            self.start_recording()
        elif self.state == "recording":
            self.stop_and_transcribe()
        elif self.state == "processing":
            elapsed = now - self._processing_started
            if elapsed >= PROCESSING_ABANDON_AFTER_S:
                self._abandon_processing("ponowne naciśnięcie skrótu")
            else:
                logger.info(f"Skrót w trakcie przetwarzania ({elapsed:.0f}s) – czekam na wynik.")
                if self.overlay:
                    self.overlay.show_balloon("info", "Trwa przetwarzanie… (po 15 s skrót je przerwie)")
        elif self.state == "meeting_recording":
            logger.info("Zatrzymywanie spotkania przed przełączeniem do trybu dyktowania...")
            self.stop_meeting()

    def cancel_dictation(self):
        """Anuluje nagrywanie (albo trwające przetwarzanie) bez wprowadzania tekstu."""
        if self.state == "processing":
            self._abandon_processing("anulowano z widżetu")
            return
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
            self.overlay.clear_transcript()
            self.overlay.show_idle()
        if self.tray_icon:
            self._set_tray_icon("idle")
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
            time.sleep(0.1)
            if self.state == "idle":
                cur_fg = user32.GetForegroundWindow() or 0
                overlay_hwnd = self.overlay.hwnd if self.overlay else 0
                if is_valid_target_window(cur_fg, overlay_hwnd):
                    self.last_active_hwnd = cur_fg

            # Watchdog: finalizacja nie może trwać w nieskończoność
            if self.state == "processing" and self._processing_deadline and time.time() > self._processing_deadline:
                self._abandon_processing("przekroczony limit czasu przetwarzania")
                continue

            # Twardy limit jednego dyktowania (np. zapomniane nagrywanie przy szumie w tle)
            try:
                max_rec_sec = float(self.config.get("max_recording_seconds", 1200) or 0)
            except (TypeError, ValueError):
                max_rec_sec = 0.0
            if max_rec_sec > 0 and self.state == "recording" and time.time() - self._recording_start_time >= max_rec_sec:
                logger.warning(f"Nagranie osiągnęło limit {max_rec_sec / 60:.0f} min – automatyczne zatrzymanie.")
                if self.overlay:
                    self.overlay.show_balloon("info", f"Limit {max_rec_sec / 60:.0f} min nagrania – zatrzymano")
                self.stop_and_transcribe()
                continue

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
            if self.overlay.is_minimized():
                self.restore_from_taskbar()
            else:
                self.overlay.show()
                self.overlay.show_meeting_recording()
        if self.tray_icon:
            self._set_tray_icon("meeting")

        self._play_start_chime()

        def _on_meeting_utterance(speaker, text, dt):
            if self.overlay and text:
                t_sec = (dt - self.meeting_manager.start_dt).total_seconds() if self.meeting_manager.start_dt else 0
                self.overlay.add_transcript_entry(f"{speaker}: {text}", timestamp_s=t_sec)

        try:
            self.meeting_manager.start_meeting(on_utterance=_on_meeting_utterance)
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
            self._set_tray_icon("processing")
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
                    self._set_tray_icon("idle")
                if self.overlay:
                    self.overlay.show_idle()
                logger.info("Aplikacja pomyślnie powróciła do stanu gotowości (idle).")

        threading.Thread(target=_finalize_worker, daemon=True).start()

    def toggle_meeting(self):
        """Przełącznik trybu spotkania (z poziomu skrótu Ctrl+Alt+M lub przycisku na widżecie)."""
        now = time.time()
        if now - self._last_meeting_toggle_time < 0.35:
            return
        self._last_meeting_toggle_time = now

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
            raw_folder = self.config.get("meetings_folder", "transkrypcje")
            folder = raw_folder if os.path.isabs(raw_folder) else os.path.join(get_app_dir(), raw_folder)
            os.makedirs(folder, exist_ok=True)
            os.startfile(folder)
        except Exception as e:
            logger.error(f"Błąd otwierania folderu transkrypcji: {e}")

    def _on_system_hotkey(self, hotkey_id: int):
        """Obsługa zdarzenia WM_HOTKEY z natywnego Win32 RegisterHotKey (np. z myszki MX Master / klawiatury)."""
        logger.info(f"Odebrano natywne zdarzenie Win32 WM_HOTKEY: id={hotkey_id}")
        if hotkey_id == 101:
            self.toggle_dictation()
        elif hotkey_id == 102:
            self.toggle_meeting()

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

        # 1. Rejestracja w natywnym Win32 RegisterHotKey
        # Działa na poziomie jądra Windows – przechwytuje zdarzenia fizyczne oraz wysyłane przez Logi Options+ (MX Master)
        if self.overlay and self.overlay.hwnd:
            res_d = self.overlay.register_system_hotkey(101, raw_hotkey)
            res_m = self.overlay.register_system_hotkey(102, raw_meeting)
            logger.info(f"Win32 RegisterHotKey: Dyktowanie({raw_hotkey})={'Aktywny' if res_d else 'Pominięty/Zajęty'}, Spotkanie({raw_meeting})={'Aktywny' if res_m else 'Pominięty/Zajęty'}")

        def _async_toggle_dictation():
            threading.Thread(target=self.toggle_dictation, daemon=True).start()

        def _async_toggle_meeting():
            threading.Thread(target=self.toggle_meeting, daemon=True).start()

        hotkey_map = {
            formatted: _async_toggle_dictation,
            formatted_meeting: _async_toggle_meeting
        }

        # 2. Rejestracja w UniversalGlobalHotKeys (fallback + wsparcie zdarzeń wstrzykiwanych injected=True z myszy)
        try:
            self.hotkey_listener = UniversalGlobalHotKeys(hotkey_map)
            self.hotkey_listener.start()
            logger.info("UniversalGlobalHotKeys uruchomiony pomyślnie (obsługa klawiatury fizycznej oraz myszy MX Master / Logi Options+)!")
        except Exception as e:
            logger.error(f"Nie udało się zarejestrować UniversalGlobalHotKeys: {e}")

    def toggle_sound_feedback(self):
        self.config["sound_feedback"] = not self.config.get("sound_feedback", True)
        save_config(self.config)
        logger.info(f"Dźwięki powiadomień: {'Włączone' if self.config['sound_feedback'] else 'Wyłączone'}")

    def _send_auto_enter(self):
        """Zatwierdza wklejony tekst Enterem, jeśli użytkownik włączył taką opcję."""
        if not self.config.get("auto_enter_after_dictation", False):
            return
        try:
            # Krótka przerwa, bo aplikacja docelowa (czat, przeglądarka) potrzebuje chwili
            # na przyjęcie wklejonego tekstu – Enter wysłany za wcześnie wysyła puste pole.
            time.sleep(0.15)
            send_enter()
            logger.info("Auto-Enter: zatwierdzono wpisany tekst.")
        except Exception as e:
            logger.warning(f"Auto-Enter nie zadziałał: {e}")

    def toggle_auto_enter(self):
        self.config["auto_enter_after_dictation"] = not self.config.get("auto_enter_after_dictation", False)
        save_config(self.config)
        logger.info(f"Enter po dyktowaniu: {'Włączony' if self.config['auto_enter_after_dictation'] else 'Wyłączony'}")
        if self.overlay:
            stan = "włączony" if self.config["auto_enter_after_dictation"] else "wyłączony"
            self.overlay.show_balloon("info", f"Enter po zakończeniu dyktowania: {stan}")

    def toggle_require_text_field(self):
        self.config["require_text_field"] = not self.config.get("require_text_field", True)
        save_config(self.config)
        logger.info(f"Wymóg pola tekstowego: {'Włączony' if self.config['require_text_field'] else 'Wyłączony'}")

    def set_widget_mode(self, mode: str):
        """Co robi główny przycisk widżetu: dyktowanie do tekstu albo transkrypcja rozmowy."""
        mode = "meeting" if mode == "meeting" else "dictation"
        self.config["widget_mode"] = mode
        save_config(self.config)
        if self.overlay:
            self.overlay.set_widget_mode(mode)
        logger.info(f"Tryb przycisku widżetu: {'transkrypcja rozmowy' if mode == 'meeting' else 'dyktowanie do tekstu'}")

    def toggle_streaming_mode(self):
        new_val = not self.config.get("stream_realtime", False)
        self.config["stream_realtime"] = new_val

        # Streaming i korekta AI mogą być włączone jednocześnie — wchodzą wtedy w tryb podglądu:
        # transkrypcja leci na żywo do widżetu, a do okna docelowego trafia raz skorygowana całość.
        # Bez dymka: stan widać na przyciskach widżetu.
        if new_val and self._llm_active():
            logger.info("Streaming włączony przy aktywnej korekcie AI - tryb podglądu w widżecie.")

        save_config(self.config)
        if self.overlay:
            self.overlay.stream_realtime = self.config["stream_realtime"]
            self.overlay._dirty = True
        logger.info(f"Pisanie na żywo: {'Włączone' if self.config['stream_realtime'] else 'Wyłączone'}")

    def toggle_always_on_top(self):
        self.config["always_on_top"] = not self.config.get("always_on_top", True)
        save_config(self.config)
        if self.overlay:
            self.overlay.set_always_on_top(self.config["always_on_top"])
            if self.config["always_on_top"]:
                self.is_minimized_to_tray = False
                self.overlay.show()
                self.overlay.show_idle()
        logger.info(f"Zawsze na wierzchu: {'Włączone' if self.config['always_on_top'] else 'Wyłączone'}")

    def toggle_restore_clipboard(self, icon=None, item=None):
        self.config["restore_clipboard"] = not self.config.get("restore_clipboard", True)
        save_config(self.config)
        logger.info(f"Czyszczenie schowka (ochrona prywatności): {'Włączone' if self.config['restore_clipboard'] else 'Wyłączone'}")

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
            try:
                self.overlay.close()
            except Exception:
                pass
        if self.tray_icon:
            try:
                self.tray_icon.stop()
            except Exception:
                pass
        if getattr(self, '_orig_lock_timeout', None) is not None:
            try:
                user32.SystemParametersInfoW(0x2001, 0, ctypes.c_void_p(self._orig_lock_timeout), 2)
            except Exception:
                pass
        logging.shutdown()
        time.sleep(0.05)
        os._exit(0)

    def _show_settings_menu(self, screen_x, screen_y):
        """Wyświetla pełne menu kontekstowe Whiscribe w warstwie Zawsze na wierzchu."""
        logger.info(f"Otwieranie menu kontekstowego na pozycji ({screen_x}, {screen_y})")
        if getattr(self, '_menu_open', False):
            logger.info("Menu jest już otwarte, pomijanie podwójnego kliknięcia.")
            return
        self._menu_open = True
        if self.overlay:
            self.overlay.is_menu_open = True
        try:
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32

            screen_w = user32.GetSystemMetrics(0)
            screen_h = user32.GetSystemMetrics(1)
            if not screen_x or not screen_y or screen_x <= 0 or screen_y <= 0:
                pt = wintypes.POINT()
                user32.GetCursorPos(ctypes.byref(pt))
                screen_x, screen_y = pt.x, pt.y

            # Wyrównanie: jeśli widżet jest w dolnej połowie ekranu, otwórz menu w górę (TPM_BOTTOMALIGN)
            # Jeśli kliknięto z prawej strony (przycisk •••), rozwiń w lewo (TPM_RIGHTALIGN)
            align_v = 0x0020 if screen_y > (screen_h // 2) else 0x0000  # TPM_BOTTOMALIGN vs TPM_TOPALIGN
            align_h = 0x0008  # TPM_RIGHTALIGN
            flags = align_h | align_v | 0x0100  # TPM_RETURNCMD

            h_menu = user32.CreatePopupMenu()
            h_theme_sub = user32.CreatePopupMenu()
            h_sound_sub = user32.CreatePopupMenu()
            h_sound_start_sub = user32.CreatePopupMenu()
            h_sound_stop_sub = user32.CreatePopupMenu()
            h_silence_sub = user32.CreatePopupMenu()
            h_ai_sub = user32.CreatePopupMenu()

            MF_STRING = 0x0000
            MF_SEPARATOR = 0x0800
            MF_POPUP = 0x0010
            MF_CHECKED = 0x0008
            MF_UNCHECKED = 0x0000

            # 0. Tryb głównego przycisku widżetu
            MF_RADIOCHECK = 0x0200
            cur_mode = self.config.get("widget_mode", "dictation")
            for m_key, m_label, m_id in (("dictation", "Dyktowanie do tekstu (mikrofon)", 111),
                                         ("meeting", "Transkrypcja rozmowy (spotkanie)", 112)):
                chk = (MF_CHECKED | MF_RADIOCHECK) if cur_mode == m_key else MF_UNCHECKED
                user32.AppendMenuW(h_menu, MF_STRING | chk, m_id, m_label)
            user32.AppendMenuW(h_menu, MF_SEPARATOR, 0, "")

            # 1. Podmenu: Styl widżetu
            cur_theme = THEME_MAP.get(self.config.get("theme", "dark"), "dark")
            themes = [
                ("dark", "Ciemny (podstawowy)", 301),
                ("apple", "Apple (macOS)", 302),
                ("win11", "Windows 11 (Fluent)", 303),
                ("google", "Google (Material)", 304),
                ("graphite", "Grafit (OLED + bursztyn)", 305),
            ]
            for t_key, t_label, t_id in themes:
                chk = MF_CHECKED if cur_theme == t_key else MF_UNCHECKED
                user32.AppendMenuW(h_theme_sub, MF_STRING | chk, t_id, t_label)
            user32.AppendMenuW(h_menu, MF_POPUP, h_theme_sub, "Styl widżetu")

            # 2. Podmenu: Dźwięki i powiadomienia
            sound_enabled = self.config.get("sound_feedback", True)
            chk_sound = MF_CHECKED if sound_enabled else MF_UNCHECKED
            user32.AppendMenuW(h_sound_sub, MF_STRING | chk_sound, 501, "Włącz dźwięki potwierdzenia")
            user32.AppendMenuW(h_sound_sub, MF_SEPARATOR, 0, "")

            cur_start = int(self.config.get("sound_start_preset", 1))
            start_presets = [
                (1, "1. Dzwonek Soft (Chime)", 511),
                (2, "2. Bąbelek Win 11 (Bubble)", 512),
                (3, "3. Arpeggio Wznoszące (Harmonia)", 513),
                (4, "4. Cyber Minimal Klik", 514),
                (0, "Brak dźwięku startu", 510),
            ]
            for p_id, p_label, cmd_id in start_presets:
                chk = MF_CHECKED if cur_start == p_id else MF_UNCHECKED
                user32.AppendMenuW(h_sound_start_sub, MF_STRING | chk, cmd_id, p_label)
            user32.AppendMenuW(h_sound_sub, MF_POPUP, h_sound_start_sub, "Dźwięk włączenia (Start)")

            cur_stop = int(self.config.get("sound_stop_preset", 1))
            stop_presets = [
                (1, "1. Dzwonek Wyłączenia (Chime Low)", 521),
                (2, "2. Bąbelek Opadający (Bubble Low)", 522),
                (3, "3. Arpeggio Opadające (Harmonia)", 523),
                (4, "4. Cyber Minimal Tik", 524),
                (0, "Brak dźwięku wyłączenia", 520),
            ]
            for p_id, p_label, cmd_id in stop_presets:
                chk = MF_CHECKED if cur_stop == p_id else MF_UNCHECKED
                user32.AppendMenuW(h_sound_stop_sub, MF_STRING | chk, cmd_id, p_label)
            user32.AppendMenuW(h_sound_sub, MF_POPUP, h_sound_stop_sub, "Dźwięk wyłączenia (Stop)")
            user32.AppendMenuW(h_menu, MF_POPUP, h_sound_sub, "Dźwięki i powiadomienia")

            # 3. Podmenu: Automatyczne zatrzymanie ciszy
            cur_silence = float(self.config.get("auto_stop_silence_seconds", 4.5))
            silence_opts = [
                (3.0, "3.0 sekundy (Krótka pauza)", 201),
                (4.5, "4.5 sekundy (Zalecane)", 202),
                (6.0, "6.0 sekund (Spokojne)", 203),
                (10.0, "10 sekund (Długa pauza)", 204),
                (0.0, "Wyłączone (Tylko ręcznie)", 205),
            ]
            for s_val, s_label, s_id in silence_opts:
                chk = MF_CHECKED if cur_silence == s_val else MF_UNCHECKED
                user32.AppendMenuW(h_silence_sub, MF_STRING | chk, s_id, s_label)
            user32.AppendMenuW(h_menu, MF_POPUP, h_silence_sub, "Automatyczne zatrzymanie ciszy")

            # 4. Podmenu: Korekta AI (LLM: Gemini / Groq / OpenAI / Ollama / LM Studio)
            cur_provider = self.config.get("llm_provider", "gemini").lower()
            prov_names = {
                "gemini": "Google Gemini",
                "ollama": "Ollama (Lokalne)",
                "local": "LM Studio (Lokalne)",
                "groq": "Groq Cloud",
                "openai": "OpenAI"
            }
            active_prov_name = prov_names.get(cur_provider, cur_provider.upper())

            use_ai = self.config.get("use_llm", False)
            chk_ai = MF_CHECKED if use_ai else MF_UNCHECKED
            user32.AppendMenuW(h_ai_sub, MF_STRING | chk_ai, 701, f"Włącz korektę AI ({active_prov_name})")
            user32.AppendMenuW(h_ai_sub, MF_SEPARATOR, 0, "")

            providers = [
                ("gemini", "Google Gemini", 710),
                ("ollama", "Ollama (Lokalne / 100% Offline)", 711),
                ("local", "LM Studio (Lokalne / 100% Offline)", 712),
                ("groq", "Groq Cloud (Llama 3.3)", 713),
                ("openai", "OpenAI (GPT-4o-mini)", 714),
            ]
            for p_code, p_name, p_id in providers:
                chk = MF_CHECKED if cur_provider == p_code else MF_UNCHECKED
                user32.AppendMenuW(h_ai_sub, MF_STRING | chk, p_id, p_name)

            user32.AppendMenuW(h_ai_sub, MF_SEPARATOR, 0, "")
            user32.AppendMenuW(h_ai_sub, MF_STRING, 702, "Klucz API chmury (Gemini / Groq / OpenAI)...")
            user32.AppendMenuW(h_ai_sub, MF_STRING, 704, "Adres serwera lokalnego (Ollama / LM Studio)...")
            user32.AppendMenuW(h_ai_sub, MF_SEPARATOR, 0, "")

            is_local = cur_provider in ("ollama", "local", "lmstudio")
            if is_local:
                ep = self.config.get("llm_endpoint", "http://localhost:11434/v1")
                key_label = f"Status: Serwer lokalny ({ep})"
            else:
                has_key = bool(self.config.get("llm_api_key", "").strip())
                key_label = "Status: Klucz API skonfigurowany" if has_key else "Status: Brak klucza API"
            user32.AppendMenuW(h_ai_sub, MF_STRING | 0x0002, 703, key_label)
            user32.AppendMenuW(h_menu, MF_POPUP, h_ai_sub, f"Korekta AI ({active_prov_name})")

            user32.AppendMenuW(h_menu, MF_SEPARATOR, 0, "")

            # 4. Główne opcje wpisywania i zachowania okna
            chk_stream = MF_CHECKED if self.config.get("stream_realtime", False) else MF_UNCHECKED
            user32.AppendMenuW(h_menu, MF_STRING | chk_stream, 101, "Pisanie na żywo (Streaming)")

            chk_topmost = MF_CHECKED if self.config.get("always_on_top", True) else MF_UNCHECKED
            user32.AppendMenuW(h_menu, MF_STRING | chk_topmost, 103, "Zawsze na wierzchu")

            chk_field = MF_CHECKED if self.config.get("require_text_field", True) else MF_UNCHECKED
            user32.AppendMenuW(h_menu, MF_STRING | chk_field, 102, "Wymagaj aktywnego pola tekstowego")

            chk_clip = MF_CHECKED if self.config.get("restore_clipboard", True) else MF_UNCHECKED
            user32.AppendMenuW(h_menu, MF_STRING | chk_clip, 107, "Czyść schowek po wklejeniu")

            chk_enter = MF_CHECKED if self.config.get("auto_enter_after_dictation", False) else MF_UNCHECKED
            user32.AppendMenuW(h_menu, MF_STRING | chk_enter, 108, "Zatwierdź Enterem po zakończeniu dyktowania")

            chk_autostart = MF_CHECKED if is_autostart_enabled() else MF_UNCHECKED
            user32.AppendMenuW(h_menu, MF_STRING | chk_autostart, 106, "Uruchamiaj z systemem Windows (Autostart)")

            user32.AppendMenuW(h_menu, MF_SEPARATOR, 0, "")

            # 5. Spotkania (start/stop głównym przyciskiem w trybie "Transkrypcja rozmowy" albo skrótem)
            user32.AppendMenuW(h_menu, MF_STRING, 105, "Otwórz folder transkrypcji spotkań")

            # 6. Zarządzanie oknem / Aplikacją
            user32.AppendMenuW(h_menu, MF_STRING, 601, "Zminimalizuj widżet (do paska)")
            user32.AppendMenuW(h_menu, MF_STRING, 402, "Zamknij aplikację")

            user32.AppendMenuW(h_menu, MF_SEPARATOR, 0, "")

            # 7. Repozytorium GitHub i Informacje o programie (pod zamknięciem aplikacji)
            user32.AppendMenuW(h_menu, MF_STRING, 801, "Projekt na GitHubie (sooony/Whiscribe)")
            user32.AppendMenuW(h_menu, MF_STRING, 802, f"O programie (v{APP_VERSION} z {APP_RELEASE_DATE})...")

            # Host window z WS_EX_TOPMOST (0x0008) i WS_EX_TOOLWINDOW (0x0080)
            WS_EX_TOPMOST = 0x00000008
            WS_EX_TOOLWINDOW = 0x00000080
            hwnd_owner = user32.CreateWindowExW(
                WS_EX_TOPMOST | WS_EX_TOOLWINDOW,
                "STATIC", "WhiscribeMenuHost",
                0x80000000,  # WS_POPUP
                int(screen_x), int(screen_y), 0, 0,
                0, None, kernel32.GetModuleHandleW(None), None
            )
            try:
                user32.SetWindowPos(hwnd_owner, -1, 0, 0, 0, 0, 0x0001 | 0x0002)  # HWND_TOPMOST, SWP_NOSIZE | SWP_NOMOVE
                user32.SetForegroundWindow(hwnd_owner)
                user32.TrackPopupMenuEx.restype = wintypes.UINT
                user32.TrackPopupMenuEx.argtypes = [
                    wintypes.HMENU,
                    wintypes.UINT,
                    ctypes.c_int,
                    ctypes.c_int,
                    wintypes.HWND,
                    ctypes.c_void_p
                ]
                cmd = user32.TrackPopupMenuEx(h_menu, flags, int(screen_x), int(screen_y), hwnd_owner, None)
                user32.PostMessageW(hwnd_owner, 0, 0, 0)
            finally:
                user32.DestroyWindow(hwnd_owner)
                user32.DestroyMenu(h_menu)

            if cmd == 101:
                self.toggle_streaming_mode()
            elif cmd == 102:
                self.toggle_require_text_field()
            elif cmd == 103:
                self.toggle_always_on_top()
            elif cmd == 104:
                self.toggle_meeting()
            elif cmd == 111:
                self.set_widget_mode("dictation")
            elif cmd == 112:
                self.set_widget_mode("meeting")
            elif cmd == 105:
                self.open_transcripts_folder()
            elif cmd == 106:
                self.toggle_autostart()
            elif cmd == 107:
                self.toggle_restore_clipboard()
            elif cmd == 108:
                self.toggle_auto_enter()
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
                self.config["auto_stop_silence_seconds"] = 0.0
                save_config(self.config)
            elif cmd in (301, 302, 303, 304, 305):
                t_map = {301: "dark", 302: "apple", 303: "win11", 304: "google", 305: "graphite"}
                t_choice = t_map.get(cmd, "dark")
                self.config["theme"] = t_choice
                save_config(self.config)
                if self.overlay:
                    self.overlay.set_theme(t_choice)
            elif cmd == 501:
                self.toggle_sound_feedback()
            elif cmd in (511, 512, 513, 514, 510):
                p_map = {511: 1, 512: 2, 513: 3, 514: 4, 510: 0}
                self.set_sound_start_preset(p_map[cmd])
            elif cmd in (521, 522, 523, 524, 520):
                p_map = {521: 1, 522: 2, 523: 3, 524: 4, 520: 0}
                self.set_sound_stop_preset(p_map[cmd])
            elif cmd == 701:
                self.toggle_llm_correction()
            elif cmd == 702:
                self.prompt_and_set_llm_api_key()
            elif cmd == 704:
                self.prompt_and_set_local_endpoint()
            elif cmd == 710:
                self.set_llm_provider("gemini")
            elif cmd == 711:
                self.set_llm_provider("ollama")
            elif cmd == 712:
                self.set_llm_provider("local")
            elif cmd == 713:
                self.set_llm_provider("groq")
            elif cmd == 714:
                self.set_llm_provider("openai")
            elif cmd == 801:
                self.open_github_repo()
            elif cmd == 802:
                self.show_about_dialog()
            elif cmd == 601:
                self.minimize_to_taskbar()
            elif cmd == 402:
                self.exit_app()
        finally:
            self._menu_open = False
            if self.overlay:
                self.overlay.is_menu_open = False

    def _on_overlay_theme_changed(self, new_theme):
        self.config["theme"] = new_theme
        save_config(self.config)
        logger.info(f"Zmieniono motyw graficzny na: {new_theme}")

    def set_llm_provider(self, provider: str):
        """Ustawia dostawcę korekty LLM (gemini, groq, openai, ollama, local)."""
        provider = provider.lower()
        self.config["llm_provider"] = provider
        if provider == "gemini":
            if not self.config.get("llm_model") or "llama" in self.config.get("llm_model", ""):
                self.config["llm_model"] = "gemini-flash-lite-latest"
        elif provider == "ollama":
            if not self.config.get("llm_model") or "gemini" in self.config.get("llm_model", ""):
                self.config["llm_model"] = "llama3.2"
        elif provider == "local":
            if not self.config.get("llm_model") or "gemini" in self.config.get("llm_model", ""):
                self.config["llm_model"] = "local-model"
        elif provider == "groq":
            if not self.config.get("llm_model") or "gemini" in self.config.get("llm_model", ""):
                self.config["llm_model"] = "llama-3.3-70b-versatile"
        elif provider == "openai":
            if not self.config.get("llm_model") or "gemini" in self.config.get("llm_model", ""):
                self.config["llm_model"] = "gpt-4o-mini"

        save_config(self.config)
        if hasattr(self, "transcriber") and self.transcriber:
            self.transcriber.config = self.config

        prov_labels = {
            "gemini": "Google Gemini",
            "ollama": "Ollama (Lokalne)",
            "local": "LM Studio (Lokalne)",
            "groq": "Groq Cloud",
            "openai": "OpenAI"
        }
        name = prov_labels.get(provider, provider)
        logger.info(f"Zmieniono silnik korekty AI na: {name}")

    def toggle_llm_correction(self):
        """Włącza lub wyłącza korektę AI bez nadpisywania skonfigurowanego dostawcy."""
        curr = self.config.get("use_llm", False)
        if not curr:
            provider = self.config.get("llm_provider", "gemini").lower()
            is_local = provider in ("ollama", "local", "lmstudio")
            api_key = self.config.get("llm_api_key", "").strip()

            if not is_local and not api_key:
                self.prompt_and_set_llm_api_key()
                return

            self.config["use_llm"] = True

            # Przy włączonym streamingu wchodzimy w tryb podglądu: na żywo widzisz tekst
            # w widżecie, a do okna docelowego wklejamy raz skorygowaną całość.
            if self.config.get("stream_realtime", False):
                logger.info("Korekta AI włączona przy aktywnym streamingu - tryb podglądu w widżecie.")
        else:
            self.config["use_llm"] = False

        save_config(self.config)
        if hasattr(self, "transcriber") and self.transcriber:
            self.transcriber.config = self.config
        if self.overlay:
            self.overlay.ai_enabled = self.config["use_llm"]
            self.overlay._dirty = True

        prov_name = {"gemini": "Gemini", "ollama": "Ollama", "local": "LM Studio", "groq": "Groq", "openai": "OpenAI"}.get(self.config.get("llm_provider", "gemini").lower(), "AI")
        state_str = "włączona" if self.config["use_llm"] else "wyłączona"
        logger.info(f"Korekta językowa ({prov_name}): {state_str}")

    toggle_gemini_correction = toggle_llm_correction

    def prompt_and_set_llm_api_key(self):
        """Wyświetla okno wprowadzania klucza API dla bieżącego dostawcy chmurowego."""
        def _dialog():
            try:
                import tkinter as tk
                from tkinter import simpledialog
                root = tk.Tk()
                root.withdraw()
                root.attributes("-topmost", True)
                curr_prov = self.config.get("llm_provider", "gemini").lower()
                prov_name = {"gemini": "Google Gemini", "groq": "Groq", "openai": "OpenAI"}.get(curr_prov, curr_prov.upper())
                has_key = bool(self.config.get("llm_api_key", "").strip())
                # Pole zawsze puste: wklejony klucz nie dokleja się do starego, a klucz nie jest pokazywany
                new_key = simpledialog.askstring(
                    f"Klucz API — {prov_name}",
                    f"Wklej klucz API dla {prov_name}"
                    + (" (puste pole = bez zmian):" if has_key else ":"),
                    parent=root
                )
                root.destroy()
                cleaned = (new_key or "").strip()
                if not cleaned:
                    return
                # Klucze Gemini: nowe z AI Studio "AQ.…", starsze "AIza…" (39 znaków).
                # Odrzuca np. przypadkowo skopiowane ID projektu "gen-lang-client-…".
                if curr_prov == "gemini" and not re.fullmatch(r"AIza[0-9A-Za-z_-]{35}|AQ\.[0-9A-Za-z_.-]{20,}", cleaned):
                    logger.warning(f"Odrzucono klucz Gemini o niepoprawnym formacie (długość {len(cleaned)}).")
                    if self.overlay:
                        self.overlay.show_balloon("info", "To nie jest klucz Gemini (zaczyna się od AQ. albo AIza) – nie zapisano")
                    return

                self.config["llm_api_key"] = cleaned
                self.config["use_llm"] = True
                # Klucz z okienka zawsze trafia wprost do secrets.json. Wcześniej przy kluczu
                # wczytanym z secrets.json save_config() go nie zapisywał, więc nowy klucz żył
                # tylko w pamięci, a po restarcie wracał stary.
                save_secret_key(cleaned)
                self.config["_llm_key_source"] = "secrets_file"
                save_config(self.config)
                if hasattr(self, "transcriber") and self.transcriber:
                    self.transcriber.config = self.config
                if self.overlay:
                    self.overlay.ai_enabled = True
                    self.overlay._dirty = True
                msg = f"Klucz API {prov_name} zapisany!"
                logger.info(msg)
                if self.overlay:
                    self.overlay.show_balloon("info", msg)
            except Exception as e:
                logger.error(f"Błąd okna wprowadzania klucza API: {e}", exc_info=True)

        threading.Thread(target=_dialog, daemon=True).start()

    prompt_and_set_gemini_api_key = prompt_and_set_llm_api_key

    def prompt_and_set_local_endpoint(self):
        """Wyświetla okno do konfiguracji adresu lokalnego serwera API (Ollama/LM Studio)."""
        def _dialog():
            try:
                import tkinter as tk
                from tkinter import simpledialog
                root = tk.Tk()
                root.withdraw()
                root.attributes("-topmost", True)
                curr_ep = self.config.get("llm_endpoint", "http://localhost:11434/v1")
                new_ep = simpledialog.askstring(
                    "Adres serwera lokalnego LLM",
                    "Wprowadź adres URL API (np. http://localhost:11434/v1 dla Ollama lub http://localhost:1234/v1 dla LM Studio):",
                    initialvalue=curr_ep,
                    parent=root
                )
                root.destroy()
                if new_ep is not None and new_ep.strip():
                    self.config["llm_endpoint"] = new_ep.strip()
                    save_config(self.config)
                    if hasattr(self, "transcriber") and self.transcriber:
                        self.transcriber.config = self.config
                    msg = f"Zapisano adres serwera: {self.config['llm_endpoint']}"
                    logger.info(msg)
                    if self.overlay:
                        self.overlay.show_balloon("info", msg)
            except Exception as e:
                logger.error(f"Błąd okna konfiguracji adresu lokalnego LLM: {e}")

        threading.Thread(target=_dialog, daemon=True).start()

    def toggle_autostart(self):
        curr = is_autostart_enabled()
        set_autostart(not curr)
        logger.info(f"Autostart Windows: {'Wyłączony' if curr else 'Włączony'}")

    def open_github_repo(self):
        """Otwiera repozytorium Whiscribe na GitHubie w domyślnej przeglądarce."""
        import webbrowser
        try:
            webbrowser.open(GITHUB_URL)
            logger.info(f"Otwarto stronę projektu GitHub: {GITHUB_URL}")
        except Exception as e:
            logger.error(f"Błąd otwierania linku GitHub: {e}")

    def show_about_dialog(self):
        """Wyświetla okno dialogowe z informacjami o wersji, dacie wydania i linkiem do repozytorium GitHub."""
        def _dialog():
            try:
                import tkinter as tk
                from tkinter import messagebox
                root = tk.Tk()
                root.withdraw()
                root.attributes("-topmost", True)
                about_text = (
                    f"Whiscribe — Dyktowanie i Transkrypcja Mowy dla Windows 11\n\n"
                    f"• Wersja: v{APP_VERSION}\n"
                    f"• Data wydania: {APP_RELEASE_DATE}\n"
                    f"• Silnik mowy: OpenAI Whisper (large-v3-turbo / float16 na GPU CUDA)\n"
                    f"• Korekta językowa: Gemini Flash / LLM\n"
                    f"• Skróty: Dyktowanie (Ctrl+Alt+D), Spotkanie (Ctrl+Alt+M)\n"
                    f"• Repozytorium: {GITHUB_URL}\n\n"
                    f"Czy chcesz otworzyć repozytorium projektu na GitHubie w przeglądarce?"
                )
                res = messagebox.askyesno(
                    f"O programie — {APP_NAME} v{APP_VERSION}",
                    about_text,
                    parent=root
                )
                root.destroy()
                if res:
                    self.open_github_repo()
            except Exception as e:
                logger.error(f"Błąd okna dialogowego O programie: {e}")
                msg = f"Whiscribe v{APP_VERSION} ({APP_RELEASE_DATE})\n\nGitHub: {GITHUB_URL}"
                user32.MessageBoxW(0, msg, f"O programie {APP_NAME}", 0x00000040 | 0x00040000)

        threading.Thread(target=_dialog, daemon=True).start()

    def run_tray(self):
        self.setup_hotkey()

        def set_theme_action(t_key):
            def handler(icon=None, item=None):
                self.config["theme"] = t_key
                save_config(self.config)
                if self.overlay:
                    self.overlay.set_theme(t_key)
            return handler

        def theme_checked(t_key):
            return lambda item: THEME_MAP.get(self.config.get("theme", "dark"), "dark") == t_key

        theme_items = [
            pystray.MenuItem(THEMES[t_key]["name"], set_theme_action(t_key), checked=theme_checked(t_key))
            for t_key in ("dark", "apple", "win11", "google", "graphite")
        ]
        theme_menu = pystray.Menu(*theme_items)

        def set_sound_start_action(p):
            def handler(icon=None, item=None):
                self.set_sound_start_preset(p)
            return handler

        def set_sound_stop_action(p):
            def handler(icon=None, item=None):
                self.set_sound_stop_preset(p)
            return handler

        sound_start_menu = pystray.Menu(
            pystray.MenuItem("1. Dzwonek Soft (Chime)", set_sound_start_action(1), checked=lambda item: int(self.config.get("sound_start_preset", 1)) == 1),
            pystray.MenuItem("2. Bąbelek Win 11 (Bubble)", set_sound_start_action(2), checked=lambda item: int(self.config.get("sound_start_preset", 1)) == 2),
            pystray.MenuItem("3. Arpeggio Wznoszące", set_sound_start_action(3), checked=lambda item: int(self.config.get("sound_start_preset", 1)) == 3),
            pystray.MenuItem("4. Cyber Minimal Klik", set_sound_start_action(4), checked=lambda item: int(self.config.get("sound_start_preset", 1)) == 4),
            pystray.MenuItem("Brak dźwięku startu", set_sound_start_action(0), checked=lambda item: int(self.config.get("sound_start_preset", 1)) == 0),
        )

        sound_stop_menu = pystray.Menu(
            pystray.MenuItem("1. Dzwonek Wyłączenia", set_sound_stop_action(1), checked=lambda item: int(self.config.get("sound_stop_preset", 1)) == 1),
            pystray.MenuItem("2. Bąbelek Opadający", set_sound_stop_action(2), checked=lambda item: int(self.config.get("sound_stop_preset", 1)) == 2),
            pystray.MenuItem("3. Arpeggio Opadające", set_sound_stop_action(3), checked=lambda item: int(self.config.get("sound_stop_preset", 1)) == 3),
            pystray.MenuItem("4. Cyber Minimal Tik", set_sound_stop_action(4), checked=lambda item: int(self.config.get("sound_stop_preset", 1)) == 4),
            pystray.MenuItem("Brak dźwięku wyłączenia", set_sound_stop_action(0), checked=lambda item: int(self.config.get("sound_stop_preset", 1)) == 0),
        )

        sound_menu = pystray.Menu(
            pystray.MenuItem("Włącz dźwięki potwierdzenia", lambda icon=None, item=None: self.toggle_sound_feedback(), checked=lambda item: self.config.get("sound_feedback", True)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Dźwięk włączenia (Start)", sound_start_menu),
            pystray.MenuItem("Dźwięk wyłączenia (Stop)", sound_stop_menu),
        )

        silence_menu = pystray.Menu(
            pystray.MenuItem("3.0 sekundy (Krótka pauza)", self.set_silence_timeout(3.0), checked=lambda item: float(self.config.get("auto_stop_silence_seconds", 4.5)) == 3.0),
            pystray.MenuItem("4.5 sekundy (Zalecane)", self.set_silence_timeout(4.5), checked=lambda item: float(self.config.get("auto_stop_silence_seconds", 4.5)) == 4.5),
            pystray.MenuItem("6.0 sekund (Spokojne)", self.set_silence_timeout(6.0), checked=lambda item: float(self.config.get("auto_stop_silence_seconds", 4.5)) == 6.0),
            pystray.MenuItem("10 sekund (Długa pauza)", self.set_silence_timeout(10.0), checked=lambda item: float(self.config.get("auto_stop_silence_seconds", 4.5)) == 10.0),
            pystray.MenuItem("Wyłączone (tylko ręcznie)", self.set_silence_timeout(0.0), checked=lambda item: float(self.config.get("auto_stop_silence_seconds", 4.5)) == 0.0)
        )

        def set_provider_action(p):
            def handler(icon=None, item=None):
                self.set_llm_provider(p)
            return handler

        provider_sub = pystray.Menu(
            pystray.MenuItem("Google Gemini", set_provider_action("gemini"), checked=lambda item: self.config.get("llm_provider", "gemini").lower() == "gemini"),
            pystray.MenuItem("Ollama (Lokalne / 100% Offline)", set_provider_action("ollama"), checked=lambda item: self.config.get("llm_provider", "gemini").lower() == "ollama"),
            pystray.MenuItem("LM Studio (Lokalne / 100% Offline)", set_provider_action("local"), checked=lambda item: self.config.get("llm_provider", "gemini").lower() == "local"),
            pystray.MenuItem("Groq Cloud (Llama 3.3)", set_provider_action("groq"), checked=lambda item: self.config.get("llm_provider", "gemini").lower() == "groq"),
            pystray.MenuItem("OpenAI (ChatGPT)", set_provider_action("openai"), checked=lambda item: self.config.get("llm_provider", "gemini").lower() == "openai"),
        )

        ai_menu = pystray.Menu(
            pystray.MenuItem(
                lambda item: f"Włącz korektę AI ({self.config.get('llm_provider', 'gemini').upper()})",
                lambda icon=None, item=None: self.toggle_llm_correction(),
                checked=lambda item: self.config.get("use_llm", False)
            ),
            pystray.MenuItem("Wybór silnika AI", provider_sub),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Klucz API chmury (Gemini / Groq / OpenAI)...", lambda icon=None, item=None: self.prompt_and_set_llm_api_key()),
            pystray.MenuItem("Adres serwera lokalnego (Ollama / LM Studio)...", lambda icon=None, item=None: self.prompt_and_set_local_endpoint()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                lambda item: f"Status: Serwer lokalny ({self.config.get('llm_endpoint', '')})" if self.config.get("llm_provider", "").lower() in ("ollama", "local", "lmstudio") else ("Status: Klucz API skonfigurowany" if self.config.get("llm_api_key", "").strip() else "Status: Brak klucza API"),
                None,
                enabled=False
            )
        )

        def toggle_vis_action(icon=None, item=None):
            self.toggle_overlay_visibility()

        menu = pystray.Menu(
            pystray.MenuItem(f"Whiscribe v{APP_VERSION} (Whisper AI Voice)", None, enabled=False),
            pystray.MenuItem(f"Dyktowanie: {self.config.get('hotkey', 'Ctrl+Alt+D')}", None, enabled=False),
            pystray.MenuItem(f"Spotkanie: {self.config.get('hotkey_meeting', 'Ctrl+Alt+M')}", None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Pokaż / Zminimalizuj widżet",
                toggle_vis_action,
                default=True,
                checked=lambda item: (not self.overlay.is_minimized()) if self.overlay else False
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Transkrypcja spotkań",
                self.toggle_meeting,
                checked=lambda item: self.state == "meeting_recording"
            ),
            pystray.MenuItem("Otwórz folder z transkrypcjami spotkań", self.open_transcripts_folder),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Korekta AI (LLM)", ai_menu),
            pystray.MenuItem("Styl widżetu", theme_menu),
            pystray.MenuItem("Dźwięki i powiadomienia", sound_menu),
            pystray.MenuItem("Automatyczne zatrzymanie ciszy", silence_menu),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Pisanie na żywo (Streaming)",
                self.toggle_streaming_mode,
                checked=lambda item: self.config.get("stream_realtime", False)
            ),
            pystray.MenuItem(
                "Zawsze na wierzchu",
                lambda icon=None, item=None: self.toggle_always_on_top(),
                checked=lambda item: self.config.get("always_on_top", True)
            ),
            pystray.MenuItem(
                "Wymagaj aktywnego pola tekstowego",
                self.toggle_require_text_field,
                checked=lambda item: self.config.get("require_text_field", True)
            ),
            pystray.MenuItem(
                "Zatwierdź Enterem po zakończeniu dyktowania",
                lambda icon=None, item=None: self.toggle_auto_enter(),
                checked=lambda item: self.config.get("auto_enter_after_dictation", False)
            ),
            pystray.MenuItem(
                "Czyść schowek po wklejeniu",
                lambda icon=None, item=None: self.toggle_restore_clipboard(),
                checked=lambda item: self.config.get("restore_clipboard", True)
            ),
            pystray.MenuItem(
                "Uruchamiaj z systemem Windows (Autostart)",
                lambda icon=None, item=None: self.toggle_autostart(),
                checked=lambda item: is_autostart_enabled()
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Zakończ Whiscribe", self.exit_app),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Projekt na GitHubie", lambda icon=None, item=None: self.open_github_repo()),
            pystray.MenuItem(f"O programie (v{APP_VERSION} z {APP_RELEASE_DATE})...", lambda icon=None, item=None: self.show_about_dialog())
        )

        self.tray_icon = pystray.Icon(
            "Whiscribe",
            create_tray_icon_image("idle"),
            f"Whiscribe v{APP_VERSION} (AI Voice Typing)",
            menu
        )

        logger.info(f"Aplikacja Whiscribe v{APP_VERSION} gotowa w zasobniku systemowym (obok zegara).")
        try:
            self.tray_icon.run()
        except OSError as e:
            if getattr(e, 'winerror', None) == 1401 or "1401" in str(e):
                logger.info("Pomyślnie zwolniono zasoby paska zadań podczas wyłączania.")
            else:
                raise

if __name__ == "__main__":
    try:
        import ctypes
        try:
            h_def = ctypes.windll.user32.OpenDesktopW("Default", 0, False, 0x01FF)
            if h_def:
                ctypes.windll.user32.SetThreadDesktop(h_def)
        except Exception:
            pass
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(f"Whiscribe.VoiceTyping.{APP_VERSION}")
        except Exception:
            pass

        is_toggle_req = "--toggle" in sys.argv
        ERROR_ALREADY_EXISTS = 183
        mutex = ctypes.windll.kernel32.CreateMutexW(None, False, r"Local\Whiscribe_SingleInstance_Mutex")
        if ctypes.windll.kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
            if is_toggle_req:
                EVENT_NAME = r"Local\Whiscribe_Toggle_Event"
                h_send = ctypes.windll.kernel32.OpenEventW(0x0002, False, EVENT_NAME)
                if h_send:
                    ctypes.windll.kernel32.SetEvent(h_send)
                    ctypes.windll.kernel32.CloseHandle(h_send)
                sys.exit(0)
            else:
                # Zapytaj użytkownika czy chce zrestartować Whiscribe z nowo otwartej lokalizacji
                MB_YESNO = 0x00000004
                MB_ICONQUESTION = 0x00000020
                MB_TOPMOST = 0x00040000
                IDYES = 6
                msg = (
                    "Aplikacja Whiscribe jest już uruchomiona w tle na tym komputerze.\n\n"
                    "Czy chcesz zamknąć poprzednio działającą instancję i uruchomić tę wersję?"
                )
                res = ctypes.windll.user32.MessageBoxW(0, msg, "Whiscribe AI", MB_YESNO | MB_ICONQUESTION | MB_TOPMOST)
                if res == IDYES:
                    my_pid = os.getpid()
                    try:
                        import subprocess
                        ps_cmd = f"Get-Process -Name 'Whiscribe' -ErrorAction SilentlyContinue | Where-Object {{ $_.Id -ne {my_pid} }} | Stop-Process -Force"
                        subprocess.run(
                            ["powershell", "-NoProfile", "-Command", ps_cmd],
                            creationflags=0x08000000
                        )
                        time.sleep(0.5)
                    except Exception:
                        pass
                    if mutex:
                        try:
                            ctypes.windll.kernel32.CloseHandle(mutex)
                        except Exception:
                            pass
                    mutex = ctypes.windll.kernel32.CreateMutexW(None, False, r"Local\Whiscribe_SingleInstance_Mutex")
                else:
                    EVENT_NAME = r"Local\Whiscribe_ShowOverlay_Event"
                    h_send = ctypes.windll.kernel32.OpenEventW(0x0002, False, EVENT_NAME)
                    if h_send:
                        ctypes.windll.kernel32.SetEvent(h_send)
                        ctypes.windll.kernel32.CloseHandle(h_send)
                    sys.exit(0)

        # Kreator pierwszego uruchomienia
        try:
            from hardware_profiler import show_first_run_wizard_if_needed
            initial_cfg = load_config()
            if not show_first_run_wizard_if_needed(initial_cfg):
                sys.exit(0)
        except Exception as e:
            logger.warning(f"Błąd kreatora pierwszego uruchomienia: {e}")

        app = DictationApp()
        if is_toggle_req:
            threading.Thread(target=app.toggle_dictation, daemon=True).start()
        app.run_tray()
    except (KeyboardInterrupt, SystemExit):
        sys.exit(0)
    except Exception as e:
        if 'app' in locals() and not getattr(app, '_running', True):
            sys.exit(0)
        logger.critical("FATAL UNCAUGHT EXCEPTION in main: %s", e, exc_info=True)
        try:
            ctypes.windll.user32.MessageBoxW(
                0,
                f"Wystąpił błąd podczas uruchamiania Whiscribe:\n\n{e}\n\nSzczegóły zapisano w pliku app.log.",
                "Błąd Whiscribe",
                0x00000010 | 0x00040000
            )
        except Exception:
            pass
        sys.exit(1)
