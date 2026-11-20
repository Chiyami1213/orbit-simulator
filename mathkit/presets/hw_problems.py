"""Every HW / exam problem that has printed answers, as a form preset + expected values (copied from the solution PDFs, with the
corrections listed in BUILD_PROMPT section 9). Problems whose data are not in the supplied files (HW2 P1-3, HW3 P1, Exam 1 P1,
HW11 P2, ...) have no preset: enter them by hand.

``vals`` only lists fields that differ from the module defaults; the runner merges defaults first.
"""
from __future__ import annotations
import numpy as np
from ..core.constants import BODIES, EXAM, AU, wrap360, wrap180
from ..core.elements import rv_from_elements
from ..core.transfers import hohmann
from ..core.conic import v_of, gamma_of
from ..registry import Preset, Expect as X, MODULES

B = BODIES; RE = B['Earth']['R']; Mo = B['Moon']; Sun = B['Sun']
S = lambda r, sym: r.get(sym)                      # value of a named step
dd = lambda r, k: r.data[k]
PRESETS: dict[str, list[Preset]] = {k: [] for k in MODULES}
add = lambda mod, p: PRESETS[mod].append(p)

# ------------------------------------------------------------------ Module 3
add('3', Preset('HW3 P3 — state (alt 8560 km, v_r, v_θ) → conic', dict(body='Earth', mode='polar', r=RE + 8560, vr=-2.11, vt=4.89),
    [X('a', lambda r: dd(r, 'a'), 15942.3), X('p', lambda r: dd(r, 'p'), 13386.7), X('e', lambda r: dd(r, 'e'), 0.4004), X('P', lambda r: dd(r, 'conic_from_rv_polar')['P'], 20032.7),
     X('θ* (0–360°)', lambda r: wrap360(dd(r, 'ths')), 254.97), X('γ', lambda r: dd(r, 'gamma'), -23.340)]))

# ------------------------------------------------------------------ Module 4
add('4', Preset('HW4 P1 — Anteros, propagate 6.4 months (30-day)', dict(body='Sun', a_kind='a', a=1.43018128 * AU, e=0.2576460, start_kind='ths', start_val=118.65, dt=6.4, dt_unit='30-day months'),
    [X('r₀ [AU]', lambda r: dd(r, 'r0') / AU, 1.52343), X('v₀', lambda r: dd(r, 'v0'), 23.3313), X('γ₀', lambda r: dd(r, 'gamma0'), 14.4651), X('E₀', lambda r: dd(r, 'E0'), 104.6595),
     X('θ*₁ (0–360°)', lambda r: wrap360(dd(r, 'th1')), 192.9160), X('γ₁', lambda r: dd(r, 'gamma1'), -4.39749)]))
add('4', Preset('HW4 P2 — M₀ = 90°, e = 0.75, a = 8R⊕, +2 h', dict(body='Earth', a_kind='a', a=8 * RE, e=0.75, start_kind='M', start_val=90.0, dt=2.0, dt_unit='h'),
    [X('E₀', lambda r: dd(r, 'E0'), 125.1401), X('θ*₀', lambda r: dd(r, 'th0'), 157.8026), X('γ₀', lambda r: dd(r, 'gamma0'), 42.8379), X('t₀−t_p [h]', lambda r: dd(r, 't0') / 3600, 7.9657),
     X('θ*₁', lambda r: dd(r, 'th1'), 164.3925)]))
add('4', Preset('HW5 P1 — Mars orbit, M₀ = −120°, Δt = 0.75 P (f, g)', dict(body='Mars', a_kind='rp, ra', rp=1.8 * B['Mars']['R'], ra=8 * B['Mars']['R'], start_kind='M', start_val=-120.0, dt=0.75, dt_unit='periods (P)'),
    [X('E₀', lambda r: dd(r, 'E0'), -142.2112), X('θ*₀', lambda r: dd(r, 'th0'), -161.5568), X('γ₀', lambda r: dd(r, 'gamma0'), -26.5912), X('θ*₁', lambda r: dd(r, 'th1'), 171.1657),
     X('E₁', lambda r: dd(r, 'E1'), 161.5011), X('γ₁', lambda r: dd(r, 'gamma1'), 14.5312), X('f', lambda r: dd(r, 'f'), 0.7033, 5e-4), X('g', lambda r: dd(r, 'g'), -1.4738e4, 5e-4),
     X('ḟ', lambda r: dd(r, 'fd'), 3.3402e-5, 5e-4), X('ġ', lambda r: dd(r, 'gd'), 0.7219, 5e-4)]))
