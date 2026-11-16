"""Module 11 - gravity assist (HW8 P4c, HW9 P2b-P4).

Planar flyby of a planet on a circular heliocentric orbit. v_inf^- = v^- - v_planet is rotated by +/- delta
(delta = 2 asin(1/e), e = 1 + r_p v_inf^2/mu); BOTH senses are computed and labelled by what they do to the heliocentric energy:
    d(eps) = v_planet . (v_inf^+ - v_inf^-)  >  0  -> energy GAINED  (spacecraft passes BEHIND the planet, trailing side)
                                              <  0  -> energy LOST    (spacecraft passes AHEAD of the planet)
Vectors are (r_hat, theta_hat) components at the planet; theta_hat is along the planet velocity.
"""
from __future__ import annotations
import numpy as np
from ..core.constants import D2R, R2D, wrap360, wrap180
from ..core.kepler import time_since_periapsis
from ..core.conic import conic_from_rv_polar, gamma_of, v_of
from ..core.hyperbola import hyperbola
from ..core.flyby import flyby
from ..core.maneuvers import impulse_planar
from ..results import Result, KM, KMS, DEG, SEC, HR, DAY, NONE, EPS
from ..scene import Scene, Orbit, Disk, Pt, Arc, vector, angle_arc, apsides_line, Rz, unit
from .common import vel_scale, pe_from_spec, orbit_track
from .m05_hyperbola import hyp_scene
from .m03_conic import signed_arc, Z


def _to_xy(v_rt, pos):
    rh = unit(pos); th = np.array([-rh[1], rh[0], 0.0]); return v_rt[0] * rh + v_rt[1] * th


def _v_minus(mu_c, r, spec):
    if 'v' in spec: v = spec['v']; g = spec['gamma']; return np.array([v * np.sin(g * D2R), v * np.cos(g * D2R)])
    if 'vr' in spec: return np.array([spec['vr'], spec['vt']])
    p, e = pe_from_spec(spec['orbit']); a = p / (1 - e * e); v = v_of(mu_c, r, a); g = float(gamma_of(e, spec['ths']))
    return np.array([v * np.sin(g * D2R), v * np.cos(g * D2R)])


