"""Build a Mission from a course module result ("Open in Mission" / GMAT export for every module).

The mission reproduces the module's analytic answer when run with the Kepler (analytic) integrator, and to ~1e-8 relative with the
numerical two-body integrator. Modules without a spacecraft trajectory (1, 2, 9, 10, 11) return a short explanation instead.
"""
from __future__ import annotations
import numpy as np
from ..core.constants import ConstantSet, BODIES, wrap180
from ..core.elements import elements_from_rv
from ..conventions import vnb_from_dv_alpha_beta
from .model import Mission, Spacecraft, CoordSys, Propagator, Burn, ReportFile, OrbitView, Command

EPOCH = '01 Jan 2026 12:00:00.000'


class NotAvailable(ValueError):
    pass


def _base(name: str, body: str, consts: ConstantSet) -> Mission:
    m = Mission(name=name, constants=consts.mode)
    cs = 'EarthMJ2000Eq' if body == 'Earth' else f'{"Luna" if body == "Moon" else body}MJ2000Eq'
    if cs != 'EarthMJ2000Eq': m.coords.append(CoordSys(cs, body, 'MJ2000Eq'))
    m.propagators.append(Propagator('Prop', body, 'two_body', [body], 'RungeKutta89'))
    m.reports.append(ReportFile('RF', f'{name.replace(" ", "_")}_report.txt', ['Sat.UTCGregorian', f'Sat.{"Luna" if body == "Moon" else body}.SMA', f'Sat.{"Luna" if body == "Moon" else body}.ECC',
                                                                                f'Sat.{"Luna" if body == "Moon" else body}.TA', f'Sat.{"Luna" if body == "Moon" else body}.RMAG', f'Sat.{"Luna" if body == "Moon" else body}.VMAG', f'Sat.{"Luna" if body == "Moon" else body}.VFPA']))
    m.views.append(OrbitView('View', ['Sat', body], cs)); m._cs = cs                      # type: ignore[attr-defined]
    return m


def _sat(m: Mission, a, e, inc, om_big, om, ths, color='#ff6b4a') -> Spacecraft:
    sc = Spacecraft('Sat', 'UTCGregorian', EPOCH, m._cs, 'Keplerian', dict(SMA=float(a), ECC=float(e), INC=float(inc), RAAN=float(om_big), AOP=float(om), TA=float(ths % 360.0)), color=color)   # type: ignore[attr-defined]
    m.spacecraft.append(sc); return sc


def _prop(m: Mission, stops: list[str]):
    m.commands.append(Command('Propagate', items=[['Prop', ['Sat']]], stops=stops))


def _fix(m: Mission):
    if hasattr(m, '_cs'): del m._cs                                            # type: ignore[attr-defined]
    return m