_a = 4 * B['Earth']['R']
add('4', Preset('Exam 2 P3 — TOF θ* = 90° → −120° (course constants)', dict(body='Earth', a_kind='a', a=_a, e=0.5, start_kind='ths', start_val=90.0, dt_mode='until θ*₁', end_ths=-120.0),
    [X('TOF [h]', lambda r: dd(r, 'tof_s') / 3600, 8.24419)], note='The printed 8.24419 h uses course-table constants for n.'))

# ------------------------------------------------------------------ Module 5
V_ = B['Venus']
add('5', Preset('HW4 P3 — Venus hyperbola, r_p = 10R, |a| = 50R, θ* = −110°', dict(body='Venus', combo='r_p + |a|', rp=10 * V_['R'], a_abs=50 * V_['R'], ths=-110.0),
    [X('v∞', lambda r: S(r, 'v∞'), 1.0361349), X('θ*∞', lambda r: S(r, 'θ*∞'), 146.44269), X('δ', lambda r: S(r, 'δ'), 112.88538), X('b', lambda r: S(r, 'b'), 200718.81569),
     X('r(−110°)/R', lambda r: S(r, 'r') / V_['R'], 37.31496), X('γ(−110°)', lambda r: S(r, 'γ'), -62.397426), X('H', lambda r: S(r, 'H'), -0.921273), X('t_p − t [h]', lambda r: S(r, 't_p−t'), 28.18302),
     X('θ*_aim', lambda r: S(r, 'θ*_aim'), -56.44269), X('r_aim/R', lambda r: S(r, 'r_aim') / V_['R'], 13.226519), X('capture Δv (circular at r_p)', lambda r: S(r, 'Δv_cap'), 1.119603)]))
add('5', Preset('HW5 P2 — lunar hyperbola, |a| = 7050 km, r_p = R + 800 km, θ* = −90°', dict(body='Moon', combo='r_p + |a|', rp=Mo['R'] + 800, a_abs=7050.0, ths=-90.0),
    [X('e', lambda r: S(r, 'e'), 1.36003), X('δ', lambda r: S(r, 'δ'), 94.6616), X('b', lambda r: S(r, 'b'), 6498.54), X('γ(−90°)', lambda r: S(r, 'γ'), -53.6737), X('H', lambda r: S(r, 'H'), -0.824968),
     X('θ*_aim', lambda r: S(r, 'θ*_aim'), -47.3308), X('r_aim', lambda r: S(r, 'r_aim'), 3117.02)]))
add('5', Preset('HW6 P1 — lunar hyperbola, |a| = 16R, e = 1.25', dict(body='Moon', combo='|a| + e', a_abs=16 * Mo['R'], e=1.25, ths=-90.0),
    [X('δ', lambda r: S(r, 'δ'), 106.2602), X('v∞', lambda r: S(r, 'v∞'), 0.4199, 5e-4), X('b/R', lambda r: S(r, 'b') / Mo['R'], 12.0), X('d_aim/R', lambda r: S(r, 'd_aim') / Mo['R'], 16.0)]))

# ------------------------------------------------------------------ Module 6
_r5, _v5, _ = rv_from_elements(B['Earth']['mu'], 66 * RE, 0.9118, 34, 60, 0, 235)
add('6', Preset('HW5 P3 — elements → state (θ = 235° is the argument of latitude)', dict(body='Earth', mode='elements', a=66 * RE, e=0.9118, inc=34.0, Om=60.0, om=0.0, ang_kind='θ', ang=235.0),
    [X(f'r_{k}/R⊕', (lambda r, i=i: dd(r, 'rvec')[i] / RE), ex) for i, (k, ex) in enumerate(zip('xyz', [7.0303, -19.5110, -10.6869]))] +
    [X(f'v_{k}', (lambda r, i=i: dd(r, 'vvec')[i]), ex, 5e-4) for i, (k, ex) in enumerate(zip('xyz', [0.3951, 2.0133, 0.4482]))] +
    [X('E (0–360°)', lambda r: wrap360(dd(r, 'E')), 315.157), X('M (0–360°)', lambda r: wrap360(dd(r, 'M')), 351.997)]))
