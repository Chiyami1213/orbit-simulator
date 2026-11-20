"""Mission workspace back end: starters, running (with 2D/3D scenes), the course-vs-propagated comparison, script export/import, files."""
from __future__ import annotations
from ..spin import spin_for
import csv
import io
import json
import re
import pathlib
import numpy as np
from ..core.constants import ConstantSet, BODIES, D2R
from ..core import timeutil as TU
from ..scene import Scene, Disk, Poly, Pt, Track, Orbit
from ..conventions import Convention, present_dict, gmat_body
from ..dyn.models import soi_radius
from . import params as P
from .model import Mission, Spacecraft, CoordSys, Propagator, Burn, ReportFile, OrbitView, Command, INTEGRATORS, DYNAMICS_LABEL
from .run import run, RunResult, MissionError
from ..gmat.export import export_script
from ..gmat.importer import import_script

PALETTE = ['#ff6b4a', '#4c8df6', '#3ecf8e', '#f5b73b', '#b37bf0', '#e66767']


# ---------------------------------------------------------------------------------------------------------------------------------
# starters
# ---------------------------------------------------------------------------------------------------------------------------------
def _geo_leo_hohmann() -> Mission:
    C = ConstantSet(); mu = C.mu('Earth'); r1, r2 = 6678.14, 42164.0
    aT = (r1 + r2) / 2; v1 = np.sqrt(mu / r1); vp = np.sqrt(mu * (2 / r1 - 1 / aT)); va = np.sqrt(mu * (2 / r2 - 1 / aT)); v2 = np.sqrt(mu / r2)
    m = Mission(name='LEO to GEO Hohmann transfer')
    m.spacecraft = [Spacecraft('Sat', 'UTCGregorian', '01 Jan 2026 12:00:00.000', 'EarthMJ2000Eq', 'Keplerian', dict(SMA=r1, ECC=0.0, INC=0.0, RAAN=0.0, AOP=0.0, TA=0.0))]
    m.propagators = [Propagator('Prop', 'Earth', 'two_body', ['Earth'], 'RungeKutta89')]
    m.burns = [Burn('DV1', 'Earth', 'VNB', float(vp - v1)), Burn('DV2', 'Earth', 'VNB', float(v2 - va))]
    m.reports = [ReportFile('RF', 'LEO_GEO_report.txt', ['Sat.UTCGregorian', 'Sat.Earth.SMA', 'Sat.Earth.ECC', 'Sat.Earth.TA', 'Sat.Earth.RMAG', 'Sat.Earth.VMAG'])]
    m.views = [OrbitView('View', ['Sat', 'Earth'], 'EarthMJ2000Eq')]
    m.commands = [Command('Maneuver', burn='DV1', sat='Sat'), Command('Propagate', items=[['Prop', ['Sat']]], stops=['Sat.Earth.Apoapsis']), Command('Maneuver', burn='DV2', sat='Sat'),
                  Command('Propagate', items=[['Prop', ['Sat']]], stops=['Sat.ElapsedSecs = 86164'])]
    m.notes = [f'dv1 = {vp - v1:.6f} km/s, dv2 = {v2 - va:.6f} km/s, total {vp - v1 + v2 - va:.6f} km/s; transfer time {np.pi * np.sqrt(aT ** 3 / mu) / 3600:.4f} h']
    return m


def _venus_flyby() -> Mission:
    m = Mission(name='Venus hyperbolic flyby (HW4 problem 3)')
    m.coords = [CoordSys('VenusMJ2000Eq', 'Venus', 'MJ2000Eq')]
    m.spacecraft = [Spacecraft('Sat', 'UTCGregorian', '27 Sep 2024 00:00:00.000', 'VenusMJ2000Eq', 'Keplerian', dict(SMA=-302595.0, ECC=1.2, INC=0.0, RAAN=0.0, AOP=0.0, TA=250.0))]
    m.propagators = [Propagator('Prop_Venus', 'Venus', 'two_body', ['Venus'], 'RungeKutta89')]
    m.reports = [ReportFile('RF', 'HW4_P3_report.txt', ['Sat.UTCGregorian', 'Sat.Venus.SMA', 'Sat.Venus.ECC', 'Sat.Venus.TA', 'Sat.Venus.RMAG', 'Sat.Venus.VMAG', 'Sat.Venus.VFPA'])]
    m.views = [OrbitView('View', ['Sat', 'Venus'], 'VenusMJ2000Eq')]
    th_aim = float(360.0 - (np.degrees(np.arccos(-1 / 1.2)) - 90.0))                     # theta*_aim = -(theta*_inf - 90 deg), written as 0..360 for GMAT
    m.commands = [Command('Propagate', items=[['Prop_Venus', ['Sat']]], stops=[f'Sat.Venus.TA = {th_aim!r}'])]
    m.notes = ['start (TA = 250 deg, theta* = -110 deg): r = 225826.422 km, v = 1.9876217 km/s, VFPA = 152.397426 deg (gamma = -62.397426 deg)',
               'aim point (TA = 303.5573 deg, theta* = -56.4427 deg): r = 80045.57339 km, v = 3.031570 km/s, VFPA = 121.01451 deg',
               'v-infinity = 1.0361 km/s and theta*-infinity = 146.44 deg are approached, not reached, in finite time']
    return m


