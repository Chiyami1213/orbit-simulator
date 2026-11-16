"""Regression tests: every expected value is copied from the AAE 532 HW/exam solution PDFs or lecture notes LLex.
Run: python test_hw.py   (prints PASS/FAIL per check; tolerance is relative 2e-4 unless noted)"""
import numpy as np
from orbitcore import *

B = BODIES; muE = B['Earth']['mu']; RE = B['Earth']['R']; muS = B['Sun']['mu']
results = []
def chk(name, got, exp, rtol=2e-4, atol=0.0):
    ok = abs(got - exp) <= max(atol, rtol * abs(exp)); results.append(ok)
    print(f"{'PASS' if ok else 'FAIL'}  {name:<48} got {got:<14.6g} expected {exp:.6g}")

# HW3 P3: state (alt, vr, vt) -> conic
c = conic_from_rv_polar(muE, RE + 8560, -2.11, 4.89)
chk('HW3P3 a', c['a'], 15942.3); chk('HW3P3 p', c['p'], 13386.7); chk('HW3P3 e', c['e'], 0.4004)
chk('HW3P3 P', c['P'], 20032.7); chk('HW3P3 th* (=254.97)', wrap360(c['ths']), 254.97); chk('HW3P3 gamma', c['gamma'], -23.340)

# HW4 P1: Anteros, elements -> state, propagate 6.4 months (30-day months)
a = 1.43018128 * AU; e = 0.2576460; p = a * (1 - e * e)
chk('HW4P1 p [AU]', p / AU, 1.33524); chk('HW4P1 r0 [AU]', r_of(p, e, 118.65) / AU, 1.52343)
chk('HW4P1 v0', v_of(muS, r_of(p, e, 118.65), a), 23.3313); chk('HW4P1 gamma0', gamma_of(e, 118.65), 14.4651)
chk('HW4P1 E0', E_from_th(e, 118.65 * D2R) * R2D, 104.6595)
th1 = propagate(muS, a, e, 118.65, 6.4 * 30 * 86400)
chk('HW4P1 th1* (=192.916)', wrap360(th1), 192.9160); chk('HW4P1 gamma1', gamma_of(e, th1), -4.39749)

# HW4 P2: M0 = 90 deg, e = .75, a = 8 RE; +2 h
a = 8 * RE; e = 0.75; E0 = kepler_E(np.pi / 2, e); th0 = th_from_E(e, E0) * R2D
chk('HW4P2 E0', E0 * R2D, 125.1401); chk('HW4P2 th0*', th0, 157.8026); chk('HW4P2 gamma', gamma_of(e, th0), 42.8379)
chk('HW4P2 t-tp [h]', time_since_periapsis(muE, a, e, th0) / 3600, 7.9657)
chk('HW4P2 th* after 2 h', propagate(muE, a, e, th0, 7200), 164.3925)

# HW4 P3: Venus hyperbola
V = B['Venus']; hy = hyperbola(V['mu'], a_abs=50 * V['R'], rp=10 * V['R'])
chk('HW4P3 vinf', hy['vinf'], 1.0361349); chk('HW4P3 th_inf', hy['th_inf'], 146.44269); chk('HW4P3 delta', hy['delta'], 112.88538)
chk('HW4P3 b', hy['b'], 200718.81569); r = r_of(hy['p'], hy['e'], -110)
chk('HW4P3 r(-110)/R', r / V['R'], 37.31496); chk('HW4P3 gamma(-110)', gamma_of(hy['e'], -110), -62.397426)
chk('HW4P3 H', H_from_th(hy['e'], -110 * D2R), -0.921273); chk('HW4P3 tp-t [h]', -time_since_periapsis(V['mu'], hy['a'], hy['e'], -110) / 3600, 28.18302)
th_aim = -(hy['th_inf'] - 90); chk('HW4P3 th_aim', th_aim, -56.44269); chk('HW4P3 r_aim/R', r_of(hy['p'], hy['e'], th_aim) / V['R'], 13.226519)
chk('HW4P3 capture dv', hy['vp'] - np.sqrt(V['mu'] / hy['rp']), 1.119603)

