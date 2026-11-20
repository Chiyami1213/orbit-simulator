"""Desktop-shell helpers and local storage.

Rule: clean program files live in the repository (and are pushed); everything the program writes on a user's machine goes to the per-user
application-data folder and is never committed (Windows ``%APPDATA%\\OrbSim``, macOS ``~/Library/Application Support/OrbSim``,
Linux ``~/.local/share/OrbSim``):

    settings.json   user settings            screenshots\\   F2 window captures      exports\\   saved figures (png/pdf/html)
    cache\\          matplotlib / bytecode    webview\\       WebView2 profile        logs\\      error log

Set ``ORBSIM_HOME`` to relocate everything (the test-suite points it at a temporary folder).
"""
from __future__ import annotations
import datetime
import json
import os
import pathlib
import sys

APP_NAME = 'OrbSim'
LEGACY_NAME = 'Orbit Simulator'                                   # the folder used before the program was renamed; it is moved to APP_NAME on first start
QUITTING = False       # set when the user confirmed quitting, so the window's close handler lets the window go
WINDOW = None            # the pywebview window, set by run.py when the app runs in its own window
_FULLSCREEN = False


def appdata_dir() -> pathlib.Path:
    override = os.environ.get('ORBSIM_HOME') or os.environ.get('ORBIT_SIMULATOR_HOME')
    if override: return pathlib.Path(override)
    if sys.platform == 'darwin': base = pathlib.Path.home() / 'Library' / 'Application Support'
    elif sys.platform == 'win32': base = pathlib.Path(os.environ.get('APPDATA') or pathlib.Path.home() / 'AppData' / 'Roaming')
    else: base = pathlib.Path(os.environ.get('XDG_DATA_HOME') or pathlib.Path.home() / '.local' / 'share')
    new, old = base / APP_NAME, base / LEGACY_NAME
    if not new.exists() and old.exists():
        try: old.rename(new)
        except OSError: return old                                    # in use by another process: keep working in the old folder, try again next start
    return new


def folder(name: str) -> pathlib.Path:
    p = appdata_dir() / name; p.mkdir(parents=True, exist_ok=True); return p


def paths() -> dict:
    return dict(root=str(appdata_dir()), screenshots=str(appdata_dir() / 'screenshots'), exports=str(appdata_dir() / 'exports'), designs=str(appdata_dir() / 'designs'), settings=str(appdata_dir() / 'settings.json'),
                logs=str(appdata_dir() / 'logs'))


def has_window() -> bool:
    return WINDOW is not None


# ---------------------------------------------------------------- settings
def load_settings() -> dict:
    f = appdata_dir() / 'settings.json'
    try: return json.loads(f.read_text(encoding='utf-8'))
    except (OSError, ValueError): return {}


def save_settings(data: dict) -> None:
    f = appdata_dir() / 'settings.json'; f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix('.tmp'); tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding='utf-8'); os.replace(tmp, f)     # atomic


def unique_path(directory: pathlib.Path, stem: str, ext: str) -> pathlib.Path:
    p = directory / f'{stem}.{ext}'; n = 2
    while p.exists(): p = directory / f'{stem} ({n}).{ext}'; n += 1
    return p


# ---------------------------------------------------------------- screenshots (Windows: capture only our own window)
def _win32():
    import ctypes
    from ctypes import wintypes as wt
    u, g = ctypes.windll.user32, ctypes.windll.gdi32
    u.GetWindowDC.argtypes = [wt.HWND]; u.GetWindowDC.restype = wt.HDC
    u.ReleaseDC.argtypes = [wt.HWND, wt.HDC]
    u.GetWindowRect.argtypes = [wt.HWND, ctypes.POINTER(wt.RECT)]
    u.PrintWindow.argtypes = [wt.HWND, wt.HDC, wt.UINT]
    u.IsWindowVisible.argtypes = [wt.HWND]
    u.GetWindowTextW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
    u.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
    g.CreateCompatibleDC.argtypes = [wt.HDC]; g.CreateCompatibleDC.restype = wt.HDC
    g.CreateCompatibleBitmap.argtypes = [wt.HDC, ctypes.c_int, ctypes.c_int]; g.CreateCompatibleBitmap.restype = wt.HBITMAP
    g.SelectObject.argtypes = [wt.HDC, wt.HGDIOBJ]; g.SelectObject.restype = wt.HGDIOBJ
    g.DeleteObject.argtypes = [wt.HGDIOBJ]; g.DeleteDC.argtypes = [wt.HDC]
    return ctypes, wt, u, g


def _find_hwnd(title: str):
    ctypes, wt, u, _ = _win32(); found = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def cb(h, _l):
        pid = wt.DWORD(); u.GetWindowThreadProcessId(h, ctypes.byref(pid))
        if pid.value == os.getpid() and u.IsWindowVisible(h):
            buf = ctypes.create_unicode_buffer(256); u.GetWindowTextW(h, buf, 256)
            if buf.value.startswith(title): found.append(h)
        return True
    u.EnumWindows(cb, 0)
    return found[0] if found else None