def _geo_perturbed() -> Mission:
    m = Mission(name='GEO with Moon and Sun perturbations (30 days)')
    m.spacecraft = [Spacecraft('Sat', 'UTCGregorian', '01 Jan 2026 12:00:00.000', 'EarthMJ2000Eq', 'Keplerian', dict(SMA=42164.0, ECC=0.0, INC=0.0, RAAN=0.0, AOP=0.0, TA=0.0))]
    m.propagators = [Propagator('Prop', 'Earth', 'two_body', ['Earth'], 'RungeKutta89'), Propagator('PropLS', 'Earth', 'selected_nbody', ['Earth', 'Moon', 'Sun'], 'RungeKutta89')]
    m.reports = [ReportFile('RF', 'GEO_report.txt', ['Sat.UTCGregorian', 'Sat.Earth.SMA', 'Sat.Earth.ECC', 'Sat.Earth.INC'])]
    m.views = [OrbitView('View', ['Sat', 'Earth', 'Moon'], 'EarthMJ2000Eq')]
    m.commands = [Command('Propagate', items=[['PropLS', ['Sat']]], stops=['Sat.ElapsedDays = 30'])]
    m.notes = ['switch the propagator to Prop (two-body) to see how far the course model is from the perturbed answer']
    return m


def _tutorial_orbit() -> Mission:
    m = Mission(name='Simulating an orbit (tutorial elements)')
    m.spacecraft = [Spacecraft('Sat', 'UTCGregorian', '22 Jul 2014 11:29:10.811', 'EarthMJ2000Eq', 'Keplerian', dict(SMA=83474.318, ECC=0.89652, INC=12.4606, RAAN=292.8362, AOP=218.9805, TA=180.0), mass=850.0, area=1.0)]
    m.propagators = [Propagator('LowEarthProp', 'Earth', 'selected_nbody', ['Earth', 'Moon', 'Sun'], 'RungeKutta89', initial_step=60.0, accuracy=1e-11, max_step=2700.0, srp=True)]
    m.views = [OrbitView('View', ['Sat', 'Earth', 'Moon'], 'EarthMJ2000Eq')]
    m.commands = [Command('Propagate', items=[['LowEarthProp', ['Sat']]], stops=['Sat.Earth.Periapsis'])]
    return m


def _earth_mars() -> Mission:
    C = ConstantSet(); mu = C.mu('Sun'); r1, r2 = BODIES['Earth']['a'], BODIES['Mars']['a']; aT = (r1 + r2) / 2
    v1 = np.sqrt(mu / r1); vp = np.sqrt(mu * (2 / r1 - 1 / aT))
    m = Mission(name='Earth to Mars Hohmann arc (heliocentric)')
    m.coords = [CoordSys('SunMJ2000Eq', 'Sun', 'MJ2000Eq')]
    m.spacecraft = [Spacecraft('Sat', 'UTCGregorian', '01 Jan 2026 12:00:00.000', 'SunMJ2000Eq', 'Keplerian', dict(SMA=float(r1), ECC=0.0, INC=0.0, RAAN=0.0, AOP=0.0, TA=0.0))]
    m.propagators = [Propagator('SunProp', 'Sun', 'two_body', ['Sun'], 'RungeKutta89', max_step=864000.0)]
    m.burns = [Burn('Depart', 'Sun', 'VNB', float(vp - v1))]
    m.views = [OrbitView('View', ['Sat', 'Sun', 'Earth', 'Mars'], 'SunMJ2000Eq')]
    m.commands = [Command('Maneuver', burn='Depart', sat='Sat'), Command('Propagate', items=[['SunProp', ['Sat']]], stops=['Sat.Sun.Apoapsis'])]
    return m


def _cr3bp_demo() -> Mission:
    m = Mission(name='Earth-Moon restricted three-body (CR3BP) demo')
    m.spacecraft = [Spacecraft('Sat', 'UTCGregorian', '01 Jan 2026 12:00:00.000', 'EarthMJ2000Eq', 'Cartesian', dict(X=-5000.0, Y=-6700.0, Z=0.0, VX=10.6, VY=-3.0, VZ=0.0))]
    m.propagators = [Propagator('PropR3B', 'Earth', 'cr3bp', ['Earth', 'Moon'], 'RungeKutta89', initial_step=10.0)]
    m.views = [OrbitView('View', ['Sat', 'Earth', 'Moon'], 'EarthMJ2000Eq')]
    m.commands = [Command('Propagate', items=[['PropR3B', ['Sat']]], stops=['Sat.ElapsedDays = 10'])]
    m.notes = ['the Earth-Moon pair is idealised as a circular orbit; the 10 day arc is in the rotating-frame equations of motion']
    return m


STARTERS = {'LEO to GEO Hohmann transfer': _geo_leo_hohmann, 'Venus hyperbolic flyby (HW4 P3)': _venus_flyby, 'GEO with Moon and Sun perturbations': _geo_perturbed,
            'Tutorial orbit (GMAT elements)': _tutorial_orbit, 'Earth to Mars Hohmann arc': _earth_mars, 'Earth-Moon restricted three-body demo': _cr3bp_demo}


def starter(name: str) -> Mission: return STARTERS[name]()