def solve(mu_c: float, planet: dict, v_minus: dict, rp: float, sense: str = 'lose', c_name: str = 'Sun', label: str = 'Module 11') -> Result:
    """planet: dict(mu, R, r, name); v_minus: {'v','gamma'} | {'vr','vt'} | {'orbit': spec, 'ths': deg}; sense 'gain' | 'lose' | 'ccw' | 'cw'."""
    res = Result('Gravity assist', label, inputs=dict(mu_c=mu_c, planet=planet, v_minus=v_minus, rp=rp, sense=sense))
    r = planet['r']; vc = np.sqrt(mu_c / r); vpl = np.array([0.0, vc]); vm = _v_minus(mu_c, r, v_minus)
    c_old = conic_from_rv_polar(mu_c, r, vm[0], vm[1]); g_old = c_old['gamma']
    g = 'Before the encounter'
    res.add('Planet speed', 'v_pl', vc, KMS, group=g); res.add('v̄⁻ (r̂,θ̂)', 'v̄⁻', vm, KMS, group=g); res.add('Speed', 'v⁻', np.linalg.norm(vm), KMS, group=g)
    res.add('Flight-path angle', 'γ⁻', g_old, DEG, group=g); res.add('θ*⁻', 'θ*⁻', c_old['ths'], DEG, group=g)
    res.add('Orbit a, e', 'a⁻', c_old['a'], KM, group=g); res.add('Eccentricity', 'e⁻', c_old['e'], NONE, group=g); res.add('Specific energy', 'ε⁻', c_old['eps'], EPS, group=g)
    outs = {}
    for sn in (+1, -1):
        fb = flyby(planet['mu'], vpl, vm, rp, sn); c = conic_from_rv_polar(mu_c, r, fb['v_plus'][0], fb['v_plus'][1])
        d_eps = float(vpl @ (fb['vinf_plus'] - fb['vinf_minus'])); kind = 'gain' if d_eps > 1e-9 else 'lose' if d_eps < -1e-9 else 'neutral'
        imp = impulse_planar(np.linalg.norm(vm), g_old, np.linalg.norm(fb['v_plus']), c['gamma'])
        outs[sn] = dict(fb=fb, c=c, d_eps=d_eps, sense=sn, imp=imp, dw=c_old['ths'] - c['ths'], kind=kind)
    # selection: 'gain' -> larger d_eps, 'lose' -> smaller d_eps, 'ccw'/'cw' explicit; ties (tangential encounter) fall back to ccw
    if sense in ('ccw', 'cw'): pick = +1 if sense == 'ccw' else -1
    elif abs(outs[1]['d_eps'] - outs[-1]['d_eps']) < 1e-9:
        pick = +1; res.check('tangential encounter: both rotation senses change the heliocentric energy identically (they differ only in the radial component); showing counter-clockwise')
    else: pick = max(outs, key=lambda k: outs[k]['d_eps']) if sense == 'gain' else min(outs, key=lambda k: outs[k]['d_eps'])
    res.data.update(outs=outs, c_old=c_old, vm=vm, vinf_minus=outs[pick]['fb']['vinf_minus'], pick=pick)
    hy = outs[pick]['fb']['hyp']; fb0 = outs[pick]['fb']
    g = 'Flyby hyperbola'
    res.add('v̄∞⁻ (r̂,θ̂)', 'v̄∞⁻', fb0['vinf_minus'], KMS, 'v̄∞⁻ = v̄⁻ − v̄_pl', group=g); res.add('v∞', 'v∞', fb0['vinf'], KMS, group=g)
    res.add('Eccentricity', 'e', hy['e'], NONE, 'e = 1 + r_p v∞²/μ', group=g); res.add('Turn angle', 'δ', hy['delta'], DEG, 'δ = 2 asin(1/e)', group=g)
    res.add('Periapsis radius', 'r_p', rp, KM, group=g); res.add('Altitude', 'alt', rp - planet['R'], KM, group=g)
    if rp < planet['R']: res.warn(f'flyby periapsis {rp:,.1f} km is below the surface ({planet["R"]:,.1f} km)')
    for sn in (+1, -1):
        o = outs[sn]; kind = o['kind']; fb = o['fb']; c = o['c']
        g = f'After — {"energy GAINED" if kind == "gain" else "energy LOST" if kind == "lose" else "energy unchanged (tangential)"} (rotate v̄∞ {"counter-clockwise" if sn > 0 else "clockwise"})'
        res.add('v̄∞⁺ (r̂,θ̂)', 'v̄∞⁺', fb['vinf_plus'], KMS, 'v̄∞⁺ = R(±δ) v̄∞⁻', group=g)
        res.add('v̄⁺ (r̂,θ̂)', 'v̄⁺', fb['v_plus'], KMS, 'v̄⁺ = v̄_pl + v̄∞⁺', group=g); res.add('Speed', 'v⁺', np.linalg.norm(fb['v_plus']), KMS, group=g)
        res.add('Flight-path angle', 'γ⁺', c['gamma'], DEG, group=g)
        res.add('New a', 'a⁺', c['a'], KM, group=g); res.add('New e', 'e⁺', c['e'], NONE, group=g)
        res.add('New periapsis radius', 'r_p⁺', c['p'] / (1 + c['e']), KM, group=g)
        if c['e'] < 1: res.add('New apoapsis radius', 'r_a⁺', c['p'] / (1 - c['e']), KM, group=g); res.add('New period', 'P⁺', c['P'] / 86400, DAY, group=g)
        res.add('New energy', 'ε⁺', c['eps'], EPS, group=g); res.add('θ*⁺', 'θ*⁺', c['ths'], DEG, group=g)
        res.add('Δω (rotation of the line of apsides)', 'Δω', o['dw'], DEG, 'Δω = θ*⁻ − θ*⁺', group=g)
        res.add('Energy change ε⁺ − ε⁻', 'Δε', c['eps'] - c_old['eps'], EPS, group=g)
        res.add('Equivalent impulse', 'Δv_eq', o['imp']['dv'], KMS, '|v̄⁺ − v̄⁻| = 2v∞ sin(δ/2)', group=g)
        res.add('Equivalent impulse angle α', 'α_eq', o['imp']['alpha'], DEG, 'from v̄⁻; + away from the Sun', group=g)
        res.check(f'{"ccw" if sn > 0 else "cw"} pass: v̄_pl·(v̄∞⁺ − v̄∞⁻) = {o["d_eps"]:+.4f} km²/s² ⇒ heliocentric energy {"gained (pass behind the planet)" if kind == "gain" else "lost (pass ahead of the planet)" if kind == "lose" else "unchanged"}')
    # ---------------- heliocentric scene ----------------
    sel = outs[pick]; c_new = sel['c']; ref = max(r * 1.6, c_old['p'] / (1 - c_old['e']) if c_old['e'] < 1 else r * 1.6)
    sc = Scene(f'gravity assist at {planet.get("name", "planet")} — {sel["kind"] if sel["kind"] != "neutral" else "tangential"} ({"ccw" if pick > 0 else "cw"})', label); sc.focus_name = c_name
    sc.pts.append(Pt(np.zeros(3), f'F ({c_name})', 'ink', 'o', 5))
    sc.orbits.append(Orbit(f'{planet.get("name", "planet")} orbit', r, 0.0, Rz(0), 'orbit3', dash=True))
    o_old = Orbit('old orbit', c_old['p'], c_old['e'], Rz(-c_old['ths']), 'orbit', rmax=1.5 * ref); o_new = Orbit('new orbit', c_new['p'], c_new['e'], Rz(-c_new['ths']), 'orbit2', rmax=1.5 * ref)
    sc.orbits += [o_old, o_new]
    P = np.array([r, 0.0, 0.0]); sc.pts.append(Pt(P, planet.get('name', 'planet'), 'ink', 'o', 8))
    apsides_line(sc, o_old, 'old line of apsides'); apsides_line(sc, o_new, 'new line of apsides')
    signed_arc(sc, np.zeros(3), o_old.Q[:, 0], o_new.Q[:, 0], wrap180(sel['dw']), 0.15 * ref, f"Δω = {sel['dw']:.2f}°", 'ink2')
    vs = vel_scale(ref, max(np.linalg.norm(vm), np.linalg.norm(sel['fb']['v_plus']), vc), 0.2)
    xy = lambda v: _to_xy(v, P)
    vector(sc, P, xy(vpl), f'v̄_planet ({vc:.4g})', 'vel', scale=vs)
    vector(sc, P, xy(vm), f'v̄⁻ ({np.linalg.norm(vm):.4g})', 'orbit', scale=vs); vector(sc, P, xy(sel['fb']['v_plus']), f"v̄⁺ ({np.linalg.norm(sel['fb']['v_plus']):.4g})", 'orbit2', scale=vs)
    vector(sc, P + xy(vm) * vs, xy(sel['fb']['v_plus'] - vm), f"Δv̄_eq ({sel['imp']['dv']:.4g}), α = {sel['imp']['alpha']:+.1f}°", 'dv', scale=vs)
    vector(sc, P + xy(vpl) * vs, xy(sel['fb']['vinf_minus']), f"v̄∞⁻ ({sel['fb']['vinf']:.4g})", 'muted', scale=vs, dash=True)
    vector(sc, P + xy(vpl) * vs, xy(sel['fb']['vinf_plus']), 'v̄∞⁺', 'muted', scale=vs, dash=True)
    if c_old['e'] < 1:
        trk, dur = orbit_track(mu_c, o_old, c_old['ths'], None, 'spacecraft (old orbit)'); sc.tracks.append(trk); sc.duration_s = dur
    res.scene = sc
    # ---------------- planet-frame hyperbola ----------------
    ang_in = np.degrees(np.arctan2(*(xy(sel['fb']['vinf_minus'])[[1, 0]])))
    th = hy['th_inf']; cw = pick < 0
    # incoming far-position direction (angle ang_in + 180) is at omega - th for a ccw pass and at omega + th for a cw (mirrored) pass
    omega = (ang_in + 180 + th) if not cw else (ang_in + 180 - th)
    res.scenes['planet-frame hyperbola'] = hyp_scene(f'planet frame: v∞ = {hy["vinf"]:.4f} km/s, δ = {hy["delta"]:.2f}°', label, planet['mu'], -hy['a'], hy['e'], planet['R'], planet.get('name', ''), omega, None, cw)
    return res


