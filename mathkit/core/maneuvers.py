"""Single impulses and orbit intersections.

Ported verbatim from the verified orbitcore.py reference. Do not change formulas without a failing test.
"""
import numpy as np
from .constants import D2R, R2D, wrap180
from .frames import vnc_frame

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
