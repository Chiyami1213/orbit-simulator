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
    for m in ("['solve', 'Solve'", "['explore', 'Sandbox'", "['design', 'Design'"): assert m in app
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


def test_placement_state_is_used_exactly(scene):
    it = next(i for i in SM.catalog() if i['name'] == 'Probe')
    sc = SM.apply_edits(scene, [dict(op='add', item=it, parent='Earth', orbit={}, place=dict(r=[1.0, 2.0, 3.0], v=[0.1, 0.2, 0.3]))], EPH)
    b = next(x for x in sc['bodies'] if x['name'] == 'Probe')
    assert b['r'] == [1.0, 2.0, 3.0] and b['v'] == [0.1, 0.2, 0.3]


def test_texture_modes_for_earth_and_venus(scene):
    earth = next(b for b in scene['bodies'] if b['id'] == 'Earth'); venus = next(b for b in scene['bodies'] if b['id'] == 'Venus')
    assert earth['texmode'].startswith('Day, Clouds') and earth['clouds'] and earth['night'] and venus['texture'] == '2k_venus_atmosphere.jpg'
    sc = SM.apply_edits(scene, [dict(op='set', id='Earth', fields=dict(texmode='Night Lights Only')), dict(op='set', id='Venus', fields=dict(texmode='Surface (Radar Map)'))], EPH)
    e = next(b for b in sc['bodies'] if b['id'] == 'Earth'); v = next(b for b in sc['bodies'] if b['id'] == 'Venus')
    assert e['texture'] == '2k_earth_nightmap.jpg' and e['clouds'] is None and v['texture'] == '2k_venus_surface.jpg'
    out = SS.run(sc, '30 days'); eb = next(b for b in out['bodies'] if b['id'] == 'Earth'); assert eb['texmode'] == 'Night Lights Only' and eb['texture'] == '2k_earth_nightmap.jpg'
    assert 'Earth' in SS.meta()['texmodes'] and len(SS.meta()['texmodes']['Earth']) == 4


def test_texture_download_accepts_only_images(tmp_path, monkeypatch):
    from mathkit import textures as TX
    monkeypatch.setenv('ORBSIM_HOME', str(tmp_path)); monkeypatch.setattr(TX, 'HIRES', {'2k_a.jpg': '8k_a.jpg'})

    class Resp:
        def __init__(self, data): self.data = data; self.pos = 0
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self, n):
            c = self.data[self.pos:self.pos + n]; self.pos += n; return c

    def run(data):
        monkeypatch.setattr(TX.urllib.request, 'urlopen', lambda req, timeout=0: Resp(data))
        TX.PROG.update(state='idle'); TX.download()
        import time
        for _ in range(100):
            if TX.PROG['state'] in ('done', 'error'): break
            time.sleep(0.05)
        return TX.status()
    st = run(b'<html>' + b'x' * 200_000)
    assert TX.PROG['state'] == 'error' and st['count'] == 0
    st = run(b'\xff\xd8\xff\xe0' + b'x' * 200_000); assert TX.PROG['state'] == 'done' and st['count'] == 1 and st['map'] == {'2k_a.jpg': '8k_a.jpg'}
    assert TX.delete_all() == 1 and TX.status()['count'] == 0


def test_sandbox_starts_at_the_current_time():
    import time
    sc = SS.default_scene(EPH); now = time.time() / 86400.0 + 2440587.5
    assert abs(sc['epoch_jd'] - now) < 0.01 and sc['name'] == 'Solar System' and len(sc['bodies']) == 11


def test_space_engine_exposes_everything_the_sandbox_calls():
    space = (ROOT / 'mathkit' / 'ui' / 'web' / 'space.js').read_text(encoding='utf-8')
    for m in ('setRate(', 'getCamera()', 'setCamera(', 'setHires(', 'select(', 'hover(', 'planePoint(', 'setGhost(', 'setPreview(', 'focus(', 'posOf:', 'velOf(', 'pick(', 'onPick(', 'dispose()', 'setJD(', 'play('):
        assert m in space, m
    explore = (ROOT / 'mathkit' / 'ui' / 'web' / 'explore.js').read_text(encoding='utf-8')
    import re
    called = set(re.findall(r'\bS3\.(\w+)\(', explore)) | set(re.findall(r'\bEX\.space\.(\w+)\(', explore))
    missing = [c for c in sorted(called) if c not in ('set',) and not re.search(r'(^|[\s,{])' + c + r'\(|(^|[\s,{])' + c + r':', space)]
    assert not missing, missing
    assert "class: 'cd blank'" in explore and 'cd.empty' not in (ROOT / 'mathkit' / 'ui' / 'web' / 'style.css').read_text(encoding='utf-8')


