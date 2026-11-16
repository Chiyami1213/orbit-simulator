"""Module 7 - single-impulse maneuvers (HW6 P2, HW7 P1-P2, Exam 2 P1).

(a) solve_target : coplanar target conic (rotated by d_omega) -> every intersection, minimum |dv| chosen.
(b) solve_given  : dv, alpha, beta at theta* -> new orbit (3-D, VNC).

alpha is measured from v-; alpha > 0 when the impulse turns v away from the central body (toward C-hat = V x N);
%energy = |v+ - v-|/|dv| x 100, %direction = 100 - %energy (HW6 P2).
"""
from __future__ import annotations
import numpy as np
from ..core.constants import D2R, R2D, wrap360, wrap180
from ..core.kepler import time_since_periapsis
from ..core.conic import gamma_of, v_of, r_of
from ..core.maneuvers import impulse_planar, apply_dv_vnc, intersect_conics
from ..core.elements import rv_from_elements, elements_from_rv
from ..core.frames import vnc_frame, dcm_313
from ..results import Result, KM, KMS, DEG, SEC, HR, NONE, EPS
from ..scene import (Scene, Orbit, Disk, Pt, vector, local_horizon, angle_arc, apsides_line, nodes_line, unit_triad, Rz, unit, Vec)
from .common import vel_scale, orbit_track, pe_from_spec, clean360
from .m03_conic import signed_arc, Z


def _imp_at(mu, p1, e1, p2, e2, dom, th1):
    a1 = p1 / (1 - e1 ** 2); a2 = p2 / (1 - e2 ** 2); r = r_of(p1, e1, th1); th2 = th1 - dom
    v1 = v_of(mu, r, a1); g1 = float(gamma_of(e1, th1)); v2 = v_of(mu, r, a2); g2 = float(gamma_of(e2, th2))
    imp = impulse_planar(v1, g1, v2, g2)
    imp.update(r=r, v1=v1, g1=g1, v2=v2, g2=g2, th1=th1, th2=th2, pct_energy=abs(v2 - v1) / imp['dv'] * 100 if imp['dv'] > 0 else 0.0)
    imp['pct_dir'] = 100 - imp['pct_energy']
    ang = np.radians(g1); imp['dv_rθ'] = (v2 * np.sin(g2 * D2R) - v1 * np.sin(g1 * D2R), v2 * np.cos(g2 * D2R) - v1 * np.cos(g1 * D2R))
    t = th1 * D2R; dr, dt_ = imp['dv_rθ']
    imp['dv_ep'] = (dr * np.cos(t) - dt_ * np.sin(t), dr * np.sin(t) + dt_ * np.cos(t)); del ang
    return imp


