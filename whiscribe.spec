# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from PyInstaller.utils.hooks import collect_all

block_cipher = None

datas = [
    ('icon.ico', '.'),
    ('config.example.json', '.'),
]
binaries = []
hiddenimports = [
    '_portaudiowpatch',
    'sounddevice',
    '_sounddevice',
    'pystray._win32',
    'pynput.keyboard._win32',
    'pynput.mouse._win32',
    'tkinter',
    'tkinter.ttk',
    'tkinter.messagebox',
    'scipy.signal',
    'onnxruntime',
    'huggingface_hub',
    'tokenizers',
    'ctranslate2',
    'faster_whisper',
    'uiautomation',
    'hardware_profiler',
    'meeting_manager',
    'meeting_recorder',
    'diarizer',
    'notepad_manager',
    'focus_detector',
    'injector',
    'overlay',
    'recorder',
    'transcriber',
    'config',
    'logging_setup',
    'paste_memory',
    'win32_desktop',
    'pyperclip',
    'httpx',
    'httpcore',
]

packages_to_collect = [
    'ctranslate2',
    'faster_whisper',
    '_sounddevice_data',
    'pyaudiowpatch',
    'pystray',
    'onnxruntime',
    'tokenizers',
    'huggingface_hub',
    'uiautomation',
]

for pkg in packages_to_collect:
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception as e:
        print(f"Warning collecting {pkg}: {e}")

# Explicitly ensure _portaudiowpatch pyd is added
import glob
site_pkgs = os.path.abspath(os.path.join(os.path.dirname(sys.executable), '..', 'Lib', 'site-packages'))
for pyd_path in glob.glob(os.path.join(site_pkgs, '_portaudiowpatch*.pyd')):
    binaries.append((pyd_path, '.'))

a = Analysis(
    ['app.py'],
    pathex=['.'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'notebook', 'scipy.spatial.cKDTree'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Whiscribe',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='Whiscribe-Portable',
)

import shutil
out_dir = os.path.join('dist', 'Whiscribe-Portable')
try:
    if os.path.exists('icon.ico'):
        shutil.copy('icon.ico', out_dir)
except Exception as e:
    print(f"Warning copying root assets: {e}")

# Bezpiecznik w buildzie — przerwij budowanie, jeśli w paczce znalazł się klucz API
import json, glob, sys
for p in glob.glob(os.path.join('dist', 'Whiscribe-Portable', '**', 'config*.json'), recursive=True):
    if 'models' in p:            # pomiń config.json modelu Whisper
        continue
    try:
        cfg = json.load(open(p, encoding='utf-8'))
        # Oba pola: od 2.2.24 zapasowy silnik ma wlasny klucz i tak samo nie ma prawa
        # pojechac w paczce portable
        for pole in ('llm_api_key', 'llm_fallback_api_key'):
            if cfg.get(pole):
                sys.exit(f'BUILD ABORTED: klucz API ({pole}) w {p}')
    except (json.JSONDecodeError, OSError):
        pass