def test_body_rotation_follows_the_jpl_pck_constants(scene):
    from mathkit import spin as SP
    assert abs(SP.period_hours(SP.spin_for('Earth')) - 23.93447) < 1e-3                       # sidereal day
    assert SP.period_hours(SP.spin_for('Venus')) < 0 and abs(SP.period_hours(SP.spin_for('Venus')) + 5832.44) < 0.1       # retrograde
    assert SP.period_hours(SP.spin_for('Uranus')) < 0 and abs(SP.period_hours(SP.spin_for('Jupiter')) - 9.9249) < 1e-3
    assert abs(SP.period_hours(SP.spin_for('Moon')) - 655.72) < 0.01                          # synchronous with its orbit (27.32 d)
    ra, dec = SP.pole(SP.spin_for('Earth'), 2451545.0 + 36525.0); assert abs(ra + 0.641) < 1e-9 and abs(dec - (90 - 0.557)) < 1e-9        # pole drift per century
    assert abs(SP.prime_meridian(SP.spin_for('Earth'), 2451545.0) - 190.147) < 1e-9 and SP.spin_for('Spacecraft') is None
    earth = next(b for b in scene['bodies'] if b['id'] == 'Earth'); assert abs(24 * 360 / earth['spin']['rate'] - 23.93447) < 1e-3


def test_body_rotation_can_be_edited_and_reaches_the_views(scene):
    sc = SM.apply_edits(scene, [dict(op='set', id='Mars', fields=dict(spin_h=-30.0, pole_dec=10.0, pole_ra=100.0))], EPH)
    m = next(b for b in sc['bodies'] if b['id'] == 'Mars'); assert abs(24 * 360 / m['spin']['rate'] + 30.0) < 1e-9 and m['spin']['dec'] == 10.0 and m['spin']['ra'] == 100.0
    out = SS.run(sc, '30 days'); assert next(b for b in out['bodies'] if b['id'] == 'Mars')['spin']['dec'] == 10.0
    assert 'spinBody' in (ROOT / 'mathkit' / 'ui' / 'web' / 'space.js').read_text(encoding='utf-8')
    from mathkit.mission import service as MS
    assert 'spin_for(n)' in (ROOT / 'mathkit' / 'mission' / 'service.py').read_text(encoding='utf-8')


def test_no_leftover_exam_rounded_code_in_the_front_end():
    web = ROOT / 'mathkit' / 'ui' / 'web'
    for f in ('app.js', 'mission.js', 'explore.js', 'index.html'):
        t = (web / f).read_text(encoding='utf-8'); assert 'Exam rounded' not in t and 'moonR' not in t and "ex ? 'exam value'" not in t, f


def test_shared_main_menu_is_wired():
    web = ROOT / 'mathkit' / 'ui' / 'web'; ex = (web / 'explore.js').read_text(encoding='utf-8'); am = (web / 'appmenu.js').read_text(encoding='utf-8'); icons = (web / 'icons.js').read_text(encoding='utf-8'); html = (web / 'index.html').read_text(encoding='utf-8')
    for name in ('exOpenFile', 'exShare', 'exDebug', 'objectSearch', "e.key === 'Tab'"): assert name in ex, name
    for name in ('function appMenu', 'MODE_TILES', 'appShare', 'appKeys', 'appDebug', 'appPerf', 'menuPinned', "'mouseover'", 'infoModal', 'pickList'): assert name in am, name
    assert 'id="logoBtn"' in html and '/appmenu.js' in html and 'exMenu' not in ex
    for icon in ('menu:', 'newf:', 'openf:', 'guide:', 'savef:', 'exit:', 'news:', 'credits:', 'feedback:', 'perf:', 'debug:', 'keys:'): assert icon in icons, icon
    assert 'perf()' in (web / 'space.js').read_text(encoding='utf-8')



