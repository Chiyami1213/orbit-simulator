"""Tiny local HTTP server: static web UI + JSON API + figure exports. Bound to 127.0.0.1 only."""
from __future__ import annotations
import json
import logging
import mimetypes
import pathlib
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs, unquote
from . import api

log = logging.getLogger('orbit-simulator')


def base_dir() -> pathlib.Path:
    if getattr(sys, 'frozen', False): return pathlib.Path(getattr(sys, '_MEIPASS', pathlib.Path(sys.executable).parent))
    return pathlib.Path(__file__).resolve().parents[2]


def web_dir() -> pathlib.Path: return base_dir() / 'mathkit' / 'ui' / 'web'


def plotly_js() -> pathlib.Path | None:
    cand = [web_dir() / 'vendor' / 'plotly.min.js']
    try:
        import plotly; cand.append(pathlib.Path(plotly.__file__).parent / 'package_data' / 'plotly.min.js')
    except Exception:
        pass
    return next((c for c in cand if c.exists()), None)


class Handler(BaseHTTPRequestHandler):
    server_version = 'MathKit'

    def log_message(self, *a): pass          # quiet

    def _send(self, code, body: bytes, ctype='application/json', extra=None):
        self.send_response(code); self.send_header('Content-Type', ctype); self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        for k, v in (extra or {}).items(): self.send_header(k, v)
        self.end_headers(); self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path); path = unquote(u.path)
        try:
            if path == '/static/plotly.min.js':
                f = plotly_js()
                if f is None: return self._send(404, b'plotly.js not found', 'text/plain')
                return self._send(200, f.read_bytes(), 'application/javascript')
            if path.startswith('/export/'):
                stem, _, fmt = path[len('/export/'):].rpartition('.'); q = parse_qs(u.query)
                data, mime, name = api.export(int(stem), fmt, q.get('theme', ['light'])[0])
                return self._send(200, data, mime, {'Content-Disposition': f'attachment; filename="{name}"'})
            if path.startswith('/backup/'):
                from . import backup
                f = (backup.backups_dir() / pathlib.PurePosixPath(path[len('/backup/'):]).name).resolve()
                if f.parent != backup.backups_dir().resolve() or f.suffix != '.zip' or not f.is_file(): return self._send(404, b'not found', 'text/plain')
                return self._send(200, f.read_bytes(), 'application/zip', {'Content-Disposition': f'attachment; filename="{f.name}"'})
            if path.startswith('/assets/textures/'):                                  # sky maps and planet textures for the three.js view (images only)
                f = (base_dir() / 'assets' / 'textures' / pathlib.PurePosixPath(path[len('/assets/textures/'):]).name).resolve()
                if f.suffix.lower() not in ('.jpg', '.png') or not f.is_file(): return self._send(404, b'not found', 'text/plain')
                return self._send(200, f.read_bytes(), mimetypes.guess_type(str(f))[0] or 'image/jpeg')
            if path in ('', '/'): path = '/index.html'
            f = (web_dir() / path.lstrip('/')).resolve()
            if web_dir().resolve() not in f.parents or not f.is_file(): return self._send(404, b'not found', 'text/plain')
            return self._send(200, f.read_bytes(), mimetypes.guess_type(str(f))[0] or 'application/octet-stream')
        except Exception as ex:
            log.exception('GET %s failed', self.path)
            return self._send(500, json.dumps(dict(error=str(ex))).encode())

    def do_POST(self):
        name = urlparse(self.path).path.rsplit('/', 1)[-1]
        try:
            n = int(self.headers.get('Content-Length') or 0); payload = json.loads(self.rfile.read(n) or b'{}')
            out = api.ROUTES[name](payload)
            return self._send(200, json.dumps(api._jsonable(out), allow_nan=False, default=str).encode())
        except KeyError:
            return self._send(404, json.dumps(dict(error='unknown endpoint')).encode())
        except Exception as ex:
            import traceback
            log.exception('POST %s failed', self.path)
            return self._send(500, json.dumps(dict(error=str(ex), trace=traceback.format_exc())).encode())


def start(port: int = 0) -> tuple[ThreadingHTTPServer, str]:
    httpd = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f'http://127.0.0.1:{httpd.server_address[1]}/'
