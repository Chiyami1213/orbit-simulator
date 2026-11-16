"""Lambert problem, alpha-beta form (notes LL), and 3-D two-position transfer.

Ported verbatim from the verified orbitcore.py reference. Do not change formulas without a failing test.
"""
import numpy as np
from .constants import D2R, R2D, wrap360
from .elements import elements_from_rv

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