def solve_target(mu: float, orbit1: dict, orbit2: dict, d_omega: float = 0.0, th_now: float | None = None,
                 body_R: float | None = None, body_name: str = '', label: str = 'Module 7a') -> Result:
    """orbit1/orbit2: conic specs (see common.pe_from_spec). d_omega: angle (deg) from orbit-1 ê to orbit-2 ê (ccw).
    th_now: current true anomaly on orbit 1 for the wait time."""
    p1, e1 = pe_from_spec(orbit1); p2, e2 = pe_from_spec(orbit2)
    res = Result('Single impulse to a target orbit', label, inputs=dict(mu=mu, orbit1=orbit1, orbit2=orbit2, d_omega=d_omega, th_now=th_now))
    a1 = p1 / (1 - e1 ** 2); a2 = p2 / (1 - e2 ** 2)
    sols = [180.0 if abs(abs(t) - 180) < 1e-9 else t for t in intersect_conics(p1, e1, p2, e2, d_omega)]   # show apogee as +180°, not −180°
    res.check('intersection from A cosθ* + B sinθ* = C, both roots kept (acos branch is not assumed)')
    if not sols:
        res.warn('the two orbits do not intersect — a single impulse cannot reach the target orbit')
    rows = [_imp_at(mu, p1, e1, p2, e2, d_omega, t) for t in sols]
    best = min(rows, key=lambda d: d['dv']) if rows else None
    P1 = 2 * np.pi * np.sqrt(a1 ** 3 / mu) if e1 < 1 else None
    g = 'Orbits'
    res.add('Old orbit: p, e', 'p₁', p1, KM, group=g); res.add('Old orbit eccentricity', 'e₁', e1, NONE, group=g); res.add('Old a', 'a₁', a1, KM, group=g)
    res.add('Old r_p, r_a', 'r_p1', p1 / (1 + e1), KM, group=g)
    if e1 < 1: res.add('Old r_a', 'r_a1', p1 / (1 - e1), KM, group=g)
    res.add('New p', 'p₂', p2, KM, group=g); res.add('New eccentricity', 'e₂', e2, NONE, group=g); res.add('New a', 'a₂', a2, KM, group=g)
    res.add('New r_p', 'r_p2', p2 / (1 + e2), KM, group=g)
    if e2 < 1: res.add('New r_a', 'r_a2', p2 / (1 - e2), KM, group=g); res.add('New period', 'P₂', 2 * np.pi * np.sqrt(a2 ** 3 / mu) / 3600, HR, group=g)
    res.add('Rotation of line of apsides', 'Δω', d_omega, DEG, 'θ*₂ = θ*₁ − Δω', group=g)

    def emit(k, d, tag):
        g = f'Intersection {k + 1}{tag}'
        res.add('True anomaly on old orbit', 'θ*₁⁻', d['th1'], DEG, group=g); res.add('True anomaly on new orbit', 'θ*₂⁺', wrap180(d['th2']), DEG, 'θ*₂ = θ*₁ − Δω', group=g)
        res.add('Radius', 'r', d['r'], KM, group=g); res.add('Speed before', 'v⁻', d['v1'], KMS, 'v = √(μ(2/r − 1/a))', group=g)
        res.add('Flight-path angle before', 'γ⁻', d['g1'], DEG, group=g); res.add('Speed after', 'v⁺', d['v2'], KMS, group=g); res.add('Flight-path angle after', 'γ⁺', d['g2'], DEG, group=g)
        res.add('Δγ', 'Δγ', d['dgamma'], DEG, 'γ⁺ − γ⁻', group=g)
        res.add('Impulse magnitude', 'Δv', d['dv'], KMS, 'Δv² = v₁² + v₂² − 2v₁v₂cosΔγ', group=g)
        res.add('Impulse angle α (from v̄⁻; + = away from body)', 'α', d['alpha'], DEG, 'α = atan2(Δv·Ĉ, Δv·V̂)', group=g)
        res.add('Δv along V̂ (velocity)', 'Δv_V', d['dV'], KMS, group=g); res.add('Δv along Ĉ (= −B̂)', 'Δv_C', d['dC'], KMS, group=g)
        res.add('Δv along B̂ = N̂×V̂', 'Δv_B', -d['dC'], KMS, group=g)
        res.add('Δv along r̂, θ̂', 'Δv_rθ', list(d['dv_rθ']), KMS, group=g); res.add('Δv along ê, p̂ (old)', 'Δv_ep', list(d['dv_ep']), KMS, group=g)
        res.add('% energy change', '%E', d['pct_energy'], '%', '|v⁺ − v⁻|/Δv × 100', group=g); res.add('% direction change', '%D', d['pct_dir'], '%', '100 − %E', group=g)
        if th_now is not None and P1:
            dt = (time_since_periapsis(mu, a1, e1, d['th1']) - time_since_periapsis(mu, a1, e1, th_now)) % P1
            d['wait'] = dt; res.add('Wait from current position', 'Δt_wait', dt / 3600, HR, 'time along old orbit from θ*_now to the burn', group=g)

    for k, d in enumerate(rows): emit(k, d, ' ← minimum |Δv̄|' if d is best else '')
    if best: res.add('Minimum impulse', 'Δv_min', best['dv'], KMS, group='Selected')
    res.data.update(p1=p1, e1=e1, p2=p2, e2=e2, intersections=rows, best=best)

    # --------------- scene ---------------
    ra1 = p1 / (1 - e1) if e1 < 1 else 3 * p1; ra2 = p2 / (1 - e2) if e2 < 1 else 3 * p2; ref = max(ra1, ra2)
    o1 = Orbit('old orbit', p1, e1, Rz(0), 'orbit', rmax=1.4 * ref); o2 = Orbit('new orbit', p2, e2, Rz(d_omega), 'orbit2', rmax=1.4 * ref)
    sc = Scene(f'single impulse, Δω = {d_omega:.2f}°', label); sc.orbits += [o1, o2]
    if body_R: sc.disks.append(Disk(np.zeros(3), body_R, '', body=body_name))
    sc.pts.append(Pt(np.zeros(3), f'F ({body_name})' if body_name else 'F', 'ink', 'o', 5))
    apsides_line(sc, o1, 'old line of apsides')
    if e2 > 1e-9:
        apsides_line(sc, o2, 'new line of apsides')
        signed_arc(sc, np.zeros(3), Rz(0)[:, 0], Rz(d_omega)[:, 0], wrap180(d_omega), 0.12 * ref, f'Δω = {d_omega:.2f}°', 'ink2')
    for k, d in enumerate(rows):
        P = o1.pos(d['th1']); is_best = d is best
        sc.pts.append(Pt(P, f"{'burn ' if is_best else ''}θ*₁ = {d['th1']:.2f}° (Δv = {d['dv']:.4g})", 'dv' if is_best else 'muted', 'o' if is_best else 's', 7 if is_best else 5))
    if th_now is not None: sc.pts.append(Pt(o1.pos(th_now), 'now', 'ink', 'o', 6))
    if best:
        P = o1.pos(best['th1']); rh = unit(P); that = unit(np.cross(Z, rh)); vs = vel_scale(ref, max(best['v1'], best['v2']), 0.2)
        v1h = o1.vel_dir(best['th1']); v2h = o2.vel_dir(best['th2']); v1v = best['v1'] * v1h; v2v = best['v2'] * v2h
        vector(sc, P, v1v, f"v̄⁻ ({best['v1']:.4g})", 'vel', scale=vs)
        vector(sc, P, v2v, f"v̄⁺ ({best['v2']:.4g})", 'orbit3', scale=vs)
        vector(sc, P + v1v * vs, v2v - v1v, f"Δv̄ ({best['dv']:.4g} km/s)", 'dv', scale=vs)
        local_horizon(sc, P, Z, 0.25 * ref)
        # alpha: angle at the tail of v- between v- and the impulse direction (placed at P)
        dvv = v2v - v1v
        signed_arc(sc, P, v1h, unit(dvv), float(np.degrees(np.arctan2(v1h[0] * dvv[1] - v1h[1] * dvv[0], v1h @ dvv))), 0.07 * ref, f"α = {best['alpha']:+.2f}°", 'ink')
        res.check(f"α sign: Δv̄·Ĉ {'> 0 (away from the body)' if best['dC'] > 0 else '< 0 (toward the body)' if best['dC'] < 0 else '= 0'}; Ĉ = V̂ × N̂")
        trk, dur = orbit_track(mu, o1, th_now if th_now is not None else best['th1'], None, 'spacecraft') if e1 < 1 else (None, 0)
        if trk: sc.tracks.append(trk); sc.duration_s = dur
    res.scene = sc
    return res


