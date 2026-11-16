"""Module 3 - State <-> planar conic (HW3 P3, HW4, Exam 1 P2/P3).

Input modes
  polar : r, v_r, v_theta (= r*thetadot)
  xy    : r_x, r_y, v_x, v_y in an inertial planar frame (counter-clockwise motion)
  h_eps : h, eps, theta*
  rp_ra : r_p, r_a, theta*
  a_e   : a (negative for a hyperbola), e, theta*
  p_e   : p, e, theta*
"""
from __future__ import annotations
import numpy as np
from ..core.constants import D2R, R2D, wrap360, wrap180
from ..core.kepler import E_from_th, H_from_th, time_since_periapsis
from ..core.conic import conic_from_rv_polar, gamma_of
from ..results import Result, KM, KMS, MU, EPS, HU, DEG, SEC, DAY, HR, NONE
from ..scene import (Scene, Orbit, Disk, Pt, vector, local_horizon, angle_arc, apsides_line, minor_axis,
                     vacant_focus, unit_triad, Rz, unit)
from .common import vel_scale, orbit_track, kind_of

Z = np.array([0, 0, 1.0])


def signed_arc(sc: Scene, origin, u, w, ang_deg, radius, label, role='ink2'):
    """Arc of |ang| from u to w when ang>=0, from w to u otherwise (so the arc always spans the signed angle)."""
    if ang_deg >= 0: angle_arc(sc, origin, u, w, radius, label, role, Z)
    else: angle_arc(sc, origin, w, u, radius, label, role, Z)


