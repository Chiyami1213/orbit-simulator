"""Hyperbolic geometry (BMW 2.5; notes F).

Ported verbatim from the verified orbitcore.py reference. Do not change formulas without a failing test.
"""
import numpy as np
from .constants import R2D

def hyperbola(mu, a_abs=None, e=None, rp=None, vinf=None):
    if a_abs is None: a_abs = mu / vinf ** 2
    if e is None: e = 1 + rp / a_abs
    rp = a_abs * (e - 1); p = a_abs * (e * e - 1); h = np.sqrt(mu * p)
    return dict(a=-a_abs, e=e, rp=rp, p=p, h=h, eps=mu / (2 * a_abs), vinf=np.sqrt(mu / a_abs),
                th_inf=np.arccos(-1 / e) * R2D, delta=2 * np.arcsin(1 / e) * R2D, b=a_abs * np.sqrt(e * e - 1),
                vp=np.sqrt(mu * (2 / rp + 1 / a_abs)))
