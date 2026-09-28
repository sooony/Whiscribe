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

user32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
user32.ClientToScreen.restype = wintypes.BOOL

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

# Włączenie pełnej świadomości DPI dla ostrości i prawidłowego pozycjonowania okna
try:
    user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
except Exception:
    try:
        user32.SetProcessDPIAware()
    except Exception:
        pass

WINDIR = os.environ.get('WINDIR', 'C:\\Windows')
FONT_REGULAR_PATH = os.path.join(WINDIR, 'Fonts', 'segoeui.ttf')
FONT_BOLD_PATH = os.path.join(WINDIR, 'Fonts', 'segoeuib.ttf')

THEMES = {
    'light': {
        'name': 'Windows 11 Jasny (Fluent Light)',
        'card_fill': (243, 243, 243, 250),
        'card_border': (222, 222, 222, 220),
        'hdr_sep': (230, 230, 230, 180),
        'handle_col': (155, 155, 155, 200),
        'icon_col': (85, 85, 85, 240),
        'icon_hover_bg': (0, 0, 0, 18),
        'mic_bg': (255, 255, 255, 255),
        'mic_border': (226, 226, 226, 240),
        'mic_icon_col': (50, 50, 50, 255),
        'ball_bg': (255, 255, 255, 255),
        'ball_border': (228, 228, 228, 255),
        'ball_text': (32, 32, 32, 255),
        'btn_bg': (255, 255, 255, 255),
        'btn_hover_bg': (242, 242, 242, 255),
        'btn_border': (208, 208, 208, 255),
        'btn_text': (32, 32, 32, 255),
        'accent': (0, 103, 192),
        'shadow_alpha': 45
    },
    'dark': {
        'name': 'Windows 11 Ciemny (Fluent Dark)',
        'card_fill': (38, 38, 38, 250),
        'card_border': (65, 65, 65, 220),
        'hdr_sep': (52, 52, 52, 200),
        'handle_col': (130, 130, 130, 200),
        'icon_col': (205, 205, 205, 240),
        'icon_hover_bg': (255, 255, 255, 25),
        'mic_bg': (52, 52, 52, 255),
        'mic_border': (75, 75, 75, 240),
        'mic_icon_col': (245, 245, 245, 255),
        'ball_bg': (44, 44, 44, 255),
        'ball_border': (70, 70, 70, 255),
        'ball_text': (240, 240, 240, 255),
        'btn_bg': (56, 56, 56, 255),
        'btn_hover_bg': (68, 68, 68, 255),
        'btn_border': (80, 80, 80, 255),
        'btn_text': (240, 240, 240, 255),
        'accent': (76, 194, 255),
        'shadow_alpha': 85
    }
}

# Mapowanie starych motywów
THEME_MAP = {
    'glass_light': 'light',
    'minimal': 'light',
    'glass_dark': 'dark',
    'cyber_neon': 'dark',
    'nordic_titanium': 'light'
}

def draw_screenshot_mic(d, cx, cy, sz, is_muted=False, color=(255, 255, 255, 255)):
    """
    Wektorowa ikona mikrofonu odwzorowana 1:1 ze zrzutu ekranu użytkownika.
    - is_muted=True: przekreślony mikrofon na czerwonym tle (stan oczekiwania / wyłączony)
    - is_muted=False: czysty mikrofon na niebieskim tle (stan nagrywania / mówienia)
    """
    cap_w = sz * 0.36
    cap_h = sz * 0.60
    cap_r = cap_w / 2.0
    cap_cy = cy - sz * 0.08

    # 1. Kapsułka mikrofonu
    d.rounded_rectangle(
        [cx - cap_w/2, cap_cy - cap_h/2, cx + cap_w/2, cap_cy + cap_h/2],
        radius=cap_r,
        fill=color
    )

    # 2. Koszyczek (cradle)
    cradle_r = sz * 0.33
    line_w = max(2, int(sz * 0.095))
    cradle_top_y = cap_cy
    cradle_bot_y = cap_cy + cradle_r

    d.arc(
        [cx - cradle_r, cap_cy - cradle_r, cx + cradle_r, cap_cy + cradle_r],
        start=0, end=180,
        fill=color, width=line_w
    )
    d.line([(cx - cradle_r, cap_cy), (cx - cradle_r, cradle_top_y)], fill=color, width=line_w)
    d.line([(cx + cradle_r, cap_cy), (cx + cradle_r, cradle_top_y)], fill=color, width=line_w)
    rc = line_w / 2.0
    d.ellipse([cx - cradle_r - rc, cradle_top_y - rc, cx - cradle_r + rc, cradle_top_y + rc], fill=color)
    d.ellipse([cx + cradle_r - rc, cradle_top_y - rc, cx + cradle_r + rc, cradle_top_y + rc], fill=color)

    # 3. Nóżka pionowa
    stem_top = cradle_bot_y
    stem_bot = stem_top + sz * 0.18
    d.line([(cx, stem_top), (cx, stem_bot)], fill=color, width=line_w)

    # 4. Podstawka pozioma
    base_w = sz * 0.38
    d.line([(cx - base_w/2, stem_bot), (cx + base_w/2, stem_bot)], fill=color, width=line_w)
    d.ellipse([cx - base_w/2 - rc, stem_bot - rc, cx - base_w/2 + rc, stem_bot + rc], fill=color)
    d.ellipse([cx + base_w/2 - rc, stem_bot - rc, cx + base_w/2 + rc, stem_bot + rc], fill=color)

    # 5. Przekreślenie ukośną kreską (dla stanu oczekiwania / wyciszenia)
    if is_muted:
        slash_w = max(2, int(sz * 0.10))
        sx1 = cx - sz * 0.46
        sy1 = cy + sz * 0.40
        sx2 = cx + sz * 0.46
        sy2 = cy - sz * 0.50
        d.line([(sx1, sy1), (sx2, sy2)], fill=color, width=slash_w)
        r_cap = slash_w / 2.0
        d.ellipse([sx1 - r_cap, sy1 - r_cap, sx1 + r_cap, sy1 + r_cap], fill=color)
        d.ellipse([sx2 - r_cap, sy2 - r_cap, sx2 + r_cap, sy2 + r_cap], fill=color)