# HW5 P1: Mars, M0 = -120, dt = 0.75 P, f and g (E form)
M_ = B['Mars']; rp, ra = 1.8 * M_['R'], 8 * M_['R']; a = (rp + ra) / 2; e = (ra - rp) / (ra + rp); p = a * (1 - e * e)
P = 2 * np.pi * np.sqrt(a ** 3 / M_['mu']); E0 = kepler_E(-120 * D2R, e); th0 = th_from_E(e, E0) * R2D; r0 = r_of(p, e, th0)
chk('HW5P1 E0', E0 * R2D, -142.2112); chk('HW5P1 th0*', th0, -161.5568); chk('HW5P1 gamma0', gamma_of(e, th0), -26.5912)
th1 = propagate(M_['mu'], a, e, th0, 0.75 * P); E1 = E_from_th(e, th1 * D2R); r1 = r_of(p, e, th1)
chk('HW5P1 th1*', th1, 171.1657); chk('HW5P1 E1', E1 * R2D, 161.5011); chk('HW5P1 gamma1', gamma_of(e, th1), 14.5312)
f, g, fdg = fg_E(M_['mu'], a, r0, (E1 - E0) % (2 * np.pi), 0.75 * P); fd, gd = fdg(r1)
chk('HW5P1 f', f, 0.7033, 5e-4); chk('HW5P1 g', g, -1.4738e4, 5e-4); chk('HW5P1 fdot', fd, 3.3402e-5, 5e-4); chk('HW5P1 gdot', gd, 0.7219, 5e-4)

# HW5 P2: lunar hyperbola
Mo = B['Moon']; hy = hyperbola(Mo['mu'], a_abs=7050, rp=Mo['R'] + 800)
chk('HW5P2 e', hy['e'], 1.36003); chk('HW5P2 delta', hy['delta'], 94.6616); chk('HW5P2 b', hy['b'], 6498.54)
chk('HW5P2 gamma(-90)', gamma_of(hy['e'], -90), -53.6737); chk('HW5P2 H', H_from_th(hy['e'], -90 * D2R), -0.824968)
th_aim = -(hy['th_inf'] - 90); chk('HW5P2 th_aim', th_aim, -47.3308); chk('HW5P2 r_aim', r_of(hy['p'], hy['e'], th_aim), 3117.02)

# HW5 P3: elements -> 3D state (theta = 235 = argument of latitude)
r, v, _ = rv_from_elements(muE, 66 * RE, 0.9118, 34, 60, 0, 235)
for k, ex in zip('xyz', [7.0303, -19.5110, -10.6869]): chk(f'HW5P3 r_{k}/RE', r['xyz'.index(k)] / RE, ex)
for k, ex in zip('xyz', [0.3951, 2.0133, 0.4482]): chk(f'HW5P3 v_{k}', v['xyz'.index(k)], ex, 5e-4)
el = elements_from_rv(muE, r, v); chk('HW5P3 E (0..360)', wrap360(el['E']), 315.157); chk('HW5P3 M (0..360)', wrap360(el['M']), 351.997)

# HW5 P4: 3D state -> elements (solution prints Omega = 114.80; correct is 65.20, see errata)
el = elements_from_rv(muE, np.array([2.12, 2.73, -0.6]) * RE, np.array([-3.4, 1.62, 2.9]))
chk('HW5P4 a', el['a'], 30582.31); chk('HW5P4 e', el['e'], 0.3746); chk('HW5P4 i', el['inc'], 37.5983)
chk('HW5P4 theta', el['theta'], 343.7207); chk('HW5P4 omega', el['om'], 45.8840); chk('HW5P4 th*', el['ths'], -62.1632)
chk('HW5P4 Omega (corrected)', el['Om'], 65.1963)

