"""Porkchop plot: departure x arrival date grid of C3, arrival v-infinity and total delta-v from the course Lambert solver with ephemeris positions.

Every cell calls ``core.lambert.lambert`` (the same verified solver as Module 12) and ``core.lambert.two_vector_transfer`` for the 3-D velocity.
Heliocentric, ecliptic-aligned axes; the transfer is prograde about the ecliptic pole; zero full revolutions; the short p root.
"""
from __future__ import annotations
import numpy as np
from ..core.constants import ConstantSet, D2R, R2D
from ..core.lambert import lambert, two_vector_transfer
from ..core import timeutil as TU
from ..dyn.models import kepler_propagate

OBL = np.radians(23.4392911)


def _ecl(v):
    c, s = np.cos(OBL), np.sin(OBL); return np.array([v[0], c * v[1] + s * v[2], -s * v[1] + c * v[2]])


def cell(mu_sun: float, eph, origin: str, target: str, jd_dep: float, jd_arr: float, consts: ConstantSet | None = None) -> dict | None:
    """One transfer (dates are UTC Julian dates). Returns None if the geometry is degenerate."""
    tof = (jd_arr - jd_dep) * 86400.0
    if tof <= 3600.0: return None
    r1, v1p = eph.state(origin, TU.utc_to_tdb(jd_dep), 'Sun'); r2, v2p = eph.state(target, TU.utc_to_tdb(jd_arr), 'Sun')
    r1, v1p, r2, v2p = _ecl(r1), _ecl(v1p), _ecl(r2), _ecl(v2p)
    n1, n2 = np.linalg.norm(r1), np.linalg.norm(r2); cosTA = np.clip(np.dot(r1, r2) / (n1 * n2), -1, 1); TA = np.degrees(np.arccos(cosTA))
    if np.cross(r1, r2)[2] < 0: TA = 360.0 - TA                              # prograde about +z (the ecliptic pole)
    if abs(TA - 180.0) < 0.5 or TA < 0.5 or TA > 359.5: return None          # collinear: the transfer plane is undefined
    best = None
    for root in ('small', 'large'):                                           # both p roots solve the alpha-beta equations; keep the one that really reaches r2 after the flight time
        try:
            L = lambert(mu_sun, n1, n2, TA, tof, root); T = two_vector_transfer(mu_sun, r1, r2, L['p'], hz_positive=True)
            rr, _ = kepler_propagate(mu_sun, r1, T['v1'], tof)
        except (ValueError, FloatingPointError, ZeroDivisionError, np.linalg.LinAlgError):
            continue
        err = float(np.linalg.norm(rr - r2))
        if np.isfinite(err) and (best is None or err < best[0]): best = (err, L, T)
    if best is None or best[0] > 1e-4 * n2: return None
    _, L, T = best
    v1 = T['v1']; p = L['p']; cT = np.cos(np.radians(T['TA']))
    gd = 1 - n1 / p * (1 - cT); fd = (np.dot(r1, v1) / (p * n1)) * (1 - cT) - np.sqrt(mu_sun / p) / n1 * np.sin(np.radians(T['TA']))
    v2 = fd * r1 + gd * v1
    vinf_d = float(np.linalg.norm(v1 - v1p)); vinf_a = float(np.linalg.norm(v2 - v2p))
    if not np.isfinite(vinf_d + vinf_a): return None
    return dict(c3=vinf_d ** 2, vinf_dep=vinf_d, vinf_arr=vinf_a, dv=vinf_d + vinf_a, tof_days=tof / 86400.0, v1=v1.tolist(), r1=r1.tolist(), a=float(L['a']), e=float(L['e']), TA=float(TA))


def grid(eph, origin: str, target: str, dep_start_jd: float, dep_days: float, arr_start_jd: float, arr_days: float, n: int = 40, consts: ConstantSet | None = None, progress=None) -> dict:
    consts = consts or ConstantSet(); mu = consts.mu('Sun')
    dep = np.linspace(dep_start_jd, dep_start_jd + dep_days, n); arr = np.linspace(arr_start_jd, arr_start_jd + arr_days, n)
    C3 = np.full((n, n), np.nan); VA = np.full((n, n), np.nan); DV = np.full((n, n), np.nan)
    for i, jd_d in enumerate(dep):
        if progress: progress(f'departure {i + 1} of {n}', i / n)
        for j, jd_a in enumerate(arr):
            c = cell(mu, eph, origin, target, jd_d, jd_a, consts)
            if c: C3[i, j], VA[i, j], DV[i, j] = c['c3'], c['vinf_arr'], c['dv']
    best = None
    if np.isfinite(C3).any():
        k = np.nanargmin(C3); i, j = np.unravel_index(k, C3.shape); best = dict(i=int(i), j=int(j), dep_jd=float(dep[i]), arr_jd=float(arr[j]), c3=float(C3[i, j]), vinf_arr=float(VA[i, j]), dv=float(DV[i, j]))
    return dict(dep=dep, arr=arr, c3=C3, vinf_arr=VA, dv=DV, best=best)


