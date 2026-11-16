"""Module 4 - Kepler propagation with f and g (HW4 P1-2, HW5 P1, Exam 2 P3).

Initial position given as theta*, mean anomaly M (deg) or eccentric anomaly E (deg) for an ellipse.
f, g, fdot, gdot are computed in BOTH the delta-theta* form (BMW 4.5) and the delta-E form (BMW 4.6-29..32) and
shown to agree (ellipse). Hyperbolas use the delta-theta* form only.
"""
from __future__ import annotations
import numpy as np
import matplotlib.pyplot as plt
from ..core.constants import D2R, R2D, wrap360
from ..core.kepler import E_from_th, th_from_E, H_from_th, kepler_E, time_since_periapsis, propagate
from ..core.conic import gamma_of
from ..core.fg import fg_theta, fg_E
from ..results import Result, KM, KMS, DEG, SEC, HR, DAY, NONE
from ..scene import (Scene, Orbit, Disk, Pt, Line, vector, angle_arc, apsides_line, aux_circle, unit_triad, Rz, unit)
from ..theme import THEMES, color
from .common import vel_scale, orbit_track
from .m03_conic import signed_arc, Z


def solve(mu: float, a: float, e: float, start: dict, dt_s: float, body_R: float | None = None, body_name: str = '',
          label: str = 'Module 4') -> Result:
    """start: one of {'ths': deg}, {'M': deg}, {'E': deg}. dt_s in seconds (may be negative)."""
    res = Result('Kepler propagation', label, inputs=dict(mu=mu, a=a, e=e, start=start, dt_s=dt_s))
    p = a * (1 - e * e); ell = e < 1
    if ell:
        n = np.sqrt(mu / a ** 3); P = 2 * np.pi / n
        if 'ths' in start: th0 = start['ths']
        elif 'E' in start: th0 = th_from_E(e, start['E'] * D2R) * R2D
        elif 'M' in start: th0 = th_from_E(e, kepler_E(np.mod(start['M'] * D2R + np.pi, 2 * np.pi) - np.pi, e)) * R2D
        else: raise ValueError('start must give ths, M or E')
    else:
        if 'ths' not in start: raise ValueError('hyperbola: give theta*')
        th0 = start['ths']; n = np.sqrt(mu / abs(a) ** 3); P = None
    r0 = p / (1 + e * np.cos(th0 * D2R)); h = np.sqrt(mu * p)
    th1 = propagate(mu, a, e, th0, dt_s); r1 = p / (1 + e * np.cos(th1 * D2R))
    v0 = np.sqrt(mu * (2 / r0 - 1 / a)); v1 = np.sqrt(mu * (2 / r1 - 1 / a))
    g0, g1 = float(gamma_of(e, th0)), float(gamma_of(e, th1))
    res.check(f'θ* via half-angle atan2 forms (no arccos): θ*₀ = {th0:.4f}°, θ*₁ = {th1:.4f}°')
    if abs(th0) > 180 or (not ell and abs(th0) > np.degrees(np.arccos(-1 / e))):
        res.warn('initial θ* is outside the valid range')

    g = 'Initial state'
    res.add('Semi-latus rectum', 'p', p, KM, 'p = a(1−e²)', group=g)
    if ell: res.add('Period', 'P', P / 3600, HR, 'P = 2π√(a³/μ)', group=g); res.add('Mean motion', 'n', n, 's⁻¹', group=g)
    res.add('True anomaly', 'θ*₀', wrap360(th0) if ell else th0, DEG, group=g)
    res.add('Radius', 'r₀', r0, KM, group=g); res.add('Speed', 'v₀', v0, KMS, 'v = √(μ(2/r − 1/a))', group=g)
    res.add('Flight-path angle', 'γ₀', g0, DEG, 'tanγ = e sinθ*/(1+e cosθ*)', group=g)
    t0 = time_since_periapsis(mu, a, e, th0); t1 = time_since_periapsis(mu, a, e, th1)
    if ell:
        E0 = E_from_th(e, th0 * D2R); E1w = E_from_th(e, th1 * D2R); M0 = E0 - e * np.sin(E0); M1u = M0 + n * dt_s
        E1w2 = kepler_E(np.mod(M1u + np.pi, 2 * np.pi) - np.pi, e)
        k = round((M1u - (E1w2 - e * np.sin(E1w2))) / (2 * np.pi)); E1u = E1w2 + 2 * np.pi * k; dE = E1u - E0
        res.add('Eccentric anomaly', 'E₀', E0 * R2D, DEG, 'E = 2 atan2(√(1−e) sin θ*/2, √(1+e) cos θ*/2)', group=g)
        res.add('Mean anomaly', 'M₀', M0 * R2D, DEG, 'M = E − e sinE', group=g)
        res.add('t₀ − t_p, (−P/2, P/2]', 't₀−t_p', t0 / 3600, HR, group=g)
        res.add('t₀ − t_p, [0, P)', 't₀−t_p', (t0 % P) / 3600, HR, group=g)
        res.data.update(E0=E0 * R2D, E1=float(E1w * R2D), dE=dE * R2D, M0=M0 * R2D)
    g = 'Final state'
    res.add('Time of flight', 'Δt', dt_s, SEC, group=g); res.add('Time of flight', 'Δt', dt_s / 3600, HR, group=g)
    if ell:
        res.add('Mean anomaly', 'M₁', ((M1u * R2D) % 360), DEG, 'M₁ = M₀ + nΔt', group=g)
        res.add('Eccentric anomaly', 'E₁', E1w * R2D, DEG, 'Newton: E − e sinE = M', group=g)
        res.add('t₁ − t_p, (−P/2, P/2]', 't₁−t_p', t1 / 3600, HR, group=g)
        res.add('t₁ − t_p, [0, P)', 't₁−t_p', (t1 % P) / 3600, HR, group=g)
    else:
        H1 = H_from_th(e, th1 * D2R); res.add('Hyperbolic anomaly', 'H₁', H1, 'rad', group=g)
        res.add('t₁ − t_p', 't₁−t_p', t1 / 3600, HR, group=g)
    res.add('True anomaly', 'θ*₁', wrap360(th1) if ell else th1, DEG, 'via E (half-angle atan2)', group=g)
    res.add('Radius', 'r₁', r1, KM, group=g); res.add('Speed', 'v₁', v1, KMS, group=g)
    res.add('Flight-path angle', 'γ₁', g1, DEG, group=g)

    # f and g
    g = 'f and g'
    dth = (th1 - th0) % 360
    r0v = r0 * np.array([np.cos(th0 * D2R), np.sin(th0 * D2R)]); v0v = mu / h * np.array([-np.sin(th0 * D2R), e + np.cos(th0 * D2R)])
    f_t, g_t, fd_t, gd_t, r_t = fg_theta(mu, p, r0v, v0v, dth)
    res.add('Δθ*', 'Δθ*', dth, DEG, 'θ*₁ − θ*₀ (mod 360°)', group=g)
    res.add('f (Δθ* form)', 'f', f_t, NONE, 'f = 1 − (r/p)(1 − cosΔθ*)', group=g)
    res.add('g (Δθ* form)', 'g', g_t, SEC, 'g = r r₀ sinΔθ*/h', group=g)
    res.add('ḟ (Δθ* form)', 'ḟ', fd_t, 's⁻¹', group=g); res.add('ġ (Δθ* form)', 'ġ', gd_t, NONE, 'ġ = 1 − (r₀/p)(1 − cosΔθ*)', group=g)
    if ell:
        f_e, g_e, fdg = fg_E(mu, a, r0, dE, dt_s); fd_e, gd_e = fdg(r1)
        res.add('ΔE', 'ΔE', dE * R2D, DEG, 'E₁ − E₀ (including whole revolutions)', group=g)
        res.add('f (ΔE form)', 'f', f_e, NONE, 'f = 1 − (a/r₀)(1 − cosΔE)', group=g)
        res.add('g (ΔE form)', 'g', g_e, SEC, 'g = Δt − √(a³/μ)(ΔE − sinΔE)', group=g)
        res.add('ḟ (ΔE form)', 'ḟ', fd_e, 's⁻¹', 'ḟ = −√(μa) sinΔE/(r r₀)', group=g)
        res.add('ġ (ΔE form)', 'ġ', gd_e, NONE, 'ġ = 1 − (a/r)(1 − cosΔE)', group=g)
        res.data.update(f=f_e, g=g_e, fd=fd_e, gd=gd_e)
        agree = max(abs(f_t - f_e), abs(gd_t - gd_e)) < 1e-8 and abs(g_t - g_e) < 1e-4 * max(1, abs(g_e))
        res.check('f, g, ḟ, ġ agree between the Δθ* and ΔE forms' if agree else 'WARNING: Δθ* and ΔE forms disagree')
        if not agree: res.warn('f/g forms disagree — check inputs')
        res.data.update(dE_form_agrees=bool(agree))
    else:
        res.data.update(f=f_t, g=g_t, fd=fd_t, gd=gd_t); res.warn('ΔE form of f and g applies to ellipses only; shown the Δθ* form')
    r1v = f_t * r0v + g_t * v0v
    res.add('r̄₁ via f,g (ê,p̂)', 'r̄₁', r1v, KM, 'r̄₁ = f r̄₀ + g v̄₀', group=g)
    v1v = fd_t * r0v + gd_t * v0v; res.add('v̄₁ via ḟ,ġ (ê,p̂)', 'v̄₁', v1v, KMS, 'v̄₁ = ḟ r̄₀ + ġ v̄₀', group=g)
    res.data.update(tof_s=dt_s, p=p, th0=th0, th1=th1, r0=r0, r1=r1, v0=v0, v1=v1, gamma0=g0, gamma1=g1, t0=t0, t1=t1, P=P)

    # ----- scene -----
    ref = a * (1 + e) if ell else max(r0, r1) * 1.1
    orb = Orbit('orbit', p, e, Rz(0), 'orbit', rmax=None if ell else 1.4 * ref)
    sc = Scene(f'Δt = {dt_s / 3600:.4g} h', label); sc.orbits.append(orb)
    sc.disks.append(Disk(np.zeros(3), body_R, '', body=body_name)) if body_R else None
    sc.pts.append(Pt(np.zeros(3), f'F ({body_name})' if body_name else 'F', 'ink', 'o', 5))
    arcseg = (th0, th0 + dth if dt_s >= 0 else th0 - dth) if ell else (th0, th1)
    if dt_s >= 0 and ell and abs(dt_s) > P: arcseg = (th0, th0 + 359.9)
    seg = Orbit(f'{abs(dt_s) / 3600:.4g} h arc', p, e, Rz(0), 'orbit2', ths_range=(min(arcseg), max(arcseg)) if ell else arcseg,
                label_ths=None)
    seg.name = ''; sc.orbits.append(seg)
    P0, P1 = orb.pos(th0), orb.pos(th1)
    apsides_line(sc, orb)
    unit_triad(sc, np.zeros(3), Rz(0), ('ê', 'p̂', 'ĥ'), 0.16 * ref)
    sc.pts.append(Pt(P0, 'P₀  (θ*₀ = %.2f°)' % (wrap360(th0) if ell else th0), 'ink', 'o', 6))
    sc.pts.append(Pt(P1, 'P₁  (θ*₁ = %.2f°)' % (wrap360(th1) if ell else th1), 'ink', 's', 6))
    vector(sc, np.zeros(3), P0, 'r̄₀', 'vector'); vector(sc, np.zeros(3), P1, 'r̄₁', 'orbit3')
    signed_arc(sc, np.zeros(3), unit(P0), unit(P1), dth if dt_s >= 0 else -dth, 0.20 * ref, f'Δθ* = {dth:.2f}°', 'ink')
    if ell:
        aux_circle(sc, orb)
        Cc = np.array([-a * e, 0, 0])
        for E_, nm in ((E0, 'E₀'), (E1w, 'E₁')):
            Q_ = Cc + a * np.array([np.cos(E_), np.sin(E_), 0]); Pp = orb.pos(E_to_th(e, E_))
            sc.pts.append(Pt(Q_, nm, 'muted', 'o', 5)); sc.lines.append(Line(Q_, Pp, '', 'muted', True, 1.0))
            sc.lines.append(Line(Cc, Q_, '', 'muted', False, 0.8))
        signed_arc(sc, Cc, np.array([1.0, 0, 0]), unit(Cc + a * np.array([np.cos(E0), np.sin(E0), 0]) - Cc), E0 * R2D, 0.30 * a, 'E₀', 'muted')
        signed_arc(sc, Cc, np.array([1.0, 0, 0]), unit(a * np.array([np.cos(E1w), np.sin(E1w), 0])), E1w * R2D, 0.42 * a, 'E₁', 'muted')
        sc.pts.append(Pt(Cc, 'C', 'muted', '+', 5))
    trk, dur = orbit_track(mu, orb, th0, None if ell else -th0, 'spacecraft')
    if not ell:
        lim = np.degrees(np.arccos(max(-1.0, min(1.0, (p / orb.rmax - 1) / e)))); trk, dur = orbit_track(mu, orb, -lim, lim, 'spacecraft')
    sc.tracks.append(trk); sc.duration_s = dur; res.scene = sc

    def fig_r(theme='light', user=''):
        T = THEMES[theme]; fig, axs = plt.subplots(1, 3, figsize=(11, 3.2), facecolor=T['surface'])
        th = np.linspace(-180, 180, 721); r = p / (1 + e * np.cos(th * D2R)) if ell else None
        if ell:
            E = np.linspace(-180, 180, 721); Mg = np.linspace(-180, 180, 721)
            Ek = Mg * D2R; thM = th_from_E(e, np.array([kepler_E(m * D2R, e) for m in Mg]))
            xs = [(th, r), (E, a * (1 - e * np.cos(E * D2R))), (Mg, p / (1 + e * np.cos(thM)))]
            labs = ['θ* (°)', 'E (°)', 'M (°)']; marks = [(th0, th1), (E0 * R2D, E1w * R2D), ((M0 * R2D + 180) % 360 - 180, (M1u * R2D + 180) % 360 - 180)]
            rr = [(r0, r1)] * 3; del Ek
        else:
            th = np.linspace(-np.degrees(np.arccos(-1 / e)) + 1, np.degrees(np.arccos(-1 / e)) - 1, 721)
            xs = [(th, p / (1 + e * np.cos(th * D2R)))]; labs = ['θ* (°)']; marks = [(th0, th1)]; rr = [(r0, r1)]; axs = [axs[0]]
        for ax, (x, y), lb, mk, rv in zip(axs, xs, labs, marks, rr):
            ax.set_facecolor(T['surface']); ax.plot(x, y, color=T['series'][0], lw=1.8); ax.grid(True, color=T['grid'], lw=0.6)
            ax.plot(mk, rv, 'o', color=T['series'][1], ms=7, mec=T['surface'])
            ax.set_xlabel(lb, color=T['ink2']); ax.set_ylabel('r (km)', color=T['ink2']); ax.tick_params(colors=T['muted'], labelsize=8)
            for s in ax.spines.values(): s.set_color(T['axis'])
        fig.suptitle(f'{user + " — " if user else ""}{label}: r vs θ*, E, M', color=T['ink'], fontsize=11, x=0.01, ha='left')
        fig.tight_layout(); return fig

    res.figs['r vs θ*, E, M'] = fig_r
    return res


def E_to_th(e, E):
    return th_from_E(e, E) * R2D
