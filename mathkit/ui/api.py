"""JSON API behind the desktop UI. Pure functions: dict in -> dict out (everything JSON-serialisable)."""
from __future__ import annotations
import io
import pathlib
import threading
import traceback
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from ..core.constants import BODIES, EXAM, AU, ConstantSet
from ..core.timeutil import calendar_to_jd, jd_to_calendar, weekday_name, et_to_ut
from ..registry import MODULES, Field
from ..presets.hw_problems import PRESETS
from ..presets.runner import run_preset, all_presets, defaults
from ..plots2d.render import render
from ..view3d.animate import build_html
from ..results import Result, Step
from ..conventions import Convention, present_step
from .present import summary_cards, extra_tabs
from ..theme import apply_palette
from . import shell, backup

VERSION = '1.0.0'
LOCK = threading.Lock()                 # matplotlib is not thread-safe
LAST: dict = {}                         # last solved result (for exports)
PLOTLY_SRC = '/static/plotly.min.js'


def _jsonable(o):
    if isinstance(o, dict): return {k: _jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)): return [_jsonable(v) for v in o]
    if isinstance(o, np.ndarray): return o.tolist()
    if isinstance(o, (np.floating, np.integer)): return o.item()
    if isinstance(o, np.bool_): return bool(o)
    return o


def field_json(f: Field) -> dict:
    return dict(key=f.key, label=f.label, kind=f.kind, default=_jsonable(f.default), options=f.options, dist=f.dist, unit=f.unit, rng=f.rng)


def meta() -> dict:
    mods = []
    for m in MODULES.values():
        mods.append(dict(id=m.id, title=m.title, short=m.short, blurb=m.blurb, body_key=m.body_key, fields=[field_json(f) for f in m.fields],
                         presets=[dict(label=p.label, vals=_jsonable(p.vals), consts=p.consts, moon_R=p.moon_R, note=p.note) for p in PRESETS.get(m.id, [])]))
    return dict(version=VERSION, modules=mods, AU=AU, paths=shell.paths(), can_window=shell.has_window(), settings=shell.load_settings(),
                bodies={n: dict(b, a=b.get('a'), e=b.get('e')) for n, b in BODIES.items()},
                exam={n: b for n, b in EXAM.items()})


def _vals(mid: str, raw: dict) -> dict:
    spec = MODULES[mid]; v = defaults(spec); v.update(raw or {})
    return v


def visible(p: dict) -> dict:
    spec = MODULES[p['mid']]; v = _vals(p['mid'], p.get('vals')); out = []
    for f in spec.fields:
        try: ok = True if f.show_if is None else bool(f.show_if(v))
        except Exception: ok = True
        if ok: out.append(f.key)
    return dict(visible=out)


def _scene_payload(name, sc, theme, user, with_3d=True, opts=None):
    opts = opts or {}
    fig = render(sc, theme, user, figsize=(6.4, 6.1), body=opts.get('body', 'symbol'))
    buf = io.StringIO(); fig.savefig(buf, format='svg', facecolor=fig.get_facecolor()); svg = buf.getvalue()
    overlaps = getattr(fig, 'label_overlaps', 0); plt.close(fig)
    svg = svg[svg.index('<svg'):]
    html = build_html(sc, theme, user, plotlyjs=PLOTLY_SRC, body=opts.get('body', 'symbol'), n_frames=int(opts.get('frames', 480)), textures=bool(opts.get('textures')), model=opts.get('model', 'marker'), show_fps=bool(opts.get('fps')), repeat=bool(opts.get('repeat', True))) if with_3d else ''
    return dict(name=name, svg=svg, html3d=html, overlaps=overlaps, has_anim=bool(sc.tracks), notes=list(sc.notes), is3d=bool(sc.is3d))


PROGRESS = dict(stage='', frac=0.0, seq=0)


def _prog(stage: str, frac: float):
    PROGRESS.update(stage=stage, frac=frac)


def progress(p: dict) -> dict:
    return dict(PROGRESS)


def _nonfinite(res) -> list[str]:
    """Names of result values that came out NaN or infinite (a sign the inputs are outside the solver's domain)."""
    bad = []
    for st in res.steps:
        v = st.value
        try:
            arr = np.asarray(v, dtype=float)
        except (TypeError, ValueError):
            continue
        if arr.size and not np.all(np.isfinite(arr)): bad.append(st.name)
    return bad