# ---------------------------------------------------------------------------------------------------------------------------------
# running
# ---------------------------------------------------------------------------------------------------------------------------------
def _recentre_samples(res: RunResult, center: str, eph, use_eph: bool):
    out = {}
    for name, s in res.samples.items():
        jd = np.array(s['jd']); r = np.array(s['r']); cen = s['central']
        if len(jd) == 0: continue
        R = r.copy()
        for i, c in enumerate(cen):
            if c != center and eph is not None:
                R[i] = r[i] + eph.state(c, TU.utc_to_tdb(jd[i]), center)[0]
        out[name] = (jd, R, np.array(s['seg']))
    return out


def build_scene(m: Mission, res: RunResult, eph, theme: str, refs: list | None = None) -> Scene:
    center = next((p.central for p in m.propagators), 'Earth'); sc = Scene(title=m.name)
    traj = _recentre_samples(res, center, eph, True); span = 1.0; t0s = {}
    allp = []
    for i, (name, (jd, R, seg)) in enumerate(traj.items()):
        col = (m.sat(name).color if any(s.name == name for s in m.spacecraft) else PALETTE[i % len(PALETTE)])
        sc.polys.append(Poly(R, name, col, False, 2.0, 0.5)); allp.append(R)
        sc.pts.append(Pt(R[0], f'{name} start', col, 'o', 6)); sc.pts.append(Pt(R[-1], f'{name} end', col, 's', 6)); t0s[name] = jd[0]
        span = max(span, (jd[-1] - jd[0]) * 86400.0)
        tt = (jd - jd[0]) * 86400.0
        sc.tracks.append(Track(name, (lambda t, tt=tt, R=R: np.array([np.interp(t, tt, R[:, k]) for k in range(3)])), col))
    for k, ref in enumerate(refs or []):                                                    # imported reference trajectories, drawn dashed
        try:
            R = np.array(ref['r'], float); jdr = np.array(ref['jd'], float)
            if ref['center'] != center:
                if eph is None: continue
                R = np.array([R[i] + eph.state(ref['center'], TU.utc_to_tdb(jdr[i]), center)[0] for i in range(len(jdr))])
            sc.polys.append(Poly(R, f'{ref["name"]} (imported)', PALETTE[(k + 3) % len(PALETTE)], True, 1.5, 0.3)); allp.append(R)
        except Exception: continue
    for ev in res.events:
        if ev['kind'] == 'burn' and ev['sat'] in traj:
            jd, R, _ = traj[ev['sat']]; k = int(np.argmin(np.abs(jd - ev['jd']))); sc.pts.append(Pt(R[k], 'burn', 'warn', 'x', 7))
    sc.duration_s = span
    allv = np.vstack(allp) if allp else np.zeros((1, 3)); ext = float(np.max(np.abs(allv))) or 1.0
    R_c = ConstantSet(m.constants).R(center); sc.disks.append(Disk(np.zeros(3), R_c, center, 'body', center)); sc.focus_name = center
    # perturbing bodies' paths during the run
    if eph is not None and res.samples:
        jd0 = min(float(s['jd'][0]) for s in res.samples.values() if len(s['jd'])); jd1 = max(float(s['jd'][-1]) for s in res.samples.values() if len(s['jd']))
        for p in m.propagators:
            if p.dynamics in ('selected_nbody', 'solar_system') or p.dynamics == 'cr3bp':
                names = p.gravity[:] if p.dynamics != 'cr3bp' else [p.cr3bp_secondary]
                for b in names:
                    if b == center or b not in getattr(eph, 'bodies', ()): continue
                    jds = np.linspace(jd0, max(jd1, jd0 + 1e-6), 120)
                    B = np.array([eph.state(b, TU.utc_to_tdb(j), center)[0] for j in jds])
                    if np.max(np.abs(B)) < 60 * ext:                                 # only draw bodies that fit the picture
                        sc.polys.append(Poly(B, b, 'muted', True, 1.0, 0.5)); sc.pts.append(Pt(B[-1], b, 'ink2', 'o', 6)); allp.append(B)
    sc.is3d = bool(allv.size) and bool(np.max(np.abs(allv[:, 2])) > 1e-6 * ext)
    return sc


LAST_RUN: dict = {}                                 # key (the mission as JSON) -> RunResult, so the node planner does not re-run the mission for every slider move


def run_mission(d: dict, opts: dict, scene_payload, eph, progress=None, refs: list | None = None) -> dict:
    m = Mission.from_dict(d); consts = ConstantSet(m.constants); conv = Convention.of(opts.get('convention', 'course'))
    try:
        res = run(m, eph, consts, progress)
    except (MissionError, ValueError, KeyError, ZeroDivisionError, np.linalg.LinAlgError) as ex:
        return dict(error=f'{type(ex).__name__}: {ex}')
    LAST_RUN.clear(); LAST_RUN.update(key=json.dumps(d, sort_keys=True, default=str), res=res)
    try:
        sc = build_scene(m, res, eph, opts.get('theme', 'dark'), refs); scene = scene_payload('main', sc, opts.get('theme', 'dark'), opts.get('name', ''), not opts.get('skip3d'), opts)
    except Exception as ex:
        scene = dict(name='main', svg='', html3d='', overlaps=0, has_anim=False, notes=[f'the figure could not be drawn: {ex}'], is3d=False)
    try: space = space_payload(m, res, eph, refs)
    except Exception as ex: space = dict(error=str(ex))
    return dict(scene=scene, space=space, events=[dict(text=e['text'], sat=e['sat'], when=TU.format_gregorian(e['jd']), kind=e['kind']) for e in res.events],
                burns=[_burn_row(b, conv) for b in res.burns], reports={k: _report_payload(v, conv) for k, v in res.reports.items()}, final=_final_rows(m, res, eph, conv),
                warnings=res.warnings, ref_diff=_ref_diffs(res, refs or [], eph, m), ephemeris=getattr(eph, 'name', 'none'), ephemeris_accuracy=getattr(eph, 'accuracy', ''), convention=conv.value)