def solve(mu: float, mode: str, vals: dict, ths_deg: float | None = None, body_R: float | None = None,
          body_name: str = '', label: str = 'Module 3') -> Result:
    res = Result('State ⇄ planar conic', label, inputs=dict(mu=mu, mode=mode, **vals, ths_deg=ths_deg))
    omega = 0.0; st = 'Input'
    if mode == 'polar':
        r, vr, vt = vals['r'], vals['vr'], vals['vt']
        c = conic_from_rv_polar(mu, r, vr, vt); p, e, ths = c['p'], c['e'], c['ths']
        res.check(f'θ* from atan2(ṙ·h/μ, p/r − 1): ṙ = {vr:+.4g} km/s ⇒ θ* ∈ ' + ('(0°, 180°) outbound' if vr > 0 else '(180°, 360°) inbound' if vr < 0 else '{0°, 180°} at an apsis'))
    elif mode == 'xy':
        rx, ry, vx, vy = (vals[k] for k in ('rx', 'ry', 'vx', 'vy')); r = np.hypot(rx, ry)
        vr = (rx * vx + ry * vy) / r; vt = (rx * vy - ry * vx) / r
        if vt <= 0: raise ValueError('clockwise / radial motion is not supported in xy mode; mirror the input')
        c = conic_from_rv_polar(mu, r, vr, vt); p, e, ths = c['p'], c['e'], c['ths']
        theta_pos = np.arctan2(ry, rx) * R2D; omega = wrap360(theta_pos - ths)
        res.check(f'ω (angle of ê from x̂) = θ − θ* = {theta_pos:.4f}° − {ths:.4f}° (θ from atan2(r_y, r_x))')
    else:
        if ths_deg is None: raise ValueError('theta* is required in this mode')
        ths = float(ths_deg)
        if mode == 'h_eps':
            h, eps = vals['h'], vals['eps']; p = h * h / mu; e = np.sqrt(max(0.0, 1 + 2 * eps * h * h / mu ** 2))
        elif mode == 'rp_ra':
            rp_, ra_ = vals['rp'], vals['ra']; p = 2 * rp_ * ra_ / (rp_ + ra_); e = (ra_ - rp_) / (ra_ + rp_)
        elif mode == 'a_e':
            e = vals['e']; p = vals['a'] * (1 - e * e)
        elif mode == 'p_e':
            p, e = vals['p'], vals['e']
        else:
            raise ValueError(mode)
        r = p / (1 + e * np.cos(ths * D2R)); c = None
        vr = mu / np.sqrt(mu * p) * e * np.sin(ths * D2R); vt = np.sqrt(mu * p) / r
    if e > 1 and abs(ths) > np.degrees(np.arccos(-1 / e)): res.warn('θ* lies beyond the asymptote: no such point on the hyperbola')
    if p / (1 + e) < 0: res.warn('negative periapsis radius')

    h = np.sqrt(mu * p); v = np.hypot(vr, vt); eps = v * v / 2 - mu / r; kind = kind_of(e)
    gam = float(gamma_of(e, ths)); a = p / (1 - e * e) if abs(1 - e) > 1e-12 else np.inf
    rp = p / (1 + e); ra = p / (1 - e) if e < 1 else None
    res.check(f'γ from atan2(e sinθ*, 1 + e cosθ*) = {gam:+.4f}° ⇒ ṙ {"> 0 (γ > 0)" if gam > 0 else "< 0 (γ < 0)" if gam < 0 else "= 0"}')
    if body_R and rp < body_R: res.warn(f'periapsis radius {rp:,.1f} km is below the surface of {body_name or "the body"} ({body_R:,.1f} km)')
    if kind == 'hyperbola': res.warn('orbit is hyperbolic (ε > 0)')
    if kind == 'parabola': res.warn('ε ≈ 0: parabola — a = ∞, no E/H or period')

    g = 'Conic'
    res.add('Conic type', '', kind, group=g)
    res.add('Semi-latus rectum', 'p', p, KM, 'p = h²/μ', group=g)
    res.add('Eccentricity', 'e', e, NONE, 'e = √(1 + 2εh²/μ²)', group=g)
    res.add('Semi-major axis', 'a', a, KM, 'a = −μ/(2ε)', group=g)
    res.add('Specific angular momentum', 'h', h, HU, 'h = r·v_θ = √(μp)', group=g)
    res.add('Specific energy', 'ε', eps, EPS, 'ε = v²/2 − μ/r', group=g)
    res.add('Periapsis radius', 'r_p', rp, KM, 'r_p = p/(1+e)', group=g)
    if ra is not None: res.add('Apoapsis radius', 'r_a', ra, KM, 'r_a = p/(1−e)', group=g)
    if e < 1:
        n = np.sqrt(mu / a ** 3); P = 2 * np.pi / n
        res.add('Period', 'P', P, SEC, 'P = 2π√(a³/μ)', group=g); res.add('Period', 'P', P / 3600, HR, group=g)
        res.add('Mean motion', 'n', n, 's⁻¹', 'n = √(μ/a³)', group=g)
    if kind == 'hyperbola':
        res.add('Hyperbolic excess speed', 'v∞', np.sqrt(mu / -a), KMS, 'v∞ = √(μ/|a|)', group=g)
        res.add('Asymptote true anomaly', 'θ*∞', np.degrees(np.arccos(-1 / e)), DEG, 'cos θ*∞ = −1/e', group=g)
    g = 'Position & velocity'
    res.add('True anomaly', 'θ*', ths if kind == 'hyperbola' else wrap360(ths), DEG, 'θ* = atan2(ṙh/μ, p/r − 1)', group=g)
    res.add('Radius', 'r', r, KM, 'r = p/(1 + e cosθ*)', group=g)
    res.add('Speed', 'v', v, KMS, 'v = √(v_r² + v_θ²)', group=g)
    res.add('Radial velocity', 'v_r', vr, KMS, 'v_r = (μ/h) e sinθ*', group=g)
    res.add('Transverse velocity', 'v_θ', vt, KMS, 'v_θ = h/r', group=g)
    res.add('Flight-path angle', 'γ', gam, DEG, 'tanγ = e sinθ*/(1+e cosθ*)', group=g)
    res.add('r̄ in ê,p̂', 'r̄', [r * np.cos(ths * D2R), r * np.sin(ths * D2R)], KM, 'r̄ = r(cosθ* ê + sinθ* p̂)', group=g)
    vp_ = mu / h * np.array([-np.sin(ths * D2R), e + np.cos(ths * D2R)])
    res.add('v̄ in ê,p̂', 'v̄', vp_, KMS, 'v̄ = (μ/h)[−sinθ* ê + (e + cosθ*) p̂]', group=g)
    res.add('r̄ in r̂,θ̂', 'r̄_rθ', [r, 0.0], KM, group=g)
    res.add('v̄ in r̂,θ̂', 'v̄_rθ', [vr, vt], KMS, group=g)
    if e > 1e-9 and abs(e - 1) > 1e-9:
        g = 'Anomalies & time'
        if e < 1:
            E = E_from_th(e, ths * D2R); M = E - e * np.sin(E); t = time_since_periapsis(mu, a, e, ths); Pp = 2 * np.pi * np.sqrt(a ** 3 / mu)
            res.add('Eccentric anomaly', 'E', E * R2D, DEG, 'E = 2 atan2(√(1−e) sin θ*/2, √(1+e) cos θ*/2)', group=g)
            res.add('Mean anomaly', 'M', M * R2D, DEG, 'M = E − e sinE', group=g)
            res.add('Time since periapsis, (−P/2, P/2]', 't−t_p', t, SEC, 't − t_p = M/n', group=g)
            res.add('Time since periapsis, [0, P)', 't−t_p', t % Pp, SEC, 'mod P', group=g)
            res.add('Time since periapsis, [0, P)', 't−t_p', (t % Pp) / 3600, HR, group=g)
        else:
            H = H_from_th(e, ths * D2R); t = time_since_periapsis(mu, a, e, ths)
            res.add('Hyperbolic anomaly', 'H', H, 'rad', 'H = 2 artanh(√((e−1)/(e+1)) tan θ*/2)', group=g)
            res.add('Time since periapsis', 't−t_p', t, SEC, 't − t_p = (e sinhH − H)/n', group=g)
            res.add('Time since periapsis', 't−t_p', t / 3600, HR, group=g)
    if c is not None: res.data['conic_from_rv_polar'] = c
    res.data.update(dict(p=p, e=e, a=a, h=h, eps=eps, r=r, v=v, vr=vr, vt=vt, gamma=gam, ths=ths, omega=omega, rp=rp, ra=ra))

    # ---------------- scene ----------------
    Q = Rz(omega); ref = ra if ra else max(r * 1.15, 4 * rp)
    orb = Orbit('orbit', p, e, Q, 'orbit', rmax=None if ra else 1.35 * ref, label_ths=(ths + 180 if e < 1 else -0.55 * np.degrees(np.arccos(max(-1.0, min(1.0, (p / (1.35 * ref) - 1) / e))))))
    sc = Scene(f'{kind} — e = {e:.4g}', label); sc.orbits.append(orb); sc.focus_name = body_name
    if body_R: sc.disks.append(Disk(np.zeros(3), body_R, ''))
    sc.pts.append(Pt(np.zeros(3), f'F ({body_name})' if body_name else 'F', 'ink', 'o', 5))
    pos = orb.pos(ths); rhat = unit(pos); that = unit(np.cross(Z, rhat)); vhat = orb.vel_dir(ths)
    apsides_line(sc, orb)
    minor_axis(sc, orb)
    if e < 1: vacant_focus(sc, orb, 'vacant focus F*')
    unit_triad(sc, np.zeros(3), Q, ('ê', 'p̂', 'ĥ'), 0.18 * ref)
    vector(sc, np.zeros(3), pos, f'r̄ (r = {r:,.1f} km)')
    sc.pts.append(Pt(pos, '', 'ink', 'o', 6))
    vector(sc, pos, vhat * v, f'v̄ ({v:,.4g} km/s)', 'vel', scale=vel_scale(ref, v))
    local_horizon(sc, pos, Z, 0.28 * ref)
    th_show = ths if kind == 'hyperbola' else wrap360(ths)
    signed_arc(sc, np.zeros(3), Q[:, 0], rhat, th_show, 0.13 * ref, f'θ* = {th_show:.2f}°')
    signed_arc(sc, pos, that, vhat, -gam, 0.12 * ref, f'γ = {gam:+.2f}°', 'ink')   # γ>0 is clockwise from θ̂ (toward +r̂)
    sc.plane2d = (np.array([1.0, 0, 0]), np.array([0, 1.0, 0]))
    trk, dur = orbit_track(mu, orb, ths, -ths if e >= 1 else None, 'spacecraft')
    if e >= 1:
        lim = np.degrees(np.arccos(max(-1.0, min(1.0, (p / orb.rmax - 1) / e)))) if orb.rmax else ths
        trk, dur = orbit_track(mu, orb, -lim, lim, 'spacecraft')
    sc.tracks.append(trk); sc.duration_s = dur
    res.scene = sc
    return res
