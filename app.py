"""AAE 532 Orbit Toolkit — Streamlit entry point.   Run:  streamlit run app.py"""
from __future__ import annotations
import io
import traceback
import numpy as np
import pandas as pd
import streamlit as st
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from aae532.core.constants import BODIES, EXAM, ConstantSet, AU
from aae532.core.timeutil import calendar_to_jd, jd_to_calendar, weekday_name, et_to_ut
from aae532.registry import MODULES, Field
from aae532.presets.hw_problems import PRESETS
from aae532.presets.runner import run_preset, all_presets
from aae532.plots2d.render import render
from aae532.view3d.animate import build_html
from aae532.results import Result

st.set_page_config(page_title='AAE 532 Orbit Toolkit', page_icon='🛰️', layout='wide')

PAGES = [m.title for m in MODULES.values()] + ['Test cases', 'Julian date & time', 'Constants browser']
TITLE_TO_ID = {m.title: m.id for m in MODULES.values()}
ss = st.session_state
ss.setdefault('canon', {})        # module id -> {field key: value in km / km·s⁻¹ / ° (canonical)}


# ---------------------------------------------------------------------------------------------------- top bar
def top_bar():
    c = st.columns([1.3, 1.1, 1.1, 0.9, 1.4, 1.2])
    with c[0]:
        mode = st.radio('Constants', ['Course table', 'Exam rounded'], horizontal=True, key='const_mode',
                        help='Course table = GMAT 2020a / JPL "Useful Constants". Exam rounded: μ⊕ = 4×10⁵, R⊕ = 6400; Moon μ = 5000; Mars μ = 4.2×10⁴, R = 3400.')
    with c[1]:
        moon_R = st.number_input('Moon R (exam)', value=2000.0, step=500.0, key='moon_R', disabled=mode != 'Exam rounded', help='Exam 1 uses 2000 km, Exam 2 uses 1500 km.')
    with c[2]:
        unit = st.radio('Distances', ['km', 'R_body', 'AU'], horizontal=True, key='dist_unit')
    with c[3]:
        theme = st.radio('Figure theme', ['light', 'dark'], horizontal=True, key='theme')
    with c[4]:
        name = st.text_input('Your name (figure titles)', key='user_name', placeholder='required on homework figures')
    with c[5]:
        label = st.text_input('Problem label', key='problem_label', placeholder='e.g. HW7 P2')
    return ConstantSet(mode, moon_R), unit, theme, name, label


# ---------------------------------------------------------------------------------------------------- inputs
def clear_widgets(mid: str):
    for k in [k for k in ss.keys() if k.startswith(f'w.{mid}.')]:
        del ss[k]


def load_preset(mid: str, idx: int):
    p = PRESETS[mid][idx]
    clear_widgets(mid); ss['canon'][mid] = dict(p.vals)
    # widget-bound keys cannot be changed after their widget exists in this run: queue them and apply at the top of the next run
    pend = ss.setdefault('_pending', {})
    pend['const_mode'] = p.consts; pend['problem_label'] = p.label.split(' — ')[0]
    if p.consts == 'Exam rounded': pend['moon_R'] = p.moon_R


def parse_vec(txt: str):
    return [float(x) for x in txt.replace(';', ',').replace('[', '').replace(']', '').split(',') if x.strip()]