def draw_meeting_icon(d, cx, cy, sz, is_recording=False, color=(255, 255, 255, 255)):
    """
    Wektorowa ikona spotkania (👥 sylwetki ludzi w trybie oczekiwania, ⏹ stop w trybie nagrywania spotkania).
    """
    if is_recording:
        # Kwadrat STOP z zaokrąglonymi rogami
        sq_sz = sz * 0.36
        r = max(2, int(sz * 0.08))
        d.rounded_rectangle([cx - sq_sz, cy - sq_sz, cx + sq_sz, cy + sq_sz], radius=r, fill=color)
    else:
        # Dwie eleganckie nakładające się sylwetki ludzi (Ja + Uczestnik)
        r_head = sz * 0.17
        # Lewa osoba
        lx = cx - sz * 0.16
        ly_head = cy - sz * 0.12
        d.ellipse([lx - r_head, ly_head - r_head, lx + r_head, ly_head + r_head], fill=color)
        d.chord([lx - sz * 0.32, ly_head + r_head * 0.6, lx + sz * 0.32, ly_head + r_head * 2.8], start=180, end=360, fill=color)

        # Prawa osoba
        rx = cx + sz * 0.18
        ry_head = cy - sz * 0.08
        d.ellipse([rx - r_head * 0.85, ry_head - r_head * 0.85, rx + r_head * 0.85, ry_head + r_head * 0.85], fill=color)
        d.chord([rx - sz * 0.28, ry_head + r_head * 0.7, rx + sz * 0.28, ry_head + r_head * 2.6], start=180, end=360, fill=color)