def _burn_row(b: dict, conv: Convention) -> dict:
    e = b['E']; row = dict(sat=b['sat'], burn=b['burn'], when=TU.format_gregorian(b['jd']), dv=b['dv'], inertial=b['dv_vec'], vnb=e, alpha=b['alpha'], beta=b['beta'])
    row['note'] = ('GMAT VNB Element1..3 shown; course form: Δv, α, β' if conv is Convention.GMAT else 'course form (Δv, α, β in VNC); GMAT Element1..3 = V, N, B components')
    return row


def _report_payload(r: dict, conv: Convention) -> dict:
    rows = [[(x if not isinstance(x, (float, np.floating)) else float(x)) for x in row] for row in r['rows']]
    return dict(columns=r['columns'], units=r.get('units', []), rows=rows, filename=r.get('filename', ''), precision=r.get('precision', 8))


def _final_rows(m: Mission, res: RunResult, eph, conv: Convention) -> list:
    consts = ConstantSet(m.constants); out = []
    for name, st in res.final.items():
        ctx = P.ParamContext(st.central, st.r, st.v, st.jd, st.jd_start, consts, eph)
        row = dict(sat=name, central=st.central, epoch=TU.format_gregorian(st.jd), elapsed=(st.jd - st.jd_start) * 86400.0)
        vals = {k: P.evaluate(f'{name}.{st.central}.{k}', ctx) for k in ('SMA', 'ECC', 'INC', 'RAAN', 'AOP', 'TA', 'RMAG', 'VMAG', 'VFPA', 'HFPA', 'Energy', 'C3Energy')}
        if conv is Convention.COURSE:
            vals['TA'] = (vals['TA'] + 180) % 360 - 180; vals['gamma'] = vals['HFPA']
        row['values'] = {k: float(v) for k, v in vals.items()}; out.append(row)
    return out


def compare(d: dict, eph, consts_mode: str = 'Course table') -> dict:
    """Course analytic (Kepler, exact) vs the mission's own propagation: final-state differences. A GMAT column is filled by ``gmat.runner`` when configured."""
    m = Mission.from_dict(d); consts = ConstantSet(m.constants)
    exact = Mission.from_dict(d)
    for p in exact.propagators: p.integrator = 'Kepler (analytic)'; p.dynamics = 'two_body'
    try:
        ra = run(exact, eph, consts); rb = run(m, eph, consts)
    except (MissionError, ValueError) as ex:
        return dict(error=str(ex))
    rows = []
    for name in ra.final:
        a, b = ra.final[name], rb.final[name]; ca = P.ParamContext(a.central, a.r, a.v, a.jd, a.jd_start, consts, eph); cb = P.ParamContext(b.central, b.r, b.v, b.jd, b.jd_start, consts, eph)
        for k, label, unit in (('SMA', 'a', 'km'), ('ECC', 'e', ''), ('INC', 'i', '°'), ('RMAG', 'r', 'km'), ('VMAG', 'v', 'km/s'), ('VFPA', 'VFPA', '°'), ('TA', 'TA', '°')):
            try: va = float(P.evaluate(f'{name}.{a.central}.{k}', ca)); vb = float(P.evaluate(f'{name}.{b.central}.{k}', cb))
            except ValueError: continue
            diff = vb - va
            if k == 'TA': diff = (diff + 180) % 360 - 180
            rows.append(dict(sat=name, quantity=label, unit=unit, calculated=va, propagated=vb, diff=diff, gmat=None))
        rows.append(dict(sat=name, quantity='epoch (s since start)', unit='s', calculated=(a.jd - a.jd_start) * 86400, propagated=(b.jd - b.jd_start) * 86400, diff=(b.jd - a.jd) * 86400, gmat=None))
    pos = {name: float(np.linalg.norm(ra.final[name].r - rb.final[name].r)) for name in ra.final}
    return dict(rows=rows, position_difference_km=pos, model=', '.join(f'{p.name}: {DYNAMICS_LABEL.get(p.dynamics, p.dynamics)} / {p.integrator}' for p in m.propagators),
                note='"Calculated" always uses the exact two-body (Kepler) solution; "Propagated" uses the propagators defined in the mission.')


# ---------------------------------------------------------------------------------------------------------------------------------
# files
# ---------------------------------------------------------------------------------------------------------------------------------
def report_csv(rep: dict) -> str:
    b = io.StringIO(); w = csv.writer(b); w.writerow(rep['columns'])
    for row in rep['rows']: w.writerow(row)
    return b.getvalue()


