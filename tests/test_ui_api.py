"""The desktop UI's backend: JSON API for every preset, the HTTP server, exports and utilities."""
import json
import urllib.request
import pytest
from mathkit.ui import api, server
from mathkit.registry import MODULES
from mathkit.presets.hw_problems import PRESETS


def test_meta_describes_every_module():
    m = api.meta(); assert [x['id'] for x in m['modules']] == list(MODULES)
    for mod in m['modules']:
        assert mod['short'] and mod['fields']; json.dumps(mod)           # JSON-serialisable
        assert all(f['kind'] in ('float', 'int', 'choice', 'text', 'bool', 'vec') for f in mod['fields'])


@pytest.mark.parametrize('mid', list(MODULES))
def test_default_inputs_solve_and_visibility(mid):
    vis = api.visible(dict(mid=mid, vals={}))['visible']; assert vis
    r = api.solve(dict(mid=mid, vals={}, theme='dark', name='Test User', label='T'))
    assert 'error' not in r, r.get('error'); assert r['scenes'] and r['groups']


CASES = [(mid, i, p.label) for mid, lst in PRESETS.items() for i, p in enumerate(lst)]


@pytest.mark.parametrize('mid,i,label', CASES, ids=[f'{m}:{l.split(" — ")[0]}' for m, i, l in CASES])
@pytest.mark.parametrize('theme', ['dark', 'light'])
def test_preset_through_api(mid, i, label, theme):
    p = PRESETS[mid][i]
    r = api.solve(dict(mid=mid, vals=p.vals, consts=dict(mode=p.consts, moon_R=p.moon_R), theme=theme, name='Test User', label=label.split(' — ')[0]))
    assert 'error' not in r, r.get('error')
    for sc in r['scenes']:
        assert sc['svg'].startswith('<svg') and 'id="plot"' in sc['html3d'] and sc['overlaps'] == 0, f'{label} [{sc["name"]}]'
    assert r['cards']; json.dumps(r)


def test_bad_input_is_reported_not_raised():
    r = api.solve(dict(mid='3', vals=dict(mode='polar', r=-5.0, vr=0.0, vt=0.0)))
    assert 'error' in r or r['warnings'] is not None            # either a clean message or a result with warnings, never an exception


def test_run_tests_all_pass():
    t = api.run_tests(); assert t['total'] == t['passed'] == 169


def test_jd_tools():
    assert api.jd(dict(type='cal2jd', Y=2000, M=1, D=1, h=12, mi=0, s=0))['jd'] == 2451545.0
    assert api.jd(dict(type='jd2cal', jd=2451545.0))['text'].startswith('2000-01-01  12:00')
    assert '13:30 UT' in api.jd(dict(type='et2ut', Y=2024, M=10, D=4, h=9, mi=30))['text']


@pytest.fixture(scope='module')
def live():
    httpd, url = server.start(0); yield url; httpd.shutdown()


def _post(url, name, payload):
    req = urllib.request.Request(url + 'api/' + name, json.dumps(payload).encode(), {'Content-Type': 'application/json'})
    return json.load(urllib.request.urlopen(req))


def test_server_serves_ui_and_api(live):
    html = urllib.request.urlopen(live).read().decode(); assert 'OrbSim' in html
    assert urllib.request.urlopen(live + 'app.js').status == 200 and urllib.request.urlopen(live + 'style.css').status == 200
    assert len(urllib.request.urlopen(live + 'static/plotly.min.js').read()) > 1_000_000
    assert _post(live, 'meta', {})['version'] == api.VERSION
    r = _post(live, 'solve', dict(mid='12', vals={}, theme='dark', name='Ethan Lee', label='HW10 P3'))
    assert r['cards'][0]['pill'] and r['scenes'][0]['svg'].startswith('<svg')


def test_server_does_not_leak_files(live):
    for bad in ('../run.py', '..%2frun.py', '%2e%2e/run.py'):
        try: code = urllib.request.urlopen(live + bad).status
        except urllib.error.HTTPError as e: code = e.code
        assert code == 404, bad


def test_exports(live):
    _post(live, 'solve', dict(mid='3', vals={}, theme='dark', name='Ethan Lee', label='HW3 P3'))
    png = urllib.request.urlopen(live + 'export/0.png?theme=light').read(); assert png[:8] == b'\x89PNG\r\n\x1a\n'
    pdf = urllib.request.urlopen(live + 'export/0.pdf?theme=light').read(); assert pdf[:4] == b'%PDF'
    assert b'plotly' in urllib.request.urlopen(live + 'export/0.html').read()
