"""Conventions, time systems, integrators, events, dynamics models, the mission model, GMAT script export / import and the licence files."""
import json
import os
import pathlib
import numpy as np
import pytest
from mathkit import conventions as CV
from mathkit.core import timeutil as TU
from mathkit.core.constants import ConstantSet, BODIES
from mathkit.core.elements import rv_from_elements, elements_from_rv
from mathkit.core.maneuvers import apply_dv_vnc
from mathkit.dyn.integrators import propagate, Event, METHODS
from mathkit.dyn.models import two_body_rhs, kepler_propagate, CR3BP, soi_radius
from mathkit.mission import service as MS
from mathkit.mission.from_module import from_module
from mathkit.mission.model import Mission, Spacecraft, Propagator, Burn, Command, CoordSys
from mathkit.mission.run import run, MissionError
from mathkit.mission import params as MP
from mathkit.gmat.export import export_script
from mathkit.gmat.importer import import_script
from mathkit.presets.runner import defaults
from mathkit.registry import MODULES
from mathkit.ephem import get_provider
from mathkit.ephem.approx import AnalyticEphemeris
from mathkit.ui import api

ROOT = pathlib.Path(__file__).resolve().parents[1]
C = ConstantSet()
MU_E = C.mu('Earth')


# ---------------------------------------------------------------------------------------------------------- conventions
def test_vfpa_is_90_minus_gamma_hw4():
    assert CV.vfpa_from_gamma(-62.397426) == pytest.approx(152.397426, abs=1e-9)
    assert CV.vfpa_from_gamma(-31.01451) == pytest.approx(121.01451, abs=1e-9)
    assert CV.gamma_from_vfpa(CV.vfpa_from_gamma(-33.3)) == pytest.approx(-33.3)


@pytest.mark.parametrize('dv,al,be', [(1.0, 45.0, 60.0), (3.2, -114.7, 0.0), (0.5, 170.0, -30.0), (2.0, 0.0, 89.0)])
def test_vnb_round_trip_and_matches_course_burn(dv, al, be):
    e = CV.vnb_from_dv_alpha_beta(dv, al, be); back = CV.dv_alpha_beta_from_vnb(*e)
    assert back[0] == pytest.approx(dv) and back[2] == pytest.approx(be) and np.cos(np.radians(back[1] - al)) == pytest.approx(1.0)
    r, v, _ = rv_from_elements(MU_E, 26000, 0.7, 28.5, 40, 60, 150)
    _, dvec_course = apply_dv_vnc(r, v, dv, al, be)
    from mathkit.mission.run import _maneuver_dv
    assert np.allclose(_maneuver_dv(Burn('b', 'Earth', 'VNB', *e), r, v, MU_E), dvec_course, atol=1e-12)


def test_angle_wraps_round_trip():
    for x in (-179.5, -10.0, 0.0, 33.0, 180.0):
        assert CV.from_gmat_angle(CV.to_gmat_angle(x)) == pytest.approx(CV.from_gmat_angle(x))
    assert CV.to_gmat_angle(-56.4427) == pytest.approx(303.5573)


def test_gmat_names_and_dates():
    assert CV.gmat_body('Moon') == 'Luna' and CV.course_body('Luna') == 'Moon' and CV.gmat_frame('Moon') == 'LunaMJ2000Eq'
    assert CV.modjulian_from_jd(2451545.0) == 21545.0 and CV.c3_from_energy(0.5368) == pytest.approx(1.0736)


def test_gmat_mode_hw4_values_and_data_unchanged():
    course = api.solve(dict(mid='5', vals={}, opts={'skip3d': True})); data_c = {k: v for k, v in api.LAST['res'].data['hy'].items()}
    gm = api.solve(dict(mid='5', vals={}, opts={'skip3d': True, 'convention': 'gmat'})); data_g = {k: v for k, v in api.LAST['res'].data['hy'].items()}
    assert data_c == data_g                                                          # presentation only: Result.data never changes
    rows = {r[1]: r for g in gm['groups'] for r in g['rows']}
    assert float(rows['VFPA'][2].split()[0]) == pytest.approx(152.397426, abs=1e-3) and float(rows['TA_aim'][2].split()[0]) == pytest.approx(303.5573, abs=1e-3)   # the table shows 6 significant digits
    res = api.LAST['res']; assert CV.vfpa_from_gamma(res.get('γ')) == pytest.approx(152.397426, abs=1e-5) and CV.to_gmat_angle(res.get('θ*_aim')) == pytest.approx(303.55730, abs=1e-5)
    assert 'course: γ' in rows['VFPA'][5] and rows['HFPA'][5]
    assert course['convention'] == 'course' and gm['convention'] == 'gmat'
    assert any(r[1] == 'γ' for g in course['groups'] for r in g['rows'])            # the course view is untouched