def report_table(rep: dict) -> str:
    """GMAT-style fixed-width text table."""
    cols = rep['columns']; rows = [[(f'{x:.{int(rep.get("precision", 8))}g}' if isinstance(x, float) else str(x)) for x in r] for r in rep['rows']]
    wid = [max(len(c), *(len(r[i]) for r in rows)) if rows else len(c) for i, c in enumerate(cols)]
    line = lambda cells: '  '.join(c.ljust(w) for c, w in zip(cells, wid))
    return '\n'.join([line(cols)] + [line(r) for r in rows]) + '\n'


def trajectory_csv(res: RunResult, sat: str) -> str:
    b = io.StringIO(); w = csv.writer(b); sm = res.samples[sat]; w.writerow(['UTC', 'JD_UTC', 'centre', 'X_km', 'Y_km', 'Z_km', 'VX_kms', 'VY_kms', 'VZ_kms'])
    for jd, r, v, c in zip(sm['jd'], sm['r'], sm['v'], sm['central']): w.writerow([TU.format_gregorian(jd), f'{jd:.9f}', c, *[f'{x:.9f}' for x in r], *[f'{x:.12f}' for x in v]])
    return b.getvalue()


def trajectory_oem(res: RunResult, sat: str) -> str:
    """CCSDS Orbit Ephemeris Message 2.0 (EME2000, UTC), km and km/s, one segment per central body."""
    import datetime as dt
    sm = res.samples[sat]; iso = lambda jd: TU.format_gregorian(jd)
    def t(jd):
        Y, M, D, h, mi, s_ = TU.jd_to_calendar(jd); return f'{Y:04d}-{M:02d}-{D:02d}T{h:02d}:{mi:02d}:{min(s_, 59.9999):07.4f}'
    out = ['CCSDS_OEM_VERS = 2.0', f'CREATION_DATE = {dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")}', 'ORIGINATOR = ORBIT SIMULATOR', '']
    segs = []; cur = None
    for i, c in enumerate(sm['central']):
        if cur is None or c != cur[0]: cur = [c, []]; segs.append(cur)
        cur[1].append(i)
    for c, idx in segs:
        out += ['META_START', f'OBJECT_NAME = {sat}', f'OBJECT_ID = {sat}', f'CENTER_NAME = {c.upper()}', 'REF_FRAME = EME2000', 'TIME_SYSTEM = UTC', f'START_TIME = {t(sm["jd"][idx[0]])}', f'STOP_TIME = {t(sm["jd"][idx[-1]])}', 'META_STOP', '']
        for i in idx: out.append(f'{t(sm["jd"][i])} ' + ' '.join(f'{x:.9f}' for x in (*sm['r'][i], *sm['v'][i])))
        out.append('')
    return '\n'.join(out)


def _ref_diffs(res: RunResult, refs: list, eph, m: Mission) -> list:
    """Position difference between each imported trajectory and the first spacecraft, at the reference epochs (both about the reference's own center)."""
    from .trajectory_io import compare_with
    out = []
    if not res.samples or not refs: return out
    name = next(iter(res.samples)); sm = res.samples[name]
    if not len(sm['jd']): return out
    jd = np.array(sm['jd']); R = np.array(sm['r'])
    for ref in refs:
        try:
            Rc = R.copy()
            for i, c in enumerate(sm['central']):
                if c != ref['center']:
                    if eph is None: raise ValueError('needs an ephemeris')
                    Rc[i] = R[i] + eph.state(c, TU.utc_to_tdb(jd[i]), ref['center'])[0]
            d = compare_with(ref, jd, Rc); d['name'] = ref['name']; out.append(d)
        except Exception as ex: out.append(dict(name=ref['name'], points=0, error=str(ex)))
    return out


BODY_COLOR = {'Sun': '#ffd27a', 'Mercury': '#a79d93', 'Venus': '#e0c28b', 'Earth': '#4c8df6', 'Moon': '#bdbdbd', 'Mars': '#d1603d', 'Jupiter': '#d8b18c', 'Saturn': '#e3d3a2',
              'Uranus': '#9fd6e0', 'Neptune': '#5a7fe0', 'Pluto': '#c9b9a8'}


def _thin(n: int, cap: int) -> np.ndarray:
    return np.unique(np.linspace(0, n - 1, min(n, cap)).astype(int))


