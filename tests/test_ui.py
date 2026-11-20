"""Front end and view wiring: modes, menus and shortcuts, text standards, the space engine, the Solar System view, textures, cancel and session."""
import pathlib
import numpy as np
import pytest
from mathkit.core import timeutil as TU
from mathkit.ephem.approx import AnalyticEphemeris
from mathkit.ui import api

ROOT = pathlib.Path(__file__).resolve().parents[1]
EPH = AnalyticEphemeris(); JD0 = TU.calendar_to_jd(2026, 1, 1, 12.0)


def test_two_modes_are_wired_in_the_front_end():
    web = ROOT / 'mathkit' / 'ui' / 'web'; app = (web / 'app.js').read_text(encoding='utf-8'); html = (web / 'index.html').read_text(encoding='utf-8'); tour = (web / 'tour.js').read_text(encoding='utf-8')
    assert 'id="modesw"' in html and '/explore.js' not in html and not (web / 'explore.js').exists()
    for m in ("['solve', 'Solve'", "['design', 'Design'"): assert m in app
    assert "'explore'" not in app and 'Sandbox' not in app and 'sandbox' not in (web / 'appmenu.js').read_text(encoding='utf-8').lower()
    assert "navGroup('utilities', 'Reference'" in app and "navItem('mission'" not in app                          # the left menu belongs to Solve only
    assert 'nonav' in app and 'Two Modes' in tour and "'Solar System'" in (web / 'mission.js').read_text(encoding='utf-8') and 'function solarTab' in (web / 'mission.js').read_text(encoding='utf-8')


def test_solar_system_view_has_every_body_at_true_size_with_full_orbit_rings():
    r = api.ROUTES['solar_view']({'jd0': JD0, 'days': 365, 'center': 'Sun'}); assert r['ok']
    sp = r['space']; names = [b['name'] for b in sp['bodies']]
    assert sp['tracks'] == [] and names[0] == 'Sun' and {'Earth', 'Moon', 'Mars', 'Jupiter', 'Neptune', 'Pluto'} <= set(names)
    by = {b['name']: b for b in sp['bodies']}
    assert by['Earth']['R'] == pytest.approx(6378.1363, rel=1e-3) and by['Moon']['parent'] == 'Earth' and 'ring' not in by['Moon']      # true radius; the Moon is drawn about the Earth
    ring = np.array(by['Neptune']['ring']); assert len(ring) > 300 and np.linalg.norm(ring, axis=1).mean() == pytest.approx(30.07 * 149597870.7, rel=0.02)     # the whole 165-year orbit
    e = np.array(by['Earth']['path']['r'][0]); assert np.linalg.norm(e) == pytest.approx(149597870.7, rel=0.02) and sp['jd1'] - sp['jd0'] == pytest.approx(365)
    g = api.ROUTES['solar_view']({'jd0': JD0, 'days': 30, 'center': 'Earth'})['space']; assert g['center'] == 'Earth' and not any('ring' in b for b in g['bodies'])


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


def test_space_engine_exposes_what_the_views_call():
    space = (ROOT / 'mathkit' / 'ui' / 'web' / 'space.js').read_text(encoding='utf-8')
    for m in ('setRate(', 'getCamera()', 'setCamera(', 'setHires(', 'select(', 'hover(', 'planePoint(', 'setGhost(', 'setPreview(', 'focus(', 'posOf:', 'velOf(', 'pick(', 'onPick(', 'dispose()', 'setJD(', 'play('):
        assert m in space, m
    assert 'cd.empty' not in (ROOT / 'mathkit' / 'ui' / 'web' / 'style.css').read_text(encoding='utf-8')


def test_body_rotation_follows_the_jpl_pck_constants():
    from mathkit import spin as SP
    assert abs(SP.period_hours(SP.spin_for('Earth')) - 23.93447) < 1e-3                       # sidereal day
    assert SP.period_hours(SP.spin_for('Venus')) < 0 and abs(SP.period_hours(SP.spin_for('Venus')) + 5832.44) < 0.1       # retrograde
    assert SP.period_hours(SP.spin_for('Uranus')) < 0 and abs(SP.period_hours(SP.spin_for('Jupiter')) - 9.9249) < 1e-3
    assert abs(SP.period_hours(SP.spin_for('Moon')) - 655.72) < 0.01                          # synchronous with its orbit (27.32 d)
    ra, dec = SP.pole(SP.spin_for('Earth'), 2451545.0 + 36525.0); assert abs(ra + 0.641) < 1e-9 and abs(dec - (90 - 0.557)) < 1e-9        # pole drift per century
    assert abs(SP.prime_meridian(SP.spin_for('Earth'), 2451545.0) - 190.147) < 1e-9 and SP.spin_for('Spacecraft') is None
    assert abs(24 * 360 / SP.spin_for('Earth')['rate'] - 23.93447) < 1e-3


