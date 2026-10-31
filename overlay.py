import ctypes
from ctypes import wintypes
import threading
import time
import math
import os
import tempfile
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

user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
user32.RegisterHotKey.restype = wintypes.BOOL
user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
user32.UnregisterHotKey.restype = wintypes.BOOL
user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.SendMessageW.restype = LRESULT

if hasattr(user32, 'GetWindowLongPtrW'):
    _GetWindowLong = user32.GetWindowLongPtrW
    _SetWindowLong = user32.SetWindowLongPtrW
    _GetWindowLong.argtypes = [wintypes.HWND, ctypes.c_int]
    _GetWindowLong.restype = ctypes.c_longlong
    _SetWindowLong.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_longlong]
    _SetWindowLong.restype = ctypes.c_longlong
else:
    _GetWindowLong = user32.GetWindowLongW
    _SetWindowLong = user32.SetWindowLongW
    _GetWindowLong.argtypes = [wintypes.HWND, ctypes.c_int]
    _GetWindowLong.restype = ctypes.c_long
    _SetWindowLong.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_long]
    _SetWindowLong.restype = ctypes.c_long

def parse_hotkey_to_win32(hk: str) -> tuple[int, int]:
    """Konwertuje string skrótu (np. <ctrl>+<alt>+d) na flagi modyfikatorów i Virtual Key Code dla RegisterHotKey."""
    clean = hk.lower().replace("<", "").replace(">", "").replace(" ", "")
    parts = clean.split("+")
    mods = 0x4000  # MOD_NOREPEAT
    vk = 0
    for p in parts:
        if p in ("ctrl", "control"):
            mods |= 0x0002
        elif p in ("alt", "menu"):
            mods |= 0x0001
        elif p == "shift":
            mods |= 0x0004
        elif p in ("win", "windows", "super"):
            mods |= 0x0008
        elif len(p) == 1:
            vk = ord(p.upper())
        elif p.startswith("f") and p[1:].isdigit():
            vk = 0x70 + (int(p[1:]) - 1)
        elif p == "space":
            vk = 0x20
        elif p in ("return", "enter"):
            vk = 0x0D
        elif p == "tab":
            vk = 0x09
        elif p in ("escape", "esc"):
            vk = 0x1B
        elif p == "backspace":
            vk = 0x08
    return mods, vk

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

import logging
logger = logging.getLogger("Overlay")

_FONT_CACHE = {}

def get_cached_font(font_path: str, size: int):
    """Pobiera skompilowaną czcionkę z pamięci podręcznej, eliminując narzut operacji We/Wy w pętli renderowania."""
    key = (font_path, size)
    font = _FONT_CACHE.get(key)
    if font is None:
        try:
            font = ImageFont.truetype(font_path, size)
        except Exception:
            try:
                font = ImageFont.load_default()
            except Exception:
                font = None
        _FONT_CACHE[key] = font
    return font

def _safe_dispatch(fn, *args, **kwargs):
    """Bezpieczne uruchamianie callbacków widżetu w osobnym wątku z pełnym logowaniem wyjątków."""
    if not fn:
        return
    def _run():
        try:
            fn(*args, **kwargs)
        except Exception:
            logger.exception(f"Błąd podczas wykonywania callbacku interfejsu ({getattr(fn, '__name__', repr(fn))}):")
    threading.Thread(target=_run, daemon=True).start()


THEMES = {
    'light': {
        'name': 'Jasny (Light Modern)',
        'panel_bg': (250, 252, 255, 245),
        'panel_border': (99, 122, 160, 48),
        'bar_bg': (214, 223, 237, 235),
        'toggle_active_bg': (186, 202, 228, 255),
        'toggle_hover_bg': (200, 212, 230, 255),
        'toggle_active_hover_bg': (176, 194, 222, 255),
        'btn_hover_bg': (200, 212, 230, 255),
        'btn_close_hover_bg': (250, 210, 215, 255),
        'panel_close_hover_bg': (235, 240, 248, 255),
        'text': (24, 49, 82, 255),
        'muted': (116, 133, 163, 255),
        'wave': (127, 142, 170, 240),
        'accent': (64, 92, 242, 255),
        'danger': (255, 33, 51, 255),
        'tab_bg': (220, 232, 255, 250),
        'mic_standby_bg': (214, 219, 230, 255),
        'mic_standby_color': (72, 97, 127, 255),
        'meet_standby_bg': (214, 221, 232, 255),
        'meet_standby_color': (255, 255, 255, 255),
        'scroll_thumb': (180, 195, 218, 255),
        'scroll_track': (238, 242, 248, 255),
        'shadow_alpha': 20,
        'glow1': (105, 157, 255, 12),
        'glow2': (178, 112, 255, 10),
        'stream_lbl': (70, 90, 125, 255),
        'stream_lbl_active': (20, 35, 65, 255),
        'stream_on_text': (24, 55, 160, 255),
        'stream_off_text': (190, 22, 38, 255),
        'bar_btn_col': (65, 85, 120, 255),
        'bar_btn_close_hover': (190, 20, 35, 255)
    },
    'dark': {
        'name': 'Ciemny (Dark Modern)',
        'panel_bg': (20, 28, 41, 238),
        'panel_border': (151, 173, 216, 42),
        'bar_bg': (18, 24, 36, 235),
        'toggle_active_bg': (36, 50, 78, 255),
        'toggle_hover_bg': (28, 38, 56, 255),
        'toggle_active_hover_bg': (46, 62, 94, 255),
        'btn_hover_bg': (30, 40, 60, 255),
        'btn_close_hover_bg': (64, 28, 36, 255),
        'panel_close_hover_bg': (30, 42, 62, 255),
        'text': (237, 243, 255, 255),
        'muted': (145, 161, 191, 255),
        'wave': (132, 147, 177, 240),
        'accent': (75, 92, 242, 255),
        'danger': (255, 33, 51, 255),
        'tab_bg': (35, 48, 78, 250),
        'mic_standby_bg': (43, 53, 70, 255),
        'mic_standby_color': (223, 232, 251, 255),
        'meet_standby_bg': (45, 55, 71, 255),
        'meet_standby_color': (255, 255, 255, 230),
        'scroll_thumb': (85, 105, 140, 255),
        'scroll_track': (28, 38, 54, 255),
        'shadow_alpha': 40,
        'glow1': (105, 157, 255, 16),
        'glow2': (178, 112, 255, 14),
        'stream_lbl': (180, 195, 220, 255),
        'stream_lbl_active': (240, 245, 255, 255),
        'stream_on_text': (56, 189, 248, 255),
        'stream_off_text': (255, 85, 95, 255),
        'bar_btn_col': (180, 195, 220, 255),
        'bar_btn_close_hover': (255, 100, 110, 255)
    },
    'glass_light': {
        'name': 'Glass Jasny (Mica Light)',
        'panel_bg': (255, 255, 255, 185),
        'panel_border': (255, 255, 255, 180),
        'bar_bg': (206, 218, 236, 215),
        'toggle_active_bg': (180, 198, 226, 255),
        'toggle_hover_bg': (194, 208, 230, 255),
        'toggle_active_hover_bg': (170, 190, 220, 255),
        'btn_hover_bg': (194, 208, 230, 255),
        'btn_close_hover_bg': (250, 212, 216, 255),
        'panel_close_hover_bg': (236, 242, 250, 255),
        'text': (42, 65, 102, 255),
        'muted': (113, 132, 165, 255),
        'wave': (128, 145, 179, 240),
        'accent': (65, 102, 238, 255),
        'danger': (255, 33, 51, 255),
        'tab_bg': (255, 255, 255, 210),
        'mic_standby_bg': (235, 242, 252, 210),
        'mic_standby_color': (42, 65, 102, 255),
        'meet_standby_bg': (235, 242, 252, 210),
        'meet_standby_color': (65, 102, 238, 240),
        'scroll_thumb': (170, 188, 215, 255),
        'scroll_track': (235, 240, 248, 255),
        'shadow_alpha': 18,
        'glow1': (150, 190, 255, 22),
        'glow2': (200, 170, 255, 18),
        'stream_lbl': (70, 90, 125, 255),
        'stream_lbl_active': (20, 35, 65, 255),
        'stream_on_text': (24, 55, 160, 255),
        'stream_off_text': (190, 22, 38, 255),
        'bar_btn_col': (65, 85, 120, 255),
        'bar_btn_close_hover': (190, 20, 35, 255)
    },
    'glass_dark': {
        'name': 'Glass Ciemny (Mica Dark)',
        'panel_bg': (22, 37, 65, 215),
        'panel_border': (228, 237, 255, 75),
        'bar_bg': (18, 28, 48, 215),
        'toggle_active_bg': (36, 56, 92, 255),
        'toggle_hover_bg': (28, 42, 70, 255),
        'toggle_active_hover_bg': (46, 68, 108, 255),
        'btn_hover_bg': (30, 44, 72, 255),
        'btn_close_hover_bg': (68, 28, 40, 255),
        'panel_close_hover_bg': (32, 48, 78, 255),
        'text': (241, 245, 255, 255),
        'muted': (173, 191, 223, 255),
        'wave': (166, 182, 215, 240),
        'accent': (78, 105, 239, 255),
        'danger': (255, 33, 51, 255),
        'tab_bg': (40, 60, 95, 220),
        'mic_standby_bg': (50, 70, 105, 210),
        'mic_standby_color': (223, 232, 251, 255),
        'meet_standby_bg': (50, 70, 105, 210),
        'meet_standby_color': (255, 255, 255, 230),
        'scroll_thumb': (90, 115, 155, 255),
        'scroll_track': (30, 44, 72, 255),
        'shadow_alpha': 42,
        'glow1': (105, 157, 255, 22),
        'glow2': (178, 112, 255, 18),
        'stream_lbl': (180, 195, 220, 255),
        'stream_lbl_active': (240, 245, 255, 255),
        'stream_on_text': (56, 189, 248, 255),
        'stream_off_text': (255, 85, 95, 255),
        'bar_btn_col': (180, 195, 220, 255),
        'bar_btn_close_hover': (255, 100, 110, 255)
    },
    'glass_color': {
        'name': 'Glass Kolorowy (Vibrant Glass)',
        'panel_bg': (86, 111, 235, 215),
        'panel_border': (255, 255, 255, 140),
        'bar_bg': (74, 76, 171, 215),
        'toggle_active_bg': (105, 115, 225, 255),
        'toggle_hover_bg': (90, 96, 200, 255),
        'toggle_active_hover_bg': (120, 130, 240, 255),
        'btn_hover_bg': (90, 96, 200, 255),
        'btn_close_hover_bg': (170, 50, 75, 255),
        'panel_close_hover_bg': (100, 120, 240, 255),
        'text': (255, 255, 255, 255),
        'muted': (220, 230, 255, 230),
        'wave': (240, 245, 255, 230),
        'accent': (255, 255, 255, 255),
        'danger': (255, 45, 65, 255),
        'tab_bg': (255, 255, 255, 65),
        'mic_standby_bg': (255, 255, 255, 55),
        'mic_standby_color': (255, 255, 255, 255),
        'meet_standby_bg': (255, 255, 255, 55),
        'meet_standby_color': (255, 255, 255, 255),
        'scroll_thumb': (160, 180, 255, 255),
        'scroll_track': (95, 115, 220, 255),
        'shadow_alpha': 35,
        'glow1': (105, 175, 255, 35),
        'glow2': (255, 116, 220, 30),
        'stream_lbl': (220, 230, 255, 240),
        'stream_lbl_active': (255, 255, 255, 255),
        'stream_on_text': (255, 255, 255, 255),
        'stream_off_text': (255, 120, 135, 255),
        'bar_btn_col': (230, 238, 255, 235),
        'bar_btn_close_hover': (255, 255, 255, 255)
    }
}

