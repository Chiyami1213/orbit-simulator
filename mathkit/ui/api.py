"""JSON API behind the desktop UI. Pure functions: dict in -> dict out (everything JSON-serialisable)."""
from __future__ import annotations
import io
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
from ..results import Result
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
        LAST.clear(); LAST.update(palette=(p.get('opts') or {}).get('palette', 'prussian'), res=res, name=user, label=vals['_label'], mid=mid, body=(p.get('opts') or {}).get('body', 'symbol'))
    groups = []
    for g in dict.fromkeys(s.group for s in res.steps):
        groups.append(dict(name=g, rows=[[s.name, s.symbol, s.display(), s.units, s.equation, s.note] for s in res.steps if s.group == g]))
    return dict(title=res.title, label=res.label, warnings=res.warnings, checks=res.checks, groups=groups, scenes=scenes, figs=extra_figs,
                cards=summary_cards(mid, res), tabs=extra_tabs(mid, res), inputs=_jsonable(res.inputs), problems=problems)


def export(idx: int, fmt: str, theme: str = 'light'):
    """Render the idx-th scene of the last result for download. Returns (bytes, mimetype, filename)."""
    if not LAST: raise ValueError('nothing solved yet')
    apply_palette(LAST.get('palette', 'prussian'))
    res: Result = LAST['res']; scenes = [('main', res.scene)] + list(res.scenes.items()); name, sc = scenes[idx]
    stem = ((LAST['name'] + '_') if LAST['name'] else '') + LAST['label'].replace(' ', '_') + ('' if name == 'main' else '_' + name.split()[0])
    with LOCK:
        if fmt == 'html': return build_html(sc, theme, LAST['name'], plotlyjs='cdn', body=LAST.get('body', 'symbol')).encode('utf-8'), 'text/html', stem + '_3D.html'
        if fmt in ('py', 'm'):
            from . import codegen
            title = (LAST['name'] + ' — ' if LAST['name'] else '') + f'{sc.label}: {sc.title}'; fname = codegen.safe_name(stem) + '_plots.' + fmt
            gen = codegen.python_script if fmt == 'py' else codegen.matlab_script
            code = gen(sc, title, theme, LAST.get('body', 'symbol'), res.inputs, fname)
            return code.encode('utf-8'), ('text/x-python' if fmt == 'py' else 'text/plain'), fname
        fig = render(sc, theme, LAST['name'], body=LAST.get('body', 'symbol')); buf = io.BytesIO()
        fig.savefig(buf, format=fmt, dpi=300, bbox_inches='tight', facecolor=fig.get_facecolor()); plt.close(fig)
    return buf.getvalue(), ('image/png' if fmt == 'png' else 'application/pdf'), f'{stem}.{fmt}'


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


ROUTES = {'meta': lambda p: meta(), 'visible': visible, 'solve': solve, 'progress': progress, 'tests': run_tests, 'jd': jd, 'settings_set': settings_set, 'screenshot': screenshot,
          'fullscreen': fullscreen, 'open_folder': open_folder, 'export_save': export_save, 'report_issue': report_issue,
          'backup_create': _bk(_bk_create), 'backup_list': _bk(_bk_list), 'backup_restore': _bk(_bk_restore), 'backup_import': _bk(_bk_import), 'backup_delete': _bk(_bk_delete)}