# HW6 P1: lunar hyperbola from r = -9R p_hat, v^2 = 41/144 mu/R; 3D orientation
R = Mo['R']; a_abs = 16 * R; e = 1.25; hy = hyperbola(Mo['mu'], a_abs=a_abs, e=e)
chk('HW6P1 delta', hy['delta'], 106.2602); chk('HW6P1 vinf', hy['vinf'], 0.4199, 5e-4); chk('HW6P1 b/R', hy['b'] / R, 12.0)
chk('HW6P1 d_aim/R = sqrt((rp+|a|)^2-b^2)', np.sqrt((hy['rp'] + a_abs) ** 2 - hy['b'] ** 2) / R, 16.0)
r1, v1, _ = rv_from_elements(Mo['mu'], -a_abs, e, 45, 60, 90, -120)
for k, ex in zip('xyz', [17.7408, 13.7574, -8.4853]): chk(f'HW6P1 r_{k}/R (th*=-120)', r1['xyz'.index(k)] / R, ex)
for k, ex in zip('xyz', [-0.5069, -0.1923, 0.3428]): chk(f'HW6P1 v_{k} (th*=-120)', v1['xyz'.index(k)], ex, 5e-4)

# HW6 P2: circularize at apogee / at r = 25000
rp, ra = 7000, 45000; a = (rp + ra) / 2; e = (ra - rp) / (ra + rp); p = a * (1 - e * e)
chk('HW6P2a dv', np.sqrt(muE / ra) - v_of(muE, ra, a), 1.4319)
ths = np.arccos((p / 25000 - 1) / e) * R2D; imp = impulse_planar(v_of(muE, 25000, a), gamma_of(e, ths), np.sqrt(muE / 25000), 0)
chk('HW6P2b th*', ths, 134.8508); chk('HW6P2b dv', imp['dv'], 3.2098); chk('HW6P2b alpha', imp['alpha'], -114.7013)
chk('HW6P2b %energy', abs(np.sqrt(muE / 25000) - v_of(muE, 25000, a)) / imp['dv'] * 100, 2.3698, 1e-3)

# HW7 P1: raise rp, lower ra, advance perigee 90 deg
a1 = 4.75 * RE; e1 = 6.5 / 9.5; p1 = a1 * (1 - e1 * e1); a2 = 4 * RE; e2 = 0.5; p2 = a2 * (1 - e2 * e2)
best = min(intersect_conics(p1, e1, p2, e2, 90), key=lambda t: impulse_planar(v_of(muE, r_of(p1, e1, t), a1), gamma_of(e1, t), v_of(muE, r_of(p1, e1, t), a2), gamma_of(e2, t - 90))['dv'])
rr = r_of(p1, e1, best); imp = impulse_planar(v_of(muE, rr, a1), gamma_of(e1, best), v_of(muE, rr, a2), gamma_of(e2, best - 90))
chk('HW7P1 dgamma', imp['dgamma'], -34.1474); chk('HW7P1 alpha', imp['alpha'], -(180 - 70.4698))

# HW7 P2: 3D impulse dv=1, alpha=45, beta=60 at th*=150 -> new elements
r, v, info = rv_from_elements(muE, 8 * RE, 0.7, 30, 60, 90, 150); vn, dvec = apply_dv_vnc(r, v, 1.0, 45, 60)
chk('HW7P2 dv_r', dvec @ info['C'][:, 0], 0.4991, 5e-4); chk('HW7P2 dv_theta', dvec @ info['C'][:, 1], 0.0294, 5e-3)
el = elements_from_rv(muE, r, vn)
chk('HW7P2 a+/RE', el['a'] / RE, 11.6729); chk('HW7P2 e+', el['e'], 0.7257); chk('HW7P2 i+', el['inc'], 28.47)
chk('HW7P2 Omega+', el['Om'], 358.68); chk('HW7P2 omega+', el['om'], 164.69); chk('HW7P2 th*+', el['ths'], 130.03)

