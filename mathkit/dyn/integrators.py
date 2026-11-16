"""Adaptive explicit Runge-Kutta integrators (pure NumPy, no SciPy) with event location.

Methods (coefficients ported from NASA GMAT, see ``_gmat_tables.py``):
  'RungeKutta89'     Verner 8(9), 16 stages   (GMAT default)
  'PrinceDormand78'  Prince-Dormand 7(8), 13 stages
  'PrinceDormand45'  Dormand-Prince 4(5), 7 stages

``propagate`` advances ``y' = f(t, y)`` and stops at the first terminal event or at ``t_end``. Events are located by a bracketed
Illinois root finder on the event function; each trial evaluation re-integrates from the start of the accepted step with a single
Runge-Kutta step, so no interpolant is needed. Located to 1e-9 s by default.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable
import numpy as np
from . import _gmat_tables as G

# name -> (A, B, c, e, p) with p = order of the error estimate (step-size exponent 1/(p+1))
_TABLES = {
    'RungeKutta89': (G.RK89_AI, G.RK89_BIJ, G.RK89_CJ, G.RK89_EE, 8),
    'PrinceDormand78': (G.PD78_AI, G.PD78_BIJ, G.PD78_CJ, G.PD78_EE, 7),
    'PrinceDormand45': (G.PD45_AI, G.PD45_BIJ, G.PD45_CJ, G.PD45_EE, 4),
}
METHODS = tuple(_TABLES)


@dataclass
class Event:
    """An event function g(t, y); an event is a sign change of g in the wanted direction (+1 rising, -1 falling, 0 either)."""
    fn: Callable[[float, np.ndarray], float]
    name: str = ''
    direction: int = 0
    terminal: bool = True
    accept: Callable | None = None        # optional filter (t, y) -> bool, to drop spurious sign changes (e.g. the +-180 deg wrap jump)


@dataclass
class Solution:
    t: np.ndarray
    y: np.ndarray                                       # shape (n_steps+1, n)
    events: list = field(default_factory=list)          # [(t, y, name)]
    status: str = 'done'                                # 'done' | 'event' | 'max_steps' | 'step_too_small'
    n_steps: int = 0
    n_evals: int = 0


class Stepper:
    def __init__(self, f, method: str = 'RungeKutta89'):
        A, B, c, e, p = _TABLES[method]
        self.f = f; self.a = np.array(A); self.B = np.array(B); self.c = np.array(c); self.e = np.array(e); self.p = p; self.s = len(c)
        self.n_evals = 0

    def step(self, t: float, y: np.ndarray, h: float):
        """One step of size h; returns (y_new, error_vector)."""
        k = np.empty((self.s, y.size))
        for i in range(self.s):
            yi = y + h * (self.B[i, :i] @ k[:i]) if i else y
            k[i] = self.f(t + self.a[i] * h, yi)
        self.n_evals += self.s
        return y + h * (self.c @ k), h * (self.e @ k)


def _illinois(g, a, b, ga, gb, tol=1e-9, maxit=80):
    """Illinois (modified regula falsi) on [a, b] with g(a)*g(b) < 0; returns t where |b - a| < tol (or g == 0)."""
    side = 0
    for _ in range(maxit):
        c = (a * gb - b * ga) / (gb - ga) if gb != ga else 0.5 * (a + b)
        if not (min(a, b) <= c <= max(a, b)): c = 0.5 * (a + b)
        gc = g(c)
        if gc == 0 or abs(b - a) < tol: return c
        if gc * gb > 0:
            b, gb = c, gc
            if side == -1: ga *= 0.5
            side = -1
        else:
            a, ga = c, gc
            if side == 1: gb *= 0.5
            side = 1
        if abs(b - a) < tol: return 0.5 * (a + b)
    return 0.5 * (a + b)


def propagate(f, y0, t0: float, t_end: float, *, method: str = 'RungeKutta89', accuracy: float = 1e-12, h0: float = 60.0,
              h_min: float = 1e-3, h_max: float = 86400.0, events: list[Event] | None = None, max_steps: int = 2_000_000,
              record: bool = True, event_tol: float = 1e-9, fixed_step: float | None = None, dense: int = 1, min_points: int = 0) -> Solution:
    """Integrate from t0 toward t_end (either direction). ``accuracy`` is the relative error tolerance per step."""
    y = np.asarray(y0, float).copy(); t = float(t0); sgn = 1.0 if t_end >= t0 else -1.0
    S = Stepper(f, method); events = events or []; T = [t]; Y = [y.copy()]; found = []
    atol = accuracy * 1e-3; h = sgn * min(abs(h0), h_max) if fixed_step is None else sgn * abs(fixed_step); gprev = [ev.fn(t, y) for ev in events]
    status = 'done'; n = 0
    while sgn * (t_end - t) > 1e-12 * max(1.0, abs(t_end)) and n < max_steps:
        h = sgn * min(abs(h), abs(t_end - t))
        ynew, err = S.step(t, y, h)
        if fixed_step is None:
            mag = np.maximum(np.abs(y), np.abs(ynew))
            if y.size == 6:                                           # scale each 3-vector by its norm, like GMAT: a component near zero must not force tiny steps
                mag = np.maximum(mag, np.repeat([np.linalg.norm(ynew[:3]), np.linalg.norm(ynew[3:])], 3))
            sc = atol + accuracy * mag; en = float(np.max(np.abs(err) / sc))
            if not np.isfinite(en): status = 'step_too_small'; break
            if en > 1.0:                                                    # reject, shrink
                hn = h * max(0.2, 0.9 * en ** (-1.0 / (S.p + 1)))
                if abs(hn) < h_min: status = 'step_too_small'; break
                h = hn; continue
            fac = min(5.0, 0.9 * en ** (-1.0 / (S.p + 1))) if en > 0 else 5.0
        else:
            fac = 1.0
        tnew = t + h; stop = False; t0_s, y_s = t, y
        if events:
            gnew = [ev.fn(tnew, ynew) for ev in events]; hit = None
            for i, ev in enumerate(events):
                a, b = gprev[i], gnew[i]
                crossed = (a < 0 <= b) if ev.direction > 0 else (a > 0 >= b) if ev.direction < 0 else (a * b < 0 or (b == 0 and a != 0))
                if crossed:
                    t_ev = _illinois(lambda tt, i=i: events[i].fn(tt, S.step(t, y, tt - t)[0]), t, tnew, a, b, tol=event_tol)
                    if ev.accept is not None and not ev.accept(t_ev, S.step(t, y, t_ev - t)[0]): continue
                    if hit is None or sgn * (t_ev - hit[0]) < 0: hit = (t_ev, i)
            if hit is not None:
                t_ev, i = hit; y_ev = S.step(t, y, t_ev - t)[0]
                found.append((t_ev, y_ev, events[i].name))
                if events[i].terminal: t, y = t_ev, y_ev; status = 'event'; stop = True
            gprev = gnew
        if stop:
            T.append(t); Y.append(y.copy()); n += 1; break
        t, y = tnew, ynew; n += 1
        if record: T.append(t); Y.append(y.copy())
        if fixed_step is None: h = h * fac if abs(h * fac) >= h_min else sgn * h_min
        h = sgn * min(abs(h), h_max)
    else:
        if n >= max_steps: status = 'max_steps'
    if not record: T = [t0, t]; Y = [np.asarray(y0, float), y.copy()]
    n_int = len(T) - 1
    k = max(dense, -(-min_points // n_int) if (min_points and n_int) else 1)                # sub-samples per accepted step, only when the run is coarse
    if record and k > 1 and n_int:
        T2, Y2 = [T[0]], [Y[0]]
        for i in range(n_int):
            h_i = T[i + 1] - T[i]
            for j in range(1, k): T2.append(T[i] + h_i * j / k); Y2.append(S.step(T[i], Y[i], h_i * j / k)[0])
            T2.append(T[i + 1]); Y2.append(Y[i + 1])
        T, Y = T2, Y2
    S_n = S.n_evals
    return Solution(np.array(T), np.array(Y), found, status, n, S_n)
