"""AAE 532 reference core: verified equations (lecture notes + BMW), used to cross-check HW solutions.
Conventions (course notes):
  gamma > 0 when r_dot > 0 (ascending);  tan(gamma) = e sin(th)/(1 + e cos(th))
  theta = omega + theta*  (argument of latitude);  3-1-3 rotation (Omega, i, theta)
  VNC: V = v/|v|, N = h/|h|, C = V x N  (GMAT 'VNB');  dv = dv(cos b cos a V + sin b N + cos b sin a C)
  alpha > 0 when the impulse rotates v away from the central body (toward C); beta out of plane
  r-theta-h: dv = dv(cos b sin Phi r + cos b cos Phi th + sin b h), Phi = alpha + gamma
"""
import numpy as np
D2R = np.pi / 180
R2D = 180 / np.pi

# Course "Useful Constants" table (GMAT 2020a / JPL)
BODIES = {
    'Sun':     dict(mu=132712440017.99, R=695990,    a=None),
    'Moon':    dict(mu=4902.8005821478, R=1738.2,    a=384400,     e=0.0554),
    'Mercury': dict(mu=22032.080486418, R=2439.7,    a=57909101,   e=0.20563661),
    'Venus':   dict(mu=324858.59882646, R=6051.9,    a=108207284,  e=0.00676399),
    'Earth':   dict(mu=398600.4415,     R=6378.1363, a=149597898,  e=0.01673163),
    'Mars':    dict(mu=42828.314258067, R=3397,      a=227944135,  e=0.09336511),
    'Jupiter': dict(mu=126712767.8578,  R=71492,     a=778279959,  e=0.04853590),
    'Saturn':  dict(mu=37940626.061137, R=60268,     a=1427387908, e=0.05550825),
    'Uranus':  dict(mu=5794549.0070719, R=25559,     a=2870480873, e=0.04685740),
    'Neptune': dict(mu=6836534.0638793, R=25269,     a=4498337290, e=0.00895439),
    'Pluto':   dict(mu=981.600887707,   R=1162,      a=5907150229, e=0.24885238),
}
EXAM = {'Earth': dict(mu=4.0e5, R=6400), 'Moon': dict(mu=5000, R=2000 / 1), 'Mars': dict(mu=4.2e4, R=3400)}
AU = 149597870.7

def wrap360(x): return x % 360
def wrap180(x): return (x + 180) % 360 - 180

# ---------------- planar conic ----------------
def conic_from_rv_polar(mu, r, vr, vt):
    """state in r-theta components -> conic (notes E/F: h = r vt, eps, p, e, gamma, theta* with quadrant from vr)."""
    v = np.hypot(vr, vt); h = r * vt; eps = v * v / 2 - mu / r
    p = h * h / mu; e = np.sqrt(max(0.0, 1 + 2 * eps * h * h / mu ** 2))
    a = -mu / (2 * eps) if abs(eps) > 1e-14 else np.inf
    gam = np.arctan2(vr, vt)
    th = np.arctan2(vr * h / mu, p / r - 1)          # e sin th = vr h / mu ; e cos th = p/r - 1
    out = dict(h=h, eps=eps, p=p, e=e, a=a, gamma=gam * R2D, ths=th * R2D, v=v)
    if e < 1:
        out['P'] = 2 * np.pi * np.sqrt(a ** 3 / mu); out['rp'] = a * (1 - e); out['ra'] = a * (1 + e)
        out['E'] = E_from_th(e, th) * R2D
    return out

def r_of(p, e, ths_deg): return p / (1 + e * np.cos(ths_deg * D2R))
def gamma_of(e, ths_deg):
    t = ths_deg * D2R; return np.arctan2(e * np.sin(t), 1 + e * np.cos(t)) * R2D
def v_of(mu, r, a): return np.sqrt(mu * (2 / r - 1 / a))

