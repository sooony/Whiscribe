import ctypes
from ctypes import wintypes
import threading
import time
import math
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
kernel32 = ctypes.windll.kernel32

LRESULT = ctypes.c_int64
user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.DefWindowProcW.restype = LRESULT
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)

class BLENDFUNCTION(ctypes.Structure):
    _fields_ = [
        ('BlendOp', ctypes.c_byte),
        ('BlendFlags', ctypes.c_byte),
        ('SourceConstantAlpha', ctypes.c_byte),
        ('AlphaFormat', ctypes.c_byte)
    ]

class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ('biSize', wintypes.DWORD),
        ('biWidth', wintypes.LONG),
        ('biHeight', wintypes.LONG),
        ('biPlanes', wintypes.WORD),
        ('biBitCount', wintypes.WORD),
        ('biCompression', wintypes.DWORD),
        ('biSizeImage', wintypes.DWORD),
        ('biXPelsPerMeter', wintypes.LONG),
        ('biYPelsPerMeter', wintypes.LONG),
        ('biClrUsed', wintypes.DWORD),
        ('biClrImportant', wintypes.DWORD)
    ]

class TRACKMOUSEEVENT(ctypes.Structure):
    _fields_ = [
        ('cbSize', wintypes.DWORD),
        ('dwFlags', wintypes.DWORD),
        ('hwndTrack', wintypes.HWND),
        ('dwHoverTime', wintypes.DWORD)
    ]

class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [
        ('cbSize', wintypes.UINT),
        ('style', wintypes.UINT),
        ('lpfnWndProc', WNDPROC),
        ('cbClsExtra', ctypes.c_int),
        ('cbWndExtra', ctypes.c_int),
        ('hInstance', wintypes.HINSTANCE),
        ('hIcon', wintypes.HICON),
        ('hCursor', wintypes.HICON),
        ('hbrBackground', wintypes.HBRUSH),
        ('lpszMenuName', wintypes.LPCWSTR),
        ('lpszClassName', wintypes.LPCWSTR),
        ('hIconSm', wintypes.HICON),
    ]

# Win32 Function Signatures (64-bit safe)
user32.UpdateLayeredWindow.argtypes = [
    wintypes.HWND, wintypes.HDC, ctypes.POINTER(wintypes.POINT),
    ctypes.POINTER(wintypes.SIZE), wintypes.HDC, ctypes.POINTER(wintypes.POINT),
    wintypes.COLORREF, ctypes.POINTER(BLENDFUNCTION), wintypes.DWORD
]
user32.UpdateLayeredWindow.restype = wintypes.BOOL

gdi32.CreateDIBSection.argtypes = [
    wintypes.HDC, ctypes.POINTER(BITMAPINFOHEADER), wintypes.UINT,
    ctypes.POINTER(ctypes.c_void_p), wintypes.HANDLE, wintypes.DWORD
]
gdi32.CreateDIBSection.restype = wintypes.HBITMAP

gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HANDLE]
gdi32.SelectObject.restype = wintypes.HANDLE
gdi32.DeleteObject.argtypes = [wintypes.HANDLE]
gdi32.DeleteObject.restype = wintypes.BOOL
gdi32.DeleteDC.argtypes = [wintypes.HDC]
gdi32.DeleteDC.restype = wintypes.BOOL

user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
user32.ReleaseDC.restype = ctypes.c_int
user32.GetDC.argtypes = [wintypes.HWND]
user32.GetDC.restype = wintypes.HDC
user32.DestroyWindow.argtypes = [wintypes.HWND]
user32.DestroyWindow.restype = wintypes.BOOL
user32.SetCursor.argtypes = [wintypes.HICON]
user32.SetCursor.restype = wintypes.HICON

user32.CreateWindowExW.argtypes = [
    wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID
]
user32.CreateWindowExW.restype = wintypes.HWND

user32.SetWindowPos.argtypes = [
    wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
    ctypes.c_int, ctypes.c_int, wintypes.UINT
]
user32.SetWindowPos.restype = wintypes.BOOL

user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
user32.GetCursorPos.restype = wintypes.BOOL
user32.ScreenToClient.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
user32.ScreenToClient.restype = wintypes.BOOL

gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
gdi32.CreateCompatibleDC.restype = wintypes.HDC
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.ShowWindow.restype = wintypes.BOOL
user32.SetCapture.argtypes = [wintypes.HWND]
user32.SetCapture.restype = wintypes.HWND
user32.ReleaseCapture.argtypes = []
user32.ReleaseCapture.restype = wintypes.BOOL

user32.GetSystemMetrics.argtypes = [ctypes.c_int]
user32.GetSystemMetrics.restype = ctypes.c_int
user32.PeekMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT, wintypes.UINT]
user32.PeekMessageW.restype = wintypes.BOOL
user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
user32.TranslateMessage.restype = wintypes.BOOL
user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
user32.DispatchMessageW.restype = LRESULT
user32.PostQuitMessage.argtypes = [ctypes.c_int]
user32.PostQuitMessage.restype = None

# DPI Awareness
try:
    user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
except Exception:
    try:
        user32.SetProcessDPIAware()
    except Exception:
        pass

WINDIR = os.environ.get('WINDIR', 'C:\\Windows')
FONT_REG_PATH = os.path.join(WINDIR, 'Fonts', 'segoeui.ttf')
FONT_BOLD_PATH = os.path.join(WINDIR, 'Fonts', 'segoeuib.ttf')
FONT_SEMI_PATH = os.path.join(WINDIR, 'Fonts', 'seguisb.ttf')

THEMES = {
    'dark': {
        'name': 'Ciemny (Dark Modern)',
        'panel_bg': (20, 28, 41, 235),
        'panel_border': (151, 173, 216, 40),
        'text': (237, 243, 255, 255),
        'muted': (145, 161, 191, 255),
        'wave': (132, 147, 177, 240),
        'accent': (75, 92, 242, 255),
        'danger': (255, 33, 51, 255),
        'tab_bg': (35, 48, 78, 250),
        'mic_standby_bg': (19, 27, 40, 240),
        'mic_standby_border': (255, 255, 255, 225),
        'meet_standby_bg': (30, 42, 60, 230),
        'scroll_thumb': (185, 199, 228, 90),
        'scroll_track': (185, 199, 228, 15),
        'shadow_alpha': 80
    },
    'light': {
        'name': 'Jasny (Light Modern)',
        'panel_bg': (248, 250, 254, 245),
        'panel_border': (99, 122, 160, 45),
        'text': (24, 49, 82, 255),
        'muted': (116, 133, 163, 255),
        'wave': (127, 142, 170, 240),
        'accent': (64, 92, 242, 255),
        'danger': (255, 33, 51, 255),
        'tab_bg': (220, 232, 255, 250),
        'mic_standby_bg': (235, 242, 252, 250),
        'mic_standby_border': (72, 97, 127, 220),
        'meet_standby_bg': (228, 236, 248, 230),
        'scroll_thumb': (100, 120, 154, 100),
        'scroll_track': (100, 120, 154, 20),
        'shadow_alpha': 40
    }
}

