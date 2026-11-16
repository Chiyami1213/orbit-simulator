"""Module 2 - two-body constants (HW2 P3, HW3 P3, Exam 1 P3).

Given masses (or gravitational parameters with G = 1) and the inertial states of two bodies: relative orbit constants
C3 = r x v, energy C4 = eps = v^2/2 - mu/r, h, areal velocity h/2, barycentre position/velocity. eps = 0 -> parabola case.
Paths are drawn about the centre of mass (CM frame): body i follows the relative conic scaled by m_j/(m_1+m_2).
"""
from __future__ import annotations
import numpy as np
from ..core.nbody import two_body_constants
from ..core.constants import R2D, wrap360
from ..core.conic import conic_from_rv_polar
from ..results import Result, KM, KMS, EPS, HU, NONE
from ..scene import Scene, Orbit, Pt, vector, Rz, unit
from .common import vel_scale, kind_of


def solve(m1: float, m2: float, r1, r2, v1, v2, G: float = 1.0, names=('body 1', 'body 2'), label: str = 'Module 2') -> Result:
    res = Result('Two-body constants', label, inputs=dict(m1=m1, m2=m2, r1=list(r1), r2=list(r2), v1=list(v1), v2=list(v2), G=G))
    T = two_body_constants(m1, m2, r1, r2, v1, v2, G); res.data.update(T)
    g = 'Relative motion'
    res.add('μ = G(m₁ + m₂)', 'μ', T['mu'], 'km³·s⁻² (if G·m in these units)', group=g)
    res.add('Relative position r̄ = r̄₂ − r̄₁', 'r̄', T['r_rel'], KM, group=g); res.add('Relative velocity', 'v̄', T['v_rel'], KMS, group=g)
    res.add('C̄₃ = r̄ × v̄', 'C̄₃', T['C3'], HU, 'specific angular momentum vector', group=g); res.add('|C̄₃| = h', 'h', T['h'], HU, group=g)
    res.add('Areal velocity', 'dA/dt', T['areal_velocity'], 'km²·s⁻¹', 'dA/dt = h/2', group=g)
    res.add('Energy constant C₄ = ε', 'C₄', T['C4'], EPS, 'ε = v²/2 − μ/r', group=g)
    res.add('Orbit type', '', 'parabola (ε = 0)' if T['parabola'] else ('ellipse (ε < 0)' if T['eps'] < 0 else 'hyperbola (ε > 0)'), NONE, group=g)
    if T['parabola']: res.warn('ε = 0: parabola — a = ∞, no period')
    g = 'Barycentre'
    res.add('Center-of-mass position', 'r̄_cm', T['r_cm'], KM, '(m₁r̄₁ + m₂r̄₂)/(m₁+m₂)', group=g); res.add('Center-of-mass velocity', 'v̄_cm', T['v_cm'], KMS, 'constant (no external force)', group=g)
    r = np.linalg.norm(T['r_rel']); r_hat = T['r_rel'] / r; h_hat = unit(T['C3']); planar = abs(T['C3'][0]) < 1e-12 and abs(T['C3'][1]) < 1e-12
    if planar and T['h'] > 0:
        vr = float(T['r_rel'] @ T['v_rel'] / r); vt = T['h'] / r; sgn = np.sign(T['C3'][2]) or 1.0
        c = conic_from_rv_polar(T['mu'], r, vr, vt); th_pos = np.degrees(np.arctan2(T['r_rel'][1], T['r_rel'][0]))
        if sgn < 0: res.warn('clockwise relative motion: figure mirrors the conic')
        res.add('Semi-latus rectum', 'p', c['p'], KM, group='Relative orbit'); res.add('Eccentricity', 'e', c['e'], NONE, group='Relative orbit')
        if np.isfinite(c['a']): res.add('Semi-major axis', 'a', c['a'], KM, group='Relative orbit')
        if 'P' in c: res.add('Period', 'P', c['P'], 's', group='Relative orbit')
        res.add('True anomaly of the current point', 'θ*', c['ths'], '°', group='Relative orbit')
        res.data.update(conic=c)
        # CM-frame scene
        M = m1 + m2; rc = [np.asarray(x, float) - T['r_cm'] for x in (r1, r2)]
        om = (th_pos - c['ths']) % 360 if sgn > 0 else (th_pos + c['ths']) % 360
        Q = Rz(om) if sgn > 0 else Rz(om) @ np.diag([1.0, -1.0, 1.0])
        sc = Scene('two-body motion about the center of mass', label)
        sc.orbits.append(Orbit(f'path of {names[0]}', c['p'] * m2 / M, c['e'], Rz(180) @ Q if sgn > 0 else Q @ Rz(180), 'orbit', rmax=3 * c['p'] * m2 / M))
        sc.orbits.append(Orbit(f'path of {names[1]}', c['p'] * m1 / M, c['e'], Q, 'orbit2', rmax=3 * c['p'] * m1 / M))
        sc.pts += [Pt(np.zeros(3), 'center of mass', 'muted', '+', 9), Pt(rc[0], names[0], 'orbit', 'o', 8), Pt(rc[1], names[1], 'orbit2', 'o', 8)]
        ref = max(np.linalg.norm(rc[0]), np.linalg.norm(rc[1]), 1.0)
        vs = vel_scale(ref, max(np.linalg.norm(np.asarray(v1) - T['v_cm']), np.linalg.norm(np.asarray(v2) - T['v_cm']), 1e-12), 0.25)
        vector(sc, rc[0], np.asarray(v1, float) - T['v_cm'], f'v̄₁ − v̄_cm', 'vel', scale=vs); vector(sc, rc[1], np.asarray(v2, float) - T['v_cm'], f'v̄₂ − v̄_cm', 'vel', scale=vs)
        res.scene = sc
    else:
        sc = Scene('two bodies (non-planar or rectilinear: no path drawn)', label); rc = [np.asarray(x, float) for x in (r1, r2)]
        sc.pts += [Pt(rc[0], names[0], 'orbit', 'o', 8), Pt(rc[1], names[1], 'orbit2', 'o', 8), Pt(T['r_cm'], 'center of mass', 'muted', '+', 9)]
        sc.is3d = True; res.scene = sc
    return res
