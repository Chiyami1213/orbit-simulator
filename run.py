"""OrbSim launcher.

    python run.py                 open the app in its own window
    python run.py --browser       open it in the default browser instead
    python run.py --serve-only    just serve on localhost (used for testing); add --port N to choose the port

Everything the program writes locally (settings, screenshots, exports, caches, logs, the WebView2 profile) goes to
%APPDATA%\\OrbSim\\ — never into the program folder.
"""
import logging
import os
import sys
import time
import webbrowser

from mathkit.ui import shell                       # light module: only resolves the data folder

HOME = shell.appdata_dir()
for sub in ('cache', 'logs', 'webview', 'screenshots', 'exports'):
    (HOME / sub).mkdir(parents=True, exist_ok=True)
sys.pycache_prefix = str(HOME / 'cache' / 'pycache')                          # no __pycache__ folders next to the sources
os.environ.setdefault('MPLCONFIGDIR', str(HOME / 'cache' / 'matplotlib'))   # must be set before matplotlib is imported
logging.basicConfig(filename=str(HOME / 'logs' / 'orbsim.log'), level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s', encoding='utf-8')

from mathkit.ui import server                      # noqa: E402  (imports matplotlib, so it must come after the settings above)

TITLE = 'OrbSim'
WEBVIEW2_GUID = '{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}'


def webview2_installed() -> bool:
    """The native window needs the Edge WebView2 runtime (preinstalled on Windows 11). Elsewhere we fall back to the browser."""
    if sys.platform != 'win32':
        return True
    try:
        import winreg
    except ImportError:
        return True
    keys = ((winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients' + '\\' + WEBVIEW2_GUID),
            (winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\Microsoft\EdgeUpdate\Clients' + '\\' + WEBVIEW2_GUID),
            (winreg.HKEY_CURRENT_USER, r'Software\Microsoft\EdgeUpdate\Clients' + '\\' + WEBVIEW2_GUID))
    for hive, sub in keys:
        try:
            with winreg.OpenKey(hive, sub) as k:
                if winreg.QueryValueEx(k, 'pv')[0]:
                    return True
        except OSError:
            continue
    return False


def main(argv):
    port = int(argv[argv.index('--port') + 1]) if '--port' in argv else 0
    httpd, url = server.start(port)
    logging.info('server started at %s', url)
    serve_only = '--serve-only' in argv
    use_window = not serve_only and '--browser' not in argv and webview2_installed()
    if use_window:
        try:
            import webview
        except ImportError:
            use_window = False
    if use_window:
        if sys.platform == 'win32':
            try:                                    # true pixel sizes, so window screenshots are not cropped on scaled displays
                import ctypes
                ctypes.windll.shcore.SetProcessDpiAwareness(2)
            except Exception:
                pass
        try:
            webview.settings['ALLOW_DOWNLOADS'] = True
        except Exception:
            pass
        shell.WINDOW = webview.create_window(TITLE, url, width=1700, height=1020, min_size=(1240, 760), background_color='#0f1628')
        def on_closing():                           # the close button: ask in the page first (unless the preference is off), then quit through api.quit
            import threading
            if shell.QUITTING or not shell.load_settings().get('confirmQuit', True):
                return True
            threading.Thread(target=lambda: shell.WINDOW.evaluate_js('askQuit()'), daemon=True).start()
            return False
        shell.WINDOW.events.closing += on_closing
        webview.start(private_mode=False, storage_path=str(HOME / 'webview'))
    else:
        print(f'{TITLE} running at {url}   (Ctrl+C to quit)', flush=True)
        if not serve_only:
            webbrowser.open(url)
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            pass
    httpd.shutdown()


if __name__ == '__main__':
    main(sys.argv[1:])
