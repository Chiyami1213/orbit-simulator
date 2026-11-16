"""LaTeX conversion, 3-D label fan-out, text-case rules (via Node) and the Python / MATLAB code export."""
import os
import pathlib
import shutil
import subprocess
import sys
import numpy as np
import pytest
from mathkit.ui.latex import tex, valid
from mathkit.view3d.scene import stagger_labels, html_label
from mathkit.ui import api
from mathkit.presets.hw_problems import PRESETS

ROOT = pathlib.Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------- LaTeX converter
@pytest.mark.parametrize('src,expected', [
    ('a_tot', r'$a_{\mathrm{tot}}$'),
    ('Δv_eq = |v̄⁺ − v̄⁻|', r'$\Delta v_{\mathrm{eq}} = |\bar{v}^{+} - \bar{v}^{-}|$'),
    ('θ*', r'$\theta ^{*}$'),
    ('Ω = atan2(ĥ_x, −ĥ_y)', r'$\Omega = \mathrm{atan2}(\hat{h}_{x}, - \hat{h}_{y})$'),
    ('120°', r'$120^{\circ}$'),
    ('orbit is hyperbolic', 'orbit is hyperbolic'),                       # pure prose is untouched
])
def test_latex_examples(src, expected):
    assert tex(src) == expected


def test_prose_stays_outside_math_and_thin_spaces_are_normalised():
    out = tex('θ* from atan2(ṙ·h/μ, p/r − 1)')
    assert out.startswith('$\\theta') and ' from ' in out and out.count('$') == 4
    assert ' ' not in tex('θ*₁ = 3 (Δv = 1)')


def test_every_math_run_is_valid_mathtext():
    for lst in PRESETS.values():
        for p in lst:
            for s in [p.label, p.note]:
                for run in tex(s).split('$')[1::2]: assert valid(run), (s, run)


def test_body_notation_symbol_or_name_subscript():
    assert tex('R⊕', 'symbol') == r'$R_{\oplus}$' and tex('R⊕', 'name') == r'$R_{\mathrm{earth}}$'
    assert tex('R♇', 'name') == r'$R_{\mathrm{pluto}}$'
    assert '<sub>earth</sub>' in html_label('R⊕', 'name') and '<sub>D</sub>' in html_label('v_D')


# ---------------------------------------------------------------- 3-D labels
def test_coincident_labels_get_different_positions():
    labs = [(np.zeros(3), 'Earth', 'a'), (np.array([1e-3, 0, 0]), 'Moon', 'b'), (np.array([0, 0, 1e-3]), 'Sun', 'c'), (np.array([1e6, 0, 0]), 'far', 'd')]
    out = stagger_labels(labs, thr=1.0); pos = [o[3] for o in out]
    assert len(set(pos[:3])) == 3 and pos[3] == 'top center'


