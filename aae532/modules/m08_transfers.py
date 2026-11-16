"""Module 8 - coplanar transfers and rendezvous (HW7 P3, HW8 P2, HW10 P2a, P3a).

Hohmann and bi-elliptic transfers between circular orbits r1 -> r2 (optional r_b). For an eccentric target
(``target_e`` and ``target_a``) the transfer arrives at the target's perihelion (or aphelion) and the arrival impulse uses the
target's ACTUAL speed there (not the circular speed).
"""
from __future__ import annotations
import numpy as np
from ..core.constants import D2R, R2D, wrap360
from ..core.transfers import hohmann, bielliptic
from ..core.kepler import propagate
from ..core.conic import gamma_of
from ..results import Result, KM, KMS, DEG, SEC, HR, DAY, YR, NONE
from ..scene import Scene, Orbit, Disk, Pt, Track, Line, vector, angle_arc, apsides_line, Rz, unit
from .common import vel_scale

YEAR_S = 365.25 * 86400


def _hr_day_yr(res, name, sym, t_s, g, eq=''):
    res.add(name, sym, t_s, SEC, eq, group=g); res.add(name, sym, t_s / 3600, HR, group=g); res.add(name, sym, t_s / 86400, DAY, group=g)
    if t_s > 365.25 * 86400 * 0.5: res.add(name, sym, t_s / YEAR_S, YR, '(Julian year = 365.25 d)', group=g)


