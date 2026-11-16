"""Shared helpers for the module solvers."""
from __future__ import annotations
import numpy as np
from ..core.constants import D2R, R2D, wrap360, wrap180
from ..core.kepler import time_since_periapsis, propagate
from ..core.conic import gamma_of
from ..scene import Orbit, Track, Rz, unit


def planar_Q(omega_deg: float = 0.0) -> np.ndarray:
    """Columns e_hat, p_hat, h_hat for a planar orbit whose periapsis is rotated omega from +x."""
    return Rz(omega_deg)


def vel_scale(ref_len_km: float, vmag: float, frac: float = 0.22) -> float:
    """Display scale so that a velocity vector of magnitude vmag is drawn frac*ref_len_km long."""
    return frac * ref_len_km / vmag if vmag > 0 else 1.0


def quadrant_note(name: str, ang_deg: float, sign_test: str) -> str:
    return f'{name} = {ang_deg:.4f}° (atan2; {sign_test})'


def orbit_track(mu: float, o: Orbit, ths_start: float, ths_end: float | None = None, name: str = 'spacecraft',
                role: str = 'orbit'):
    """Animation track for ``o`` starting at true anomaly ths_start (deg). Frames are uniform in *time* because
    positions come from Kepler's equation (core.propagate). Returns (Track, duration_s)."""
    e = o.e; a = o.p / (1 - e * e)
    if e < 1:
        T = 2 * np.pi * np.sqrt(a ** 3 / mu); dur = T
    else:
        t0 = time_since_periapsis(mu, a, e, ths_start)
        t1 = time_since_periapsis(mu, a, e, ths_end if ths_end is not None else -ths_start)
        dur = abs(t1 - t0)

    def th_at(t):
        return propagate(mu, a, e, ths_start, t)

    def fn(t):
        return o.pos(th_at(t))

    def state(t):
        th = th_at(t); r = float(o.r(th)); v = float(np.sqrt(mu * (2 / r - 1 / a)))
        return dict(t=t, r=r, v=v, gamma=float(gamma_of(e, th)), ths=float(wrap360(th)))

    return Track(name, fn, role, state), dur


def clean360(x: float, tol: float = 1e-7) -> float:
    """Wrap to [0, 360) and snap float residue (359.99999999 -> 0) so displayed angles and arcs are sane."""
    x = x % 360
    return 0.0 if (x > 360 - tol or x < tol) else x


def pe_from_spec(spec: dict) -> tuple[float, float]:
    """(p, e) from a conic spec: {rp, ra} | {a, e} | {p, e} | {rp, e} | {ra, e} | {r} (circular)."""
    k = set(spec)
    if k == {'r'}: return spec['r'], 0.0
    if k == {'rp', 'ra'}:
        rp, ra = spec['rp'], spec['ra']; return 2 * rp * ra / (rp + ra), (ra - rp) / (ra + rp)
    if k == {'a', 'e'}: return spec['a'] * (1 - spec['e'] ** 2), spec['e']
    if k == {'p', 'e'}: return spec['p'], spec['e']
    if k == {'rp', 'e'}: return spec['rp'] * (1 + spec['e']), spec['e']
    if k == {'ra', 'e'}: return spec['ra'] * (1 - spec['e']), spec['e']
    raise ValueError(f'unsupported conic spec keys: {sorted(k)}')


def kind_of(e: float, tol: float = 1e-9) -> str:
    return 'circle' if e < tol else 'ellipse' if e < 1 - tol else 'parabola' if abs(e - 1) <= tol else 'hyperbola'


__all__ = ['pe_from_spec', 'clean360', 'planar_Q', 'vel_scale', 'quadrant_note', 'orbit_track', 'kind_of', 'np', 'D2R', 'R2D', 'wrap360', 'wrap180',
           'unit']
