"""Explore (sandbox): scene model, N-body simulation, edits, conversion to a mission, API routes and the three-mode wiring."""
import copy
import json
import pathlib
import numpy as np
import pytest
from mathkit.core import timeutil as TU
from mathkit.core.constants import ConstantSet
from mathkit.ephem.approx import AnalyticEphemeris
from mathkit.sandbox import model as SM, sim, service as SS
from mathkit.mission.run import run
from mathkit.ui import api

ROOT = pathlib.Path(__file__).resolve().parents[1]
AU = 149597870.7
EPH = AnalyticEphemeris(); JD0 = TU.calendar_to_jd(2026, 1, 1, 12.0)


@pytest.fixture(scope='module')
def scene():
    return SM.solar_system(EPH, JD0)


def test_solar_system_scene_is_barycentric_and_complete(scene):
    assert [b['id'] for b in scene['bodies']] == ['Sun', 'Mercury', 'Venus', 'Earth', 'Moon', 'Mars', 'Jupiter', 'Saturn', 'Uranus', 'Neptune', 'Pluto']
    mus = np.array([b['mu'] for b in scene['bodies']]); R = np.array([b['r'] for b in scene['bodies']]); V = np.array([b['v'] for b in scene['bodies']])
    assert np.linalg.norm((mus[:, None] * R).sum(0)) / mus.sum() < 1e-6 and np.linalg.norm((mus[:, None] * V).sum(0)) / mus.sum() < 1e-12
    assert SM.get(scene, 'Earth')['texture'] == '2k_earth_daymap.jpg'


def test_nbody_year_matches_the_real_orbits(scene):
    r = sim.simulate(scene, 0, 365.25, accuracy=1e-11)
    assert r['status'] == 'done' and r['energy_drift'] < 1e-9
    E, S, M = (np.array(r['bodies'][k]) for k in ('Earth', 'Sun', 'Moon'))
    d = np.linalg.norm(E - S, axis=1) / AU; assert 0.9832 < d.min() and d.max() < 1.0168
    dm = np.linalg.norm(M - E, axis=1); assert 356000 < dm.min() and dm.max() < 407000
    assert len(r['jd']) > 500                                                                   # the Moon's month is resolved (about 40 samples per orbit)
    # after one year Earth is back near where it started relative to the Sun (a sidereal year is 365.256 d)
    assert abs(d[-1] - d[0]) < 5e-3


def test_time_runs_backwards_and_round_trips(scene):
    fwd = sim.state_at(scene, JD0 + 30); back = sim.state_at(fwd, JD0)
    for a, b in zip(scene['bodies'], back['bodies']): assert np.linalg.norm(np.array(a['r']) - np.array(b['r'])) < 1.0                    # km after +30 d and back
    r = sim.simulate(scene, 15, 15); assert r['jd'][0] < JD0 < r['jd'][-1] and np.all(np.diff(r['jd']) > 0)


def test_test_particles_feel_gravity_but_pull_on_nothing(scene):
    sc = copy.deepcopy(scene); a = SM.add_item(sc, SM.catalog()[ [c['name'] for c in SM.catalog()].index('Spacecraft') ], EPH, parent='Earth')
    assert a['mu'] == 0 and a['gravity'] is False
    el = SM.elements_about(sc, a['id'], 'Earth'); assert el['SMA'] == pytest.approx(3 * 6378.1363, rel=1e-6) and el['ECC'] < 1e-9
    r0 = sim.simulate(scene, 0, 5); r1 = sim.simulate(sc, 0, 5)
    assert np.linalg.norm(np.array(r0['bodies']['Earth'][-1]) - np.array(r1['bodies']['Earth'][-1])) < 1e-3                                                # the spacecraft did not move Earth
    P = np.array(r1['bodies'][a['id']]) - np.array(r1['bodies']['Earth']); assert 18000 < np.linalg.norm(P, axis=1).min() and np.linalg.norm(P, axis=1).max() < 20500


def test_parent_rule_uses_spheres_of_influence(scene):
    assert {b['id']: SM.dominant_parent(scene, b['id']) for b in scene['bodies']} == {'Sun': None, 'Mercury': 'Sun', 'Venus': 'Sun', 'Earth': 'Sun', 'Moon': 'Earth', 'Mars': 'Sun',
                                                                                         'Jupiter': 'Sun', 'Saturn': 'Sun', 'Uranus': 'Sun', 'Neptune': 'Sun', 'Pluto': 'Sun'}