class FloatingOverlay:
    """
    Wiernie odwzorowany widżet Wpisywania Głosowego Windows 11 (Voice Typing Win+H).
    - Rozmiar, układ i elementy graficzne 1:1 ze zrzutem ekranu Windows 11
    - Dymek błędu ("Aby używać wpisywania głosowego, zaznacz pole tekstowe i spróbuj ponownie.")
    - Przycisk "Rozumiem" do natychmiastowego zamykania
    - Przycisk Ustawienia ⚙ z menu kontekstowym
    - Przycisk Pomoc ? z podpowiedziami
    - Płynne przeciąganie oknem, niekradnący fokusu (WS_EX_NOACTIVATE, MA_NOACTIVATE)
    - Dynamiczne animacje głosu w czasie rzeczywistym
    """

    def __init__(self, theme='light'):
        self.hwnd = None
        self._thread = None
        self._ready_event = threading.Event()
        self._running = True

        # Dopasowanie motywu
        if theme in THEME_MAP:
            theme = THEME_MAP[theme]
        self.theme = theme if theme in THEMES else 'light'
        self.on_theme_changed = None

        # Stan pracy: "idle", "recording", "processing"
        self.mode = "idle"
        self._visible = True
        self._hover_target = None
        self._pressed_btn = None
        self.volume_getter = lambda: 0.0

        # Dymek powiadomień (dymek błędu jak ze zrzutu ekranu lub pomoc)
        self._balloon_type = None  # None, "error", "help", "info", "live", "processing"
        self._balloon_message = None
        self._balloon_until = 0.0
        self.live_text = ""
        self.show_live_preview = False
        self._dirty = True

        # Callbacki do logiki aplikacji
        self.on_stop_callback = None
        self.on_close_callback = None
        self.on_toggle_callback = None
        self.on_meeting_toggle_callback = None
        self.settings_handler = None
        self.loopback_volume_getter = lambda: 0.0

        # Wymiary całego okna (mieści dymek powyżej oraz widżet poniżej)
        self.w = 280
        self.h = 196

        # Wymiary i współrzędne widżetu dolnego (rozszerzony pod 2 przyciski: Dyktowanie 🎙️ + Spotkanie 👥)
        self.ww = 144
        self.wh = 74
        self.wx = (self.w - self.ww) // 2       # 68
        self.wy = self.h - self.wh - 8          # 114
        self.card_r = 14

        # Pasek nagłówka widżetu
        self.hdr_h = 18
        self.handle_w = 26
        self.handle_h = 3
        self.handle_x = self.wx + (self.ww - self.handle_w) / 2
        self.handle_y = self.wy + 6.5

        # Przycisk Zamknij ✕
        self.close_cx = self.wx + self.ww - 13
        self.close_cy = self.wy + 9

        # Lewy przycisk: Mikrofon (Dyktowanie)
        self.mic_cx = self.wx + 36
        self.mic_cy = self.wy + 42
        self.mic_rad = 19

        # Prawy przycisk: Spotkanie (Mity)
        self.meet_cx = self.wx + self.ww - 36
        self.meet_cy = self.wy + 42
        self.meet_rad = 19

        # Geometria dymka
        self.bw = 260
        self.bh = 96
        self.bx = (self.w - self.bw) // 2        # 10
        self.by = self.wy - self.bh - 8          # 10
        self.ball_r = 10
        self.btn_w = self.bw - 32
        self.btn_h = 26
        self.btn_x = self.bx + 16
        self.btn_y = self.by + self.bh - self.btn_h - 10

        # Domyślne wycentrowanie na dole ekranu
        screen_w = user32.GetSystemMetrics(0)
        screen_h = user32.GetSystemMetrics(1)
        self.pos_x = (screen_w - self.w) // 2
        self.pos_y = screen_h - self.h - 60

        # Przeciąganie okna
        self._is_dragging = False
        self._drag_start_cursor_x = 0
        self._drag_start_cursor_y = 0
        self._drag_start_win_x = 0
        self._drag_start_win_y = 0

        # Kursory systemowe
        self._hcursor_arrow = user32.LoadCursorW(None, 32512)
        self._hcursor_hand = user32.LoadCursorW(None, 32649)
        self._hcursor_move = user32.LoadCursorW(None, 32646)

        # Bufor DIB do UpdateLayeredWindow
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

    def _is_inside_balloon(self, x, y):
        if not self._balloon_type:
            return False
        return (self.bx - 4 <= x <= self.bx + self.bw + 4) and (self.by - 4 <= y <= self.by + self.bh + 12)

    def _is_inside_widget(self, x, y):
        return (self.wx - 2 <= x <= self.wx + self.ww + 2) and (self.wy - 2 <= y <= self.wy + self.wh + 2)

    def _get_target(self, x, y):
        # 1. Sprawdź przyciski w dymku (jeśli dymek jest widoczny)
        if self._balloon_type:
            if self._balloon_type not in ('live', 'processing') and (self.btn_x <= x <= self.btn_x + self.btn_w) and (self.btn_y <= y <= self.btn_y + self.btn_h):
                return 'btn_rozumiem'
            if self._is_inside_balloon(x, y):
                return 'balloon_body'

        # 2. Sprawdź kontrolki w widżecie
        if not self._is_inside_widget(x, y):
            return None

        # Mikrofon (lewy przycisk)
        d_mic = (x - self.mic_cx)**2 + (y - self.mic_cy)**2
        if d_mic <= (self.mic_rad + 3)**2:
            return 'btn_mic'

        # Spotkanie (prawy przycisk)
        d_meet = (x - self.meet_cx)**2 + (y - self.meet_cy)**2
        if d_meet <= (self.meet_rad + 3)**2:
            return 'btn_meeting'

        # Zamknij ✕
        if abs(x - self.close_cx) <= 12 and abs(y - self.close_cy) <= 12:
            return 'btn_close'

        # Uchwyt lub reszta korpusu do przeciągania
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
            # NIE POZWÓL, aby kliknięcie w widżet ukradło fokus z aktywnego edytora/pola tekstowego!
            return MA_NOACTIVATE

        if msg == WM_NCHITTEST:
            x = lparam & 0xFFFF
            y = (lparam >> 16) & 0xFFFF
            if x > 0x7FFF: x -= 0x10000
            if y > 0x7FFF: y -= 0x10000
            pt = wintypes.POINT(x, y)
            user32.ScreenToClient(hwnd, ctypes.byref(pt))

            if self._is_inside_widget(pt.x, pt.y) or self._is_inside_balloon(pt.x, pt.y):
                return 1  # HTCLIENT
            return -1  # HTTRANSPARENT (kliknięcia obok przelatują do okna pod spodem!)

        elif msg == WM_MOUSEMOVE:
            tme = TRACKMOUSEEVENT()
            tme.cbSize = ctypes.sizeof(TRACKMOUSEEVENT)
            tme.dwFlags = 2  # TME_LEAVE
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
                    0x0001 | 0x0004 | 0x0010  # SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE
                )
            else:
                target = self._get_target(x, y)
                if target != self._hover_target:
                    self._hover_target = target
            return 0

        elif msg == WM_MOUSELEAVE:
            self._hover_target = None
            return 0

        elif msg == WM_SETCURSOR:
            if self._hover_target in ('btn_mic', 'btn_meeting', 'btn_close', 'btn_rozumiem'):
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
                    elif self.mode == "meeting_recording":
                        if self.on_meeting_toggle_callback:
                            threading.Thread(target=self.on_meeting_toggle_callback, daemon=True).start()
                    else:
                        if self.on_toggle_callback:
                            threading.Thread(target=self.on_toggle_callback, daemon=True).start()

                elif target == 'btn_meeting':
                    if self.mode == "meeting_recording":
                        if self.on_meeting_toggle_callback:
                            threading.Thread(target=self.on_meeting_toggle_callback, daemon=True).start()
                    elif self.mode == "recording":
                        if self.on_stop_callback:
                            threading.Thread(target=self.on_stop_callback, daemon=True).start()
                    else:
                        if self.on_meeting_toggle_callback:
                            threading.Thread(target=self.on_meeting_toggle_callback, daemon=True).start()

                elif target == 'btn_rozumiem':
                    # Zamknięcie dymka powiadomienia
                    self.hide_balloon()

                elif target == 'btn_close':
                    if self.mode == "recording":
                        if self.on_close_callback:
                            threading.Thread(target=self.on_close_callback, daemon=True).start()
                    elif self.mode == "meeting_recording":
                        if self.on_meeting_toggle_callback:
                            threading.Thread(target=self.on_meeting_toggle_callback, daemon=True).start()
                    else:
                        self.hide()

            self._pressed_btn = None
            return 0

        elif msg == WM_RBUTTONUP:
            # Menu ustawień dostępne po kliknięciu prawym przyciskiem myszy w widżet
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
            wc.style = 3  # CS_HREDRAW | CS_VREDRAW
            wc.lpfnWndProc = self._proc
            wc.hInstance = kernel32.GetModuleHandleW(None)
            wc.hCursor = self._hcursor_arrow
            wc.lpszClassName = "Win11VoiceTypingOverlayClass"

            user32.RegisterClassExW(ctypes.byref(wc))

            WS_EX_LAYERED = 0x00080000
            WS_EX_TOPMOST = 0x00000008
            WS_EX_TOOLWINDOW = 0x00000080
            WS_EX_NOACTIVATE = 0x08000000
            WS_POPUP = 0x80000000

            self.hwnd = user32.CreateWindowExW(
                WS_EX_LAYERED | WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE,
                "Win11VoiceTypingOverlayClass",
                "Win11VoiceTypingOverlay",
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
                user32.ShowWindow(self.hwnd, 8)  # SW_SHOWNA = 8
                user32.SetWindowPos(self.hwnd, -1, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010)

            self._ready_event.set()

            # Renderuj natychmiast pierwszą klatkę (stan czuwania)
            self._dirty = True
            self._render_frame(time.time())

            msg = wintypes.MSG()
            last_frame_time = time.time()
            prev_hover = self._hover_target

            # Inteligentna pętla renderowania: 33 FPS w trakcie nagrywania/przetwarzania, 0% CPU w stanie czuwania
            while self._running:
                while user32.PeekMessageW(ctypes.byref(msg), self.hwnd, 0, 0, 1):
                    user32.TranslateMessage(ctypes.byref(msg))
                    user32.DispatchMessageW(ctypes.byref(msg))

                now = time.time()
                elapsed = now - last_frame_time
                if elapsed < 0.030:
                    time.sleep(max(0.001, 0.030 - elapsed))
                    continue

                # Auto-dismiss dymka
                if self._balloon_type and self._balloon_until > 0 and now > self._balloon_until:
                    self._balloon_type = None
                    self._dirty = True

                if self._hover_target != prev_hover:
                    self._dirty = True
                    prev_hover = self._hover_target

                needs_continuous_anim = (self.mode in ("recording", "processing")) or self._is_dragging

                if self._visible and self.hwnd and (needs_continuous_anim or self._dirty):
                    self._dirty = False
                    last_frame_time = time.time()
                    self._render_frame(last_frame_time)
                else:
                    time.sleep(0.025)

        except Exception as e:
            import logging
            logging.getLogger("Overlay").error(f"Krytyczny błąd w wątku UI widżetu: {e}", exc_info=True)
        finally:
            self._ready_event.set()
            if self.mem_dc and self.old_bmp:
                try:
                    gdi32.SelectObject(self.mem_dc, self.old_bmp)
                except Exception:
                    pass
            if self.h_bmp:
                try:
                    gdi32.DeleteObject(self.h_bmp)
                except Exception:
                    pass
            if self.mem_dc:
                try:
                    gdi32.DeleteDC(self.mem_dc)
                except Exception:
                    pass

    def _render_frame(self, t_now):
        cfg = THEMES.get(self.theme, THEMES['light'])
        scale = 2  # supersampling 2x dla nieskazitelnej ostrości
        W, H = self.w * scale, self.h * scale

        img = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)

        wx, wy = int(self.wx * scale), int(self.wy * scale)
        ww, wh = int(self.ww * scale), int(self.wh * scale)
        card_r = int(self.card_r * scale)

        # 1. Cień widżetu
        shadow = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        sd = ImageDraw.Draw(shadow)
        sd.rounded_rectangle(
            [wx, wy + int(4*scale), wx + ww, wy + wh + int(6*scale)],
            radius=card_r,
            fill=(0, 0, 0, cfg['shadow_alpha'])
        )
        shadow = shadow.filter(ImageFilter.GaussianBlur(radius=int(4*scale)))
        img.alpha_composite(shadow)
        d = ImageDraw.Draw(img)

        # 2. Korpus widżetu
        d.rounded_rectangle([wx, wy, wx + ww, wy + wh], radius=card_r, fill=cfg['card_fill'], outline=cfg['card_border'], width=max(1, int(1.1*scale)))

        # Pasek nagłówka
        hdr_h = int(self.hdr_h * scale)
        d.line([(wx + int(8*scale), wy + hdr_h), (wx + ww - int(8*scale), wy + hdr_h)], fill=cfg['hdr_sep'], width=max(1, int(1*scale)))

        # Uchwyt do przeciągania
        hx = int(self.handle_x * scale)
        hy = int(self.handle_y * scale)
        hw = int(self.handle_w * scale)
        hh = int(self.handle_h * scale)
        d.rounded_rectangle([hx, hy, hx + hw, hy + hh], radius=int(hh/2), fill=cfg['handle_col'])

        # Przycisk Zamknij ✕
        cx = int(self.close_cx * scale)
        cy = int(self.close_cy * scale)
        if self._hover_target == 'btn_close':
            d.rounded_rectangle([cx - int(9*scale), cy - int(9*scale), cx + int(9*scale), cy + int(9*scale)], radius=int(4*scale), fill=cfg['icon_hover_bg'])
        x_sz = int(3.5 * scale)
        d.line([(cx - x_sz, cy - x_sz), (cx + x_sz, cy + x_sz)], fill=cfg['icon_col'], width=max(1, int(1.4*scale)))
        d.line([(cx - x_sz, cy + x_sz), (cx + x_sz, cy - x_sz)], fill=cfg['icon_col'], width=max(1, int(1.4*scale)))

        # Centralny Mikrofon oraz Przycisk Spotkania
        mx = int(self.mic_cx * scale)
        my = int(self.mic_cy * scale)
        mr = int(self.mic_rad * scale)
        sz = int(22 * scale)

        meet_x = int(self.meet_cx * scale)
        meet_y = int(self.meet_cy * scale)
        meet_r = int(self.meet_rad * scale)
        meet_sz = int(22 * scale)

        vol = 0.0
        if self.volume_getter:
            try:
                vol = float(self.volume_getter())
            except Exception:
                vol = 0.0

        loop_vol = 0.0
        if self.loopback_volume_getter:
            try:
                loop_vol = float(self.loopback_volume_getter())
            except Exception:
                loop_vol = 0.0

        # --- Renderowanie Przycisku 1: Mikrofon (Dyktowanie) ---
        if self.mode == "recording":
            # Niebieski przycisk aktywny (#2d84f8)
            wave_pulse = max(0.04, min(1.0, (vol ** 0.6) * 1.5))
            glow_rad = int(mr + (1.5 + wave_pulse * 3.5) * scale)
            glow_alpha = int(90 * wave_pulse + 25)

            glow = Image.new('RGBA', (W, H), (0, 0, 0, 0))
            gd = ImageDraw.Draw(glow)
            gd.ellipse([mx - glow_rad, my - glow_rad, mx + glow_rad, my + glow_rad], fill=(45, 132, 248, glow_alpha))
            glow = glow.filter(ImageFilter.GaussianBlur(radius=max(1, int(2.5 * scale))))
            img.alpha_composite(glow)
            d = ImageDraw.Draw(img)

            d.ellipse([mx - mr, my - mr, mx + mr, my + mr], fill=(45, 132, 248, 255))
            draw_screenshot_mic(d, mx, my, sz, is_muted=False, color=(255, 255, 255, 255))

        elif self.mode == "processing":
            # Ciepły bursztynowy przycisk przetwarzania (#f59e0b)
            pulse = 0.5 + 0.5 * math.sin(t_now * 8.0)
            glow_rad = int(mr + (1.5 + pulse * 2.5) * scale)
            glow_alpha = int(70 * pulse + 30)

            glow = Image.new('RGBA', (W, H), (0, 0, 0, 0))
            gd = ImageDraw.Draw(glow)
            gd.ellipse([mx - glow_rad, my - glow_rad, mx + glow_rad, my + glow_rad], fill=(245, 158, 11, glow_alpha))
            glow = glow.filter(ImageFilter.GaussianBlur(radius=max(1, int(2.0 * scale))))
            img.alpha_composite(glow)
            d = ImageDraw.Draw(img)

            d.ellipse([mx - mr, my - mr, mx + mr, my + mr], fill=(245, 158, 11, 255))
            draw_screenshot_mic(d, mx, my, sz, is_muted=False, color=(255, 255, 255, 255))

        elif self.mode == "meeting_recording":
            # W trybie nagrywania spotkania: stonowany mikrofon
            d.ellipse([mx - mr, my - mr, mx + mr, my + mr], fill=(70, 70, 80, 240))
            draw_screenshot_mic(d, mx, my, sz, is_muted=False, color=(200, 200, 200, 220))

        else:  # idle - Czerwony przycisk z przekreślonym mikrofonem (#ee1c25)
            mic_sh = Image.new('RGBA', (W, H), (0, 0, 0, 0))
            msd = ImageDraw.Draw(mic_sh)
            msd.ellipse([mx - mr, my - mr + int(1.5*scale), mx + mr, my + mr + int(2.5*scale)], fill=(0, 0, 0, 35))
            mic_sh = mic_sh.filter(ImageFilter.GaussianBlur(radius=int(2.0 * scale)))
            img.alpha_composite(mic_sh)
            d = ImageDraw.Draw(img)

            btn_fill = (255, 45, 55, 255) if self._hover_target == 'btn_mic' else (238, 28, 37, 255)
            d.ellipse([mx - mr, my - mr, mx + mr, my + mr], fill=btn_fill)
            draw_screenshot_mic(d, mx, my, sz, is_muted=True, color=(255, 255, 255, 255))

        # --- Renderowanie Przycisku 2: Spotkanie (Mity / Notatnik) ---
        if self.mode == "meeting_recording":
            # Aktywne indygo/fiolet (#6366f1) pulsujące w rytm dźwięku rozmówców
            active_energy = max(vol, loop_vol)
            m_pulse = max(0.06, min(1.0, (active_energy ** 0.6) * 1.6))
            m_glow_rad = int(meet_r + (2.0 + m_pulse * 4.0) * scale)
            m_glow_alpha = int(95 * m_pulse + 30)

            m_glow = Image.new('RGBA', (W, H), (0, 0, 0, 0))
            mgd = ImageDraw.Draw(m_glow)
            mgd.ellipse([meet_x - m_glow_rad, meet_y - m_glow_rad, meet_x + m_glow_rad, meet_y + m_glow_rad], fill=(99, 102, 241, m_glow_alpha))
            m_glow = m_glow.filter(ImageFilter.GaussianBlur(radius=max(1, int(2.5 * scale))))
            img.alpha_composite(m_glow)
            d = ImageDraw.Draw(img)

            meet_fill = (129, 140, 248, 255) if self._hover_target == 'btn_meeting' else (99, 102, 241, 255)
            d.ellipse([meet_x - meet_r, meet_y - meet_r, meet_x + meet_r, meet_y + meet_r], fill=meet_fill)
            # Rysuj kwadrat STOP ⏹
            draw_meeting_icon(d, meet_x, meet_y, meet_sz, is_recording=True, color=(255, 255, 255, 255))

        elif self.mode == "recording":
            # Wygaszony podczas dyktowania
            d.ellipse([meet_x - meet_r, meet_y - meet_r, meet_x + meet_r, meet_y + meet_r], fill=(60, 60, 70, 200))
            draw_meeting_icon(d, meet_x, meet_y, meet_sz, is_recording=False, color=(160, 160, 170, 200))

        else:  # idle
            meet_sh = Image.new('RGBA', (W, H), (0, 0, 0, 0))
            m_sd = ImageDraw.Draw(meet_sh)
            m_sd.ellipse([meet_x - meet_r, meet_y - meet_r + int(1.5*scale), meet_x + meet_r, meet_y + meet_r + int(2.5*scale)], fill=(0, 0, 0, 35))
            meet_sh = meet_sh.filter(ImageFilter.GaussianBlur(radius=int(2.0 * scale)))
            img.alpha_composite(meet_sh)
            d = ImageDraw.Draw(img)

            meet_fill = (129, 140, 248, 255) if self._hover_target == 'btn_meeting' else (99, 102, 241, 255)
            d.ellipse([meet_x - meet_r, meet_y - meet_r, meet_x + meet_r, meet_y + meet_r], fill=meet_fill)
            draw_meeting_icon(d, meet_x, meet_y, meet_sz, is_recording=False, color=(255, 255, 255, 255))

        # 4. DYMEK POWIADOMIENIA (jeśli aktywny)
        if self._balloon_type:
            bx = int(self.bx * scale)
            by = int(self.by * scale)
            bw = int(self.bw * scale)
            bh = int(self.bh * scale)
            br = int(self.ball_r * scale)

            # Cień dymka
            b_shadow = Image.new('RGBA', (W, H), (0, 0, 0, 0))
            bsd = ImageDraw.Draw(b_shadow)
            bsd.rounded_rectangle([bx, by + int(3*scale), bx + bw, by + bh + int(5*scale)], radius=br, fill=(0, 0, 0, cfg['shadow_alpha']))
            tri_cx = int(W / 2)
            tri_top = by + bh + int(3*scale)
            tri_bot = tri_top + int(8*scale)
            tri_hw = int(8*scale)
            bsd.polygon([(tri_cx - tri_hw, tri_top), (tri_cx + tri_hw, tri_top), (tri_cx, tri_bot)], fill=(0, 0, 0, cfg['shadow_alpha']))
            b_shadow = b_shadow.filter(ImageFilter.GaussianBlur(radius=int(4*scale)))
            img.alpha_composite(b_shadow)
            d = ImageDraw.Draw(img)

            # Korpus dymka
            d.rounded_rectangle([bx, by, bx + bw, by + bh], radius=br, fill=cfg['ball_bg'], outline=cfg['ball_border'], width=max(1, int(1.1*scale)))

            # Trójkąt dymka skierowany w dół do widżetu
            tri_top = by + bh - int(1*scale)
            tri_bot = tri_top + int(8*scale)
            d.polygon([(tri_cx - tri_hw, tri_top), (tri_cx + tri_hw, tri_top), (tri_cx, tri_bot)], fill=cfg['ball_bg'])
            d.line([(tri_cx - tri_hw, tri_top), (tri_cx, tri_bot)], fill=cfg['ball_border'], width=max(1, int(1.1*scale)))
            d.line([(tri_cx + tri_hw, tri_top), (tri_cx, tri_bot)], fill=cfg['ball_border'], width=max(1, int(1.1*scale)))

            try:
                fnt_text = ImageFont.truetype(FONT_REGULAR_PATH, int(11.5 * scale))
            except Exception:
                fnt_text = ImageFont.load_default()

            if self._balloon_type == "error":
                # Czerwone kółko błędu ❌
                err_cx = bx + int(22 * scale)
                err_cy = by + int(26 * scale)
                err_r = int(8.5 * scale)
                d.ellipse([err_cx - err_r, err_cy - err_r, err_cx + err_r, err_cy + err_r], fill=(209, 52, 56, 255))
                ex_sz = int(3.2 * scale)
                d.line([(err_cx - ex_sz, err_cy - ex_sz), (err_cx + ex_sz, err_cy + ex_sz)], fill=(255, 255, 255, 255), width=max(1, int(1.6*scale)))
                d.line([(err_cx - ex_sz, err_cy + ex_sz), (err_cx + ex_sz, err_cy - ex_sz)], fill=(255, 255, 255, 255), width=max(1, int(1.6*scale)))

                msg_lines = [
                    "Aby używać wpisywania głosowego,",
                    "zaznacz pole tekstowe i spróbuj",
                    "ponownie."
                ]
            elif self._balloon_type == "help":
                # Niebieska ikonka info ℹ
                info_cx = bx + int(22 * scale)
                info_cy = by + int(26 * scale)
                info_r = int(8.5 * scale)
                d.ellipse([info_cx - info_r, info_cy - info_r, info_cx + info_r, info_cy + info_r], fill=cfg['accent'] + (255,))
                try:
                    fnt_i = ImageFont.truetype(FONT_BOLD_PATH, int(11 * scale))
                except Exception:
                    fnt_i = ImageFont.load_default()
                d.text((info_cx, info_cy - int(0.5*scale)), "i", fill=(255, 255, 255, 255), font=fnt_i, anchor="mm")

                msg_lines = [
                    "Wskazówki wpisywania głosowego:",
                    "Kliknij pole tekstowe, mów po polsku.",
                    "Skrót: Ctrl+Alt+D lub mysz MX Master."
                ]
            elif self._balloon_type == "live":
                # Niebieska pulsująca ikonka mikrofonu
                info_cx = bx + int(22 * scale)
                info_cy = by + int(26 * scale)
                info_r = int(8.5 * scale)
                d.ellipse([info_cx - info_r, info_cy - info_r, info_cx + info_r, info_cy + info_r], fill=cfg['accent'] + (255,))
                draw_screenshot_mic(d, info_cx, info_cy, int(10 * scale), is_muted=False, color=(255, 255, 255, 255))

                txt = (self.live_text or "Słucham... mów swobodnie").strip()
                words = txt.split()
                lines = []
                cur_l = []
                for w in words:
                    cur_l.append(w)
                    if len(" ".join(cur_l)) > 26:
                        lines.append(" ".join(cur_l))
                        cur_l = []
                if cur_l:
                    lines.append(" ".join(cur_l))
                if len(lines) > 3:
                    lines = lines[-3:]
                while len(lines) < 3:
                    lines.append("")
                msg_lines = lines
            elif self._balloon_type == "processing":
                # Bursztynowe kółko z mikrofonem ⏳
                info_cx = bx + int(22 * scale)
                info_cy = by + int(26 * scale)
                info_r = int(8.5 * scale)
                d.ellipse([info_cx - info_r, info_cy - info_r, info_cx + info_r, info_cy + info_r], fill=(245, 158, 11, 255))
                draw_screenshot_mic(d, info_cx, info_cy, int(10 * scale), is_muted=False, color=(255, 255, 255, 255))
                msg_lines = [
                    "Trwa przetwarzanie mowy...",
                    "Zaraz nastąpi wstawienie",
                    "tekstu do aplikacji."
                ]
            else:
                info_cx = bx + int(22 * scale)
                info_cy = by + int(26 * scale)
                info_r = int(8.5 * scale)
                d.ellipse([info_cx - info_r, info_cy - info_r, info_cx + info_r, info_cy + info_r], fill=cfg['accent'] + (255,))
                msg_lines = [self._balloon_message or "Informacja", "", ""]

            ty = by + int(13 * scale)
            tx = bx + int(37 * scale)
            for line in msg_lines:
                d.text((tx, ty), line, fill=cfg['ball_text'], font=fnt_text)
                ty += int(16 * scale)

            # Dolny pasek dymka
            btn_w = int(self.btn_w * scale)
            btn_h = int(self.btn_h * scale)
            btn_x = int(self.btn_x * scale)
            btn_y = int(self.btn_y * scale)
            btn_r = int(5 * scale)

            if self._balloon_type in ("live", "processing"):
                d.rounded_rectangle([btn_x, btn_y, btn_x + btn_w, btn_y + btn_h], radius=btn_r, fill=cfg['btn_bg'], outline=cfg['btn_border'], width=max(1, int(1*scale)))
                txt_lbl = "🎙️ Transkrypcja na żywo (W tle)" if self._balloon_type == "live" else "⏳ Kończenie transkrypcji..."
                d.text((btn_x + btn_w/2, btn_y + btn_h/2), txt_lbl, fill=cfg['accent'] + (255,), font=fnt_text, anchor="mm")
            else:
                btn_fill = cfg['btn_hover_bg'] if self._hover_target == 'btn_rozumiem' else cfg['btn_bg']
                d.rounded_rectangle([btn_x, btn_y, btn_x + btn_w, btn_y + btn_h], radius=btn_r, fill=btn_fill, outline=cfg['btn_border'], width=max(1, int(1*scale)))
                d.text((btn_x + btn_w/2, btn_y + btn_h/2), "Rozumiem", fill=cfg['btn_text'], font=fnt_text, anchor="mm")

        # 5. Konwersja na bufor BGRA i UpdateLayeredWindow
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

    def show_recording(self):
        self.mode = "recording"
        self.live_text = ""
        if self.show_live_preview:
            self._balloon_type = "live"
            self._balloon_until = time.time() + 4.0
        else:
            self._balloon_type = None
        self._dirty = True
        self.show()

    def show_idle(self):
        self.mode = "idle"
        self.live_text = ""
        if self._balloon_type in ("live", "processing"):
            self._balloon_type = None
        self._dirty = True
        self.show()

    def show_processing(self):
        self.mode = "processing"
        self.live_text = ""
        if self.show_live_preview:
            self._balloon_type = "processing"
            self._balloon_until = time.time() + 8.0
        else:
            self._balloon_type = None
        self._dirty = True
        self.show()

    def show_meeting_recording(self):
        self.mode = "meeting_recording"
        self.live_text = ""
        self._balloon_type = None
        self._dirty = True
        self.show()

    def show_error_balloon(self, duration_s=7.0):
        """Wyświetla dymek ostrzegawczy dokładnie ze zrzutu ekranu Windows 11."""
        self._balloon_type = "error"
        self._balloon_message = None
        self._balloon_until = time.time() + duration_s if duration_s > 0 else 0
        self._dirty = True
        self.show()

    def show_help_balloon(self, duration_s=10.0):
        """Wyświetla dymek pomocy z informacją o dyktowaniu."""
        self._balloon_type = "help"
        self._balloon_message = None
        self._balloon_until = time.time() + duration_s if duration_s > 0 else 0
        self._dirty = True
        self.show()

    def show_info(self, text: str, icon="ℹ", duration_ms=2500):
        self._balloon_type = "info"
        self._balloon_message = text
        self._balloon_until = time.time() + (duration_ms / 1000.0)
        self._dirty = True
        self.show()

    def hide_balloon(self):
        self._balloon_type = None
        self._balloon_until = 0
        self._dirty = True

    def update_live_text(self, text: str):
        if text:
            self.live_text = text.strip()
            if self.mode == "recording" and self.show_live_preview:
                self._balloon_type = "live"
                self._balloon_until = time.time() + 5.0
                self._dirty = True
                self.show()

    def show(self):
        self._visible = True
        self._dirty = True
        if self.hwnd:
            user32.ShowWindow(self.hwnd, 8)  # SW_SHOWNA
            user32.SetWindowPos(self.hwnd, -1, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010)

    def hide(self):
        self._visible = False
        self._dirty = True
        if self.hwnd:
            user32.ShowWindow(self.hwnd, 0)  # SW_HIDE

    def set_theme(self, theme_name: str):
        if theme_name in THEME_MAP:
            theme_name = THEME_MAP[theme_name]
        if theme_name in THEMES and theme_name != self.theme:
            self.theme = theme_name
            self._dirty = True
            if self.on_theme_changed:
                try:
                    self.on_theme_changed(self.theme)
                except Exception:
                    pass

    def is_alive(self):
        return self._thread is not None and self._thread.is_alive()

    def stop(self):
        self.close()

    def close(self):
        self._running = False
        if self.hwnd and user32.IsWindow(self.hwnd):
            user32.PostMessageW(self.hwnd, 0x0010, 0, 0)