THEME_MAP = {
    'light': 'light',
    'dark': 'dark',
    'glass_light': 'glass_light',
    'glass-light': 'glass_light',
    'glass_dark': 'glass_dark',
    'glass-dark': 'glass_dark',
    'glass_color': 'glass_color',
    'glass-color': 'glass_color',
    'minimal': 'light',
    'cyber_neon': 'glass_dark',
    'nordic_titanium': 'glass_light'
}

# Profile wysokosci slupkow audio
BAR_HEIGHTS = [
    [7,15,10,22],[11,27,16,31],[8,18,12,25],[14,33,19,36],
    [10,21,15,29],[13,30,18,34],[8,16,11,23],[16,34,20,38],
    [11,25,15,31],[7,18,10,21],[13,29,18,33],[9,22,14,27],
    [15,35,21,39],[8,17,11,24],[12,28,17,32],[10,23,14,29],
    [7,16,10,22],[14,31,19,36],[10,20,14,27],[13,30,18,34],
    [8,18,12,25],[12,27,16,31],[9,19,13,24],[15,33,20,38],
    [10,24,15,30],[7,16,11,22],[12,26,16,30]
]

# Profil kolumn matrycy amplitudy (23 kolumny); różnica wartości = jak wysoko kolumna sięga przy mowie
MATRIX_PROFILE = [
    (7, 15), (11, 27), (8, 18), (14, 33), (10, 21), (13, 30), (8, 16), (16, 34),
    (11, 25), (7, 18), (13, 29), (9, 22), (15, 35), (8, 17), (12, 28), (10, 23),
    (7, 16), (14, 31), (10, 20), (9, 22), (13, 30), (8, 17), (11, 26)
]


def _mix(fg, bg, t):
    """Kolor fg nałożony na bg z kryciem t, jako pełny kolor (rysowanie z alfą robiłoby dziury w karcie)."""
    return tuple(int(round(fg[k] * t + bg[k] * (1.0 - t))) for k in range(3)) + (255,)


_ICON_CACHE = {}

def get_svg_mic_image(sz, color=(255, 255, 255, 255)):
    """Renderuje wektorowa ikone mikrofonu."""
    key = ('mic', sz, color)
    if key in _ICON_CACHE:
        return _ICON_CACHE[key]
    ss = 4
    w = max(4, sz * ss)
    h = max(4, sz * ss)
    img = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    scale = w / 24.0
    stroke = max(1, int(round(2.0 * scale)))

    rx1 = 8.0 * scale
    ry1 = 3.0 * scale
    rx2 = 16.0 * scale
    ry2 = 15.0 * scale
    d.rounded_rectangle([rx1, ry1, rx2, ry2], radius=int(4.0 * scale), outline=color, width=stroke)

    cx1 = 5.0 * scale
    cy1 = 4.0 * scale
    cx2 = 19.0 * scale
    cy2 = 18.0 * scale
    d.arc([cx1, cy1, cx2, cy2], start=0, end=180, fill=color, width=stroke)

    sx = 12.0 * scale
    sy1 = 18.0 * scale
    sy2 = 21.0 * scale
    d.line([(sx, sy1), (sx, sy2)], fill=color, width=stroke)

    fx1 = 8.5 * scale
    fx2 = 15.5 * scale
    fy = 21.0 * scale
    d.line([(fx1, fy), (fx2, fy)], fill=color, width=stroke)

    out = img.resize((sz, sz), Image.Resampling.LANCZOS)
    _ICON_CACHE[key] = out
    return out

def _eval_cubic_bezier(p0, p1, p2, p3, n=16):
    ts = np.linspace(0, 1, n)
    pts = []
    for t in ts:
        pt = (1-t)**3 * p0 + 3*(1-t)**2 * t * p1 + 3*(1-t) * t**2 * p2 + t**3 * p3
        pts.append((float(pt[0]), float(pt[1])))
    return pts

def get_people_image(sz, color=(255, 255, 255, 255)):
    """Renderuje wektorowa ikone spotkania."""
    key = ('people', sz, color)
    if key in _ICON_CACHE:
        return _ICON_CACHE[key]
    ss = 4
    w = max(4, sz * ss)
    h = max(4, sz * ss)
    img = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    scale = w / 38.0

    c1x, c1y, r1 = 14.0 * scale, 13.0 * scale, 6.0 * scale
    d.ellipse([c1x - r1, c1y - r1, c1x + r1, c1y + r1], fill=color)

    c2x, c2y, r2 = 27.0 * scale, 15.0 * scale, 4.6 * scale
    d.ellipse([c2x - r2, c2y - r2, c2x + r2, c2y + r2], fill=color)

    p0 = np.array([3.5, 30.0])
    p1 = np.array([3.5, 24.8])
    p2 = np.array([7.8, 20.6])
    p3 = np.array([13.0, 20.6])
    p4 = np.array([18.2, 20.6])
    p5 = np.array([22.5, 24.8])
    p6 = np.array([22.5, 30.0])
    pts1 = _eval_cubic_bezier(p0, p1, p2, p3, 16) + _eval_cubic_bezier(p3, p4, p5, p6, 16)[1:]
    pts1.append((3.5, 30.0))
    d.polygon([(x * scale, y * scale) for x, y in pts1], fill=color)

    q0 = np.array([22.0, 29.5])
    q1 = np.array([22.3, 25.9])
    q2 = np.array([25.3, 22.9])
    q3 = np.array([29.0, 22.9])
    q4 = np.array([32.6, 22.9])
    q5 = np.array([35.5, 25.7])
    q6 = np.array([35.9, 29.5])
    pts2 = _eval_cubic_bezier(q0, q1, q2, q3, 16) + _eval_cubic_bezier(q3, q4, q5, q6, 16)[1:]
    pts2.append((22.0, 29.5))
    d.polygon([(x * scale, y * scale) for x, y in pts2], fill=color)

    out = img.resize((sz, sz), Image.Resampling.LANCZOS)
    _ICON_CACHE[key] = out
    return out