def solve_given(mu: float, el: dict, ths: float, dv: float, alpha: float, beta: float = 0.0, body_R: float | None = None,
                body_name: str = '', label: str = 'Module 7b') -> Result:
    """el: a, e, inc, Om, om (deg); impulse at theta*=ths with (dv, alpha, beta) in VNC."""
    res = Result('Impulse given Δv, α, β', label, inputs=dict(mu=mu, el=el, ths=ths, dv=dv, alpha=alpha, beta=beta))
    a, e, inc, Om, om = (el[k] for k in ('a', 'e', 'inc', 'Om', 'om'))
    r_v, v_v, info = rv_from_elements(mu, a, e, inc, Om, om, ths)
    vn, dvec = apply_dv_vnc(r_v, v_v, dv, alpha, beta)
    V, N, C = vnc_frame(r_v, v_v)
    old = elements_from_rv(mu, r_v, v_v); new = elements_from_rv(mu, r_v, vn)
    Qm = info['C']; r = np.linalg.norm(r_v)
    g = 'Before'
    res.add('Radius', 'r', r, KM, group=g); res.add('v̄⁻ (x̂ŷẑ)', 'v̄⁻', v_v, KMS, group=g); res.add('Speed', 'v⁻', np.linalg.norm(v_v), KMS, group=g)
    res.add('Flight-path angle', 'γ⁻', old['gamma'], DEG, group=g)
    g = 'Impulse'
    res.add('Δv̄ (VNC: V̂, N̂, Ĉ)', 'Δv̄_VNC', [dv * np.cos(beta * D2R) * np.cos(alpha * D2R), dv * np.sin(beta * D2R), dv * np.cos(beta * D2R) * np.sin(alpha * D2R)], KMS,
            'Δv̄ = Δv(cosβ cosα V̂ + sinβ N̂ + cosβ sinα Ĉ)', group=g)
    res.add('Δv̄ (r̂, θ̂, ĥ)', 'Δv̄_rθh', [float(dvec @ Qm[:, k]) for k in range(3)], KMS, 'Φ = α + γ: Δv(cosβ sinΦ, cosβ cosΦ, sinβ)', group=g)
    Qo = dcm_313(Om, inc, om)
    res.add('Δv̄ (ê, p̂, ĥ)', 'Δv̄_epĥ', [float(dvec @ Qo[:, k]) for k in range(3)], KMS, group=g)
    res.add('Δv̄ (x̂, ŷ, ẑ)', 'Δv̄_xyz', dvec, KMS, group=g)
    Phi = alpha + old['gamma']; res.add('Φ = α + γ⁻', 'Φ', Phi, DEG, group=g)
    res.add('v̄⁺ (x̂ŷẑ)', 'v̄⁺', vn, KMS, group=g); res.add('Speed after', 'v⁺', np.linalg.norm(vn), KMS, group=g)
    res.add('Flight-path angle after', 'γ⁺', new['gamma'], DEG, group=g)
    dgam = new['gamma'] - old['gamma']; res.add('Δγ', 'Δγ', dgam, DEG, group=g)
    pe = abs(np.linalg.norm(vn) - np.linalg.norm(v_v)) / dv * 100 if dv else 0
    res.add('% energy', '%E', pe, '%', '|v⁺ − v⁻|/Δv × 100', group=g); res.add('% direction', '%D', 100 - pe, '%', group=g)
    g = 'New orbit'
    for nm, sym, key, u in (('a', 'a⁺', 'a', KM), ('e', 'e⁺', 'e', NONE), ('i', 'i⁺', 'inc', DEG), ('Ω', 'Ω⁺', 'Om', DEG), ('ω', 'ω⁺', 'om', DEG), ('θ*', 'θ*⁺', 'ths', DEG)):
        res.add(f'New {nm}', sym, new[key], u, group=g)
    res.add('New periapsis radius', 'r_p⁺', new['p'] / (1 + new['e']), KM, group=g)
    if new['e'] < 1: res.add('New apoapsis radius', 'r_a⁺', new['p'] / (1 - new['e']), KM, group=g); res.add('New period', 'P⁺', new['P'] / 3600, HR, group=g)
    res.add('Δi', 'Δi', new['inc'] - old['inc'], DEG, group=g); res.add('ΔΩ', 'ΔΩ', wrap180(new['Om'] - old['Om']), DEG, group=g)
    res.add('Δω', 'Δω', wrap180(new['om'] - old['om']), DEG, 'ω⁺ − ω⁻ (change of the argument of periapsis)', group=g)
    res.add('Δθ*', 'Δθ*', wrap180(new['ths'] - old['ths']), DEG, group=g)
    res.check(f'α sign: Δv̄·Ĉ = {dvec @ C:+.5f} km/s ⇒ {"away from" if dvec @ C > 0 else "toward"} the central body')
    if old['e'] >= 1 or new['e'] >= 1: res.warn('an orbit involved is not an ellipse')
    res.data.update(old=old, new=new, dvec=dvec, vn=vn, r_vec=r_v, v_vec=v_v, Q=Qm)

    ref = max(old['p'] / (1 - old['e']) if old['e'] < 1 else 3 * old['p'], new['p'] / (1 - new['e']) if new['e'] < 1 else 3 * new['p'])
    o1 = Orbit('old orbit', old['p'], old['e'], dcm_313(old['Om'], old['inc'], old['om']), 'orbit', rmax=1.4 * ref)
    o2 = Orbit('new orbit', new['p'], new['e'], dcm_313(new['Om'], new['inc'], new['om']), 'orbit2', rmax=1.4 * ref)
    sc = Scene(f'Δv = {dv:g} km/s, α = {alpha:g}°, β = {beta:g}°', label, is3d=abs(beta) > 1e-9 or abs(new['inc'] - old['inc']) > 1e-9)
    sc.orbits += [o1, o2]
    if body_R: sc.disks.append(Disk(np.zeros(3), body_R, body_name or 'body', body=body_name))
    sc.pts.append(Pt(np.zeros(3), 'F', 'ink', 'o', 5)); sc.pts.append(Pt(r_v, 'burn', 'ink', 'o', 7))
    apsides_line(sc, o1, 'old line of apsides'); apsides_line(sc, o2, 'new line of apsides')
    vs = vel_scale(ref, max(np.linalg.norm(v_v), np.linalg.norm(vn)), 0.2)
    vector(sc, r_v, v_v, f'v̄⁻ ({np.linalg.norm(v_v):.4g})', 'vel', scale=vs); vector(sc, r_v, vn, f'v̄⁺ ({np.linalg.norm(vn):.4g})', 'orbit3', scale=vs)
    vector(sc, r_v + v_v * vs, dvec, f'Δv̄ ({dv:g})', 'dv', scale=vs)
    angle_arc(sc, r_v, V, unit(dvec), 0.07 * ref, f'α = {alpha:g}°, β = {beta:g}°', 'ink', N if abs(beta) < 1e-9 else None)
    unit_triad(sc, r_v, np.column_stack([V, N, C]), ('V̂', 'N̂', 'Ĉ'), 0.12 * ref, 'accent', only3d=False)
    if not (np.sin(old['inc'] * D2R) < 1e-10): nodes_line(sc, old['Om'], 1.1 * ref)
    # 2-D view: the old orbit plane
    sc.plane2d = (o1.Q[:, 0], o1.Q[:, 1])
    if old['e'] < 1:
        trk, dur = orbit_track(mu, o1, ths, None, 'spacecraft (old)'); sc.tracks.append(trk); sc.duration_s = dur
    res.scene = sc
    return res