@pytest.mark.parametrize('mid', list(MODULES))
def test_convention_never_changes_results(mid):
    a = api.solve(dict(mid=mid, vals={}, opts={'skip3d': True})); ra = api.LAST['res']
    b = api.solve(dict(mid=mid, vals={}, opts={'skip3d': True, 'convention': 'gmat'})); rb = api.LAST['res']
    assert 'error' not in a and 'error' not in b
    for s1, s2 in zip(ra.steps, rb.steps):
        assert s1.name == s2.name and (s1.value is s2.value or np.all(np.asarray(s1.value) == np.asarray(s2.value)) if not isinstance(s1.value, str) else s1.value == s2.value)


# --------------------------------------------------------------------------------------------------------------- time
def test_gmat_time_systems():
    jd = TU.calendar_to_jd(2000, 1, 1, 12)
    assert TU.jd_to_modjulian(jd) == 21545.0
    assert TU.tai_minus_utc(TU.calendar_to_jd(2024, 3, 1)) == 37.0 and TU.tai_minus_utc(TU.calendar_to_jd(2016, 12, 31, 12)) == 36.0
    assert TU.tdb_minus_utc(TU.calendar_to_jd(2026, 6, 1)) == pytest.approx(69.184, abs=0.002)        # 37 + 32.184 + periodic term
    assert TU.format_gregorian(TU.parse_gregorian('27 Sep 2024 00:00:00.000')) == '27 Sep 2024 00:00:00.000'
    for fmt in ('UTCGregorian', 'UTCModJulian', 'TAIModJulian', 'A1ModJulian'):
        j = TU.calendar_to_jd(2024, 9, 27, 3.5); assert abs(MP.parse_epoch(MP.format_epoch(j, fmt), fmt) - j) * 86400 < 1e-3


# ---------------------------------------------------------------------------------------------- integrators and events
@pytest.mark.parametrize('method,tol', [('RungeKutta89', 1e-6), ('PrinceDormand78', 1e-6), ('PrinceDormand45', 1e-4)])
def test_integrators_match_kepler_over_a_period(method, tol):
    a, e = 40000.0, 0.75; r0, v0, _ = rv_from_elements(MU_E, a, e, 30, 40, 50, 100); y0 = np.concatenate([r0, v0]); P = 2 * np.pi * np.sqrt(a ** 3 / MU_E)
    s = propagate(two_body_rhs(MU_E), y0, 0.0, P, method=method)
    rK, vK = kepler_propagate(MU_E, r0, v0, P)
    assert np.linalg.norm(s.y[-1][:3] - rK) < tol
    en = lambda y: 0.5 * y[3:] @ y[3:] - MU_E / np.linalg.norm(y[:3]); h = lambda y: np.linalg.norm(np.cross(y[:3], y[3:]))
    if method != 'PrinceDormand45':
        assert abs(en(s.y[-1]) - en(y0)) / abs(en(y0)) < 1e-10 and abs(h(s.y[-1]) - h(y0)) / h(y0) < 1e-10


def test_gmat_tables_satisfy_order_conditions():
    from mathkit.dyn import _gmat_tables as T
    for tag, order in (('RK89', 8), ('PD78', 8)):
        ai = np.array(getattr(T, tag + '_AI')); c = np.array(getattr(T, tag + '_CJ'))
        for k in range(order): assert c @ ai ** k == pytest.approx(1.0 / (k + 1), abs=1e-12)


def test_hyperbola_hw4_p3_gmat_table():
    m = MS.starter('Venus hyperbolic flyby (HW4 P3)'); r = run(m, None); s0, st = r.start['Sat'], r.final['Sat']; mu = C.mu('Venus')
    assert np.linalg.norm(s0.r) == pytest.approx(225826.422, abs=1e-3) and np.linalg.norm(s0.v) == pytest.approx(1.9876217, abs=1e-7)       # HW4 (c) GMAT table, start
    k0 = MP.keplerian(mu, s0.r, s0.v); assert k0['VFPA'] == pytest.approx(152.397426, abs=1e-5) and k0['HFPA'] == pytest.approx(-62.397426, abs=1e-5)
    k1 = MP.keplerian(mu, st.r, st.v); assert k1['RMAG'] == pytest.approx(80045.57339, abs=2e-3) and k1['VMAG'] == pytest.approx(3.031570, abs=2e-6)        # aim point
    assert k1['TA'] == pytest.approx(303.5573, abs=1e-4) and k1['VFPA'] == pytest.approx(121.01451, abs=2e-5)
    m.propagators[0].integrator = 'Kepler (analytic)'; r2 = run(m, None)
    assert np.linalg.norm(r2.final['Sat'].r - st.r) < 1e-5                           # numerical and exact agree


def test_apsis_events_match_analytic_times():
    from mathkit.core.kepler import time_since_periapsis
    a, e = 30000.0, 0.6; r0, v0, _ = rv_from_elements(MU_E, a, e, 20, 10, 30, 70.0); y0 = np.concatenate([r0, v0]); P = 2 * np.pi * np.sqrt(a ** 3 / MU_E)
    s = propagate(two_body_rhs(MU_E), y0, 0.0, 2 * P, events=[Event(lambda t, y: y[:3] @ y[3:], 'peri', +1, False), Event(lambda t, y: y[:3] @ y[3:], 'apo', -1, False)])
    t0 = time_since_periapsis(MU_E, a, e, 70.0); t_apo = P / 2 - t0
    first = {}
    for t, _, n in s.events: first.setdefault(n, t)
    assert first['apo'] == pytest.approx(t_apo, abs=1e-6) and first['peri'] == pytest.approx(P - t0, abs=1e-6)
    assert len(s.events) == 4                                                        # two apsides per period over two periods


