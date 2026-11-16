"""Classical elements <-> inertial state (3-1-3 rotation).

Ported verbatim from the verified orbitcore.py reference. Do not change formulas without a failing test.
"""
import numpy as np
from .constants import D2R, R2D, wrap360
from .kepler import E_from_th, H_from_th
from .conic import r_of
from .frames import dcm_313

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
