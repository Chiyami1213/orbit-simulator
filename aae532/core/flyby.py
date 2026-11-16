"""Planar gravity assist.

Ported verbatim from the verified orbitcore.py reference. Do not change formulas without a failing test.
"""
import numpy as np
from .constants import D2R
from .hyperbola import hyperbola

def flyby(mu_pl, vpl_vec, v_minus_vec, rp, sense):
    """2D: rotate v_inf by delta. sense=+1 rotates counter-clockwise (pass ahead/behind decided by caller)."""
    vinf_m = v_minus_vec - vpl_vec; vinf = np.linalg.norm(vinf_m); hy = hyperbola(mu_pl, vinf=vinf, rp=rp)
    d = sense * hy['delta'] * D2R; Rm = np.array([[np.cos(d), -np.sin(d)], [np.sin(d), np.cos(d)]])
    vinf_p = Rm @ vinf_m; v_plus = vpl_vec + vinf_p
    return dict(hyp=hy, vinf=vinf, vinf_minus=vinf_m, vinf_plus=vinf_p, v_plus=v_plus, dv_eq=v_plus - v_minus_vec,
                dv_eq_mag=2 * vinf * np.sin(hy['delta'] * D2R / 2))