def test_stop_at_true_anomaly_and_first_event_wins():
    m = Mission(); m.spacecraft = [Spacecraft('A', epoch='01 Jan 2026 12:00:00.000', state=dict(SMA=30000.0, ECC=0.6, INC=20, RAAN=10, AOP=30, TA=0.0)), Spacecraft('B', epoch='01 Jan 2026 12:00:00.000', state=dict(SMA=9000.0, ECC=0.05, INC=0, RAAN=0, AOP=0, TA=0.0))]
    m.propagators = [Propagator('P1', 'Earth', 'two_body', ['Earth'], 'RungeKutta89'), Propagator('P2', 'Earth', 'two_body', ['Earth'], 'Kepler (analytic)')]
    m.commands = [Command('Propagate', items=[['P1', ['A']]], stops=['A.Earth.TA = 90'])]
    r = run(m, None); el = elements_from_rv(MU_E, r.final['A'].r, r.final['A'].v); assert el['ths'] == pytest.approx(90.0, abs=1e-7)
    m.commands = [Command('Propagate', synchronized=True, items=[['P1', ['A']], ['P2', ['B']]], stops=['A.Earth.TA = 90', 'B.ElapsedSecs = 300'])]
    r = run(m, None); assert (r.final['A'].jd - r.start['A'].jd) * 86400 == pytest.approx(300.0, abs=1e-3) and (r.final['B'].jd - r.start['B'].jd) * 86400 == pytest.approx(300.0, abs=1e-3)      # epochs are float JDs: ~5e-5 s resolution


def test_missing_stop_condition_is_reported():
    m = MS.starter('LEO to GEO Hohmann transfer'); m.commands = [Command('Propagate', items=[['Prop', ['Sat']]], stops=[])]
    with pytest.raises(MissionError): run(m, None)


# ----------------------------------------------------------------------------------------------- module -> mission
@pytest.mark.parametrize('mid', ['3', '4', '5', '6', '7', '8', '12'])
def test_open_in_mission_reproduces_module(mid):
    spec = MODULES[mid]; v = defaults(spec); v['_label'] = 't'; res = spec.run(v, C); m = from_module(mid, v, res, C)
    m.propagators[0].integrator = 'Kepler (analytic)'; exact = run(m, None, C).final['Sat']
    m.propagators[0].integrator = 'RungeKutta89'; num = run(m, None, C).final['Sat']
    assert np.linalg.norm(exact.r - num.r) / np.linalg.norm(exact.r) < 1e-8
    if mid == '12':                                                              # arrives at r2 after the Lambert time of flight
        TA = np.radians(res.data['TA']); r2 = res.data['r2'] * np.array([np.cos(TA), np.sin(TA), 0])
        assert np.linalg.norm(exact.r - r2) < 1e-6
    if mid == '8': assert np.linalg.norm(exact.r) == pytest.approx(float(v['r2']), rel=1e-9)
    text = export_script(m); back = import_script(text)
    assert not back.skipped and [c.text() for c in back.mission.commands] == [c.text() for c in m.commands if c.enabled]


def test_unsupported_modules_explain_themselves():
    r = api.solve(dict(mid='1', vals={}, opts={'skip3d': True})); assert 'error' not in r
    out = api.mission_from_module({}); assert not out['ok'] and 'Module 1' in out['error']


# ------------------------------------------------------------------------------------------ models, forces, ephemeris
def test_moon_and_sun_perturb_geo_by_a_physical_amount():
    eph = AnalyticEphemeris(); m = MS.starter('GEO with Moon and Sun perturbations'); m.commands[0].stops = ['Sat.ElapsedDays = 5']; a = run(m, eph).final['Sat']
    m.commands[0].items = [['Prop', ['Sat']]]; b = run(m, eph).final['Sat']
    d = np.linalg.norm(a.r - b.r)
    assert 0.5 < d < 500                                                          # km after 5 days: nonzero and sensible
    # compare with the perturbing/dominant acceleration ratio of Module 1's formula at the start state
    r0 = run(m, eph).start['Sat'].r; mu_m, mu_s = C.mu('Moon'), C.mu('Sun'); dm = eph.state('Moon', TU.utc_to_tdb(run(m, eph).start['Sat'].jd), 'Earth')[0]
    ratio = mu_m * np.linalg.norm(1 / np.linalg.norm(dm - r0) ** 2 * (dm - r0) / np.linalg.norm(dm - r0) - dm / np.linalg.norm(dm) ** 3) / (MU_E / np.linalg.norm(r0) ** 2)
    assert 1e-6 < ratio < 1e-3