# ---------------- anomalies & Kepler ----------------
def E_from_th(e, th):  return 2 * np.arctan2(np.sqrt(1 - e) * np.sin(th / 2), np.sqrt(1 + e) * np.cos(th / 2))
def th_from_E(e, E):   return 2 * np.arctan2(np.sqrt(1 + e) * np.sin(E / 2), np.sqrt(1 - e) * np.cos(E / 2))
def H_from_th(e, th):  return 2 * np.arctanh(np.sqrt((e - 1) / (e + 1)) * np.tan(th / 2))
def th_from_H(e, H):   return 2 * np.arctan(np.sqrt((e + 1) / (e - 1)) * np.tanh(H / 2))
def kepler_E(M, e, tol=1e-13):
    E = M + e * np.sin(M) if e < 0.8 else np.pi * np.sign(np.sin(M) or 1)
    for _ in range(100):
        dE = (E - e * np.sin(E) - M) / (1 - e * np.cos(E)); E -= dE
        if abs(dE) < tol: break
    return E
def kepler_H(M, e, tol=1e-13):
    H = np.arcsinh(M / e) if e > 1 else M
    for _ in range(200):
        dH = (e * np.sinh(H) - H - M) / (e * np.cosh(H) - 1); H -= dH
        if abs(dH) < tol: break
    return H

def time_since_periapsis(mu, a, e, ths_deg):
    th = ths_deg * D2R
    if e < 1:
        n = np.sqrt(mu / a ** 3); E = E_from_th(e, th); return (E - e * np.sin(E)) / n
    n = np.sqrt(mu / abs(a) ** 3); H = H_from_th(e, th); return (e * np.sinh(H) - H) / n

def propagate(mu, a, e, ths0_deg, dt):
    """advance true anomaly by dt (ellipse or hyperbola); returns theta* (deg) wrapped to (-180,180]"""
    t0 = time_since_periapsis(mu, a, e, ths0_deg)
    if e < 1:
        n = np.sqrt(mu / a ** 3); M = n * (t0 + dt); E = kepler_E(np.mod(M + np.pi, 2 * np.pi) - np.pi, e)
        return th_from_E(e, E) * R2D
    n = np.sqrt(mu / abs(a) ** 3); H = kepler_H(n * (t0 + dt), e); return th_from_H(e, H) * R2D

# ---------------- f and g ----------------
def fg_theta(mu, p, r0vec, v0vec, dth_deg):
    """f, g, fdot, gdot in terms of delta-theta* (notes G/H, BMW 4.5)"""
    dth = dth_deg * D2R; r0 = np.linalg.norm(r0vec); h = np.sqrt(mu * p)
    r = p / (1 + (p / r0 - 1) * np.cos(dth) - np.sqrt(p / mu) * np.dot(r0vec, v0vec) / r0 * np.sin(dth))
    f = 1 - r / p * (1 - np.cos(dth)); g = r * r0 * np.sin(dth) / h
    fd = np.sqrt(mu / p) * np.tan(dth / 2) * ((1 - np.cos(dth)) / p - 1 / r - 1 / r0)
    gd = 1 - r0 / p * (1 - np.cos(dth))
    return f, g, fd, gd, r
def fg_E(mu, a, r0, dE, dt):
    """eccentric-anomaly form (BMW 4.6-29..32; HW5 P1d). r from r = a + (r0 - a) cos dE + sigma0 sqrt(a) sin dE is
    avoided: pass r via the propagated state instead -> here returns f, g and a function for fdot, gdot given r."""
    f = 1 - a / r0 * (1 - np.cos(dE)); g = dt - np.sqrt(a ** 3 / mu) * (dE - np.sin(dE))
    fdg = lambda r: (-np.sqrt(mu * a) * np.sin(dE) / (r * r0), 1 - a / r * (1 - np.cos(dE)))
    return f, g, fdg

# ---------------- 3D: elements <-> state ----------------
def dcm_313(Om, inc, th):
    """columns r_hat, theta_hat, h_hat expressed in x,y,z (angles deg)"""
    O, i, t = Om * D2R, inc * D2R, th * D2R
    cO, sO, ci, si, ct, st = np.cos(O), np.sin(O), np.cos(i), np.sin(i), np.cos(t), np.sin(t)
    return np.array([[cO * ct - sO * ci * st, -cO * st - sO * ci * ct,  sO * si],
                     [sO * ct + cO * ci * st, -sO * st + cO * ci * ct, -cO * si],
                     [si * st,                 si * ct,                  ci]])