def space_payload(m: Mission, res: RunResult, eph, refs: list | None = None, cap: int = 1500) -> dict:
    """Everything the three.js space view needs: tracks and bodies about the display center (km, ICRF axes), times as UTC Julian dates."""
    from ..view3d.models import TEXTURES
    from .patched import soi as soi_of, PARENT
    consts = ConstantSet(m.constants); center = next((p.central for p in m.propagators), 'Earth')
    tracks = []; jd0 = np.inf; jd1 = -np.inf; ext = 1.0
    traj = _recentre_samples(res, center, eph, True)
    for i, (name, (jd, R, seg)) in enumerate(traj.items()):
        k = _thin(len(jd), cap); col = next((s.color for s in m.spacecraft if s.name == name), PALETTE[i % len(PALETTE)])
        sm_ = res.samples[name]; tracks.append(dict(name=name, color=col, jd=jd[k].tolist(), r=R[k].tolist(), idx=k.tolist(), cmd=[sm_['cmd'][i] for i in k], tc=[round(sm_['tc'][i], 3) for i in k])); jd0 = min(jd0, jd[0]); jd1 = max(jd1, jd[-1]); ext = max(ext, float(np.max(np.abs(R))))
    if not tracks: return dict(markers=[], tracks=[], bodies=[], jd0=0, jd1=1, center=center, extent=1, events=[], lagrange=[], refs=[])
    names = []                                                                                      # bodies worth drawing: the center, whatever the propagators or views mention, and the Sun
    for p in m.propagators:
        names += [p.central] + list(p.gravity) + ([p.cr3bp_primary, p.cr3bp_secondary] if p.dynamics == 'cr3bp' else [])
    for v in m.views: names += [o for o in (c if c != 'Luna' else 'Moon' for c in v.objects) if o in BODIES]
    if eph is not None and any(p.dynamics in ('selected_nbody', 'solar_system', 'patched') for p in m.propagators): names.append('Sun')
    names = [center] + [n for n in dict.fromkeys(names) if n in BODIES and n != center]
    bodies = []; jds = np.linspace(jd0, max(jd1, jd0 + 1e-6), 160)
    patched = any(p.dynamics == 'patched' for p in m.propagators)
    for n in names:
        b = dict(name=n, R=consts.R(n), texture=TEXTURES.get(n), clouds=cloud_map(n), cloud_kind='opaque' if n in CLOUD_OPAQUE else 'alpha', dust=(n == 'Mars'), color=BODY_COLOR.get(n, '#8aa0c8'), spin=spin_for(n))
        if n != center:
            if eph is None or n not in getattr(eph, 'bodies', ()): continue
            B = np.array([eph.state(n, TU.utc_to_tdb(j), center)[0] for j in jds]); b['path'] = dict(jd=jds.tolist(), r=B.tolist())
            if n in PARENT and (patched or n == 'Moon'): b['soi'] = float(soi_of(n, consts, eph, TU.utc_to_tdb(jd0)))
        bodies.append(b)
    ev = []
    for e in res.events:
        if e['sat'] in traj:
            jd, R, _ = traj[e['sat']]; k = int(np.argmin(np.abs(jd - e['jd']))); ev.append(dict(jd=float(e['jd']), r=R[k].tolist(), kind=e['kind'], text=e['text']))
    lagr = []
    for p in m.propagators:
        if p.dynamics == 'cr3bp' and eph is not None:
            try: lagr = _lagrange_paths(p, consts, eph, jd0, jd1, center)
            except Exception: lagr = []
    from .. import sky as SK
    markers = [dict(name='Galactic Center', ra=SK.GALACTIC_CENTER[0], dec=SK.GALACTIC_CENTER[1]), dict(name='North Galactic Pole', ra=SK.NORTH_GALACTIC_POLE[0], dec=SK.NORTH_GALACTIC_POLE[1])] + [dict(name=k, ra=r_, dec=d_) for k, (r_, d_) in SK.STARS.items()]
    from ..view3d.models import spacecraft_mesh
    return dict(models={k: spacecraft_mesh(k) for k in ('comsat', 'probe')}, markers=markers, center=center, jd0=float(jd0), jd1=float(jd1), tracks=tracks, bodies=bodies, events=ev, lagrange=lagr, extent=ext,
                refs=[dict(name=r_['name'], r=[x for x in np.array(r_['r'])[_thin(len(r_['r']), cap)].tolist()]) for r_ in (refs or []) if r_.get('center') == center])


CLOUD_FILES = {'Earth': '2k_earth_clouds.jpg', 'Venus': '2k_venus_atmosphere.jpg'}
CLOUD_OPAQUE = {'Venus'}                    # Venus's cloud deck hides the whole surface: an opaque shell over the radar map, not a see-through cloud mask like the Earth's


def cloud_map(name: str):
    """The cloud layer texture of a body (the Earth's cloud mask and Venus's opaque cloud deck), or None when the image is not installed."""
    from ..view3d.models import assets_dir
    f = CLOUD_FILES.get(name); return f if f and (assets_dir() / f).exists() else None


PERIOD_DAYS = {'Mercury': 87.97, 'Venus': 224.70, 'Earth': 365.256, 'Mars': 686.98, 'Jupiter': 4332.59, 'Saturn': 10759.2, 'Uranus': 30688.5, 'Neptune': 60182.0, 'Pluto': 90560.0}