# HW7 P3 / HW8 P4: Earth -> Pluto Hohmann, with and without local fields, eccentric Pluto perihelion
h = hohmann(muS, B['Earth']['a'], B['Pluto']['a'])
chk('HW7P3 dv1', h['dv1'], 11.8138); chk('HW7P3 dv2', h['dv2'], 3.6864); chk('HW7P3 TOF [yr]', h['tof'] / 86400 / 365.25, 45.5412)
chk('HW7P3 phase', h['phase'], 113.9276); chk('HW7P3 synodic [yr]', h['synodic'] / 86400 / 365.25, 1.0041)
rpP = B['Pluto']['a'] * (1 - B['Pluto']['e']); h2 = hohmann(muS, B['Earth']['a'], rpP)
chk('HW7P3e arrival dv (Pluto perihelion speed)', np.sqrt(muS * (2 / rpP - 1 / B['Pluto']['a'])) - h2['va'], 4.7149)
chk('HW8P4 dv_dep (250 km)', escape_dv(muE, RE + 250, h['dv1']), 8.3647)
chk('HW8P4 dv_arr circ 11R', capture_dv(B['Pluto']['mu'], 11 * B['Pluto']['R'], h['dv2']), 3.4301)
chk('HW8P4 dv_arr e=0.9', capture_dv(B['Pluto']['mu'], 11 * B['Pluto']['R'], h['dv2'], 0.9), 3.3252)
fb = flyby(B['Pluto']['mu'], np.array([0, h['vc2']]), np.array([0, h['va']]), 11 * B['Pluto']['R'], +1)
chk('HW8P4 flyby delta', fb['hyp']['delta'], 0.6439, 5e-4); chk('HW8P4 dv_eq', fb['dv_eq_mag'], 0.04143, 5e-4)

# HW8 P2: LEO -> 18 RE Hohmann and bi-elliptic via 66 RE
h = hohmann(muE, 1.04 * RE, 18 * RE); b = bielliptic(muE, 1.04 * RE, 18 * RE, 66 * RE)
chk('HW8P2 Hohmann dv', h['dv'], 4.1548); chk('HW8P2 phase', h['phase'], 110.7660); chk('HW8P2 synodic [h]', h['synodic'] / 3600, 1.5145)
chk('HW8P2 bi dv', b['dv'], 4.0637); chk('HW8P2 bi TOF [d]', b['tof'] / 86400, 13.6784)
chk('HW8P2 bi phase', (2 * np.pi - np.sqrt(muE / (18 * RE) ** 3) * b['tof']) * R2D % 360, 341.0145)

# HW8 P3: 90 deg plane change at Moon, single vs bi-elliptic (ra = 19000 km radius)
r = Mo['R'] + 100; vc = np.sqrt(Mo['mu'] / r); chk('HW8P3 single', plane_change(vc, 90), 2.3096)
a1 = (r + 19000) / 2; d1 = np.sqrt(Mo['mu'] * (2 / r - 1 / a1)) - vc; d2 = plane_change(np.sqrt(Mo['mu'] * (2 / 19000 - 1 / a1)), 90)
chk('HW8P3 bi total', 2 * d1 + d2, 1.4462); chk('HW8P3 bi TOF [h]', 2 * np.pi * np.sqrt(a1 ** 3 / Mo['mu']) / 3600, 26.5094)

# HW9 P2: Earth -> Moon Hohmann, capture, flyby without capture
h = hohmann(muE, RE + 175, Mo['a']); vinf = h['vc2'] - h['va']
chk('HW9P2 dv1', h['dv1'], 3.1377); chk('HW9P2 TOF [d]', h['tof'] / 86400, 4.9775); chk('HW9P2 phase', h['phase'], 114.7261)
chk('HW9P2 capture 120 km', capture_dv(Mo['mu'], Mo['R'] + 120, vinf), 0.81880)
fb = flyby(Mo['mu'], np.array([0, h['vc2']]), np.array([0, h['va']]), Mo['R'] + 120, +1); c = conic_from_rv_polar(muE, Mo['a'], *fb['v_plus'])
chk('HW9P2 delta', fb['hyp']['delta'], 104.7878); chk('HW9P2 gamma+', np.arctan2(*fb['v_plus']) * R2D, 33.16752)
chk('HW9P2 e+', c['e'], 1.05981); chk('HW9P2 th*+', c['ths'], 64.2463); chk('HW9P2 dv_eq', fb['dv_eq_mag'], 1.3180)