def test_cr3bp_lagrange_points_and_jacobi_constant():
    sysm = CR3BP.from_bodies(C.mu('Earth'), C.mu('Moon'), 384400.0); f = sysm.rhs(); L = sysm.lagrange_points()
    for k, p in L.items(): assert np.abs(f(0, np.concatenate([p, np.zeros(3)]))[3:]).max() < 1e-12
    assert 0.83 < L['L1'][0] < 0.85 and 1.15 < L['L2'][0] < 1.16 and L['L3'][0] < -1.0
    y0 = np.array([0.5, 0.3, 0.0, -0.4, 0.6, 0.0]); s = propagate(f, y0, 0.0, 2 * np.pi * 10, accuracy=1e-13, h0=0.01, h_min=1e-9, h_max=0.05)
    assert abs(sysm.jacobi(s.y[-1]) - sysm.jacobi(y0)) / abs(sysm.jacobi(y0)) < 1e-10


def test_earth_sphere_of_influence():
    assert soi_radius(BODIES['Earth']['a'], C.mu('Earth'), C.mu('Sun')) == pytest.approx(9.25e5, rel=0.01)


def test_cr3bp_mission_runs():
    r = api.mission_run(dict(mission=MS.starter('Earth-Moon restricted three-body demo').to_dict(), opts={'skip3d': True}, theme='dark')); assert 'error' not in r


def test_hiding_a_body_does_not_change_the_trajectory_but_gravity_does():
    eph = AnalyticEphemeris(); m = MS.starter('GEO with Moon and Sun perturbations'); m.commands[0].stops = ['Sat.ElapsedDays = 3']; a = run(m, eph).final['Sat'].r.copy()
    m.views[0].objects = ['Sat']; assert np.allclose(run(m, eph).final['Sat'].r, a)                  # visibility lives in the view only
    m.propagators[1].gravity = ['Earth']; assert np.linalg.norm(run(m, eph).final['Sat'].r - a) > 1.0


def test_builtin_ephemeris_is_sane():
    eph = AnalyticEphemeris()
    for day in range(0, 365, 30):
        jd = TU.calendar_to_jd(2026, 1, 1) + day; r = eph.state('Earth', jd, 'Sun')[0]
        assert 0.9832 < np.linalg.norm(r) / 149597870.7 < 1.0168
        assert 356000 < np.linalg.norm(eph.state('Moon', jd, 'Earth')[0]) < 407000


@pytest.mark.ephem
@pytest.mark.skipif(not os.environ.get('ORBIT_DE440S') and not (pathlib.Path(os.environ.get('ORBIT_SIMULATOR_HOME', '')) / 'kernels' / 'de440s.bsp').exists(), reason='DE440s kernel not available')
def test_builtin_ephemeris_against_de440s():
    de = get_provider(prefer='auto'); assert 'DE440s' in de.name; an = AnalyticEphemeris()
    jd = TU.utc_to_tdb(TU.calendar_to_jd(2026, 6, 1))
    assert np.linalg.norm(de.state('Moon', jd, 'Earth')[0] - an.state('Moon', jd, 'Earth')[0]) < 200
    assert np.linalg.norm(de.state('Mars', jd, 'Sun')[0] - an.state('Mars', jd, 'Sun')[0]) < 2e5


# ------------------------------------------------------------------------------------------------------ GMAT I/O
@pytest.mark.parametrize('name', list(MS.STARTERS))
def test_starter_missions_run_and_round_trip(name):
    m = MS.starter(name); out = api.mission_run(dict(mission=m.to_dict(), opts={'skip3d': True}, theme='dark')); assert 'error' not in out, out.get('error')
    text = export_script(m); back = import_script(text); assert not back.skipped
    assert [c.text() for c in back.mission.commands] == [c.text() for c in m.commands]
    assert [round(s.state[k], 9) for s in back.mission.spacecraft for k in s.state] == [round(s.state[k], 9) for s in m.spacecraft for k in s.state]
    assert Mission.from_json(m.to_json()).to_dict() == m.to_dict()                                 # .orbitmission round trip


def test_script_syntax_matches_gmat_template():
    t = export_script(MS.starter('Venus hyperbolic flyby (HW4 P3)'))
    for line in ('Create Spacecraft Sat;', "Sat.Epoch = '27 Sep 2024 00:00:00.000';", 'Sat.CoordinateSystem = VenusMJ2000Eq;', 'FM_Prop_Venus.CentralBody = Venus;', 'FM_Prop_Venus.PointMasses = {Venus};',
                 'Prop_Venus.Type = RungeKutta89;', 'VenusMJ2000Eq.Origin = Venus;', 'BeginMissionSequence;', 'Propagate Prop_Venus(Sat) {Sat.Venus.TA = 303.5573097619207};', 'Sat.SMA = -302595.0;'):
        assert line in t, line
    assert 'Luna' in export_script(MS.starter('GEO with Moon and Sun perturbations')) and '% expected' in t


def test_exam_rounded_constants_write_a_warning():
    m = MS.starter('LEO to GEO Hohmann transfer'); m.constants = 'Exam rounded'
    assert 'WARNING' in export_script(m)