def solar_payload(eph, jd0: float, days: float, center: str = 'Sun', ring_points: int = 361, tracks: list | None = None, track_center: str | None = None, events: list | None = None) -> dict:
    """The real Solar System for the space view, with no mission: every body of the ephemeris (positions from DE440s or the built-in model, true radii) about ``center`` over
    [jd0, jd0 + days] (UTC Julian dates). A mission's tracks (positions about ``track_center``) can be laid over it: each sample is shifted by the position of that body about ``center`` at the sample time. When the center is the Sun each planet also gets a full-orbit ring, so the outer planets show their whole orbit, not just the arc of the time window."""
    from ..view3d.models import TEXTURES, spacecraft_mesh
    consts = ConstantSet('Course table'); days = float(max(1.0, min(days, 73050.0)))
    avail = [b for b in getattr(eph, 'bodies', ()) if b in BODIES]
    if center not in avail: center = 'Sun' if 'Sun' in avail else avail[0]
    n = int(min(5000, max(400, days / 0.5))); jds = np.linspace(jd0, jd0 + days, n); tdb = [TU.utc_to_tdb(j) for j in jds]
    names = [center] + [b for b in avail if b != center]; bodies = []; ext = 1.0
    for nm in names:
        b = dict(name=nm, R=consts.R(nm), mu=consts.mu(nm), texture=TEXTURES.get(nm), clouds=cloud_map(nm), cloud_kind='opaque' if nm in CLOUD_OPAQUE else 'alpha', dust=(nm == 'Mars'), color=BODY_COLOR.get(nm, '#8aa0c8'), spin=spin_for(nm), kind='star' if nm == 'Sun' else 'moon' if nm == 'Moon' else 'planet')
        if nm != center:
            B = np.array([eph.state(nm, t, center)[0] for t in tdb]); b['path'] = dict(jd=jds.tolist(), r=B.tolist()); ext = max(ext, float(np.max(np.linalg.norm(B, axis=1))))
            if nm == 'Moon' and center != 'Moon' and 'Earth' in avail: b['parent'] = 'Earth'
            if center == 'Sun' and nm in PERIOD_DAYS:                                           # the whole orbit as a static ring (the window may cover only a small arc of it)
                try:
                    pj = np.linspace(jd0, jd0 + PERIOD_DAYS[nm], ring_points); b['ring'] = [eph.state(nm, TU.utc_to_tdb(j), 'Sun')[0].tolist() for j in pj]
                except Exception: pass
        bodies.append(b)
    def shift(jd_list, R):                                  # mission-center-relative positions -> positions about the view center
        if not track_center or track_center == center or track_center not in avail: return np.asarray(R, float)
        off = np.array([eph.state(track_center, TU.utc_to_tdb(j), center)[0] for j in jd_list]); return np.asarray(R, float) + off
    out_tracks = []
    for t in tracks or []:
        R = shift(t['jd'], t['r']); out_tracks.append({**t, 'r': R.tolist()}); ext = max(ext, float(np.max(np.linalg.norm(R, axis=1))))
    out_events = []
    for e in events or []:
        out_events.append({**e, 'r': shift([e['jd']], [e['r']])[0].tolist()})
    from .. import sky as SK
    markers = [dict(name='Galactic Center', ra=SK.GALACTIC_CENTER[0], dec=SK.GALACTIC_CENTER[1]), dict(name='North Galactic Pole', ra=SK.NORTH_GALACTIC_POLE[0], dec=SK.NORTH_GALACTIC_POLE[1])]
    return dict(models={k: spacecraft_mesh(k) for k in ('comsat', 'probe')}, markers=markers, center=center, jd0=float(jds[0]), jd1=float(jds[-1]), tracks=out_tracks, bodies=bodies, events=out_events, lagrange=[], extent=ext, refs=[])


def _lagrange_paths(p: Propagator, consts: ConstantSet, eph, jd0: float, jd1: float, center: str) -> list:
    """L1-L5 of the circular restricted problem as moving points in the display frame (centered on the primary when the display center is the primary)."""
    from ..dyn.models import CR3BP
    mu1, mu2 = consts.mu(p.cr3bp_primary), consts.mu(p.cr3bp_secondary)
    rs, vs = eph.state(p.cr3bp_secondary, TU.utc_to_tdb(jd0), p.cr3bp_primary); L = float(np.linalg.norm(rs)); sys_ = CR3BP.from_bodies(mu1, mu2, L); T = sys_.T
    ex = rs / L; ez = np.cross(rs, vs); ez /= np.linalg.norm(ez); ey = np.cross(ez, ex); Rm = np.array([ex, ey, ez]); pts = sys_.lagrange_points(); jds = np.linspace(jd0, max(jd1, jd0 + 1e-6), 120); out = []
    for name, rot in pts.items():
        path = []
        for j in jds:
            t = (j - jd0) * 86400.0 / T; c, s_ = np.cos(t), np.sin(t); R = np.array([[c, -s_, 0], [s_, c, 0], [0, 0, 1]])
            rin = (R @ rot) * L - sys_.mu * L * np.array([c, s_, 0]); path.append((Rm.T @ rin).tolist())
        out.append(dict(name=name, jd=jds.tolist(), r=path))
    return out


# ---------------------------------------------------------------------------------------------------------------- maneuver-node planner
def _cached_run(d: dict, eph) -> tuple[Mission, RunResult]:
    m = Mission.from_dict(d); key = json.dumps(d, sort_keys=True, default=str)
    if LAST_RUN.get('key') == key: return m, LAST_RUN['res']
    res = run(m, eph, ConstantSet(m.constants)); LAST_RUN.clear(); LAST_RUN.update(key=key, res=res); return m, res


def _elements(mu: float, r, v) -> dict:
    k = P.keplerian(mu, np.asarray(r), np.asarray(v)); return {n: (None if not np.isfinite(k[n]) else float(k[n])) for n in ('SMA', 'ECC', 'INC', 'RAAN', 'AOP', 'TA', 'RadPer', 'RadApo', 'OrbitPeriod', 'VMAG', 'RMAG')}