def rv_from_elements(mu, a, e, inc, Om, om, ths):
    p = a * (1 - e * e); r = r_of(p, e, ths); h = np.sqrt(mu * p)
    vr = mu / h * e * np.sin(ths * D2R); vt = h / r
    C = dcm_313(Om, inc, om + ths)
    return C @ np.array([r, 0, 0]), C @ np.array([vr, vt, 0]), dict(p=p, r=r, h=h, vr=vr, vt=vt, C=C)

def elements_from_rv(mu, rvec, vvec):
    r = np.linalg.norm(rvec); v = np.linalg.norm(vvec); hv = np.cross(rvec, vvec); h = np.linalg.norm(hv)
    hh = hv / h; eps = v * v / 2 - mu / r; a = -mu / (2 * eps); p = h * h / mu
    ev = ((v * v - mu / r) * rvec - np.dot(rvec, vvec) * vvec) / mu; e = np.linalg.norm(ev)
    inc = np.arccos(np.clip(hh[2], -1, 1)) * R2D
    rh = rvec / r; si = np.sin(inc * D2R)
    if si < 1e-10:   # equatorial: Omega undefined -> set 0, theta measured from x
        Om = 0.0; th = np.arctan2(rh[1], rh[0]) * R2D * np.sign(hh[2])
    else:
        Om = np.arctan2(hh[0], -hh[1]) * R2D                   # h = (sO si, -cO si, ci)
        th = np.arctan2(rh[2] / si, (rh[0] * np.cos(Om * D2R) + rh[1] * np.sin(Om * D2R))) * R2D
    ths = np.arctan2(np.dot(rvec, vvec) / r * h / mu, p / r - 1) * R2D    # quadrant via r_dot
    om = wrap360(th - ths)
    gam = np.arcsin(np.dot(rvec, vvec) / (r * v)) * R2D
    out = dict(a=a, e=e, p=p, h=h, inc=inc, Om=wrap360(Om), om=om, theta=wrap360(th), ths=ths, gamma=gam, r=r, v=v, eps=eps, ev=ev, hv=hv)
    if e < 1:
        E = E_from_th(e, ths * D2R); n = np.sqrt(mu / a ** 3)
        out.update(E=E * R2D, M=(E - e * np.sin(E)) * R2D, t_tp=(E - e * np.sin(E)) / n, P=2 * np.pi / n)
    else:
        H = H_from_th(e, ths * D2R); n = np.sqrt(mu / abs(a) ** 3); out.update(H=H, t_tp=(e * np.sinh(H) - H) / n)
    return out

# ---------------- hyperbola ----------------
def hyperbola(mu, a_abs=None, e=None, rp=None, vinf=None):
    if a_abs is None: a_abs = mu / vinf ** 2
    if e is None: e = 1 + rp / a_abs
    rp = a_abs * (e - 1); p = a_abs * (e * e - 1); h = np.sqrt(mu * p)
    return dict(a=-a_abs, e=e, rp=rp, p=p, h=h, eps=mu / (2 * a_abs), vinf=np.sqrt(mu / a_abs),
                th_inf=np.arccos(-1 / e) * R2D, delta=2 * np.arcsin(1 / e) * R2D, b=a_abs * np.sqrt(e * e - 1),
                vp=np.sqrt(mu * (2 / rp + 1 / a_abs)))

# ---------------- maneuvers ----------------
def vnc_frame(rvec, vvec):
    V = vvec / np.linalg.norm(vvec); N = np.cross(rvec, vvec); N /= np.linalg.norm(N); return V, N, np.cross(V, N)

def impulse_planar(v1, g1_deg, v2, g2_deg):
    """dv between (v1,gamma1) and (v2,gamma2) at the same point, same plane. alpha from v- (>0 away from body)."""
    g1, g2 = g1_deg * D2R, g2_deg * D2R
    dv_r = v2 * np.sin(g2) - v1 * np.sin(g1); dv_t = v2 * np.cos(g2) - v1 * np.cos(g1)
    dv = np.hypot(dv_r, dv_t)
    # components along V (v- direction) and C (outward normal, V x N)
    dV = dv_t * np.cos(g1) + dv_r * np.sin(g1); dC = dv_r * np.cos(g1) - dv_t * np.sin(g1)
    return dict(dv=dv, alpha=np.arctan2(dC, dV) * R2D, dV=dV, dC=dC, dgamma=(g2 - g1) * R2D)