def test_edits(scene):
    sc = SM.apply_edits(scene, [{'op': 'scale_mass', 'id': 'Moon', 'factor': 2}]); assert SM.get(sc, 'Moon')['mu'] == pytest.approx(2 * SM.get(scene, 'Moon')['mu'])
    sc = SM.apply_edits(scene, [{'op': 'whatif', 'name': 'remove_jupiter'}]); assert 'Jupiter' not in [b['id'] for b in sc['bodies']] and len(sc['bodies']) == 10
    sc = SM.apply_edits(scene, [{'op': 'set', 'id': 'Mars', 'fields': {'name': 'Barsoom', 'radius': 4000, 'mu': 0}}]); m = SM.get(sc, 'Mars'); assert m['name'] == 'Barsoom' and m['radius'] == 4000 and m['gravity'] is False
    sc = SM.apply_edits(scene, [{'op': 'orbit', 'id': 'Moon', 'parent': 'Earth', 'elements': dict(SMA=500000, ECC=0.05, INC=10, RAAN=0, AOP=0, TA=90)}]); el = SM.elements_about(sc, 'Moon', 'Earth')
    assert el['SMA'] == pytest.approx(500000, rel=1e-9) and el['ECC'] == pytest.approx(0.05, rel=1e-9) and el['INC'] == pytest.approx(10, abs=1e-9)
    with pytest.raises(KeyError): SM.apply_edits(scene, [{'op': 'remove', 'id': 'Nope'}])
    with pytest.raises(ValueError): SM.apply_edits(scene, [{'op': 'orbit', 'id': 'Moon', 'parent': 'Earth', 'elements': dict(SMA=-5, ECC=0.1, INC=0, RAAN=0, AOP=0, TA=0)}])
    with pytest.raises(ValueError): SM.apply_edits(scene, [{'op': 'add', 'item': {'name': 'Mars', 'kind': 'planet', 'mu': 1, 'radius': 1, 'real': True}}], EPH)         # already in the scene
    assert scene['bodies'][5]['name'] == 'Mars'                                                                                                              # the input scene is never modified


def test_removing_a_perturber_changes_the_trajectory(scene):
    a = sim.simulate(scene, 0, 200)['bodies']['Earth']; b = sim.simulate(SM.apply_edits(scene, [{'op': 'whatif', 'name': 'remove_jupiter'}]), 0, 200)['bodies']['Earth']
    assert 50 < np.linalg.norm(np.array(a[-1]) - np.array(b[-1])) < 5e5


def test_rogue_planet_what_if_adds_a_hyperbolic_intruder(scene):
    item = next(c for c in SM.catalog() if c.get('whatif') == 'rogue'); sc = SM.apply_edits(scene, [{'op': 'add', 'item': item, 'parent': 'Sun'}], EPH)
    rogue = sc['bodies'][-1]; assert rogue['mu'] > 1e8 and np.linalg.norm(rogue['v']) > 20


def test_panel_and_mission_conversion(scene):
    sc = SM.apply_edits(scene, [{'op': 'add', 'item': next(c for c in SM.catalog() if c['name'] == 'Spacecraft'), 'parent': 'Earth'}], EPH); sat = sc['bodies'][-1]['id']
    p = SS.panel(sc, sat); assert p['parent'] == 'Earth' and p['orbit']['period'] == pytest.approx(2 * np.pi * np.sqrt((3 * 6378.1363) ** 3 / ConstantSet().mu('Earth')), rel=1e-6)
    m = SS.to_mission(sc, sat); assert m.propagators[0].central == 'Earth' and 'Moon' in m.propagators[0].gravity and m.spacecraft[0].state_type == 'Cartesian'
    res = run(m, EPH); assert res.final['Sat'].central == 'Earth'
    # the mission's own propagation (ephemeris-driven) and the sandbox's N-body agree closely over one orbit
    r = sim.simulate(sc, 0, res.final['Sat'].jd - res.start['Sat'].jd)
    S, E = np.array(r['bodies'][sat]), np.array(r['bodies']['Earth']); rel = (S - E)[-1]
    assert np.linalg.norm(rel - res.final['Sat'].r) < 25.0                                                                                       # km: two models of the same physics
    with pytest.raises(ValueError): SS.to_mission(sc, 'Sun')