def test_no_leftover_exam_rounded_code_in_the_front_end():
    web = ROOT / 'mathkit' / 'ui' / 'web'
    for f in ('app.js', 'mission.js', 'index.html'):
        t = (web / f).read_text(encoding='utf-8'); assert 'Exam rounded' not in t and 'moonR' not in t and "ex ? 'exam value'" not in t, f


def test_shared_main_menu_is_wired():
    web = ROOT / 'mathkit' / 'ui' / 'web'; am = (web / 'appmenu.js').read_text(encoding='utf-8'); icons = (web / 'icons.js').read_text(encoding='utf-8'); html = (web / 'index.html').read_text(encoding='utf-8')
    for name in ('function appMenu', 'MODE_TILES', 'appShare', 'appKeys', 'appDebug', 'appPerf', 'menuPinned', "'mouseover'", 'infoModal', 'pickList'): assert name in am, name
    assert 'id="logoBtn"' in html and '/appmenu.js' in html
    for icon in ('menu:', 'newf:', 'openf:', 'guide:', 'savef:', 'exit:', 'news:', 'credits:', 'feedback:', 'perf:', 'debug:', 'keys:'): assert icon in icons, icon
    assert 'perf()' in (web / 'space.js').read_text(encoding='utf-8')



def test_stylesheet_keeps_every_theme_and_menu_block():
    css = (ROOT / 'mathkit' / 'ui' / 'web' / 'style.css').read_text(encoding='utf-8')
    for k in ('body[data-palette=dark]', 'body[data-palette=ocean]', 'body[data-palette=forest]', 'body[data-palette=plum]', 'body[data-palette=light]',
              '.xmenu{', '.mtile{', '.logobtn{', '.mrow1{', 'UNIVERSAL PANEL HEADER'):
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
    assert len(vals) == len(set(vals)) and {'F9', 'F10', 'F12', 'Ctrl+R', 'F6'} <= set(vals), vals
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
    for f in ('app.js', 'appmenu.js', 'tour.js', 'mission.js', 'index.html'):
        assert not re.search(r'colour|licence|centre', (web / f).read_text(encoding='utf-8'), re.I), f


def test_quit_confirmation_busy_bar_and_quit_route():
    from mathkit.ui import api, shell
    web = ROOT / 'mathkit' / 'ui' / 'web'
    js = (web / 'app.js').read_text(encoding='utf-8')
    assert "quit: 'Ctrl+Q'" in js and 'confirmQuit: true' in js and 'async function askQuit' in js and 'async function busy(' in js
    assert 'Confirm Before Quitting' in js and "busy('exporting'" in js and "busy('creating backup'" in js
    assert 'id="busybar"' in (web / 'index.html').read_text(encoding='utf-8') and '.busybar.on' in (web / 'style.css').read_text(encoding='utf-8')
    run_py = (ROOT / 'run.py').read_text(encoding='utf-8')
    assert 'events.closing' in run_py and 'os._exit(0)' in run_py                           # quitting must end the process, not leave a hidden python.exe behind
    assert shell.WINDOW is None and api.ROUTES['quit']({}) == dict(ok=True, mode='browser')       # no window in the tests: the page closes itself, nothing is destroyed


def test_cancel_session_designs_and_latex_symbols(tmp_path, monkeypatch):
    monkeypatch.setenv('ORBSIM_HOME', str(tmp_path))
    from mathkit.ui import api, shell
    # Esc cancel: a cancel request makes the next progress call stop the solve; the wrapper turns that into a dropped answer
    api.CANCEL.set()
    try:
        r = api.ROUTES['cancel']({}); assert r['ok']
        try: api._prog('drawing', 0.5); raise AssertionError('progress did not stop')
        except api.Cancelled: pass
    finally: api.CANCEL.clear()
    def boom(p): raise api.Cancelled()
    out = api._cancellable(boom)({}); assert out['cancelled'] and not api.CANCEL.is_set()
    # last session: saved to the backups folder and read back
    assert api.ROUTES['session_load']({})['ok'] is False
    assert api.ROUTES['session_save']({'session': {'page': '12', 'canon': {'12': {'r1': 1.5}}}})['ok']
    assert api.ROUTES['session_load']({})['session']['canon']['12']['r1'] == 1.5
    # designs: mission files go to designs/, other exports to exports/
    assert 'designs' in shell.paths()
    web = ROOT / 'mathkit' / 'ui' / 'web'
    js = (web / 'app.js').read_text(encoding='utf-8')
    assert "ico('close')" in js and "'Restore Last Session'" in js and 'function cancelSolve' in js
    assert 'katex.renderToString' in js and '/vendor/katex/katex.min.js' in (web / 'index.html').read_text(encoding='utf-8')
    assert "'\\\\mathrm{'" in js                                                        # a LaTeX backslash must survive as two characters in the JS source