def solve(p: dict) -> dict:
    mid = p['mid']; spec = MODULES[mid]; vals = _vals(mid, p.get('vals')); theme = p.get('theme', 'dark'); user = p.get('name', '')
    vals['_label'] = p.get('label') or f'Module {mid}'
    c = p.get('consts') or {}; C = ConstantSet(c.get('mode', 'Course table'), float(c.get('moon_R', 2000.0)))
    problems: list[str] = []
    with LOCK:
        apply_palette((p.get('opts') or {}).get('palette', 'prussian'))
        _prog('solving the equations', 0.08)
        try:
            res: Result = spec.run(vals, C)
        except (ValueError, ZeroDivisionError, KeyError, np.linalg.LinAlgError, OverflowError, FloatingPointError) as ex:
            _prog('', 1.0)
            return dict(error=f'Could not solve with these inputs: {ex}', fatal=True)
        except Exception:
            _prog('', 1.0)
            return dict(error='Unexpected error', trace=traceback.format_exc(), fatal=True)
        bad = _nonfinite(res)
        if bad: problems.append('these values are not finite numbers: ' + ', '.join(bad[:6]) + ('…' if len(bad) > 6 else ''))
        try:
            opts = p.get('opts') or {}
            names = ['main'] + list(res.scenes)
            scs = [res.scene] + list(res.scenes.values())
            scenes = []
            for i, (nm, sc) in enumerate(zip(names, scs)):
                _prog('drawing the 2d figure' + (' and the 3d view' if not opts.get('skip3d') else ''), 0.3 + 0.6 * i / len(scs))
                scenes.append(_scene_payload(nm, sc, theme, user, not opts.get('skip3d'), opts))
            extra_figs = []
            for k, f in res.figs.items():
                fig = f(theme, user); b = io.StringIO(); fig.savefig(b, format='svg', facecolor=fig.get_facecolor()); plt.close(fig)
                extra_figs.append(dict(name=k, svg=b.getvalue()[b.getvalue().index('<svg'):]))
        except Exception as ex:
            plt.close('all'); trace = traceback.format_exc()
            problems.append(f'the figures could not be drawn ({type(ex).__name__}: {ex}); the numbers and steps are still available')
            scenes = [dict(name='main', svg='', html3d='', overlaps=0, has_anim=False, notes=[], is3d=False)]; extra_figs = []
        _prog('done', 1.0)
        LAST.clear(); LAST.update(vals=dict(vals), consts_mode=C.mode, palette=(p.get('opts') or {}).get('palette', 'prussian'), res=res, name=user, label=vals['_label'], mid=mid, body=(p.get('opts') or {}).get('body', 'symbol'))
    conv = Convention.of((p.get('opts') or {}).get('convention', 'course'))
    groups = []
    for g in dict.fromkeys(s.group for s in res.steps):
        rows = []
        for s in (x for x in res.steps if x.group == g):
            for nm, sym, val, un, note in present_step(s.name, s.symbol, s.value, s.units, conv):
                unchanged = (nm == s.name and sym == s.symbol and val is s.value)
                rows.append([nm, sym, s.display() if unchanged else Step(nm, sym, val, un).display(), un, s.equation if unchanged else '', note or (s.note if unchanged else '')])
        groups.append(dict(name=g, rows=rows))
    return dict(title=res.title, label=res.label, warnings=res.warnings, checks=res.checks, groups=groups, scenes=scenes, figs=extra_figs,
                cards=summary_cards(mid, res), tabs=extra_tabs(mid, res), inputs=_jsonable(res.inputs), problems=problems, convention=conv.value)


