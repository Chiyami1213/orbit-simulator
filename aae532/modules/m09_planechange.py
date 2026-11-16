"""Module 9 - plane change (HW8 P3, HW11 P2): single burn at the node vs. three-burn (bi-elliptic) maneuver.

Single burn: the plane rotates about the line of nodes (r-hat axis), so v_r is unchanged and the transverse component
v_theta = v cos(gamma) rotates through di:  dv = 2 v cos(gamma) sin(di/2)  (core.plane_change with v -> v cos gamma;
for a circular orbit this is the textbook 2 v sin(di/2)).
Three burns: raise apoapsis to r_a in the old plane, change plane at r_a (little v there), return to r in the new plane.
"""
from __future__ import annotations
import numpy as np
from ..core.constants import D2R, R2D
from ..core.transfers import plane_change
from ..core.conic import gamma_of, r_of, v_of
from ..results import Result, KM, KMS, DEG, SEC, HR, DAY, NONE
from ..scene import Scene, Orbit, Disk, Pt, Plane, vector, angle_arc, nodes_line, unit_triad, unit
from .common import vel_scale, pe_from_spec


def Rx(deg: float) -> np.ndarray:
    c, s = np.cos(deg * D2R), np.sin(deg * D2R); return np.array([[1.0, 0, 0], [0, c, -s], [0, s, c]])


