"""Explore (sandbox) scene model: bodies with mass and state, a catalogue to add from, and the editing operations the side panel performs.

Frame: ICRF axes, origin at the system barycentre of the scene's massive bodies at the scene epoch (fixed in space). Units: km, km/s, s, km^3/s^2 (mu = G m).
A body with mu = 0 is a test particle (a spacecraft): it feels gravity and attracts nothing.
"""
from __future__ import annotations
import copy
import numpy as np
from ..core.constants import BODIES, ConstantSet, D2R
from ..core.elements import rv_from_elements, elements_from_rv
from ..core import timeutil as TU
from ..mission.model import Spacecraft  # noqa: F401  (re-exported for callers that build missions)

G_KM = 6.67430e-20                                                    # km^3 kg^-1 s^-2
KIND_COLOR = {'star': '#ffd27a', 'planet': '#6b9fd8', 'moon': '#bdbdbd', 'small': '#a89f91', 'spacecraft': '#ff6b4a', 'custom': '#9b8cf2'}
TEXTURES = {'Sun': '2k_sun.jpg', 'Moon': '2k_moon.jpg', 'Mercury': '2k_mercury.jpg', 'Venus': '2k_venus_surface.jpg', 'Earth': '2k_earth_daymap.jpg', 'Mars': '2k_mars.jpg',
            'Jupiter': '2k_jupiter.jpg', 'Saturn': '2k_saturn.jpg', 'Uranus': '2k_uranus.jpg', 'Neptune': '2k_neptune.jpg', 'Ceres': '2k_ceres_fictional.jpg'}
REAL = {'Sun': 'star', 'Mercury': 'planet', 'Venus': 'planet', 'Earth': 'planet', 'Moon': 'moon', 'Mars': 'planet', 'Jupiter': 'planet', 'Saturn': 'planet', 'Uranus': 'planet',
        'Neptune': 'planet', 'Pluto': 'planet'}
SMALL = {'Ceres': dict(mu=62.6284, R=469.7, a=413.7e6, e=0.0785, inc=10.6), 'Vesta': dict(mu=17.288, R=262.7, a=353.3e6, e=0.0887, inc=7.1)}
BODY_COLOR = {'Sun': '#ffd27a', 'Mercury': '#a79d93', 'Venus': '#e0c28b', 'Earth': '#4c8df6', 'Moon': '#bdbdbd', 'Mars': '#d1603d', 'Jupiter': '#d8b18c', 'Saturn': '#e3d3a2',
              'Uranus': '#9fd6e0', 'Neptune': '#5a7fe0', 'Pluto': '#c9b9a8', 'Ceres': '#9a948a', 'Vesta': '#b3a28c'}


def new_body(name: str, kind: str, mu: float, radius: float, r, v, **kw) -> dict:
    return dict(id=kw.pop('id', name), name=name, kind=kind, mu=float(mu), radius=float(radius), color=kw.pop('color', BODY_COLOR.get(name, KIND_COLOR.get(kind, '#8aa0c8'))),
                texture=kw.pop('texture', TEXTURES.get(name)), r=[float(x) for x in r], v=[float(x) for x in v], gravity=kw.pop('gravity', mu > 0), visible=True, **kw)


def unique_id(scene: dict, base: str) -> str:
    ids = {b['id'] for b in scene['bodies']}; n = 1; cand = base
    while cand in ids: n += 1; cand = f'{base} {n}'
    return cand


def solar_system(eph, jd_utc: float, consts: ConstantSet | None = None, names=None) -> dict:
    """The real Solar System at an epoch from the active ephemeris (barycentric, ICRF)."""
    consts = consts or ConstantSet(); jd_tdb = TU.utc_to_tdb(jd_utc); bodies = []
    for n in (names or list(REAL)):
        if n not in getattr(eph, 'bodies', ()): continue
        r, v = eph.state(n, jd_tdb, 'SSB'); b = consts.body(n)
        bodies.append(new_body(n, REAL[n], b['mu'], b['R'], r, v))
    sc = dict(name='Solar System', epoch_jd=float(jd_utc), bodies=bodies, source=getattr(eph, 'name', 'ephemeris'))
    recenter(sc); return sc


def recenter(scene: dict) -> dict:
    """Move the origin to the barycentre of the massive bodies and remove the drift (so the Sun does not wander off while the planets orbit)."""
    mus = np.array([b['mu'] for b in scene['bodies']])
    if mus.sum() <= 0: return scene
    R = np.array([b['r'] for b in scene['bodies']]); V = np.array([b['v'] for b in scene['bodies']])
    c = (mus[:, None] * R).sum(0) / mus.sum(); w = (mus[:, None] * V).sum(0) / mus.sum()
    for b, r, v in zip(scene['bodies'], R - c, V - w): b['r'] = r.tolist(); b['v'] = v.tolist()
    return scene


def get(scene: dict, bid: str) -> dict:
    for b in scene['bodies']:
        if b['id'] == bid: return b
    raise KeyError(f'no body "{bid}" in the scene')


