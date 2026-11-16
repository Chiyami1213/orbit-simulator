"""Module registry: form fields, `run` adapters (form values -> module.solve) and preset types.

Values handed to ``run`` are ALWAYS in km, km/s, degrees, seconds (the UI converts from R_body / AU / hours first), so presets
and the Test-cases page exercise exactly the same code path as the app.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable, Optional
import numpy as np
from .core.constants import ConstantSet, BODIES, AU
from .results import Result

BODY_NAMES = list(BODIES)
YEAR_S = 365.25 * 86400


@dataclass
class Field:
    key: str
    label: str
    default: Any
    kind: str = 'float'          # float | int | choice | text | bool | vec
    options: Optional[list] = None
    dist: bool = False           # a distance in km (UI offers km / R_body / AU)
    unit: str = ''               # display unit string, e.g. 'km·s⁻¹' or '°'
    show_if: Optional[Callable[[dict], bool]] = None
    help: str = ''


@dataclass
class Expect:
    name: str
    get: Callable[[Result], float]
    value: float
    rtol: float = 2e-4
    note: str = ''


@dataclass
class Preset:
    label: str                   # e.g. "HW4 P1 — Anteros, propagate 6.4 months"
    vals: dict
    expected: list[Expect] = field(default_factory=list)
    consts: str = 'Course table'
    moon_R: float = 2000.0
    note: str = ''


@dataclass
class ModuleSpec:
    id: str
    title: str
    fields: list[Field]
    run: Callable[[dict, ConstantSet], Result]
    presets: list[Preset] = field(default_factory=list)
    body_key: Optional[str] = 'body'   # field whose body supplies R_body for unit conversion
    blurb: str = ''


def D(key, label, default, **kw): return Field(key, label, default, 'float', dist=True, unit='km', **kw)
def F(key, label, default, unit='', **kw): return Field(key, label, default, 'float', unit=unit, **kw)
def V(key, label, default, unit='', dist=False, **kw): return Field(key, label, default, 'vec', unit=unit, dist=dist, **kw)
def C(key, label, default, options, **kw): return Field(key, label, default, 'choice', options=options, **kw)
def T(key, label, default, **kw): return Field(key, label, default, 'text', **kw)


def vec3(x): return np.array(list(x) + [0.0] * (3 - len(x)), float)


# ---------------------------------------------------------------------------------------------------------------
# run adapters
# ---------------------------------------------------------------------------------------------------------------
from .modules import (m01_nbody, m02_twobody, m03_conic, m04_kepler, m05_hyperbola, m06_elements3d, m07_impulse, m08_transfers,
                      m09_planechange, m10_patched, m11_flyby, m12_lambert)


def _body(v, C, key='body'):
    n = v[key]; b = C.body(n); return n, b


def run01(v, C):
    bodies = []
    layout = v['layout']
    if layout != 'custom':
        pts = m01_nbody.LAYOUTS[layout](v['d'])
    for i in range(1, 5):
        if not v[f'b{i}_use']: continue
        pos = np.asarray(vec3(v[f'b{i}_pos']))
        if layout != 'custom' and i <= 3: pos = pts[i - 1]
        bodies.append(dict(name=v[f'b{i}_name'], mu=v[f'b{i}_mu'], pos=pos))
    names = [b['name'] for b in bodies]
    return m01_nbody.solve(bodies, names.index(v['central']), names.index(v['target']), v['_label'])


def run02(v, C):
    return m02_twobody.solve(v['m1'], v['m2'], vec3(v['r1']), vec3(v['r2']), vec3(v['v1']), vec3(v['v2']), v['G'], (v['n1'], v['n2']), v['_label'])


def run03(v, C):
    n, b = _body(v, C); mode = v['mode']; ths = None
    if mode == 'polar': vals = dict(r=v['r'], vr=v['vr'], vt=v['vt'])
    elif mode == 'xy': vals = dict(rx=v['rx'], ry=v['ry'], vx=v['vx'], vy=v['vy'])
    else:
        ths = v['ths']
        vals = {'h_eps': dict(h=v['h'], eps=v['eps']), 'rp_ra': dict(rp=v['rp'], ra=v['ra']), 'a_e': dict(a=v['a'], e=v['e']), 'p_e': dict(p=v['p'], e=v['e'])}[mode]
    return m03_conic.solve(b['mu'], mode, vals, ths, b['R'], n, v['_label'])


def run04(v, C):
    n, b = _body(v, C)
    a = v['a'] if v['a_kind'] == 'a' else None
    if v['a_kind'] == 'rp, ra': rp, ra = v['rp'], v['ra']; a = (rp + ra) / 2; e = (ra - rp) / (ra + rp)
    else: e = v['e']
    unit = {'s': 1, 'min': 60, 'h': 3600, 'd': 86400, '30-day months': 30 * 86400, 'years (365.25 d)': YEAR_S}
    if v['dt_mode'] == 'until θ*₁':
        from .core.kepler import time_since_periapsis
        th0 = v['start_val'] if v['start_kind'] == 'ths' else None
        if th0 is None: raise ValueError('"until θ*₁" needs the start given as θ*')
        P_ = 2 * np.pi * np.sqrt(a ** 3 / b['mu'])
        dt = (time_since_periapsis(b['mu'], a, e, v['end_ths']) - time_since_periapsis(b['mu'], a, e, th0)) % P_ + P_ * v['extra_revs']
    elif v['dt_unit'] == 'periods (P)':
        dt = v['dt'] * 2 * np.pi * np.sqrt(a ** 3 / b['mu'])
    else: dt = v['dt'] * unit[v['dt_unit']]
    start = {v['start_kind']: v['start_val']}
    return m04_kepler.solve(b['mu'], a, e, start, dt, b['R'], n, v['_label'])


def run05(v, C):
    n, b = _body(v, C); keys = v['combo'].split(' + ')
    mapk = {'r_p': 'rp', '|a|': 'a_abs', 'e': 'e', 'v∞': 'vinf'}      # label in the combo -> field key / argument name
    given = {mapk[k]: v[mapk[k]] for k in keys}
    return m05_hyperbola.solve(b['mu'], given, b['R'], n, v['ths'], v['e_cap'], v['_label'])


def run06(v, C):
    n, b = _body(v, C)
    if v['mode'] == 'elements':
        vals = dict(a=v['a'], e=v['e'], inc=v['inc'], Om=v['Om'], om=v['om'])
        vals['ths' if v['ang_kind'] == 'θ*' else 'theta'] = v['ang']
    else: vals = dict(r=vec3(v['r']), v=vec3(v['v']))
    return m06_elements3d.solve(b['mu'], v['mode'], vals, b['R'], n, v['_label'])


def _spec(v, pre, kinds):
    m = v[pre + '_mode']
    return {'r_p, r_a': dict(rp=v[pre + '_rp'], ra=v[pre + '_ra']), 'a, e': dict(a=v[pre + '_a'], e=v[pre + '_e']),
            'p, e': dict(p=v[pre + '_p'], e=v[pre + '_e']), 'circular r': dict(r=v[pre + '_r'])}[m]


def run07(v, C):
    n, b = _body(v, C)
    if v['sub'] == 'target orbit (find intersections)':
        return m07_impulse.solve_target(b['mu'], _spec(v, 'o1', None), _spec(v, 'o2', None), v['d_omega'], v['th_now'] if v['use_now'] else None, b['R'], n, v['_label'])
    el = dict(a=v['g_a'], e=v['g_e'], inc=v['g_inc'], Om=v['g_Om'], om=v['g_om'])
    return m07_impulse.solve_given(b['mu'], el, v['g_ths'], v['g_dv'], v['g_alpha'], v['g_beta'], b['R'], n, v['_label'])


def run08(v, C):
    n, b = _body(v, C)
    return m08_transfers.solve(b['mu'], v['r1'], v['r2'], v['rb'] if v['rb'] > 0 else None, v['e_t'], v['r2'] if v['e_t'] > 0 else None,
                               v['arrive'], b['R'], n, v['_label'])


def run09(v, C):
    n, b = _body(v, C)
    orbit = dict(r=v['r']) if v['o_mode'] == 'circular r' else dict(rp=v['rp'], ra=v['ra'])
    return m09_planechange.solve(b['mu'], orbit, v['d_inc'], v['ths_node'], v['r_apo'] if v['r_apo'] > 0 else None, b['R'], n, v['_label'])


def run10(v, C):
    c = C.body(v['central']); d = C.body(v['dep']); a = C.body(v['arr'])
    dep = dict(mu=d['mu'], R=d['R'], r=v['r_dep'], name=v['dep']); arr = dict(mu=a['mu'], R=a['R'], r=v['r_arr'], name=v['arr'])
    tr = dict(kind='hohmann') if v['tkind'] == 'Hohmann' else dict(kind='state', v_dep=tuple(v['vdep'][:2]), v_arr=tuple(v['varr'][:2]))
    return m10_patched.solve(c['mu'], dep, arr, tr, v['r_park'], v['r_cap'], v['e_cap'], v['central'], v['_label'])


def run11(v, C):
    c = C.body(v['central']); pl = C.body(v['planet']); planet = dict(mu=pl['mu'], R=pl['R'], r=v['r_pl'], name=v['planet'])
    if v['sub'] == 'free return':
        return m11_flyby.solve_free_return(c['mu'], planet, v['r_park'], v['TA'], v['central'], c['R'], v['_label'])
    vm = dict(v=v['vmag'], gamma=v['gamma']) if v['vm_mode'] == 'v, γ' else dict(vr=v['vr'], vt=v['vt'])
    return m11_flyby.solve(c['mu'], planet, vm, v['rp'], v['sense'], v['central'], v['_label'])


def run12(v, C):
    n, b = _body(v, C); kind = v['pos_kind']
    if kind == 'radii': pos = dict(kind='radii', r1=v['r1'], r2=v['r2'], TA=v['TA'])
    elif kind == 'vectors': pos = dict(kind='vectors', r1=vec3(v['r1v']), r2=vec3(v['r2v']))
    else: pos = dict(kind='radec', ra1=v['ra1'], dec1=v['dec1'], d1=v['d1'], ra2=v['ra2'], dec2=v['dec2'], d2=v['d2'])
    tm = {'tof': dict(mode='tof', tof_s=v['tof_h'] * 3600), 'minimum energy': dict(mode='minE'), 'given p': dict(mode='p', p=v['p'])}[v['t_mode']]
    return m12_lambert.solve(b['mu'], pos, tm, v['root'], b['R'], n, v['peri_R'] if v['peri_R'] > 0 else None, None, None, None, v['hz_pos'], v['_label'])


# ---------------------------------------------------------------------------------------------------------------
# field lists
# ---------------------------------------------------------------------------------------------------------------
BODY = lambda d='Earth': C('body', 'Central body', d, BODY_NAMES)
mode_is = lambda k, *vals: (lambda v: v.get(k) in vals)

M01 = [C('layout', 'Layout', 'custom', ['custom', 'collinear', 'equilateral triangle']), D('d', 'Spacing d (layout only)', 384400.0, show_if=lambda v: v['layout'] != 'custom')]
for i, (nm, mu, pos, use) in enumerate([('Earth', 398600.4415, [0, 0, 0], True), ('Moon', 4902.8005821478, [384400, 0, 0], True),
                                         ('Sun', 132712440017.99, [89758722.0, 119678296.0, 0], True), ('Spacecraft', 0.0, [42164, 0, 0], False)], 1):
    M01 += [Field(f'b{i}_use', f'Body {i} used', use, 'bool'), T(f'b{i}_name', f'Body {i} name', nm), F(f'b{i}_mu', f'Body {i} μ', mu, 'km³·s⁻²'), V(f'b{i}_pos', f'Body {i} position', pos, 'km', dist=True)]
M01 += [T('central', 'Central body (name)', 'Earth'), T('target', 'Target body (name)', 'Moon')]

M02 = [F('m1', 'm₁ (or μ₁ with G = 1)', 5.0), F('m2', 'm₂ (or μ₂ with G = 1)', 3.0), F('G', 'G', 1.0), T('n1', 'Name 1', 'm₁'), T('n2', 'Name 2', 'm₂'),
       V('r1', 'r̄₁', [0, 0, 0], 'km'), V('r2', 'r̄₂', [4, 0, 0], 'km'), V('v1', 'v̄₁', [0, 0, 0], 'km·s⁻¹'), V('v2', 'v̄₂', [0, 1.2, 0], 'km·s⁻¹')]

M03 = [BODY(), C('mode', 'Input', 'polar', ['polar', 'xy', 'h_eps', 'rp_ra', 'a_e', 'p_e']),
       D('r', 'r', 14938.5, show_if=mode_is('mode', 'polar')), F('vr', 'v_r', -2.11, 'km·s⁻¹', show_if=mode_is('mode', 'polar')), F('vt', 'v_θ = r·θ̇', 4.89, 'km·s⁻¹', show_if=mode_is('mode', 'polar')),
       D('rx', 'r_x', 10000.0, show_if=mode_is('mode', 'xy')), D('ry', 'r_y', 5000.0, show_if=mode_is('mode', 'xy')),
       F('vx', 'v_x', -2.0, 'km·s⁻¹', show_if=mode_is('mode', 'xy')), F('vy', 'v_y', 5.0, 'km·s⁻¹', show_if=mode_is('mode', 'xy')),
       F('h', 'h', 8.0e4, 'km²·s⁻¹', show_if=mode_is('mode', 'h_eps')), F('eps', 'ε', -10.0, 'km²·s⁻²', show_if=mode_is('mode', 'h_eps')),
       D('rp', 'r_p', 7000.0, show_if=mode_is('mode', 'rp_ra')), D('ra', 'r_a', 45000.0, show_if=mode_is('mode', 'rp_ra')),
       D('a', 'a (negative = hyperbola)', 15942.3, show_if=mode_is('mode', 'a_e')), F('e', 'e', 0.4, show_if=mode_is('mode', 'a_e', 'p_e')),
       D('p', 'p', 13386.7, show_if=mode_is('mode', 'p_e')),
       F('ths', 'θ*', 90.0, '°', show_if=mode_is('mode', 'h_eps', 'rp_ra', 'a_e', 'p_e'))]

M04 = [BODY(), C('a_kind', 'Size given as', 'a', ['a', 'rp, ra']), D('a', 'a', 64000.0, show_if=mode_is('a_kind', 'a')), F('e', 'e', 0.75, show_if=mode_is('a_kind', 'a')),
       D('rp', 'r_p', 6000.0, show_if=mode_is('a_kind', 'rp, ra')), D('ra', 'r_a', 24000.0, show_if=mode_is('a_kind', 'rp, ra')),
       C('start_kind', 'Start from', 'M', ['ths', 'M', 'E']), F('start_val', 'Start value', 90.0, '°'),
       C('dt_mode', 'Time of flight', 'Δt', ['Δt', 'until θ*₁']),
       F('dt', 'Δt', 2.0, show_if=mode_is('dt_mode', 'Δt')), C('dt_unit', 'Δt unit', 'h', ['s', 'min', 'h', 'd', '30-day months', 'years (365.25 d)', 'periods (P)'], show_if=mode_is('dt_mode', 'Δt')),
       F('end_ths', 'θ*₁ (target true anomaly; start must be given as θ*)', -120.0, '°', show_if=mode_is('dt_mode', 'until θ*₁')),
       Field('extra_revs', 'Extra whole revolutions', 0, 'int', show_if=mode_is('dt_mode', 'until θ*₁'))]

M05 = [BODY('Venus'), C('combo', 'Given (any two)', 'r_p + |a|', ['r_p + |a|', 'r_p + e', 'r_p + v∞', '|a| + e', 'e + v∞']),
       D('rp', 'r_p', 60519.0, show_if=lambda v: 'r_p' in v['combo']), D('a_abs', '|a|', 302595.0, show_if=lambda v: '|a|' in v['combo']),
       F('e', 'e', 1.2, show_if=lambda v: 'e' in v['combo'].replace('v∞', '').replace('r_p', '')), F('vinf', 'v∞', 1.0, 'km·s⁻¹', show_if=lambda v: 'v∞' in v['combo']),
       F('ths', 'θ* for the time/velocity readout', -110.0, '°'), F('e_cap', 'Capture-orbit eccentricity (0 = circular)', 0.0)]

M06 = [BODY(), C('mode', 'Direction', 'elements', ['elements', 'state']),
       D('a', 'a', 420957.0, show_if=mode_is('mode', 'elements')), F('e', 'e', 0.9118, show_if=mode_is('mode', 'elements')), F('inc', 'i', 34.0, '°', show_if=mode_is('mode', 'elements')),
       F('Om', 'Ω', 60.0, '°', show_if=mode_is('mode', 'elements')), F('om', 'ω', 0.0, '°', show_if=mode_is('mode', 'elements')),
       C('ang_kind', 'Angle given', 'θ', ['θ*', 'θ'], show_if=mode_is('mode', 'elements')), F('ang', 'angle value', 235.0, '°', show_if=mode_is('mode', 'elements')),
       V('r', 'r̄ (x̂ŷẑ)', [13520.0, 17420.0, -3830.0], 'km', dist=True, show_if=mode_is('mode', 'state')), V('v', 'v̄ (x̂ŷẑ)', [-3.4, 1.62, 2.9], 'km·s⁻¹', show_if=mode_is('mode', 'state'))]


def _orbit_fields(pre, title, defaults, show=None):
    s = show or (lambda v: True)
    return [C(f'{pre}_mode', f'{title}: given', defaults['mode'], ['r_p, r_a', 'a, e', 'p, e', 'circular r'], show_if=s),
            D(f'{pre}_rp', f'{title}: r_p', defaults['rp'], show_if=lambda v: s(v) and v[f'{pre}_mode'] == 'r_p, r_a'), D(f'{pre}_ra', f'{title}: r_a', defaults['ra'], show_if=lambda v: s(v) and v[f'{pre}_mode'] == 'r_p, r_a'),
            D(f'{pre}_a', f'{title}: a', defaults['a'], show_if=lambda v: s(v) and v[f'{pre}_mode'] == 'a, e'), F(f'{pre}_e', f'{title}: e', defaults['e'], show_if=lambda v: s(v) and v[f'{pre}_mode'] in ('a, e', 'p, e')),
            D(f'{pre}_p', f'{title}: p', defaults['p'], show_if=lambda v: s(v) and v[f'{pre}_mode'] == 'p, e'), D(f'{pre}_r', f'{title}: r', defaults['r'], show_if=lambda v: s(v) and v[f'{pre}_mode'] == 'circular r')]


_t = lambda v: v['sub'] == 'target orbit (find intersections)'
M07 = [BODY(), C('sub', 'Problem', 'target orbit (find intersections)', ['target orbit (find intersections)', 'given Δv, α, β']),
       *_orbit_fields('o1', 'Old orbit', dict(mode='r_p, r_a', rp=7000.0, ra=45000.0, a=26000.0, e=0.7, p=13000.0, r=25000.0), _t),
       *_orbit_fields('o2', 'Target orbit', dict(mode='circular r', rp=7000.0, ra=45000.0, a=26000.0, e=0.5, p=13000.0, r=25000.0), _t),
       F('d_omega', 'Δω (rotation of line of apsides)', 0.0, '°', show_if=_t), Field('use_now', 'Compute wait time', False, 'bool', show_if=_t), F('th_now', 'Current θ*', 0.0, '°', show_if=_t),
       D('g_a', 'a', 51025.0, show_if=lambda v: not _t(v)), F('g_e', 'e', 0.7, show_if=lambda v: not _t(v)), F('g_inc', 'i', 30.0, '°', show_if=lambda v: not _t(v)),
       F('g_Om', 'Ω', 60.0, '°', show_if=lambda v: not _t(v)), F('g_om', 'ω', 90.0, '°', show_if=lambda v: not _t(v)), F('g_ths', 'θ* at the burn', 150.0, '°', show_if=lambda v: not _t(v)),
       F('g_dv', 'Δv', 1.0, 'km·s⁻¹', show_if=lambda v: not _t(v)), F('g_alpha', 'α', 45.0, '°', show_if=lambda v: not _t(v)), F('g_beta', 'β', 60.0, '°', show_if=lambda v: not _t(v))]

M08 = [BODY('Sun'), D('r1', 'r₁ (departure orbit radius)', BODIES['Earth']['a']), D('r2', 'r₂ (target orbit radius / semi-major axis)', BODIES['Mars']['a']), D('rb', 'r_b for bi-elliptic (0 = none)', 0.0),
       F('e_t', 'Target eccentricity (0 = circular)', 0.0), C('arrive', 'Arrive at target’s', 'perihelion', ['perihelion', 'aphelion'], show_if=lambda v: v['e_t'] > 0)]

M09 = [BODY('Moon'), C('o_mode', 'Initial orbit', 'circular r', ['circular r', 'r_p, r_a']), D('r', 'r', 1838.2, show_if=mode_is('o_mode', 'circular r')),
       D('rp', 'r_p', 7000.0, show_if=mode_is('o_mode', 'r_p, r_a')), D('ra', 'r_a', 20000.0, show_if=mode_is('o_mode', 'r_p, r_a')), F('ths_node', 'θ* at the node', 0.0, '°', show_if=mode_is('o_mode', 'r_p, r_a')),
       F('d_inc', 'Δi', 90.0, '°'), D('r_apo', 'Three-burn apoapsis radius (0 = skip; circular only)', 19000.0)]

M10 = [C('central', 'Central body', 'Sun', BODY_NAMES), C('dep', 'Departure planet', 'Earth', BODY_NAMES), C('arr', 'Arrival planet', 'Pluto', BODY_NAMES),
       D('r_dep', 'Departure planet orbit radius', BODIES['Earth']['a']), D('r_arr', 'Arrival planet orbit radius', BODIES['Pluto']['a']),
       D('r_park', 'Parking-orbit radius (from the planet centre)', 6628.1363), D('r_cap', 'Capture periapsis radius', 12782.0), F('e_cap', 'Capture-orbit eccentricity', 0.0),
       C('tkind', 'Transfer', 'Hohmann', ['Hohmann', 'given states']), V('vdep', 'v̄ at departure (v_r, v_θ)', [0.0, 40.0], 'km·s⁻¹', show_if=mode_is('tkind', 'given states')),
       V('varr', 'v̄ at arrival (v_r, v_θ)', [0.0, 2.0], 'km·s⁻¹', show_if=mode_is('tkind', 'given states'))]

M11 = [C('central', 'Central body', 'Sun', BODY_NAMES), C('planet', 'Flyby planet', 'Venus', BODY_NAMES), D('r_pl', 'Planet orbit radius', BODIES['Venus']['a']),
       C('sub', 'Problem', 'flyby', ['flyby', 'free return']),
       C('vm_mode', 'Incoming velocity given as', 'v, γ', ['v, γ', 'v_r, v_θ'], show_if=mode_is('sub', 'flyby')),
       F('vmag', 'v⁻', 34.26, 'km·s⁻¹', show_if=lambda v: v['sub'] == 'flyby' and v['vm_mode'] == 'v, γ'), F('gamma', 'γ⁻', -26.12, '°', show_if=lambda v: v['sub'] == 'flyby' and v['vm_mode'] == 'v, γ'),
       F('vr', 'v_r⁻', 0.0, 'km·s⁻¹', show_if=lambda v: v['sub'] == 'flyby' and v['vm_mode'] == 'v_r, v_θ'), F('vt', 'v_θ⁻', 30.0, 'km·s⁻¹', show_if=lambda v: v['sub'] == 'flyby' and v['vm_mode'] == 'v_r, v_θ'),
       D('rp', 'Flyby periapsis radius', 4 * BODIES['Venus']['R'], show_if=mode_is('sub', 'flyby')), C('sense', 'Pass', 'lose', ['gain', 'lose', 'ccw', 'cw'], show_if=mode_is('sub', 'flyby')),
       D('r_park', 'Parking-orbit radius', 6558.1363, show_if=mode_is('sub', 'free return')), F('TA', 'Transfer angle TA', 174.0, '°', show_if=mode_is('sub', 'free return'))]

M12 = [BODY('Earth'), C('pos_kind', 'Positions', 'radii', ['radii', 'vectors', 'radec']),
       D('r1', 'r₁', 7972.7, show_if=mode_is('pos_kind', 'radii')), D('r2', 'r₂', 25512.5, show_if=mode_is('pos_kind', 'radii')), F('TA', 'TA', 120.0, '°', show_if=mode_is('pos_kind', 'radii')),
       V('r1v', 'r̄₁', [7972.7, 0, 0], 'km', dist=True, show_if=mode_is('pos_kind', 'vectors')), V('r2v', 'r̄₂', [0, 20000, 10000], 'km', dist=True, show_if=mode_is('pos_kind', 'vectors')),
       F('ra1', 'RA₁', 30.0, '°', show_if=mode_is('pos_kind', 'radec')), F('dec1', 'Dec₁', 10.0, '°', show_if=mode_is('pos_kind', 'radec')), D('d1', 'distance₁', 8000.0, show_if=mode_is('pos_kind', 'radec')),
       F('ra2', 'RA₂', 120.0, '°', show_if=mode_is('pos_kind', 'radec')), F('dec2', 'Dec₂', 20.0, '°', show_if=mode_is('pos_kind', 'radec')), D('d2', 'distance₂', 25000.0, show_if=mode_is('pos_kind', 'radec')),
       C('t_mode', 'Time', 'tof', ['tof', 'minimum energy', 'given p']), F('tof_h', 'TOF', 15.0, 'h', show_if=mode_is('t_mode', 'tof')), D('p', 'p', 31890.0, show_if=mode_is('t_mode', 'given p')),
       C('root', 'p root to report', 'small', ['small', 'large'], show_if=mode_is('t_mode', 'tof')), D('peri_R', 'Check perihelion against a body of radius (0 = off)', 0.0),
       Field('hz_pos', 'Choose ĥ·ẑ > 0', True, 'bool', show_if=lambda v: v['pos_kind'] != 'radii')]

MODULES: dict[str, ModuleSpec] = {
    '1': ModuleSpec('1', '1 · N-body accelerations', M01, run01, body_key=None, blurb='Dominant, direct, indirect and net perturbing accelerations of a target relative to a central body.'),
    '2': ModuleSpec('2', '2 · Two-body constants', M02, run02, body_key=None, blurb='C̄₃, C₄, h, ε, areal velocity, centre-of-mass motion.'),
    '3': ModuleSpec('3', '3 · State ⇄ planar conic', M03, run03, blurb='Position/velocity (or h, ε, r_p/r_a…) to a conic with every standard quantity.'),
    '4': ModuleSpec('4', '4 · Kepler propagation', M04, run04, blurb='Propagate with Kepler’s equation; f and g in both Δθ* and ΔE forms.'),
    '5': ModuleSpec('5', '5 · Hyperbolic flyby geometry', M05, run05, blurb='Asymptotes, aim point, b, δ, time to periapsis, capture Δv.'),
    '6': ModuleSpec('6', '6 · Elements ⇄ 3-D state', M06, run06, blurb='Classical elements to r̄, v̄ in x̂ŷẑ and back, with quadrant checks.'),
    '7': ModuleSpec('7', '7 · Single-impulse maneuver', M07, run07, blurb='All intersections of two coplanar orbits with the minimum |Δv̄|, or a given Δv, α, β.'),
    '8': ModuleSpec('8', '8 · Coplanar transfers / rendezvous', M08, run08, blurb='Hohmann, bi-elliptic, phase angle and synodic period.'),
    '9': ModuleSpec('9', '9 · Plane change', M09, run09, blurb='Single burn vs. three-burn plane change.'),
    '10': ModuleSpec('10', '10 · Patched conics', M10, run10, body_key=None, blurb='Heliocentric transfer with departure and capture hyperbolas.'),
    '11': ModuleSpec('11', '11 · Gravity assist', M11, run11, body_key=None, blurb='Flyby in both senses, new orbit, Δω, Δv̄_eq, free return.'),
    '12': ModuleSpec('12', '12 · Lambert / two-position', M12, run12, blurb='Lambert (general, minimum energy, given p), 2-D or 3-D positions.'),
}
