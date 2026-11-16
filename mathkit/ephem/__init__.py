"""Ephemeris providers. ``get_provider()`` picks DE440s (through jplephem) when a kernel file is available, else the built-in analytic model.

Frame everywhere: ICRF axes (equatorial J2000), km and km/s. ``center`` is 'SSB', 'Sun' or a body name.
"""
from __future__ import annotations
import os
import pathlib
from .approx import AnalyticEphemeris

DE440S_URL = 'https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/planets/de440s.bsp'
DE440S_SIZE = 32726016                  # bytes, as served by NAIF when this was written

_cache: dict = {}


def kernel_dir() -> pathlib.Path:
    from ..ui import shell
    return shell.folder('kernels')


def find_kernel(custom: str | None = None) -> pathlib.Path | None:
    for c in (custom, os.environ.get('ORBIT_DE440S'), str(kernel_dir() / 'de440s.bsp')):
        if c and pathlib.Path(c).is_file(): return pathlib.Path(c)
    return None


def get_provider(custom: str | None = None, prefer: str = 'auto'):
    """prefer: 'auto' (DE440s if present), 'analytic' (force the built-in model)."""
    if prefer != 'analytic':
        k = find_kernel(custom)
        if k is not None:
            key = str(k)
            if key not in _cache:
                try:
                    from .spk import SPKEphemeris
                    _cache[key] = SPKEphemeris(key)
                except Exception:                                  # jplephem missing or kernel unreadable: fall back
                    _cache[key] = None
            if _cache[key] is not None: return _cache[key]
    if 'analytic' not in _cache: _cache['analytic'] = AnalyticEphemeris()
    return _cache['analytic']
