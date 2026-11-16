"""Patched-conic departure/capture burns.

Ported verbatim from the verified orbitcore.py reference. Do not change formulas without a failing test.
"""
import numpy as np

def escape_dv(mu, rp, vinf): return np.sqrt(vinf ** 2 + 2 * mu / rp) - np.sqrt(mu / rp)

def capture_dv(mu, rp, vinf, e_cap=0.0):
    return np.sqrt(vinf ** 2 + 2 * mu / rp) - np.sqrt(mu * (1 + e_cap) / rp)
