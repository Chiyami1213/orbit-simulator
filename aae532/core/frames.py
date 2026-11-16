"""Rotation matrices and the VNC frame.

Ported verbatim from the verified orbitcore.py reference. Do not change formulas without a failing test.
"""
import numpy as np
from .constants import D2R

def dcm_313(Om, inc, th):
    """columns r_hat, theta_hat, h_hat expressed in x,y,z (angles deg)"""
    O, i, t = Om * D2R, inc * D2R, th * D2R
    cO, sO, ci, si, ct, st = np.cos(O), np.sin(O), np.cos(i), np.sin(i), np.cos(t), np.sin(t)
    return np.array([[cO * ct - sO * ci * st, -cO * st - sO * ci * ct,  sO * si],
                     [sO * ct + cO * ci * st, -sO * st + cO * ci * ct, -cO * si],
                     [si * st,                 si * ct,                  ci]])

def vnc_frame(rvec, vvec):
    V = vvec / np.linalg.norm(vvec); N = np.cross(rvec, vvec); N /= np.linalg.norm(N); return V, N, np.cross(V, N)
