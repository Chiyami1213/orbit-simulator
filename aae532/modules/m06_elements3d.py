"""Module 6 - classical elements <-> inertial state (HW5 P3-P4, HW6 P1, Exam 1 P2).

Conventions: theta = omega + theta* (argument of latitude); 3-1-3 rotation (Omega, i, theta).
Omega = atan2(h_x, -h_y) because h_hat = (sinOmega sin i, -cosOmega sin i, cos i).
"""
from __future__ import annotations
import numpy as np
from ..core.constants import D2R, R2D, wrap360
from ..core.elements import rv_from_elements, elements_from_rv
from ..core.frames import dcm_313
from ..core.conic import gamma_of
from ..core.kepler import E_from_th, H_from_th, time_since_periapsis
from ..results import Result, KM, KMS, DEG, SEC, HR, NONE, EPS, HU
from ..scene import (Scene, Orbit, Disk, Pt, Line, vector, local_horizon, angle_arc, apsides_line, nodes_line,
                     equatorial_plane, unit_triad, unit)
from .common import vel_scale, orbit_track, kind_of, clean360


def solve(mu: float, mode: str, vals: dict, body_R: float | None = None, body_name: str = '', label: str = 'Module 6') -> Result:
    """mode 'elements': a, e, inc, Om, om and either ths or theta (deg).  mode 'state': r (3), v (3) in x,y,z."""
    res = Result('Elements ⇄ 3-D state', label, inputs=dict(mu=mu, mode=mode, **{k: (list(v) if hasattr(v, '__len__') else v) for k, v in vals.items()}))
    if mode == 'elements':
        a, e, inc, Om, om = (vals[k] for k in ('a', 'e', 'inc', 'Om', 'om'))
        ths = vals['ths'] if 'ths' in vals else vals['theta'] - om
        rvec, vvec, info = rv_from_elements(mu, a, e, inc, Om, om, ths)
    else:
        rvec, vvec = np.asarray(vals['r'], float), np.asarray(vals['v'], float)
    el = elements_from_rv(mu, rvec, vvec)
    a, e, inc, Om, om, ths, theta = el['a'], el['e'], el['inc'], clean360(el['Om']), clean360(el['om']), el['ths'], clean360(el['theta'])
    el.update(Om=Om, om=om, theta=theta)
    r, v, h = el['r'], el['v'], el['h']; hv = el['hv']; hh = hv / h; p = el['p']; kind = kind_of(e)
    Q = dcm_313(Om, inc, om)
    vr = float(rvec @ vvec / r); vt = h / r
    equatorial = np.sin(inc * D2R) < 1e-10
    # ---------- quadrant checks (never arccos alone) ----------
    res.check(f'Ω = atan2(ĥ_x, −ĥ_y) = atan2({hh[0]:+.5f}, {-hh[1]:+.5f}) = {Om:.4f}°  (sinΩ sin i = {hh[0]:+.5f}, −cosΩ sin i = {hh[1]:+.5f})')
    res.check(f'i = arccos(ĥ_z) = {inc:.4f}° is unambiguous on [0°, 180°] ({"prograde" if inc < 90 else "retrograde"})')
    res.check(f'θ* = atan2((r̄·v̄/r)·h/μ, p/r − 1) = {ths:.4f}°; ṙ = {vr:+.5f} km/s ⇒ θ* ∈ ' + ('(0°, 180°)' if vr > 0 else '(−180°, 0°)' if vr < 0 else '{0°, 180°}'))
    res.check(f'θ = atan2(r̂_z/sin i, r̂·n̂) = {theta:.4f}°  (r̂_z = {rvec[2] / r:+.5f});  ω = θ − θ* = {om:.4f}°')
    if equatorial: res.warn('equatorial orbit: Ω is undefined — set to 0° and θ measured from x̂ (ω is then the longitude of periapsis)')
    if body_R and el.get('a') and e < 1 and a * (1 - e) < body_R: res.warn('perigee radius is below the surface')
    if kind == 'hyperbola': res.warn('orbit is hyperbolic')

    g = 'Elements'
    res.add('Semi-major axis', 'a', a, KM, 'a = −μ/(2ε)', group=g); res.add('Eccentricity', 'e', e, NONE, 'ē = [(v² − μ/r) r̄ − (r̄·v̄) v̄]/μ', group=g)
    res.add('Inclination', 'i', inc, DEG, 'cos i = ĥ_z', group=g); res.add('RAAN', 'Ω', Om, DEG, 'Ω = atan2(ĥ_x, −ĥ_y)', group=g)
    res.add('Argument of periapsis', 'ω', om, DEG, 'ω = θ − θ*', group=g); res.add('True anomaly', 'θ*', ths if e >= 1 else wrap360(ths), DEG, group=g)
    res.add('Argument of latitude', 'θ', theta, DEG, 'θ = ω + θ*', group=g)
    res.add('Semi-latus rectum', 'p', p, KM, group=g); res.add('Angular momentum', 'h', h, HU, group=g); res.add('Energy', 'ε', el['eps'], EPS, group=g)
    res.add('Radius', 'r', r, KM, group=g); res.add('Speed', 'v', v, KMS, group=g); res.add('Flight-path angle', 'γ', el['gamma'], DEG, 'γ = arcsin(r̄·v̄/(r v))', group=g)
    res.add('Periapsis radius', 'r_p', p / (1 + e), KM, group=g)
    if e < 1:
        res.add('Apoapsis radius', 'r_a', p / (1 - e), KM, group=g); res.add('Period', 'P', el['P'] / 3600, HR, group=g)
        res.add('Eccentric anomaly', 'E', el['E'], DEG, group=g); res.add('Mean anomaly', 'M', el['M'] % 360, DEG, 'M = E − e sinE', group=g)
        res.add('E in [0°, 360°)', 'E', el['E'] % 360, DEG, group=g)
        res.add('t − t_p, (−P/2, P/2]', 't−t_p', el['t_tp'] / 3600, HR, group=g); res.add('t − t_p, [0, P)', 't−t_p', (el['t_tp'] % el['P']) / 3600, HR, group=g)
    else:
        res.add('Hyperbolic anomaly', 'H', el['H'], 'rad', group=g); res.add('t − t_p', 't−t_p', el['t_tp'] / 3600, HR, group=g)
    g = 'Vectors'
    res.add('r̄ in x̂,ŷ,ẑ', 'r̄_xyz', rvec, KM, group=g); res.add('v̄ in x̂,ŷ,ẑ', 'v̄_xyz', vvec, KMS, group=g)
    res.add('r̄ in r̂,θ̂,ĥ', 'r̄_rθh', [r, 0, 0], KM, group=g); res.add('v̄ in r̂,θ̂,ĥ', 'v̄_rθh', [vr, vt, 0], KMS, 'v_r = (μ/h) e sinθ*, v_θ = h/r', group=g)
    t_ = ths * D2R
    res.add('r̄ in ê,p̂,ĥ', 'r̄_epĥ', [r * np.cos(t_), r * np.sin(t_), 0], KM, group=g)
    res.add('v̄ in ê,p̂,ĥ', 'v̄_epĥ', (mu / h) * np.array([-np.sin(t_), e + np.cos(t_), 0]), KMS, group=g)
    res.add('ĥ in x̂,ŷ,ẑ', 'ĥ', hh, NONE, 'ĥ = (sinΩ sin i, −cosΩ sin i, cos i)', group=g)
    res.add('ê in x̂,ŷ,ẑ', 'ê', Q[:, 0], NONE, group=g); res.add('p̂ in x̂,ŷ,ẑ', 'p̂', Q[:, 1], NONE, group=g)
    res.add('Rotation matrix [r̂ θ̂ ĥ] (columns, x̂ŷẑ)', 'C', Q.ravel(), NONE, '3-1-3 (Ω, i, θ)', group=g)
    res.data.update(el); res.data.update(rvec=rvec, vvec=vvec, Q=Q, vr=vr, vt=vt)

    # ---------------- scene (3-D native; 2-D = perifocal view) ----------------
    Qo = dcm_313(Om, inc, om)
    ref = p / (1 - e) if e < 1 else max(r * 1.2, 4 * p / (1 + e))
    orb = Orbit('orbit', p, e, Qo, 'orbit', rmax=None if e < 1 else 1.4 * ref)
    sc = Scene(f'{kind}: a = {a:,.1f} km, e = {e:.4f}, i = {inc:.2f}°', label, is3d=True); sc.orbits.append(orb)
    if body_R: sc.disks.append(Disk(np.zeros(3), body_R, body_name or 'body'))
    sc.pts.append(Pt(np.zeros(3), 'F', 'ink', 'o', 5))
    S = 1.2 * ref
    equatorial_plane(sc, S)
    unit_triad(sc, np.zeros(3), np.eye(3), ('x̂', 'ŷ', 'ẑ'), 0.35 * ref, 'muted', only3d=True)
    unit_triad(sc, np.zeros(3), Qo, ('ê', 'p̂', 'ĥ'), 0.30 * ref, 'ink2')
    ex, ph = Qo[:, 0], Qo[:, 1]
    rh = unit(rvec); th_hat = unit(np.cross(hh, rh))
    unit_triad(sc, rvec, np.column_stack([rh, th_hat, hh]), ('r̂', 'θ̂', 'ĥ'), 0.18 * ref, 'accent')
    vector(sc, np.zeros(3), rvec, f'r̄ (r = {r:,.1f} km)', 'vector')
    vector(sc, rvec, vvec, f'v̄ ({v:.4f} km/s)', 'vel', scale=vel_scale(ref, v))
    sc.pts.append(Pt(rvec, '', 'ink', 'o', 6))
    apsides_line(sc, orb)
    if not equatorial:
        n_hat = nodes_line(sc, Om, S)
        sc.pts.append(Pt(orb.pos(-om), 'ascending node ☊', 'good', 'D', 6)); sc.pts.append(Pt(orb.pos(180 - om), 'descending node ☋', 'warn', 'D', 6))
        angle_arc(sc, np.zeros(3), np.array([0, 0, 1.0]), hh, 0.22 * ref, f'i = {inc:.2f}°', 'ink2', only3d=True)
        angle_arc(sc, np.zeros(3), np.array([1.0, 0, 0]), n_hat, 0.5 * ref, f'Ω = {Om:.2f}°', 'ink2', np.array([0, 0, 1.0]), only3d=True)
        angle_arc(sc, np.zeros(3), n_hat, ex, 0.4 * ref, f'ω = {om:.2f}°', 'ink2', hh)
    angle_arc(sc, np.zeros(3), ex, rh, 0.14 * ref, f'θ* = {wrap360(ths):.2f}°', 'ink', hh)
    sc.plane2d = (ex, ph)       # 2-D figure = perifocal projection
    trk, dur = orbit_track(mu, orb, ths, -ths if e >= 1 else None, 'spacecraft')
    if e >= 1:
        lim = np.degrees(np.arccos(max(-1.0, min(1.0, (p / orb.rmax - 1) / e)))); trk, dur = orbit_track(mu, orb, -lim, lim, 'spacecraft')
    sc.tracks.append(trk); sc.duration_s = dur; res.scene = sc
    return res