add('6', Preset('HW5 P4 — state → elements (corrected Ω = 65.20°)', dict(body='Earth', mode='state', r=list(np.array([2.12, 2.73, -0.6]) * RE), v=[-3.4, 1.62, 2.9]),
    [X('a', lambda r: dd(r, 'a'), 30582.31), X('e', lambda r: dd(r, 'e'), 0.3746), X('i', lambda r: dd(r, 'inc'), 37.5983), X('θ', lambda r: dd(r, 'theta'), 343.7207), X('ω', lambda r: dd(r, 'om'), 45.8840),
     X('θ*', lambda r: dd(r, 'ths'), -62.1632), X('Ω (corrected)', lambda r: dd(r, 'Om'), 65.1963)],
    note='Erratum: the solution prints Ω = 114.80°; sinΩ sin i = +0.5538 and −cosΩ sin i = −0.2560 put Ω in quadrant I: 65.20°.'))
_R_ = Mo['R']
add('6', Preset('HW6 P1 — lunar hyperbola in 3-D at θ* = −120°', dict(body='Moon', mode='elements', a=-16 * _R_, e=1.25, inc=45.0, Om=60.0, om=90.0, ang_kind='θ*', ang=-120.0),
    [X(f'r_{k}/R', (lambda r, i=i: dd(r, 'rvec')[i] / _R_), ex) for i, (k, ex) in enumerate(zip('xyz', [17.7408, 13.7574, -8.4853]))] +
    [X(f'v_{k}', (lambda r, i=i: dd(r, 'vvec')[i]), ex, 5e-4) for i, (k, ex) in enumerate(zip('xyz', [-0.5069, -0.1923, 0.3428]))]))

# ------------------------------------------------------------------ Module 7
best = lambda r: r.data['best']
add('7', Preset('HW6 P2a — circularize at apogee (r_p = 7000, r_a = 45000 km)', dict(body='Earth', sub='target orbit (find intersections)', o1_mode='r_p, r_a', o1_rp=7000.0, o1_ra=45000.0, o2_mode='circular r', o2_r=45000.0),
    [X('Δv', lambda r: best(r)['dv'], 1.4319)]))
add('7', Preset('HW6 P2b — circularize at r = 25 000 km', dict(body='Earth', sub='target orbit (find intersections)', o1_mode='r_p, r_a', o1_rp=7000.0, o1_ra=45000.0, o2_mode='circular r', o2_r=25000.0),
    [X('θ*', lambda r: best(r)['th1'], 134.8508), X('Δv', lambda r: best(r)['dv'], 3.2098), X('α', lambda r: best(r)['alpha'], -114.7013), X('% energy', lambda r: best(r)['pct_energy'], 2.3698, 1e-3)]))
add('7', Preset('HW7 P1 — raise r_p, lower r_a, advance perigee 90°', dict(body='Earth', sub='target orbit (find intersections)', o1_mode='a, e', o1_a=4.75 * RE, o1_e=6.5 / 9.5, o2_mode='a, e', o2_a=4 * RE, o2_e=0.5, d_omega=90.0),
    [X('Δγ', lambda r: best(r)['dgamma'], -34.1474), X('α', lambda r: best(r)['alpha'], -(180 - 70.4698))]))
add('7', Preset('HW7 P2 — Δv = 1, α = 45°, β = 60° at θ* = 150°', dict(body='Earth', sub='given Δv, α, β', g_a=8 * RE, g_e=0.7, g_inc=30.0, g_Om=60.0, g_om=90.0, g_ths=150.0, g_dv=1.0, g_alpha=45.0, g_beta=60.0),
    [X('Δv_r', lambda r: r.get('Δv̄_rθh')[0], 0.4991, 5e-4), X('Δv_θ', lambda r: r.get('Δv̄_rθh')[1], 0.0294, 5e-3), X('a⁺/R⊕', lambda r: dd(r, 'new')['a'] / RE, 11.6729), X('e⁺', lambda r: dd(r, 'new')['e'], 0.7257),
     X('i⁺', lambda r: dd(r, 'new')['inc'], 28.47), X('Ω⁺', lambda r: dd(r, 'new')['Om'], 358.68), X('ω⁺', lambda r: dd(r, 'new')['om'], 164.69), X('θ*⁺', lambda r: dd(r, 'new')['ths'], 130.03)]))