def inputs_panel(spec, C: ConstantSet, unit: str) -> dict | None:
    mid = spec.id; canon = ss['canon'].setdefault(mid, {})
    # preset picker
    if PRESETS.get(mid):
        labels = ['— choose a homework / exam problem —'] + [p.label for p in PRESETS[mid]]
        sel = st.selectbox('Load a problem', labels, key=f'preset_sel.{mid}', index=0)
        if sel != labels[0] and ss.get(f'preset_loaded.{mid}') != sel:
            load_preset(mid, labels.index(sel) - 1); ss[f'preset_loaded.{mid}'] = sel; st.rerun()
        if sel != labels[0]:
            note = PRESETS[mid][labels.index(sel) - 1].note
            if note: st.caption('ℹ️ ' + note)
    vals: dict = {}
    # the body must be known first so R_body conversions work
    for f in spec.fields:
        if f.show_if is not None and not f.show_if({**{g.key: g.default for g in spec.fields}, **canon, **vals}):
            vals[f.key] = canon.get(f.key, f.default); continue
        wkey = f'w.{mid}.{f.key}.{unit if (f.dist) else ""}'
        cur = canon.get(f.key, f.default)
        if f.kind == 'choice':
            opts = f.options; v = st.selectbox(f.label, opts, index=opts.index(cur) if cur in opts else 0, key=wkey)
        elif f.kind == 'bool':
            v = st.checkbox(f.label, value=bool(cur), key=wkey)
        elif f.kind == 'text':
            v = st.text_input(f.label, value=str(cur), key=wkey)
        elif f.kind == 'int':
            v = int(st.number_input(f.label, value=int(cur), step=1, key=wkey))
        elif f.kind == 'vec':
            fac = _unit_factor(spec, vals, canon, C, unit) if f.dist else 1.0
            shown = [x / fac for x in cur]
            txt = st.text_input(f'{f.label} ({_unit_label(f, unit)})', value=', '.join(f'{x:.10g}' for x in shown), key=wkey)
            try: v = [x * fac for x in parse_vec(txt)]
            except ValueError: st.error(f'{f.label}: could not parse "{txt}"'); return None
        else:
            if f.dist:
                fac = _unit_factor(spec, vals, canon, C, unit)
                x = st.number_input(f'{f.label} ({_unit_label(f, unit)})', value=float(cur) / fac, format='%.10g', step=None, key=wkey); v = x * fac
            else:
                v = st.number_input(f'{f.label}' + (f' ({f.unit})' if f.unit else ''), value=float(cur), format='%.10g', step=None, key=wkey)
        vals[f.key] = v; canon[f.key] = v
    return vals


def _unit_factor(spec, vals, canon, C, unit):
    if unit == 'km': return 1.0
    if unit == 'AU': return AU
    bk = spec.body_key
    if not bk: return 1.0
    name = vals.get(bk, canon.get(bk, 'Earth'))
    return C.R(name)


def _unit_label(f: Field, unit: str) -> str:
    return unit if f.dist else f.unit


# ---------------------------------------------------------------------------------------------------- outputs
def fig_bytes(fig, fmt: str) -> bytes:
    buf = io.BytesIO(); fig.savefig(buf, format=fmt, dpi=300, bbox_inches='tight', facecolor=fig.get_facecolor()); return buf.getvalue()


def show_scene_2d(sc, theme, name, key, fname):
    fig = render(sc, theme, name)
    st.pyplot(fig, clear_figure=False)
    c = st.columns([1, 1, 6])
    c[0].download_button('PNG · 300 dpi', fig_bytes(fig, 'png'), f'{fname}.png', 'image/png', key=f'png.{key}')
    c[1].download_button('PDF', fig_bytes(fig, 'pdf'), f'{fname}.pdf', 'application/pdf', key=f'pdf.{key}')
    if fig.label_overlaps: st.caption(f'⚠️ {fig.label_overlaps} label overlap(s) detected — try a different view or export and nudge manually.')
    plt.close(fig)


def show_result(res: Result, theme: str, name: str, mid: str):
    for w in res.warnings: st.warning(w)
    tabs = ['Results table', '2-D figure', '3-D view / animation', 'Checks']
    if res.figs: tabs.append('Plots')
    T = st.tabs(tabs)
    with T[0]:
        rows = res.table(); groups = list(dict.fromkeys(r['Group'] for r in rows))
        for g in groups:
            if g: st.markdown(f'**{g}**')
            df = pd.DataFrame([{k: str(v) for k, v in r.items() if k != 'Group'} for r in rows if r['Group'] == g])
            st.dataframe(df, hide_index=True, width='stretch')
        with st.expander('Inputs echoed'): st.json(_jsonable(res.inputs))
    scenes = {'main': res.scene, **res.scenes}
    with T[1]:
        fname = (name + '_' if name else '') + res.label.replace(' ', '_')
        if len(scenes) > 1:
            sub = st.tabs(list(scenes))
            for t, (k, sc) in zip(sub, scenes.items()):
                with t: show_scene_2d(sc, theme, name, f'{mid}.{k}', f'{fname}_{k.split()[0]}')
        else:
            show_scene_2d(res.scene, theme, name, mid, fname)
        for n in res.scene.notes: st.caption(n)
    with T[2]:
        if len(scenes) > 1:
            sub = st.tabs(list(scenes))
            for t, (k, sc) in zip(sub, scenes.items()):
                with t: st.iframe(build_html(sc, theme, name), height=860)
        else:
            st.iframe(build_html(res.scene, theme, name), height=860)
    with T[3]:
        if res.checks:
            for c in res.checks: st.info(c)
        else: st.write('No quadrant checks for this problem.')
    if res.figs:
        with T[4]:
            for k, f in res.figs.items():
                fig = f(theme, name); st.pyplot(fig); plt.close(fig)