def test_mission_tracks_are_laid_over_the_solar_system_about_the_view_center():
    m = api.ROUTES['mission_starter']({'name': 'LEO to GEO Hohmann transfer'})['mission']
    sp = api.ROUTES['mission_run']({'mission': m, 'theme': 'dark', 'opts': {'skip3d': True}})['space']; assert sp['center'] == 'Earth' and sp['tracks']
    span = sp['jd1'] - sp['jd0'] + 1
    sun = api.ROUTES['solar_view']({'jd0': sp['jd0'], 'days': span, 'center': 'Sun', 'tracks': sp['tracks'], 'track_center': 'Earth', 'events': sp['events']})['space']
    r_sun = np.array(sun['tracks'][0]['r']); r_earth = np.array(sp['tracks'][0]['r'])
    assert np.linalg.norm(r_sun[0]) == pytest.approx(149597870.7, rel=0.03)                                  # the spacecraft sits at about 1 AU from the Sun, where the Earth is
    assert np.linalg.norm(r_sun[0] - r_earth[0]) == pytest.approx(np.linalg.norm(r_sun[0]), rel=0.03)         # shifted by the Earth's position, not left about the Earth
    same = api.ROUTES['solar_view']({'jd0': sp['jd0'], 'days': span, 'center': 'Earth', 'tracks': sp['tracks'], 'track_center': 'Earth'})['space']
    assert np.allclose(same['tracks'][0]['r'], sp['tracks'][0]['r'])                                         # already about the view center: unchanged
    assert 'Show Last Mission Run' in (ROOT / 'mathkit' / 'ui' / 'web' / 'mission.js').read_text(encoding='utf-8')


def test_design_header_stays_on_one_row_space_view_has_full_window_and_menu_has_quit():
    web = ROOT / 'mathkit' / 'ui' / 'web'; css = (web / 'style.css').read_text(encoding='utf-8'); mis = (web / 'mission.js').read_text(encoding='utf-8'); am = (web / 'appmenu.js').read_text(encoding='utf-8')
    assert '.mrow1{flex-wrap:nowrap}' in css and '.spacecard.full{position:fixed;inset:0' in css                # no second header row holding the Run button; the full-window card covers the page
    assert 'Leave Full Window' in mis and "e.key === 'Tab'" in mis and "item('exit', 'Quit'" in am


def test_earth_and_venus_have_a_cloud_layer_toggle_in_the_space_view():
    r = api.ROUTES['solar_view']({'jd0': JD0, 'days': 30, 'center': 'Sun'})['space']; by = {b['name']: b for b in r['bodies']}
    assert by['Earth']['clouds'] == '2k_earth_clouds.jpg' and by['Earth']['cloud_kind'] == 'alpha' and by['Mars']['clouds'] is None
    assert by['Mars']['dust'] is True and by['Earth']['dust'] is False and 'function dustTexture' in (ROOT / 'mathkit' / 'ui' / 'web' / 'space.js').read_text(encoding='utf-8') and "chk('dust', 'Dust Storms'" in (ROOT / 'mathkit' / 'ui' / 'web' / 'mission.js').read_text(encoding='utf-8')
    assert by['Venus']['clouds'] == '2k_venus_atmosphere.jpg' and by['Venus']['cloud_kind'] == 'opaque' and by['Venus']['texture'] == '2k_venus_surface.jpg'
    web = ROOT / 'mathkit' / 'ui' / 'web'; assert "chk('clouds', 'Clouds'" in (web / 'mission.js').read_text(encoding='utf-8') and 'mesh.userData.cloud = cl' in (web / 'space.js').read_text(encoding='utf-8')


def test_preferences_have_search_and_layer_defaults():
    js = (ROOT / 'mathkit' / 'ui' / 'web' / 'app.js').read_text(encoding='utf-8')
    assert "id: 'setsearch'" in js and 'Search Preferences' in js and 'const SEARCHED' in js and 'Mars Dust Storms' in js and 'Clouds on Earth and Venus' in js
    assert 'input[type=search].setsearch' in (ROOT / 'mathkit' / 'ui' / 'web' / 'style.css').read_text(encoding='utf-8')