def preview_node(d: dict, eph, sat: str, idx: int, e: list, length_s: float | None = None, cap: int = 600) -> dict:
    """Where would the spacecraft go if it burned (E1, E2, E3 in VNB, km/s) at sample ``idx`` of its trajectory? Returns the predicted path and the new elements."""
    m, res = _cached_run(d, eph); consts = ConstantSet(m.constants); sm = res.samples[sat]; idx = int(max(0, min(len(sm['jd']) - 1, idx)))
    central = sm['central'][idx]; jd = float(sm['jd'][idx]); r = np.array(sm['r'][idx]); v = np.array(sm['v'][idx]); mu = consts.mu(central)
    prop = next((Propagator(**{**p.__dict__, 'name': 'PropPreview'}) for p in m.propagators if p.central == central), None) or Propagator('PropPreview', central, 'two_body', [central], 'RungeKutta89')
    cs = 'EarthMJ2000Eq' if central == 'Earth' else f'{"Luna" if central == "Moon" else central}MJ2000Eq'
    pm = Mission(name='preview', constants=m.constants); pm.coords = [] if cs == 'EarthMJ2000Eq' else [CoordSys(cs, central, 'MJ2000Eq')]
    pm.spacecraft = [Spacecraft('Sat', 'UTCModJulian', repr(float(TU.jd_to_modjulian(jd))), cs, 'Cartesian', dict(X=r[0], Y=r[1], Z=r[2], VX=v[0], VY=v[1], VZ=v[2]))]
    pm.propagators = [prop]; pm.burns = [Burn('Node', central, 'VNB', float(e[0]), float(e[1]), float(e[2]))]
    from .run import _maneuver_dv
    dvec = _maneuver_dv(pm.burns[0], r, v, mu); after = _elements(mu, r, v + dvec); before = _elements(mu, r, v)
    L = length_s if length_s else (min(after['OrbitPeriod'], 400 * 86400.0) if after['OrbitPeriod'] and after['ECC'] < 1 else 10 * 86400.0)
    pm.commands = [Command('Maneuver', burn='Node', sat='Sat'), Command('Propagate', items=[['PropPreview', ['Sat']]], stops=[f'Sat.ElapsedSecs = {float(max(L, 60.0))!r}'])]
    try: pr = run(pm, eph, consts)
    except Exception as ex: return dict(ok=False, error=f'{type(ex).__name__}: {ex}')
    center = next((q.central for q in m.propagators), central); traj = _recentre_samples(pr, center, eph, True)
    jdp, R, _ = traj['Sat']; k = _thin(len(jdp), cap); node_r = np.array(sm['r'][idx])
    if central != center and eph is not None: node_r = node_r + eph.state(central, TU.utc_to_tdb(jd), center)[0]
    return dict(ok=True, path=dict(jd=jdp[k].tolist(), r=R[k].tolist()), node=dict(jd=jd, r=node_r.tolist()), before=before, after=after, dv=float(np.linalg.norm(dvec)), central=central,
                elapsed=float(sm['tc'][idx]), command=int(sm['cmd'][idx]), length_s=float(L), epoch=TU.format_gregorian(jd))


def insert_node(d: dict, eph, sat: str, idx: int, e: list) -> dict:
    """Turn the node into real commands: the Propagate that contains the sample is split there, and a Maneuver (a new VNB burn) is inserted."""
    import copy
    m, res = _cached_run(d, eph); sm = res.samples[sat]; idx = int(max(0, min(len(sm['jd']) - 1, idx))); ci = int(sm['cmd'][idx]); tc = float(sm['tc'][idx]); central = sm['central'][idx]
    n = 1
    while any(b.name == f'Node{n}' for b in m.burns): n += 1
    name = f'Node{n}'; m.burns.append(Burn(name, central, 'VNB', float(e[0]), float(e[1]), float(e[2]))); man = Command('Maneuver', burn=name, sat=sat); cmd = m.commands[ci]
    if cmd.kind == 'Maneuver': m.commands.insert(ci + 1, man)
    elif cmd.kind == 'Propagate':
        if tc < 1e-6: m.commands.insert(ci, man)
        else:
            first = copy.deepcopy(cmd); first.stops = [f'{sat}.ElapsedSecs = {tc!r}']; rest = copy.deepcopy(cmd); new = []
            for st in rest.stops:
                mt = re.match(r'^(\w+)\.(ElapsedSecs|ElapsedDays)\s*=\s*([-+0-9.eE]+)$', st.strip())
                if mt:
                    val = float(mt.group(3)) - (tc if mt.group(2) == 'ElapsedSecs' else tc / 86400.0); new.append(f'{mt.group(1)}.{mt.group(2)} = {max(val, 1e-6)!r}')
                else: new.append(st)
            rest.stops = new; m.commands[ci:ci + 1] = [first, man, rest]
    else: raise ValueError('a node can only be placed on a propagation or a maneuver')
    m.notes = list(m.notes) + [f'{name}: E1 = {e[0]:.6f}, E2 = {e[1]:.6f}, E3 = {e[2]:.6f} km/s (VNB) at {TU.format_gregorian(sm["jd"][idx])}']
    return m.to_dict()