def solve(mu: float, r1: float, r2: float, rb: float | None = None, target_e: float = 0.0, target_a: float | None = None,
          arrive_at: str = 'perihelion', body_R: float | None = None, body_name: str = '', label: str = 'Module 8') -> Result:
    res = Result('Coplanar transfer / rendezvous', label, inputs=dict(mu=mu, r1=r1, r2=r2, rb=rb, target_e=target_e, target_a=target_a))
    ecc_target = target_e > 0 and target_a is not None
    if ecc_target:
        r2_arr = target_a * (1 - target_e) if arrive_at == 'perihelion' else target_a * (1 + target_e)
        v_target = np.sqrt(mu * (2 / r2_arr - 1 / target_a))
        res.check(f'eccentric target: arrive at {arrive_at}, r = a(1 ∓ e) = {r2_arr:,.1f} km; target speed there v = √(μ(2/r − 1/a)) = {v_target:.4f} km/s (NOT the circular speed {np.sqrt(mu / r2_arr):.4f})')
    else:
        r2_arr = r2; v_target = None
    h = hohmann(mu, r1, r2_arr); dv2 = h['dv2']
    if ecc_target: dv2 = abs(v_target - h['va'])
    g = 'Hohmann'
    res.add('Transfer semi-major axis', 'a_T', h['aT'], KM, 'a_T = (r₁ + r₂)/2', group=g); res.add('Transfer eccentricity', 'e_T', h['eT'], NONE, group=g)
    res.add('Circular speed at r₁', 'v_c1', h['vc1'], KMS, group=g); res.add('Transfer speed at departure', 'v_p', h['vp'], KMS, group=g)
    res.add('Transfer speed at arrival', 'v_a', h['va'], KMS, group=g)
    if ecc_target: res.add('Target speed at arrival', 'v_target', v_target, KMS, 'v = √(μ(2/r − 1/a_target))', group=g)
    else: res.add('Circular speed at r₂', 'v_c2', h['vc2'], KMS, group=g)
    res.add('Departure impulse', 'Δv₁', h['dv1'], KMS, 'Δv₁ = |v_p − v_c1|', group=g); res.add('Arrival impulse', 'Δv₂', dv2, KMS, 'Δv₂ = |v_target − v_a|', group=g)
    res.add('Total Δv', 'Δv', h['dv1'] + dv2, KMS, group=g)
    _hr_day_yr(res, 'Time of flight', 'TOF', h['tof'], g, 'TOF = π√(a_T³/μ)')
    n2 = np.sqrt(mu / r2_arr ** 3)
    res.add('Transfer angle', 'TA', 180.0, DEG, group=g)
    res.add('Phase angle at departure (target ahead)', 'φ', h['phase'], DEG, 'φ = 180° − n₂·TOF', group=g)
    res.add('Synodic period', 'T_syn', h['synodic'], SEC, 'T_syn = 2π/|n₁ − n₂|', group=g); _hr_day_yr(res, 'Synodic period', 'T_syn', h['synodic'], g)
    res.data.update(hohmann=h, dv2=dv2, dv_total=h['dv1'] + dv2, v_target=v_target, r2_arr=r2_arr)
    if rb:
        b = bielliptic(mu, r1, r2_arr, rb); g = 'Bi-elliptic'
        res.add('Impulse 1', 'Δv₁', b['dv1'], KMS, group=g); res.add('Impulse 2', 'Δv₂', b['dv2'], KMS, group=g); res.add('Impulse 3', 'Δv₃', b['dv3'], KMS, group=g)
        res.add('Total Δv', 'Δv', b['dv'], KMS, group=g); _hr_day_yr(res, 'Time of flight', 'TOF', b['tof'], g)
        res.add('Phase angle at departure', 'φ_bi', (2 * np.pi - n2 * b['tof']) * R2D % 360, DEG, 'φ = 360° − n₂·TOF (mod 360°)', group=g)
        res.add('Cheaper than Hohmann?', '', 'bi-elliptic' if b['dv'] < h['dv1'] + dv2 else 'Hohmann', NONE, group=g)
        res.data['bielliptic'] = b
    # ---------------- scene ----------------
    ext = max(r1, r2_arr, rb or 0)
    sc = Scene('Hohmann transfer' + (' and bi-elliptic' if rb else ''), label); sc.focus_name = body_name
    if body_R: sc.disks.append(Disk(np.zeros(3), body_R, ''))
    sc.pts.append(Pt(np.zeros(3), f'F ({body_name})' if body_name else 'F', 'ink', 'o', 5))
    sc.orbits.append(Orbit('departure orbit', r1, 0.0, Rz(0), 'orbit'))
    if ecc_target:
        tgt = Orbit('target orbit', target_a * (1 - target_e ** 2), target_e, Rz(180 if arrive_at == 'perihelion' else 0), 'orbit2'); sc.orbits.append(tgt)
    else:
        sc.orbits.append(Orbit('target orbit', r2, 0.0, Rz(0), 'orbit2'))
    T = Orbit('Hohmann transfer', (lambda a_, e_: a_ * (1 - e_ ** 2))(h['aT'], h['eT']), h['eT'], Rz(0), 'transfer', ths_range=(0, 180))
    sc.orbits.append(T)
    if rb:
        b = res.data['bielliptic']
        sc.orbits.append(Orbit('bi-elliptic leg 1', b['a1'] * (1 - ((rb - r1) / (rb + r1)) ** 2), (rb - r1) / (rb + r1), Rz(0), 'accent', ths_range=(0, 180), dash=True))
        sc.orbits.append(Orbit('bi-elliptic leg 2', b['a2'] * (1 - ((rb - r2_arr) / (rb + r2_arr)) ** 2), (rb - r2_arr) / (rb + r2_arr), Rz(180), 'accent', ths_range=(0, 180), dash=True))
    # positions at departure (t = 0): departure body on the x axis, target ahead by phase angle; at arrival target at 180 deg
    phi = h['phase']; Pdep = np.array([r1, 0, 0]); Ptar = r2_arr * np.array([np.cos(phi * D2R), np.sin(phi * D2R), 0]); Parr = np.array([-r2_arr, 0, 0])
    pt_tar = Pt(Ptar, 'target at departure', 'target', 'o', 7)
    sc.pts += [Pt(Pdep, 'departure point', 'ink', 'o', 7), pt_tar, Pt(Parr, 'arrival point', 'ink', 's', 7)]
    angle_arc(sc, np.zeros(3), np.array([1.0, 0, 0]), unit(Ptar), 0.3 * ext, f'phase angle φ = {phi:.2f}°', 'ink', np.array([0, 0, 1.0]))
    vs = vel_scale(ext, h['vp'], 0.18)
    vector(sc, Pdep, np.array([0, h['dv1'], 0]), f"Δv₁ = {h['dv1']:.4g} km/s", 'dv', scale=vs * 1.0)
    vector(sc, Parr, np.array([0, -dv2, 0]) if True else None, f'Δv₂ = {dv2:.4g} km/s', 'dv', scale=vs)
    apsides_line(sc, T)
    # animation: spacecraft on the transfer, target body moving (and the departure body, to show the angle closing)
    TOF = h['tof']; aT, eT = h['aT'], h['eT']; p_T = aT * (1 - eT ** 2); n1 = np.sqrt(mu / r1 ** 3)

    def sc_pos(t): return T.pos(propagate(mu, aT, eT, 0.0, t))

    def sc_state(t):
        th = propagate(mu, aT, eT, 0.0, t); r = float(T.r(th)); return dict(t=t, r=r, v=float(np.sqrt(mu * (2 / r - 1 / aT))), gamma=float(gamma_of(eT, th)), ths=float(wrap360(th)))
    sc.tracks.append(Track('spacecraft', sc_pos, 'transfer', sc_state))
    if ecc_target:
        th_arr = 0.0 if arrive_at == 'perihelion' else 180.0          # target true anomaly at the arrival instant
        tgt_pos = lambda t: tgt.pos(propagate(mu, target_a, target_e, th_arr, t - TOF))
        p0 = tgt_pos(0.0); phi_ecc = float(np.degrees(np.arctan2(p0[1], p0[0])) % 360)
        res.add('Phase angle at departure, actual eccentric target', 'φ_ecc', phi_ecc, DEG, 'inertial angle of the target at t = 0 so that it reaches the arrival point at t = TOF', group='Hohmann')
        res.data['phi_ecc'] = phi_ecc
        pt_tar.pos = p0; sc.arcs[0].w = unit(p0); sc.arcs[0].label = f'phase angle φ = {phi_ecc:.2f}° (actual target)'
    else:
        tgt_pos = lambda t: r2_arr * np.array([np.cos(phi * D2R + n2 * t), np.sin(phi * D2R + n2 * t), 0])
    sc.tracks.append(Track('target body', tgt_pos, 'target'))
    sc.tracks.append(Track('departure body', lambda t: r1 * np.array([np.cos(n1 * t), np.sin(n1 * t), 0]), 'orbit', trail=False))
    sc.duration_s = TOF
    res.scene = sc
    return res
