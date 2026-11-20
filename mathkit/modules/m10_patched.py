"""Module 10 - patched conics (HW8 P4, HW9 P2a, HW10 P3d).

Heliocentric (or planet-centered) transfer between two bodies on circular orbits of radius r_dep, r_arr.
v_inf vector = v_transfer - v_planet, INCLUDING the non-tangential case (gamma != 0 at the planet).
Departure from a circular parking orbit of radius r_pk:  dv = sqrt(v_inf^2 + 2 mu/r_pk) - sqrt(mu/r_pk).
Capture into an orbit (r_cap periapsis, eccentricity e_cap):  dv = sqrt(v_inf^2 + 2 mu/r_cap) - sqrt(mu(1 + e_cap)/r_cap).
"""
from __future__ import annotations
import numpy as np
from ..core.constants import D2R, R2D, wrap180
from ..core.transfers import hohmann
from ..core.patched import escape_dv, capture_dv
from ..core.hyperbola import hyperbola
from ..core.conic import conic_from_rv_polar
from ..results import Result, KM, KMS, DEG, SEC, HR, DAY, YR, NONE
from ..scene import Scene, Orbit, Disk, Pt, vector, angle_arc, Rz, unit
from .common import vel_scale, orbit_track
from .m05_hyperbola import hyp_scene
from .m03_conic import signed_arc, Z