def orbit_state(parent: dict, mu_child: float, a: float, e: float, inc: float, raan: float, aop: float, ta: float):
    """Absolute (r, v) of a child on the given orbit about ``parent`` (km, deg)."""
    mu = parent['mu'] + max(mu_child, 0.0)
    if e < 1 and a <= 0: raise ValueError('an elliptical orbit needs SMA > 0')
    if e > 1 and a >= 0: raise ValueError('a hyperbolic orbit needs SMA < 0')
    r, v, _ = rv_from_elements(mu, a, e, inc, raan, aop, ta)
    return np.array(parent['r']) + r, np.array(parent['v']) + v


def elements_about(scene: dict, bid: str, parent_id: str) -> dict:
    b, p = get(scene, bid), get(scene, parent_id); mu = p['mu'] + max(b['mu'], 0.0)
    r = np.array(b['r']) - np.array(p['r']); v = np.array(b['v']) - np.array(p['v']); el = elements_from_rv(mu, r, v)
    out = dict(SMA=el['a'], ECC=el['e'], INC=el['inc'], RAAN=el['Om'], AOP=el['om'], TA=el['ths'] % 360, dist=float(np.linalg.norm(r)), speed=float(np.linalg.norm(v)))
    out['period'] = float(2 * np.pi * np.sqrt(el['a'] ** 3 / mu)) if el['e'] < 1 else float('nan')
    return out


def dominant_parent(scene: dict, bid: str) -> str | None:
    """The body this one orbits: the heaviest body is the root; any other body orbits the smallest-distance candidate whose sphere of influence
    (|r_j - r_root| (mu_j / mu_root)^(2/5)) contains it and which is heavier than it, else the root. Test particles follow the same rule."""
    bodies = [b for b in scene['bodies'] if b['mu'] > 0 and b.get('gravity', True)]
    if not bodies: return None
    root = max(bodies, key=lambda x: x['mu']); b = get(scene, bid)
    if b['id'] == root['id']: return None
    rr = np.array(root['r']); pos = np.array(b['r']); best, bd = root['id'], np.inf
    for o in bodies:
        if o['id'] in (bid, root['id']) or o['mu'] <= b['mu']: continue
        soi = np.linalg.norm(np.array(o['r']) - rr) * (o['mu'] / root['mu']) ** 0.4; d = np.linalg.norm(np.array(o['r']) - pos)
        if d < soi and d < bd: best, bd = o['id'], d
    return best


# ---------------------------------------------------------------------------------------------------- catalogue
def catalog(consts: ConstantSet | None = None) -> list[dict]:
    consts = consts or ConstantSet(); items = []
    for n, k in REAL.items():
        b = consts.body(n); items.append(dict(cat='Solar System' if k in ('star',) else ('Moons' if k == 'moon' else 'Planets'), name=n, kind=k, mu=b['mu'], radius=b['R'], real=True, color=BODY_COLOR.get(n), texture=TEXTURES.get(n)))
    for n, d in SMALL.items(): items.append(dict(cat='Small Bodies', name=n, kind='small', mu=d['mu'], radius=d['R'], real=False, color=BODY_COLOR.get(n), texture=TEXTURES.get(n), orbit=dict(a=d['a'], e=d['e'], inc=d['inc'])))
    items += [dict(cat='Small Bodies', name='Asteroid', kind='small', mu=1e-3, radius=5.0, real=False, color='#a89f91', texture=None),
              dict(cat='Small Bodies', name='Comet', kind='small', mu=1e-6, radius=2.0, real=False, color='#cfe8ff', texture=None, orbit=dict(a=3.0e9, e=0.9, inc=20.0)),
              dict(cat='Spacecraft', name='Spacecraft', kind='spacecraft', mu=0.0, radius=0.01, real=False, color='#ff6b4a', texture=None),
              dict(cat='Spacecraft', name='Probe', kind='spacecraft', mu=0.0, radius=0.01, real=False, color='#3ecf8e', texture=None),
              dict(cat='Custom', name='Earth-like Planet', kind='custom', mu=consts.mu('Earth'), radius=consts.R('Earth'), real=False, color='#6bd0a8', texture=None),
              dict(cat='Custom', name='Gas Giant', kind='custom', mu=consts.mu('Jupiter'), radius=consts.R('Jupiter'), real=False, color='#d8a56b', texture=None),
              dict(cat='Custom', name='Sun-like Star', kind='star', mu=consts.mu('Sun'), radius=consts.R('Sun'), real=False, color='#ffd27a', texture=None),
              dict(cat='Custom', name='Black Hole (10 solar masses)', kind='star', mu=10 * consts.mu('Sun'), radius=30.0, real=False, color='#111111', texture=None),
              dict(cat='What If', name='Rogue Planet Flyby', kind='custom', mu=consts.mu('Jupiter'), radius=consts.R('Jupiter'), real=False, color='#b37bf0', texture=None, whatif='rogue'),
              dict(cat='What If', name='Double the Moon', kind='moon', mu=0, radius=0, real=False, whatif='double_moon'),
              dict(cat='What If', name='Remove Jupiter', kind='planet', mu=0, radius=0, real=False, whatif='remove_jupiter'),
              dict(cat='What If', name='Remove the Moon', kind='moon', mu=0, radius=0, real=False, whatif='remove_moon')]
    return items