def export(idx: int, fmt: str, theme: str = 'light'):
    """Render the idx-th scene of the last result for download. Returns (bytes, mimetype, filename)."""
    if not LAST: raise ValueError('nothing solved yet')
    apply_palette(LAST.get('palette', 'prussian'))
    res: Result = LAST['res']; scenes = [('main', res.scene)] + list(res.scenes.items()); name, sc = scenes[idx]
    stem = ((LAST['name'] + '_') if LAST['name'] else '') + LAST['label'].replace(' ', '_') + ('' if name == 'main' else '_' + name.split()[0])
    with LOCK:
        if fmt == 'html': return build_html(sc, theme, LAST['name'], plotlyjs='cdn', body=LAST.get('body', 'symbol')).encode('utf-8'), 'text/html', stem + '_3D.html'
        if fmt == 'script':
            from ..mission.from_module import from_module
            from ..gmat.export import export_script
            m = from_module(LAST['mid'], LAST['vals'], res, ConstantSet(LAST.get('consts_mode', 'Course table')))
            return export_script(m).encode('utf-8'), 'text/plain', stem + '.script'
        if fmt in ('py', 'm'):
            from . import codegen
            title = (LAST['name'] + ' — ' if LAST['name'] else '') + f'{sc.label}: {sc.title}'; fname = codegen.safe_name(stem) + '_plots.' + fmt
            gen = codegen.python_script if fmt == 'py' else codegen.matlab_script
            code = gen(sc, title, theme, LAST.get('body', 'symbol'), res.inputs, fname)
            return code.encode('utf-8'), ('text/x-python' if fmt == 'py' else 'text/plain'), fname
        fig = render(sc, theme, LAST['name'], body=LAST.get('body', 'symbol')); buf = io.BytesIO()
        fig.savefig(buf, format=fmt, dpi=300, bbox_inches='tight', facecolor=fig.get_facecolor()); plt.close(fig)
    return buf.getvalue(), ('image/png' if fmt == 'png' else 'application/pdf'), f'{stem}.{fmt}'


# ------------------------------------------------------------------------------------------------ Mission workspace
MPROG = dict(stage='', frac=0.0)


def _settings() -> dict:
    try: return shell.load_settings()
    except Exception: return {}


def _eph():
    from ..ephem import get_provider
    st = _settings(); return get_provider(st.get('ephemPath') or None, 'analytic' if st.get('ephemMode') == 'analytic' else 'auto')


def mission_meta(p: dict) -> dict:
    from ..mission import service as MS
    from ..mission.model import INTEGRATORS, DYNAMICS_LABEL
    from ..mission import params as MP
    e = _eph(); return dict(starters=list(MS.STARTERS), integrators=list(INTEGRATORS), dynamics=DYNAMICS_LABEL, bodies=list(BODIES), params=list(MP.ALL_PARAMS), units=MP.UNITS,
                            ephemeris=dict(name=e.name, accuracy=e.accuracy, bodies=list(getattr(e, 'bodies', ()))), kernel=_kernel_status())


def mission_starter(p: dict) -> dict:
    from ..mission import service as MS
    return dict(mission=MS.starter(p['name']).to_dict())


def mission_run(p: dict) -> dict:
    from ..mission import service as MS
    opts = dict(p.get('opts') or {}); opts['theme'] = p.get('theme', 'dark')
    with LOCK:
        apply_palette(opts.get('palette', 'prussian'))
        MPROG.update(stage='starting', frac=0.0)
        out = MS.run_mission(p['mission'], opts, lambda n, sc, th, u, w3, o: _scene_payload(n, sc, th, u, w3, o), _eph(), lambda s, f: MPROG.update(stage=s, frac=f), p.get('refs') or [])
        MPROG.update(stage='done', frac=1.0)
    return out


def mission_progress(p: dict) -> dict: return dict(MPROG)


def mission_convert(p: dict) -> dict:
    """Convert one spacecraft's state between Cartesian and Keplerian (live sync in the editor)."""
    from ..mission.model import Mission
    from ..mission import run as MR, params as MP
    try:
        m = Mission.from_dict(p['mission']); sc = m.spacecraft[int(p['index'])]; consts = ConstantSet(m.constants)
        cs = m.coord(sc.coord); st = MR.initial_state(m, sc, consts)
        M = MP.axes_matrix(cs.axes, cs.origin); r, v = M @ st.r, M @ st.v
        d = MP.keplerian(consts.mu(cs.origin), r, v); keys = MP.KEP_PARAMS[:6] if p['to'] == 'Keplerian' else MP.CART_PARAMS[:6]
        return dict(ok=True, state={k: float(d[k]) for k in keys})
    except Exception as ex: return dict(ok=False, error=str(ex))


