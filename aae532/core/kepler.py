"""Anomalies and Kepler propagation (notes F/G; BMW 4.2-4.4).

Ported verbatim from the verified orbitcore.py reference. Do not change formulas without a failing test.
"""
import numpy as np
from .constants import D2R, R2D

def E_from_th(e, th):  return 2 * np.arctan2(np.sqrt(1 - e) * np.sin(th / 2), np.sqrt(1 + e) * np.cos(th / 2))

def th_from_E(e, E):   return 2 * np.arctan2(np.sqrt(1 + e) * np.sin(E / 2), np.sqrt(1 - e) * np.cos(E / 2))

def H_from_th(e, th):  return 2 * np.arctanh(np.sqrt((e - 1) / (e + 1)) * np.tan(th / 2))

def th_from_H(e, H):   return 2 * np.arctan(np.sqrt((e + 1) / (e - 1)) * np.tanh(H / 2))

def kepler_E(M, e, tol=1e-13):
    E = M + e * np.sin(M) if e < 0.8 else np.pi * np.sign(np.sin(M) or 1)
    for _ in range(100):
        dE = (E - e * np.sin(E) - M) / (1 - e * np.cos(E)); E -= dE
        if abs(dE) < tol: break
    return E

def kepler_H(M, e, tol=1e-13):
    H = np.arcsinh(M / e) if e > 1 else M
    for _ in range(200):
        dH = (e * np.sinh(H) - H - M) / (e * np.cosh(H) - 1); H -= dH
        if abs(dH) < tol: break
    return H

def time_since_periapsis(mu, a, e, ths_deg):
    th = ths_deg * D2R
    if e < 1:
        n = np.sqrt(mu / a ** 3); E = E_from_th(e, th); return (E - e * np.sin(E)) / n
    n = np.sqrt(mu / abs(a) ** 3); H = H_from_th(e, th); return (e * np.sinh(H) - H) / n

def propagate(mu, a, e, ths0_deg, dt):
    """advance true anomaly by dt (ellipse or hyperbola); returns theta* (deg) wrapped to (-180,180]"""
    t0 = time_since_periapsis(mu, a, e, ths0_deg)
    if e < 1:
        n = np.sqrt(mu / a ** 3); M = n * (t0 + dt); E = kepler_E(np.mod(M + np.pi, 2 * np.pi) - np.pi, e)
        return th_from_E(e, E) * R2D
    n = np.sqrt(mu / abs(a) ** 3); H = kepler_H(n * (t0 + dt), e); return th_from_H(e, H) * R2D