def _jsonable(o):
    if isinstance(o, dict): return {k: _jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)): return [_jsonable(v) for v in o]
    if isinstance(o, np.ndarray): return o.tolist()
    if isinstance(o, (np.floating, np.integer)): return o.item()
    return o


# ---------------------------------------------------------------------------------------------------- pages
def module_page(spec, C, unit, theme, name, label):
    st.subheader(spec.title); st.caption(spec.blurb)
    if unit == 'R_body' and not spec.body_key: st.caption('R_body is not defined on this page (several bodies); distances are entered in km.')
    left, right = st.columns([1, 2.6], gap='large')
    with left:
        vals = inputs_panel(spec, C, unit)
    if vals is None: return
    vals['_label'] = label or ss.get('problem_label', '') or f'Module {spec.id}'
    with right:
        try:
            res = spec.run(vals, C)
        except (ValueError, ZeroDivisionError, KeyError, np.linalg.LinAlgError) as ex:
            st.error(f'Could not solve with these inputs: {ex}'); return
        except Exception:
            st.error('Unexpected error'); st.code(traceback.format_exc()); return
        show_result(res, theme, name, spec.id)


def test_page(theme, name):
    st.subheader('Test cases — computed vs. printed solution values')
    st.caption('Each preset is run through the same code path as the module pages. Tolerance is relative 2×10⁻⁴ unless the solution prints fewer digits. '
               'Errata (corrected values) are noted on the problems they affect.')
    if st.button('Run all test cases', type='primary') or ss.get('tests_ran'):
        ss['tests_ran'] = True; total = ok = 0; summary = []; detail = []
        for mid, p in all_presets():
            try:
                res, rows = run_preset(mid, p)
            except Exception as ex:
                summary.append(dict(Module=MODULES[mid].title, Problem=p.label, Checks=0, Passed=0, Status=f'ERROR {type(ex).__name__}: {ex}')); continue
            n_ok = sum(r.ok for r in rows); total += len(rows); ok += n_ok
            summary.append(dict(Module=MODULES[mid].title, Problem=p.label, Checks=len(rows), Passed=n_ok, Status='✅' if n_ok == len(rows) else '❌'))
            detail.append((mid, p, rows))
        (st.success if ok == total else st.error)(f'{ok} / {total} checks passed')
        st.dataframe(pd.DataFrame(summary), hide_index=True, width='stretch')
        st.markdown('#### Details')
        for mid, p, rows in detail:
            with st.expander(f'{MODULES[mid].title} — {p.label}   ({sum(r.ok for r in rows)}/{len(rows)})'):
                if p.note: st.caption('ℹ️ ' + p.note)
                df = pd.DataFrame([dict(Quantity=r.name, Computed=('—' if r.got is None else f'{r.got:.8g}'), Expected=f'{r.expected:.8g}',
                                        RelErr=('—' if r.got is None else f'{abs(r.got - r.expected) / abs(r.expected):.1e}'), Tol=f'{r.rtol:.0e}', OK='✅' if r.ok else '❌') for r in rows])
                st.dataframe(df, hide_index=True, width='stretch')
                i = PRESETS[mid].index(p)
                if st.button('Open in module', key=f'open.{mid}.{i}'):
                    load_preset(mid, i); ss[f'preset_loaded.{mid}'] = p.label; ss['_pending']['page'] = MODULES[mid].title; st.rerun()