CATEGORIES = ['All', 'Solar System', 'Planets', 'Moons', 'Small Bodies', 'Spacecraft', 'Custom', 'What If']


def add_item(scene: dict, item: dict, eph=None, consts: ConstantSet | None = None, parent: str | None = None, orbit: dict | None = None) -> dict:
    """Add a catalogue item. Real bodies come from the ephemeris at the scene epoch; others are put on an orbit about ``parent`` (default: the Sun / heaviest body)."""
    consts = consts or ConstantSet(); name = item['name']
    if item.get('real') and eph is not None and name in getattr(eph, 'bodies', ()):
        if any(b['name'] == name for b in scene['bodies']): raise ValueError(f'{name} is already in the scene')
        r, v = eph.state(name, TU.utc_to_tdb(scene['epoch_jd']), 'SSB'); cur = dict(scene); bd = new_body(name, item['kind'], item['mu'], item['radius'], r, v)
        # express relative to the scene's own frame: the scene origin was the barycentre of its bodies; add relative to the Sun's position in the scene
        sun_s = next((b for b in scene['bodies'] if b['name'] == 'Sun'), None)
        if sun_s is not None:
            rs, vs = eph.state('Sun', TU.utc_to_tdb(scene['epoch_jd']), 'SSB'); bd['r'] = (np.array(sun_s['r']) + (np.array(r) - rs)).tolist(); bd['v'] = (np.array(sun_s['v']) + (np.array(v) - vs)).tolist()
        scene['bodies'].append(bd); return bd
    parent_id = parent or next((b['id'] for b in sorted(scene['bodies'], key=lambda x: -x['mu'])), None)
    if parent_id is None:
        bd = new_body(name, item['kind'], item['mu'], item['radius'], [0, 0, 0], [0, 0, 0], id=unique_id(scene, name)); scene['bodies'].append(bd); return bd
    par = get(scene, parent_id); o = dict(item.get('orbit') or {}); o.update(orbit or {})
    if item.get('whatif') == 'rogue':                                                              # an unbound Jupiter-mass planet crossing the inner system at 25 km/s
        d = 3.0e8; p0 = np.array(par['r']) + np.array([d, -d * 0.55, 0.0]); aim = np.array(par['r']) - p0; v = 25.0 * aim / np.linalg.norm(aim)
        bd = new_body(name, item['kind'], item['mu'], item['radius'], p0, np.array(par['v']) + v, id=unique_id(scene, name), color=item.get('color'))
    else:
        a = o.get('a') or (1.5e8 if par['kind'] == 'star' else max(3.0 * par['radius'], par['radius'] + 400.0))
        r, v = orbit_state(par, item['mu'], a, o.get('e', 0.0), o.get('inc', 0.0), o.get('raan', 0.0), o.get('aop', 0.0), o.get('ta', 0.0))
        bd = new_body(name, item['kind'], item['mu'], item['radius'], r, v, id=unique_id(scene, name), color=item.get('color'), texture=item.get('texture'))
    scene['bodies'].append(bd); return bd


def apply_edits(scene: dict, edits: list[dict], eph=None, consts: ConstantSet | None = None) -> dict:
    """Apply a list of edit operations and return the (re-centred) scene. Unknown ids raise KeyError, bad orbits ValueError."""
    sc = copy.deepcopy(scene); consts = consts or ConstantSet()
    for e in edits:
        op = e['op']
        if op == 'set':
            b = get(sc, e['id'])
            for k, v in e['fields'].items():
                if k in ('mu', 'radius'): b[k] = max(float(v), 0.0)
                elif k in ('r', 'v'): b[k] = [float(x) for x in v]
                elif k in ('name', 'color', 'texture', 'gravity', 'visible', 'kind'): b[k] = v
            if 'mu' in e['fields']: b['gravity'] = b['mu'] > 0 if 'gravity' not in e['fields'] else b['gravity']
        elif op == 'scale_mass': get(sc, e['id'])['mu'] *= float(e['factor'])
        elif op == 'remove':
            get(sc, e['id']); sc['bodies'] = [b for b in sc['bodies'] if b['id'] != e['id']]
        elif op == 'orbit':
            b, p = get(sc, e['id']), get(sc, e['parent']); el = e['elements']
            r, v = orbit_state(p, b['mu'], float(el['SMA']), float(el['ECC']), float(el['INC']), float(el['RAAN']), float(el['AOP']), float(el['TA'])); b['r'], b['v'] = r.tolist(), v.tolist()
        elif op == 'add': add_item(sc, e['item'], eph, consts, e.get('parent'), e.get('orbit'));
        elif op == 'whatif':
            w = e['name']
            if w == 'double_moon': get(sc, 'Moon')['mu'] *= 2
            elif w == 'remove_moon': sc['bodies'] = [b for b in sc['bodies'] if b['id'] != 'Moon']
            elif w == 'remove_jupiter': sc['bodies'] = [b for b in sc['bodies'] if b['id'] != 'Jupiter']
            else: raise ValueError(f'unknown what-if {w}')
        else: raise ValueError(f'unknown edit {op}')
    return sc