# ------------------------------------------------------------------ Module 8
Pl = B['Pluto']
add('8', Preset('HW7 P3 — Earth → Pluto Hohmann (circular Pluto)', dict(body='Sun', r1=B['Earth']['a'], r2=Pl['a']),
    [X('Δv₁', lambda r: dd(r, 'hohmann')['dv1'], 11.8138), X('Δv₂', lambda r: dd(r, 'hohmann')['dv2'], 3.6864), X('TOF [yr]', lambda r: dd(r, 'hohmann')['tof'] / 86400 / 365.25, 45.5412),
     X('phase', lambda r: dd(r, 'hohmann')['phase'], 113.9276), X('synodic [yr]', lambda r: dd(r, 'hohmann')['synodic'] / 86400 / 365.25, 1.0041)]))
add('8', Preset('HW7 P3(e) — arrive at Pluto’s perihelion (actual perihelion speed)', dict(body='Sun', r1=B['Earth']['a'], r2=Pl['a'], e_t=Pl['e'], arrive='perihelion'),
    [X('Δv₂ (target perihelion speed)', lambda r: dd(r, 'dv2'), 4.7149), X('total Δv', lambda r: dd(r, 'dv_total'), 16.3595)],
    note='Erratum: the solution labels "v_sJ = 4.7399"; the perihelion speed 6.1117 km/s is what gives Δv₂ = 4.7149.'))
add('8', Preset('HW8 P2 — LEO → 18R⊕ Hohmann and bi-elliptic via 66R⊕', dict(body='Earth', r1=1.04 * RE, r2=18 * RE, rb=66 * RE),
    [X('Hohmann Δv', lambda r: dd(r, 'hohmann')['dv'], 4.1548), X('Hohmann phase', lambda r: dd(r, 'hohmann')['phase'], 110.7660), X('synodic [h]', lambda r: dd(r, 'hohmann')['synodic'] / 3600, 1.5145),
     X('bi-elliptic Δv', lambda r: dd(r, 'bielliptic')['dv'], 4.0637), X('bi-elliptic TOF [d]', lambda r: dd(r, 'bielliptic')['tof'] / 86400, 13.6784), X('bi-elliptic phase', lambda r: S(r, 'φ_bi'), 341.0145)]))

# ------------------------------------------------------------------ Module 9
add('9', Preset('HW8 P3 — 90° plane change at the Moon, single vs three burns', dict(body='Moon', o_mode='circular r', r=Mo['R'] + 100, d_inc=90.0, r_apo=19000.0),
    [X('single-burn Δv', lambda r: dd(r, 'dv_single'), 2.3096), X('three-burn Δv', lambda r: dd(r, 'bi')['dv'], 1.4462), X('three-burn TOF [h]', lambda r: dd(r, 'bi')['tof'] / 3600, 26.5094)]))

# ------------------------------------------------------------------ Module 10
_hP = hohmann(Sun['mu'], B['Earth']['a'], Pl['a'])
for _e, _x, _t in ((0.0, 3.4301, 'circular'), (0.9, 3.3252, 'e = 0.9')):
    add('10', Preset(f'HW8 P4 — Earth → Pluto, 250 km parking orbit, capture at 11R♇ ({_t})',
                     dict(central='Sun', dep='Earth', arr='Pluto', r_dep=B['Earth']['a'], r_arr=Pl['a'], r_park=RE + 250, r_cap=11 * Pl['R'], e_cap=_e, tkind='Hohmann'),
                     [X('departure Δv', lambda r: dd(r, 'dv_dep'), 8.3647), X('capture Δv', lambda r: dd(r, 'dv_cap'), _x)]))