def render_svg(g: dict, origin: str, target: str, theme: str = 'dark') -> str:
    import io
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from ..theme import THEMES
    T = THEMES[theme]; fig, ax = plt.subplots(figsize=(7.2, 5.4), facecolor=T['surface']); ax.set_facecolor(T['surface'])
    d0 = g['dep'][0]; a0 = g['arr'][0]; X = g['dep'] - d0; Y = g['arr'] - a0
    c3 = np.ma.masked_invalid(g['c3']).T
    lv = np.array([5, 8, 10, 12, 15, 20, 30, 40, 60, 80, 120, 200]); lv = lv[lv <= np.nanmax(g['c3']) * 1.01] if np.isfinite(g['c3']).any() else lv
    if len(lv) >= 2 and c3.count():
        cs = ax.contourf(X, Y, c3, levels=np.concatenate([[0], lv, [np.nanmax(g['c3']) + 1]]), cmap='viridis_r', alpha=0.85)
        cl = ax.contour(X, Y, c3, levels=lv, colors=T['ink'], linewidths=0.6)
        ax.clabel(cl, fmt='%g', fontsize=7); cb = fig.colorbar(cs, ax=ax); cb.set_label('C3 (km²·s⁻²)', color=T['ink2']); cb.ax.tick_params(colors=T['ink2'])
    if g['best']:
        b = g['best']; ax.plot(b['dep_jd'] - d0, b['arr_jd'] - a0, marker='*', color='#ff6b4a', markersize=14, markeredgecolor=T['ink'])
    ax.set_xlabel(f'days after {TU.format_gregorian(d0)[:11]} (departure from {origin})', color=T['ink2']); ax.set_ylabel(f'days after {TU.format_gregorian(a0)[:11]} (arrival at {target})', color=T['ink2'])
    ax.tick_params(colors=T['ink2']); [s.set_color(T['axis']) for s in ax.spines.values()]; ax.set_title(f'{origin} to {target}: departure C3 (km²·s⁻²)', color=T['ink'])
    b = io.StringIO(); fig.savefig(b, format='svg', facecolor=fig.get_facecolor()); plt.close(fig); t = b.getvalue(); return t[t.index('<svg'):]


def transfer_mission(eph, origin: str, target: str, jd_dep: float, jd_arr: float, consts: ConstantSet | None = None):
    """A heliocentric Mission for one porkchop cell: the spacecraft leaves ``origin`` on the Lambert transfer and is propagated to the arrival date."""
    from .model import Mission, Spacecraft, CoordSys, Propagator, OrbitView, Command
    consts = consts or ConstantSet(); c = cell(consts.mu('Sun'), eph, origin, target, jd_dep, jd_arr, consts)
    if c is None: raise ValueError('no valid transfer for these dates')
    from .params import format_epoch
    m = Mission(name=f'{origin} to {target} transfer ({TU.format_gregorian(jd_dep)[:11]})', constants=consts.mode)
    m.coords = [CoordSys('SunMJ2000Ec', 'Sun', 'MJ2000Ec')]
    r, v = c['r1'], c['v1']
    m.spacecraft = [Spacecraft('Sat', 'UTCGregorian', format_epoch(jd_dep, 'UTCGregorian'), 'SunMJ2000Ec', 'Cartesian', dict(X=r[0], Y=r[1], Z=r[2], VX=v[0], VY=v[1], VZ=v[2]))]
    m.propagators = [Propagator('SunProp', 'Sun', 'two_body', ['Sun'], 'RungeKutta89', max_step=864000.0)]
    m.views = [OrbitView('View', ['Sat', 'Sun', origin, target], 'SunMJ2000Ec')]
    m.commands = [Command('Propagate', items=[['SunProp', ['Sat']]], stops=[f'Sat.ElapsedSecs = {float(c["tof_days"]) * 86400.0!r}'])]
    m.notes = [f'departure C3 = {c["c3"]:.4f} km^2/s^2 (v-infinity {c["vinf_dep"]:.4f} km/s); arrival v-infinity = {c["vinf_arr"]:.4f} km/s; time of flight {c["tof_days"]:.2f} days']
    return m
