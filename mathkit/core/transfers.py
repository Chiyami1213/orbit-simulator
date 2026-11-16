"""Coplanar transfers, bi-elliptic, plane change.

Ported verbatim from the verified orbitcore.py reference. Do not change formulas without a failing test.
"""
import numpy as np
from .constants import D2R, R2D

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
