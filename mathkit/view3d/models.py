"""Procedural 3-D bodies for the plots: textured spheres (real planet maps) and two spacecraft models.

Everything is plain Plotly Mesh3d geometry with per-vertex colours, so it works offline and needs no WebGL texture support.
Spacecraft models are built in a local frame (+x forward, +y right, +z up) with a length of about 1; the animation page scales and
orients them along the velocity vector every frame.
"""
from __future__ import annotations
import functools
import pathlib
import sys
import numpy as np

TEXTURES = {'Sun': '2k_sun.jpg', 'Moon': '2k_moon.jpg', 'Mercury': '2k_mercury.jpg', 'Venus': '2k_venus_surface.jpg', 'Earth': '2k_earth_daymap.jpg',
            'Mars': '2k_mars.jpg', 'Jupiter': '2k_jupiter.jpg', 'Saturn': '2k_saturn.jpg', 'Uranus': '2k_uranus.jpg', 'Neptune': '2k_neptune.jpg'}
CREDIT = 'Planet textures: Solar System Scope (2k maps), CC BY 4.0 — https://www.solarsystemscope.com/textures/ (license to be confirmed by the project owner).'


def assets_dir() -> pathlib.Path:
    base = pathlib.Path(getattr(sys, '_MEIPASS', pathlib.Path(__file__).resolve().parents[2])) if getattr(sys, 'frozen', False) else pathlib.Path(__file__).resolve().parents[2]
    return base / 'mathkit' / 'assets' / 'textures'


def has_texture(body: str) -> bool:
    return body in TEXTURES and (assets_dir() / TEXTURES[body]).exists()


@functools.lru_cache(maxsize=16)
def _image(name: str) -> np.ndarray:
    from PIL import Image
    return np.asarray(Image.open(assets_dir() / name).convert('RGB').resize((1024, 512)), dtype=float)


@functools.lru_cache(maxsize=32)
def sphere_mesh(body: str, nlon: int = 112, nlat: int = 56):
    """Unit-sphere vertices (x, y, z), triangle indices (i, j, k) and per-vertex colours sampled from the body's texture map."""
    img = _image(TEXTURES[body]); H, W, _ = img.shape
    lon = np.linspace(0, 2 * np.pi, nlon, endpoint=True); lat = np.linspace(np.pi / 2, -np.pi / 2, nlat)
    LON, LAT = np.meshgrid(lon, lat)
    x = np.cos(LAT) * np.cos(LON); y = np.cos(LAT) * np.sin(LON); z = np.sin(LAT)
    px = (LON / (2 * np.pi) * (W - 1)); py = ((np.pi / 2 - LAT) / np.pi * (H - 1))
    x0 = np.clip(px.astype(int), 0, W - 2); y0 = np.clip(py.astype(int), 0, H - 2); fx = (px - x0)[..., None]; fy = (py - y0)[..., None]
    c = (img[y0, x0] * (1 - fx) * (1 - fy) + img[y0, x0 + 1] * fx * (1 - fy) + img[y0 + 1, x0] * (1 - fx) * fy + img[y0 + 1, x0 + 1] * fx * fy)
    idx = np.arange(nlat * nlon).reshape(nlat, nlon); a = idx[:-1, :-1].ravel(); b = idx[:-1, 1:].ravel(); cc = idx[1:, :-1].ravel(); d = idx[1:, 1:].ravel()
    colors = ['rgb(%d,%d,%d)' % tuple(v) for v in c.reshape(-1, 3)]
    return x.ravel(), y.ravel(), z.ravel(), np.r_[a, b], np.r_[b, d], np.r_[cc, cc], colors


def _box(cx, cy, cz, sx, sy, sz):
    v = np.array([[x, y, z] for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)], float) * [sx / 2, sy / 2, sz / 2] + [cx, cy, cz]
    f = np.array([[0, 1, 3], [0, 3, 2], [4, 6, 7], [4, 7, 5], [0, 4, 5], [0, 5, 1], [2, 3, 7], [2, 7, 6], [0, 2, 6], [0, 6, 4], [1, 5, 7], [1, 7, 3]])
    return v, f


def _cone(cx, cy, cz, r, h, n=14):
    """Dish: a shallow cone opening toward +x (apex at the back)."""
    t = np.linspace(0, 2 * np.pi, n, endpoint=False); ring = np.c_[np.full(n, cx + h), cy + r * np.cos(t), cz + r * np.sin(t)]
    v = np.vstack([[cx, cy, cz], ring, [cx + h, cy, cz]]); f = [[0, 1 + k, 1 + (k + 1) % n] for k in range(n)] + [[n + 1, 1 + (k + 1) % n, 1 + k] for k in range(n)]
    return v, np.array(f)


def _assemble(parts):
    V, F, C, off = [], [], [], 0
    for (v, f), col in parts:
        V.append(v); F.append(f + off); C += [col] * len(v); off += len(v)
    V = np.vstack(V); F = np.vstack(F)
    return dict(x=V[:, 0].tolist(), y=V[:, 1].tolist(), z=V[:, 2].tolist(), i=F[:, 0].tolist(), j=F[:, 1].tolist(), k=F[:, 2].tolist(), colors=C)


MODELS = {
    'comsat': 'Communications Satellite',
    'probe': 'Deep-Space Probe',
}


def spacecraft_mesh(kind: str) -> dict:
    """Local-frame mesh (+x forward, +y right, +z up). 'comsat': gold bus + two long solar wings + dish. 'probe': slim bus, big dish, boom and RTG."""
    gold, panel, grey, white = '#d9b13a', '#1c3f94', '#b9c0cc', '#eceff4'
    if kind == 'probe':
        return _assemble([(_box(0, 0, 0, 0.5, 0.28, 0.28), gold), (_cone(0.25, 0, 0, 0.34, 0.2), white), (_box(-0.42, 0, 0, 0.5, 0.05, 0.05), grey),
                          (_box(-0.62, 0, 0, 0.18, 0.12, 0.12), '#5a5f6b'), (_box(0.05, 0, 0.2, 0.05, 0.05, 0.28), grey)])
    return _assemble([(_box(0, 0, 0, 0.55, 0.42, 0.42), gold), (_box(0, 0.62, 0, 0.36, 0.7, 0.03), panel), (_box(0, -0.62, 0, 0.36, 0.7, 0.03), panel),
                      (_box(0, 0.27, 0, 0.08, 0.14, 0.06), grey), (_box(0, -0.27, 0, 0.08, 0.14, 0.06), grey), (_cone(0.28, 0, 0.0, 0.2, 0.14), white), (_box(-0.3, 0, 0, 0.1, 0.1, 0.1), grey)])
