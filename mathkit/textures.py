"""Planet texture quality.

The program ships 2K texture maps (assets/textures, Solar System Scope, CC BY 4.0). Sharper maps (mostly 8K) can be downloaded on request from the same source
into the per-user data folder (``textures/``); nothing is fetched unless the user presses the download button. The 3-D views use a sharper map only for the one
or two bodies that are large on screen, so memory stays low.
"""
from __future__ import annotations
import pathlib
import threading
import urllib.request
from .ui import shell

BASE_URL = 'https://www.solarsystemscope.com/textures/download/'
# bundled 2K file -> the sharper file offered for download (not every body has an 8K map: Venus' atmosphere tops out at 4K)
HIRES = {
    '2k_sun.jpg': '8k_sun.jpg', '2k_mercury.jpg': '8k_mercury.jpg', '2k_venus_surface.jpg': '8k_venus_surface.jpg', '2k_venus_atmosphere.jpg': '4k_venus_atmosphere.jpg',
    '2k_earth_daymap.jpg': '8k_earth_daymap.jpg', '2k_earth_nightmap.jpg': '8k_earth_nightmap.jpg', '2k_earth_clouds.jpg': '8k_earth_clouds.jpg',
    '2k_moon.jpg': '8k_moon.jpg', '2k_mars.jpg': '8k_mars.jpg', '2k_jupiter.jpg': '8k_jupiter.jpg', '2k_saturn.jpg': '8k_saturn.jpg', '2k_ceres_fictional.jpg': '4k_ceres_fictional.jpg',
}
MIN_BYTES = 100_000
PROG = dict(state='idle', done=0, total=len(HIRES), current='', error='', bytes=0)


def folder() -> pathlib.Path:
    return shell.folder('textures')


def present(hi: str) -> bool:
    f = folder() / hi
    return f.is_file() and f.stat().st_size >= MIN_BYTES


def status() -> dict:
    files = [dict(src=s, hi=h, present=present(h)) for s, h in HIRES.items()]
    have = {f['src']: f['hi'] for f in files if f['present']}
    size = sum((folder() / h).stat().st_size for h in have.values())
    return dict(files=files, map=have, count=len(have), total=len(HIRES), size_mb=round(size / 1e6, 1), progress=dict(PROG), folder=str(folder()))


def _is_image(head: bytes) -> bool:
    return head[:3] == b'\xff\xd8\xff' or head[:8] == b'\x89PNG\r\n\x1a\n'


def download() -> dict:
    """Fetch every missing sharper map in a background thread (only when the user asks). Poll ``status()['progress']``."""
    if PROG['state'] == 'running': return dict(ok=True)

    def work():
        todo = [h for h in HIRES.values() if not present(h)]
        PROG.update(state='running', done=len(HIRES) - len(todo), total=len(HIRES), current='', error='', bytes=0)
        try:
            for hi in todo:
                PROG['current'] = hi; dest = folder() / hi; tmp = dest.with_suffix(dest.suffix + '.part')
                req = urllib.request.Request(BASE_URL + hi, headers={'User-Agent': 'OrbSim'})
                with urllib.request.urlopen(req, timeout=60) as r, open(tmp, 'wb') as f:
                    first = True
                    while True:
                        b = r.read(1 << 18)
                        if not b: break
                        if first:
                            if not _is_image(b): raise OSError(f'{hi}: the server did not send an image')
                            first = False
                        f.write(b); PROG['bytes'] += len(b)
                if tmp.stat().st_size < MIN_BYTES: tmp.unlink(); raise OSError(f'{hi}: the download is too small to be a texture')
                tmp.replace(dest); PROG['done'] += 1
            PROG.update(state='done', current='')
        except Exception as ex:
            PROG.update(state='error', error=str(ex))
    threading.Thread(target=work, daemon=True).start(); return dict(ok=True)


def delete_all() -> int:
    n = 0
    for h in HIRES.values():
        f = folder() / h
        try:
            if f.is_file(): f.unlink(); n += 1
        except OSError: pass
    return n
