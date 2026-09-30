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
        'glow2': (178, 112, 255, 10)
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
        'glow2': (178, 112, 255, 14)
    },
    'glass_light': {
        'name': 'Glass Jasny (Mica Light)',
        'panel_bg': (255, 255, 255, 185),
        'panel_border': (255, 255, 255, 180),
        'bar_bg': (206, 218, 236, 190),
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
        'glow2': (200, 170, 255, 18)
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
        'glow2': (178, 112, 255, 18)
    },
    'glass_color': {
        'name': 'Glass Kolorowy (Vibrant Glass)',
        'panel_bg': (86, 111, 235, 215),
        'panel_border': (255, 255, 255, 140),
        'bar_bg': (74, 76, 171, 190),
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
        'glow2': (255, 116, 220, 30)
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

_ICON_CACHE = {}

def get_svg_mic_image(sz, color=(255, 255, 255, 255)):
    """Render supersampled (4x) vector microphone icon from exact prototype SVG."""
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

    # <rect x="8" y="3" width="8" height="12" rx="4"></rect>
    rx1 = 8.0 * scale
    ry1 = 3.0 * scale
    rx2 = 16.0 * scale
    ry2 = 15.0 * scale
    d.rounded_rectangle([rx1, ry1, rx2, ry2], radius=int(4.0 * scale), outline=color, width=stroke)

    # <path d="M5 11a7 7 0 0 0 14 0 ..."> (Cradle arc centered at 12, 11 r=7)
    cx1 = 5.0 * scale
    cy1 = 4.0 * scale
    cx2 = 19.0 * scale
    cy2 = 18.0 * scale
    d.arc([cx1, cy1, cx2, cy2], start=0, end=180, fill=color, width=stroke)

    # ... M12 18v3 ... (Stem)
    sx = 12.0 * scale
    sy1 = 18.0 * scale
    sy2 = 21.0 * scale
    d.line([(sx, sy1), (sx, sy2)], fill=color, width=stroke)

    # ... M8.5 21h7 ... (Base foot)
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
    """Render supersampled (4x) vector people icon from exact prototype SVG."""
    key = ('people', sz, color)
    if key in _ICON_CACHE:
        return _ICON_CACHE[key]
    ss = 4
    w = max(4, sz * ss)
    h = max(4, sz * ss)
    img = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    scale = w / 38.0

    # <circle cx="14" cy="13" r="6"></circle>
    c1x, c1y, r1 = 14.0 * scale, 13.0 * scale, 6.0 * scale
    d.ellipse([c1x - r1, c1y - r1, c1x + r1, c1y + r1], fill=color)

    # <circle cx="27" cy="15" r="4.6"></circle>
    c2x, c2y, r2 = 27.0 * scale, 15.0 * scale, 4.6 * scale
    d.ellipse([c2x - r2, c2y - r2, c2x + r2, c2y + r2], fill=color)

    # <path d="M3.5 30c0-5.2 4.3-9.4 9.5-9.4s9.5 4.2 9.5 9.4H3.5Z"></path>
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

    # <path d="M22 29.5c.3-3.6 3.3-6.6 7-6.6 3.6 0 6.5 2.8 6.9 6.6H22Z"></path>
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

def draw_svg_mic(target, cx, cy, sz, color=(255, 255, 255, 255)):
    """SVG Microphone icon matching HTML prototype (viewBox 0 0 24 24, stroke-width 2)."""
    img_dest = target if isinstance(target, Image.Image) else getattr(target, '_image', None)
    mic_img = get_svg_mic_image(sz, color)
    if img_dest:
        img_dest.alpha_composite(mic_img, (int(round(cx - sz / 2.0)), int(round(cy - sz / 2.0))))

def draw_people_icon(target, cx, cy, sz, color=(255, 255, 255, 255)):
    """SVG Group / People icon matching HTML prototype (viewBox 0 0 38 38, fill currentColor)."""
    img_dest = target if isinstance(target, Image.Image) else getattr(target, '_image', None)
    people_img = get_people_image(sz, color)
    if img_dest:
        img_dest.alpha_composite(people_img, (int(round(cx - sz / 2.0)), int(round(cy - sz / 2.0))))

def _create_taskbar_icon():
    """Generuje elegancką ikonę HICON dla paska zadań Windows 11 (granatowa bez obwiedni, biały mikrofon)."""
    try:
        temp_dir = tempfile.gettempdir()
        ico_path = os.path.join(temp_dir, "voice_ui_taskbar.ico")
        img_hi = Image.new('RGBA', (256, 256), color=(0, 0, 0, 0))
        d = ImageDraw.Draw(img_hi)
        # Granatowe tło bez obwiedni (Navy Blue)
        d.ellipse((10, 10, 246, 246), fill=(18, 28, 58, 255))
        # Czysty biały mikrofon wektorowy
        draw_svg_mic(img_hi, 128, 128, 124, color=(255, 255, 255, 255))
        img_hi.save(ico_path, format='ICO', sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
        return user32.LoadImageW(None, ico_path, 1, 32, 32, 0x0010)
    except Exception:
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
    Wiernie odwzorowany interfejs Voice UI zgodny w 100% z prototypem użytkownika (250x90 Voice Module + Panel Transkrypcji).
    - Zablokowanie kradzieży fokusu (WS_EX_NOACTIVATE, MA_NOACTIVATE)
    - Płynne przeciąganie po obu monitorach
    - Kreski reaktywne fali dźwiękowej (27 słupków z dynamiczną modulacją)
    - Panel transkrypcji z pełnym przewijaniem (scroll myszą i suwak) bez znaczników czasu
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

        # Wymiary całego okna warstwowego z bezpiecznym buforem dla miękkich cieni (brak uciętych krawędzi)
        self.w = 320
        self.h = 280

        # Moduł dolny (Voice Module): 250x90 px
        self.mw = 250
        self.mh = 90
        self.mx = (self.w - self.mw) // 2       # 35 px margines z lewej i prawej
        self.my = self.h - self.mh - 20          # 20 px margines od dołu (y=170)
        self.mod_r = 20

        # Belka górna (Window Bar): 250x27 px
        self.bw = 250
        self.bh = 27
        self.bx = self.mx                       # 35 px (y=143 do 170)
        self.by = self.my - self.bh             # 143 px
        self.bar_r = 15

        # Przyciski belki górnej (.window-bar):
        self.tgl_btn_x = self.bx + 8
        self.tgl_btn_y = self.by + 4
        self.tgl_btn_w = 98
        self.tgl_btn_h = 19

        self.bar_close_cx = self.bx + self.bw - 16   # 269
        self.bar_close_cy = self.by + 13.5           # 156.5
        self.bar_min_cx = self.bar_close_cx - 22     # 247
        self.bar_min_cy = self.by + 13.5             # 156.5
        self.bar_menu_cx = self.bar_min_cx - 22      # 225
        self.bar_menu_cy = self.by + 13.5            # 156.5

        # Zachowanie kompatybilności dla dawnych odwołań
        self.close_cx = self.bar_close_cx
        self.close_cy = self.bar_close_cy
        self.min_cx = self.bar_min_cx
        self.min_cy = self.bar_min_cy

        # Panel górny (Transkrypcja z przewijaniem): 250x110 px
        self.pw = 250
        self.ph = 110
        self.px = (self.w - self.pw) // 2            # 35 px margines z lewej i prawej
        self.py = self.by - self.ph - 8              # 8 px odstęp nad belką okna (y=25)
        self.panel_r = 16
        self.panel_open = False                      # Domyślnie wyłączona transkrypcja!
        self.show_live_preview = False
        self._smooth_vol = 0.0

        # Przewijanie transkrypcji (Scroll & Drag)
        self.scroll_line = 0
        self._user_scrolled = False
        self._is_scrolling = False
        self._total_lines_count = 0
        self._max_visible_lines = 4

        # Uchwyt do przeciągania
        self.handle_w = 29
        self.handle_h = 3
        self.handle_x = self.mx + (self.mw - self.handle_w) / 2
        self.handle_y = self.my + 6.0

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
        self.on_minimize_callback = None
        self.on_restore_callback = None
        self.on_hotkey_callback = None
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

    def set_callbacks(self, on_stop=None, on_close=None, on_toggle=None, on_meeting_toggle=None, on_minimize=None, on_restore=None, on_hotkey=None):
        self.on_stop_callback = on_stop
        self.on_close_callback = on_close
        self.on_toggle_callback = on_toggle
        self.on_meeting_toggle_callback = on_meeting_toggle
        self.on_minimize_callback = on_minimize
        self.on_restore_callback = on_restore
        if on_hotkey is not None:
            self.on_hotkey_callback = on_hotkey

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

    def _is_inside_bar(self, x, y):
        return (self.bx <= x <= self.bx + self.bw) and (self.by <= y <= self.by + self.bh)

    def _is_inside_panel(self, x, y):
        if not self.panel_open and not self._balloon_type:
            return False
        return (self.px <= x <= self.px + self.pw) and (self.py <= y <= self.py + self.ph)

    def _get_target(self, x, y):
        # 1. Sprawdź kliknięcie w panelu górnym
        if self._balloon_type == "error":
            btn_x = self.px + 16
            btn_y = self.py + self.ph - 30
            btn_w = self.pw - 32
            btn_h = 24
            if (btn_x <= x <= btn_x + btn_w) and (btn_y <= y <= btn_y + btn_h):
                return 'btn_rozumiem'
            if self._is_inside_panel(x, y):
                return 'balloon_body'

        elif self.panel_open:
            close_px = self.px + self.pw - 14
            close_py = self.py + 11
            if abs(x - close_px) <= 12 and abs(y - close_py) <= 12:
                return 'btn_panel_close'

            sb_x = self.px + self.pw - 8
            sb_y = self.py + 24
            sb_h = self.ph - 32
            if (sb_x - 12 <= x <= sb_x + 12) and (sb_y <= y <= sb_y + sb_h):
                return 'scrollbar'

            if self._is_inside_panel(x, y):
                return 'panel_content'

        # 2. Sprawdź kontrolki na belce okna (.window-bar)
        if self._is_inside_bar(x, y):
            # Przycisk Zamknij ✕
            if abs(x - self.bar_close_cx) <= 12 and (self.by <= y <= self.by + self.bh):
                return 'btn_bar_close'

            # Przycisk Zminimalizuj −
            if abs(x - self.bar_min_cx) <= 12 and (self.by <= y <= self.by + self.bh):
                return 'btn_bar_minimize'

            # Przycisk Menu •••
            if abs(x - self.bar_menu_cx) <= 12 and (self.by <= y <= self.by + self.bh):
                return 'btn_bar_menu'

            # Przycisk Pokaż / Zwiń transkrypcję
            if (self.tgl_btn_x <= x <= self.tgl_btn_x + self.tgl_btn_w) and (self.by <= y <= self.by + self.bh):
                return 'btn_toggle_transcript'

            # Przeciąganie za belkę okna
            return 'widget_drag'

        # 3. Sprawdź kontrolki w module dolnym (.voice-module)
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
        WM_MOUSEWHEEL = 0x020A

        if msg == WM_MOUSEACTIVATE:
            # Kluczowe: kliknięcie w widżet NIE kradnie fokusu z edytora docelowego!
            return MA_NOACTIVATE

        WM_HOTKEY = 0x0312
        if msg == WM_HOTKEY:
            hotkey_id = int(wparam)
            if self.on_hotkey_callback:
                threading.Thread(target=self.on_hotkey_callback, args=(hotkey_id,), daemon=True).start()
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
                user32.ShowWindow(hwnd, 6)  # SW_MINIMIZE
                if self.on_minimize_callback:
                    threading.Thread(target=self.on_minimize_callback, daemon=True).start()
                return 0
            elif cmd == SC_RESTORE:
                user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                self._dirty = True
                if self.on_restore_callback:
                    threading.Thread(target=self.on_restore_callback, daemon=True).start()
                return 0

        if msg == WM_SIZE:
            if wparam == 0:  # SIZE_RESTORED
                self._dirty = True
                if self.on_restore_callback:
                    threading.Thread(target=self.on_restore_callback, daemon=True).start()
            elif wparam == 1:  # SIZE_MINIMIZED
                if self.on_minimize_callback:
                    threading.Thread(target=self.on_minimize_callback, daemon=True).start()
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
            x = lparam & 0xFFFF
            y = (lparam >> 16) & 0xFFFF
            if x > 0x7FFF: x -= 0x10000
            if y > 0x7FFF: y -= 0x10000
            pt = wintypes.POINT(x, y)
            user32.ScreenToClient(hwnd, ctypes.byref(pt))

            if self._is_inside_module(pt.x, pt.y) or self._is_inside_bar(pt.x, pt.y) or self._is_inside_panel(pt.x, pt.y):
                return 1  # HTCLIENT
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
            if self._hover_target in ('btn_mic', 'btn_meeting', 'btn_bar_close', 'btn_bar_minimize', 'btn_bar_menu', 'btn_toggle_transcript', 'btn_close', 'btn_minimize', 'btn_panel_close', 'btn_rozumiem', 'scrollbar'):
                user32.SetCursor(self._hcursor_hand)
                return 1
            elif self._hover_target in ('widget_drag', 'panel_content', 'balloon_body'):
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

            if target in ('widget_drag', 'panel_content', 'balloon_body'):
                self._is_dragging = True
                user32.SetCapture(hwnd)
                cur_pt = wintypes.POINT()
                user32.GetCursorPos(ctypes.byref(cur_pt))
                self._drag_start_cursor_x = cur_pt.x
                self._drag_start_cursor_y = cur_pt.y
                self._drag_start_win_x = self.pos_x
                self._drag_start_win_y = self.pos_y
            elif target == 'scrollbar':
                self._is_scrolling = True
                user32.SetCapture(hwnd)
                sb_norm_y = self.py + 24
                sb_norm_h = max(1, self.ph - 32)
                ratio = max(0.0, min(1.0, (y - sb_norm_y) / float(sb_norm_h)))
                with self._lock:
                    max_scroll = max(0, self._total_lines_count - self._max_visible_lines)
                    self.scroll_line = int(round(ratio * max_scroll))
                    self._user_scrolled = (self.scroll_line < max_scroll)
                self._dirty = True
            return 0

        elif msg == WM_LBUTTONUP:
            if self._is_dragging:
                self._is_dragging = False
                user32.ReleaseCapture()

            if self._is_scrolling:
                self._is_scrolling = False
                user32.ReleaseCapture()
                self._dirty = True

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

                elif target == 'btn_toggle_transcript':
                    self.panel_open = not self.panel_open
                    self._dirty = True

                elif target == 'btn_rozumiem':
                    self.hide_balloon()

                elif target == 'btn_bar_menu' or (self._pressed_btn == 'btn_bar_menu' and abs(x - self.bar_menu_cx) <= 15 and (self.by - 2 <= y <= self.by + self.bh + 2)):
                    menu_screen_x = self.pos_x + int(self.bar_menu_cx)
                    menu_screen_y = self.pos_y + int(self.by + self.bh)
                    if self.settings_handler:
                        threading.Thread(target=self.settings_handler, args=(menu_screen_x, menu_screen_y), daemon=True).start()

                elif target in ('btn_bar_minimize', 'btn_minimize'):
                    if self.on_minimize_callback:
                        threading.Thread(target=self.on_minimize_callback, daemon=True).start()
                    else:
                        self.minimize()

                elif target in ('btn_bar_close', 'btn_close'):
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
            WS_EX_APPWINDOW = 0x00040000
            WS_EX_NOACTIVATE = 0x08000000

            WS_POPUP = 0x80000000
            WS_MINIMIZEBOX = 0x00020000
            WS_SYSMENU = 0x00080000

            self.hwnd = user32.CreateWindowExW(
                WS_EX_LAYERED | WS_EX_TOPMOST | WS_EX_APPWINDOW | WS_EX_NOACTIVATE,
                self._class_name,
                "Whiscribe",
                WS_POPUP | WS_MINIMIZEBOX | WS_SYSMENU,
                self.pos_x, self.pos_y, self.w, self.h,
                None, None, wc.hInstance, None
            )

            if h_icon:
                user32.SendMessageW(self.hwnd, 0x0080, 1, h_icon)  # WM_SETICON ICON_BIG
                user32.SendMessageW(self.hwnd, 0x0080, 0, h_icon)  # WM_SETICON ICON_SMALL

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
            if hasattr(self, '_class_name') and self._class_name:
                try: user32.UnregisterClassW(self._class_name, kernel32.GetModuleHandleW(None))
                except Exception: pass

    def _render_frame(self, t_now):
        cfg = THEMES.get(self.theme, THEMES['dark'])
        scale = 2
        W, H = self.w * scale, self.h * scale

        img = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)

        # Czcionki
        try:
            fnt_tab = ImageFont.truetype(FONT_SEMI_PATH, int(8.2 * scale))
            fnt_text = ImageFont.truetype(FONT_REG_PATH, int(8.8 * scale))
            fnt_time = ImageFont.truetype(FONT_REG_PATH, int(8.2 * scale))
            fnt_status = ImageFont.truetype(FONT_REG_PATH, int(8.5 * scale))
            fnt_timer = ImageFont.truetype(FONT_BOLD_PATH, int(8.5 * scale))
            fnt_close = ImageFont.truetype(FONT_REG_PATH, int(15 * scale))
        except Exception:
            try:
                fnt_tab = ImageFont.truetype(FONT_BOLD_PATH, int(8.5 * scale))
            except Exception:
                fnt_tab = ImageFont.load_default()
            fnt_text = fnt_time = fnt_status = fnt_timer = fnt_close = ImageFont.load_default()

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
            sh_offset_y = int(2.5 * scale)
            sh_blur = int(4.5 * scale)
            sd.rounded_rectangle([px, py + sh_offset_y, px + pw, py + ph + sh_offset_y], radius=pr, fill=(0, 0, 0, cfg.get('shadow_alpha', 30)))
            sh = sh.filter(ImageFilter.GaussianBlur(radius=sh_blur))
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
            if self.theme in ('light', 'glass_light'):
                btn_fill = (220, 232, 255, 255) if self._hover_target == 'btn_rozumiem' else (205, 220, 250, 255)
            elif self.theme == 'glass_color':
                btn_fill = (130, 150, 255, 255) if self._hover_target == 'btn_rozumiem' else (110, 130, 245, 255)
            else:
                btn_fill = (45, 60, 90, 255) if self._hover_target == 'btn_rozumiem' else (35, 48, 75, 255)
            d.rounded_rectangle([btn_x, btn_y, btn_x + btn_w, btn_y + btn_h], radius=int(6*scale), fill=btn_fill, outline=cfg['panel_border'])
            d.text((btn_x + btn_w/2, btn_y + btn_h/2 - int(0.5*scale)), "Rozumiem", fill=cfg['text'], font=fnt_tab, anchor="mm")

        elif self.panel_open:
            # Uproszczony panel transkrypcji (nagłówek 22px z pojedynczym krzyżykiem z prawej)
            sh_p = Image.new('RGBA', (W, H), (0, 0, 0, 0))
            spd = ImageDraw.Draw(sh_p)
            sh_offset_y = int(2.5 * scale)
            sh_blur = int(4.5 * scale)
            spd.rounded_rectangle([px, py + sh_offset_y, px + pw, py + ph + sh_offset_y], radius=pr, fill=(0, 0, 0, cfg.get('shadow_alpha', 30)))
            sh_p = sh_p.filter(ImageFilter.GaussianBlur(radius=sh_blur))
            img.alpha_composite(sh_p)

            d = ImageDraw.Draw(img)
            d.rounded_rectangle([px, py, px + pw, py + ph], radius=pr, fill=cfg['panel_bg'], outline=cfg['panel_border'], width=max(1, int(1.1*scale)))

            # Nagłówek panelu (22px) z linią rozdzielającą
            head_h = int(22 * scale)
            d.line([(px, py + head_h), (px + pw, py + head_h)], fill=cfg['panel_border'], width=max(1, int(1*scale)))

            # Przycisk ✕ (zamknij panel transkrypcji z prawej strony)
            close_px = px + pw - int(14 * scale)
            close_py = py + int(11 * scale)
            if self._hover_target == 'btn_panel_close':
                d.ellipse([close_px - int(7*scale), close_py - int(7*scale), close_px + int(7*scale), close_py + int(7*scale)], fill=cfg.get('panel_close_hover_bg', (200, 210, 230, 255)))
            csz = int(3.5 * scale)
            close_col = (255, 80, 80, 255) if self._hover_target == 'btn_panel_close' else cfg['muted']
            d.line([(close_px - csz, close_py - csz), (close_px + csz, close_py + csz)], fill=close_col, width=max(1, int(1.3 * scale)))
            d.line([(close_px - csz, close_py + csz), (close_px + csz, close_py - csz)], fill=close_col, width=max(1, int(1.3 * scale)))

            # Linie transkrypcji (pełna treść bez znaczników czasu, z płynnym przewijaniem)
            with self._lock:
                lines = list(self.transcript_lines)
                live_text = self.live_tail

            max_text_w = pw - int(24 * scale)
            tx_x = px + int(12 * scale)
            all_lines = []

            for item in lines:
                txt = item.get("text", "") if isinstance(item, dict) else str(item)
                if not txt:
                    continue
                w_lines = _wrap_text_lines(txt, max_text_w, d, fnt_text)
                for wl in w_lines:
                    all_lines.append((wl, False))

            if live_text and (not all_lines or self.mode in ("recording", "transcribing")):
                w_live = _wrap_text_lines(live_text, max_text_w, d, fnt_text)
                for idx, wl in enumerate(w_live):
                    is_last = (idx == len(w_live) - 1)
                    all_lines.append((wl, is_last))

            line_h = int(14 * scale)
            content_h = (ph - head_h - int(12 * scale))
            max_visible = max(1, content_h // line_h)
            self._max_visible_lines = max_visible
            self._total_lines_count = len(all_lines)

            if not all_lines:
                d.text((px + pw/2, py + head_h + int(36 * scale)), "Transkrypcja pojawi się tutaj podczas mówienia.", fill=cfg['muted'], font=fnt_text, anchor="mm")
            else:
                max_scroll = max(0, len(all_lines) - max_visible)
                if not self._user_scrolled:
                    self.scroll_line = max_scroll
                else:
                    self.scroll_line = max(0, min(max_scroll, self.scroll_line))

                start_idx = self.scroll_line
                visible_slice = all_lines[start_idx : start_idx + max_visible]

                cur_y = py + head_h + int(6 * scale)
                for wl, is_last_live in visible_slice:
                    d.text((tx_x, cur_y), wl, fill=cfg['text'], font=fnt_text)

                    # Karetka | na końcu ostatniej linii podczas nagrywania na żywo
                    if is_last_live and self.mode in ("recording", "transcribing"):
                        bbox = d.textbbox((tx_x, cur_y), wl, font=fnt_text)
                        caret_x = bbox[2] + int(2 * scale)
                        caret_y = cur_y + int(1.5 * scale)
                        if int(t_now * 2) % 2 == 0:
                            d.rounded_rectangle([caret_x, caret_y, caret_x + int(2.5 * scale), caret_y + int(9 * scale)], radius=int(1*scale), fill=cfg['accent'])

                    cur_y += line_h

            # Pasek przewijania (interaktywny suwak)
            sb_x = px + pw - int(8 * scale)
            sb_y = py + head_h + int(5 * scale)
            sb_w = int(3.5 * scale)
            sb_h = max(10, ph - head_h - int(10 * scale))
            d.rounded_rectangle([sb_x, sb_y, sb_x + sb_w, sb_y + sb_h], radius=int(sb_w/2), fill=cfg['scroll_track'])

            if len(all_lines) > max_visible:
                max_scroll = len(all_lines) - max_visible
                thumb_h = max(int(14 * scale), int(sb_h * (max_visible / float(len(all_lines)))))
                scroll_ratio = max(0.0, min(1.0, self.scroll_line / float(max_scroll)))
                thumb_y = sb_y + int((sb_h - thumb_h) * scroll_ratio)
                thumb_fill = cfg['accent'] if self._hover_target == 'scrollbar' or self._is_scrolling else cfg['scroll_thumb']
                d.rounded_rectangle([sb_x, thumb_y, sb_x + sb_w, thumb_y + thumb_h], radius=int(sb_w/2), fill=thumb_fill)
            else:
                thumb_h = int(24 * scale)
                d.rounded_rectangle([sb_x, sb_y + int(4*scale), sb_x + sb_w, sb_y + int(4*scale) + thumb_h], radius=int(sb_w/2), fill=cfg['scroll_thumb'])

        # ========================================================
        # 2. OKNO GŁÓWNE: POŁĄCZONA BELKA I MODUŁ GŁOSU
        # ========================================================
        bx = int(self.bx * scale)
        by = int(self.by * scale)
        bw = int(self.bw * scale)
        bh = int(self.bh * scale)

        mx = int(self.mx * scale)
        my = int(self.my * scale)
        mw = int(self.mw * scale)
        mh = int(self.mh * scale)

        # Cień połączonej karty okna (Window Bar + Voice Module)
        sh_m = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        smd = ImageDraw.Draw(sh_m)
        sh_offset_y = int(2.5 * scale)
        sh_blur = int(5.0 * scale)
        smd.rounded_rectangle([bx, by + sh_offset_y, bx + bw, my + sh_offset_y], radius=int(self.bar_r * scale), corners=(True, True, False, False), fill=(0, 0, 0, cfg.get('shadow_alpha', 30)))
        smd.rounded_rectangle([mx, my + sh_offset_y, mx + mw, my + mh + sh_offset_y], radius=int(self.mod_r * scale), corners=(False, False, True, True), fill=(0, 0, 0, cfg.get('shadow_alpha', 30)))
        sh_m = sh_m.filter(ImageFilter.GaussianBlur(radius=sh_blur))
        img.alpha_composite(sh_m)

        # Tła i obramowania połączonej karty
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([bx, by, bx + bw, my], radius=int(self.bar_r * scale), corners=(True, True, False, False), fill=cfg.get('bar_bg', cfg['panel_bg']))
        d.rounded_rectangle([mx, my, mx + mw, my + mh], radius=int(self.mod_r * scale), corners=(False, False, True, True), fill=cfg['panel_bg'])

        border_w = max(1, int(1.1 * scale))
        d.rounded_rectangle([bx, by, bx + bw, my], radius=int(self.bar_r * scale), corners=(True, True, False, False), outline=cfg['panel_border'], width=border_w)
        d.rounded_rectangle([mx, my, mx + mw, my + mh], radius=int(self.mod_r * scale), corners=(False, False, True, True), outline=cfg['panel_border'], width=border_w)
        d.line([(bx, my), (bx + bw, my)], fill=cfg['panel_border'], width=border_w)

        # Subtelne radialne podświetlenie karty modułu
        glow_mod = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        gmd = ImageDraw.Draw(glow_mod)
        g_col1 = cfg.get('glow1', (105, 157, 255, 14))
        g_col2 = cfg.get('glow2', (178, 112, 255, 12))
        gmd.ellipse([mx - int(10*scale), my - int(10*scale), mx + int(90*scale), my + mh + int(10*scale)], fill=g_col1)
        gmd.ellipse([mx + mw - int(90*scale), my - int(10*scale), mx + mw + int(10*scale), my + mh + int(10*scale)], fill=g_col2)
        glow_mod = glow_mod.filter(ImageFilter.GaussianBlur(radius=int(12*scale)))

        card_mask = Image.new('L', (W, H), 0)
        cmd = ImageDraw.Draw(card_mask)
        cmd.rounded_rectangle([mx, my, mx + mw, my + mh], radius=int(self.mod_r * scale), corners=(False, False, True, True), fill=255)
        glow_mod_masked = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        glow_mod_masked.paste(glow_mod, (0, 0), mask=card_mask)
        img.alpha_composite(glow_mod_masked)
        d = ImageDraw.Draw(img)

        # --- KONTROLKI BELKI GÓRNEJ (.window-bar) ---
        # 1. Przycisk "Pokaż transkrypcję" / "Zwiń transkrypcję"
        tgl_x = int(self.tgl_btn_x * scale)
        tgl_y = int(self.tgl_btn_y * scale)
        tgl_w = int(self.tgl_btn_w * scale)
        tgl_h = int(self.tgl_btn_h * scale)

        is_dark = self.theme in ('dark', 'glass_dark', 'glass_color')

        if self.panel_open:
            if self._hover_target == 'btn_toggle_transcript':
                d.rounded_rectangle([tgl_x, tgl_y, tgl_x + tgl_w, tgl_y + tgl_h], radius=int(6*scale), fill=cfg.get('toggle_active_hover_bg', cfg.get('toggle_active_bg')))
            else:
                d.rounded_rectangle([tgl_x, tgl_y, tgl_x + tgl_w, tgl_y + tgl_h], radius=int(6*scale), fill=cfg.get('toggle_active_bg'))
            tgl_lbl = "Zwiń transkrypcję"
            tgl_col = (255, 255, 255, 255) if is_dark else (20, 40, 75, 255)
        elif self._hover_target == 'btn_toggle_transcript':
            d.rounded_rectangle([tgl_x, tgl_y, tgl_x + tgl_w, tgl_y + tgl_h], radius=int(6*scale), fill=cfg.get('toggle_hover_bg', (200, 212, 230, 255)))
            tgl_lbl = "Pokaż transkrypcję"
            tgl_col = (255, 255, 255, 255) if is_dark else (20, 40, 75, 255)
        else:
            tgl_lbl = "Pokaż transkrypcję"
            tgl_col = cfg['muted']

        d.text((tgl_x + int(8*scale), tgl_y + tgl_h//2 - int(0.5*scale)), tgl_lbl, fill=tgl_col, font=fnt_tab, anchor="lm")

        # 2. Przyciski sterowania oknem po prawej stronie
        bar_cy = int(self.bar_close_cy * scale)

        # 2a. Przycisk Menu ••• (otwiera pełne menu ustawień)
        mcx = int(self.bar_menu_cx * scale)
        if self._hover_target == 'btn_bar_menu':
            d.rounded_rectangle([mcx - int(9*scale), bar_cy - int(9*scale), mcx + int(9*scale), bar_cy + int(9*scale)], radius=int(5*scale), fill=cfg.get('btn_hover_bg', (200, 212, 230, 255)))
        dot_r = int(1.1 * scale)
        sp = int(3.8 * scale)
        dot_col = ((255, 255, 255, 255) if is_dark else (20, 40, 75, 255)) if self._hover_target == 'btn_bar_menu' else cfg['muted']
        for ox in (-sp, 0, sp):
            d.ellipse([mcx + ox - dot_r, bar_cy - dot_r, mcx + ox + dot_r, bar_cy + dot_r], fill=dot_col)

        # 2b. Przycisk Zminimalizuj − (minimalizuje do paska zadań)
        mncx = int(self.bar_min_cx * scale)
        if self._hover_target in ('btn_bar_minimize', 'btn_minimize'):
            d.rounded_rectangle([mncx - int(9*scale), bar_cy - int(9*scale), mncx + int(9*scale), bar_cy + int(9*scale)], radius=int(5*scale), fill=cfg.get('btn_hover_bg', (200, 212, 230, 255)))
        ln_w = int(4.5 * scale)
        min_col = ((255, 255, 255, 255) if is_dark else (20, 40, 75, 255)) if self._hover_target in ('btn_bar_minimize', 'btn_minimize') else cfg['muted']
        d.line([(mncx - ln_w, bar_cy), (mncx + ln_w, bar_cy)], fill=min_col, width=max(1, int(1.3 * scale)))

        # 2c. Przycisk Zamknij ✕ (zamyka / ukrywa aplikację)
        ccx = int(self.bar_close_cx * scale)
        if self._hover_target in ('btn_bar_close', 'btn_close'):
            d.rounded_rectangle([ccx - int(9*scale), bar_cy - int(9*scale), ccx + int(9*scale), bar_cy + int(9*scale)], radius=int(5*scale), fill=cfg.get('btn_close_hover_bg', (250, 210, 215, 255)))
        csz = int(3.5 * scale)
        close_col = (255, 80, 80, 255) if self._hover_target in ('btn_bar_close', 'btn_close') else cfg['muted']
        d.line([(ccx - csz, bar_cy - csz), (ccx + csz, bar_cy + csz)], fill=close_col, width=max(1, int(1.3 * scale)))
        d.line([(ccx - csz, bar_cy + csz), (ccx + csz, bar_cy - csz)], fill=close_col, width=max(1, int(1.3 * scale)))

        # --- WNĘTRZE MODUŁU GŁOSU (.voice-module) ---
        # Uchwyt (Drag Handle) na górze: 29x3 px
        hx = int(self.handle_x * scale)
        hy = int(self.handle_y * scale)
        hw = int(self.handle_w * scale)
        hh = int(self.handle_h * scale)
        d.rounded_rectangle([hx, hy, hx + hw, hy + hh], radius=int(hh/2), fill=cfg['muted'])

        # Koordynaty przycisków
        mic_x = int(self.mic_cx * scale)
        mic_y = int(self.mic_cy * scale)
        b_rad = int(self.mic_rad * scale)

        meet_x = int(self.meet_cx * scale)
        meet_y = int(self.meet_cy * scale)

        # --- PRZYCISK 1: MIKROFON (Lewy) ---
        if self.mode == "recording":
            # Czerwony aktywny przycisk z pulsującym pierścieniem (zamkniętym w karcie)
            p_factor = 0.5 + 0.5 * math.sin(t_now * 5.0)
            glow_rad = int(b_rad + (4 + p_factor * 3.0) * scale)
            glow_m = Image.new('RGBA', (W, H), (0, 0, 0, 0))
            gmd = ImageDraw.Draw(glow_m)
            gmd.ellipse([mic_x - glow_rad, mic_y - glow_rad, mic_x + glow_rad, mic_y + glow_rad], fill=(255, 34, 52, int(35 + p_factor * 20)))
            glow_m = glow_m.filter(ImageFilter.GaussianBlur(radius=int(4*scale)))
            glow_m_masked = Image.new('RGBA', (W, H), (0, 0, 0, 0))
            glow_m_masked.paste(glow_m, (0, 0), mask=card_mask)
            img.alpha_composite(glow_m_masked)
            d = ImageDraw.Draw(img)

            d.ellipse([mic_x - b_rad, mic_y - b_rad, mic_x + b_rad, mic_y + b_rad], fill=(255, 51, 73, 255))
            draw_svg_mic(d, mic_x, mic_y, sz=int(21 * scale), color=(255, 255, 255, 255))

        elif self.mode == "processing":
            # Bursztynowy przycisk finalizacji
            d.ellipse([mic_x - b_rad, mic_y - b_rad, mic_x + b_rad, mic_y + b_rad], fill=(245, 158, 11, 255))
            draw_svg_mic(d, mic_x, mic_y, sz=int(21 * scale), color=(255, 255, 255, 255))

        else:
            # W spoczynku: miękki okrąg z palety bez obramowania
            d.ellipse([mic_x - b_rad, mic_y - b_rad, mic_x + b_rad, mic_y + b_rad], fill=cfg['mic_standby_bg'])
            draw_svg_mic(d, mic_x, mic_y, sz=int(21 * scale), color=cfg.get('mic_standby_color', (223, 232, 251, 255)))

        # --- PRZYCISK 2: SPOTKANIE (Prawy) ---
        if self.mode == "transcribing":
            # Niebieski aktywny przycisk z poświatą (zamkniętą w karcie)
            p_factor = 0.5 + 0.5 * math.sin(t_now * 5.0)
            glow_rad = int(b_rad + (4 + p_factor * 3.0) * scale)
            glow_mt = Image.new('RGBA', (W, H), (0, 0, 0, 0))
            gmd = ImageDraw.Draw(glow_mt)
            gmd.ellipse([meet_x - glow_rad, meet_y - glow_rad, meet_x + glow_rad, meet_y + glow_rad], fill=(46, 94, 255, int(40 + p_factor * 20)))
            glow_mt = glow_mt.filter(ImageFilter.GaussianBlur(radius=int(4*scale)))
            glow_mt_masked = Image.new('RGBA', (W, H), (0, 0, 0, 0))
            glow_mt_masked.paste(glow_mt, (0, 0), mask=card_mask)
            img.alpha_composite(glow_mt_masked)
            d = ImageDraw.Draw(img)

            d.ellipse([meet_x - b_rad, meet_y - b_rad, meet_x + b_rad, meet_y + b_rad], fill=(64, 92, 242, 255))
            draw_people_icon(d, meet_x, meet_y, sz=int(27 * scale), color=(255, 255, 255, 255))

        else:
            d.ellipse([meet_x - b_rad, meet_y - b_rad, meet_x + b_rad, meet_y + b_rad], fill=cfg['meet_standby_bg'])
            draw_people_icon(d, meet_x, meet_y, sz=int(27 * scale), color=cfg.get('meet_standby_color', (255, 255, 255, 230)))

        # --- SEKCJA ŚRODKOWA: FALA DŹWIĘKOWA (dokładnie 80px) ---
        center_cx = mx + mw // 2
        wave_cy = my + int(39.5 * scale)

        num_bars = len(BAR_HEIGHTS)
        bar_w = 1.6 * scale
        bar_gap = 1.4 * scale
        total_wave_w = num_bars * bar_w + (num_bars - 1) * bar_gap
        start_bx = center_cx - total_wave_w / 2.0

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

        bar_color = cfg['danger'] if self.mode == "recording" else (cfg['text'] if self.mode == "transcribing" else cfg['wave'])

        base_h = 4.0 * scale
        max_h = 20.0 * scale
        vol_boost = min(1.0, self._smooth_vol * 1.6)

        for i, h_vals in enumerate(BAR_HEIGHTS):
            bx_cur = start_bx + i * (bar_w + bar_gap)
            if self.mode in ("recording", "transcribing") and vol_boost >= 0.03:
                # Dynamiczne powiększanie i zmniejszanie w zależności od natężenia głosu
                prof_factor = (h_vals[1] - h_vals[0]) / 22.0
                mod = 1.0 + 0.25 * math.sin(t_now * 7.5 + i * 0.72) + 0.15 * math.sin(t_now * 12.0 - i * 0.38)
                dynamic_span = (max_h - base_h) * vol_boost * prof_factor * mod
                eff_h = min(max_h, max(base_h, base_h + dynamic_span))
            else:
                # W spoczynku: profil wysokości kresek fali odpowiadający specyfikacji prototypu
                eff_h = h_vals[0] * 0.75 * scale

            by1 = wave_cy - eff_h / 2.0
            by2 = wave_cy + eff_h / 2.0
            d.rounded_rectangle([bx_cur, by1, bx_cur + bar_w, by2], radius=max(1, int(bar_w/2)), fill=bar_color)

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
        with self._lock:
            self.mode = "recording"
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
        if not self.is_minimized() and self._visible:
            self.show()

    def show_processing(self):
        with self._lock:
            self.mode = "processing"
            self._dirty = True
        if not self.is_minimized() and self._visible:
            self.show()

    def show_meeting_recording(self):
        with self._lock:
            self.mode = "transcribing"
            self._start_time = time.time()
            self.clear_transcript()
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
            user32.SetWindowPos(self.hwnd, -1, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010)

    def hide(self):
        self._visible = False
        self._dirty = True
        if self.hwnd:
            user32.ShowWindow(self.hwnd, 0)

    def minimize(self):
        """Minimalizuje okno do dolnego paska zadań Windows (Taskbar)."""
        self._dirty = True
        if self.hwnd:
            user32.ShowWindow(self.hwnd, 6)  # SW_MINIMIZE

    def restore(self):
        """Przywraca okno z dolnego paska zadań Windows (Taskbar)."""
        self._visible = True
        self._dirty = True
        if self.hwnd:
            user32.ShowWindow(self.hwnd, 9)  # SW_RESTORE
            user32.SetWindowPos(self.hwnd, -1, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010)

    def is_minimized(self) -> bool:
        if self.hwnd:
            return bool(user32.IsIconic(self.hwnd))
        return False

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
