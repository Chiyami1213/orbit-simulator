"""Explore workspace back end: scenes, edits, simulation and conversion of a scene into a Mission."""
from __future__ import annotations
import numpy as np
from ..core.constants import ConstantSet, BODIES
from ..core import timeutil as TU
from ..core.elements import elements_from_rv
from ..mission.model import Mission, Spacecraft, Propagator, OrbitView, Command, CoordSys, ReportFile
from ..mission.params import format_epoch
from . import model as SM, sim

HORIZONS = {'30 days': (15, 15), '1 year': (183, 183), '5 years': (913, 913), '25 years': (4566, 4566), '100 years': (18262, 18262)}


def models() -> dict:
    from ..view3d.models import spacecraft_mesh
    return {k: spacecraft_mesh(k) for k in ('comsat', 'probe')}


def shape_of(name: str, kind: str) -> str:
    n = name.lower()
    if kind == 'spacecraft': return 'probe' if 'probe' in n else 'comsat'
    if 'black hole' in n: return 'blackhole'
    if 'comet' in n: return 'comet'
    if kind == 'small' and 'ceres' not in n: return 'asteroid'
    if kind == 'star' and name != 'Sun': return 'star'
    if name == 'Saturn': return 'ring'
    return 'sphere'


def meta(consts: ConstantSet | None = None) -> dict:
    from .. import sky as SK
    cat = SM.catalog(consts)
    for c in cat: c['shape'] = shape_of(c['name'], c['kind'])
    markers = [dict(name='Galactic Center', ra=SK.GALACTIC_CENTER[0], dec=SK.GALACTIC_CENTER[1]), dict(name='North Galactic Pole', ra=SK.NORTH_GALACTIC_POLE[0], dec=SK.NORTH_GALACTIC_POLE[1])] + [dict(name=k, ra=r_, dec=d_) for k, (r_, d_) in SK.STARS.items()]
    return dict(catalog=cat, categories=SM.CATEGORIES, horizons=list(HORIZONS), kinds=['star', 'planet', 'moon', 'small', 'spacecraft', 'custom'], models=models(), markers=markers)


def default_scene(eph, jd_utc: float | None = None) -> dict:
    jd = jd_utc if jd_utc is not None else TU.calendar_to_jd(2026, 1, 1, 12.0)
    return SM.solar_system(eph, jd)


def run(scene: dict, horizon: str | tuple = '1 year', accuracy: float = 1e-11) -> dict:
    back, fwd = HORIZONS[horizon] if isinstance(horizon, str) else horizon
    cap = max(5.0, sim.fastest_period_days(scene) * 80.0); limited = None                      # a spacecraft in low orbit would need millions of steps over years
    if fwd > cap or back > cap: back, fwd = min(back, cap), min(fwd, cap); limited = round(cap, 1)
    r = sim.simulate(scene, back, fwd, accuracy)
    bodies = []
    for b in scene['bodies']:
        d = dict(id=b['id'], name=b['name'], kind=b['kind'], shape=shape_of(b['name'], b['kind']), mu=b['mu'], radius=b['radius'], color=b['color'], texture=b.get('texture'), gravity=b.get('gravity', True), visible=b.get('visible', True),
                 parent=SM.dominant_parent(scene, b['id']), path=dict(jd=r['jd'], r=r['bodies'][b['id']]))
        bodies.append(d)
    return dict(bodies=bodies, jd0=r['jd'][0], jd1=r['jd'][-1], epoch_jd=scene['epoch_jd'], energy_drift=r['energy_drift'], steps=r['steps'], status=r['status'], samples=len(r['jd']), limited_days=limited)


def edit(scene: dict, jd: float, edits: list[dict], eph=None, consts: ConstantSet | None = None) -> dict:
    """Advance the scene to the current simulation time, apply the edits there, and return the new scene (epoch = jd)."""
    cur = sim.state_at(scene, jd) if abs(jd - scene['epoch_jd']) > 1e-9 else scene
    return SM.apply_edits(cur, edits, eph, consts)


def panel(scene: dict, bid: str) -> dict:
    """Everything the object panel shows for one body: basic data, motion, orbit about its dominant parent."""
    b = SM.get(scene, bid); par = SM.dominant_parent(scene, bid); out = dict(id=bid, name=b['name'], kind=b['kind'], mu=b['mu'], radius=b['radius'], r=b['r'], v=b['v'],
                                                                           speed=float(np.linalg.norm(b['v'])), parent=par)
    if b['mu'] > 0 and b['radius'] > 0: out['density_gcc'] = float(b['mu'] / SM.G_KM / (4 / 3 * np.pi * (b['radius'] * 1e3) ** 3) / 1e3)         # kg m^-3 -> g cm^-3
    out['mass_kg'] = float(b['mu'] / SM.G_KM) if b['mu'] > 0 else 0.0
    if par:
        try: out['orbit'] = SM.elements_about(scene, bid, par)
        except Exception: out['orbit'] = None
    return out


def to_mission(scene: dict, bid: str, name: str | None = None, consts: ConstantSet | None = None) -> Mission:
    """A mission for one body (normally a spacecraft): central body = the strongest attractor, point masses = every massive body, state about that body (MJ2000Eq)."""
    consts = consts or ConstantSet(); b = SM.get(scene, bid); par_id = SM.dominant_parent(scene, bid)
    if par_id is None: raise ValueError('this body has no attracting body to build a mission around')
    par = SM.get(scene, par_id); central = par['name']
    if central not in BODIES: raise ValueError(f'{central} is a custom body; missions can only be centred on a Solar System body')
    grav = [central] + [o['name'] for o in scene['bodies'] if o['name'] in BODIES and o['name'] != central and o['mu'] > 0 and o['gravity']]
    r = np.array(b['r']) - np.array(par['r']); v = np.array(b['v']) - np.array(par['v'])
    cs = 'EarthMJ2000Eq' if central == 'Earth' else f'{"Luna" if central == "Moon" else central}MJ2000Eq'
    m = Mission(name=name or f'{b["name"]} from the Explore scene', constants=consts.mode)
    if cs != 'EarthMJ2000Eq': m.coords.append(CoordSys(cs, central, 'MJ2000Eq'))
    m.spacecraft = [Spacecraft('Sat', 'UTCGregorian', format_epoch(scene['epoch_jd'], 'UTCGregorian'), cs, 'Cartesian', dict(X=r[0], Y=r[1], Z=r[2], VX=v[0], VY=v[1], VZ=v[2]), color=b.get('color', '#ff6b4a'))]
    m.propagators = [Propagator('Prop', central, 'selected_nbody', grav, 'RungeKutta89')]
    m.views = [OrbitView('View', ['Sat'] + grav[:4], cs)]
    el = elements_from_rv(consts.mu(central), r, v)
    stop = f'Sat.ElapsedSecs = {float(el["P"]) if el["e"] < 1 else 86400.0 * 30!r}'
    m.commands = [Command('Propagate', items=[['Prop', ['Sat']]], stops=[stop])]
    m.notes = [f'built from the Explore scene at {format_epoch(scene["epoch_jd"], "UTCGregorian")}: state of {b["name"]} about {central}']
    return m