THEME_MAP = {
    'glass_light': 'light',
    'minimal': 'light',
    'glass_dark': 'dark',
    'cyber_neon': 'dark',
    'nordic_titanium': 'light'
}

# 27 bar height profiles from HTML prototype
BAR_HEIGHTS = [
    [7,15,10,22],[11,27,16,31],[8,18,12,25],[14,33,19,36],
    [10,21,15,29],[13,30,18,34],[8,16,11,23],[16,34,20,38],
    [11,25,15,31],[7,18,10,21],[13,29,18,33],[9,22,14,27],
    [15,35,21,39],[8,17,11,24],[12,28,17,32],[10,23,14,29],
    [7,16,10,22],[14,31,19,36],[10,20,14,27],[13,30,18,34],
    [8,18,12,25],[12,27,16,31],[9,19,13,24],[15,33,20,38],
    [10,24,15,30],[7,16,11,22],[12,26,16,30]
]

def draw_svg_mic(d, cx, cy, sz, color=(255, 255, 255, 255)):
    """SVG Microphone icon matching HTML prototype."""
    scale = sz / 24.0
    rx1 = cx - 4 * scale
    ry1 = cy - 9 * scale
    rx2 = cx + 4 * scale
    ry2 = cy + 3 * scale
    d.rounded_rectangle([rx1, ry1, rx2, ry2], radius=int(4 * scale), fill=None, outline=color, width=max(1, int(1.8 * scale)))
    
    cradle_r = 7 * scale
    cradle_top = cy - 1 * scale
    line_w = max(1, int(1.8 * scale))
    d.arc([cx - cradle_r, cradle_top - cradle_r, cx + cradle_r, cradle_top + cradle_r], start=0, end=180, fill=color, width=line_w)
    
    stem_top = cradle_top + cradle_r
    stem_bot = stem_top + 3.2 * scale
    d.line([(cx, stem_top), (cx, stem_bot)], fill=color, width=line_w)
    
    base_hw = 3.5 * scale
    d.line([(cx - base_hw, stem_bot), (cx + base_hw, stem_bot)], fill=color, width=line_w)

def draw_people_icon(d, cx, cy, sz, color=(255, 255, 255, 255)):
    """SVG Group / People icon matching HTML prototype."""
    scale = sz / 38.0
    ox = cx - 19 * scale
    oy = cy - 19 * scale
    
    c1x = ox + 14 * scale
    c1y = oy + 13 * scale
    r1 = 6 * scale
    d.ellipse([c1x - r1, c1y - r1, c1x + r1, c1y + r1], fill=color)
    
    c2x = ox + 27 * scale
    c2y = oy + 15 * scale
    r2 = 4.6 * scale
    d.ellipse([c2x - r2, c2y - r2, c2x + r2, c2y + r2], fill=color)
    
    body1_l = ox + 3.5 * scale
    body1_r = ox + 22.5 * scale
    body1_t = oy + 20.6 * scale
    body1_b = oy + 30.0 * scale
    d.chord([body1_l, body1_t - 4 * scale, body1_r, body1_b + 4 * scale], start=180, end=360, fill=color)
    
    body2_l = ox + 21.0 * scale
    body2_r = ox + 36.0 * scale
    body2_t = oy + 22.9 * scale
    body2_b = oy + 30.0 * scale
    d.chord([body2_l, body2_t - 3.5 * scale, body2_r, body2_b + 3.5 * scale], start=180, end=360, fill=color)

