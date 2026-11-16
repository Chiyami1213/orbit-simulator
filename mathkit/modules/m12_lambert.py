"""Module 12 - Lambert and two-position problems (HW10 P1-P3, HW11, Exam 2 P2).

Position input: 'radii' (r1, r2, TA), 'vectors' (3-D r1, r2) or 'radec' (RA, Dec, distance for each end).
Time input    : 'tof' (general), 'minE' (minimum energy) or 'p' (semi-latus rectum given).
Departure/arrival Delta-v are measured against circular, prograde, in-plane orbits at r1 and r2 (core.lambert_velocities)
unless explicit 3-D old/target velocities are supplied.
"""
from __future__ import annotations
import numpy as np
from ..core.constants import D2R, R2D, wrap360, wrap180
from ..core.lambert import lambert_velocities, lambert_minE, two_vector_transfer
from ..core.lambert import lambert as lambert_gen
from ..core.kepler import time_since_periapsis
from ..core.elements import elements_from_rv
from ..core.frames import dcm_313
from ..results import Result, KM, KMS, DEG, SEC, HR, DAY, NONE, EPS, HU
from ..scene import (Scene, Orbit, Disk, Pt, Line, vector, local_horizon, angle_arc, apsides_line, vacant_focus, nodes_line,
                     equatorial_plane, unit_triad, Rz, unit)
from .common import vel_scale, orbit_track, clean360
from .m03_conic import signed_arc, Z


def radec_to_vec(ra_deg: float, dec_deg: float, dist: float) -> np.ndarray:
    a, d = ra_deg * D2R, dec_deg * D2R
    return dist * np.array([np.cos(d) * np.cos(a), np.cos(d) * np.sin(a), np.sin(d)])


def _ae_from_p(mu, r1, vD, p):
    eps = 0.5 * float(vD @ vD) - mu / r1
    a = -mu / (2 * eps) if abs(eps) > 1e-14 else np.inf
    e = np.sqrt(max(0.0, 1 - p / a)) if a > 0 else np.sqrt(1 + p / -a)
    return a, e, eps