def test_api_routes_round_trip():
    n = api.sandbox_new({'horizon': '30 days'}); assert n['ok'] and len(n['scene']['bodies']) == 11 and n['sim']['samples'] > 50 and n['sim']['energy_drift'] < 1e-9
    sc = n['scene']; jd = sc['epoch_jd'] + 3
    e = api.sandbox_edit({'scene': sc, 'jd': jd, 'edits': [{'op': 'add', 'item': {'name': 'Spacecraft', 'kind': 'spacecraft', 'mu': 0, 'radius': 0.01, 'real': False}, 'parent': 'Earth'}], 'horizon': '30 days'})
    assert e['ok'] and e['scene']['epoch_jd'] == pytest.approx(jd) and e['scene']['bodies'][-1]['id'] == 'Spacecraft'
    assert api.sandbox_panel({'scene': e['scene'], 'id': 'Spacecraft', 'jd': jd + 1})['panel']['parent'] == 'Earth'
    bad = api.sandbox_edit({'scene': sc, 'jd': jd, 'edits': [{'op': 'remove', 'id': 'Nope'}]}); assert not bad['ok'] and 'Nope' in bad['error']
    mm = api.sandbox_to_mission({'scene': e['scene'], 'id': 'Spacecraft'}); assert mm['ok'] and mm['mission']['spacecraft'][0]['state_type'] == 'Cartesian'
    out = api.sandbox_save({'scene': e['scene']}); assert out['ok'] and json.loads(pathlib.Path(out['path']).read_text(encoding='utf-8'))['format'] == 'orbitscene'
    assert api.sandbox_run({'scene': e['scene'], 'horizon': '30 days'})['ok'] and 'catalog' in api.sandbox_meta({}) and 'Scene' in api.sandbox_meta({})['categories']


def test_three_modes_are_wired_in_the_front_end():
    web = ROOT / 'mathkit' / 'ui' / 'web'; app = (web / 'app.js').read_text(encoding='utf-8'); html = (web / 'index.html').read_text(encoding='utf-8'); tour = (web / 'tour.js').read_text(encoding='utf-8')
    assert '/explore.js' in html and 'id="modesw"' in html
    for m in ("['solve', 'Solve'", "['explore', 'Explore'", "['design', 'Design'"): assert m in app
    assert "navGroup('utilities', 'Reference'" in app and "navItem('mission'" not in app                          # the left menu belongs to Solve only
    assert 'nonav' in app and "renderExplore()" in app and 'Three Modes' in tour
    ex = (web / 'explore.js').read_text(encoding='utf-8')
    for part in ('exLib', 'exPanel', 'exBottom', "'Basic'", "'Motion'", "'Orbit'", "'Forces'", "'Actions'", 'sandbox_to_mission', 'exHistory'): assert part in ex


def test_nothing_orbits_a_massless_body(scene):
    sat_item = next(c for c in SM.catalog() if c['name'] == 'Spacecraft'); sc = SM.apply_edits(scene, [{'op': 'add', 'item': sat_item, 'parent': 'Earth'}], EPH); sat = sc['bodies'][-1]['id']
    for it in SM.catalog():                                                                      # clicking any library item with a spacecraft selected must never give NaN states
        if it.get('real') and any(b['name'] == it['name'] for b in sc['bodies']): continue
        out = SM.apply_edits(sc, [{'op': 'add', 'item': it, 'parent': sat}], EPH) if not it.get('whatif') or it['whatif'] == 'rogue' else sc
        assert all(np.all(np.isfinite(b['r'])) and np.all(np.isfinite(b['v'])) for b in out['bodies']), it['name']
    two = SM.apply_edits(sc, [{'op': 'add', 'item': sat_item, 'parent': sat}], EPH); a, b = two['bodies'][-1], SM.get(two, 'Earth')
    assert 1e4 < np.linalg.norm(np.array(a['r']) - np.array(b['r'])) < 3e4                       # it went into orbit about Earth, the spacecraft's own parent
    with pytest.raises(ValueError): SM.apply_edits(sc, [{'op': 'orbit', 'id': 'Moon', 'parent': sat, 'elements': dict(SMA=1000, ECC=0, INC=0, RAAN=0, AOP=0, TA=0)}])


def test_coincident_bodies_give_a_clear_error_not_an_index_error(scene):
    sc = copy.deepcopy(scene); sc['bodies'].append(SM.new_body('Twin', 'small', 1e-3, 1.0, SM.get(sc, 'Earth')['r'], SM.get(sc, 'Earth')['v'], id='Twin'))        # exactly on top of Earth
    try:
        r = sim.simulate(sc, 5, 5); assert r['jd'] and len(r['bodies']['Twin']) == len(r['jd'])                                                            # either a partial run ...
    except ValueError as ex:
        assert 'could not take a single step' in str(ex) or 'invalid' in str(ex)                                                                      # ... or a readable message, never IndexError
    out = api.sandbox_edit({'scene': scene, 'jd': scene['epoch_jd'], 'edits': [{'op': 'add', 'item': {'name': 'X', 'kind': 'small', 'mu': 1e-3, 'radius': 1.0, 'real': False, 'orbit': {'a': 1e-3}}, 'parent': 'Earth', 'orbit': {'a': 1e-3}}], 'horizon': '30 days'})
    assert out['ok'] or 'IndexError' not in out['error']