# HW9 P3b: free return, TA = 174 deg from 180 km parking orbit
r1 = 180 + RE; r2 = Mo['a']; e = (r2 - r1) / (r1 - r2 * np.cos(174 * D2R)); p = r1 * (1 + e); a = p / (1 - e * e)
v2 = v_of(muE, r2, a); g = gamma_of(e, 174); vm = np.array([v2 * np.sin(g * D2R), v2 * np.cos(g * D2R)]); vpl = np.array([-vm[0], vm[1]])
wi = vm - np.array([0, np.sqrt(muE / r2)]); wo = vpl - np.array([0, np.sqrt(muE / r2)]); vinf = np.linalg.norm(wi)
delta = np.arccos(wi @ wo / vinf ** 2); rpH = Mo['mu'] / vinf ** 2 * (1 / np.sin(delta / 2) - 1)
chk('HW9P3 e', e, 0.9717); chk('HW9P3 TOF [d]', time_since_periapsis(muE, a, e, 174) / 86400, 3.2769); chk('HW9P3 gamma-', g, 71.6757)
chk('HW9P3 vinf', vinf, 1.0047); chk('HW9P3 delta', delta * R2D, 68.2877); chk('HW9P3 rp_H', rpH, 3796.4, 5e-4); chk('HW9P3 dv_eq', np.linalg.norm(vpl - vm), 1.1278)

# HW9 P4: Venus flyby on Earth -> Mercury Hohmann (4 R_Venus), lose energy
rE, rV, rMe = B['Earth']['a'], B['Venus']['a'], B['Mercury']['a']; aT = (rE + rMe) / 2; eT = (rE - rMe) / (rE + rMe); pT = aT * (1 - eT * eT)
thV = -np.arccos((pT / rV - 1) / eT) * R2D; v = v_of(muS, rV, aT); g = gamma_of(eT, thV)
chk('HW9P4 th*_V', thV, -121.12, 1e-3); chk('HW9P4 v-', v, 34.26, 1e-3); chk('HW9P4 gamma-', g, -26.12, 1e-3)
fb = flyby(B['Venus']['mu'], np.array([0, np.sqrt(muS / rV)]), np.array([v * np.sin(g * D2R), v * np.cos(g * D2R)]), 4 * B['Venus']['R'], +1)
c = conic_from_rv_polar(muS, rV, *fb['v_plus'])
chk('HW9P4 vinf', fb['vinf'], 15.67, 1e-3); chk('HW9P4 delta', fb['hyp']['delta'], 5.9406); chk('HW9P4 v+', np.linalg.norm(fb['v_plus']), 32.65, 1e-3)
chk('HW9P4 e+', c['e'], 0.4610, 1e-3); chk('HW9P4 d_omega', thV - c['ths'], 10.07, 1e-3); chk('HW9P4 dv_eq', fb['dv_eq_mag'], 1.62, 3e-3)

# HW10 P1: two 3D position vectors, p = 5 RE
r1, _, _ = rv_from_elements(muE, 4 * RE, 0, 28.5, 60, 0, 0); r2, _, _ = rv_from_elements(muE, 6 * RE, 0, 45, 60, 0, 120)
T = two_vector_transfer(muE, r1, r2, 5 * RE); el = T['el']
for k, ex in zip('xyz', [-2.6212, 1.7097, 3.1249]): chk(f'HW10P1 v1_{k}', T['v1']['xyz'.index(k)], ex, 5e-4)
chk('HW10P1 a', el['a'], 34100.93); chk('HW10P1 e', el['e'], 0.2546); chk('HW10P1 th1*', el['ths'], 10.89, 1e-3)
chk('HW10P1 TOF [h]', (time_since_periapsis(muE, el['a'], el['e'], el['ths'] + T['TA']) - el['t_tp']) / 3600, 4.8173)

# HW10 P2: 2 RE -> 6 RE; Hohmann and minimum-energy Lambert with TA = 240
h = hohmann(muE, 2 * RE, 6 * RE); L = lambert_minE(muE, 2 * RE, 6 * RE, 240)
chk('HW10P2 alphaD', L['alphaD'], -76.1538); chk('HW10P2 dvD V comp', L['dvD'][1], 0.6550, 5e-4); chk('HW10P2 dvD B comp', -L['dvD'][0], 2.6574)