def solve_free_return(mu_c: float, planet: dict, r_park: float, TA: float, body_name: str = 'Earth', c_R: float | None = None, label: str = 'Module 11 (free return)') -> Result:
    """Free return (HW9 P3): transfer from a parking radius to the planet's orbit radius with transfer angle TA; v_r^+ = -v_r^- after the flyby
    (symmetric) so the spacecraft returns to the primary. Gives the flyby radius/altitude that produces the required turn."""
    res = Result('Free-return flyby', label, inputs=dict(mu_c=mu_c, planet=planet, r_park=r_park, TA=TA))
    r2 = planet['r']; r1 = r_park
    e = (r2 - r1) / (r1 - r2 * np.cos(TA * D2R)); p = r1 * (1 + e); a = p / (1 - e * e)
    v2 = v_of(mu_c, r2, a); gm = float(gamma_of(e, TA)); vm = np.array([v2 * np.sin(gm * D2R), v2 * np.cos(gm * D2R)]); vc = np.sqrt(mu_c / r2)
    wi = vm - np.array([0, vc]); vp_ = np.array([-vm[0], vm[1]]); wo = vp_ - np.array([0, vc]); vinf = np.linalg.norm(wi)
    delta = np.arccos(np.clip(wi @ wo / vinf ** 2, -1, 1)); rpH = planet['mu'] / vinf ** 2 * (1 / np.sin(delta / 2) - 1)
    tof = time_since_periapsis(mu_c, a, e, TA)
    g = 'Transfer to the planet'
    res.add('Eccentricity', 'e', e, NONE, 'p = r₁(1+e) = r₂(1 + e cosTA)  ⇒  e = (r₂−r₁)/(r₁ − r₂ cosTA)', group=g); res.add('Semi-latus rectum', 'p', p, KM, group=g); res.add('Semi-major axis', 'a', a, KM, group=g)
    res.add('Time of flight (periapsis → TA)', 'TOF', tof / 86400, DAY, group=g); res.add('Speed at the planet', 'v⁻', v2, KMS, group=g)
    res.add('Flight-path angle at the planet', 'γ⁻', gm, DEG, group=g); res.add('v̄⁻ (r̂,θ̂)', 'v̄⁻', vm, KMS, group=g)
    g = 'Flyby'
    res.add('v̄∞⁻', 'v̄∞⁻', wi, KMS, group=g); res.add('v∞', 'v∞', vinf, KMS, group=g); res.add('v̄⁺ = (−v_r⁻, v_θ⁻)', 'v̄⁺', vp_, KMS, 'symmetric return: v_r⁺ = −v_r⁻', group=g)
    res.add('Required turn angle', 'δ', np.degrees(delta), DEG, 'cosδ = v̄∞⁻·v̄∞⁺/v∞²', group=g)
    res.add('Required flyby periapsis radius', 'r_p', rpH, KM, 'r_p = (μ/v∞²)(1/sin(δ/2) − 1)', group=g); res.add('Altitude', 'alt', rpH - planet['R'], KM, group=g)
    res.add('Equivalent impulse', 'Δv_eq', np.linalg.norm(vp_ - vm), KMS, group=g)
    if rpH < planet['R']: res.warn('required periapsis is below the surface: the free return is not achievable at this TA')
    res.data.update(e=e, p=p, a=a, tof=tof, vinf=vinf, delta=np.degrees(delta), rp=rpH, vm=vm, vp=vp_)
    ref = max(r2, a * (1 + e) if e < 1 else 2 * r2)
    sc = Scene(f'free return, TA = {TA:g}°', label); sc.pts.append(Pt(np.zeros(3), f'F ({body_name})', 'ink', 'o', 5))
    if c_R: sc.disks.append(Disk(np.zeros(3), c_R, '', body=body_name))
    sc.orbits.append(Orbit(f'{planet.get("name", "planet")} orbit', r2, 0.0, Rz(0), 'orbit3', dash=True))
    out = Orbit('outbound transfer', p, e, Rz(0), 'orbit', ths_range=(0, TA)); ret = Orbit('return transfer (mirror)', p, e, Rz(2 * TA), 'orbit2', ths_range=(-TA, 0))
    sc.orbits += [out, ret, Orbit('', p, e, Rz(0), 'orbit', dash=True), Orbit('', p, e, Rz(2 * TA), 'orbit2', dash=True)]
    Pm = np.array([r2 * np.cos(TA * D2R), r2 * np.sin(TA * D2R), 0]); sc.pts.append(Pt(Pm, f'{planet.get("name", "planet")} at flyby', 'ink', 'o', 8))
    sc.pts.append(Pt(np.array([r1, 0, 0]), 'departure', 'ink', 's', 6))
    vs = vel_scale(ref, np.linalg.norm(vm), 0.2)
    vector(sc, Pm, _to_xy(vm, Pm), f'v̄⁻ ({np.linalg.norm(vm):.4g})', 'orbit', scale=vs); vector(sc, Pm, _to_xy(vp_, Pm), 'v̄⁺', 'orbit2', scale=vs)
    vector(sc, Pm, _to_xy(np.array([0, vc]), Pm), f'v̄_planet ({vc:.4g})', 'vel', scale=vs)
    angle_arc(sc, np.zeros(3), np.array([1.0, 0, 0]), unit(Pm), 0.2 * ref, f'TA = {TA:g}°', 'ink', Z)
    res.scene = sc
    return res