def test_importer_loads_the_gmat_tutorial_script():
    text = (ROOT / 'tests' / 'data' / 'Tut_SimulatingAnOrbit.script').read_text(encoding='utf-8'); r = import_script(text)
    m = r.mission; sc = m.spacecraft[0]
    assert sc.name == 'Sat' and sc.state['SMA'] == pytest.approx(83474.318) and m.propagators[0].gravity == ['Earth', 'Moon', 'Sun'] and m.propagators[0].srp
    assert [c.text() for c in m.commands] == ['Propagate LowEarthProp(Sat) {Sat.Earth.Periapsis}']
    assert any('OpenFrames' in s for s in r.skipped)                                               # unsupported items are listed, not fatal
    res = run(m, AnalyticEphemeris()); st = res.final['Sat']; el = elements_from_rv(MU_E, st.r, st.v)
    assert abs(el['ths']) < 1e-6 and 8000 < np.linalg.norm(st.r) < 9200                              # apoapsis to the next periapsis


def test_importer_skips_what_it_cannot_model():
    r = import_script("Create Spacecraft S; S.SMA = 7000; S.ECC = 0.0;\nCreate Variable v;\nBeginMissionSequence;\nTarget DC;\nPropagate Prop(S) {S.ElapsedSecs = 10};\n")
    assert 'Create Variable v' in r.skipped and any(s.startswith('Target') for s in r.skipped) and len(r.mission.commands) == 1


def test_api_import_export_paths():
    m = MS.starter('Earth to Mars Hohmann arc').to_dict(); s = api.mission_script(dict(mission=m)); assert s['round_trip_commands'] and not s['skipped']
    back = api.mission_import(dict(filename='x.script', text=s['script'])); assert back['ok'] and back['mission']['commands']
    assert not api.mission_import(dict(filename='x.script', text='% nothing'))['ok']
    assert api.mission_import(dict(filename='m.orbitmission', text=json.dumps(m)))['ok'] and not api.mission_import(dict(filename='m.orbitmission', text='nope'))['ok']
    save = api.mission_save(dict(mission=m, kind='script')); assert save['ok'] and pathlib.Path(save['path']).read_text(encoding='utf-8').startswith('%')


def test_gmat_export_from_a_module_result():
    api.solve(dict(mid='8', vals={}, opts={'skip3d': True})); data, mime, name = api.export(0, 'script', 'light')
    assert name.endswith('.script') and b'BeginMissionSequence' in data and b'Maneuver DV1(Sat);' in data


def test_comparison_panel_flags_differences():
    mm = MS.starter('GEO with Moon and Sun perturbations'); mm.commands[0].stops = ['Sat.ElapsedDays = 5']; out = api.mission_compare(dict(mission=mm.to_dict()))
    assert 'rows' in out and out['position_difference_km']['Sat'] > 0.5 and out['gmat_status'] == 'GMAT not configured'
    exact = api.mission_compare(dict(mission=MS.starter('Venus hyperbolic flyby (HW4 P3)').to_dict())); assert exact['position_difference_km']['Sat'] < 1e-6


def test_failed_run_returns_a_clear_error():
    m = MS.starter('LEO to GEO Hohmann transfer').to_dict(); m['spacecraft'][0]['state']['SMA'] = -5.0
    out = api.mission_run(dict(mission=m, opts={'skip3d': True}, theme='dark')); assert 'error' in out and 'SMA' in out['error']


# ------------------------------------------------------------------------------------------------------- licences
def test_licence_files_and_about_data():
    assert 'Apache License' in (ROOT / 'LICENSES' / 'GMAT-Apache-2.0.txt').read_text(encoding='utf-8') and 'MIT' in (ROOT / 'LICENSES' / 'jplephem-MIT.txt').read_text(encoding='utf-8')
    notice = (ROOT / 'NOTICE').read_text(encoding='utf-8'); assert 'GMAT' in notice and 'Apache' in notice and 'MODIFIED' in notice
    items = api.licenses({})['items']; assert any('Apache License' in i['text'] for i in items) and items[0]['name'] == 'Notice'
    assert 'NASA GMAT' in (ROOT / 'mathkit' / 'dyn' / '_gmat_tables.py').read_text(encoding='utf-8')


# ------------------------------------------------------------------------------------------------------- porkchop, trajectory files
def test_porkchop_cell_matches_module_12_lambert():
    from mathkit.mission import porkchop as PK
    from mathkit.core.lambert import lambert
    eph = AnalyticEphemeris(); mu = C.mu('Sun'); jd_d = TU.calendar_to_jd(2026, 11, 8); jd_a = TU.calendar_to_jd(2027, 8, 12)
    c = PK.cell(mu, eph, 'Earth', 'Mars', jd_d, jd_a)
    r1 = PK._ecl(eph.state('Earth', TU.utc_to_tdb(jd_d), 'Sun')[0]); r2 = PK._ecl(eph.state('Mars', TU.utc_to_tdb(jd_a), 'Sun')[0])
    TA = np.degrees(np.arccos(r1 @ r2 / (np.linalg.norm(r1) * np.linalg.norm(r2)))); TA = TA if np.cross(r1, r2)[2] > 0 else 360 - TA
    L = lambert(mu, np.linalg.norm(r1), np.linalg.norm(r2), TA, (jd_a - jd_d) * 86400.0, 'small')
    assert np.linalg.norm(c['v1']) == pytest.approx(L['vD_mag'], rel=1e-9) and c['a'] == pytest.approx(L['a'], rel=1e-9)
    assert 5 < c['c3'] < 30 and 1 < c['vinf_arr'] < 8