# HW10 P3: Earth -> Mars, minimum energy, TA = 130
L = lambert_minE(muS, B['Earth']['a'], B['Mars']['a'], 130)
chk('HW10P3 e', L['e'], 0.31037); chk('HW10P3 TOF_min [d]', L['tof'] / 86400, 240.64357); chk('HW10P3 vD', L['vD_mag'], 32.22270)
chk('HW10P3 th*_D', L['thD'], 73.27991); chk('HW10P3 gamma_A', L['gA'], -9.73645)
chk('HW10P3 phase', (130 * D2R - np.sqrt(muS / B['Mars']['a'] ** 3) * L['tof']) * R2D, 3.89746)
chk('HW10P3 vinf', L['dvD_mag'], 8.58217); chk('HW10P3 dv_dep 250 km', escape_dv(muE, RE + 250, L['dvD_mag']), 6.17100)

# Lecture notes LLex 1-2: general Lambert (time of flight given)
L = lambert(398600.4415, 1.25 * 6378.1363, 4 * 6378.1363, 120, 15 * 3600, 'small')
chk('LLex1 a (1B)', L['a'], 32815.67); chk('LLex1 p small', L['p'], 7258.09); chk('LLex1 |dvD|', L['dvD_mag'], 6.514, 5e-4)
L = lambert(42828.37, 9376, 23458, 240, 25.419 * 3600, 'large')
chk('LLex2 a (2B)', L['a'], 23298.0, 5e-4); chk('LLex2 p large', L['p'], 14944.6, 5e-4); chk('LLex2 total dv', L['dv_total'], 1.4268, 5e-4)
L = lambert(1.32712440018e11, 1.496e8, 2.2795e8, 140, 90 * 86400, 'large')
chk('LLex2 Earth-Mars 1H a', L['a'], -3.0252e8, 5e-4); chk('LLex2 TOF_par [d]', L['tof_par'] / 86400, 104.62, 5e-4)

# Exams (rounded exam constants)
mu, R = EXAM['Earth']['mu'], EXAM['Earth']['R']
el = elements_from_rv(mu, np.array([-2 * R, 2 * np.sqrt(3) * R, 0]), np.array([-np.sqrt(mu / (4 * R)), 0, 0]))
chk('Exam1 P2 p/R', el['p'] / R, 3.0); chk('Exam1 P2 e', el['e'], 0.5); chk('Exam1 P2 th*', el['ths'], 120); chk('Exam1 P2 gamma', el['gamma'], 30)
m = 4.2e4; p = 2.5e4 ** 2 / m; a = -m / (2 * -1.2351)
chk('Exam1 P3 p/R', p / 3400, 4.377, 5e-4); chk('Exam1 P3 e', np.sqrt(1 - p / a), 0.3530, 1e-3); chk('Exam1 P3 parabola v(-90)', np.sqrt(2 * m / p), 2.3758, 5e-4)
m = 5000; p = 6000; e = 1 / np.sqrt(3); a = p / (1 - e * e); eN = 0.25; pN = p * (1 + eN * np.cos(-120 * D2R)); aN = pN / (1 - eN ** 2)
imp = impulse_planar(v_of(m, p, a), gamma_of(e, -90), v_of(m, p, aN), gamma_of(eN, -120))
chk('Exam2 P1 dv', imp['dv'], 0.32122); chk('Exam2 P1 alpha', imp['alpha'], 130.577)
T = two_vector_transfer(mu, np.array([np.sqrt(3) * R, -R, 0]), np.array([0, 2 * R, 2 * np.sqrt(3) * R]), 3 * R)
chk('Exam2 P2 TA', T['TA'], 104.478); chk('Exam2 P2 i', T['inc'], 63.435); chk('Exam2 P2 Omega', T['Om'], 330)
for k, ex in zip('xyz', [2.04119, 2.35691, 6.12348]): chk(f'Exam2 P2 v1_{k}', T['v1']['xyz'.index(k)], ex, 1e-3)
# Exam 2 P3: solution used n from course constants (8.24419 h); with exam constants 8.2721 h
a = 4 * 6378.1363; t1 = time_since_periapsis(398600.4415, a, 0.5, 90); t2 = time_since_periapsis(398600.4415, a, 0.5, -120) + 2 * np.pi * np.sqrt(a ** 3 / 398600.4415)
chk('Exam2 P3 TOF [h] (course constants)', (t2 - t1) / 3600, 8.24419)

print(f"\n{sum(results)}/{len(results)} checks passed")