def apply_dv_vnc(rvec, vvec, dv, alpha_deg, beta_deg):
    V, N, C = vnc_frame(rvec, vvec); a, b = alpha_deg * D2R, beta_deg * D2R
    dvec = dv * (np.cos(b) * np.cos(a) * V + np.sin(b) * N + np.cos(b) * np.sin(a) * C)
    return vvec + dvec, dvec

def intersect_conics(p1, e1, p2, e2, dom_deg):
    """theta* (in orbit 1) where two coplanar coaxial-focus conics cross; orbit 2 periapsis rotated by dom."""
    # p1/(1+e1 c) = p2/(1+e2 cos(t - dom)) -> A cos t + B sin t = C
    dm = dom_deg * D2R; A = p2 * e1 - p1 * e2 * np.cos(dm); B = -p1 * e2 * np.sin(dm); Cc = p1 - p2
    R = np.hypot(A, B); phi = np.arctan2(B, A)
    if abs(Cc / R) > 1: return []
    d = np.arccos(Cc / R); return sorted({wrap180((phi + d) * R2D), wrap180((phi - d) * R2D)})

def hohmann(mu, r1, r2):
    aT = (r1 + r2) / 2; vc1, vc2 = np.sqrt(mu / r1), np.sqrt(mu / r2)
    vp, va = np.sqrt(mu * (2 / r1 - 1 / aT)), np.sqrt(mu * (2 / r2 - 1 / aT))
    dv1, dv2 = abs(vp - vc1), abs(vc2 - va); tof = np.pi * np.sqrt(aT ** 3 / mu)
    n2 = np.sqrt(mu / r2 ** 3); phase = (np.pi - n2 * tof) * R2D
    n1 = np.sqrt(mu / r1 ** 3); syn = 2 * np.pi / abs(n1 - n2)
    return dict(aT=aT, eT=abs(r2 - r1) / (r1 + r2), dv1=dv1, dv2=dv2, dv=dv1 + dv2, tof=tof, phase=phase, synodic=syn, vp=vp, va=va, vc1=vc1, vc2=vc2)

def bielliptic(mu, r1, r2, rb):
    a1, a2 = (r1 + rb) / 2, (r2 + rb) / 2
    dv1 = np.sqrt(mu * (2 / r1 - 1 / a1)) - np.sqrt(mu / r1)
    dv2 = abs(np.sqrt(mu * (2 / rb - 1 / a2)) - np.sqrt(mu * (2 / rb - 1 / a1)))
    dv3 = abs(np.sqrt(mu * (2 / r2 - 1 / a2)) - np.sqrt(mu / r2))
    tof = np.pi * (np.sqrt(a1 ** 3 / mu) + np.sqrt(a2 ** 3 / mu))
    return dict(dv1=dv1, dv2=dv2, dv3=dv3, dv=dv1 + dv2 + dv3, tof=tof, a1=a1, a2=a2)

def plane_change(v, di_deg): return 2 * v * np.sin(di_deg * D2R / 2)

# ---------------- patched conics / flyby ----------------
def escape_dv(mu, rp, vinf): return np.sqrt(vinf ** 2 + 2 * mu / rp) - np.sqrt(mu / rp)
def capture_dv(mu, rp, vinf, e_cap=0.0):
    return np.sqrt(vinf ** 2 + 2 * mu / rp) - np.sqrt(mu * (1 + e_cap) / rp)

def flyby(mu_pl, vpl_vec, v_minus_vec, rp, sense):
    """2D: rotate v_inf by delta. sense=+1 rotates counter-clockwise (pass ahead/behind decided by caller)."""
    vinf_m = v_minus_vec - vpl_vec; vinf = np.linalg.norm(vinf_m); hy = hyperbola(mu_pl, vinf=vinf, rp=rp)
    d = sense * hy['delta'] * D2R; Rm = np.array([[np.cos(d), -np.sin(d)], [np.sin(d), np.cos(d)]])
    vinf_p = Rm @ vinf_m; v_plus = vpl_vec + vinf_p
    return dict(hyp=hy, vinf=vinf, vinf_minus=vinf_m, vinf_plus=vinf_p, v_plus=v_plus, dv_eq=v_plus - v_minus_vec,
                dv_eq_mag=2 * vinf * np.sin(hy['delta'] * D2R / 2))

