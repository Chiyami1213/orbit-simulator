"""Lagrange f and g functions (notes G/H; BMW 4.5, 4.6-29..32).

Ported verbatim from the verified orbitcore.py reference. Do not change formulas without a failing test.
"""
import numpy as np
from .constants import D2R

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
