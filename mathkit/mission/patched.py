"""Patched-conic propagation (dynamics model 3): one attracting body at a time, exact Kepler arcs, hand-offs on the spheres of influence.

Hierarchy: the Sun attracts everything outside the planets' spheres; each planet's sphere has r_SOI = a (m/M)^(2/5) about the Sun, and the
Moon's has the same form about the Earth. The crossing epochs are found with a bracketed Illinois root finder on the analytic arc; at a hand-off
the state is re-centred with the ephemeris, so the trajectory is continuous in the propagator's central-body frame (to rounding).
Everything is returned relative to ``frame_body`` (the propagator's central body) in ICRF axes.
"""
from __future__ import annotations
import numpy as np
from ..core import timeutil as TU
from ..core.constants import BODIES, ConstantSet
from ..dyn.integrators import _illinois
from ..dyn.models import kepler_propagate, soi_radius

PARENT = {'Moon': 'Earth', 'Mercury': 'Sun', 'Venus': 'Sun', 'Earth': 'Sun', 'Mars': 'Sun', 'Jupiter': 'Sun', 'Saturn': 'Sun', 'Uranus': 'Sun', 'Neptune': 'Sun', 'Pluto': 'Sun'}
CHILDREN = {'Sun': ['Mercury', 'Venus', 'Earth', 'Mars', 'Jupiter', 'Saturn', 'Uranus', 'Neptune', 'Pluto'], 'Earth': ['Moon']}


def soi(body: str, consts: ConstantSet, eph=None, jd_tdb: float | None = None) -> float:
    """Sphere-of-influence radius (km) of ``body`` about its parent, using the instantaneous distance when an ephemeris time is given."""
    if body not in PARENT: return np.inf
    par = PARENT[body]
    a = BODIES[body].get('a') or 1.0
    if eph is not None and jd_tdb is not None: a = float(np.linalg.norm(eph.state(body, jd_tdb, par)[0]))
    return soi_radius(a, consts.mu(body), consts.mu(par))


class Arc:
    __slots__ = ('t0', 'center', 'r', 'v')

    def __init__(self, t0, center, r, v): self.t0, self.center, self.r, self.v = t0, center, np.asarray(r, float), np.asarray(v, float)


class PatchedPath:
    """Piecewise-Kepler path. ``state(t)`` returns the 6-vector about ``frame_body`` at t seconds after the start epoch."""

    def __init__(self, consts: ConstantSet, eph, jd0_utc: float, frame_body: str, r0, v0, central0: str, t_max: float):
        self.consts, self.eph, self.jd0 = consts, eph, jd0_utc; self.frame = frame_body; self.arcs: list[Arc] = []; self.handoffs: list[dict] = []
        self.tdb0 = TU.utc_to_tdb(jd0_utc); self.t_max = t_max
        r, v = np.asarray(r0, float), np.asarray(v0, float)
        center = self._innermost(central0, r, v, 0.0)
        self.arcs.append(Arc(0.0, center[0], center[1], center[2])); self._extend()

    # ---- geometry helpers
    def _rel(self, body: str, t: float, center: str):
        """(r, v) of ``body`` relative to ``center`` at time t (zeros when equal)."""
        if body == center: return np.zeros(3), np.zeros(3)
        return self.eph.state(body, self.tdb0 + t / 86400.0, center)

    def _innermost(self, central: str, r, v, t):
        """Which body's sphere contains the point? Returns (body, r, v) about that body."""
        body = central
        for ch in CHILDREN.get(central, []):
            rc, vc = self._rel(ch, t, central)
            if np.linalg.norm(r - rc) < soi(ch, self.consts, self.eph, self.tdb0 + t / 86400.0): return ch, r - rc, v - vc
        return body, r, v

    def _arc_state(self, a: Arc, t: float):
        return kepler_propagate(self.consts.mu(a.center), a.r, a.v, t - a.t0)

    def _next_handoff(self, a: Arc, t_from: float):
        """First SOI crossing of the arc after t_from: ('exit', t) / ('enter', body, t) or None within t_max."""
        mu = self.consts.mu(a.center); cands = []
        par = PARENT.get(a.center); kids = [k for k in CHILDREN.get(a.center, [])]
        ts = np.unique(np.concatenate([np.linspace(t_from, self.t_max, 1500), t_from + np.geomspace(60.0, max(self.t_max - t_from, 61.0), 400)]))
        ts = ts[ts <= self.t_max]
        if len(ts) < 3: return None
        R = np.array([self._arc_state(a, t)[0] for t in ts])
        def exit_g(t, r=None):
            rr = self._arc_state(a, t)[0] if r is None else r; return float(np.linalg.norm(rr) - soi(a.center, self.consts, self.eph, self.tdb0 + t / 86400.0))
        def enter_g(k):
            def g(t, r=None):
                rr = self._arc_state(a, t)[0] if r is None else r; rc = self._rel(k, t, a.center)[0]
                return float(np.linalg.norm(rr - rc) - soi(k, self.consts, self.eph, self.tdb0 + t / 86400.0))
            return g
        found = []
        if par is not None:
            g = [exit_g(t, r) for t, r in zip(ts, R)]
            for i in range(len(ts) - 1):
                if g[i] < 0 <= g[i + 1]: found.append((_illinois(exit_g, ts[i], ts[i + 1], g[i], g[i + 1], tol=1e-6), 'exit', None)); break
        for k in kids:
            gf = enter_g(k); g = [gf(t, r) for t, r in zip(ts, R)]
            for i in range(len(ts) - 1):
                if g[i] > 0 >= g[i + 1]: found.append((_illinois(gf, ts[i], ts[i + 1], g[i], g[i + 1], tol=1e-6), 'enter', k)); break
        found = [f for f in found if f[0] > t_from + 1e-3]
        return min(found, key=lambda f: f[0]) if found else None

    def _extend(self):
        while True:
            a = self.arcs[-1]; h = self._next_handoff(a, a.t0)
            if h is None: return
            t, kind, kid = h; r, v = self._arc_state(a, t)
            if kind == 'exit':
                par = PARENT[a.center]; rp, vp = self._rel(a.center, t, par); new = Arc(t, par, r + rp, v + vp)
                self.handoffs.append(dict(t=t, text=f'leaves the sphere of influence of {a.center} (r = {np.linalg.norm(r):.6g} km)', kind='soi-exit', to=par))
            else:
                rc, vc = self._rel(kid, t, a.center); new = Arc(t, kid, r - rc, v - vc)
                self.handoffs.append(dict(t=t, text=f'enters the sphere of influence of {kid} (r = {np.linalg.norm(new.r):.6g} km)', kind='soi-enter', to=kid))
            self.arcs.append(new)
            if len(self.arcs) > 12: return

    def arc_at(self, t: float) -> Arc:
        cur = self.arcs[0]
        for a in self.arcs:
            if a.t0 <= t: cur = a
        return cur

    def state(self, t: float) -> np.ndarray:
        """6-vector about the frame body, ICRF axes."""
        a = self.arc_at(t); r, v = self._arc_state(a, t)
        if a.center != self.frame:
            rc, vc = self._rel(a.center, t, self.frame); r = r + rc; v = v + vc
        return np.concatenate([r, v])

    def local_state(self, t: float):
        a = self.arc_at(t); r, v = self._arc_state(a, t); return a.center, r, v
