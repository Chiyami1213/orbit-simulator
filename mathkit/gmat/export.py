"""Write a GMAT R2022a ``.script`` from a Mission. Always GMAT convention (Luna, VNB, TA 0..360 ...), whatever the UI convention is.

GMAT is Apache-2.0 licensed software of NASA; this module only writes text in the script language it reads. "Compatible with GMAT R2022a"
describes the syntax; no GMAT code is included here.
"""
from __future__ import annotations
import re
from ..conventions import gmat_body, GMAT_BODY
from ..mission.model import Mission, Command

_BUILTIN_CS = {'EarthMJ2000Eq', 'EarthMJ2000Ec', 'EarthFixed', 'EarthICRF'}
_GMAT_INT = {'RungeKutta89': 'RungeKutta89', 'PrinceDormand78': 'PrinceDormand78', 'PrinceDormand45': 'PrinceDormand45', 'Kepler (analytic)': 'RungeKutta89'}


def _g(x) -> str:
    if isinstance(x, float): return repr(float(f'{x:.15g}'))
    return str(x)


def gmat_text(s: str) -> str:
    """Replace course body names inside a parameter / stop-condition string by GMAT names (Moon -> Luna)."""
    for k, v in GMAT_BODY.items(): s = re.sub(rf'\b{k}\b', v, s)
    return s


def export_script(m: Mission, expected: list[str] | None = None, warn_exam: bool | None = None) -> str:
    out: list[str] = []; a = out.append
    a('%  GMAT script written by Orbit Simulator (compatible with GMAT R2022a).'); a(f'%  Mission: {m.name}')
    if warn_exam is None: warn_exam = (m.constants == 'Exam rounded')
    if warn_exam:
        a('%  WARNING: this mission was built with the "Exam rounded" constants (e.g. mu_Earth = 4.0e5, R_Earth = 6400 km).')
        a('%  GMAT uses its own gravitational parameters, so GMAT results will differ slightly from the printed exam answers.')
    for line in (expected or []) + list(m.notes): a(f'% expected: {line}' if not line.startswith('%') else line)
    approximated = [p.name for p in m.propagators if p.dynamics == 'cr3bp' or p.integrator == 'Kepler (analytic)']
    for n in approximated: a(f'%  note: propagator {n} uses a model GMAT does not have (analytic Kepler or the circular restricted three-body problem); exported as the closest GMAT force model.')
    a('')
    for sc in m.spacecraft:
        a(f'Create Spacecraft {sc.name};')
        a(f'{sc.name}.DateFormat = {sc.date_format};'); ep = sc.epoch if sc.date_format == 'UTCGregorian' else sc.epoch
        a(f"{sc.name}.Epoch = '{ep}';")
        a(f'{sc.name}.CoordinateSystem = {gmat_text(sc.coord)};'); a(f'{sc.name}.DisplayStateType = {sc.state_type};')
        keys = ('SMA', 'ECC', 'INC', 'RAAN', 'AOP', 'TA') if sc.state_type == 'Keplerian' else ('X', 'Y', 'Z', 'VX', 'VY', 'VZ')
        a(' '.join(f'{sc.name}.{k} = {_g(sc.state[k])};' for k in keys))
        a(f'{sc.name}.DryMass = {_g(sc.mass)}; {sc.name}.Cr = {_g(sc.cr)}; {sc.name}.SRPArea = {_g(sc.area)};'); a('')
    for p in m.propagators:
        fm = f'FM_{p.name}'; bodies = [gmat_body(b) for b in ([p.central] + [g for g in p.gravity if g != p.central])]
        if p.dynamics == 'solar_system':
            bodies = [gmat_body(b) for b in ([p.central] + [b for b in ('Sun', 'Moon', 'Mercury', 'Venus', 'Earth', 'Mars', 'Jupiter', 'Saturn', 'Uranus', 'Neptune', 'Pluto') if b != p.central])]
        if p.dynamics == 'two_body': bodies = [gmat_body(p.central)]
        a(f'Create ForceModel {fm};'); a(f'{fm}.CentralBody = {gmat_body(p.central)};'); a(f'{fm}.PointMasses = {{{", ".join(bodies)}}};')
        a(f'{fm}.Drag = None;'); a(f'{fm}.SRP = {"On" if p.srp else "Off"};'); a('')
        a(f'Create Propagator {p.name};'); a(f'{p.name}.FM = {fm};'); a(f'{p.name}.Type = {_GMAT_INT[p.integrator]};')
        a(f'{p.name}.InitialStepSize = {_g(p.initial_step)};'); a(f'{p.name}.Accuracy = {_g(p.accuracy)};'); a(f'{p.name}.MinStep = {_g(p.min_step)};'); a(f'{p.name}.MaxStep = {_g(p.max_step)};'); a('')
    for c in m.coords:
        if c.name in _BUILTIN_CS: continue
        a(f'Create CoordinateSystem {gmat_text(c.name)};'); a(f'{gmat_text(c.name)}.Origin = {gmat_body(c.origin)};'); a(f'{gmat_text(c.name)}.Axes = {c.axes};'); a('')
    for b in m.burns:
        a(f'Create ImpulsiveBurn {b.name};'); a(f'{b.name}.CoordinateSystem = Local;'); a(f'{b.name}.Origin = {gmat_body(b.origin)};'); a(f'{b.name}.Axes = {b.axes};')
        a(f'{b.name}.Element1 = {_g(b.e1)}; {b.name}.Element2 = {_g(b.e2)}; {b.name}.Element3 = {_g(b.e3)};'); a('')
    for r in m.reports:
        a(f'Create ReportFile {r.name};'); a(f"{r.name}.Filename = '{r.filename}';"); a(f'{r.name}.Add = {{{", ".join(gmat_text(p) for p in r.params)}}};')
        a(f'{r.name}.WriteHeaders = On;'); a('')
    for v in m.views:
        a(f'Create OrbitView {v.name};'); a(f'{v.name}.Add = {{{", ".join(gmat_body(o) for o in v.objects)}}};'); a(f'{v.name}.CoordinateSystem = {gmat_text(v.coord)};')
        a(f'{v.name}.XYPlane = {"On" if v.xy_plane else "Off"}; {v.name}.Axes = {"On" if v.axes else "Off"}; {v.name}.Grid = {"On" if v.grid else "Off"};'); a('')
    a('BeginMissionSequence;')
    for c in m.commands:
        pre = '' if c.enabled else '% disabled: '
        if c.kind == 'Propagate':
            body = ' '.join(f'{p}({", ".join(s)})' for p, s in c.items)
            a(f'{pre}Propagate {"Synchronized " if c.synchronized else ""}{body} {{{", ".join(gmat_text(s) for s in c.stops)}}};')
        elif c.kind == 'Maneuver': a(f'{pre}Maneuver {c.burn}({c.sat});')
        elif c.kind == 'Report': a(f'{pre}Report {c.report} {" ".join(gmat_text(p) for p in c.params)};')
        elif c.kind == 'Toggle': a(f'{pre}Toggle {c.report} {"On" if c.on else "Off"};')
    return '\n'.join(out) + '\n'
