# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from PyInstaller.utils.hooks import collect_all

block_cipher = None

datas = [
    ('icon.ico', '.'),
    ('config.json', '.'),
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
site_pkgs = os.path.abspath(os.path.join(os.path.dirname(sys.executable), '..', 'Lib', 'site-packages'))
pyd_path = os.path.join(site_pkgs, '_portaudiowpatch.cp310-win_amd64.pyd')
if os.path.exists(pyd_path):
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