def test_porkchop_finds_the_2026_mars_window_and_builds_a_transfer():
    from mathkit.mission import porkchop as PK
    eph = AnalyticEphemeris(); g = PK.grid(eph, 'Earth', 'Mars', TU.calendar_to_jd(2026, 9, 1), 200, TU.calendar_to_jd(2027, 5, 1), 250, n=14)
    b = g['best']; assert TU.calendar_to_jd(2026, 10, 1) < b['dep_jd'] < TU.calendar_to_jd(2027, 1, 15) and 7 < b['c3'] < 16             # the late-2026 minimum-energy window
    m = PK.transfer_mission(eph, 'Earth', 'Mars', b['dep_jd'], b['arr_jd']); fin = run(m, None).final['Sat']
    r2 = PK._ecl(eph.state('Mars', TU.utc_to_tdb(b['arr_jd']), 'Sun')[0]); assert np.linalg.norm(PK._ecl(fin.r) - r2) < 50                            # arrives at Mars (km), limited by the float-JD epoch


def test_trajectory_files():
    m = MS.starter('LEO to GEO Hohmann transfer'); res = run(m, None)
    csv_text = MS.trajectory_csv(res, 'Sat'); assert csv_text.splitlines()[0].startswith('UTC,JD_UTC') and len(csv_text.splitlines()) > 100
    oem = MS.trajectory_oem(res, 'Sat'); assert oem.startswith('CCSDS_OEM_VERS = 2.0') and 'REF_FRAME = EME2000' in oem and 'CENTER_NAME = EARTH' in oem and 'META_START' in oem
    assert api.mission_trajectory(dict(mission=m.to_dict(), kind='oem'))['ok'] and api.mission_trajectory(dict(mission=m.to_dict(), kind='csv'))['ok']


# ------------------------------------------------------------------------------------ patched conics, trajectory import, tour files
def test_patched_conics_hand_off_at_the_earth_sphere_of_influence():
    from mathkit.mission.patched import PatchedPath, soi
    eph = AnalyticEphemeris(); jd = TU.calendar_to_jd(2026, 11, 1); re_, ve_ = eph.state('Earth', TU.utc_to_tdb(jd), 'Sun')
    assert soi('Earth', C) == pytest.approx(9.25e5, rel=0.01) and soi('Moon', C) == pytest.approx(6.6e4, rel=0.02)
    path = PatchedPath(C, eph, jd, 'Sun', np.array([7000.0, 0, 0]) + re_, np.array([0, 11.5, 0]) + ve_, 'Sun', 100 * 86400.0)
    assert [a.center for a in path.arcs] == ['Earth', 'Sun'] and path.handoffs[0]['kind'] == 'soi-exit'
    t = path.handoffs[0]['t']; a = path.state(t - 1e-3); b = path.state(t + 1e-3)
    assert np.linalg.norm(a[:3] - b[:3]) < 0.1 and np.linalg.norm(a[3:] - b[3:]) < 1e-6          # continuous in the heliocentric frame (the gap is the motion in 2 ms)
    el_ = elements_from_rv(C.mu('Sun'), path.state(t + 86400)[:3], path.state(t + 86400)[3:]); assert el_['e'] < 1 and el_['a'] > 1.2e8


def test_patched_conics_in_a_mission():
    eph = AnalyticEphemeris(); m = Mission(); m.coords = [CoordSys('SunMJ2000Eq', 'Sun', 'MJ2000Eq')]
    m.spacecraft = [Spacecraft('Sat', epoch='01 Nov 2026 00:00:00.000', coord='EarthMJ2000Eq', state_type='Cartesian', state=dict(X=7000.0, Y=0.0, Z=0.0, VX=0.0, VY=11.5, VZ=0.0))]
    m.propagators = [Propagator('PC', 'Sun', 'patched', ['Sun'], 'Kepler (analytic)')]; m.commands = [Command('Propagate', items=[['PC', ['Sat']]], stops=['Sat.ElapsedDays = 30'])]
    r = run(m, eph, C); assert any(e['kind'] == 'soi-exit' for e in r.events) and r.final['Sat'].central == 'Sun'
    with pytest.raises(MissionError): run(m, None, C)                                          # no ephemeris, no patched conics