def state_to_conic_2d(mu, r, vvec_rt):
    """heliocentric state given radius and (v_r, v_theta) -> a, e, theta*, gamma, etc."""
    return conic_from_rv_polar(mu, r, vvec_rt[0], vvec_rt[1])

# ---------------- Lambert (alpha-beta form, notes LL) ----------------
def lambert(mu, r1, r2, TA_deg, tof, root='small', N=0):
    TA = TA_deg * D2R; typ = 1 if TA < np.pi else 2; sg = -1 if typ == 1 else 1
    phi = TA if typ == 1 else 2 * np.pi - TA
    c = np.sqrt(r1 ** 2 + r2 ** 2 - 2 * r1 * r2 * np.cos(phi)); s = (r1 + r2 + c) / 2; am = s / 2
    tpar = np.sqrt(2 / mu) / 3 * (s ** 1.5 + sg * (s - c) ** 1.5)
    bm = 2 * np.arcsin(np.sqrt((s - c) / s)); tmin = np.sqrt(am ** 3 / mu) * (np.pi + sg * (bm - np.sin(bm)))
    asn = lambda x: np.arcsin(min(1.0, np.sqrt(x)))
    def tE(a, B):
        ao, bo = 2 * asn(s / (2 * a)), 2 * asn((s - c) / (2 * a)); al = 2 * np.pi - ao if B else ao
        return a ** 1.5 / np.sqrt(mu) * ((al - np.sin(al)) + sg * (bo - np.sin(bo)) + 2 * np.pi * N)
    def tH(x):
        ao, bo = 2 * np.arcsinh(np.sqrt(s / (2 * x))), 2 * np.arcsinh(np.sqrt((s - c) / (2 * x)))
        return x ** 1.5 / np.sqrt(mu) * ((np.sinh(ao) - ao) + sg * (np.sinh(bo) - bo))
    def bis(fn, lo, hi, inc):
        for _ in range(300):
            m = np.sqrt(lo * hi); v = fn(m)
            if (v < tof) == inc: lo = m
            else: hi = m
        return np.sqrt(lo * hi)
    out = dict(type=typ, c=c, s=s, am=am, tof_par=tpar, tof_min=tmin, alpha_m=np.pi, beta_m=bm * R2D)
    if tof < tpar:
        x = bis(tH, 1e-6 * s, 1e6 * s, True); a = -x; cls = f'{typ}H'
        al = 2 * np.arcsinh(np.sqrt(s / (2 * x))); bo = 2 * np.arcsinh(np.sqrt((s - c) / (2 * x))); be = bo if typ == 1 else -bo
        K = 4 * x * (s - r1) * (s - r2) / c ** 2; pr = [K * np.sinh((al + be) / 2) ** 2, K * np.sinh((al - be) / 2) ** 2]
    else:
        B = tof >= tmin; cls = f'{typ}{"B" if B else "A"}'
        if B:
            hi = 2 * am
            while tE(hi, True) < tof: hi *= 2
            a = bis(lambda x: tE(x, True), am, hi, True)
        else: a = bis(lambda x: tE(x, False), am, am * 1e7, False)
        ao, bo = 2 * asn(s / (2 * a)), 2 * asn((s - c) / (2 * a)); al = 2 * np.pi - ao if B else ao; be = bo if typ == 1 else -bo
        K = 4 * a * (s - r1) * (s - r2) / c ** 2; pr = [K * np.sin((al + be) / 2) ** 2, K * np.sin((al - be) / 2) ** 2]
    ps = sorted(pr); p = ps[0] if root == 'small' else ps[1]
    e = np.sqrt(1 + p / -a) if a < 0 else np.sqrt(max(0.0, 1 - p / a))
    out.update(cls=cls, a=a, alpha=al * R2D, beta=be * R2D, p_roots=ps, p=p, e=e)
    out.update(lambert_velocities(mu, r1, r2, TA_deg, p))
    return out

