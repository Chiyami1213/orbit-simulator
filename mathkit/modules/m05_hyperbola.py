"""Module 5 - hyperbolic flyby geometry (HW4 P3, HW5 P2, HW6 P1; also the planet-centred inset of Modules 10-11).

Give any two of r_p, |a|, e, v_inf. Aim point: theta*_aim = -(theta*_inf - 90 deg) on approach; d_aim = sqrt((r_p + |a|)^2 - b^2) = |a|.
"""
from __future__ import annotations
import numpy as np
from ..core.constants import D2R, R2D
from ..core.hyperbola import hyperbola
from ..core.kepler import H_from_th, time_since_periapsis
from ..core.conic import r_of, gamma_of
from ..core.patched import capture_dv
from ..results import Result, KM, KMS, DEG, SEC, HR, DAY, NONE, EPS, HU
from ..scene import (Arc, Scene, Orbit, Disk, Pt, Line, vector, angle_arc, apsides_line, asymptotes, aim_point_b, Rz, unit, unit_triad)
from .common import orbit_track
from .m03_conic import signed_arc, Z


def resolve_hyperbola(mu: float, given: dict) -> tuple[float, float]:
    """(|a|, e) from any two of rp, a_abs, e, vinf."""
    k = set(given)
    if len(k) != 2: raise ValueError('give exactly two of rp, a_abs, e, vinf')
    g = lambda n: given[n]
    if k == {'rp', 'a_abs'}: return g('a_abs'), 1 + g('rp') / g('a_abs')
    if k == {'rp', 'e'}: return g('rp') / (g('e') - 1), g('e')
    if k == {'rp', 'vinf'}: a = mu / g('vinf') ** 2; return a, 1 + g('rp') / a
    if k == {'a_abs', 'e'}: return g('a_abs'), g('e')
    if k == {'a_abs', 'vinf'}: raise ValueError('|a| and v_inf are not independent (|a| = μ/v∞²)')
    if k == {'e', 'vinf'}: return mu / g('vinf') ** 2, g('e')
    raise ValueError(sorted(k))


def hyp_scene(title: str, label: str, mu: float, a_abs: float, e: float, R: float | None, body_name: str = '', omega: float = 0.0,
              ths_mark: float | None = 120.0, cw: bool = False) -> Scene:
    hy = hyperbola(mu, a_abs=a_abs, e=e); rp, p, b = hy['rp'], hy['p'], hy['b']; th_inf = hy['th_inf']
    Q = Rz(omega) @ np.diag([1.0, -1.0, 1.0]) if cw else Rz(omega)     # cw: mirrored (clockwise) pass
    rmax = max(5 * rp, 3.2 * a_abs); nrm = -Z if cw else Z
    orb = Orbit('hyperbola', p, e, Q, 'orbit', rmax=rmax)
    sc = Scene(title, label); sc.orbits.append(orb)
    if R: sc.disks.append(Disk(np.zeros(3), R, '', body=body_name))
    sc.pts.append(Pt(np.zeros(3), f'F ({body_name})' if body_name else 'F', 'ink', 'o', 5))
    asymptotes(sc, orb, length=2.2 * rmax)
    aim_point_b(sc, orb, 'aim point', 'b')
    apsides_line(sc, orb); sc.pts.append(Pt(orb.pos(0), f'r_p = {rp:,.1f} km', 'ink', 'o', 6))
    sc.lines.append(Line(np.zeros(3), orb.pos(90), f'p = {p:,.1f} km', 'muted', False, 1.0, 0.6))
    if ths_mark and ths_mark < th_inf - 1:
        arc = Orbit('', p, e, Q, 'orbit2', ths_range=(-ths_mark, ths_mark)); sc.orbits.append(arc)
        for s_ in (-ths_mark, ths_mark): sc.pts.append(Pt(orb.pos(s_), f'θ* = {s_:+.0f}°', 'orbit2', 'o', 6))
    angle_arc(sc, np.zeros(3), Q[:, 0], Q @ np.array([np.cos(th_inf * D2R), np.sin(th_inf * D2R), 0]), 0.2 * rmax, f'θ*∞ = {th_inf:.2f}°', 'ink2', nrm)
    C = Q @ np.array([a_abs * e, 0, 0]); d_out = Q @ np.array([np.cos(th_inf * D2R), np.sin(th_inf * D2R), 0]); d_in = -(Q @ np.array([np.cos(th_inf * D2R), -np.sin(th_inf * D2R), 0]))
    sc.arcs.append(Arc(C, d_in, d_out, 0.35 * a_abs * e, f"δ = {hy['delta']:.2f}°", 'warn', nrm))      # turn angle at the asymptote intersection
    lim = np.degrees(np.arccos(max(-1.0, min(1.0, (p / rmax - 1) / e))))
    trk, dur = orbit_track(mu, orb, -lim, lim, 'spacecraft'); sc.tracks.append(trk); sc.duration_s = dur
    return sc