def mission_compare(p: dict) -> dict:
    from ..mission import service as MS
    out = MS.compare(p['mission'], _eph())
    st = _settings(); g = st.get('gmatPath')
    if g and 'rows' in out:
        from ..gmat import runner
        from ..gmat.export import export_script
        from ..mission.model import Mission
        con = runner.find_console(g)
        if con is None: out['gmat_status'] = 'GMAT console not found in the configured folder'
        else:
            m = Mission.from_dict(p['mission']); r = runner.run_script(con, export_script(m)); out['gmat_status'] = 'GMAT ran' if r['ok'] else (r.get('error') or 'GMAT produced no report')
            if r['ok'] and m.reports:
                rows = runner.parse_report(next(iter(r['reports'].values())), m.reports[0].params)
                if rows:
                    last = rows[-1]; keymap = {'a': 'SMA', 'e': 'ECC', 'i': 'INC', 'r': 'RMAG', 'v': 'VMAG', 'VFPA': 'VFPA', 'TA': 'TA'}
                    for row in out['rows']:
                        key = keymap.get(row['quantity'])
                        for c, v in last.items():
                            if key and c.endswith('.' + key) and c.startswith(row['sat'] + '.'): row['gmat'] = v
    else: out['gmat_status'] = 'GMAT not configured'
    return out


def mission_script(p: dict) -> dict:
    from ..mission.model import Mission
    from ..gmat.export import export_script
    from ..gmat.importer import import_script
    m = Mission.from_dict(p['mission']); text = export_script(m); back = import_script(text)
    return dict(script=text, skipped=back.skipped, round_trip_commands=len(back.mission.commands) == len([c for c in m.commands if c.enabled]))


def mission_import(p: dict) -> dict:
    from ..gmat.importer import import_script
    from ..mission.model import Mission
    name = (p.get('filename') or 'Imported mission').rsplit('.', 1)[0]; txt = p['text']
    if (p.get('filename') or '').endswith('.orbitmission'):
        try: return dict(ok=True, mission=Mission.from_json(txt).to_dict(), skipped=[], notes=[])
        except Exception as ex: return dict(ok=False, error=f'not a valid .orbitmission file: {ex}')
    r = import_script(txt, name)
    if not r.mission.spacecraft and not r.mission.commands: return dict(ok=False, error='no spacecraft or mission commands were found in this script', skipped=r.skipped)
    return dict(ok=True, mission=r.mission.to_dict(), skipped=r.skipped, notes=r.notes)


def mission_from_module(p: dict) -> dict:
    from ..mission.from_module import from_module, NotAvailable
    if not LAST: return dict(ok=False, error='solve a module first')
    try: m = from_module(LAST['mid'], LAST['vals'], LAST['res'], ConstantSet(LAST.get('consts_mode', 'Course table')))
    except NotAvailable as ex: return dict(ok=False, error=str(ex))
    except Exception as ex: return dict(ok=False, error=f'could not build a mission from this result: {ex}')
    return dict(ok=True, mission=m.to_dict())


def mission_save(p: dict) -> dict:
    from ..mission.model import Mission
    from ..mission import service as MS
    try:
        m = Mission.from_dict(p['mission']); kind = p.get('kind', 'orbitmission'); stem = ''.join(c if c.isalnum() or c in '-_' else '_' for c in m.name)[:60] or 'mission'
        if kind == 'script':
            from ..gmat.export import export_script
            data, ext = export_script(m).encode('utf-8'), 'script'
        elif kind == 'orbitmission': data, ext = m.to_json().encode('utf-8'), 'orbitmission'
        elif kind in ('csv', 'txt'):
            rep = p['report']; data, ext = (MS.report_csv(rep) if kind == 'csv' else MS.report_table(rep)).encode('utf-8'), kind
            stem = ''.join(c if c.isalnum() or c in '-_' else '_' for c in rep.get('filename', 'report').rsplit('.', 1)[0]) or 'report'
        else: return dict(ok=False, error='unknown export type')
        out = shell.unique_path(shell.folder('exports'), stem, ext); out.write_bytes(data); return dict(ok=True, path=str(out))
    except Exception as ex: return dict(ok=False, error=str(ex))


def _kernel_status() -> dict:
    from .. import ephem
    k = ephem.find_kernel(_settings().get('ephemPath') or None)
    try:
        import jplephem  # noqa: F401
        have = True
    except Exception: have = False
    return dict(path=str(k) if k else '', size=k.stat().st_size if k else 0, jplephem=have, folder=str(ephem.kernel_dir()), url=ephem.DE440S_URL, expected_size=ephem.DE440S_SIZE)


KPROG = dict(done=0, total=0, state='idle', error='', sha256='')


def ephem_status(p: dict) -> dict:
    e = _eph(); return dict(kernel=_kernel_status(), progress=dict(KPROG), ephemeris=dict(name=e.name, accuracy=e.accuracy))


