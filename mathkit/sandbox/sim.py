"""N-body simulation for the Explore scene: every body with mu > 0 attracts every other body; test particles (mu = 0) only feel gravity.

Integrated with the adaptive Verner RK8(9) from ``mathkit.dyn`` (pure NumPy). The result is resampled with cubic Hermite interpolation (positions and
velocities are known at every accepted step), so the client can play it back at any time warp and in either direction.
"""
from __future__ import annotations
import numpy as np
from ..dyn.integrators import propagate

DAY = 86400.0


def rhs_for(mu: np.ndarray, attract: np.ndarray):
    """Right-hand side for y = [r1, v1, r2, v2, ...] (6 per body)."""
    n = len(mu); src = np.where(attract, mu, 0.0)
    def f(t, y):
        Y = y.reshape(n, 6); R = Y[:, :3]
        D = R[None, :, :] - R[:, None, :]                                   # D[i, j] = r_j - r_i
        d2 = np.einsum('ijk,ijk->ij', D, D); np.fill_diagonal(d2, 1.0)
        w = src[None, :] / (d2 * np.sqrt(d2)); np.fill_diagonal(w, 0.0)
        A = np.einsum('ij,ijk->ik', w, D)
        out = np.empty_like(Y); out[:, :3] = Y[:, 3:]; out[:, 3:] = A
        return out.reshape(-1)
    return f


def pack(scene: dict) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    bodies = scene['bodies']; mu = np.array([b['mu'] for b in bodies], float); att = np.array([bool(b.get('gravity', True)) and b['mu'] > 0 for b in bodies])
    y = np.concatenate([np.concatenate([b['r'], b['v']]) for b in bodies]).astype(float); return mu, att, y


def energy(mu: np.ndarray, Y: np.ndarray) -> float:
    """Total energy of the massive bodies (per unit of G): kinetic plus pairwise potential. Used to report integration quality."""
    m = mu > 0; R = Y[m, :3]; V = Y[m, 3:]; M = mu[m]; k = 0.5 * np.sum(M * np.sum(V * V, axis=1)); u = 0.0
    for i in range(len(M)):
        for j in range(i + 1, len(M)): u -= M[i] * M[j] / np.linalg.norm(R[i] - R[j])
    return float(k + u)


def simulate(scene: dict, days_back: float = 0.0, days_forward: float = 365.25, accuracy: float = 1e-11, max_samples: int = 6000) -> dict:
    """Integrate from the scene epoch backward and forward; returns uniformly sampled positions of every body.

    Result: dict(jd=[...], bodies={id: [[x, y, z], ...]}, energy_drift=float, steps=int, status=str). jd are UTC Julian dates.
    """
    bodies = scene['bodies']; n = len(bodies)
    if n == 0: return dict(jd=[scene['epoch_jd']], bodies={}, energy_drift=0.0, steps=0, status='empty')
    mu, att, y0 = pack(scene); f = rhs_for(mu, att); jd0 = scene['epoch_jd']
    # sampling interval: resolve the fastest orbit (about 40 samples per period) within the sample budget
    horizon = max(days_back + days_forward, 1e-6)
    dts = []
    for i, b in enumerate(bodies):                                                              # fastest orbital time scale of each body about any heavier attractor
        for j in range(n):
            if j == i or not att[j] or mu[j] < mu[i]: continue
            d = np.linalg.norm(np.array(bodies[j]['r']) - np.array(b['r']))
            T = 2 * np.pi * np.sqrt(d ** 3 / (mu[j] + max(mu[i], 0.0))) if d > 0 else np.inf
            if np.isfinite(T) and T > 0: dts.append(T / 40.0)
    dt_s = max(min(dts) if dts else horizon * DAY / 2000, horizon * DAY / max_samples)
    out_jd = [jd0]; out_r = [y0.reshape(n, 6)[:, :3].copy()]; steps = 0; status = 'done'
    e0 = energy(mu, y0.reshape(n, 6))
    final = {}
    for sgn, span in ((1.0, days_forward), (-1.0, days_back)):
        if span <= 0: continue
        sol = propagate(f, y0, 0.0, sgn * span * DAY, accuracy=accuracy, h0=3600.0, h_min=1e-3, h_max=5 * DAY, record=True)
        steps += sol.n_steps; status = sol.status if sol.status not in ('done', 'event') else status
        T = sol.t; Y = sol.y.reshape(len(T), n, 6); grid = np.arange(0.0, sgn * span * DAY, sgn * dt_s)[1:]
        if len(grid) == 0 or grid[-1] != sgn * span * DAY: grid = np.append(grid, sgn * span * DAY)
        pos = np.empty((len(grid), n, 3)); k = 0
        for gi, tg in enumerate(grid):
            while k < len(T) - 2 and (T[k + 1] - tg) * sgn < 0: k += 1
            f0 = Y[k][:, 3:]
            f1 = Y[k + 1][:, 3:]; h = T[k + 1] - T[k]; s = (tg - T[k]) / h; s2, s3 = s * s, s * s * s
            pos[gi] = (2 * s3 - 3 * s2 + 1) * Y[k][:, :3] + (s3 - 2 * s2 + s) * h * f0 + (-2 * s3 + 3 * s2) * Y[k + 1][:, :3] + (s3 - s2) * h * f1
        out_jd += (jd0 + grid / DAY).tolist(); out_r += list(pos); final[sgn] = Y[-1]
    order = np.argsort(out_jd); jd = np.array(out_jd)[order]; R = np.array(out_r)[order]
    e1 = energy(mu, (final.get(1.0) if 1.0 in final else y0.reshape(n, 6)))
    drift = abs(e1 - e0) / abs(e0) if e0 != 0 else 0.0
    return dict(jd=jd.tolist(), bodies={b['id']: np.round(R[:, i, :], 3).tolist() for i, b in enumerate(bodies)}, energy_drift=float(drift), steps=int(steps), status=status)


def state_at(scene: dict, jd: float, accuracy: float = 1e-11) -> dict:
    """The scene advanced (or reversed) to the given UTC Julian date: same bodies, new states, epoch = jd."""
    out = {**scene, 'bodies': [dict(b) for b in scene['bodies']]}
    dt = (jd - scene['epoch_jd']) * DAY
    if abs(dt) < 1e-6 or not scene['bodies']: out['epoch_jd'] = jd; return out
    mu, att, y0 = pack(scene); sol = propagate(rhs_for(mu, att), y0, 0.0, dt, accuracy=accuracy, h0=3600.0, h_min=1e-3, h_max=5 * DAY, record=False)
    Y = sol.y[-1].reshape(len(scene['bodies']), 6)
    for b, row in zip(out['bodies'], Y): b['r'] = row[:3].tolist(); b['v'] = row[3:].tolist()
    out['epoch_jd'] = jd; return out