def solve(mu: float, pos: dict, timing: dict, root: str = 'small', body_R: float | None = None, body_name: str = '',
          perihelion_body_R: float | None = None, n_target: float | None = None, vD_old=None, vA_target=None,
          hz_positive: bool = True, label: str = 'Module 12') -> Result:
    """pos: {'kind':'radii','r1','r2','TA'} | {'kind':'vectors','r1','r2'} | {'kind':'radec','ra1','dec1','d1','ra2','dec2','d2'}.
    timing: {'mode':'tof','tof_s'} | {'mode':'minE'} | {'mode':'p','p'}.  n_target: mean motion (s^-1) of the target body
    at r2 for the phase angle psi = TA - n2*TOF (default: circular at r2)."""
    res = Result('Lambert / two-position transfer', label, inputs=dict(mu=mu, pos=pos, timing=timing, root=root))
    three_d = pos['kind'] in ('vectors', 'radec')
    if pos['kind'] == 'radii':
        r1, r2, TA = pos['r1'], pos['r2'], pos['TA']; Qp = np.eye(3); r1v = r1 * np.array([1.0, 0, 0]); r2v = r2 * np.array([np.cos(TA * D2R), np.sin(TA * D2R), 0])
        hh = np.array([0, 0, 1.0])
    else:
        r1v = np.asarray(pos['r1'], float) if pos['kind'] == 'vectors' else radec_to_vec(pos['ra1'], pos['dec1'], pos['d1'])
        r2v = np.asarray(pos['r2'], float) if pos['kind'] == 'vectors' else radec_to_vec(pos['ra2'], pos['dec2'], pos['d2'])
        r1, r2 = np.linalg.norm(r1v), np.linalg.norm(r2v)
        T0 = two_vector_transfer(mu, r1v, r2v, 0.5 * (r1 + r2), hz_positive); TA = T0['TA']
        hv = np.cross(r1v, r2v); hv = hv if (hv[2] > 0) == hz_positive else -hv; hh = unit(hv)
        res.check(f'transfer plane normal ĥ = r̄₁×r̄₂/|r̄₁×r̄₂| chosen with ĥ·ẑ {"> 0" if hz_positive else "< 0"}; TA = {TA:.4f}° from cosTA = r̄₁·r̄₂/(r₁r₂) with the 2π − TA branch when ĥ was flipped')
    Qp = np.column_stack([unit(r1v), np.cross(hh, unit(r1v)), hh])
    mode = timing['mode']; tof_in = timing.get('tof_s')
    g = 'Geometry'
    res.add('Departure radius', 'r₁', r1, KM, group=g); res.add('Arrival radius', 'r₂', r2, KM, group=g); res.add('Transfer angle', 'TA', TA, DEG, group=g)
    res.add('Transfer type', 'type', 1 if TA < 180 else 2, NONE, 'type 1 if TA < 180°, type 2 if TA > 180°', group=g)
    if three_d:
        res.add('r̄₁', 'r̄₁', r1v, KM, group=g); res.add('r̄₂', 'r̄₂', r2v, KM, group=g)
        res.add('Transfer-plane inclination', 'i', np.degrees(np.arccos(np.clip(hh[2], -1, 1))), DEG, 'cos i = ĥ_z', group=g)
        res.add('Transfer-plane Ω', 'Ω', clean360(np.degrees(np.arctan2(hh[0], -hh[1]))), DEG, 'Ω = atan2(ĥ_x, −ĥ_y)', group=g)

    def per_root(d, tag):
        g = f'Transfer{tag}'
        if 'tof' in d and d.get('cls'):
            pass
        res.add('Orbit class', 'class', d.get('cls', '—'), NONE, group=g)
        for k, sym, nm, u in (('a', 'a', 'Semi-major axis', KM), ('p', 'p', 'Semi-latus rectum', KM), ('e', 'e', 'Eccentricity', NONE)):
            res.add(nm, sym, d[k], u, group=g)
        if 'alpha' in d: res.add('α (Lambert)', 'α', d['alpha'], DEG, group=g); res.add('β (Lambert)', 'β', d['beta'], DEG, group=g)
        res.add('Angular momentum', 'h', np.sqrt(mu * d['p']), HU, 'h = √(μp)', group=g)
        res.add('f', 'f', d['f'], NONE, group=g); res.add('g', 'g', d['g'], SEC, group=g); res.add('ḟ', 'ḟ', d['fd'], 's⁻¹', group=g); res.add('ġ', 'ġ', d['gd'], NONE, group=g)
        res.add('Departure speed', 'v_D', d['vD_mag'], KMS, group=g); res.add('Arrival speed', 'v_A', d['vA_mag'], KMS, group=g)
        res.add('v̄_D (plane: r̂₁, ĥ×r̂₁)', 'v̄_D', d['vD'], KMS, 'v̄_D = (r̄₂ − f r̄₁)/g', group=g); res.add('v̄_A (plane)', 'v̄_A', d['vA'], KMS, 'v̄_A = ḟ r̄₁ + ġ v̄_D', group=g)
        res.add('θ*_D', 'θ*_D', d['thD'], DEG, 'atan2(ṙ h/μ, p/r − 1)', group=g); res.add('θ*_A', 'θ*_A', d['thA'], DEG, group=g)
        res.add('γ_D', 'γ_D', d['gD'], DEG, group=g); res.add('γ_A', 'γ_A', d['gA'], DEG, group=g)
        a_, e_ = d['a'], d['e']
        rp = d['p'] / (1 + e_); res.add('Periapsis radius', 'r_p', rp, KM, group=g)
        thD = d['thD']; thA = thD + TA; passes = (thD < 0 < thA) or (thD < 360 < thA)
        res.add('Passes periapsis during the transfer?', 'periapsis?', 'yes' if passes else 'no', NONE, f'θ* sweeps {thD:.2f}° → {thA:.2f}°', group=g)
        d['passes_periapsis'] = bool(passes)
        if body_R and rp < body_R: res.warn(f'{tag.strip() or "transfer"}: r_p = {rp:,.1f} km is below the surface ({body_R:,.1f} km)')
        if perihelion_body_R is not None and passes and rp < perihelion_body_R: res.warn(f'{tag.strip() or "transfer"}: perihelion {rp:,.1f} km is inside the body at {perihelion_body_R:,.1f} km')
        if vD_old is None:
            res.add('Δv_D', 'Δv_D', d['dvD_mag'], KMS, 'v̄_D − v̄_circ,1', group=g); res.add('α_D (from v̄⁻)', 'α_D', d['alphaD'], DEG, 'α from circular velocity; + away from body', group=g)
            res.add('Δv_D along V̂', 'Δv_D,V', d['dvD_mag'] * np.cos(d['alphaD'] * D2R), KMS, group=g); res.add('Δv_D along Ĉ', 'Δv_D,C', d['dvD_mag'] * np.sin(d['alphaD'] * D2R), KMS, group=g)
            res.add('Δv_D along B̂ = −Ĉ', 'Δv_D,B', -d['dvD_mag'] * np.sin(d['alphaD'] * D2R), KMS, group=g)
            res.add('Δv_A', 'Δv_A', d['dvA_mag'], KMS, 'v̄_circ,2 − v̄_A', group=g); res.add('α_A', 'α_A', d['alphaA'], DEG, group=g)
            res.add('Δv_A along V̂, Ĉ', 'Δv_A,VC', [d['dvA_mag'] * np.cos(d['alphaA'] * D2R), d['dvA_mag'] * np.sin(d['alphaA'] * D2R)], KMS, group=g)
            res.add('Total Δv', 'Δv_tot', d['dv_total'], KMS, group=g)

    rows = {}
    if mode == 'minE':
        d = lambert_minE(mu, r1, r2, TA); d['cls'] = f"{d['type']}-min energy"; tof = d['tof']; rows['minE'] = d
        res.add('Minimum-energy TOF', 'TOF_min', tof / 3600, HR, 'α = π, a = s/2', group='Times'); res.add('Chord', 'c', d['c'], KM, group='Times'); res.add('Semiperimeter', 's', d['s'], KM, group='Times')
        per_root(d, ''); sel = d
    elif mode == 'p':
        p = timing['p']; d = lambert_velocities(mu, r1, r2, TA, p); a_, e_, eps = _ae_from_p(mu, r1, d['vD'], p)
        d.update(a=a_, p=p, e=e_, cls='given p'); rows['p'] = d; tof = None
        res.add('Specific energy', 'ε', eps, EPS, group='Transfer'); per_root(d, ''); sel = d
        # TOF from Kepler along the arc
        if a_ > 0 or a_ < 0:
            thD = d['thD']; tof = (time_since_periapsis(mu, a_, e_, thD + TA) - time_since_periapsis(mu, a_, e_, thD))
            if e_ < 1 and tof < 0: tof += 2 * np.pi * np.sqrt(a_ ** 3 / mu)
            res.add('Time of flight', 'TOF', tof / 3600, HR, 'Kepler along the arc θ*_D → θ*_D + TA', group='Times')
    else:
        tof = tof_in
        for rt in ('small', 'large'): rows[rt] = lambert_gen(mu, r1, r2, TA, tof, rt)
        d0 = rows['small']
        res.add('Parabolic TOF (Euler)', 'TOF_par', d0['tof_par'] / 3600, HR, 's^{3/2} ∓ (s−c)^{3/2}', group='Times'); res.add('Minimum-energy TOF', 'TOF_min', d0['tof_min'] / 3600, HR, group='Times')
        res.add('Given TOF', 'TOF', tof / 3600, HR, group='Times'); res.add('Chord', 'c', d0['c'], KM, group='Times'); res.add('Semiperimeter', 's', d0['s'], KM, group='Times')
        res.add('Both p roots', 'p roots', list(d0['p_roots']), KM, '4a(s−r₁)(s−r₂)/c² · sin²((α ± β)/2)', group='Times')
        for rt, tag in (('small', ' — smaller p'), ('large', ' — larger p')): per_root(rows[rt], tag)
        better = min(rows, key=lambda k: rows[k]['dv_total'])
        res.add('Root with the smaller total Δv', 'best root', f'{better} p = {rows[better]["p"]:,.1f} km  (Δv_tot = {rows[better]["dv_total"]:.4f} km/s)', NONE, group='Selected')
        sel = rows[root]
    res.data.update(rows=rows, TA=TA, tof=tof, sel=sel, r1=r1, r2=r2)
    # phase angle at departure
    n2 = n_target if n_target is not None else np.sqrt(mu / r2 ** 3)
    if tof: res.add('Target phase angle at departure', 'ψ', (TA - np.degrees(n2 * tof)), DEG, 'ψ = TA − n₂·TOF', group='Times'); res.data['psi'] = TA - np.degrees(n2 * tof)

    # 3-D transfer elements
    p_sel = sel['p']
    if three_d:
        T = two_vector_transfer(mu, r1v, r2v, p_sel, hz_positive); el = T['el']
        res.add('Transfer i', 'i_t', el['inc'], DEG, group='Transfer plane'); res.add('Transfer Ω', 'Ω_t', clean360(el['Om']), DEG, group='Transfer plane')
        res.add('Transfer ω', 'ω_t', clean360(el['om']), DEG, 'ω = θ − θ*', group='Transfer plane')
        res.add('v̄_D (x̂ŷẑ)', 'v̄_D,xyz', T['v1'], KMS, 'v̄₁ = (r̄₂ − f r̄₁)/g', group='Transfer plane')
        v2 = (sel['fd'] * r1v + sel['gd'] * T['v1']); res.add('v̄_A (x̂ŷẑ)', 'v̄_A,xyz', v2, KMS, 'v̄₂ = ḟ r̄₁ + ġ v̄₁', group='Transfer plane')
        res.data.update(T=T, v1_xyz=T['v1'], v2_xyz=v2)
        for nm, vo, vt_ in (('departure', vD_old, T['v1']), ('arrival', vA_target, v2)):
            pass
        if vD_old is not None:
            dv = T['v1'] - np.asarray(vD_old, float); res.add('Δv̄_D (x̂ŷẑ)', 'Δv̄_D', dv, KMS, group='Maneuvers'); res.add('|Δv̄_D|', 'Δv_D', np.linalg.norm(dv), KMS, group='Maneuvers')
        if vA_target is not None:
            dv = np.asarray(vA_target, float) - v2; res.add('Δv̄_A (x̂ŷẑ)', 'Δv̄_A', dv, KMS, group='Maneuvers'); res.add('|Δv̄_A|', 'Δv_A', np.linalg.norm(dv), KMS, group='Maneuvers')

    # ---------------- scene ----------------
    a_, e_, thD = sel['a'], sel['e'], sel['thD']
    ref = max(r1, r2) * (1.3 if e_ < 1 and a_ < 5 * max(r1, r2) else 1.2) if e_ >= 1 else max(sel['p'] / (1 - e_), r1, r2)
    Qo = Qp @ Rz(-thD)
    orb = Orbit('transfer conic', sel['p'], e_, Qo, 'transfer', dash=True, rmax=1.5 * max(r1, r2))
    arc_ = Orbit(f'transfer arc (TA = {TA:.2f}°)', sel['p'], e_, Qo, 'transfer', ths_range=(thD, thD + TA))
    c1 = Orbit('departure orbit', r1, 0.0, Qp, 'orbit'); c2 = Orbit('arrival orbit', r2, 0.0, Qp, 'orbit2')
    sc = Scene(f'{sel.get("cls", "")} transfer, TA = {TA:.2f}°', label, is3d=three_d); sc.orbits += [c1, c2, orb, arc_]
    orb.name = ''; arc_.label_ths = thD + TA / 2
    if body_R: sc.disks.append(Disk(np.zeros(3), body_R, '', body=body_name))
    sc.pts.append(Pt(np.zeros(3), f'F ({body_name})' if body_name else 'F', 'ink', 'o', 5))
    Pd, Pa = r1v, r2v
    sc.pts.append(Pt(Pd, 'D (departure)', 'ink', 'o', 7)); sc.pts.append(Pt(Pa, 'A (arrival)', 'ink', 's', 7))
    vector(sc, np.zeros(3), Pd, 'r̄₁', 'vector'); vector(sc, np.zeros(3), Pa, 'r̄₂', 'orbit2')
    sc.pts.append(Pt(Qo @ np.array([-2 * a_ * e_, 0, 0]), 'vacant focus F*', 'ink2', 'x', 8)) if (e_ < 1 or a_ < 0) else None
    apsides_line(sc, orb)
    vs = vel_scale(ref, max(sel['vD_mag'], sel['vA_mag']), 0.2)
    vDv = Qp @ np.array([sel['vD'][0], sel['vD'][1], 0.0]); vAv = Qp @ np.array([sel['vA'][0], sel['vA'][1], 0.0])
    vector(sc, Pd, vDv, f"v̄_D ({sel['vD_mag']:.4g} km/s)", 'vel', scale=vs); vector(sc, Pa, vAv, f"v̄_A ({sel['vA_mag']:.4g} km/s)", 'vel', scale=vs)
    local_horizon(sc, Pd, hh, 0.2 * ref, 'local horizon'); local_horizon(sc, Pa, hh, 0.2 * ref, '')
    if vD_old is None:
        dvD = Qp @ np.array([sel['dvD'][0], sel['dvD'][1], 0.0]); dvA = Qp @ np.array([sel['dvA'][0], sel['dvA'][1], 0.0])
        vector(sc, Pd + vDv * vs - dvD * vs, dvD, f"Δv̄_D ({sel['dvD_mag']:.4g}), α = {sel['alphaD']:+.1f}°", 'dv', scale=vs)
        vector(sc, Pa + vAv * vs, dvA, f"Δv̄_A ({sel['dvA_mag']:.4g}), α = {sel['alphaA']:+.1f}°", 'good', scale=vs)
    angle_arc(sc, np.zeros(3), unit(Pd), unit(Pa), 0.18 * ref, f'TA = {TA:.2f}°', 'ink', hh)
    sc.plane2d = (Qp[:, 0], Qp[:, 1])
    if three_d:
        equatorial_plane(sc, 1.1 * max(r1, r2)); Om_t = np.degrees(np.arctan2(hh[0], -hh[1]))
        if np.linalg.norm(hh[:2]) > 1e-9: nodes_line(sc, Om_t, 1.1 * max(r1, r2))
    if e_ < 1 and tof:
        trk, dur = orbit_track(mu, Orbit('', sel['p'], e_, Qo), thD, None, 'spacecraft'); sc.tracks.append(trk); sc.duration_s = dur
    res.scene = sc
    return res