def from_module(mid: str, vals: dict, res, consts: ConstantSet) -> Mission:
    d = res.data; label = vals.get('_label') or f'Module {mid}'; body = vals.get('body', vals.get('central', 'Earth'))
    G = {'Moon': 'Luna'}.get(body, body)
    if mid == '3':
        m = _base(f'{label} (module 3)', body, consts); a, e = float(d['a']), float(d['e'])
        _sat(m, a, e, 0, 0, float(d.get('omega', 0.0)), float(d['ths']))
        if e < 1:
            m.notes += [f'a = {a:.6f} km, e = {e:.8f}, r = {float(d["r"]):.6f} km, v = {float(d["v"]):.8f} km/s, gamma = {float(d["gamma"]):.6f} deg']
            _prop(m, [f'Sat.{G}.Apoapsis']); _prop(m, [f'Sat.{G}.Periapsis'])
        else:
            _prop(m, [f'Sat.{G}.ElapsedSecs = 3600'])
        return _fix(m)
    if mid == '4':
        m = _base(f'{label} (module 4)', body, consts)
        a_ = float(d['p']) / (1 - _ecc(d, consts, body) ** 2); e_ = _ecc(d, consts, body)
        _sat(m, a_, e_, 0, 0, 0, float(d['th0']))
        m.notes += [f'after {float(d["tof_s"]):.6f} s: theta* = {float(d["th1"]):.6f} deg, r = {float(d["r1"]):.6f} km, v = {float(d["v1"]):.8f} km/s']
        _prop(m, [f'Sat.ElapsedSecs = {float(d["tof_s"])!r}']); return _fix(m)
    if mid == '5':
        hy = d['hy']; m = _base(f'{label} (module 5)', body, consts); ths = abs(float(vals.get('ths', 120.0))) or 120.0
        _sat(m, float(hy['a']), float(hy['e']), 0, 0, 0, -ths)
        m.notes += [f'v_inf = {float(hy["vinf"]):.8f} km/s, theta*_inf = {float(hy["th_inf"]):.6f} deg, turn angle delta = {float(hy["delta"]):.6f} deg (approached, not reached, at finite time)']
        _prop(m, [f'Sat.{G}.TA = {ths!r}']); return _fix(m)
    if mid == '6':
        m = _base(f'{label} (module 6)', body, consts)
        _sat(m, float(d['a']), float(d['e']), float(d['inc']), float(d['Om']), float(d['om']), float(d['ths']))
        m.notes += [f'r = {float(d["r"]):.6f} km, v = {float(d["v"]):.8f} km/s, gamma = {float(d["gamma"]):.6f} deg']
        if float(d['e']) < 1: _prop(m, [f'Sat.ElapsedSecs = {float(d["P"])!r}'])
        else: _prop(m, [f'Sat.ElapsedSecs = 3600'])
        return _fix(m)
    if mid == '7':
        b = d['best']; m = _base(f'{label} (module 7)', body, consts); p1, e1 = float(d['p1']), float(d['e1']); a1 = p1 / (1 - e1 ** 2)
        _sat(m, a1, e1, 0, 0, 0, float(b['th1']))
        m.burns.append(Burn('DV1', body, 'VNB', float(b['dV']), 0.0, float(b['dC'])))
        m.notes += [f'dv = {float(b["dv"]):.8f} km/s, alpha = {float(b["alpha"]):.6f} deg; new orbit p = {float(d["p2"]):.4f} km, e = {float(d["e2"]):.8f}']
        m.commands += [Command('Maneuver', burn='DV1', sat='Sat')]; _prop(m, ['Sat.ElapsedSecs = 3600']); return _fix(m)
    if mid == '8':
        h = d['hohmann']; r1 = float(vals['r1']); m = _base(f'{label} (module 8)', body, consts)
        _sat(m, r1, 0.0, 0, 0, 0, 0.0)
        m.burns += [Burn('DV1', body, 'VNB', float(h['dv1'])), Burn('DV2', body, 'VNB', float(h['dv2']))]
        m.notes += [f'dv1 = {float(h["dv1"]):.8f} km/s, dv2 = {float(h["dv2"]):.8f} km/s, transfer time = {float(h["tof"]):.4f} s']
        m.commands += [Command('Maneuver', burn='DV1', sat='Sat'), Command('Propagate', items=[['Prop', ['Sat']]], stops=[f'Sat.{G}.Apoapsis']), Command('Maneuver', burn='DV2', sat='Sat'),
                       Command('Propagate', items=[['Prop', ['Sat']]], stops=['Sat.ElapsedSecs = 3600'])]
        return _fix(m)
    if mid == '12':
        s = d['sel']; m = _base(f'{label} (module 12)', body, consts); r1 = float(d['r1']); sc = Spacecraft('Sat', 'UTCGregorian', EPOCH, m._cs, 'Cartesian',    # type: ignore[attr-defined]
                                                                                                          dict(X=r1, Y=0.0, Z=0.0, VX=float(s['vD'][0]), VY=float(s['vD'][1]), VZ=float(s['vD'][2]) if len(s['vD']) > 2 else 0.0))
        m.spacecraft.append(sc)
        m.notes += [f'transfer: a = {float(s["a"]):.6f} km, e = {float(s["e"]):.8f}, tof = {float(d["tof"]):.6f} s, dv_D = {float(s["dvD_mag"]):.8f} km/s, dv_A = {float(s["dvA_mag"]):.8f} km/s']
        _prop(m, [f'Sat.ElapsedSecs = {float(d["tof"])!r}']); return _fix(m)
    raise NotAvailable(f'Module {mid} has no spacecraft trajectory to send to the Mission workspace (use modules 3-8 or 12).')


def _ecc(d, consts, body) -> float:
    r0, v0, g0 = float(d['r0']), float(d['v0']), float(d['gamma0'])
    mu = consts.mu(body); vr = v0 * np.sin(np.radians(g0)); h = r0 * v0 * np.cos(np.radians(g0)); p = h * h / mu
    return float(np.sqrt(max(0.0, (p / r0 - 1) ** 2 + (vr * h / mu) ** 2)))
