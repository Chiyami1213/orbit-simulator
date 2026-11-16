"""Module 1 - N-body accelerations (HW2 P1-2, HW3 P1, Exam 1 P1).

Acceleration of a target body relative to a chosen central body: dominant two-body term, direct and indirect perturbations
(one pair per additional body), net perturbation and total. Arrows are drawn in two scales (dominant/total together, perturbations
together) because the dominant term is usually orders of magnitude larger; the scale factors are stated in the figure notes.
"""
from __future__ import annotations
import numpy as np
from ..core.nbody import nbody_relative, rank_terms
from ..results import Result, KM, MU, ACC, NONE
from ..scene import Scene, Pt, Line, vector, unit_triad, unit

LAYOUTS = {
    'collinear': lambda d: [np.array([0.0, 0, 0]), np.array([d, 0, 0]), np.array([2 * d, 0, 0])],
    'equilateral triangle': lambda d: [np.array([0.0, 0, 0]), np.array([d, 0, 0]), np.array([d / 2, d * np.sqrt(3) / 2, 0])],
}


def solve(bodies: list[dict], central: int, target: int, label: str = 'Module 1') -> Result:
    """bodies: [{'name', 'mu' (km³/s²), 'pos' (km, 3-vector)}, ...]; indices of the central body and the target."""
    res = Result('N-body accelerations', label, inputs=dict(bodies=[{k: (list(v) if hasattr(v, '__len__') and not isinstance(v, str) else v) for k, v in b.items()} for b in bodies],
                                                          central=central, target=target))
    mus = [b['mu'] for b in bodies]; pos = [np.asarray(b['pos'], float) for b in bodies]
    nm = lambda i: bodies[i]['name']
    R = nbody_relative(mus, pos, central, target); res.data.update(R)
    g = 'Setup'
    res.add('Central body', '', nm(central), group=g); res.add('Target body', '', nm(target), group=g)
    res.add('Relative position r̄_ic = r̄_i − r̄_c', 'r̄_ic', R['r_ic'], KM, group=g); res.add('Distance', 'r', np.linalg.norm(R['r_ic']), KM, group=g)
    res.add('Center of mass', 'r̄_cm', R['center_of_mass'], KM, 'Σμ r̄/Σμ', group=g)
    res.check('target spacecraft/body mass handled through (μ_c + μ_i) in the dominant term; pass μ_i = 0 for a spacecraft')
    g = 'Accelerations'
    res.add('Dominant two-body term', 'ā_dom', R['dominant'], 'km·s⁻²', 'ā = −(μ_c + μ_i) r̄_ic/r³', group=g); res.add('|ā_dom|', 'a_dom', R['dominant_mag'], 'km·s⁻²', group=g)
    for t in R['terms']:
        j = t['j']
        res.add(f'Direct from {nm(j)}', f'ā_dir,{nm(j)}', t['direct'], 'km·s⁻²', 'μ_j (r̄_j − r̄_i)/|r̄_j − r̄_i|³', group=g)
        res.add(f'Indirect from {nm(j)}', f'ā_ind,{nm(j)}', t['indirect'], 'km·s⁻²', '−μ_j (r̄_j − r̄_c)/|r̄_j − r̄_c|³', group=g)
        res.add(f'Net perturbation from {nm(j)}', f'ā_pert,{nm(j)}', t['net'], 'km·s⁻²', 'direct + indirect', group=g)
    res.add('Total direct', 'ā_dir', R['direct'], 'km·s⁻²', group=g); res.add('|ā_dir|', 'a_dir', R['direct_mag'], 'km·s⁻²', group=g)
    res.add('Total indirect', 'ā_ind', R['indirect'], 'km·s⁻²', group=g); res.add('|ā_ind|', 'a_ind', R['indirect_mag'], 'km·s⁻²', group=g)
    res.add('Net perturbing acceleration', 'ā_pert', R['net_pert'], 'km·s⁻²', group=g); res.add('|ā_pert|', 'a_pert', R['net_pert_mag'], 'km·s⁻²', group=g)
    res.add('Total relative acceleration', 'ā_tot', R['total'], 'km·s⁻²', 'dominant + net perturbing', group=g); res.add('|ā_tot|', 'a_tot', R['total_mag'], 'km·s⁻²', group=g)
    res.add('Perturbing / dominant', 'a_pert/a_dom', R['pert_over_dominant'], NONE, group=g)
    rk = rank_terms(R); res.add('Ranking, largest first', 'rank', ' > '.join(f'{k} ({v:.3e})' for k, v in rk), NONE, group='Ranking')
    # ---------------- scene ----------------
    P = np.array(pos); ref = max(np.ptp(P, axis=0).max(), 1.0)
    sc = Scene('N-body relative accelerations', label);
    for i, b in enumerate(bodies):
        sc.pts.append(Pt(pos[i], b['name'] + (' (central)' if i == central else ' (target)' if i == target else ''), 'ink' if i in (central, target) else 'ink2', 'o', 9 if i == central else 7))
    sc.pts.append(Pt(R['center_of_mass'], 'center of mass', 'muted', '+', 8))
    s_big = 0.28 * ref / max(R['dominant_mag'], R['total_mag'], 1e-300); s_pert = 0.28 * ref / max(R['direct_mag'], R['indirect_mag'], R['net_pert_mag'], 1e-300)
    ot = pos[target]
    vector(sc, ot, R['dominant'], 'ā_dom', 'orbit', scale=s_big)
    vector(sc, ot, R['direct'], 'ā_dir', 'orbit2', scale=s_pert); vector(sc, ot, R['indirect'], 'ā_ind', 'orbit3', scale=s_pert)
    vector(sc, ot, R['net_pert'], 'ā_pert (net)', 'dv', scale=s_pert); vector(sc, ot, R['total'], 'ā_tot', 'accent', scale=s_big)
    for i in range(len(bodies)):
        if i != target: sc.lines.append(Line(ot, pos[i], '', 'muted', True, 0.6))
    ur = unit(-R['r_ic']); vector(sc, ot, ur, 'û (toward central body)', 'muted', scale=0.12 * ref)
    sc.notes += [f'dominant and total arrows: {s_big:.3g} km per (km/s²); perturbing arrows: {s_pert:.3g} km per (km/s²) — different scales']
    sc.is3d = bool(np.any(np.abs(P[:, 2]) > 1e-9))
    res.scene = sc
    return res