def solve(mu: float, given: dict, R: float | None = None, body_name: str = '', ths_deg: float | None = -120.0, e_capture: float = 0.0,
          label: str = 'Module 5') -> Result:
    res = Result('Hyperbolic flyby geometry', label, inputs=dict(mu=mu, given=given, R=R, ths_deg=ths_deg, e_capture=e_capture))
    a_abs, e = resolve_hyperbola(mu, given); hy = hyperbola(mu, a_abs=a_abs, e=e)
    g = 'Hyperbola'
    res.add('|a|', '|a|', a_abs, KM, '|a| = μ/v∞²', group=g); res.add('Eccentricity', 'e', e, NONE, 'e = 1 + r_p/|a|', group=g)
    res.add('Periapsis radius', 'r_p', hy['rp'], KM, 'r_p = |a|(e − 1)', group=g); res.add('Semi-latus rectum', 'p', hy['p'], KM, 'p = |a|(e² − 1)', group=g)
    res.add('Angular momentum', 'h', hy['h'], HU, 'h = √(μp)', group=g); res.add('Energy', 'ε', hy['eps'], EPS, 'ε = μ/(2|a|)', group=g)
    res.add('Hyperbolic excess speed', 'v∞', hy['vinf'], KMS, 'v∞ = √(μ/|a|)', group=g)
    res.add('Asymptote true anomaly', 'θ*∞', hy['th_inf'], DEG, 'θ*∞ = atan2(√(e²−1), −1) (cosθ*∞ = −1/e)', group=g)
    res.add('Turn angle', 'δ', hy['delta'], DEG, 'δ = 2 asin(1/e)', group=g)
    res.add('Impact parameter', 'b', hy['b'], KM, 'b = |a|√(e² − 1)', group=g)
    res.add('Aim-point distance', 'd_aim', np.sqrt((hy['rp'] + a_abs) ** 2 - hy['b'] ** 2), KM, 'd_aim = √((r_p + |a|)² − b²) = |a|', group=g)
    res.add('Aim-point true anomaly', 'θ*_aim', -(hy['th_inf'] - 90), DEG, 'θ*_aim = −(θ*∞ − 90°)', group=g)
    res.add('Radius at θ*_aim', 'r_aim', r_of(hy['p'], e, -(hy['th_inf'] - 90)), KM, group=g)
    res.add('Periapsis speed', 'v_p', hy['vp'], KMS, 'v_p = √(μ(2/r_p + 1/|a|))', group=g)
    res.add('Capture Δv at r_p' + (' (circular)' if e_capture == 0 else f' (e = {e_capture:g})'), 'Δv_cap', capture_dv(mu, hy['rp'], hy['vinf'], e_capture), KMS,
            'Δv = v_p − √(μ(1 + e_c)/r_p)', group=g)
    res.add('Escape Δv from a circular orbit at r_p', 'Δv_esc', capture_dv(mu, hy['rp'], hy['vinf'], 0.0), KMS, 'same magnitude, applied as a departure burn', group=g)
    if R and hy['rp'] < R: res.warn(f'periapsis radius {hy["rp"]:,.1f} km is below the surface ({R:,.1f} km)')
    if ths_deg is not None:
        if abs(ths_deg) >= hy['th_inf']: res.warn(f'θ* = {ths_deg}° is beyond the asymptote (θ*∞ = {hy["th_inf"]:.2f}°)')
        else:
            g = f'At θ* = {ths_deg:g}°'; r_ = r_of(hy['p'], e, ths_deg); H = H_from_th(e, ths_deg * D2R); t = time_since_periapsis(mu, hy['a'], e, ths_deg)
            res.add('Radius', 'r', r_, KM, group=g)
            if R: res.add('Radius in body radii', 'r/R', r_ / R, NONE, group=g)
            res.add('Speed', 'v', np.sqrt(mu * (2 / r_ + 1 / a_abs)), KMS, group=g); res.add('Flight-path angle', 'γ', float(gamma_of(e, ths_deg)), DEG, group=g)
            res.add('Hyperbolic anomaly', 'H', H, 'rad', 'H = 2 artanh(√((e−1)/(e+1)) tan θ*/2)', group=g)
            res.add('Time from periapsis (t − t_p)', 't−t_p', t, SEC, '(e sinhH − H)/n', group=g); res.add('Time to periapsis', 't_p−t', -t / 3600, HR, group=g)
    res.data.update(hy=hy, a_abs=a_abs, e=e)
    res.scene = hyp_scene(f'hyperbola, e = {e:.4f}, v∞ = {hy["vinf"]:.4f} km/s', label, mu, a_abs, e, R, body_name, 0.0, 120.0)
    return res