def test_trajectory_import_round_trip_and_comparison():
    from mathkit.mission import trajectory_io as TI
    m = MS.starter('LEO to GEO Hohmann transfer'); res = run(m, None)
    csv_ref = TI.import_text('x.csv', MS.trajectory_csv(res, 'Sat')); oem_ref = TI.import_text('x.oem', MS.trajectory_oem(res, 'Sat'))
    for ref in (csv_ref, oem_ref):
        assert ref['center'] == 'Earth' and len(ref['jd']) == len(res.samples['Sat']['jd'])
        d = TI.compare_with(ref, res.samples['Sat']['jd'], np.array(res.samples['Sat']['r'])); assert d['max_km'] < 1e-3              # 1 m (CSV prints 9 decimals; epochs are float JDs)
    with pytest.raises(ValueError): TI.parse_oem(MS.trajectory_oem(res, 'Sat').replace('EME2000', 'TEME'))
    with pytest.raises(ValueError): TI.parse_csv('a,b\n1,2\n3,4\n5,6')
    out = api.mission_run(dict(mission=m.to_dict(), opts={'skip3d': True}, theme='dark', refs=[csv_ref])); assert out['ref_diff'][0]['points'] > 50 and out['ref_diff'][0]['max_km'] < 1e-3


@pytest.mark.ephem
@pytest.mark.skipif(not os.environ.get('ORBIT_DE440S'), reason='DE440s kernel not available')
def test_spk_import_samples_a_kernel():
    from mathkit.mission import trajectory_io as TI
    ref = TI.parse_spk(os.environ['ORBIT_DE440S'], target=301, n=50); assert ref['center'] == 'Earth' and 356000 < np.linalg.norm(ref['r'][0]) < 407000


def test_tutorial_is_wired_for_first_launch_and_later_access():
    web = ROOT / 'mathkit' / 'ui' / 'web'; app = (web / 'app.js').read_text(encoding='utf-8'); tour = (web / 'tour.js').read_text(encoding='utf-8'); html = (web / 'index.html').read_text(encoding='utf-8')
    assert '/tour.js' in html and 'tourDone' in app and "if (!SET.tourDone) setTimeout(() => startTour()" in app          # first launch
    assert "label: 'Start Tutorial'" in app and "tour: 'F1'" in app and "'Start the Tutorial'" in app                  # help menu, F1, settings
    assert tour.count("title:") >= 10 and 'function startTour' in tour


# ------------------------------------------------------------------------------------------------------ sky orientation
def test_sky_rotation_maps_the_galactic_centre_and_pole_to_icrf():
    from mathkit import sky
    gc = sky.ICRS_TO_GAL.T @ np.array([1.0, 0, 0]); ngp = sky.ICRS_TO_GAL.T @ np.array([0, 0, 1.0])
    ra, dec = sky.vec_to_radec(gc); assert ra == pytest.approx(266.405, abs=0.01) and dec == pytest.approx(-28.936, abs=0.01)
    ra, dec = sky.vec_to_radec(ngp); assert ra == pytest.approx(192.859, abs=0.01) and dec == pytest.approx(27.128, abs=0.01)
    assert np.allclose(sky.ICRS_TO_GAL @ sky.ICRS_TO_GAL.T, np.eye(3), atol=1e-12) and np.linalg.det(sky.ICRS_TO_GAL) == pytest.approx(1.0)
    l, b = sky.to_galactic(sky.radec_to_vec(*sky.GALACTIC_CENTER)); assert abs(((l + 180) % 360) - 180) < 0.01 and abs(b) < 0.01


def test_sky_map_pixels_hit_the_bright_stars():
    """The star map's brightest pixels sit exactly where the documented mapping puts Sirius, Arcturus, Canopus, Vega, Capella, Procyon, Betelgeuse and Rigel."""
    from mathkit import sky
    from PIL import Image, ImageFilter
    im = Image.open(ROOT / 'assets' / 'textures' / '2k_stars.jpg').convert('L'); W, H = im.size; a = np.asarray(im.filter(ImageFilter.GaussianBlur(2)), float)
    for name in ('Sirius', 'Arcturus', 'Canopus', 'Vega', 'Capella', 'Procyon', 'Betelgeuse', 'Rigel'):
        x, y = sky.pixel(sky.radec_to_vec(*sky.STARS[name]), W, H); x, y = int(round(x)) % W, int(round(y))
        assert a[max(0, y - 6):y + 7, max(0, x - 6):x + 7].max() >= 10, name
    x, y = sky.pixel(sky.radec_to_vec(*sky.STARS['Polaris']), W, H); assert 0 <= y < H                         # Polaris is a debug marker only (too faint to test)
    x0, y0 = sky.pixel(sky.radec_to_vec(*sky.GALACTIC_CENTER), W, H); assert abs(x0 - W / 2) < 1 and abs(y0 - H / 2) < 1


@pytest.mark.spice
@pytest.mark.skipif(__import__('importlib').util.find_spec('spiceypy') is None, reason='spiceypy not installed')
def test_cosmographia_spk_reads_back_with_spice(tmp_path):
    import spiceypy as sp
    from mathkit.mission import cosmographia as CG
    m = MS.starter('LEO to GEO Hohmann transfer'); res = run(m, None); out = CG.export(res, 'Sat', tmp_path, m.name)
    cat = json.loads(pathlib.Path(out['catalog']).read_text(encoding='utf-8')); assert cat['items'][0]['class'] == 'spacecraft' and cat['spiceKernels'] == ['Sat.bsp']
    sp.furnsh(out['spk']); sm = res.samples['Sat']
    try:
        for k in (5, 300, len(sm['jd']) - 5):
            et = (TU.utc_to_tdb(sm['jd'][k]) - TU.JD_J2000) * 86400; st, _ = sp.spkgeo(-999000, et, 'J2000', 399)
            assert np.linalg.norm(np.array(st[:3]) - sm['r'][k]) < 1e-6 and np.linalg.norm(np.array(st[3:]) - sm['v'][k]) < 1e-9
    finally: sp.unload(out['spk'])