def test_stylesheet_keeps_every_theme_and_sandbox_block():
    css = (ROOT / 'mathkit' / 'ui' / 'web' / 'style.css').read_text(encoding='utf-8')
    for k in ('body[data-palette=dark]', 'body[data-palette=ocean]', 'body[data-palette=forest]', 'body[data-palette=plum]', 'body[data-palette=light]',
              '.xobj{', '.xitem.have', '.objpop', '.xmenu{', '.mtile{', '.logobtn{', '.mrow1{', 'UNIVERSAL PANEL HEADER', '.xside{background:color-mix'):
        assert k in css, k
    js = (ROOT / 'mathkit' / 'ui' / 'web' / 'app.js').read_text(encoding='utf-8'); assert "['dark', 'Graphite'" in js and "THEME_KEYS = ['dark', 'ocean', 'forest', 'plum', 'light']" in js
    from mathkit import theme; assert set(theme.PALETTES) == {'dark', 'ocean', 'forest', 'plum'}


def test_solve_3d_view_spins_the_textured_body():
    from mathkit.view3d.scene import build_figure
    from mathkit.view3d import animate
    src = (ROOT / 'mathkit' / 'view3d' / 'animate.py').read_text(encoding='utf-8'); assert 'function spinAt' in src and 'id="spin"' in src
    from mathkit.ui import api
    r = api.solve(dict(mid='12', vals=None, theme='light', opts=dict(textures=True, frames=60)))
    html = next((s.get('html3d') for s in r['scenes'] if s.get('html3d')), '')
    assert '"spin": {"idx"' in html and '"name": "Earth"' in html


def test_menu_order_and_unique_default_shortcuts():
    import re
    js = (ROOT / 'mathkit' / 'ui' / 'web' / 'app.js').read_text(encoding='utf-8')
    assert "['File', 'Edit', 'View', 'Design', 'Analysis', 'Help']" in js
    keys = re.search(r"const KEYS_DEFAULT = \{(.*?)\};", js).group(1)
    vals = re.findall(r":\s*'([^']+)'", keys)
    assert len(vals) == len(set(vals)) and {'F9', 'F10', 'F12', 'Ctrl+R'} <= set(vals), vals
    for a in re.findall(r"(\w+):", keys): assert re.search(r"\n  %s: \[" % a, js), a            # every binding has a description row
    assert '…' not in re.search(r"function menuDefs\(\).*?\nlet openMenu", js, re.S).group(0)    # no trailing ellipsis on menu items


MINOR = {'a', 'an', 'and', 'as', 'at', 'but', 'by', 'for', 'in', 'of', 'on', 'or', 'the', 'to', 'vs', 'with', 'from', 'into', 'per', 'about', 'than'}


def _apa_ok(s: str) -> bool:
    """APA title case: major words capitalized, minor words (a, of, and, to ...) lower case except first and last. Words with digits, symbols or inner capitals pass."""
    ws = s.split()
    for i, w in enumerate(ws):
        core = w.strip('()[]:,.;')
        if not core.isalpha() or core.upper() == core or any(c.isupper() for c in core[1:]): continue
        if (i in (0, len(ws) - 1) or core.lower() not in MINOR) and core[0].islower(): return False
        if 0 < i < len(ws) - 1 and core.lower() in MINOR and core[0].isupper(): return False
    return True


def test_menu_labels_tour_titles_and_tab_names_use_apa_title_case_and_american_spelling():
    import re
    web = ROOT / 'mathkit' / 'ui' / 'web'
    app = (web / 'app.js').read_text(encoding='utf-8')
    menus = re.search(r"function menuDefs\(\).*?\nlet openMenu", app, re.S).group(0)
    labels = re.findall(r"\blabel: '([^']+)'", menus) + re.findall(r"\bhead: '([^']+)'", menus)
    tour = re.findall(r"title: '([^']+)'", (web / 'tour.js').read_text(encoding='utf-8'))
    bad = [s for s in labels + tour if not _apa_ok(s)]
    assert not bad, bad
    for f in ('app.js', 'appmenu.js', 'tour.js', 'mission.js', 'explore.js', 'index.html'):
        assert not re.search(r'colour|licence|centre', (web / f).read_text(encoding='utf-8'), re.I), f
