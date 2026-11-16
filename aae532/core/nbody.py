"""N-body relative acceleration (Module 1; HW2 P1-2, HW3 P1, Exam 1 P1).

Notation: body j sits at r_j with gravitational parameter mu_j = G m_j. d_ij = r_j - r_i points from i to j.
Acceleration of body i relative to central body c (N-body relative-motion equation; BMW ch. 1, course notes):

    r_ddot_ic = -(mu_c + mu_i) r_ic / r_ic^3                           (dominant two-body term)
              + sum_{j != i,c} mu_j d_ij/|d_ij|^3                      (direct perturbation)
              - sum_{j != i,c} mu_j d_cj/|d_cj|^3                      (indirect perturbation)

with r_ic = r_i - r_c.  For a spacecraft target pass mu_i = 0.  All inputs/outputs in km, km^3 s^-2, km s^-2.
"""
from __future__ import annotations
import numpy as np


def _attr(mu_j: float, d: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(d)
    return mu_j * d / n ** 3


def nbody_relative(mus: list[float], pos: list[np.ndarray], c: int, i: int) -> dict:
    """Decompose the acceleration of body ``i`` relative to central body ``c``. Indices refer to ``mus``/``pos``."""
    mus = [float(m) for m in mus]; pos = [np.asarray(p, float) for p in pos]
    if c == i:
        raise ValueError('central body and target must differ')
    r_ic = pos[i] - pos[c]
    dominant = -(mus[c] + mus[i]) * r_ic / np.linalg.norm(r_ic) ** 3
    direct = np.zeros_like(r_ic); indirect = np.zeros_like(r_ic)
    terms = []
    for j in range(len(mus)):
        if j in (c, i):
            continue
        dj = _attr(mus[j], pos[j] - pos[i]); ij = -_attr(mus[j], pos[j] - pos[c])
        direct += dj; indirect += ij; terms.append(dict(j=j, direct=dj, indirect=ij, net=dj + ij))
    net = direct + indirect
    total = dominant + net
    mag = np.linalg.norm
    return dict(r_ic=r_ic, dominant=dominant, direct=direct, indirect=indirect, net_pert=net, total=total,
                terms=terms, dominant_mag=mag(dominant), direct_mag=mag(direct), indirect_mag=mag(indirect),
                net_pert_mag=mag(net), total_mag=mag(total),
                pert_over_dominant=mag(net) / mag(dominant), center_of_mass=center_of_mass(mus, pos))


def center_of_mass(mus: list[float], pos: list[np.ndarray]) -> np.ndarray:
    """Barycenter (masses proportional to mu)."""
    m = np.asarray(mus, float); P = np.asarray(pos, float)
    return (m[:, None] * P).sum(axis=0) / m.sum()


def rank_terms(res: dict) -> list[tuple[str, float]]:
    """Magnitude ranking of the acceleration terms, largest first."""
    items = [('dominant', res['dominant_mag']), ('direct', res['direct_mag']), ('indirect', res['indirect_mag']),
             ('net perturbing', res['net_pert_mag']), ('total', res['total_mag'])]
    return sorted(items, key=lambda kv: -kv[1])


def two_body_constants(m1: float, m2: float, r1, r2, v1, v2, G: float = 1.0) -> dict:
    """Two-body integrals (HW2 P3, HW3 P3, Exam 1 P3). Relative vector r = r2 - r1, mu = G(m1+m2).

    C3 = r x v (specific angular momentum of the relative orbit), C4 = eps = v^2/2 - mu/r (energy constant; this
    identification of C4 with eps is an assumption to be checked against the notes), h = |C3|, areal velocity = h/2, barycentric velocity v_cm = (m1 v1 + m2 v2)/(m1+m2).
    Pass G=1 with mu-valued 'masses' (mu1, mu2) when only gravitational parameters are known.
    """
    r1, r2, v1, v2 = (np.asarray(x, float) for x in (r1, r2, v1, v2))
    mu = G * (m1 + m2); r = r2 - r1; v = v2 - v1
    C3 = np.cross(r, v); eps = 0.5 * v @ v - mu / np.linalg.norm(r); h = np.linalg.norm(C3)
    vcm = (m1 * v1 + m2 * v2) / (m1 + m2); rcm = (m1 * r1 + m2 * r2) / (m1 + m2)
    out = dict(mu=mu, r_rel=r, v_rel=v, C3=C3, h=h, eps=eps, areal_velocity=h / 2, v_cm=vcm, r_cm=rcm,
               parabola=abs(eps) < 1e-12)
    out['C4'] = eps
    return out