def ephem_download(p: dict) -> dict:
    """Download DE440s into the app data folder (only when the user clicks). Runs in a thread; poll ``ephem_status``."""
    import hashlib
    import urllib.request
    from .. import ephem
    if KPROG['state'] == 'running': return dict(ok=True)

    def work():
        KPROG.update(done=0, total=ephem.DE440S_SIZE, state='running', error='', sha256='')
        dest = ephem.kernel_dir() / 'de440s.bsp'; tmp = dest.with_suffix('.part'); h = hashlib.sha256()
        try:
            req = urllib.request.Request(ephem.DE440S_URL, headers={'User-Agent': 'OrbitSimulator'})
            with urllib.request.urlopen(req, timeout=60) as r, open(tmp, 'wb') as f:
                KPROG['total'] = int(r.headers.get('Content-Length') or ephem.DE440S_SIZE)
                while True:
                    b = r.read(1 << 18)
                    if not b: break
                    f.write(b); h.update(b); KPROG['done'] += len(b)
            if KPROG['done'] < 1_000_000: raise OSError('the download is too small to be the kernel')
            tmp.replace(dest); KPROG.update(state='done', sha256=h.hexdigest())
        except Exception as ex:
            try: tmp.unlink()
            except OSError: pass
            KPROG.update(state='error', error=str(ex))
    threading.Thread(target=work, daemon=True).start(); return dict(ok=True)


def licenses(p: dict) -> dict:
    """Third-party notices shown in Settings > About (the NOTICE file and the licence texts shipped with the program)."""
    import sys
    base = pathlib.Path(getattr(sys, '_MEIPASS', pathlib.Path(__file__).resolve().parents[2])) if getattr(sys, 'frozen', False) else pathlib.Path(__file__).resolve().parents[2]
    out = []
    n = base / 'NOTICE'
    if n.exists(): out.append(dict(name='Notice', text=n.read_text(encoding='utf-8', errors='replace')))
    for f in sorted((base / 'LICENSES').glob('*.txt')) if (base / 'LICENSES').exists() else []:
        out.append(dict(name=f.stem.replace('-', ' '), text=f.read_text(encoding='utf-8', errors='replace')))
    return dict(items=out)


def mission_import_trajectory(p: dict) -> dict:
    """Read a reference trajectory: CSV / CCSDS OEM text, or the path of an SPK kernel (.bsp)."""
    from ..mission import trajectory_io as TI
    try:
        if p.get('path'): ref = TI.parse_spk(p['path'], p.get('target'), name=p.get('name') or pathlib.Path(p['path']).stem)
        else: ref = TI.import_text(p.get('filename') or 'trajectory.csv', p['text'])
        return dict(ok=True, ref=ref, points=len(ref['jd']))
    except Exception as ex: return dict(ok=False, error=f'{type(ex).__name__}: {ex}')


def save_blob(p: dict) -> dict:
    """Save a recording or a screenshot made in the space view into the exports folder (base64 payload)."""
    import base64
    kind = p.get('kind', 'webm')
    if kind not in ('webm', 'png'): return dict(ok=False, error='unsupported file type')
    try:
        out = shell.unique_path(shell.folder('exports'), ''.join(c if c.isalnum() or c in '-_' else '_' for c in p.get('name', 'space_view'))[:60] or 'space_view', kind)
        out.write_bytes(base64.b64decode(p['data'].split(',')[-1])); return dict(ok=True, path=str(out))
    except Exception as ex: return dict(ok=False, error=str(ex))


# ------------------------------------------------------------------------------------------------ Explore (sandbox)
def sandbox_meta(p: dict) -> dict:
    from ..sandbox import service as SS
    out = SS.meta(ConstantSet(p.get('constants', 'Course table'))); e = _eph(); out['ephemeris'] = dict(name=e.name, accuracy=e.accuracy); return out


def sandbox_new(p: dict) -> dict:
    from ..sandbox import service as SS
    try:
        with LOCK:
            scene = SS.default_scene(_eph(), p.get('jd')); return dict(ok=True, scene=scene, sim=SS.run(scene, p.get('horizon', '1 year')))
    except Exception as ex: return dict(ok=False, error=f'{type(ex).__name__}: {ex}')


def sandbox_run(p: dict) -> dict:
    from ..sandbox import service as SS
    try:
        with LOCK: return dict(ok=True, sim=SS.run(p['scene'], p.get('horizon', '1 year')))
    except Exception as ex: return dict(ok=False, error=f'{type(ex).__name__}: {ex}')


