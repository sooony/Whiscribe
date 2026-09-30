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
    # 1. Nowoczesny dzwonek (Bell Chime): 580Hz -> 720Hz z ciepłą harmoniczną
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
    # 2. Subtelny Pop (Win11 Soft Bubble): szybki wznoszący chirp 460Hz -> 860Hz
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
    # 3. Harmonia (Arpeggio Akord): C5 (523Hz) -> G5 (784Hz)
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
    # 4. Cyber Minimal (Dyskretny tik): krótki krystaliczny impuls 940Hz
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
    # 1. Łagodny spadek: 480Hz -> 380Hz
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
    # 2. Subtelny Pop (Win11 Soft Bubble opadający): 680Hz -> 340Hz
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
    # 3. Harmonia (Arpeggio Akord opadający): G5 (784Hz) -> C5 (523Hz)
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
    # 4. Cyber Minimal (Dyskretny niski tik): 440Hz
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

from config import load_config, save_config, CONFIG_FILE, get_app_dir, APP_NAME, APP_VERSION
from recorder import AudioRecorder
from transcriber import Transcriber
from injector import inject_text, sync_text, send_unicode_string, ForwardStreamCommitter
from overlay import FloatingOverlay, THEMES, draw_svg_mic
from focus_detector import is_text_field_focused, NON_EDITABLE_WINDOW_CLASSES, get_proc_name_from_hwnd
from meeting_manager import MeetingManager

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetForegroundWindow.argtypes = []
user32.SetForegroundWindow.restype = wintypes.BOOL
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.IsWindow.restype = wintypes.BOOL
user32.IsWindow.argtypes = [wintypes.HWND]

def safe_bring_to_foreground(hwnd: int) -> bool:
    """
    Bezpieczne, błyskawiczne i bezblokujące przywrócenie okna docelowego w Windows.
    Używa neutralnego klawisza VK_F24 (0x87) do odblokowania ForegroundLock:
    ZERO ryzyka aktywacji menu (w przeciwieństwie do Alt 0x12) i ZERO uciętych spacji!
    """
    if not hwnd or not user32.IsWindow(hwnd):
        return False
    cur = user32.GetForegroundWindow()
    if cur == hwnd:
        return True

    # 1. Próba standardowa przez AllowSetForegroundWindow + SwitchToThisWindow
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

    # 2. Odblokowanie ForegroundLock w Windows przez neutralny klawisz VK_F24 (brak aktywacji menu)
    user32.keybd_event(0x87, 0, 0, 0)
    user32.keybd_event(0x87, 0, 2, 0)
    res = user32.SetForegroundWindow(hwnd)
    user32.BringWindowToTop(hwnd)

    for _ in range(5):
        if user32.GetForegroundWindow() == hwnd:
            return True
        time.sleep(0.015)

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

LOG_FILE = os.path.join(get_app_dir(), "app.log")
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