# ------------------------------------------------------------------ Module 11
_hM = hohmann(B['Earth']['mu'], RE + 175, Mo['a'])
add('11', Preset('HW9 P2 — Earth → Moon Hohmann, flyby 120 km above the Moon (counter-clockwise pass)',
                 dict(central='Earth', planet='Moon', r_pl=Mo['a'], sub='flyby', vm_mode='v_r, v_θ', vr=0.0, vt=_hM['va'], rp=Mo['R'] + 120, sense='ccw'),
                 [X('δ', lambda r: dd(r, 'outs')[1]['fb']['hyp']['delta'], 104.7878), X('γ⁺', lambda r: np.degrees(np.arctan2(*dd(r, 'outs')[1]['fb']['v_plus'])), 33.16752),
                  X('e⁺', lambda r: dd(r, 'outs')[1]['c']['e'], 1.05981), X('θ*⁺', lambda r: dd(r, 'outs')[1]['c']['ths'], 64.2463), X('Δv_eq', lambda r: dd(r, 'outs')[1]['fb']['dv_eq_mag'], 1.3180)]))
_rE, _rV, _rMe = B['Earth']['a'], B['Venus']['a'], B['Mercury']['a']; _aT = (_rE + _rMe) / 2; _eT = (_rE - _rMe) / (_rE + _rMe); _pT = _aT * (1 - _eT ** 2)
_thV = -np.degrees(np.arccos((_pT / _rV - 1) / _eT)); _vv = v_of(Sun['mu'], _rV, _aT); _gg = float(gamma_of(_eT, _thV))
add('11', Preset('HW9 P4 — Venus flyby (4R♀) on an Earth → Mercury Hohmann, losing energy',
                 dict(central='Sun', planet='Venus', r_pl=_rV, sub='flyby', vm_mode='v, γ', vmag=_vv, gamma=_gg, rp=4 * V_['R'], sense='lose'),
                 [X('θ*⁻ at Venus', lambda r: dd(r, 'c_old')['ths'], -121.12, 1e-3), X('v⁻', lambda r: np.linalg.norm(dd(r, 'vm')), 34.26, 1e-3), X('γ⁻', lambda r: dd(r, 'c_old')['gamma'], -26.12, 1e-3),
                  X('v∞', lambda r: S(r, 'v∞'), 15.67, 1e-3), X('δ', lambda r: S(r, 'δ'), 5.9406), X('v⁺', lambda r: np.linalg.norm(dd(r, 'outs')[dd(r, 'pick')]['fb']['v_plus']), 32.65, 1e-3),
                  X('e⁺', lambda r: dd(r, 'outs')[dd(r, 'pick')]['c']['e'], 0.4610, 1e-3), X('Δω', lambda r: dd(r, 'outs')[dd(r, 'pick')]['dw'], 10.07, 1e-3),
                  X('Δv_eq', lambda r: dd(r, 'outs')[dd(r, 'pick')]['fb']['dv_eq_mag'], 1.62, 3e-3)]))
add('11', Preset('HW9 P3 — free return, TA = 174° from a 180 km parking orbit', dict(central='Earth', planet='Moon', r_pl=Mo['a'], sub='free return', r_park=RE + 180, TA=174.0),
    [X('e', lambda r: dd(r, 'e'), 0.9717), X('TOF [d]', lambda r: dd(r, 'tof') / 86400, 3.2769), X('γ⁻', lambda r: S(r, 'γ⁻'), 71.6757), X('v∞', lambda r: dd(r, 'vinf'), 1.0047),
     X('δ', lambda r: dd(r, 'delta'), 68.2877), X('r_p at the Moon', lambda r: dd(r, 'rp'), 3796.4, 5e-4), X('Δv_eq', lambda r: S(r, 'Δv_eq'), 1.1278)]))