def sandbox_edit(p: dict) -> dict:
    """Apply edit operations at the current simulation time and re-simulate. A bad edit leaves the scene untouched and returns a message."""
    from ..sandbox import service as SS
    try:
        with LOCK:
            scene = SS.edit(p['scene'], float(p['jd']), p['edits'], _eph(), ConstantSet(p.get('constants', 'Course table')))
            return dict(ok=True, scene=scene, sim=SS.run(scene, p.get('horizon', '1 year')))
    except (KeyError, ValueError) as ex: return dict(ok=False, error=str(ex.args[0]) if ex.args else str(ex))
    except Exception as ex: return dict(ok=False, error=f'{type(ex).__name__}: {ex}')


def sandbox_panel(p: dict) -> dict:
    from ..sandbox import service as SS
    try:
        from ..sandbox import sim as SIM
        sc = SIM.state_at(p['scene'], float(p['jd'])) if p.get('jd') else p['scene']
        return dict(ok=True, panel=SS.panel(sc, p['id']))
    except Exception as ex: return dict(ok=False, error=str(ex))


def sandbox_to_mission(p: dict) -> dict:
    from ..sandbox import service as SS
    try: return dict(ok=True, mission=SS.to_mission(p['scene'], p['id'], p.get('name'), ConstantSet(p.get('constants', 'Course table'))).to_dict())
    except Exception as ex: return dict(ok=False, error=str(ex))


def sandbox_save(p: dict) -> dict:
    """Save a scene as an .orbitscene file in the exports folder."""
    import json
    try:
        stem = ''.join(c if c.isalnum() or c in '-_' else '_' for c in p['scene'].get('name', 'scene'))[:60] or 'scene'
        out = shell.unique_path(shell.folder('exports'), stem, 'orbitscene'); out.write_text(json.dumps(dict(format='orbitscene', version=1, scene=p['scene']), indent=1), encoding='utf-8'); return dict(ok=True, path=str(out))
    except Exception as ex: return dict(ok=False, error=str(ex))


def mission_porkchop(p: dict) -> dict:
    """Departure x arrival grid (Earth to Mars by default). Dates are 'YYYY-MM-DD'."""
    from ..mission import porkchop as PK
    from ..core.timeutil import calendar_to_jd, format_gregorian
    def jd_of(x):
        y, m, d = (int(v) for v in str(x).split('-')); return calendar_to_jd(y, m, d)
    try:
        o, t = p.get('origin', 'Earth'), p.get('target', 'Mars'); d0, a0 = jd_of(p['dep_start']), jd_of(p['arr_start']); n = int(min(60, max(8, p.get('n', 30))))
        with LOCK:
            apply_palette(p.get('palette', 'prussian')); MPROG.update(stage='porkchop', frac=0.0)
            g = PK.grid(_eph(), o, t, d0, float(p['dep_days']), a0, float(p['arr_days']), n, ConstantSet(p.get('constants', 'Course table')), lambda s_, f: MPROG.update(stage=s_, frac=f))
            svg = PK.render_svg(g, o, t, p.get('theme', 'dark')); MPROG.update(stage='done', frac=1.0)
        b = g['best']
        if not b: return dict(ok=False, error='no valid transfers in this date range (check that the arrival dates are after the departure dates)')
        return dict(ok=True, svg=svg, best=dict(b, dep=format_gregorian(b['dep_jd']), arr=format_gregorian(b['arr_jd']), tof_days=b['arr_jd'] - b['dep_jd']), origin=o, target=t, ephemeris=_eph().name)
    except Exception as ex: return dict(ok=False, error=f'{type(ex).__name__}: {ex}')


def mission_from_porkchop(p: dict) -> dict:
    from ..mission import porkchop as PK
    try: return dict(ok=True, mission=PK.transfer_mission(_eph(), p.get('origin', 'Earth'), p.get('target', 'Mars'), float(p['dep_jd']), float(p['arr_jd']), ConstantSet(p.get('constants', 'Course table'))).to_dict())
    except Exception as ex: return dict(ok=False, error=str(ex))


def mission_trajectory(p: dict) -> dict:
    """Save a spacecraft trajectory as CSV or CCSDS OEM into the exports folder."""
    from ..mission.model import Mission
    from ..mission import service as MS
    from ..mission.run import run
    try:
        m = Mission.from_dict(p['mission']); res = run(m, _eph(), ConstantSet(m.constants)); sat = p.get('sat') or m.spacecraft[0].name; kind = p.get('kind', 'csv')
        text = MS.trajectory_csv(res, sat) if kind == 'csv' else MS.trajectory_oem(res, sat); ext = 'csv' if kind == 'csv' else 'oem'
        out = shell.unique_path(shell.folder('exports'), f'{sat}_trajectory', ext); out.write_text(text, encoding='utf-8'); return dict(ok=True, path=str(out))
    except Exception as ex: return dict(ok=False, error=str(ex))