def solve(mu_c: float, dep: dict, arr: dict, transfer: dict, r_park: float, r_cap: float, e_cap: float = 0.0, c_name: str = 'Sun',
          label: str = 'Module 10') -> Result:
    """dep/arr: dict(mu, R, r (orbit radius about the central body), name).
    transfer: {'kind': 'hohmann'} or {'kind': 'state', 'v_dep': (v_r, v_theta), 'v_arr': (v_r, v_theta)} in each end's r̂θ̂ frame (km/s).
    r_park, r_cap: radii (km from each planet's center) of the parking orbit and of the capture periapsis."""
    res = Result('Patched conics', label, inputs=dict(mu_c=mu_c, dep=dep, arr=arr, transfer=transfer, r_park=r_park, r_cap=r_cap, e_cap=e_cap))
    r1, r2 = dep['r'], arr['r']; vc1, vc2 = np.sqrt(mu_c / r1), np.sqrt(mu_c / r2)
    if transfer['kind'] == 'hohmann':
        h = hohmann(mu_c, r1, r2); v_dep = np.array([0.0, h['vp']]); v_arr = np.array([0.0, h['va']]); tof = h['tof']
        res.add('Hohmann transfer time', 'TOF', tof / 86400, DAY, group='Heliocentric transfer'); res.add('Hohmann transfer time', 'TOF', tof / 86400 / 365.25, YR, group='Heliocentric transfer')
    else:
        v_dep = np.asarray(transfer['v_dep'], float); v_arr = np.asarray(transfer['v_arr'], float); tof = None
    vpl_d = np.array([0.0, vc1]); vpl_a = np.array([0.0, vc2])
    vinf_d = v_dep - vpl_d; vinf_a = v_arr - vpl_a; vd, va = np.linalg.norm(vinf_d), np.linalg.norm(vinf_a)
    ang_d = np.degrees(np.arctan2(vinf_d[0], vinf_d[1])); ang_a = np.degrees(np.arctan2(vinf_a[0], vinf_a[1]))
    g = 'Heliocentric transfer'
    res.add('Planet speed at departure', 'v_pl,D', vc1, KMS, group=g); res.add('Transfer velocity at departure (r̂,θ̂)', 'v̄_D', v_dep, KMS, group=g)
    res.add('Planet speed at arrival', 'v_pl,A', vc2, KMS, group=g); res.add('Transfer velocity at arrival (r̂,θ̂)', 'v̄_A', v_arr, KMS, group=g)
    g = 'Departure'
    res.add('v̄∞ at departure (r̂,θ̂)', 'v̄∞,D', vinf_d, KMS, 'v̄∞ = v̄_transfer − v̄_planet', group=g); res.add('v∞ at departure', 'v∞,D', vd, KMS, group=g)
    res.add('Angle of v̄∞ from the planet velocity', 'ε_D', ang_d, DEG, 'atan2(v∞_r, v∞_θ); 0° = tangential', group=g)
    if abs(ang_d) > 1e-6: res.check(f'non-tangential departure: v̄∞ is {ang_d:+.3f}° from the planet velocity, so v∞ = |v̄_D − v̄_pl| (vector difference), not a speed difference')
    hd = hyperbola(dep['mu'], vinf=vd, rp=r_park); dv_dep = escape_dv(dep['mu'], r_park, vd)
    res.add('Parking-orbit speed', 'v_c', np.sqrt(dep['mu'] / r_park), KMS, group=g); res.add('Departure Δv', 'Δv_dep', dv_dep, KMS, 'Δv = √(v∞² + 2μ/r_p) − √(μ/r_p)', group=g)
    res.add('Departure hyperbola e', 'e_D', hd['e'], NONE, group=g); res.add('Turn angle', 'δ_D', hd['delta'], DEG, group=g); res.add('θ*∞', 'θ*∞,D', hd['th_inf'], DEG, group=g)
    g = 'Arrival'
    res.add('v̄∞ at arrival (r̂,θ̂)', 'v̄∞,A', vinf_a, KMS, group=g); res.add('v∞ at arrival', 'v∞,A', va, KMS, group=g)
    res.add('Angle of v̄∞ from the planet velocity', 'ε_A', ang_a, DEG, group=g)
    ha = hyperbola(arr['mu'], vinf=va, rp=r_cap)
    dv_cap = capture_dv(arr['mu'], r_cap, va, e_cap)
    res.add('Capture Δv' + (' (circular)' if e_cap == 0 else f' (e = {e_cap:g})'), 'Δv_cap', dv_cap, KMS, 'Δv = √(v∞² + 2μ/r_p) − √(μ(1+e)/r_p)', group=g)
    res.add('Arrival hyperbola e', 'e_A', ha['e'], NONE, group=g); res.add('Turn angle', 'δ_A', ha['delta'], DEG, group=g); res.add('θ*∞', 'θ*∞,A', ha['th_inf'], DEG, group=g)
    res.add('Total Δv (departure + capture)', 'Δv_tot', dv_dep + dv_cap, KMS, group='Total')
    if dep.get('R') and r_park < dep['R']: res.warn('parking orbit is below the departure planet surface')
    if arr.get('R') and r_cap < arr['R']: res.warn('capture periapsis is below the arrival planet surface')
    res.data.update(vinf_dep=vd, vinf_arr=va, dv_dep=dv_dep, dv_cap=dv_cap, hd=hd, ha=ha, vinf_d_vec=vinf_d, vinf_a_vec=vinf_a, tof=tof)

    # ---------------- heliocentric scene ----------------
    ref = max(r1, r2)
    sc = Scene('heliocentric transfer', label); sc.focus_name = c_name
    sc.pts.append(Pt(np.zeros(3), f'F ({c_name})', 'ink', 'o', 5))
    sc.orbits += [Orbit(f'{dep.get("name", "departure")} orbit', r1, 0.0, Rz(0), 'orbit'), Orbit(f'{arr.get("name", "arrival")} orbit', r2, 0.0, Rz(0), 'orbit2')]
    # conic through the end states (planar): reconstruct from departure state
    c = conic_from_rv_polar(mu_c, r1, v_dep[0], v_dep[1]); th_d = c['ths']
    omega = -th_d  # departure at +x
    T = Orbit('transfer', c['p'], c['e'], Rz(omega), 'transfer', dash=True, rmax=1.3 * ref)
    # arrival: where the transfer crosses r2 after departure
    cos_a = (c['p'] / r2 - 1) / c['e'] if c['e'] > 0 else 1.0
    th_a = np.degrees(np.arccos(np.clip(cos_a, -1, 1)))
    cand = [th_a, -th_a]; th_arr = min(cand, key=lambda t: ((t - th_d) % 360) if ((t - th_d) % 360) > 1e-6 else 1e9)
    T_arc = Orbit('transfer arc', c['p'], c['e'], Rz(omega), 'transfer', ths_range=(th_d, th_d + ((th_arr - th_d) % 360))); sc.orbits += [T, T_arc]; T.name = ''
    Pd = np.array([r1, 0, 0]); Pa = T.pos(th_arr)
    sc.pts += [Pt(Pd, f'{dep.get("name", "dep")} at departure', 'ink', 'o', 7), Pt(Pa, f'{arr.get("name", "arr")} at arrival', 'ink', 's', 7)]
    vs = vel_scale(ref, max(np.linalg.norm(v_dep), vc1), 0.16)
    # v∞ vectors in inertial 2-D: (r̂, θ̂) -> x/y
    def to_xy(v_r_t, pos): rh = unit(pos); th = np.array([-rh[1], rh[0], 0]); return v_r_t[0] * rh + v_r_t[1] * th
    vector(sc, Pd, to_xy(vpl_d, Pd), f'v̄_planet ({vc1:.4g})', 'vel', scale=vs); vector(sc, Pd, to_xy(v_dep, Pd), f'v̄_transfer ({np.linalg.norm(v_dep):.4g})', 'orbit3', scale=vs)
    vector(sc, Pd + to_xy(vpl_d, Pd) * vs, to_xy(vinf_d, Pd), f'v̄∞ ({vd:.4g} km/s)', 'dv', scale=vs)
    Pa_r = Pa
    vector(sc, Pa_r, to_xy(vpl_a, Pa_r), f'v̄_planet ({vc2:.4g})', 'vel', scale=vs); vector(sc, Pa_r, to_xy(v_arr, Pa_r), f'v̄_transfer ({np.linalg.norm(v_arr):.4g})', 'orbit3', scale=vs)
    vector(sc, Pa_r + to_xy(vpl_a, Pa_r) * vs, to_xy(vinf_a, Pa_r), f'v̄∞ ({va:.4g} km/s)', 'dv', scale=vs)
    if c['e'] < 1 and tof:
        trk, _ = orbit_track(mu_c, T, th_d, None, 'spacecraft', 'transfer'); sc.tracks.append(trk); sc.duration_s = tof     # animate departure -> arrival only
    res.scene = sc
    # ---------------- planet-centered insets ----------------
    d_dir = np.arctan2(to_xy(vinf_d, Pd)[1], to_xy(vinf_d, Pd)[0]) * R2D
    res.scenes['departure hyperbola (planet-centered)'] = hyp_scene(f'departure: v∞ = {vd:.4f} km/s, e = {hd["e"]:.4f}, δ = {hd["delta"]:.2f}°', label, dep['mu'], hd['a'] * -1, hd['e'], dep.get('R'), dep.get('name', ''),
                                                                      omega=d_dir - hd['th_inf'], ths_mark=None)
    a_dir = np.arctan2(to_xy(vinf_a, Pa)[1], to_xy(vinf_a, Pa)[0]) * R2D
    res.scenes['arrival hyperbola (planet-centered)'] = hyp_scene(f'arrival: v∞ = {va:.4f} km/s, e = {ha["e"]:.4f}, δ = {ha["delta"]:.2f}°', label, arr['mu'], ha['a'] * -1, ha['e'], arr.get('R'), arr.get('name', ''),
                                                                    omega=a_dir + 180 + ha['th_inf'], ths_mark=None)
    return res