def lambert_minE(mu, r1, r2, TA_deg):
    """minimum-energy transfer: a = s/2, alpha = pi; single p"""
    TA = TA_deg * D2R; typ = 1 if TA < np.pi else 2; sg = -1 if typ == 1 else 1
    phi = TA if typ == 1 else 2 * np.pi - TA
    c = np.sqrt(r1 ** 2 + r2 ** 2 - 2 * r1 * r2 * np.cos(phi)); s = (r1 + r2 + c) / 2; am = s / 2
    bm = 2 * np.arcsin(np.sqrt((s - c) / s)); be = bm if typ == 1 else -bm
    tmin = np.sqrt(am ** 3 / mu) * (np.pi + sg * (bm - np.sin(bm)))
    p = 4 * am * (s - r1) * (s - r2) / c ** 2 * np.sin((np.pi + be) / 2) ** 2
    e = np.sqrt(1 - p / am)
    out = dict(type=typ, c=c, s=s, a=am, p=p, e=e, tof=tmin, beta=be * R2D)
    out.update(lambert_velocities(mu, r1, r2, TA_deg, p)); return out

def lambert_velocities(mu, r1, r2, TA_deg, p):
    TA = TA_deg * D2R; ct, st = np.cos(TA), np.sin(TA)
    rD = np.array([r1, 0.0]); rA = np.array([r2 * ct, r2 * st])
    f = 1 - r2 / p * (1 - ct); g = r1 * r2 * st / np.sqrt(mu * p); vD = (rA - f * rD) / g
    fd = np.dot(rD, vD) / (p * r1) * (1 - ct) - np.sqrt(mu / p) / r1 * st; gd = 1 - r1 / p * (1 - ct)
    vA = fd * rD + gd * vD
    def thg(rv, vv):
        r = np.linalg.norm(rv); h = rv[0] * vv[1] - rv[1] * vv[0]; rd = np.dot(rv, vv) / r
        return np.arctan2(rd * h / mu, p / r - 1) * R2D, np.arctan2(rd, h / r) * R2D
    thD, gD = thg(rD, vD); thA, gA = thg(rA, vA)
    vc1 = np.array([0, np.sqrt(mu / r1)]); vc2 = np.sqrt(mu / r2) * np.array([-st, ct])
    dvD = vD - vc1; dvA = vc2 - vA
    def alpha(dv, vold, rv):  # angle from old velocity, + away from the body
        V = vold / np.linalg.norm(vold); Cn = np.array([V[1], -V[0]])   # V x N for planar ccw: outward
        return np.arctan2(np.dot(dv, Cn), np.dot(dv, V)) * R2D
    return dict(f=f, g=g, fd=fd, gd=gd, vD=vD, vA=vA, vD_mag=np.linalg.norm(vD), vA_mag=np.linalg.norm(vA),
                thD=thD, thA=thA, gD=gD, gA=gA, dvD=dvD, dvA=dvA, dvD_mag=np.linalg.norm(dvD), dvA_mag=np.linalg.norm(dvA),
                alphaD=alpha(dvD, vc1, rD), alphaA=alpha(dvA, vA, rA), dv_total=np.linalg.norm(dvD) + np.linalg.norm(dvA))

def two_vector_transfer(mu, r1vec, r2vec, p, hz_positive=True):
    """3D: transfer plane, TA from h direction, velocities from f & g given p (HW10 P1, Exam 2 P2)."""
    r1, r2 = np.linalg.norm(r1vec), np.linalg.norm(r2vec); hv = np.cross(r1vec, r2vec)
    cosTA = np.dot(r1vec, r2vec) / (r1 * r2); TA = np.arccos(cosTA)
    if (hv[2] > 0) != hz_positive: hv = -hv; TA = 2 * np.pi - TA
    hh = hv / np.linalg.norm(hv); inc = np.arccos(hh[2]) * R2D; Om = wrap360(np.arctan2(hh[0], -hh[1]) * R2D)
    f = 1 - r2 / p * (1 - np.cos(TA)); g = r1 * r2 * np.sin(TA) / np.sqrt(mu * p); v1 = (r2vec - f * r1vec) / g
    el = elements_from_rv(mu, r1vec, v1)
    return dict(TA=TA * R2D, inc=inc, Om=Om, f=f, g=g, v1=v1, el=el)

def julian_date(Y, M, Dd, hr=12.0):
    if M <= 2: Y -= 1; M += 12
    A = Y // 100; B = 2 - A + A // 4
    return int(365.25 * (Y + 4716)) + int(30.6001 * (M + 1)) + Dd + B - 1524.5 + hr / 24