def gmat_check(p: dict) -> dict:
    from ..gmat import runner
    c = runner.find_console(p.get('path') or _settings().get('gmatPath')); return dict(ok=bool(c), console=str(c or ''))


def run_tests(_: dict | None = None) -> dict:
    summary, detail = [], []
    total = ok = 0
    for mid, p in all_presets():
        with LOCK:
            try:
                res, rows = run_preset(mid, p)
            except Exception as ex:
                summary.append(dict(mid=mid, module=MODULES[mid].short, problem=p.label, checks=0, passed=0, status=f'ERROR {type(ex).__name__}: {ex}', idx=PRESETS[mid].index(p))); continue
        n_ok = sum(r.ok for r in rows); total += len(rows); ok += n_ok
        summary.append(dict(mid=mid, module=MODULES[mid].short, problem=p.label, checks=len(rows), passed=n_ok, status='pass' if n_ok == len(rows) else 'fail', idx=PRESETS[mid].index(p), note=p.note))
        detail.append(dict(mid=mid, idx=PRESETS[mid].index(p), rows=[dict(name=r.name, got=r.got, expected=r.expected, rtol=r.rtol, ok=r.ok, error=r.error) for r in rows]))
    return dict(total=total, passed=ok, summary=summary, detail=detail)


def jd(p: dict) -> dict:
    t = p['type']
    if t == 'cal2jd':
        Y, M, D, h, mi, s = (p[k] for k in ('Y', 'M', 'D', 'h', 'mi', 's'))
        return dict(jd=calendar_to_jd(int(Y), int(M), int(D), float(h), float(mi), float(s)), weekday=weekday_name(int(Y), int(M), int(D)))
    if t == 'jd2cal':
        y, m, d, h, mi, s = jd_to_calendar(float(p['jd'])); return dict(text=f'{y:04d}-{m:02d}-{d:02d}  {h:02d}:{mi:02d}:{s:06.3f} UT', weekday=weekday_name(y, m, d))
    uy, um, ud, uh, umi, off = et_to_ut(int(p['Y']), int(p['M']), int(p['D']), int(p['h']), int(p['mi']))
    return dict(text=f"{weekday_name(int(p['Y']), int(p['M']), int(p['D']))} {int(p['h']):02d}:{int(p['mi']):02d} {'EDT' if off == 4 else 'EST'} = {uy:04d}-{um:02d}-{ud:02d} {uh:02d}:{umi:02d} UT",
                jd=calendar_to_jd(uy, um, ud, uh, umi))


def settings_set(p: dict) -> dict:
    shell.save_settings(p.get('settings') or {}); return dict(ok=True)


def screenshot(_: dict | None = None) -> dict:
    try: return dict(ok=True, path=str(shell.capture_window()))
    except Exception as ex: return dict(ok=False, error=str(ex))


def fullscreen(_: dict | None = None) -> dict:
    try: return dict(ok=True, **shell.toggle_fullscreen())
    except Exception as ex: return dict(ok=False, error=str(ex))


def open_folder(p: dict) -> dict:
    try: return dict(ok=True, path=shell.open_folder(p.get('which', 'root')))
    except Exception as ex: return dict(ok=False, error=str(ex))


def export_save(p: dict) -> dict:
    """Write an export into the exports folder under %APPDATA%/Orbit Simulator and return its path."""
    try:
        data, _mime, name = export(int(p['idx']), p['fmt'], p.get('theme', 'light'))
        stem, _, ext = name.rpartition('.'); out = shell.unique_path(shell.folder('exports'), stem, ext); out.write_bytes(data)
        return dict(ok=True, path=str(out))
    except Exception as ex:
        return dict(ok=False, error=str(ex))


def _bk(fn):
    """Wrap a backup action: ValueError -> a clean message for the UI."""
    def run(p):
        try: return dict(ok=True, **fn(p or {}))
        except (ValueError, OSError) as ex: return dict(ok=False, error=str(ex))
    return run


def _bk_create(p):
    path = backup.create_backup(p.get('label') or 'backup'); return dict(name=path.name, path=str(path), backups=backup.list_backups())