def _glow_sprite(rad, color, blur):
    """Rozmyta elipsa o promieniu rad (px) na przezroczystym kwadracie; zwraca (obraz, połowa boku)."""
    half = int(rad + blur * 3 + 2)
    sp = Image.new('RGBA', (half * 2, half * 2), (0, 0, 0, 0))
    ImageDraw.Draw(sp).ellipse([half - rad, half - rad, half + rad, half + rad], fill=color)
    return sp.filter(ImageFilter.GaussianBlur(radius=blur)), half

def draw_svg_mic(target, cx, cy, sz, color=(255, 255, 255, 255)):
    """Rysuje ikone mikrofonu."""
    img_dest = target if isinstance(target, Image.Image) else getattr(target, '_image', None)
    mic_img = get_svg_mic_image(sz, color)
    if img_dest:
        img_dest.alpha_composite(mic_img, (int(round(cx - sz / 2.0)), int(round(cy - sz / 2.0))))

def draw_people_icon(target, cx, cy, sz, color=(255, 255, 255, 255)):
    """Rysuje ikone spotkania."""
    img_dest = target if isinstance(target, Image.Image) else getattr(target, '_image', None)
    people_img = get_people_image(sz, color)
    if img_dest:
        img_dest.alpha_composite(people_img, (int(round(cx - sz / 2.0)), int(round(cy - sz / 2.0))))

def _create_taskbar_icon():
    """Tworzy ikone HICON dla paska zadan Windows."""
    try:
        import sys
        base_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        app_ico = os.path.join(base_dir, "icon.ico")
        if os.path.exists(app_ico):
            h = user32.LoadImageW(None, app_ico, 1, 32, 32, 0x0010)
            if h:
                return h
        temp_dir = tempfile.gettempdir()
        ico_path = os.path.join(temp_dir, "voice_ui_taskbar.ico")
        img_hi = Image.new('RGBA', (256, 256), color=(0, 0, 0, 0))
        d = ImageDraw.Draw(img_hi)
        d.ellipse((10, 10, 246, 246), fill=(18, 28, 58, 255))
        draw_svg_mic(img_hi, 128, 128, 124, color=(255, 255, 255, 255))
        img_hi.save(ico_path, format='ICO', sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
        return user32.LoadImageW(None, ico_path, 1, 32, 32, 0x0010)
    except Exception:
        return None

def _add_hwnd_to_taskbar(hwnd: int):
    """Rejestruje okno w ITaskbarList."""
    if not hwnd or not user32.IsWindow(hwnd):
        return None
    try:
        class GUID(ctypes.Structure):
            _fields_ = [
                ("Data1", wintypes.DWORD),
                ("Data2", wintypes.WORD),
                ("Data3", wintypes.WORD),
                ("Data4", ctypes.c_byte * 8)
            ]
        CLSID_TaskbarList = GUID(0x56FDF344, 0xFD6D, 0x11d0, (ctypes.c_byte * 8)(0x95, 0x8A, 0x00, 0x60, 0x97, 0xC9, 0xA0, 0x90))
        IID_ITaskbarList = GUID(0x56FDF342, 0xFD6D, 0x11d0, (ctypes.c_byte * 8)(0x95, 0x8A, 0x00, 0x60, 0x97, 0xC9, 0xA0, 0x90))
        ole32 = ctypes.windll.ole32
        ole32.CoInitialize(None)
        p_tb = ctypes.c_void_p()
        hr = ole32.CoCreateInstance(
            ctypes.byref(CLSID_TaskbarList),
            None,
            1,  # CLSCTX_INPROC_SERVER
            ctypes.byref(IID_ITaskbarList),
            ctypes.byref(p_tb)
        )
        if hr == 0 and p_tb.value:
            vtable = ctypes.cast(p_tb, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
            HrInit = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p)(vtable[3])
            AddTab = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, wintypes.HWND)(vtable[4])
            HrInit(p_tb)
            AddTab(p_tb, hwnd)
            return p_tb
    except Exception:
        pass
    return None

def _wrap_text_lines(text, max_w, draw, font):
    """Zawija tekst na wiersze mieszczące się w szerokości max_w."""
    words = text.split()
    if not words:
        return []
    lines = []
    curr = []
    for w in words:
        test_line = ' '.join(curr + [w])
        bbox = draw.textbbox((0, 0), test_line, font=font)
        if (bbox[2] - bbox[0]) > max_w and curr:
            lines.append(' '.join(curr))
            curr = [w]
        else:
            curr.append(w)
    if curr:
        lines.append(' '.join(curr))
    return lines