def solve(mu: float, orbit: dict, d_inc: float, ths_node: float = 0.0, r_apo: float | None = None, body_R: float | None = None,
          body_name: str = '', label: str = 'Module 9') -> Result:
    """orbit: conic spec; d_inc in deg; ths_node: true anomaly of the node (deg); r_apo: bi-elliptic apoapsis radius (circular case)."""
    res = Result('Plane change', label, inputs=dict(mu=mu, orbit=orbit, d_inc=d_inc, ths_node=ths_node, r_apo=r_apo))
    p, e = pe_from_spec(orbit); a = p / (1 - e * e); rn = r_of(p, e, ths_node); v = v_of(mu, rn, a); gam = float(gamma_of(e, ths_node))
    vth = v * np.cos(gam * D2R); dv1 = plane_change(vth, d_inc)
    g = 'Single burn at the node'
    res.add('Radius at the node', 'r', rn, KM, group=g); res.add('Speed at the node', 'v', v, KMS, group=g); res.add('Flight-path angle', 'γ', gam, DEG, group=g)
    res.add('Transverse speed', 'v_θ', vth, KMS, 'v cosγ', group=g)
    res.add('Plane-change impulse', 'Δv', dv1, KMS, 'Δv = 2 v_θ sin(Δi/2)', group=g)
    v1_ = np.array([v * np.sin(gam * D2R), v * np.cos(gam * D2R), 0.0]); c_, s_ = np.cos(d_inc * D2R), np.sin(d_inc * D2R)
    v2_ = np.array([v1_[0], v1_[1] * c_, v1_[1] * s_]); dvv = v2_ - v1_; Vh = unit(v1_); Nh = np.array([0, 0, 1.0]); Ch = np.cross(Vh, Nh)
    al = np.degrees(np.arctan2(dvv @ Ch, dvv @ Vh)); be = np.degrees(np.arcsin(np.clip(dvv @ Nh / np.linalg.norm(dvv), -1, 1)))
    res.add('Impulse angle α (in plane, from v̄⁻)', 'α', al, DEG, 'α = atan2(Δv̄·Ĉ, Δv̄·V̂)', group=g)
    res.add('Impulse angle β (out of plane)', 'β', be, DEG, 'sinβ = Δv̄·N̂/Δv  (= 90° − Δi/2 for a circular orbit with α = 180°)', group=g)
    res.data.update(dv_single=dv1, v=v, r=rn)
    bi = None
    if r_apo and e < 1e-9:
        r = rn; a1 = (r + r_apo) / 2; vc = np.sqrt(mu / r); vp = np.sqrt(mu * (2 / r - 1 / a1)); va = np.sqrt(mu * (2 / r_apo - 1 / a1))
        d1 = vp - vc; d2 = plane_change(va, d_inc); d3 = d1; P_ = 2 * np.pi * np.sqrt(a1 ** 3 / mu)
        g = 'Three-burn (bi-elliptic) plane change'
        res.add('Burn 1 at r (raise apoapsis)', 'Δv₁', d1, KMS, group=g); res.add('Burn 2 at r_a (plane change)', 'Δv₂', d2, KMS, 'Δv₂ = 2 v_a sin(Δi/2)', group=g)
        res.add('Burn 3 at r (circularize)', 'Δv₃', d3, KMS, group=g); res.add('Total Δv', 'Δv_tot', d1 + d2 + d3, KMS, group=g)
        res.add('Time of flight', 'TOF', P_ / 3600, HR, 'TOF = P of the transfer ellipse = 2π√(a³/μ)', group=g)
        res.add('Time of flight', 'TOF', P_ / 86400, DAY, group=g)
        res.add('Savings vs single burn', 'ΔΔv', dv1 - (d1 + d2 + d3), KMS, 'positive ⇒ three burns are cheaper', group=g)
        res.add('Cheaper option', '', 'three-burn' if d1 + d2 + d3 < dv1 else 'single burn', NONE, group=g)
        bi = dict(dv1=d1, dv2=d2, dv3=d3, dv=d1 + d2 + d3, tof=P_, a1=a1, vp=vp, va=va); res.data['bi'] = bi
    elif r_apo: res.warn('three-burn option implemented for circular initial orbits only')
    # ---------------- scene (node on +x; 2-D view looks along the line of nodes) ----------------
    ref = (r_apo or p / (1 - e) if e < 1 else rn)
    R2 = Rx(d_inc)
    sc = Scene(f'plane change Δi = {d_inc:g}°', label, is3d=True)
    if body_R: sc.disks.append(Disk(np.zeros(3), body_R, ''))
    sc.pts.append(Pt(np.zeros(3), f'F ({body_name})' if body_name else 'F', 'ink', 'o', 5))
    if e < 1e-9:
        sc.orbits.append(Orbit('orbit before', p, 0.0, np.eye(3), 'orbit')); sc.orbits.append(Orbit('orbit after', p, 0.0, R2, 'orbit2'))
    else:
        sc.orbits.append(Orbit('orbit before', p, e, np.eye(3), 'orbit')); sc.orbits.append(Orbit('orbit after', p, e, R2, 'orbit2'))
    sc.planes.append(Plane(np.array([0, 0, 1.0]), 1.05 * ref, 'plane before', role='orbit')); sc.planes.append(Plane(R2[:, 2], 1.05 * ref, 'plane after', role='orbit2'))
    node = np.array([rn, 0, 0]); sc.pts.append(Pt(node, 'node', 'ink', 'D', 6))
    nodes_line(sc, 0.0, 1.1 * ref, 'line of nodes')
    v1 = np.array([0, v, 0]) if abs(gam) < 1e-9 else np.array([v * np.sin(gam * D2R), v * np.cos(gam * D2R), 0]); v2 = R2 @ v1
    vs = vel_scale(ref, v, 0.25)
    vector(sc, node, v1, f'v̄⁻ ({v:.4g})', 'vel', scale=vs); vector(sc, node, v2, 'v̄⁺', 'orbit3', scale=vs)
    vector(sc, node + v1 * vs, v2 - v1, f'Δv̄ ({dv1:.4g} km/s)', 'dv', scale=vs)
    angle_arc(sc, node, unit(v1), unit(v2), 0.12 * ref, f'Δi = {d_inc:g}°', 'ink', np.array([1.0, 0, 0]))
    if bi:
        a1 = bi['a1']; pT = a1 * (1 - ((r_apo - rn) / (r_apo + rn)) ** 2); eT = (r_apo - rn) / (r_apo + rn)
        sc.orbits.append(Orbit('three-burn leg 1 (old plane)', pT, eT, np.eye(3), 'accent', ths_range=(0, 180), dash=True))
        sc.orbits.append(Orbit('three-burn leg 2 (new plane)', pT, eT, R2, 'accent', ths_range=(180, 360), dash=True))
        sc.pts.append(Pt(np.array([-r_apo, 0, 0]), f'Δv₂ at r_a = {bi["dv2"]:.4g}', 'dv', 'D', 6))
    sc.plane2d = (np.array([0, 1.0, 0]), np.array([0, 0, 1.0]))      # look along the line of nodes
    sc.notes.append('2-D view looks along the line of nodes (both orbit planes edge-on); the velocity triangle is in true shape.')
    res.scene = sc
    return res