def _bk_list(p):
    return dict(backups=backup.list_backups(), folder=str(backup.backups_dir()))


def _bk_restore(p):
    import pathlib as _pl
    path = (backup.backups_dir() / _pl.PurePosixPath(p['name']).name)
    if not path.is_file(): raise ValueError('backup not found')
    return dict(backup.restore_backup(path), settings=shell.load_settings(), backups=backup.list_backups())


def _bk_import(p):
    import base64
    return dict(backup.import_backup(p.get('filename') or 'backup.zip', base64.b64decode(p['data'])), settings=shell.load_settings(), backups=backup.list_backups())


def _bk_delete(p):
    backup.delete_backup(p['name']); return dict(backups=backup.list_backups())


REPO_URL = 'https://github.com/Chiyami1213/orbit-simulator'


def _scrub(text: str) -> str:
    """Remove the user's name / home folder from text that leaves the machine (log excerpts)."""
    import os, pathlib
    for h in {str(pathlib.Path.home()), os.environ.get('USERPROFILE', ''), os.environ.get('HOME', '')}:
        if h: text = text.replace(h, '~').replace(h.replace('\\', '/'), '~')
    user = os.environ.get('USERNAME') or os.environ.get('USER') or ''
    return text.replace(user, '<user>') if len(user) > 2 else text


def report_issue(p: dict) -> dict:
    """Open a pre-filled 'new issue' page on GitHub (the user reviews and submits it; nothing is sent automatically)."""
    import platform, sys, webbrowser, pathlib
    from urllib.parse import urlencode
    title = (p.get('title') or 'Issue report').strip()[:120]
    env = [f'- Orbit Simulator: {VERSION}', f'- OS: {platform.platform()}', f"- Packaged build: {bool(getattr(sys, 'frozen', False))}", f"- Graphics (WebGL): {p.get('gpu') or 'unknown'}",
           f"- Page: {p.get('page') or ''}", f"- Constants: {p.get('consts') or ''}"]
    body = '## What happened\n' + (p.get('description') or '').strip() + '\n\n## Steps to reproduce\n1. \n\n## Environment\n' + '\n'.join(env) + '\n'
    if p.get('include_log'):
        log = pathlib.Path(shell.paths()['logs']) / 'orbit-simulator.log'
        try: tail = '\n'.join(log.read_text(encoding='utf-8', errors='replace').splitlines()[-25:])
        except OSError: tail = '(no log file)'
        body += '\n<details><summary>Log (last lines)</summary>\n\n```\n' + _scrub(tail) + '\n```\n</details>\n'
    url = REPO_URL + '/issues/new?' + urlencode({'title': title, 'body': body[:6500]})
    try: webbrowser.open(url)
    except Exception as ex: return dict(ok=False, error=str(ex), url=url)
    return dict(ok=True, url=url)


ROUTES = {'meta': lambda p: meta(), 'visible': visible, 'solve': solve, 'progress': progress, 'mission_meta': mission_meta, 'mission_starter': mission_starter, 'mission_run': mission_run, 'mission_progress': mission_progress, 'mission_convert': mission_convert,
          'mission_compare': mission_compare, 'mission_script': mission_script, 'mission_import': mission_import, 'mission_from_module': mission_from_module, 'mission_save': mission_save,
          'ephem_status': ephem_status, 'mission_porkchop': mission_porkchop, 'sandbox_meta': sandbox_meta, 'sandbox_new': sandbox_new, 'sandbox_run': sandbox_run, 'sandbox_edit': sandbox_edit, 'sandbox_panel': sandbox_panel, 'sandbox_to_mission': sandbox_to_mission, 'sandbox_save': sandbox_save, 'save_blob': save_blob, 'mission_import_trajectory': mission_import_trajectory, 'mission_from_porkchop': mission_from_porkchop, 'mission_trajectory': mission_trajectory, 'licenses': licenses, 'ephem_download': ephem_download, 'gmat_check': gmat_check, 'tests': run_tests, 'jd': jd, 'settings_set': settings_set, 'screenshot': screenshot,
          'fullscreen': fullscreen, 'open_folder': open_folder, 'export_save': export_save, 'report_issue': report_issue,
          'backup_create': _bk(_bk_create), 'backup_list': _bk(_bk_list), 'backup_restore': _bk(_bk_restore), 'backup_import': _bk(_bk_import), 'backup_delete': _bk(_bk_delete)}