class FloatingOverlay:
    """
    Pływający widżet Voice UI oparty na Win32 Layered Windows:
    - Brak aktywacji fokusu (WS_EX_NOACTIVATE, MA_NOACTIVATE)
    - Obsługa przeciągania okna
    - Reaktywna fala dźwiękowa
    - Panel historii transkrypcji z przewijaniem
    - Komunikaty stanu i błędów
    """

    def __init__(self, theme='dark', always_on_top=True):
        self.hwnd = None
        self._thread = None
        self._ready_event = threading.Event()
        self._running = True
        self._lock = threading.RLock()
        self.always_on_top = bool(always_on_top)

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

        # Układ w pikselach okna (ui = 1). Kształty rysowane w 3x i zmniejszane, a tekst
        # rysowany już w docelowym rozmiarze, żeby był ostry (zmniejszany tekst się rozmywał).
        self.ui = 1.0
        self.margin = 2
        self.panel_open = False                      # Domyślnie wyłączona transkrypcja!
        self.show_live_preview = False
        self._smooth_vol = 0.0

        # Przewijanie transkrypcji (Scroll & Drag)
        self.scroll_line = 0
        self._user_scrolled = False
        self._is_scrolling = False
        self._total_lines_count = 0
        self._max_visible_lines = 4

        # Przyciski "Stream" i "Korekta" (sam napis; włączony = podświetlone tło)
        self.chip_font_px = 10
        self.chip_h = 15
        self.chip_pad = 8
        self.chip_min_ai_w = 54
        self.chip_gap = 6
        self.stream_realtime = False
        self.on_stream_toggle_callback = None
        self.ai_enabled = False
        self.on_ai_toggle_callback = None
        chip_ws = self._measure_chips()

        # Karta widżetu
        self.cw = max(140, int(math.ceil(sum(chip_ws) + self.chip_gap + 16)))
        self.ch = 168
        self.card_r = 14

        # Dymek powiadomień (błąd / info) nad kartą, tej samej szerokości
        self.pw = self.cw
        self.ph = 74
        self.px = self.margin
        self.py = self.margin
        self.panel_r = 10

        self.cx0 = self.margin
        self.cy0 = self.py + self.ph + 6
        self.w = self.cw + 2 * self.margin
        self.h = self.cy0 + self.ch + self.margin
        self.dw, self.dh = self.w, self.h

        # Nagłówek (logo, nazwa, ··· — ×); menu kotwiczy się do jego krawędzi
        self.bw = self.cw
        self.bh = 26
        self.bx = self.cx0
        self.by = self.cy0

        # Reszta karty: przyciski, główny przycisk, fala i status
        self.mw = self.cw
        self.mh = self.ch - self.bh
        self.mx = self.cx0
        self.my = self.cy0 + self.bh

        self.bar_close_cx = self.bx + self.bw - 12.5
        self.bar_close_cy = self.by + self.bh / 2
        self.bar_min_cx = self.bar_close_cx - 16
        self.bar_min_cy = self.bar_close_cy
        self.bar_menu_cx = self.bar_min_cx - 16
        self.bar_menu_cy = self.bar_close_cy

        # Zachowanie kompatybilności dla dawnych odwołań
        self.close_cx = self.bar_close_cx
        self.close_cy = self.bar_close_cy
        self.min_cx = self.bar_min_cx
        self.min_cy = self.bar_min_cy

        self.chips_cy = self.my + 17
        self._layout_chips(chip_ws)

        # Główny przycisk: mikrofon (dyktowanie) albo ludziki (transkrypcja rozmowy) – wg trybu z menu
        self.mic_cx = self.cx0 + self.cw / 2
        self.mic_cy = self.my + 55
        self.mic_rad = 20
        self.widget_mode = "dictation"
        self._session_kind = "dictation"

        # Matryca amplitudy (środek) i linia statusu
        self.wave_cy = self.my + 99
        self.status_cy = self.my + 122
        self._chrome_cache = None

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
        self.on_minimize_callback = None
        self.on_restore_callback = None
        self.on_hotkey_callback = None
        self.settings_handler = None
        self.is_menu_open = False
        self._user_minimized = False

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

    @property
    def state(self) -> str:
        return self.mode

    @state.setter
    def state(self, val: str):
        with self._lock:
            self.mode = val
            if val == "idle":
                self._start_time = 0.0
            elif val in ("recording", "transcribing"):
                if self._start_time <= 0:
                    self._start_time = time.time()
            self._dirty = True

    def set_callbacks(self, on_stop=None, on_close=None, on_toggle=None, on_meeting_toggle=None, on_minimize=None, on_restore=None, on_hotkey=None, on_stream_toggle=None, on_ai_toggle=None):
        self.on_stop_callback = on_stop
        self.on_close_callback = on_close
        self.on_toggle_callback = on_toggle
        self.on_meeting_toggle_callback = on_meeting_toggle
        self.on_minimize_callback = on_minimize
        self.on_restore_callback = on_restore
        if on_hotkey is not None:
            self.on_hotkey_callback = on_hotkey
        if on_stream_toggle is not None:
            self.on_stream_toggle_callback = on_stream_toggle
        if on_ai_toggle is not None:
            self.on_ai_toggle_callback = on_ai_toggle

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

    def _measure_chips(self):
        """Szerokości przycisków "Stream" i "Korekta" w pikselach okna."""
        fnt = get_cached_font(FONT_REG_PATH, self.chip_font_px)

        def text_w(txt):
            return fnt.getlength(txt) if fnt is not None else len(txt) * 5.0

        base = 2 * self.chip_pad
        return [base + text_w("Stream"), max(self.chip_min_ai_w, base + text_w("Korekta"))]

    def _layout_chips(self, chip_ws):
        """Rozmieszcza przyciski "Stream" i "Korekta" na środku karty."""
        sw, aw = chip_ws
        x0 = self.cx0 + (self.cw - (sw + self.chip_gap + aw)) / 2.0
        y0 = self.chips_cy - self.chip_h / 2.0

        self.stream_btn_x, self.stream_btn_y, self.stream_btn_w, self.stream_btn_h = x0, y0, sw, self.chip_h
        self.ai_btn_x, self.ai_btn_y, self.ai_btn_w, self.ai_btn_h = x0 + sw + self.chip_gap, y0, aw, self.chip_h

        # Zachowanie kompatybilności dla dawnych odwołań
        self.bar_stream_cx = self.stream_btn_x + self.stream_btn_w / 2
        self.bar_stream_cy = self.chips_cy
        self.tgl_btn_x = self.stream_btn_x
        self.tgl_btn_y = self.stream_btn_y
        self.tgl_btn_w = self.stream_btn_w
        self.tgl_btn_h = self.stream_btn_h

    @staticmethod
    def _lparam_xy(lparam):
        x = lparam & 0xFFFF
        y = (lparam >> 16) & 0xFFFF
        if x > 0x7FFF: x -= 0x10000
        if y > 0x7FFF: y -= 0x10000
        return x, y

    def _to_design(self, x, y):
        """Piksele okna na ekranie -> jednostki projektu (w nich liczony jest cały układ)."""
        return x / self.ui, y / self.ui

    def _is_inside_module(self, x, y):
        return (self.mx <= x <= self.mx + self.mw) and (self.my <= y <= self.my + self.mh)

    def _is_inside_bar(self, x, y):
        return (self.bx <= x <= self.bx + self.bw) and (self.by <= y <= self.by + self.bh)

    def _is_inside_panel(self, x, y):
        if not self._balloon_type:
            return False
        return (self.px <= x <= self.px + self.pw) and (self.py <= y <= self.py + self.ph)

    def _get_target(self, x, y):
        # 1. Sprawdź kliknięcie w panelu górnym (w dymku błędu lub info)
        if self._balloon_type in ("error", "info"):
            btn_x = self.px + 8
            btn_y = self.py + self.ph - 25
            btn_w = self.pw - 16
            btn_h = 19
            if (btn_x <= x <= btn_x + btn_w) and (btn_y <= y <= btn_y + btn_h):
                return 'btn_rozumiem'
            if self._is_inside_panel(x, y):
                return 'balloon_body'

        # 2. Nagłówek: ··· — ×
        if self._is_inside_bar(x, y):
            if abs(x - self.bar_close_cx) <= 12:
                return 'btn_bar_close'
            if abs(x - self.bar_min_cx) <= 12:
                return 'btn_bar_minimize'
            if abs(x - self.bar_menu_cx) <= 12:
                return 'btn_bar_menu'
            return 'widget_drag'

        if not self._is_inside_module(x, y):
            return None

        # 3. Przyciski "Stream" i "Korekta"
        if (self.stream_btn_x <= x <= self.stream_btn_x + self.stream_btn_w) and (self.stream_btn_y <= y <= self.stream_btn_y + self.stream_btn_h):
            return 'btn_toggle_stream'
        if (self.ai_btn_x <= x <= self.ai_btn_x + self.ai_btn_w) and (self.ai_btn_y <= y <= self.ai_btn_y + self.ai_btn_h):
            return 'btn_toggle_ai'

        # 4. Główny przycisk
        d_mic = (x - self.mic_cx)**2 + (y - self.mic_cy)**2
        if d_mic <= (self.mic_rad + 3)**2:
            return 'btn_mic'

        # Przeciąganie za resztę karty
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
        WM_MOUSEWHEEL = 0x020A

        if msg == WM_MOUSEACTIVATE:
            # MA_NOACTIVATE: nie zmienia aktywnego okna
            return MA_NOACTIVATE

        WM_HOTKEY = 0x0312
        if msg == WM_HOTKEY:
            hotkey_id = int(wparam)
            if self.on_hotkey_callback:
                _safe_dispatch(self.on_hotkey_callback, hotkey_id)
            return 0

        WM_APP_REGISTER_HOTKEY = 0x8001
        WM_APP_UNREGISTER_HOTKEY = 0x8002

        if msg == WM_APP_REGISTER_HOTKEY:
            hotkey_id = int(wparam)
            mods = (int(lparam) >> 16) & 0xFFFF
            vk = int(lparam) & 0xFFFF
            user32.UnregisterHotKey(hwnd, hotkey_id)
            res = user32.RegisterHotKey(hwnd, hotkey_id, mods, vk)
            return 1 if res else 0

        if msg == WM_APP_UNREGISTER_HOTKEY:
            hotkey_id = int(wparam)
            user32.UnregisterHotKey(hwnd, hotkey_id)
            return 0

        WM_SIZE = 0x0005
        WM_SYSCOMMAND = 0x0112
        SC_RESTORE = 0xF120
        SC_MINIMIZE = 0xF020

        if msg == WM_SYSCOMMAND:
            cmd = wparam & 0xFFF0
            if cmd == SC_MINIMIZE:
                self.minimize()
                if self.on_minimize_callback:
                    _safe_dispatch(self.on_minimize_callback)
                return 0
            elif cmd == SC_RESTORE:
                self.restore()
                if self.on_restore_callback:
                    _safe_dispatch(self.on_restore_callback)
                return 0

        if msg == WM_SIZE:
            if wparam == 0:  # SIZE_RESTORED
                self._user_minimized = False
                self._visible = True
                self._dirty = True
                if self.hwnd and self.always_on_top:
                    user32.SetWindowPos(self.hwnd, -1, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010)
                if self.on_restore_callback:
                    _safe_dispatch(self.on_restore_callback)
            elif wparam == 1:  # SIZE_MINIMIZED
                self._user_minimized = True
                self._visible = False
                if self.on_minimize_callback:
                    _safe_dispatch(self.on_minimize_callback)
            return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

        if msg == WM_MOUSEWHEEL:
            if self.panel_open:
                delta = (wparam >> 16) & 0xFFFF
                if delta > 0x7FFF:
                    delta -= 0x10000
                steps = 1 if delta > 0 else -1
                with self._lock:
                    max_scroll = max(0, self._total_lines_count - self._max_visible_lines)
                    new_scroll = self.scroll_line - steps
                    self.scroll_line = max(0, min(max_scroll, new_scroll))
                    self._user_scrolled = (self.scroll_line < max_scroll)
                self._dirty = True
            return 0

        if msg == WM_NCHITTEST:
            x, y = self._lparam_xy(lparam)
            pt = wintypes.POINT(x, y)
            user32.ScreenToClient(hwnd, ctypes.byref(pt))

            cx, cy = self._to_design(pt.x, pt.y)
            if self._is_inside_module(cx, cy) or self._is_inside_bar(cx, cy) or self._is_inside_panel(cx, cy):
                return 1  # HTCLIENT
            return -1  # HTTRANSPARENT (kliknięcia obok przelatują bez przeszkód)

        elif msg == WM_MOUSEMOVE:
            tme = TRACKMOUSEEVENT()
            tme.cbSize = ctypes.sizeof(TRACKMOUSEEVENT)
            tme.dwFlags = 2
            tme.hwndTrack = hwnd
            user32.TrackMouseEvent(ctypes.byref(tme))

            x, y = self._to_design(*self._lparam_xy(lparam))

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
            elif self._is_scrolling:
                sb_norm_y = self.py + 24
                sb_norm_h = max(1, self.ph - 32)
                ratio = max(0.0, min(1.0, (y - sb_norm_y) / float(sb_norm_h)))
                with self._lock:
                    max_scroll = max(0, self._total_lines_count - self._max_visible_lines)
                    self.scroll_line = int(round(ratio * max_scroll))
                    self._user_scrolled = (self.scroll_line < max_scroll)
                self._dirty = True
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
            if self._hover_target in ('btn_mic', 'btn_bar_close', 'btn_bar_minimize', 'btn_bar_menu', 'btn_toggle_stream', 'btn_toggle_ai', 'btn_close', 'btn_minimize', 'btn_rozumiem'):
                user32.SetCursor(self._hcursor_hand)
                return 1
            elif self._hover_target in ('widget_drag', 'panel_content', 'balloon_body'):
                user32.SetCursor(self._hcursor_move)
                return 1
            else:
                user32.SetCursor(self._hcursor_arrow)
                return 1

        elif msg == WM_LBUTTONDOWN:
            if not self.always_on_top:
                user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010)  # HWND_TOP, SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE

            x, y = self._to_design(*self._lparam_xy(lparam))

            target = self._get_target(x, y)
            self._pressed_btn = target

            if target in ('widget_drag', 'panel_content', 'balloon_body'):
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

            if self._is_scrolling:
                self._is_scrolling = False
                user32.ReleaseCapture()
                self._dirty = True

            x, y = self._to_design(*self._lparam_xy(lparam))
            target = self._get_target(x, y)

            if self._pressed_btn == target:
                if target == 'btn_mic':
                    if self.mode == "recording":
                        _safe_dispatch(self.on_stop_callback)
                    elif self.mode == "transcribing":
                        _safe_dispatch(self.on_meeting_toggle_callback)
                    elif self.mode == "idle" and self.widget_mode == "meeting":
                        _safe_dispatch(self.on_meeting_toggle_callback)
                    else:
                        _safe_dispatch(self.on_toggle_callback)

                elif target == 'btn_toggle_stream':
                    self.stream_realtime = not self.stream_realtime
                    self._dirty = True
                    _safe_dispatch(self.on_stream_toggle_callback)

                elif target == 'btn_toggle_ai':
                    if self.on_ai_toggle_callback:
                        _safe_dispatch(self.on_ai_toggle_callback)
                    else:
                        self.ai_enabled = not self.ai_enabled
                        self._dirty = True

                elif target == 'btn_rozumiem':
                    self.hide_balloon()

                elif target == 'btn_bar_menu' or (self._pressed_btn == 'btn_bar_menu' and abs(x - self.bar_menu_cx) <= 15 and (self.by - 2 <= y <= self.by + self.bh + 2)):
                    screen_h = user32.GetSystemMetrics(1)
                    menu_screen_x = self.pos_x + int(self.bar_menu_cx * self.ui)
                    # Jeśli widżet jest w dolnej połowie ekranu, zakotwicz na górnej krawędzi pastylki
                    if self.pos_y > screen_h // 2:
                        menu_screen_y = self.pos_y + int(self.by * self.ui)
                    else:
                        menu_screen_y = self.pos_y + int((self.by + self.bh) * self.ui)
                    _safe_dispatch(self.settings_handler, menu_screen_x, menu_screen_y)

                elif target in ('btn_bar_minimize', 'btn_minimize'):
                    self.minimize()
                    _safe_dispatch(self.on_minimize_callback)

                elif target in ('btn_bar_close', 'btn_close'):
                    if self.mode == "recording":
                        _safe_dispatch(self.on_close_callback)
                    elif self.mode == "transcribing":
                        _safe_dispatch(self.on_meeting_toggle_callback)
                    else:
                        self.hide()

            self._pressed_btn = None
            return 0

        elif msg == WM_RBUTTONUP:
            pt_screen = wintypes.POINT()
            user32.GetCursorPos(ctypes.byref(pt_screen))
            _safe_dispatch(self.settings_handler, pt_screen.x, pt_screen.y)
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

            try:
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Whiscribe.VoiceTyping.1.0")
            except Exception:
                pass

            self._proc = WNDPROC(self._wnd_proc)
            h_icon = _create_taskbar_icon()

            self._class_name = f"VoiceUIClass_{id(self)}_{int(time.time()*1000)}"
            wc = WNDCLASSEXW()
            wc.cbSize = ctypes.sizeof(WNDCLASSEXW)
            wc.style = 3
            wc.lpfnWndProc = self._proc
            wc.hInstance = kernel32.GetModuleHandleW(None)
            wc.hIcon = h_icon if h_icon else 0
            wc.hIconSm = h_icon if h_icon else 0
            wc.hCursor = self._hcursor_arrow
            wc.lpszClassName = self._class_name

            user32.RegisterClassExW(ctypes.byref(wc))

            WS_EX_LAYERED = 0x00080000
            WS_EX_TOPMOST = 0x00000008
            WS_EX_NOACTIVATE = 0x08000000
            WS_EX_APPWINDOW = 0x00040000

            WS_POPUP = 0x80000000
            WS_SYSMENU = 0x00080000
            WS_MINIMIZEBOX = 0x00020000

            ex_flags = WS_EX_LAYERED | WS_EX_APPWINDOW | WS_EX_NOACTIVATE
            if self.always_on_top:
                ex_flags |= WS_EX_TOPMOST

            self.hwnd = user32.CreateWindowExW(
                ex_flags,
                self._class_name,
                "Whiscribe",
                WS_POPUP | WS_SYSMENU | WS_MINIMIZEBOX,
                self.pos_x, self.pos_y, self.w, self.h,
                None, None, wc.hInstance, None
            )

            if h_icon:
                user32.SendMessageW(self.hwnd, 0x0080, 1, h_icon)  # WM_SETICON ICON_BIG
                user32.SendMessageW(self.hwnd, 0x0080, 0, h_icon)  # WM_SETICON ICON_SMALL

            self._tb_interface = _add_hwnd_to_taskbar(self.hwnd)

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
                hwnd_insert = -1 if self.always_on_top else -2
                user32.SetWindowPos(self.hwnd, hwnd_insert, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010)

            self._ready_event.set()
            self._dirty = True
            self._render_frame(time.time())

            msg = wintypes.MSG()
            last_frame_time = time.time()
            last_topmost_check = time.time()
            last_fg = None
            prev_hover = self._hover_target

            while self._running:
                while user32.PeekMessageW(ctypes.byref(msg), self.hwnd, 0, 0, 1):
                    user32.TranslateMessage(ctypes.byref(msg))
                    user32.DispatchMessageW(ctypes.byref(msg))

                now = time.time()

                # Topmost Keep-Alive: gwarantuje, że widżet nigdy nie zostaje przykryty ani zminimalizowany (poza celową minimalizacją użytkownika)
                if self.always_on_top and self._visible and self.hwnd and not getattr(self, '_user_minimized', False) and not user32.IsIconic(self.hwnd) and not getattr(self, 'is_menu_open', False):
                    cur_fg = user32.GetForegroundWindow()
                    if cur_fg != last_fg or (now - last_topmost_check > 0.8):
                        last_topmost_check = now
                        last_fg = cur_fg
                        user32.SetWindowPos(
                            self.hwnd, -1, 0, 0, 0, 0,
                            0x0001 | 0x0002 | 0x0010  # SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE
                        )
                needs_anim = (self.mode in ("recording", "transcribing", "processing")) or self._is_dragging
                target_interval = 0.030 if needs_anim else 0.050
                elapsed = now - last_frame_time
                if elapsed < target_interval:
                    time.sleep(max(0.001, target_interval - elapsed))
                    continue

                if self._balloon_type and self._balloon_until > 0 and now > self._balloon_until:
                    self._balloon_type = None
                    self._dirty = True

                if self._hover_target != prev_hover:
                    self._dirty = True
                    prev_hover = self._hover_target

                if self._visible and self.hwnd and (needs_anim or self._dirty):
                    self._dirty = False
                    last_frame_time = time.time()
                    self._render_frame(last_frame_time)
                else:
                    time.sleep(0.035)

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
            if hasattr(self, '_class_name') and self._class_name:
                try: user32.UnregisterClassW(self._class_name, kernel32.GetModuleHandleW(None))
                except Exception: pass

    def _render_chrome(self, cfg, S):
        """Rysuje niezmienną część karty (tło, ramka, logo, separator) raz na motyw."""
        W, H = self.w * S, self.h * S
        img = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)

        x1 = int(self.cx0 * S)
        y1 = int(self.cy0 * S)
        x2 = int((self.cx0 + self.cw) * S) - 1
        y2 = int((self.cy0 + self.ch) * S) - 1
        bw = max(1, int(1.0 * S))
        d.rounded_rectangle([x1, y1, x2, y2], radius=int(self.card_r * S), fill=cfg['panel_bg'], outline=cfg['panel_border'], width=bw)

        # Logo: pięć zaokrąglonych słupków fali (nazwa jest tekstem rysowanym w klatce)
        hcy = self.bar_close_cy * S
        lx = x1 + 9.7 * S
        lbw = 1.8 * S
        lgap = 1.4 * S
        for i, lh in enumerate((4, 7, 10, 7, 4)):
            bx_ = lx + i * (lbw + lgap)
            d.rounded_rectangle([bx_, hcy - lh * S / 2, bx_ + lbw, hcy + lh * S / 2], radius=max(1, int(lbw / 2)), fill=cfg['accent'])

        # Separator pod nagłówkiem
        sep_y = int((self.my - 1) * S)
        d.line([(x1 + bw, sep_y), (x2 - bw, sep_y)], fill=cfg['panel_border'], width=bw)
        return img

    def _render_frame(self, t_now):
        cfg = THEMES.get(self.theme, THEMES['dark'])
        S = 3  # nadpróbkowanie kształtów
        W, H = self.w * S, self.h * S

        chrome_key = (self.theme, W, H)
        if not self._chrome_cache or self._chrome_cache[0] != chrome_key:
            self._chrome_cache = (chrome_key, self._render_chrome(cfg, S))
        img = self._chrome_cache[1].copy()
        d = ImageDraw.Draw(img)

        # Tekst odkładany i rysowany na końcu, już w rozmiarze okna (ostry, bez zmniejszania)
        texts = []

        def text(x, y, txt, fill, font_path, size_px, anchor="lm"):
            texts.append((x, y, txt, fill, font_path, size_px, anchor))

        def font(font_path, size_px):
            return get_cached_font(font_path, size_px) or get_cached_font(FONT_REG_PATH, size_px)

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

        is_dark = self.theme in ('dark', 'glass_dark', 'glass_color')
        is_light = self.theme in ('light', 'glass_light')
        # Na niebieskim tle motywu kolorowego niebieskie elementy znikały, więc tam są białe
        blue = (255, 255, 255, 255) if self.theme == 'glass_color' else (77, 115, 255, 255)
        amber = (245, 158, 11, 255)
        thin = max(1, int(1.0 * S))

        # ========================================================
        # 1. DYMEK (błąd / informacja) nad kartą
        # ========================================================
        if self._balloon_type in ("error", "info"):
            bx1, by1 = int(self.px * S), int(self.py * S)
            bx2, by2 = int((self.px + self.pw) * S) - 1, int((self.py + self.ph) * S) - 1
            d.rounded_rectangle([bx1, by1, bx2, by2], radius=int(self.panel_r * S), fill=cfg['panel_bg'], outline=cfg['panel_border'], width=thin)

            icx, icy, ir = (self.px + 14) * S, (self.py + 17) * S, 7 * S
            if self._balloon_type == "error":
                d.ellipse([icx - ir, icy - ir, icx + ir, icy + ir], fill=(209, 52, 56, 255))
                ex = 2.6 * S
                d.line([(icx - ex, icy - ex), (icx + ex, icy + ex)], fill=(255, 255, 255, 255), width=max(1, int(1.4 * S)))
                d.line([(icx - ex, icy + ex), (icx + ex, icy - ex)], fill=(255, 255, 255, 255), width=max(1, int(1.4 * S)))
                raw_msg = "Aby używać wpisywania głosowego, zaznacz pole tekstowe i spróbuj ponownie."
            else:
                d.ellipse([icx - ir, icy - ir, icx + ir, icy + ir], fill=(0, 120, 215, 255))
                dr = 1.0 * S
                d.ellipse([icx - dr, icy - 3.3 * S - dr, icx + dr, icy - 3.3 * S + dr], fill=(255, 255, 255, 255))
                d.line([(icx, icy - 1.0 * S), (icx, icy + 3.4 * S)], fill=(255, 255, 255, 255), width=max(1, int(1.5 * S)))
                raw_msg = getattr(self, '_balloon_text', '') or getattr(self, '_balloon_message', '') or "Informacja"

            fnt_msg = font(FONT_REG_PATH, 9)
            lines = []
            for part in raw_msg.split('\n'):
                lines.extend(_wrap_text_lines(part, self.pw - 36, d, fnt_msg) or [''])
            lines = lines[:3]
            line_h = 12
            start_y = max(self.py + 9, self.py + 17 - (len(lines) - 1) * line_h / 2)
            for idx, line in enumerate(lines):
                text(self.px + 28, start_y + idx * line_h, line, cfg['text'], FONT_REG_PATH, 9)

            rb_x, rb_y, rb_w, rb_h = self.px + 8, self.py + self.ph - 25, self.pw - 16, 19
            if is_light:
                btn_fill = (220, 232, 255, 255) if self._hover_target == 'btn_rozumiem' else (205, 220, 250, 255)
            elif self.theme == 'glass_color':
                btn_fill = (130, 150, 255, 255) if self._hover_target == 'btn_rozumiem' else (110, 130, 245, 255)
            else:
                btn_fill = (45, 60, 90, 255) if self._hover_target == 'btn_rozumiem' else (35, 48, 75, 255)
            d.rounded_rectangle([rb_x * S, rb_y * S, (rb_x + rb_w) * S, (rb_y + rb_h) * S], radius=int(6 * S), fill=btn_fill, outline=cfg['panel_border'], width=thin)
            text(rb_x + rb_w / 2, rb_y + rb_h / 2, "Rozumiem", cfg['text'], FONT_SEMI_PATH, 9, anchor="mm")

        # ========================================================
        # 2. KARTA WIDŻETU (tło, logo i separator są w _render_chrome)
        # ========================================================
        d = ImageDraw.Draw(img)

        # --- Nagłówek: nazwa oraz ··· — × ---
        text(self.cx0 + 30, self.bar_close_cy, "Whiscribe", cfg['text'], FONT_SEMI_PATH, 10)

        bar_cy = self.bar_close_cy * S
        bar_icon_col = cfg.get('bar_btn_col', (65, 85, 120, 255) if not is_dark else (180, 195, 220, 255))
        hov_col = (255, 255, 255, 255) if is_dark else (20, 40, 75, 255)
        hb = 7 * S
        stroke = max(1, int(1.3 * S))

        mcx = self.bar_menu_cx * S
        is_menu_hover = (self._hover_target == 'btn_bar_menu')
        if is_menu_hover:
            d.rounded_rectangle([mcx - hb, bar_cy - hb, mcx + hb, bar_cy + hb], radius=int(4 * S), fill=cfg.get('btn_hover_bg', (200, 212, 230, 255)))
        dot_r = 1.0 * S
        sp = 3.2 * S
        dot_col = hov_col if is_menu_hover else bar_icon_col
        for ox in (-sp, 0, sp):
            d.ellipse([mcx + ox - dot_r, bar_cy - dot_r, mcx + ox + dot_r, bar_cy + dot_r], fill=dot_col)

        mncx = self.bar_min_cx * S
        is_min_hover = (self._hover_target in ('btn_bar_minimize', 'btn_minimize'))
        if is_min_hover:
            d.rounded_rectangle([mncx - hb, bar_cy - hb, mncx + hb, bar_cy + hb], radius=int(4 * S), fill=cfg.get('btn_hover_bg', (200, 212, 230, 255)))
        ln_w = 3.6 * S
        d.line([(mncx - ln_w, bar_cy), (mncx + ln_w, bar_cy)], fill=hov_col if is_min_hover else bar_icon_col, width=stroke)

        ccx = self.bar_close_cx * S
        is_close_hover = (self._hover_target in ('btn_bar_close', 'btn_close'))
        if is_close_hover:
            d.rounded_rectangle([ccx - hb, bar_cy - hb, ccx + hb, bar_cy + hb], radius=int(4 * S), fill=cfg.get('btn_close_hover_bg', (250, 210, 215, 255)))
        csz = 3.0 * S
        close_hover_fallback = (190, 20, 35, 255) if is_light else ((255, 255, 255, 255) if self.theme == 'glass_color' else (255, 100, 110, 255))
        close_col = cfg.get('bar_btn_close_hover', close_hover_fallback) if is_close_hover else bar_icon_col
        d.line([(ccx - csz, bar_cy - csz), (ccx + csz, bar_cy + csz)], fill=close_col, width=stroke)
        d.line([(ccx - csz, bar_cy + csz), (ccx + csz, bar_cy - csz)], fill=close_col, width=stroke)

        # --- Przyciski "Stream" i "Korekta": włączony = podświetlone tło i kolorowy napis ---
        panel = cfg['panel_bg']
        chip_on_col = cfg.get('stream_on_text', blue)
        chip_off_col = _mix(cfg.get('bar_btn_col', cfg['muted']), panel, 0.6)

        def draw_chip(x, y, w, h, label, enabled, hover):
            x1, y1 = int(x * S), int(y * S)
            x2, y2 = int((x + w) * S), int((y + h) * S)
            if enabled:
                fill = cfg.get('toggle_active_hover_bg' if hover else 'toggle_active_bg', (36, 50, 78, 255))
                txt_col = chip_on_col
            else:
                fill = cfg.get('toggle_hover_bg') if hover else None
                txt_col = cfg['text'] if hover else chip_off_col
            if fill is not None:
                d.rounded_rectangle([x1, y1, x2, y2], radius=int(6 * S), fill=fill)
            text(x + w / 2, y + h / 2, label, txt_col, FONT_REG_PATH, self.chip_font_px, anchor="mm")

        draw_chip(self.stream_btn_x, self.stream_btn_y, self.stream_btn_w, self.stream_btn_h, "Stream",
                  self.stream_realtime, self._hover_target == 'btn_toggle_stream')
        draw_chip(self.ai_btn_x, self.ai_btn_y, self.ai_btn_w, self.ai_btn_h, "Korekta",
                  self.ai_enabled, self._hover_target == 'btn_toggle_ai')

        # --- Wygładzona głośność (fala i poświata przycisku) ---
        if self.mode in ("recording", "transcribing"):
            active_vol = vol if self.mode == "recording" else max(vol, loop_vol)
            if active_vol > self._smooth_vol:
                self._smooth_vol = self._smooth_vol * 0.35 + active_vol * 0.65
            else:
                self._smooth_vol = self._smooth_vol * 0.75 + active_vol * 0.25
            if self._smooth_vol < 0.03:
                self._smooth_vol = 0.0
        else:
            self._smooth_vol = 0.0
        # Dyktowanie: poziom z mikrofonu jest już w skali dB 0-1, bez dodatkowego wzmocnienia
        # (to ono sprawiało, że fala zawsze była pełna). Tryb spotkania bez zmian.
        vol_boost = self._smooth_vol if self.mode == "recording" else min(1.0, self._smooth_vol * 1.84)

        # --- Główny przycisk ---
        mic_x = int(self.mic_cx * S)
        mic_y = int(self.mic_cy * S)
        b_rad = int(self.mic_rad * S)
        is_mic_hover = (self._hover_target == 'btn_mic')

        if self.mode == "transcribing":
            show_people = True
        elif self.mode in ("recording", "processing"):
            show_people = (self._session_kind == "meeting" and self.mode == "processing")
        else:
            show_people = (self.widget_mode == "meeting")

        if self.mode in ("recording", "transcribing", "processing"):
            if self.mode == "recording":
                ring_col = cfg['danger']
            elif self.mode == "transcribing":
                ring_col = blue
            else:
                ring_col = amber
            # Delikatnie zabarwione tło, cienka obwódka i ikona w kolorze stanu
            btn_fill = _mix(ring_col, panel, 0.12)
            icon_col = ring_col
            ring_soft = _mix(ring_col, panel, 0.6)

            if self.mode != "processing":
                # Rozchodzące się fale (2 naraz), odrobinę mocniejsze przy głośniejszej mowie
                R = int(b_rad * 1.5) + 2 * S
                layer = Image.new('RGBA', (2 * R, 2 * R), (0, 0, 0, 0))
                ld = ImageDraw.Draw(layer)
                for k in range(2):
                    p = (t_now / 2.4 + k * 0.5) % 1.0
                    rr = b_rad * (1.0 + 0.5 * (1.0 - (1.0 - p) ** 2))
                    a = int(255 * 0.33 * (1.0 - p) * (0.7 + 0.3 * vol_boost))
                    if a > 0:
                        ld.ellipse([R - rr, R - rr, R + rr, R + rr], outline=ring_col[:3] + (a,), width=thin)
                glow, half = _glow_sprite(b_rad + int(2 * S), ring_col[:3] + (int(45 + vol_boost * 50),), int(4 * S))
                img.alpha_composite(glow, (mic_x - half, mic_y - half))
                img.alpha_composite(layer, (mic_x - R, mic_y - R))
                d = ImageDraw.Draw(img)

            d.ellipse([mic_x - b_rad, mic_y - b_rad, mic_x + b_rad, mic_y + b_rad], fill=btn_fill)
            if self.mode == "processing":
                d.ellipse([mic_x - b_rad, mic_y - b_rad, mic_x + b_rad, mic_y + b_rad], outline=_mix(ring_col, panel, 0.3), width=thin)
                ang = (t_now * 300.0) % 360.0
                d.arc([mic_x - b_rad, mic_y - b_rad, mic_x + b_rad, mic_y + b_rad], start=ang, end=ang + 100, fill=ring_col, width=max(2, int(1.5 * S)))
            else:
                d.ellipse([mic_x - b_rad, mic_y - b_rad, mic_x + b_rad, mic_y + b_rad], outline=ring_soft, width=thin)
        else:
            btn_fill = cfg['mic_standby_bg']
            ring_col = cfg['accent'] if is_mic_hover else _mix(cfg['muted'], panel, 0.3)
            icon_col = cfg.get('mic_standby_color', (223, 232, 251, 255))
            d.ellipse([mic_x - b_rad, mic_y - b_rad, mic_x + b_rad, mic_y + b_rad], fill=btn_fill, outline=ring_col, width=thin)

        if show_people:
            draw_people_icon(img, mic_x, mic_y, sz=int(18 * S), color=icon_col)
        else:
            draw_svg_mic(img, mic_x, mic_y, sz=int(15 * S), color=icon_col)
        d = ImageDraw.Draw(img)

        # --- Amplituda: matryca 23 x 7 kropek 2x2 px. Zgaszone kropki tworzą stałą, ledwie widoczną siatkę;
        # w spoczynku świeci środkowy rząd, przy mowie kropki zapalają się symetrycznie od środka ---
        if self.mode == "recording":
            bar_color = cfg['danger']
        elif self.mode == "transcribing":
            bar_color = blue
        else:
            bar_color = cfg['wave']
        live = self.mode in ("recording", "transcribing")

        cols, rows, mid = len(MATRIX_PROFILE), 7, 3
        dot, col_gap, row_gap = 2, 2, 1
        mtx_w = cols * dot + (cols - 1) * col_gap
        mtx_h = rows * dot + (rows - 1) * row_gap
        mtx_x = int(round(self.cx0 + (self.cw - mtx_w) / 2.0))
        mtx_y = int(round(self.wave_cy - mtx_h / 2.0))
        layer = Image.new('RGBA', (mtx_w * S, mtx_h * S), (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        base_a = bar_color[3] / 255.0
        for i, (lo, hi) in enumerate(MATRIX_PROFILE):
            lit = 0
            if live and vol_boost >= 0.03:
                env = math.sin(math.pi * (i + 0.5) / cols) ** 0.6
                mod = 1.0 + 0.25 * math.sin(t_now * 7.5 + i * 0.72) + 0.15 * math.sin(t_now * 12.0 - i * 0.38)
                lit = max(0, min(mid, int(round(mid * vol_boost * env * ((hi - lo) / 22.0) * mod * 1.5))))
            for k in range(rows):
                dd = abs(k - mid)
                if dd > lit:
                    a = 0.13
                else:
                    a = 1.0 - 0.17 * dd
                    if live and dd == lit and dd > 0:
                        a *= 0.55 + 0.45 * (0.5 + 0.5 * math.sin(t_now * 2.0 * math.pi / (1.8 + (i % 5) * 0.3) + i * 0.9))
                xx = i * (dot + col_gap) * S
                yy = k * (dot + row_gap) * S
                ld.rounded_rectangle([xx, yy, xx + dot * S - 1, yy + dot * S - 1], radius=S,
                                     fill=bar_color[:3] + (int(255 * base_a * a),))
        img.alpha_composite(layer, (mtx_x * S, mtx_y * S))
        d = ImageDraw.Draw(img)

        # --- Status: [kropka] [stan] [czas] ---
        if self.mode == "recording":
            dot_col = cfg['danger']
            status_lbl = "Nagrywanie"
            status_col = cfg['text'] if self.theme == 'glass_color' else cfg['danger']
        elif self.mode == "transcribing":
            dot_col = blue
            status_lbl = "Transkrypcja"
            status_col = blue
        elif self.mode == "processing":
            dot_col = amber
            status_lbl = "Przetwarzanie..."
            status_col = amber
        else:
            dot_col = cfg['muted']
            status_lbl = "Gotowe"
            status_col = cfg['muted']

        timer_str = f"{timer_s//60:02d}:{timer_s%60:02d}"
        f_lbl = font(FONT_REG_PATH, 9)
        f_tim = font(FONT_SEMI_PATH, 9)
        lbl_w = f_lbl.getlength(status_lbl) if f_lbl else len(status_lbl) * 5
        tim_w = f_tim.getlength(timer_str) if f_tim else len(timer_str) * 5
        dot_d = 4
        total_line_w = dot_d + 4 + lbl_w + 6 + tim_w
        line_x = self.cx0 + self.cw / 2 - total_line_w / 2.0

        d.ellipse([line_x * S, (self.status_cy - dot_d / 2) * S, (line_x + dot_d) * S, (self.status_cy + dot_d / 2) * S], fill=dot_col)
        text(line_x + dot_d + 4, self.status_cy, status_lbl, status_col, FONT_REG_PATH, 9)
        text(line_x + dot_d + 4 + lbl_w + 6, self.status_cy, timer_str, _mix(cfg['text'], panel, 0.85), FONT_SEMI_PATH, 9)

        # ========================================================
        # 3. ZMNIEJSZENIE, OSTRY TEKST I AKTUALIZACJA OKNA WARSTWOWEGO
        # ========================================================
        # BOX = uśrednienie bloków 3x3: bez prześwitu poza kartę i bez obwódek wokół krawędzi
        frame = img.resize((self.w, self.h), Image.Resampling.BOX)
        fd = ImageDraw.Draw(frame)
        for (x, y, txt, fill, font_path, size_px, anchor) in texts:
            f = font(font_path, size_px)
            if f is not None:
                fd.text((round(x), round(y)), txt, fill=fill, font=f, anchor=anchor)

        if not self.hwnd or not getattr(self, 'p_bits', None):
            return frame

        arr = np.array(frame, dtype=np.uint8)
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
        return frame

    # ========================================================
    # METODY PUBLICZNE (STEROWANIE STANEM)
    # ========================================================
    def show_recording(self):
        with self._lock:
            self.mode = "recording"
            self._session_kind = "dictation"
            self._start_time = time.time()
            self.clear_transcript()
            self._balloon_type = None
            self._dirty = True
        self.show()

    def show_idle(self):
        with self._lock:
            self.mode = "idle"
            self._start_time = 0.0
            self.clear_transcript()
            self._balloon_type = None
            self._dirty = True
        if self.always_on_top or (not self.is_minimized() and self._visible):
            self.show()

    def show_processing(self):
        with self._lock:
            self.mode = "processing"
            self._dirty = True
        if self.always_on_top or (not self.is_minimized() and self._visible):
            self.show()

    def show_meeting_recording(self):
        with self._lock:
            self.mode = "transcribing"
            self._session_kind = "meeting"
            self._start_time = time.time()
            self.clear_transcript()
            self._balloon_type = None
            self._dirty = True
        self.show()

    def show_balloon(self, kind: str = "info", text: str = "", duration_s: float = 4.0):
        """Wyświetla dymek powiadomienia (info lub error) z określonym tekstem."""
        with self._lock:
            self._balloon_type = kind
            self._balloon_text = text
            self._balloon_until = time.time() + duration_s if duration_s > 0 else 0
            self._dirty = True
        self.show()

    def show_error_balloon(self, duration_s=7.0):
        self.show_balloon("error", "", duration_s=duration_s)

    def hide_balloon(self):
        with self._lock:
            self._balloon_type = None
            self._balloon_text = ""
            self._balloon_until = 0
            self._dirty = True

    def update_live_text(self, text: str):
        if text:
            with self._lock:
                self.live_tail = text.strip()
                if not self._user_scrolled:
                    self.scroll_line = 999999
            self._dirty = True

    def add_transcript_entry(self, text: str, timestamp_s: float = None):
        if not text:
            return
        with self._lock:
            self.transcript_lines.append({"text": text.strip()})
            if len(self.transcript_lines) > 100:
                self.transcript_lines = self.transcript_lines[-100:]
            self.live_tail = ""
            if not self._user_scrolled:
                self.scroll_line = 999999
            self._dirty = True

    def clear_transcript(self):
        with self._lock:
            self.transcript_lines = []
            self.live_tail = ""
            self.scroll_line = 0
            self._user_scrolled = False
        self._dirty = True

    def show(self):
        self._visible = True
        self._dirty = True
        if self.hwnd:
            if user32.IsIconic(self.hwnd):
                user32.ShowWindow(self.hwnd, 9)  # SW_RESTORE
            else:
                user32.ShowWindow(self.hwnd, 8)  # SW_SHOWNA
            hwnd_insert = -1 if self.always_on_top else -2
            user32.SetWindowPos(self.hwnd, hwnd_insert, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010)

    def hide(self):
        self._visible = False
        self._dirty = True
        if self.hwnd:
            user32.ShowWindow(self.hwnd, 0)

    def minimize(self):
        """Minimalizuje widżet do dolnego paska zadań Windows 11."""
        self._user_minimized = True
        self._visible = False
        self._dirty = True
        if self.hwnd:
            user32.ShowWindow(self.hwnd, 6)  # SW_MINIMIZE

    def restore(self):
        """Przywraca okno widżetu z dolnego paska zadań na ekran."""
        self._user_minimized = False
        self._visible = True
        self._dirty = True
        if self.hwnd:
            user32.ShowWindow(self.hwnd, 9)  # SW_RESTORE
            hwnd_insert = -1 if self.always_on_top else -2
            user32.SetWindowPos(self.hwnd, hwnd_insert, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010)
            _add_hwnd_to_taskbar(self.hwnd)
            self._render_frame(time.time())

    def is_minimized(self) -> bool:
        if getattr(self, '_user_minimized', False):
            return True
        if self.hwnd:
            return bool(user32.IsIconic(self.hwnd)) or not self._visible
        return not self._visible

    def set_always_on_top(self, enable: bool):
        """Dynamicznie włącza lub wyłącza tryb 'Zawsze na wierzchu' (HWND_TOPMOST vs HWND_NOTOPMOST)."""
        with self._lock:
            self.always_on_top = bool(enable)
        if self.hwnd:
            self._visible = True
            if self.always_on_top:
                if user32.IsIconic(self.hwnd):
                    user32.ShowWindow(self.hwnd, 9)  # SW_RESTORE
                else:
                    user32.ShowWindow(self.hwnd, 8)  # SW_SHOWNA
            GWL_EXSTYLE = -20
            WS_EX_TOPMOST = 0x00000008
            cur_ex = _GetWindowLong(self.hwnd, GWL_EXSTYLE)
            if self.always_on_top:
                new_ex = cur_ex | WS_EX_TOPMOST
                hwnd_insert = -1  # HWND_TOPMOST
            else:
                new_ex = cur_ex & ~WS_EX_TOPMOST
                hwnd_insert = -2  # HWND_NOTOPMOST
            _SetWindowLong(self.hwnd, GWL_EXSTYLE, new_ex)
            user32.SetWindowPos(
                self.hwnd, hwnd_insert, 0, 0, 0, 0,
                0x0001 | 0x0002 | 0x0010 | 0x0020  # SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE | SWP_FRAMECHANGED
            )
            self._dirty = True

    def set_widget_mode(self, mode: str):
        """Tryb głównego przycisku: "dictation" (mikrofon) albo "meeting" (transkrypcja rozmowy)."""
        with self._lock:
            self.widget_mode = "meeting" if mode == "meeting" else "dictation"
            self._dirty = True

    def set_theme(self, theme_name: str):
        if theme_name in THEME_MAP:
            theme_name = THEME_MAP[theme_name]
        if theme_name in THEMES and theme_name != self.theme:
            self.theme = theme_name
            self._dirty = True
            if self.on_theme_changed:
                try: self.on_theme_changed(self.theme)
                except Exception: pass

    def register_system_hotkey(self, hotkey_id: int, hk_str: str) -> bool:
        """Rejestruje globalny skrót w systemie Windows za pomocą Win32 RegisterHotKey w wątku okna."""
        if not self.hwnd or not user32.IsWindow(self.hwnd):
            return False
        mods, vk = parse_hotkey_to_win32(hk_str)
        if not vk:
            return False
        lparam = ((mods & 0xFFFF) << 16) | (vk & 0xFFFF)
        res = user32.SendMessageW(self.hwnd, 0x8001, hotkey_id, lparam)
        return bool(res)

    def unregister_system_hotkey(self, hotkey_id: int):
        if self.hwnd and user32.IsWindow(self.hwnd):
            user32.SendMessageW(self.hwnd, 0x8002, hotkey_id, 0)

    def is_alive(self):
        return self._thread is not None and self._thread.is_alive()

    def stop(self):
        self.close()

    def close(self):
        self._running = False
        self.unregister_system_hotkey(101)
        self.unregister_system_hotkey(102)
        if self.hwnd and user32.IsWindow(self.hwnd):
            user32.PostMessageW(self.hwnd, 0x0010, 0, 0)
        if self._thread and self._thread.is_alive() and threading.current_thread() != self._thread:
            self._thread.join(timeout=0.8)