class FloatingOverlay:
    """
    Wiernie odwzorowany interfejs Voice UI zgodny w 100% z prototypem użytkownika (250x90 Voice Module + Panel Transkrypcji).
    - Zablokowanie kradzieży fokusu (WS_EX_NOACTIVATE, MA_NOACTIVATE)
    - Płynne przeciąganie po obu monitorach
    - Kreski reaktywne fali dźwiękowej (27 słupków z dynamiczną modulacją)
    - Panel transkrypcji na żywo ze znacznikiem czasu i karetką tekstu
    - Dymek błędu braku pola tekstowego
    """

    def __init__(self, theme='dark'):
        self.hwnd = None
        self._thread = None
        self._ready_event = threading.Event()
        self._running = True
        self._lock = threading.RLock()

        if theme in THEME_MAP:
            theme = THEME_MAP[theme]
        self.theme = theme if theme in THEMES else 'dark'
        self.on_theme_changed = None

        # Stan pracy: "idle", "recording", "transcribing", "processing"
        self.mode = "idle"
        self._visible = True
        self._hover_target = None
        self._pressed_btn = None
        self.volume_getter = lambda: 0.0
        self.loopback_volume_getter = lambda: 0.0

        # Wymiary całego okna warstwowego (mieści panel u góry oraz moduł 250x90 u dołu)
        self.w = 280
        self.h = 264

        # Moduł dolny (Voice Module): 250x90 px
        self.mw = 250
        self.mh = 90
        self.mx = (self.w - self.mw) // 2       # 15
        self.my = self.h - self.mh - 16          # 158
        self.mod_r = 20

        # Panel górny (Transkrypcja): 250x126 px
        self.pw = 250
        self.ph = 126
        self.px = (self.w - self.pw) // 2       # 15
        self.py = self.my - self.ph - 8          # 24
        self.panel_r = 18
        self.panel_open = True
        self.show_live_preview = False

        # Uchwyt do przeciągania
        self.handle_w = 29
        self.handle_h = 3
        self.handle_x = self.mx + (self.mw - self.handle_w) / 2
        self.handle_y = self.my + 6.0

        # Przycisk Zamknij ✕ modułu
        self.close_cx = self.mx + self.mw - 14
        self.close_cy = self.my + 12

        # Lewy przycisk mikrofonu (Dyktowanie)
        self.mic_cx = self.mx + 42
        self.mic_cy = self.my + 47
        self.mic_rad = 24

        # Prawy przycisk transkrypcji (Spotkanie)
        self.meet_cx = self.mx + self.mw - 42
        self.meet_cy = self.my + 47
        self.meet_rad = 24

        # Dymek powiadomień / ostrzeżeń
        self._balloon_type = None  # None, "error", "info"
        self._balloon_message = None
        self._balloon_until = 0.0

        # Dane transkrypcji
        self.transcript_lines = []
        self._start_time = 0.0
        self.live_tail = ""
        self._dirty = True

        # Callbacki
        self.on_stop_callback = None
        self.on_close_callback = None
        self.on_toggle_callback = None
        self.on_meeting_toggle_callback = None
        self.settings_handler = None

        # Pozycja wyjściowa: wycentrowana na dole ekranu
        screen_w = user32.GetSystemMetrics(0)
        screen_h = user32.GetSystemMetrics(1)
        self.pos_x = (screen_w - self.w) // 2
        self.pos_y = screen_h - self.h - 60

        # Dragging
        self._is_dragging = False
        self._drag_start_cursor_x = 0
        self._drag_start_cursor_y = 0
        self._drag_start_win_x = 0
        self._drag_start_win_y = 0

        # Kursory
        self._hcursor_arrow = user32.LoadCursorW(None, 32512)
        self._hcursor_hand = user32.LoadCursorW(None, 32649)
        self._hcursor_move = user32.LoadCursorW(None, 32646)

        # Bufor DIB
        self.mem_dc = None
        self.h_bmp = None
        self.old_bmp = None
        self.p_bits = None

        self._start_thread()

    def set_callbacks(self, on_stop=None, on_close=None, on_toggle=None, on_meeting_toggle=None):
        self.on_stop_callback = on_stop
        self.on_close_callback = on_close
        self.on_toggle_callback = on_toggle
        self.on_meeting_toggle_callback = on_meeting_toggle

    def set_meeting_volume_getter(self, getter):
        self.loopback_volume_getter = getter

    def set_settings_handler(self, handler):
        self.settings_handler = handler

    def set_volume_getter(self, getter):
        self.volume_getter = getter

    def _start_thread(self):
        self._thread = threading.Thread(target=self._run_ui, daemon=True)
        self._thread.start()
        self._ready_event.wait(timeout=3.0)

    def _is_inside_module(self, x, y):
        return (self.mx <= x <= self.mx + self.mw) and (self.my <= y <= self.my + self.mh)

    def _is_inside_panel(self, x, y):
        if not self.panel_open and not self._balloon_type:
            return False
        return (self.px <= x <= self.px + self.pw) and (self.py <= y <= self.py + self.ph)

    def _get_target(self, x, y):
        # 1. Sprawdź kliknięcie w panelu górnym
        if self._balloon_type == "error":
            btn_x = self.px + 16
            btn_y = self.py + self.ph - 36
            btn_w = self.pw - 32
            btn_h = 26
            if (btn_x <= x <= btn_x + btn_w) and (btn_y <= y <= btn_y + btn_h):
                return 'btn_rozumiem'
            if self._is_inside_panel(x, y):
                return 'balloon_body'

        elif self.panel_open:
            # Przycisk ✕ zamykający panel transkrypcji
            close_px = self.px + self.pw - 16
            close_py = self.py + 16
            if abs(x - close_px) <= 12 and abs(y - close_py) <= 12:
                return 'btn_panel_close'
            if self._is_inside_panel(x, y):
                return 'panel_content'
        else:
            # Gdy panel jest zamknięty, sprawdź przycisk "Pokaż transkrypcję"
            tgl_x = self.mx + self.mw // 2
            tgl_y = self.my - 14
            if abs(x - tgl_x) <= 50 and abs(y - tgl_y) <= 12:
                return 'btn_panel_open'

        # 2. Sprawdź kontrolki w module dolnym
        if not self._is_inside_module(x, y):
            return None

        # Mikrofon (lewy)
        d_mic = (x - self.mic_cx)**2 + (y - self.mic_cy)**2
        if d_mic <= (self.mic_rad + 3)**2:
            return 'btn_mic'

        # Transkrypcja / Spotkanie (prawy)
        d_meet = (x - self.meet_cx)**2 + (y - self.meet_cy)**2
        if d_meet <= (self.meet_rad + 3)**2:
            return 'btn_meeting'

        # Zamknij ✕ modułu
        if abs(x - self.close_cx) <= 12 and abs(y - self.close_cy) <= 12:
            return 'btn_close'

        # Przeciąganie modułu
        return 'widget_drag'

    def _wnd_proc(self, hwnd, msg, wparam, lparam):
        WM_DESTROY = 0x0002
        WM_MOUSEACTIVATE = 0x0021
        MA_NOACTIVATE = 3
        WM_LBUTTONDOWN = 0x0201
        WM_LBUTTONUP = 0x0202
        WM_RBUTTONUP = 0x0205
        WM_MOUSEMOVE = 0x0200
        WM_MOUSELEAVE = 0x02A3
        WM_SETCURSOR = 0x0020
        WM_NCHITTEST = 0x0084

        if msg == WM_MOUSEACTIVATE:
            # Kluczowe: kliknięcie w widżet NIE kradnie fokusu z edytora docelowego!
            return MA_NOACTIVATE

        if msg == WM_NCHITTEST:
            x = lparam & 0xFFFF
            y = (lparam >> 16) & 0xFFFF
            if x > 0x7FFF: x -= 0x10000
            if y > 0x7FFF: y -= 0x10000
            pt = wintypes.POINT(x, y)
            user32.ScreenToClient(hwnd, ctypes.byref(pt))

            if self._is_inside_module(pt.x, pt.y) or self._is_inside_panel(pt.x, pt.y):
                return 1  # HTCLIENT
            if not self.panel_open and abs(pt.x - (self.mx + self.mw//2)) <= 50 and abs(pt.y - (self.my - 14)) <= 12:
                return 1
            return -1  # HTTRANSPARENT (kliknięcia obok przelatują bez przeszkód)

        elif msg == WM_MOUSEMOVE:
            tme = TRACKMOUSEEVENT()
            tme.cbSize = ctypes.sizeof(TRACKMOUSEEVENT)
            tme.dwFlags = 2
            tme.hwndTrack = hwnd
            user32.TrackMouseEvent(ctypes.byref(tme))

            x = lparam & 0xFFFF
            y = (lparam >> 16) & 0xFFFF
            if x > 0x7FFF: x -= 0x10000
            if y > 0x7FFF: y -= 0x10000

            if self._is_dragging:
                cur_pt = wintypes.POINT()
                user32.GetCursorPos(ctypes.byref(cur_pt))
                dx = cur_pt.x - self._drag_start_cursor_x
                dy = cur_pt.y - self._drag_start_cursor_y
                self.pos_x = self._drag_start_win_x + dx
                self.pos_y = self._drag_start_win_y + dy
                user32.SetWindowPos(
                    hwnd, 0, self.pos_x, self.pos_y, 0, 0,
                    0x0001 | 0x0004 | 0x0010
                )
            else:
                target = self._get_target(x, y)
                if target != self._hover_target:
                    self._hover_target = target
                    self._dirty = True
            return 0

        elif msg == WM_MOUSELEAVE:
            self._hover_target = None
            self._dirty = True
            return 0

        elif msg == WM_SETCURSOR:
            if self._hover_target in ('btn_mic', 'btn_meeting', 'btn_close', 'btn_panel_close', 'btn_panel_open', 'btn_rozumiem'):
                user32.SetCursor(self._hcursor_hand)
                return 1
            elif self._hover_target == 'widget_drag':
                user32.SetCursor(self._hcursor_move)
                return 1
            else:
                user32.SetCursor(self._hcursor_arrow)
                return 1

        elif msg == WM_LBUTTONDOWN:
            x = lparam & 0xFFFF
            y = (lparam >> 16) & 0xFFFF
            if x > 0x7FFF: x -= 0x10000
            if y > 0x7FFF: y -= 0x10000

            target = self._get_target(x, y)
            self._pressed_btn = target

            if target == 'widget_drag':
                self._is_dragging = True
                user32.SetCapture(hwnd)
                cur_pt = wintypes.POINT()
                user32.GetCursorPos(ctypes.byref(cur_pt))
                self._drag_start_cursor_x = cur_pt.x
                self._drag_start_cursor_y = cur_pt.y
                self._drag_start_win_x = self.pos_x
                self._drag_start_win_y = self.pos_y
            return 0

        elif msg == WM_LBUTTONUP:
            if self._is_dragging:
                self._is_dragging = False
                user32.ReleaseCapture()

            x = lparam & 0xFFFF
            y = (lparam >> 16) & 0xFFFF
            if x > 0x7FFF: x -= 0x10000
            if y > 0x7FFF: y -= 0x10000
            target = self._get_target(x, y)

            if self._pressed_btn == target:
                if target == 'btn_mic':
                    if self.mode == "recording":
                        if self.on_stop_callback:
                            threading.Thread(target=self.on_stop_callback, daemon=True).start()
                    elif self.mode == "transcribing":
                        if self.on_meeting_toggle_callback:
                            threading.Thread(target=self.on_meeting_toggle_callback, daemon=True).start()
                    else:
                        if self.on_toggle_callback:
                            threading.Thread(target=self.on_toggle_callback, daemon=True).start()

                elif target == 'btn_meeting':
                    if self.mode == "transcribing":
                        if self.on_meeting_toggle_callback:
                            threading.Thread(target=self.on_meeting_toggle_callback, daemon=True).start()
                    elif self.mode == "recording":
                        if self.on_stop_callback:
                            threading.Thread(target=self.on_stop_callback, daemon=True).start()
                    else:
                        if self.on_meeting_toggle_callback:
                            threading.Thread(target=self.on_meeting_toggle_callback, daemon=True).start()

                elif target == 'btn_panel_close':
                    self.panel_open = False
                    self._dirty = True

                elif target == 'btn_panel_open':
                    self.panel_open = True
                    self._dirty = True

                elif target == 'btn_rozumiem':
                    self.hide_balloon()

                elif target == 'btn_close':
                    if self.mode == "recording":
                        if self.on_close_callback:
                            threading.Thread(target=self.on_close_callback, daemon=True).start()
                    elif self.mode == "transcribing":
                        if self.on_meeting_toggle_callback:
                            threading.Thread(target=self.on_meeting_toggle_callback, daemon=True).start()
                    else:
                        self.hide()

            self._pressed_btn = None
            return 0

        elif msg == WM_RBUTTONUP:
            pt_screen = wintypes.POINT()
            user32.GetCursorPos(ctypes.byref(pt_screen))
            if self.settings_handler:
                threading.Thread(target=self.settings_handler, args=(pt_screen.x, pt_screen.y), daemon=True).start()
            return 0

        elif msg == 0x0010:  # WM_CLOSE
            user32.DestroyWindow(hwnd)
            return 0

        elif msg == WM_DESTROY:
            user32.PostQuitMessage(0)
            return 0

        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _run_ui(self):
        try:
            try:
                h_def = user32.OpenDesktopW("Default", 0, False, 0x01FF)
                if h_def:
                    user32.SetThreadDesktop(h_def)
            except Exception:
                pass

            self._proc = WNDPROC(self._wnd_proc)

            wc = WNDCLASSEXW()
            wc.cbSize = ctypes.sizeof(WNDCLASSEXW)
            wc.style = 3
            wc.lpfnWndProc = self._proc
            wc.hInstance = kernel32.GetModuleHandleW(None)
            wc.hCursor = self._hcursor_arrow
            wc.lpszClassName = "VoiceUI250x90Class"

            user32.RegisterClassExW(ctypes.byref(wc))

            WS_EX_LAYERED = 0x00080000
            WS_EX_TOPMOST = 0x00000008
            WS_EX_TOOLWINDOW = 0x00000080
            WS_EX_NOACTIVATE = 0x08000000
            WS_POPUP = 0x80000000

            self.hwnd = user32.CreateWindowExW(
                WS_EX_LAYERED | WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE,
                "VoiceUI250x90Class",
                "VoiceUICompactOverlay",
                WS_POPUP,
                self.pos_x, self.pos_y, self.w, self.h,
                None, None, wc.hInstance, None
            )

            screen_dc = user32.GetDC(0)
            self.mem_dc = gdi32.CreateCompatibleDC(screen_dc)
            bih = BITMAPINFOHEADER()
            bih.biSize = ctypes.sizeof(BITMAPINFOHEADER)
            bih.biWidth = self.w
            bih.biHeight = self.h
            bih.biPlanes = 1
            bih.biBitCount = 32
            bih.biCompression = 0
            self.p_bits = ctypes.c_void_p()
            self.h_bmp = gdi32.CreateDIBSection(self.mem_dc, ctypes.byref(bih), 0, ctypes.byref(self.p_bits), None, 0)
            self.old_bmp = gdi32.SelectObject(self.mem_dc, self.h_bmp)
            user32.ReleaseDC(0, screen_dc)

            if self._visible:
                user32.ShowWindow(self.hwnd, 8)  # SW_SHOWNA
                user32.SetWindowPos(self.hwnd, -1, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010)

            self._ready_event.set()
            self._dirty = True
            self._render_frame(time.time())

            msg = wintypes.MSG()
            last_frame_time = time.time()
            prev_hover = self._hover_target

            while self._running:
                while user32.PeekMessageW(ctypes.byref(msg), self.hwnd, 0, 0, 1):
                    user32.TranslateMessage(ctypes.byref(msg))
                    user32.DispatchMessageW(ctypes.byref(msg))

                now = time.time()
                elapsed = now - last_frame_time
                if elapsed < 0.030:
                    time.sleep(max(0.001, 0.030 - elapsed))
                    continue

                if self._balloon_type and self._balloon_until > 0 and now > self._balloon_until:
                    self._balloon_type = None
                    self._dirty = True

                if self._hover_target != prev_hover:
                    self._dirty = True
                    prev_hover = self._hover_target

                needs_anim = (self.mode in ("recording", "transcribing", "processing")) or self._is_dragging

                if self._visible and self.hwnd and (needs_anim or self._dirty):
                    self._dirty = False
                    last_frame_time = time.time()
                    self._render_frame(last_frame_time)
                else:
                    time.sleep(0.025)

        except Exception as e:
            import logging
            logging.getLogger("Overlay").error(f"Błąd wątku UI overlay: {e}", exc_info=True)
        finally:
            self._ready_event.set()
            if self.mem_dc and self.old_bmp:
                try: gdi32.SelectObject(self.mem_dc, self.old_bmp)
                except Exception: pass
            if self.h_bmp:
                try: gdi32.DeleteObject(self.h_bmp)
                except Exception: pass
            if self.mem_dc:
                try: gdi32.DeleteDC(self.mem_dc)
                except Exception: pass

    def _render_frame(self, t_now):
        cfg = THEMES.get(self.theme, THEMES['dark'])
        scale = 2
        W, H = self.w * scale, self.h * scale

        img = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)

        # Czcionki
        try:
            fnt_tab = ImageFont.truetype(FONT_BOLD_PATH, int(9.5 * scale))
            fnt_text = ImageFont.truetype(FONT_REG_PATH, int(8.8 * scale))
            fnt_time = ImageFont.truetype(FONT_REG_PATH, int(8.2 * scale))
            fnt_status = ImageFont.truetype(FONT_REG_PATH, int(8.5 * scale))
            fnt_timer = ImageFont.truetype(FONT_REG_PATH, int(8.5 * scale))
            fnt_close = ImageFont.truetype(FONT_REG_PATH, int(15 * scale))
        except Exception:
            fnt_tab = fnt_text = fnt_time = fnt_status = fnt_timer = fnt_close = ImageFont.load_default()

        # Pobierz poziomy głośności
        vol = 0.0
        if self.volume_getter:
            try: vol = float(self.volume_getter())
            except Exception: vol = 0.0

        loop_vol = 0.0
        if self.loopback_volume_getter:
            try: loop_vol = float(self.loopback_volume_getter())
            except Exception: loop_vol = 0.0

        timer_s = 0
        if self.mode in ("recording", "transcribing") and self._start_time > 0:
            timer_s = int(t_now - self._start_time)

        # ========================================================
        # 1. PANEL GÓRNY (Transkrypcja lub Ostrzeżenie Błędu)
        # ========================================================
        px = int(self.px * scale)
        py = int(self.py * scale)
        pw = int(self.pw * scale)
        ph = int(self.ph * scale)
        pr = int(self.panel_r * scale)

        if self._balloon_type == "error":
            # Dymek błędu z przyciskiem Rozumiem
            sh = Image.new('RGBA', (W, H), (0, 0, 0, 0))
            sd = ImageDraw.Draw(sh)
            sd.rounded_rectangle([px, py + int(4*scale), px + pw, py + ph + int(6*scale)], radius=pr, fill=(0, 0, 0, cfg['shadow_alpha']))
            sh = sh.filter(ImageFilter.GaussianBlur(radius=int(6*scale)))
            img.alpha_composite(sh)

            d = ImageDraw.Draw(img)
            d.rounded_rectangle([px, py, px + pw, py + ph], radius=pr, fill=cfg['panel_bg'], outline=cfg['panel_border'], width=max(1, int(1.1*scale)))

            # Ikona błędu ❌
            err_cx = px + int(24 * scale)
            err_cy = py + int(30 * scale)
            err_r = int(9 * scale)
            d.ellipse([err_cx - err_r, err_cy - err_r, err_cx + err_r, err_cy + err_r], fill=(209, 52, 56, 255))
            ex_sz = int(3.5 * scale)
            d.line([(err_cx - ex_sz, err_cy - ex_sz), (err_cx + ex_sz, err_cy + ex_sz)], fill=(255, 255, 255, 255), width=max(1, int(1.6*scale)))
            d.line([(err_cx - ex_sz, err_cy + ex_sz), (err_cx + ex_sz, err_cy - ex_sz)], fill=(255, 255, 255, 255), width=max(1, int(1.6*scale)))

            d.text((px + int(42 * scale), py + int(18 * scale)), "Aby używać wpisywania głosowego,", fill=cfg['text'], font=fnt_text)
            d.text((px + int(42 * scale), py + int(32 * scale)), "zaznacz pole tekstowe i spróbuj", fill=cfg['text'], font=fnt_text)
            d.text((px + int(42 * scale), py + int(46 * scale)), "ponownie.", fill=cfg['text'], font=fnt_text)

            btn_x = px + int(16 * scale)
            btn_y = py + ph - int(34 * scale)
            btn_w = pw - int(32 * scale)
            btn_h = int(24 * scale)
            btn_fill = (45, 60, 90, 250) if self._hover_target == 'btn_rozumiem' else (35, 48, 75, 250)
            d.rounded_rectangle([btn_x, btn_y, btn_x + btn_w, btn_y + btn_h], radius=int(6*scale), fill=btn_fill, outline=cfg['panel_border'])
            d.text((btn_x + btn_w/2, btn_y + btn_h/2 - int(0.5*scale)), "Rozumiem", fill=cfg['text'], font=fnt_tab, anchor="mm")

        elif self.panel_open:
            # Standardowy panel transkrypcji z prototypu
            sh = Image.new('RGBA', (W, H), (0, 0, 0, 0))
            sd = ImageDraw.Draw(sh)
            sd.rounded_rectangle([px, py + int(4*scale), px + pw, py + ph + int(6*scale)], radius=pr, fill=(0, 0, 0, cfg['shadow_alpha']))
            sh = sh.filter(ImageFilter.GaussianBlur(radius=int(6*scale)))
            img.alpha_composite(sh)

            d = ImageDraw.Draw(img)
            d.rounded_rectangle([px, py, px + pw, py + ph], radius=pr, fill=cfg['panel_bg'], outline=cfg['panel_border'], width=max(1, int(1.1*scale)))

            # Header panelu (33px)
            head_h = int(33 * scale)
            d.line([(px, py + head_h), (px + pw, py + head_h)], fill=cfg['panel_border'], width=max(1, int(1*scale)))

            # Zakładka Transkrypcja
            tab_x = px + int(8 * scale)
            tab_y = py + int(5.5 * scale)
            tab_w = int(72 * scale)
            tab_h = int(22 * scale)
            d.rounded_rectangle([tab_x, tab_y, tab_x + tab_w, tab_y + tab_h], radius=int(7*scale), fill=cfg['tab_bg'])
            d.text((tab_x + tab_w/2, tab_y + tab_h/2 - int(0.5*scale)), "Transkrypcja", fill=cfg['text'], font=fnt_tab, anchor="mm")

            # Przycisk ✕ (zamknij panel)
            close_px = px + pw - int(16 * scale)
            close_py = py + int(16 * scale)
            if self._hover_target == 'btn_panel_close':
                d.ellipse([close_px - int(8*scale), close_py - int(8*scale), close_px + int(8*scale), close_py + int(8*scale)], fill=(128, 145, 175, 45))
            d.text((close_px, close_py - int(1*scale)), "×", fill=cfg['muted'], font=fnt_close, anchor="mm")

            # Linie transkrypcji
            with self._lock:
                lines = list(self.transcript_lines)
                live_text = self.live_tail

            if not lines and not live_text:
                d.text((px + pw/2, py + head_h + int(36 * scale)), "Transkrypcja pojawi się tutaj podczas mówienia.", fill=cfg['muted'], font=fnt_text, anchor="mm")
            else:
                display_items = []
                for item in lines[-3:]:
                    display_items.append({"t": item.get("t", 0), "text": item.get("text", "")})

                if live_text and (not display_items or self.mode in ("recording", "transcribing")):
                    cur_t = timer_s
                    display_items.append({"t": cur_t, "text": live_text, "live": True})
                    if len(display_items) > 3:
                        display_items = display_items[-3:]

                cur_y = py + head_h + int(8 * scale)
                for i, item in enumerate(display_items):
                    t_val = item.get("t", 0)
                    time_str = f"{t_val//60:02d}:{t_val%60:02d}"
                    d.text((px + int(10 * scale), cur_y), time_str, fill=cfg['muted'], font=fnt_time)

                    tx_x = px + int(39 * scale)
                    # Zawijanie wierszy tekstu
                    words = item.get("text", "").split()
                    l_lines = []
                    c_line = []
                    for w in words:
                        c_line.append(w)
                        if len(" ".join(c_line)) > 30:
                            l_lines.append(" ".join(c_line))
                            c_line = []
                    if c_line:
                        l_lines.append(" ".join(c_line))
                    if not l_lines:
                        l_lines = [""]
                    if len(l_lines) > 2:
                        l_lines = l_lines[:2]

                    for l_idx, tl in enumerate(l_lines):
                        d.text((tx_x, cur_y + l_idx * int(12 * scale)), tl, fill=cfg['text'], font=fnt_text)

                    # Karetka | na końcu ostatniej linii
                    if i == len(display_items) - 1 and (self.mode in ("recording", "transcribing") or item.get("live")):
                        last_line = l_lines[-1]
                        bbox = d.textbbox((tx_x, cur_y + (len(l_lines)-1) * int(12 * scale)), last_line, font=fnt_text)
                        caret_x = bbox[2] + int(2 * scale)
                        caret_y = bbox[1] + int(1 * scale)
                        # Miganie karetki (0.5s)
                        if int(t_now * 2) % 2 == 0:
                            d.rounded_rectangle([caret_x, caret_y, caret_x + int(2.5 * scale), caret_y + int(9 * scale)], radius=int(1*scale), fill=cfg['accent'])

                    cur_y += max(int(26 * scale), len(l_lines) * int(13 * scale) + int(2 * scale))

            # Pasek przewijania
            sb_x = px + pw - int(8 * scale)
            sb_y = py + head_h + int(6 * scale)
            sb_w = int(3.5 * scale)
            sb_h = int(76 * scale)
            d.rounded_rectangle([sb_x, sb_y, sb_x + sb_w, sb_y + sb_h], radius=int(sb_w/2), fill=cfg['scroll_track'])
            thumb_h = int(34 * scale)
            d.rounded_rectangle([sb_x, sb_y + int(10*scale), sb_x + sb_w, sb_y + int(10*scale) + thumb_h], radius=int(sb_w/2), fill=cfg['scroll_thumb'])

        else:
            # Panel zwinięty: przycisk "Pokaż transkrypcję"
            tgl_x = int((self.mx + self.mw//2) * scale)
            tgl_y = int((self.my - 14) * scale)
            tgl_w = int(88 * scale)
            tgl_h = int(18 * scale)
            tgl_fill = (35, 48, 75, 240) if self._hover_target == 'btn_panel_open' else cfg['panel_bg']
            d.rounded_rectangle([tgl_x - tgl_w/2, tgl_y - tgl_h/2, tgl_x + tgl_w/2, tgl_y + tgl_h/2], radius=int(9*scale), fill=tgl_fill, outline=cfg['panel_border'])
            d.text((tgl_x, tgl_y - int(0.5*scale)), "Pokaż transkrypcję", fill=cfg['text'], font=fnt_time, anchor="mm")

        # ========================================================
        # 2. MODUŁ GŁÓWNY (Voice Module 250x90 px)
        # ========================================================
        mx = int(self.mx * scale)
        my = int(self.my * scale)
        mw = int(self.mw * scale)
        mh = int(self.mh * scale)
        mr = int(self.mod_r * scale)

        # Cień modułu
        sh_m = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        smd = ImageDraw.Draw(sh_m)
        smd.rounded_rectangle([mx, my + int(5*scale), mx + mw, my + mh + int(8*scale)], radius=mr, fill=(0, 0, 0, cfg['shadow_alpha']))
        sh_m = sh_m.filter(ImageFilter.GaussianBlur(radius=int(7*scale)))
        img.alpha_composite(sh_m)

        d = ImageDraw.Draw(img)
        d.rounded_rectangle([mx, my, mx + mw, my + mh], radius=mr, fill=cfg['panel_bg'], outline=cfg['panel_border'], width=max(1, int(1.1*scale)))

        # Subtelne radialne podświetlenie
        glow_mod = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        gmd = ImageDraw.Draw(glow_mod)
        gmd.ellipse([mx - int(20*scale), my, mx + int(80*scale), my + mh], fill=(105, 157, 255, 18))
        gmd.ellipse([mx + mw - int(80*scale), my, mx + mw + int(20*scale), my + mh], fill=(178, 112, 255, 16))
        glow_mod = glow_mod.filter(ImageFilter.GaussianBlur(radius=int(10*scale)))
        img.alpha_composite(glow_mod)
        d = ImageDraw.Draw(img)

        # Uchwyt (Drag Handle) na górze: 29x3 px
        hx = int(self.handle_x * scale)
        hy = int(self.handle_y * scale)
        hw = int(self.handle_w * scale)
        hh = int(self.handle_h * scale)
        d.rounded_rectangle([hx, hy, hx + hw, hy + hh], radius=int(hh/2), fill=cfg['muted'])

        # Przycisk Zamknij ✕ modułu
        cx = int(self.close_cx * scale)
        cy = int(self.close_cy * scale)
        if self._hover_target == 'btn_close':
            d.ellipse([cx - int(8*scale), cy - int(8*scale), cx + int(8*scale), cy + int(8*scale)], fill=(128, 145, 175, 45))
        d.text((cx, cy), "×", fill=cfg['muted'], font=fnt_close, anchor="mm")

        # Koordynaty przycisków
        mic_x = int(self.mic_cx * scale)
        mic_y = int(self.mic_cy * scale)
        b_rad = int(self.mic_rad * scale)

        meet_x = int(self.meet_cx * scale)
        meet_y = int(self.meet_cy * scale)

        # --- PRZYCISK 1: MIKROFON (Lewy) ---
        if self.mode == "recording":
            # Czerwony aktywny przycisk z pulsującym pierścieniem
            p_factor = 0.5 + 0.5 * math.sin(t_now * 5.0)
            glow_rad = int(b_rad + (5 + p_factor * 3.5) * scale)
            glow_m = Image.new('RGBA', (W, H), (0, 0, 0, 0))
            gmd = ImageDraw.Draw(glow_m)
            gmd.ellipse([mic_x - glow_rad, mic_y - glow_rad, mic_x + glow_rad, mic_y + glow_rad], fill=(255, 34, 52, int(45 + p_factor * 25)))
            glow_m = glow_m.filter(ImageFilter.GaussianBlur(radius=int(5*scale)))
            img.alpha_composite(glow_m)
            d = ImageDraw.Draw(img)

            d.ellipse([mic_x - b_rad, mic_y - b_rad, mic_x + b_rad, mic_y + b_rad], fill=(255, 51, 73, 255))
            draw_svg_mic(d, mic_x, mic_y, sz=int(22 * scale), color=(255, 255, 255, 255))

        elif self.mode == "processing":
            # Bursztynowy przycisk finalizacji
            d.ellipse([mic_x - b_rad, mic_y - b_rad, mic_x + b_rad, mic_y + b_rad], fill=(245, 158, 11, 255))
            draw_svg_mic(d, mic_x, mic_y, sz=int(22 * scale), color=(255, 255, 255, 255))

        else:
            # W spoczynku: ciemny okrąg z białym pierścieniem zewnętrznym
            d.ellipse([mic_x - b_rad, mic_y - b_rad, mic_x + b_rad, mic_y + b_rad],
                      fill=cfg['mic_standby_bg'], outline=cfg['mic_standby_border'], width=max(1, int(1.8 * scale)))
            draw_svg_mic(d, mic_x, mic_y, sz=int(22 * scale), color=(255, 255, 255, 255))

        # --- PRZYCISK 2: SPOTKANIE (Prawy) ---
        if self.mode == "transcribing":
            # Niebieski aktywny przycisk z poświatą
            p_factor = 0.5 + 0.5 * math.sin(t_now * 5.0)
            glow_rad = int(b_rad + (5 + p_factor * 4.0) * scale)
            glow_mt = Image.new('RGBA', (W, H), (0, 0, 0, 0))
            gmd = ImageDraw.Draw(glow_mt)
            gmd.ellipse([meet_x - glow_rad, meet_y - glow_rad, meet_x + glow_rad, meet_y + glow_rad], fill=(46, 94, 255, int(50 + p_factor * 25)))
            glow_mt = glow_mt.filter(ImageFilter.GaussianBlur(radius=int(6*scale)))
            img.alpha_composite(glow_mt)
            d = ImageDraw.Draw(img)

            d.ellipse([meet_x - b_rad, meet_y - b_rad, meet_x + b_rad, meet_y + b_rad], fill=(64, 92, 242, 255))
            draw_people_icon(d, meet_x, meet_y, sz=int(26 * scale), color=(255, 255, 255, 255))

        else:
            d.ellipse([meet_x - b_rad, meet_y - b_rad, meet_x + b_rad, meet_y + b_rad], fill=cfg['meet_standby_bg'])
            draw_people_icon(d, meet_x, meet_y, sz=int(26 * scale), color=(255, 255, 255, 200))

        # --- SEKCJA ŚRODKOWA: FALA DŹWIĘKOWA (dokładnie 80px) ---
        center_cx = mx + mw // 2
        wave_cy = my + int(36 * scale)

        num_bars = len(BAR_HEIGHTS)
        bar_w = 1.6 * scale
        bar_gap = 1.4 * scale
        total_wave_w = num_bars * bar_w + (num_bars - 1) * bar_gap
        start_bx = center_cx - total_wave_w / 2.0

        active_vol = vol if self.mode == "recording" else max(vol, loop_vol)

        bar_color = cfg['danger'] if self.mode == "recording" else (cfg['text'] if self.mode == "transcribing" else cfg['wave'])

        for i, h_vals in enumerate(BAR_HEIGHTS):
            bx = start_bx + i * (bar_w + bar_gap)
            if self.mode in ("recording", "transcribing"):
                # Naturalna wielotonowa modulacja wysokości słupków
                a = 1.0 + 0.23 * math.sin(t_now * 7.0 + i * 0.78) + 0.16 * math.sin(t_now * 12.7 - i * 0.41) + 0.10 * math.sin(t_now * 3.6 + i * 1.13)
                base_h = h_vals[1] if self.mode == "recording" else h_vals[0]
                eff_h = max(5, min(36, base_h * a * (0.8 + active_vol * 1.5))) * scale
            else:
                eff_h = h_vals[0] * scale

            by1 = wave_cy - eff_h / 2.0
            by2 = wave_cy + eff_h / 2.0
            d.rounded_rectangle([bx, by1, bx + bar_w, by2], radius=int(bar_w/2), fill=bar_color)

        # Pasek statusu pod falą: [dot] [statusText] [timer]
        status_y = my + int(64 * scale)

        if self.mode == "recording":
            dot_col = cfg['danger']
            status_lbl = "Nagrywanie"
            status_col = cfg['danger']
        elif self.mode == "transcribing":
            dot_col = (77, 115, 255, 255)
            status_lbl = "Transkrypcja"
            status_col = (77, 115, 255, 255)
        elif self.mode == "processing":
            dot_col = (245, 158, 11, 255)
            status_lbl = "Przetwarzanie..."
            status_col = (245, 158, 11, 255)
        else:
            dot_col = cfg['muted']
            status_lbl = "Gotowe"
            status_col = cfg['muted']

        timer_str = f"{timer_s//60:02d}:{timer_s%60:02d}"

        dot_d = int(4 * scale)
        lbl_bbox = d.textbbox((0, 0), status_lbl, font=fnt_status)
        lbl_w = lbl_bbox[2] - lbl_bbox[0]
        tim_bbox = d.textbbox((0, 0), timer_str, font=fnt_timer)
        tim_w = tim_bbox[2] - tim_bbox[0]

        spacing = int(5 * scale)
        total_line_w = dot_d + spacing + lbl_w + spacing + tim_w
        line_start_x = center_cx - total_line_w / 2.0

        d_x = line_start_x
        d_y = status_y + int(4 * scale)
        d.ellipse([d_x, d_y, d_x + dot_d, d_y + dot_d], fill=dot_col)

        tx_x = d_x + dot_d + spacing
        d.text((tx_x, status_y), status_lbl, fill=status_col, font=fnt_status)

        tm_x = tx_x + lbl_w + spacing
        d.text((tm_x, status_y), timer_str, fill=cfg['text'], font=fnt_timer)

        # ========================================================
        # 3. AKTUALIZACJA OKNA WARSTWOWEGO
        # ========================================================
        smooth = img.resize((self.w, self.h), Image.Resampling.LANCZOS)
        arr = np.array(smooth, dtype=np.uint8)
        r = arr[:, :, 0].astype(np.uint32)
        g = arr[:, :, 1].astype(np.uint32)
        b = arr[:, :, 2].astype(np.uint32)
        a = arr[:, :, 3].astype(np.uint32)
        bgra = np.zeros_like(arr)
        bgra[:, :, 0] = ((b * a) // 255).astype(np.uint8)
        bgra[:, :, 1] = ((g * a) // 255).astype(np.uint8)
        bgra[:, :, 2] = ((r * a) // 255).astype(np.uint8)
        bgra[:, :, 3] = a.astype(np.uint8)
        bgra = np.ascontiguousarray(np.flipud(bgra))

        ctypes.memmove(self.p_bits, bgra.ctypes.data, bgra.nbytes)

        screen_dc = user32.GetDC(0)
        blend = BLENDFUNCTION(0, 0, 255, 1)
        pt_src = wintypes.POINT(0, 0)
        size = wintypes.SIZE(self.w, self.h)
        user32.UpdateLayeredWindow(
            self.hwnd, screen_dc, None, ctypes.byref(size),
            self.mem_dc, ctypes.byref(pt_src), 0, ctypes.byref(blend), 2
        )
        user32.ReleaseDC(0, screen_dc)

    # ========================================================
    # METODY PUBLICZNE (STEROWANIE STANEM)
    # ========================================================
    def show_recording(self):
        self.mode = "recording"
        self._start_time = time.time()
        self.live_tail = ""
        self.panel_open = True
        self._balloon_type = None
        self._dirty = True
        self.show()

    def show_idle(self):
        self.mode = "idle"
        self._start_time = 0.0
        self.live_tail = ""
        self._balloon_type = None
        self._dirty = True
        self.show()

    def show_processing(self):
        self.mode = "processing"
        self._dirty = True
        self.show()

    def show_meeting_recording(self):
        self.mode = "transcribing"
        self._start_time = time.time()
        self.live_tail = ""
        self.panel_open = True
        self._balloon_type = None
        self._dirty = True
        self.show()

    def show_error_balloon(self, duration_s=7.0):
        self._balloon_type = "error"
        self._balloon_until = time.time() + duration_s if duration_s > 0 else 0
        self._dirty = True
        self.show()

    def hide_balloon(self):
        self._balloon_type = None
        self._balloon_until = 0
        self._dirty = True

    def update_live_text(self, text: str):
        if text:
            with self._lock:
                self.live_tail = text.strip()
            self._dirty = True

    def add_transcript_entry(self, text: str, timestamp_s: float = None):
        if not text:
            return
        with self._lock:
            t = int(timestamp_s if timestamp_s is not None else (time.time() - self._start_time if self._start_time > 0 else 0))
            self.transcript_lines.append({"t": max(0, t), "text": text.strip()})
            if len(self.transcript_lines) > 50:
                self.transcript_lines = self.transcript_lines[-50:]
            self.live_tail = ""
        self._dirty = True

    def clear_transcript(self):
        with self._lock:
            self.transcript_lines = []
            self.live_tail = ""
        self._dirty = True

    def show(self):
        self._visible = True
        self._dirty = True
        if self.hwnd:
            user32.ShowWindow(self.hwnd, 8)
            user32.SetWindowPos(self.hwnd, -1, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010)

    def hide(self):
        self._visible = False
        self._dirty = True
        if self.hwnd:
            user32.ShowWindow(self.hwnd, 0)

    def set_theme(self, theme_name: str):
        if theme_name in THEME_MAP:
            theme_name = THEME_MAP[theme_name]
        if theme_name in THEMES and theme_name != self.theme:
            self.theme = theme_name
            self._dirty = True
            if self.on_theme_changed:
                try: self.on_theme_changed(self.theme)
                except Exception: pass

    def is_alive(self):
        return self._thread is not None and self._thread.is_alive()

    def stop(self):
        self.close()

    def close(self):
        self._running = False
        if self.hwnd and user32.IsWindow(self.hwnd):
            user32.PostMessageW(self.hwnd, 0x0010, 0, 0)