def jd_page():
    st.subheader('Julian date & time')
    a, b = st.columns(2)
    with a:
        st.markdown('**Calendar (UT) → Julian date**')
        c = st.columns(6); Y = c[0].number_input('Year', value=2000, step=1, key='jd_y'); M = c[1].number_input('Month', 1, 12, 1, key='jd_m'); Dd = c[2].number_input('Day', 1, 31, 1, key='jd_d')
        h = c[3].number_input('h', 0, 23, 12, key='jd_h'); mi = c[4].number_input('min', 0, 59, 0, key='jd_mi'); se = c[5].number_input('s', 0.0, 59.999, 0.0, key='jd_s')
        jd = calendar_to_jd(int(Y), int(M), int(Dd), h, mi, se); st.metric('Julian date', f'{jd:.6f}'); st.caption(f'{weekday_name(int(Y), int(M), int(Dd))}; JD days are 86 400 s; Julian year = 365.25 d.')
    with b:
        st.markdown('**Julian date → calendar (UT)**')
        j = st.number_input('JD', value=2451545.0, format='%.6f', key='jd_in'); y, m, d, hh, mm, ss_ = jd_to_calendar(j)
        st.metric('UT', f'{y:04d}-{m:02d}-{d:02d}  {hh:02d}:{mm:02d}:{ss_:06.3f}'); st.caption(weekday_name(y, m, d))
    st.markdown('**US Eastern → UT** (e.g. “Friday 9:30 am ET”)')
    c = st.columns(5); Y2 = c[0].number_input('Year', value=2024, step=1, key='et_y'); M2 = c[1].number_input('Month', 1, 12, 10, key='et_m'); D2 = c[2].number_input('Day', 1, 31, 4, key='et_d')
    h2 = c[3].number_input('ET hour', 0, 23, 9, key='et_h'); m2 = c[4].number_input('ET min', 0, 59, 30, key='et_mi')
    try:
        uy, um, ud, uh, umi, off = et_to_ut(int(Y2), int(M2), int(D2), int(h2), int(m2)); jd2 = calendar_to_jd(uy, um, ud, uh, umi)
        st.success(f'{weekday_name(int(Y2), int(M2), int(D2))} {int(h2):02d}:{int(m2):02d} {"EDT" if off == 4 else "EST"} = {uy:04d}-{um:02d}-{ud:02d} {uh:02d}:{umi:02d} UT   (JD {jd2:.5f})')
    except ValueError as ex:
        st.error(str(ex))


def constants_page(C):
    st.subheader('Constants browser')
    rows = []
    for n, b in BODIES.items():
        cb = C.body(n)
        rows.append({'Body': n, 'μ (km³·s⁻²)': cb['mu'], 'R (km)': cb['R'], 'a (km)': b.get('a'), 'e': b.get('e'), 'overridden by exam set': 'yes' if C.exam and n in EXAM else ''})
    st.dataframe(pd.DataFrame(rows), hide_index=True, width='stretch')
    st.caption(f'Active set: **{C.mode}**. 1 AU = {AU:,.1f} km (reproduces the HW4 numbers); the constants table lists Earth’s a = 149 597 898 km — use that for “Earth’s orbit radius”. '
               'Julian year = 365.25 d, HW4 months = 30 d, JD day = 86 400 s.')


def main():
    for k, v in ss.pop('_pending', {}).items(): ss[k] = v
    C, unit, theme, name, label = top_bar()
    st.divider()
    with st.sidebar:
        st.markdown('### 🛰️ AAE 532 Orbit Toolkit')
        page = st.radio('Module', PAGES, key='page', label_visibility='collapsed')
        if not name: st.warning('Enter your name above: homework figure titles must carry it.')
    if page in TITLE_TO_ID: module_page(MODULES[TITLE_TO_ID[page]], C, unit, theme, name, label)
    elif page == 'Test cases': test_page(theme, name)
    elif page == 'Julian date & time': jd_page()
    else: constants_page(C)


main()
