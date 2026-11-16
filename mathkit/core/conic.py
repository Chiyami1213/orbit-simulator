"""Planar conic geometry (notes E/F).

Ported verbatim from the verified orbitcore.py reference. Do not change formulas without a failing test.
"""
import numpy as np
from .constants import D2R, R2D
from .kepler import E_from_th

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

def state_to_conic_2d(mu, r, vvec_rt):
    """heliocentric state given radius and (v_r, v_theta) -> a, e, theta*, gamma, etc."""
    return conic_from_rv_polar(mu, r, vvec_rt[0], vvec_rt[1])