def test_cosmographia_export_explains_a_missing_spiceypy(monkeypatch):
    from mathkit.mission import cosmographia as CG
    monkeypatch.setattr(CG, 'available', lambda: False)
    with pytest.raises(ValueError, match='spiceypy'): CG.export(run(MS.starter('LEO to GEO Hohmann transfer'), None), 'Sat', '.')


# -------------------------------------------------------------------------------------------------------- maneuver-node planner
def _planner_setup():
    d = MS.starter('LEO to GEO Hohmann transfer').to_dict()
    out = MS.run_mission(d, {'skip3d': True, 'theme': 'dark'}, lambda n, sc, th, u, w3, o: dict(name=n, svg='', html3d='', overlaps=0, has_anim=False, notes=[], is3d=False), None)
    return d, out['space']['tracks'][0]


def test_node_preview_matches_the_inserted_burn():
    d, trk = _planner_setup(); assert len(trk['idx']) == len(trk['cmd']) == len(trk['tc']) > 100
    idx = trk['idx'][len(trk['idx']) // 4]; e = [0.3, 0.05, -0.1]
    pv = MS.preview_node(d, None, 'Sat', idx, e); assert pv['ok'] and pv['after']['SMA'] != pv['before']['SMA'] and pv['dv'] == pytest.approx(np.linalg.norm(e))
    new = Mission.from_dict(MS.insert_node(d, None, 'Sat', idx, e)); res = run(new, None)
    k = next(i for i, c in enumerate(new.commands) if c.kind == 'Maneuver' and c.burn == 'Node1')
    assert [c.kind for c in new.commands][k - 1:k + 2] == ['Propagate', 'Maneuver', 'Propagate']
    sm = res.samples['Sat']; j = next(i for i in range(len(sm['jd'])) if sm['cmd'][i] == k)                      # first sample recorded by the node burn (after the burn)
    el = MP.keplerian(MU_E, sm['r'][j], sm['v'][j]); assert el['SMA'] == pytest.approx(pv['after']['SMA'], rel=1e-6) and el['ECC'] == pytest.approx(pv['after']['ECC'], abs=1e-7)
    assert np.linalg.norm(sm['r'][j] - np.array(pv['node']['r'])) < 1.0                                         # the burn happens exactly where the node was placed


def test_node_insertion_edge_cases():
    d, trk = _planner_setup(); first = Mission.from_dict(MS.insert_node(d, None, 'Sat', trk['idx'][0], [0.1, 0, 0]))
    assert first.commands[0].kind == 'Maneuver' and first.burns[-1].name == 'Node1'                              # sample 0 is the start of the first command's burn: node goes after it
    last = trk['idx'][-10]; late = Mission.from_dict(MS.insert_node(d, None, 'Sat', last, [0.0, 0.2, 0.0]))
    stops = [c.stops for c in late.commands if c.kind == 'Propagate']; assert stops[-1][0].startswith('Sat.ElapsedSecs = ') and float(stops[-1][0].split('=')[1]) < 86164 - 80000        # the remainder of the original stop
    assert 'Node1' in late.notes[-1] and run(late, None).final['Sat'].central == 'Earth'
    assert not MS.preview_node(d, None, 'Sat', trk['idx'][5], [0, 0, 0])['dv']



@pytest.mark.parametrize('name', ['sky_milkyway_8k.jpg', 'sky_milkyway_4k.jpg'])
def test_nasa_milky_way_map_orientation(name):
    """The NASA SVS Deep Star Maps 2020 map (galactic, latitude up): the eight brightest stars sit on bright pixels with b_up=True, and not with the older convention."""
    from mathkit import sky
    from PIL import Image, ImageFilter
    Image.MAX_IMAGE_PIXELS = None
    im = Image.open(ROOT / 'assets' / 'textures' / name).convert('L'); W, H = im.size; assert (W, H) in ((8192, 4096), (4096, 2048))
    a = np.asarray(im.filter(ImageFilter.GaussianBlur(1.5)), float); good = bad = 0
    for star in ('Sirius', 'Arcturus', 'Canopus', 'Vega', 'Capella', 'Procyon', 'Betelgeuse', 'Rigel'):
        v = sky.radec_to_vec(*sky.STARS[star])
        for up in (True, False):
            x, y = sky.pixel(v, W, H, b_up=up); x, y = int(round(x)) % W, int(round(y)); m = a[max(0, y - 8):y + 9, max(0, x - 8):x + 9].max()
            if up and m > 150: good += 1
            if not up and m > 150: bad += 1
    assert good == 8 and bad == 0
    x, y = sky.pixel(sky.radec_to_vec(*sky.GALACTIC_CENTER), W, H, b_up=True); assert abs(x - W / 2) < 1 and abs(y - H / 2) < 1