def _grab(hwnd):
    ctypes, wt, u, g = _win32(); from PIL import Image
    rect = wt.RECT(); u.GetWindowRect(hwnd, ctypes.byref(rect)); w, h = rect.right - rect.left, rect.bottom - rect.top
    hdc = u.GetWindowDC(hwnd); mdc = g.CreateCompatibleDC(hdc); bmp = g.CreateCompatibleBitmap(hdc, w, h); old = g.SelectObject(mdc, bmp)
    u.PrintWindow(hwnd, mdc, 2)                                       # 2 = PW_RENDERFULLCONTENT (captures GPU-composited web content)

    class BIH(ctypes.Structure):
        _fields_ = [('biSize', wt.DWORD), ('biWidth', wt.LONG), ('biHeight', wt.LONG), ('biPlanes', wt.WORD), ('biBitCount', wt.WORD), ('biCompression', wt.DWORD),
                    ('biSizeImage', wt.DWORD), ('biXPelsPerMeter', wt.LONG), ('biYPelsPerMeter', wt.LONG), ('biClrUsed', wt.DWORD), ('biClrImportant', wt.DWORD)]
    bi = BIH(); bi.biSize = ctypes.sizeof(BIH); bi.biWidth = w; bi.biHeight = -h; bi.biPlanes = 1; bi.biBitCount = 32
    buf = (ctypes.c_ubyte * (w * h * 4))()
    ctypes.windll.gdi32.GetDIBits(mdc, bmp, 0, h, buf, ctypes.byref(bi), 0)
    g.SelectObject(mdc, old); g.DeleteObject(bmp); g.DeleteDC(mdc); u.ReleaseDC(hwnd, hdc)
    return Image.frombuffer('RGBA', (w, h), bytes(buf), 'raw', 'BGRA', 0, 1).convert('RGB'), (rect.left, rect.top, rect.right, rect.bottom)


def _capture_mac() -> pathlib.Path:
    """macOS: capture only our own window with the system ``screencapture`` tool (needs Screen Recording permission the first time)."""
    import subprocess
    from webview.platforms.cocoa import BrowserView
    number = BrowserView.instances[WINDOW.uid].window.windowNumber()
    out = unique_path(folder('screenshots'), 'OrbSim ' + datetime.datetime.now().strftime('%Y-%m-%d %H-%M-%S'), 'png')
    subprocess.run(['screencapture', '-x', '-o', f'-l{number}', str(out)], check=True)
    if not out.exists() or out.stat().st_size == 0: raise RuntimeError('screencapture produced no image (allow Screen Recording for OrbSim in System Settings)')
    return out


def capture_window() -> pathlib.Path:
    """Save a PNG of the application window to the screenshots folder and return its path."""
    if WINDOW is None: raise RuntimeError('screenshots capture the application window; start the app without --browser')
    if sys.platform == 'darwin': return _capture_mac()
    if sys.platform != 'win32': raise RuntimeError('window screenshots are available on Windows and macOS')
    hwnd = _find_hwnd(WINDOW.title if hasattr(WINDOW, 'title') else APP_NAME)
    if not hwnd: raise RuntimeError('the application window was not found')
    img, box = _grab(hwnd)
    if img.getextrema() == ((0, 0), (0, 0), (0, 0)):                  # nothing rendered: fall back to a region grab of our own window
        from PIL import ImageGrab; img = ImageGrab.grab(bbox=box, all_screens=True)
    out = unique_path(folder('screenshots'), 'OrbSim ' + datetime.datetime.now().strftime('%Y-%m-%d %H-%M-%S'), 'png')
    img.save(out); return out


# ---------------------------------------------------------------- window / folders
def toggle_fullscreen() -> dict:
    """F11: real full screen when running in the native window; the page falls back to the browser Fullscreen API otherwise."""
    global _FULLSCREEN
    if WINDOW is None: return dict(mode='browser')
    WINDOW.toggle_fullscreen(); _FULLSCREEN = not _FULLSCREEN
    return dict(mode='window', fullscreen=_FULLSCREEN)


def open_folder(which: str) -> str:
    target = folder({'screenshots': 'screenshots', 'exports': 'exports', 'designs': 'designs', 'logs': 'logs', 'backups': 'backups'}.get(which, '.')) if which != 'root' else appdata_dir()
    target.mkdir(parents=True, exist_ok=True)
    if sys.platform == 'win32': os.startfile(str(target))              # noqa: S606 (opening a folder we created)
    else:
        import subprocess
        subprocess.run(['open' if sys.platform == 'darwin' else 'xdg-open', str(target)], check=False)
    return str(target)