def create_tray_icon_image(state="idle", frame_idx=0, vol=0.0) -> Image.Image:
    """Generuje ikonę dla zasobnika systemowego Windows 11 (granatowa bez obwiedni, biały mikrofon)."""
    img_hi = Image.new('RGBA', (256, 256), color=(0, 0, 0, 0))
    d = ImageDraw.Draw(img_hi)
    navy_color = (18, 28, 58, 255)
    # Granatowe tło bez obwiedni (identyczne jak na pasku zadań)
    d.ellipse((10, 10, 246, 246), fill=navy_color)
    # Czysty biały mikrofon wektorowy
    draw_svg_mic(img_hi, 128, 128, 124, color=(255, 255, 255, 255))

    if state == "recording":
        # Wskaźnik nagrywania: subtelna czerwona dioda REC w prawym górnym rogu
        pulse = 0.5 + 0.5 * math.sin(frame_idx * 0.5)
        rec_r = int(22 + pulse * 8)
        d.ellipse((196 - rec_r, 60 - rec_r, 196 + rec_r, 60 + rec_r), fill=(255, 45, 65, 255))
    elif state == "meeting":
        # Wskaźnik spotkania: subtelna dioda w prawym górnym rogu
        pulse = 0.5 + 0.5 * math.sin(frame_idx * 0.5)
        rec_r = int(22 + pulse * 8)
        d.ellipse((196 - rec_r, 60 - rec_r, 196 + rec_r, 60 + rec_r), fill=(99, 133, 248, 255))
    elif state == "processing":
        # Wskaźnik przetwarzania: subtelna bursztynowa dioda w prawym górnym rogu
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
    Globalny listener skrótów klawiszowych pynput, który:
    1. Akceptuje zdarzenia wstrzykiwane (injected=True) – kluczowe dla myszek Logitech MX Master (Logi Options+),
       oprogramowania myszy gamingowych, stream decków i makr.
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
            exe_path = sys.executable
            work_dir = os.path.dirname(exe_path)
            ps_cmd = (
                f'$sh=New-Object -ComObject WScript.Shell; '
                f'$s=$sh.CreateShortcut(\"{lnk}\"); '
                f'$s.TargetPath=\"{exe_path}\"; '
                f'$s.Arguments=\"\"; '
                f'$s.WorkingDirectory=\"{work_dir}\"; '
                f'$s.IconLocation=\"{exe_path},0\"; '
                f'$s.Description=\"Whiscribe v{APP_VERSION} - AI Voice Typing\"; '
                f'$s.Save()'
            )
        else:
            app_dir = get_app_dir()
            vbs_path = os.path.join(app_dir, "run_silent.vbs")
            ico_path = os.path.join(app_dir, "icon.ico")
            ps_cmd = (
                f'$sh=New-Object -ComObject WScript.Shell; '
                f'$s=$sh.CreateShortcut(\"{lnk}\"); '
                f'$s.TargetPath=\"wscript.exe\"; '
                f'$s.Arguments=\"`\"{vbs_path}`\"\"; '
                f'$s.WorkingDirectory=\"{app_dir}\"; '
                f'$s.IconLocation=\"{ico_path},0\"; '
                f'$s.Description=\"Whiscribe v{APP_VERSION} - AI Voice Typing\"; '
                f'$s.Save()'
            )
        try:
            subprocess.run(["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps_cmd], check=True, creationflags=0x08000000)
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


class DictationApp:
    def __init__(self):
        self.config = load_config()
        self.recorder = AudioRecorder(sample_rate=16000)
        self._last_toggle_time = 0.0
        self._last_meeting_toggle_time = 0.0
        theme = self.config.get("theme", "light")
        self.overlay = FloatingOverlay(theme=theme, always_on_top=self.config.get("always_on_top", True)) if self.config.get("show_overlay", True) else None
        if self.overlay:
            self.overlay.show_live_preview = self.config.get("show_live_preview", False)
            self.overlay.stream_realtime = self.config.get("stream_realtime", False)
        
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
                on_stream_toggle=self.toggle_streaming_mode
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

    def _type_stream_chunk(self, chunk: str):
        """Wpisuje słowa w przód (Forward-only) z ciągłym streamingiem do zablokowanego okna docelowego (nawet przy pracy na 2 monitorach)."""
        if not chunk:
            return

        with self._type_lock:
            cur_fg = user32.GetForegroundWindow()

            # 1. Okno docelowe jest aktywne na pierwszym planie (np. edytor tekstu, IDE) LUB trwa finalizacja (state == "processing")
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
                self.buffered_untyped_text += chunk

                # Jeśli użytkownik trzyma wciśnięty przycisk myszy (klikanie/zaznaczanie w Chrome), nie przerywamy
                if is_mouse_down():
                    return

                # Sprawdź czy bufor zawiera kompletną frazę / klauzulę (np. kropka, przecinek, pytajnik lub >= 4 słowa)
                buf_words = self.buffered_untyped_text.strip().split()
                has_punct = any(self.buffered_untyped_text.rstrip().endswith(p) for p in ('.', ',', '!', '?', ';', ':'))
                should_flush = has_punct or (len(buf_words) >= 4)

                if should_flush:
                    other_fg = cur_fg
                    to_type = self.buffered_untyped_text
                    self.buffered_untyped_text = ""

                    safe_bring_to_foreground(self.target_hwnd)
                    time.sleep(0.025)
                    send_unicode_string(to_type)
                    time.sleep(0.035)
                    if other_fg and user32.IsWindow(other_fg) and other_fg != self.target_hwnd:
                        safe_bring_to_foreground(other_fg)
                        time.sleep(0.010)
            else:
                send_unicode_string(chunk)

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
                st = "recording" if self.state == "recording" else ("meeting" if self.state == "meeting_recording" else "processing")
                try:
                    self.tray_icon.icon = create_tray_icon_image(st, frame_idx=frame, vol=vol)
                except Exception:
                    pass
                frame += 1
                time.sleep(0.08)
            else:
                time.sleep(0.18)

    def minimize_to_taskbar(self):
        """Minimalizuje widżet do dolnego paska zadań Windows (Taskbar)."""
        if self.config.get("always_on_top", True):
            logger.info("Tryb 'Zawsze na wierzchu' aktywny – widżet pozostaje stale widoczny na ekranie.")
            if self.overlay:
                self.overlay.show()
                self.overlay.show_idle()
            return
        self.is_minimized_to_tray = True
        if self.overlay:
            self.overlay.minimize()
        logger.info("Widżet pomyślnie zminimalizowany do dolnego paska zadań Windows.")

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
        h_show = ctypes.windll.kernel32.CreateEventW(None, False, False, EVENT_SHOW)
        h_toggle = ctypes.windll.kernel32.CreateEventW(None, False, False, EVENT_TOGGLE)
        while self._running:
            res_t = ctypes.windll.kernel32.WaitForSingleObject(h_toggle, 200)
            if res_t == 0:
                logger.info("Odebrano sygnał IPC przełączenia dyktowania (--toggle).")
                self.toggle_dictation()
            res_s = ctypes.windll.kernel32.WaitForSingleObject(h_show, 200)
            if res_s == 0:
                logger.info("Odebrano sygnał wybudzenia/pokazania widżetu PIL.")
                self.restore_from_tray()
                self._play_ready_chime()
        if h_show:
            ctypes.windll.kernel32.CloseHandle(h_show)
        if h_toggle:
            ctypes.windll.kernel32.CloseHandle(h_toggle)

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
        """Łagodny dźwięk ostrzegawczy przy braku pola tekstowego."""
        if self.config.get("sound_feedback", True):
            _play_chime_file('error')

    def _play_ready_chime(self):
        """Krótki, subtelny ton gotowości."""
        if self.config.get("sound_feedback", True):
            _play_chime_file('ready')

    def _play_beep(self, freq=None, duration=None):
        self._play_ready_chime()

    def start_recording(self):
        # 1. Rygorystyczny czujnik aktywnego pola tekstowego
        cur_fg = user32.GetForegroundWindow()
        check_hwnd = self.last_active_hwnd if (self.overlay and cur_fg == self.overlay.hwnd and self.last_active_hwnd) else None

        if self.config.get("require_text_field", True):
            is_focused, reason = is_text_field_focused(check_hwnd)
            if not is_focused:
                logger.warning(f"Zablokowano start dyktowania – brak aktywnego pola tekstowego ({reason})")
                self._play_error_chime()
                if self.overlay:
                    self.overlay.show()
                    self.overlay.show_error_balloon()
                return

        # Jeśli użytkownik kliknął widżet, przywróć fokus do docelowego okna roboczego
        if check_hwnd and user32.IsWindow(check_hwnd):
            safe_bring_to_foreground(check_hwnd)

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
            if self.overlay.is_minimized():
                self.restore_from_taskbar()
            else:
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
                    for seg_text, _ in completed:
                        self.committer.commit_segment(seg_text)
                        if self.overlay:
                            self.overlay.add_transcript_entry(seg_text)
                    self.committed_sample_offset += int(completed[-1][1] * 16000)

                    # Jeśli użytkownik przegląda inne okno, a segment się zakończył – wstrzyknij gotową klauzulę
                    cur_fg = user32.GetForegroundWindow()
                    if hasattr(self, 'target_hwnd') and self.target_hwnd and cur_fg != self.target_hwnd:
                        if self.buffered_untyped_text and not is_mouse_down():
                            other_fg = cur_fg
                            to_type = self.buffered_untyped_text
                            self.buffered_untyped_text = ""

                            safe_bring_to_foreground(self.target_hwnd)
                            time.sleep(0.025)
                            send_unicode_string(to_type)
                            time.sleep(0.035)
                            if other_fg and user32.IsWindow(other_fg) and other_fg != self.target_hwnd:
                                safe_bring_to_foreground(other_fg)
                                time.sleep(0.010)

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
                if self.overlay and self.overlay.mode != "idle":
                    self.overlay.show_idle()
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
                    trimmed_rem = AudioRecorder.trim_silence(remaining_audio, sample_rate=16000, keep_lead_s=0.20, keep_tail_s=0.35)
                    if len(trimmed_rem) >= 16000 * 0.25:
                        final_tail = self.transcriber.transcribe(trimmed_rem)

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
                        if self.overlay:
                            self.overlay.add_transcript_entry(final_tail)
                    else:
                        self.committer.finalize()

                    # Upewnij się, że ogon (final_tail) lub jakiekolwiek zaległe znaki po finalize też zostały wpisane
                    if self.buffered_untyped_text:
                        send_unicode_string(self.buffered_untyped_text)
                        self.buffered_untyped_text = ""

                logger.info(f"Finalizacja streamingu: {time.time() - t0:.2f}s | Wpisano łącznie: '{self.committer.typed_text.strip()}'")

            else:
                # Czyste wklejenie po zatrzymaniu nagrywania (tryb batch)
                final_text = self.transcriber.transcribe(audio_data)
                duration = time.time() - t0
                logger.info(f"Finalny czas: {duration:.2f}s | Tekst: '{final_text}'")

                if final_text:
                    if self.overlay:
                        self.overlay.add_transcript_entry(final_text)

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
            self.overlay.clear_transcript()
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
            if self.overlay.is_minimized():
                self.restore_from_taskbar()
            else:
                self.overlay.show()
                self.overlay.show_meeting_recording()
        if self.tray_icon:
            self.tray_icon.icon = create_tray_icon_image("meeting")

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

    def toggle_require_text_field(self):
        self.config["require_text_field"] = not self.config.get("require_text_field", True)
        save_config(self.config)
        logger.info(f"Wymóg pola tekstowego: {'Włączony' if self.config['require_text_field'] else 'Wyłączony'}")

    def toggle_streaming_mode(self):
        self.config["stream_realtime"] = not self.config.get("stream_realtime", True)
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
        """Wyświetla pełne menu kontekstowe Whiscribe (identyczne z menu zasobnika systemowego)."""
        logger.info(f"Otwieranie menu kontekstowego na pozycji ({screen_x}, {screen_y})")
        if getattr(self, '_menu_open', False):
            logger.info("Menu jest już otwarte, pomijanie podwójnego kliknięcia.")
            return
        self._menu_open = True
        try:
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32

            # Sprawdź i uzupełnij współrzędne ekranowe
            if not screen_x or not screen_y or screen_x <= 0 or screen_y <= 0:
                pt = wintypes.POINT()
                user32.GetCursorPos(ctypes.byref(pt))
                screen_x, screen_y = pt.x, pt.y

            # Wyrównanie: jeśli kliknięto po prawej stronie okna (przycisk •••), menu rozwija się do wewnątrz
            flags = 0x0008 | 0x0000 | 0x0100  # TPM_RIGHTALIGN | TPM_TOPALIGN | TPM_RETURNCMD
            if self.overlay and screen_x < self.overlay.pos_x + (self.overlay.bw // 2):
                flags = 0x0000 | 0x0000 | 0x0100  # TPM_LEFTALIGN | TPM_TOPALIGN | TPM_RETURNCMD

            # 1. Preferowane: natywne menu pystray tray_icon (100% spójności ze stanem i zasobnikiem)
            if self.tray_icon and hasattr(self.tray_icon, '_hwnd') and self.tray_icon._hwnd:
                try:
                    import pystray._util.win32 as w
                    self.tray_icon.update_menu()
                    if self.tray_icon._menu_handle:
                        hmenu, descriptors = self.tray_icon._menu_handle

                        # Tworzymy tymczasowe okno hosta powiązane z BIEŻĄCYM wątkiem (eliminuje błąd Win32 ERROR_INVALID_PARAMETER 87)
                        hwnd_owner = user32.CreateWindowExW(
                            0, "STATIC", "WhiscribeMenuHost",
                            0x80000000,  # WS_POPUP
                            int(screen_x), int(screen_y), 0, 0,
                            0, None, kernel32.GetModuleHandleW(None), None
                        )
                        try:
                            user32.SetForegroundWindow(hwnd_owner)
                            idx = w.TrackPopupMenuEx(
                                hmenu,
                                flags,
                                int(screen_x),
                                int(screen_y),
                                hwnd_owner,
                                None
                            )
                            user32.PostMessageW(hwnd_owner, 0, 0, 0)
                        finally:
                            user32.DestroyWindow(hwnd_owner)

                        if idx > 0 and idx <= len(descriptors):
                            cb = descriptors[idx - 1]
                            cb(self.tray_icon)
                        return
                except Exception as e:
                    logger.error(f"Błąd wyświetlania menu przez tray_icon: {e}", exc_info=True)

            # 2. Fallback: bezpośrednie menu Win32 (np. w środowiskach testowych)
            self._show_fallback_win32_menu(screen_x, screen_y)
        finally:
            self._menu_open = False

    def _show_fallback_win32_menu(self, screen_x, screen_y):
        """Wyświetla zapasowe menu Win32 gdy pystray nie jest jeszcze zainicjalizowany."""
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        h_menu = user32.CreatePopupMenu()
        h_theme_sub = user32.CreatePopupMenu()
        h_sound_sub = user32.CreatePopupMenu()
        h_sound_start_sub = user32.CreatePopupMenu()
        h_sound_stop_sub = user32.CreatePopupMenu()
        h_silence_sub = user32.CreatePopupMenu()

        MF_STRING = 0x0000
        MF_SEPARATOR = 0x0800
        MF_POPUP = 0x0010
        MF_CHECKED = 0x0008
        MF_UNCHECKED = 0x0000

        # 1. Podmenu: Styl widżetu (Wszystkie 5 dopracowanych motywów)
        cur_theme = self.config.get("theme", "light")
        themes = [
            ("light", "Jasny (Fluent Light)", 301),
            ("dark", "Ciemny (Fluent Dark)", 302),
            ("glass_light", "Glass Jasny (Mica Light)", 303),
            ("glass_dark", "Glass Ciemny (Mica Dark)", 304),
            ("glass_color", "Glass Kolorowy (Vibrant Glass)", 305),
        ]
        for t_key, t_label, t_id in themes:
            chk = MF_CHECKED if cur_theme == t_key else MF_UNCHECKED
            user32.AppendMenuW(h_theme_sub, MF_STRING | chk, t_id, t_label)
        user32.AppendMenuW(h_menu, MF_POPUP, h_theme_sub, "Styl widżetu")

        # 2. Podmenu: Dźwięki i powiadomienia (Konfiguracja 4 presetów potwierdzenia i wyłączenia)
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

        user32.AppendMenuW(h_menu, MF_SEPARATOR, 0, "")

        # 4. Główne opcje wpisywania i zachowania okna
        chk_stream = MF_CHECKED if self.config.get("stream_realtime", False) else MF_UNCHECKED
        user32.AppendMenuW(h_menu, MF_STRING | chk_stream, 101, "Pisanie na żywo (Streaming)")

        chk_topmost = MF_CHECKED if self.config.get("always_on_top", True) else MF_UNCHECKED
        user32.AppendMenuW(h_menu, MF_STRING | chk_topmost, 103, "Zawsze na wierzchu")

        chk_field = MF_CHECKED if self.config.get("require_text_field", True) else MF_UNCHECKED
        user32.AppendMenuW(h_menu, MF_STRING | chk_field, 102, "Wymagaj aktywnego pola tekstowego")

        user32.AppendMenuW(h_menu, MF_SEPARATOR, 0, "")

        # 5. Spotkania
        chk_meeting = MF_CHECKED if self.state == "meeting_recording" else MF_UNCHECKED
        user32.AppendMenuW(h_menu, MF_STRING | chk_meeting, 104, "Transkrypcja spotkań")
        user32.AppendMenuW(h_menu, MF_STRING, 105, "Otwórz folder transkrypcji spotkań")

        user32.AppendMenuW(h_menu, MF_SEPARATOR, 0, "")

        # 6. Zarządzanie oknem / Aplikacją
        user32.AppendMenuW(h_menu, MF_STRING, 601, "Zminimalizuj do paska zadań")
        user32.AppendMenuW(h_menu, MF_STRING, 402, "Zamknij aplikację")

        hwnd_owner = user32.CreateWindowExW(
            0, "STATIC", "WhiscribeFallbackMenuHost",
            0x80000000,  # WS_POPUP
            int(screen_x), int(screen_y), 0, 0,
            0, None, kernel32.GetModuleHandleW(None), None
        )
        try:
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
            flags = 0x0100 | 0x0008  # TPM_RETURNCMD | TPM_RIGHTALIGN
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
            self.config["auto_stop_silence_seconds"] = 0.0
            save_config(self.config)
        elif cmd in (301, 302, 303, 304, 305):
            t_map = {301: "light", 302: "dark", 303: "glass_light", 304: "glass_dark", 305: "glass_color"}
            t_choice = t_map.get(cmd, "light")
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
        elif cmd == 601:
            self.minimize_to_taskbar()
        elif cmd == 402:
            self.exit_app()

    def _on_overlay_theme_changed(self, new_theme):
        self.config["theme"] = new_theme
        save_config(self.config)
        logger.info(f"Zmieniono motyw graficzny na: {new_theme}")

    def toggle_autostart(self):
        curr = is_autostart_enabled()
        set_autostart(not curr)
        logger.info(f"Autostart Windows: {'Wyłączony' if curr else 'Włączony'}")

    def run_tray(self):
        self.setup_hotkey()

        def set_theme_action(t_key):
            def handler(icon=None, item=None):
                self.config["theme"] = t_key
                save_config(self.config)
                if self.overlay:
                    self.overlay.set_theme(t_key)
            return handler

        theme_items = [
            pystray.MenuItem("Jasny (Fluent Light)", set_theme_action("light"), checked=lambda item: self.config.get("theme", "light") == "light"),
            pystray.MenuItem("Ciemny (Fluent Dark)", set_theme_action("dark"), checked=lambda item: self.config.get("theme", "light") == "dark"),
            pystray.MenuItem("Glass Jasny (Mica Light)", set_theme_action("glass_light"), checked=lambda item: self.config.get("theme", "light") == "glass_light"),
            pystray.MenuItem("Glass Ciemny (Mica Dark)", set_theme_action("glass_dark"), checked=lambda item: self.config.get("theme", "light") == "glass_dark"),
            pystray.MenuItem("Glass Kolorowy (Vibrant Glass)", set_theme_action("glass_color"), checked=lambda item: self.config.get("theme", "light") == "glass_color"),
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
                "Uruchamiaj z systemem Windows (Autostart)",
                lambda icon=None, item=None: self.toggle_autostart(),
                checked=lambda item: is_autostart_enabled()
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Zakończ Whiscribe", self.exit_app)
        )

        self.tray_icon = pystray.Icon(
            "Whiscribe",
            create_tray_icon_image("idle"),
            f"Whiscribe v{APP_VERSION} (AI Voice Typing)",
            menu
        )

        logger.info(f"Aplikacja Whiscribe v{APP_VERSION} gotowa w zasobniku systemowym (obok zegara).")
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
                        subprocess.run(
                            ["powershell", "-NoProfile", "-Command", f"Get-Process -Name '*Whiscribe*' | Where-Object {{ $_.Id -ne {my_pid} }} | Stop-Process -Force"],
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

        # Kreator pierwszego uruchomienia i automatyczny dobór silnika AI do sprzętu
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
    except Exception as e:
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