# ---------------------------------------------------------------- text-case rules (Node)
@pytest.mark.skipif(shutil.which('node') is None, reason='node is not installed')
def test_textcase_rules_with_node():
    js = r'''
const {apa, lc} = require(process.argv[1]); let bad = 0;
const eq = (a, b) => { if (a !== b) { console.log('FAIL', JSON.stringify(a), '!==', JSON.stringify(b)); bad++; } };
eq(apa('step-by-step'), 'Step-by-Step'); eq(apa('n-body accelerations'), 'N-Body Accelerations'); eq(apa('use device settings'), 'Use Device Settings');
eq(apa('single burn at the node'), 'Single Burn at the Node'); eq(apa('Ω from the node'), 'Ω From the Node'); eq(apa('departure v_D'), 'Departure v_D');
eq(apa('problem label (printed in the title)'), 'Problem Label (printed in the title)'); eq(apa('constants and units'), 'Constants and Units');
eq(lc('Erratum: the printed e = 0.8225 for Earth'), 'erratum: the printed e = 0.8225 for earth');
eq(lc('ΔV_D,y and Ω stay; TOF and HW4 stay'), 'ΔV_D,y and Ω stay; TOF and HW4 stay');       // symbols and acronyms are never altered (Ω and ω differ!)
process.exit(bad ? 1 : 0);'''
    r = subprocess.run(['node', '-e', js, str(ROOT / 'mathkit/ui/web/textcase.js')], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


# ---------------------------------------------------------------- code export
def scan_matlab(src):
    """MATLAB-aware scan: strings terminate (a quote touching the previous token is the transpose operator) and brackets balance across '...' lines."""
    problems = []; depth = {'(': 0, '[': 0, '{': 0}; pair = {')': '(', ']': '[', '}': '{'}
    for n, line in enumerate(src.splitlines(), 1):
        i, in_str = 0, False
        while i < len(line):
            ch = line[i]
            if in_str:
                if ch == "'":
                    if i + 1 < len(line) and line[i + 1] == "'": i += 2; continue
                    in_str = False
            else:
                if ch == '%' or line[i:i + 3] == '...': break
                if ch == "'":
                    adj = line[i - 1] if i else ''
                    if not (adj and (adj.isalnum() or adj in ")]}'._")): in_str = True
                elif ch in '([{': depth[ch] += 1
                elif ch in ')]}': depth[pair[ch]] -= 1
            i += 1
        if in_str: problems.append((n, 'unterminated string'))
        if not line.rstrip().endswith('...') and any(depth.values()): problems.append((n, f'unbalanced {depth}')); depth = dict.fromkeys(depth, 0)
    return problems


CASES = [('3', 0), ('7', 2), ('12', 2), ('6', 0), ('11', 0)]


@pytest.mark.parametrize('mid,idx', CASES, ids=[f'module{m}' for m, _ in CASES])
def test_code_export_python_runs_and_matlab_is_wellformed(mid, idx, tmp_path):
    p = PRESETS[mid][idx]
    r = api.solve(dict(mid=mid, vals=p.vals, consts=dict(mode=p.consts, moon_R=p.moon_R), theme='light', name='T U', label='T', opts={}))
    assert 'error' not in r
    for si in range(len(r['scenes'])):
        code, _, pyname = api.export(si, 'py', 'light'); ml, _, mname = api.export(si, 'm', 'light')
        assert pyname.endswith('_plots.py') and mname.endswith('_plots.m') and mname[:-2].replace('_', '').isalnum()           # valid MATLAB script name
        f = tmp_path / pyname; f.write_bytes(code)
        run = subprocess.run([sys.executable, str(f)], capture_output=True, text=True, timeout=180, env={**os.environ, 'MPLBACKEND': 'Agg'})
        assert run.returncode == 0, run.stderr[-600:]
        text = ml.decode('utf-8')
        assert scan_matlab(text) == [] and "'Interpreter', 'latex'" in text and 'function plot_scene(is3d, S)' in text and 'evalin' not in text
        assert '$' in code.decode('utf-8')                                                                                    # LaTeX labels are present


# ---------------------------------------------------------------- 3-D page regressions
def test_fps_badge_is_never_stretched_over_the_plot():
    """Regression: '#wrap > div {height:100%}' also matched the FPS badge and covered the whole plot when the FPS monitor was on."""
    from mathkit.view3d.animate import build_html
    p = PRESETS['6'][0]; r = api.solve(dict(mid='6', vals=p.vals, consts=dict(mode=p.consts, moon_R=p.moon_R), theme='dark', name='T', label='T', opts=dict(skip3d=True)))
    from mathkit.registry import MODULES
    from mathkit.presets.runner import full_vals, constants_for
    res = MODULES['6'].run(full_vals(MODULES['6'], p), constants_for(p))
    html = build_html(res.scene, 'dark', 'T', n_frames=120, plotlyjs='/static/plotly.min.js', show_fps=True)
    assert '#wrap>div:not(#fps)' in html and '#wrap>div{' not in html
    assert html.count('id="fps"') == 1 and '"showFps": true' in html