# ------------------------------------------------------------------ Module 12
_r1, _, _ = rv_from_elements(B['Earth']['mu'], 4 * RE, 0, 28.5, 60, 0, 0); _r2, _, _ = rv_from_elements(B['Earth']['mu'], 6 * RE, 0, 45, 60, 0, 120)
add('12', Preset('HW10 P1 — two 3-D position vectors, p = 5R⊕', dict(body='Earth', pos_kind='vectors', r1v=list(_r1), r2v=list(_r2), t_mode='given p', p=5 * RE),
    [X(f'v_{k}', (lambda r, i=i: dd(r, 'v1_xyz')[i]), ex, 5e-4) for i, (k, ex) in enumerate(zip('xyz', [-2.6212, 1.7097, 3.1249]))] +
    [X('a', lambda r: dd(r, 'sel')['a'], 34100.93), X('e', lambda r: dd(r, 'sel')['e'], 0.2546), X('θ*₁', lambda r: dd(r, 'sel')['thD'], 10.89, 1e-3), X('TOF [h]', lambda r: dd(r, 'tof') / 3600, 4.8173)],
    note='Erratum: the solution prints a = 5.36 R⊕; a = 34 100.93 km = 5.3465 R⊕.'))
add('12', Preset('HW10 P2 — 2R⊕ → 6R⊕, minimum-energy Lambert, TA = 240°', dict(body='Earth', pos_kind='radii', r1=2 * RE, r2=6 * RE, TA=240.0, t_mode='minimum energy'),
    [X('α_D', lambda r: dd(r, 'sel')['alphaD'], -76.1538), X('Δv_D along V̂', lambda r: dd(r, 'sel')['dvD'][1], 0.6550, 5e-4), X('Δv_D along B̂', lambda r: -dd(r, 'sel')['dvD'][0], 2.6574)]))
add('12', Preset('HW10 P3 — Earth → Mars, minimum energy, TA = 130°', dict(body='Sun', pos_kind='radii', r1=B['Earth']['a'], r2=B['Mars']['a'], TA=130.0, t_mode='minimum energy'),
    [X('e', lambda r: dd(r, 'sel')['e'], 0.31037), X('TOF_min [d]', lambda r: dd(r, 'sel')['tof'] / 86400, 240.64357), X('v_D', lambda r: dd(r, 'sel')['vD_mag'], 32.22270), X('θ*_D', lambda r: dd(r, 'sel')['thD'], 73.27991),
     X('γ_A', lambda r: dd(r, 'sel')['gA'], -9.73645), X('phase ψ', lambda r: dd(r, 'psi'), 3.89746), X('v∞ (= |Δv_D|)', lambda r: dd(r, 'sel')['dvD_mag'], 8.58217)]))
add('12', Preset('Lecture notes LLex 1 — general Lambert (type 1B), TOF = 15 h', dict(body='Earth', pos_kind='radii', r1=1.25 * RE, r2=4 * RE, TA=120.0, t_mode='tof', tof_h=15.0, root='small'),
    [X('a', lambda r: dd(r, 'sel')['a'], 32815.67), X('p (smaller root)', lambda r: dd(r, 'sel')['p'], 7258.09), X('|Δv_D|', lambda r: dd(r, 'sel')['dvD_mag'], 6.514, 5e-4)],
    note='Erratum (lecture notes LLex 1): the printed e = 0.8225 and ΔV_D,y = −3.24 should be 0.8825 and −0.324.'))
add('12', Preset('Lecture notes LLex 2 — Mars-centered, TA = 240° (type 2B), larger p root', dict(body='Mars', pos_kind='radii', r1=9376.0, r2=23458.0, TA=240.0, t_mode='tof', tof_h=25.419, root='large'),
    [X('a', lambda r: dd(r, 'sel')['a'], 23298.0, 5e-4), X('p (larger root)', lambda r: dd(r, 'sel')['p'], 14944.6, 5e-4), X('total Δv', lambda r: dd(r, 'sel')['dv_total'], 1.4268, 5e-4)],
    note='Erratum (lecture notes LLex 2): TOF_min(Phobos → Deimos) is 8.210 h, not 5.705 h.'))
add('12', Preset('Lecture notes LLex 2 — Earth → Mars heliocentric, TOF = 90 d (type 1H)', dict(body='Sun', pos_kind='radii', r1=1.496e8, r2=2.2795e8, TA=140.0, t_mode='tof', tof_h=90 * 24.0, root='large'),
    [X('a', lambda r: dd(r, 'sel')['a'], -3.0252e8, 5e-4), X('TOF_par [d]', lambda r: dd(r, 'sel')['tof_par'] / 86400, 104.62, 5e-4)]))
