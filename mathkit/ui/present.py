"""Presentation helpers: number formatting, summary cards and comparison tables for the UI (pure functions of a Result)."""
from __future__ import annotations
import numpy as np
from ..results import Result, NONE


def num(v, sig: int = 5) -> str:
    if isinstance(v, str): return v
    if isinstance(v, (bool, np.bool_)): return 'yes' if v else 'no'
    v = float(v)
    if v == 0: return '0'
    if not np.isfinite(v): return str(v)
    a = abs(v)
    if a >= 1e7: return f'{v:.4e}'
    if a >= 1000: return f'{v:,.1f}'
    if a >= 1e-3: return f'{v:.{sig}g}'
    return f'{v:.3e}'


def with_units(v, units: str = '') -> str:
    s = num(v)
    if not units or units == NONE or isinstance(v, str): return s
    return s + units if units == '°' else f'{s} {units}'


def card(title, rows, headline=None, pill=None):
    return dict(title=title, headline=headline, pill=pill, rows=[[a, b] for a, b in rows])


def _scalar_steps(res: Result):
    out = {}
    for s in res.steps:
        if isinstance(s.value, (list, tuple, np.ndarray)): continue
        out.setdefault(s.group, []).append(s)
    return out


def cards_lambert(res: Result):
    sel = res.data['sel']; rows = res.data['rows']; first = next(iter(rows.values()))
    e = sel['e']; a = sel['a']; rp = sel['p'] / (1 + e)
    t = []
    if 'tof_par' in first: t.append(('TOF_par / TOF_min', f"{first['tof_par'] / 3600:.3f} / {first['tof_min'] / 3600:.3f} h"))
    elif 'tof' in sel: t.append(('TOF_min', f"{sel['tof'] / 3600:.3f} h"))
    t += [('a', with_units(a, 'km')), ('p', with_units(sel['p'], 'km')), ('e', num(e)), ('r_p', with_units(rp, 'km'))]
    cs = [card('Type', t, pill=str(sel.get('cls', '—')))]
    cs.append(card('Departure v_D', [('γ_D', with_units(sel['gD'], '°')), ('θ*_D', with_units(sel['thD'], '°')), ('|Δv_D|', with_units(sel['dvD_mag'], 'km·s⁻¹')),
                                     ('α_D', with_units(sel['alphaD'], '°'))], headline=with_units(sel['vD_mag'], 'km·s⁻¹')))
    cs.append(card('Arrival v_A', [('γ_A', with_units(sel['gA'], '°')), ('θ*_A', with_units(sel['thA'], '°')), ('|Δv_A|', with_units(sel['dvA_mag'], 'km·s⁻¹')),
                                   ('α_A', with_units(sel['alphaA'], '°'))], headline=with_units(sel['vA_mag'], 'km·s⁻¹')))
    tot = []
    if len(rows) == 2:
        key = [k for k in rows if rows[k] is not sel][0]; o = rows[key]; tot.append((f"Other root (p = {num(o['p'], 5)})", dict(pill=f"{o['dv_total']:.3f}")))
    tot.append(('Phase angle at D', with_units(res.data['psi'], '°') if 'psi' in res.data else '—'))
    tot.append(('Passes periapsis?', 'yes' if sel.get('passes_periapsis') else 'no'))
    tot.append(('Vacant focus F', f"2ae = {num(2 * abs(a) * e)} km from O"))
    cs.append(card('Total Δv', tot, headline=with_units(sel['dv_total'], 'km·s⁻¹')))
    return cs


def summary_cards(mid: str, res: Result):
    try:
        if mid == '12': return cards_lambert(res)
    except Exception:
        pass
    cs = []
    for g, steps in list(_scalar_steps(res).items())[:4]:
        rows = [(s.symbol or s.name, with_units(s.value, s.units)) for s in steps[:7]]
        if rows: cs.append(card(g or 'Results', rows))
    return cs


def extra_tabs(mid: str, res: Result):
    """Comparison tables shown as extra tabs (Both roots / All intersections / Both senses)."""
    out = []
    d = res.data
    if mid == '12' and 'rows' in d and len(d['rows']) >= 2:
        names = list(d['rows']); cols = ['Quantity'] + [f'{k} p' if k in ('small', 'large') else k for k in names]
        sel = d['sel']; items = [('Class', lambda r: r.get('cls', '—')), ('p (km)', lambda r: num(r['p'])), ('a (km)', lambda r: num(r['a'])), ('e', lambda r: num(r['e'])),
                                 ('r_p (km)', lambda r: num(r['p'] / (1 + r['e']))), ('v_D (km·s⁻¹)', lambda r: num(r['vD_mag'])), ('v_A (km·s⁻¹)', lambda r: num(r['vA_mag'])),
                                 ('|Δv_D| (km·s⁻¹)', lambda r: num(r['dvD_mag'])), ('α_D (°)', lambda r: num(r['alphaD'])), ('|Δv_A| (km·s⁻¹)', lambda r: num(r['dvA_mag'])),
                                 ('α_A (°)', lambda r: num(r['alphaA'])), ('Total Δv (km·s⁻¹)', lambda r: num(r['dv_total'])), ('Passes periapsis?', lambda r: 'yes' if r.get('passes_periapsis') else 'no')]
        best = min(names, key=lambda k: d['rows'][k]['dv_total'])
        rows = [[lab] + [f(d['rows'][k]) for k in names] for lab, f in items]
        out.append(dict(name='Both roots', note=f'Smaller total Δv: {best} p root. Check r_p against the body radius for each root.', columns=cols, rows=rows,
                        highlight=1 + names.index(best)))
    if mid == '7' and 'intersections' in d and d['intersections']:
        cols = ['θ*₁ (°)', 'r (km)', 'v⁻ (km·s⁻¹)', 'v⁺ (km·s⁻¹)', 'γ⁻ (°)', 'γ⁺ (°)', 'Δγ (°)', 'Δv (km·s⁻¹)', 'α (°)', '% energy']
        rows = [[num(x['th1']), num(x['r']), num(x['v1']), num(x['v2']), num(x['g1']), num(x['g2']), num(x['dgamma']), num(x['dv']), num(x['alpha']), num(x['pct_energy'])]
                for x in d['intersections']]
        out.append(dict(name='All intersections', note='The minimum |Δv̄| crossing is highlighted.', columns=cols, rows=rows,
                        highlight=[i for i, x in enumerate(d['intersections']) if x is d['best']][0]))
    if mid == '11' and 'outs' in d:
        cols = ['Rotation', 'Energy', 'v∞⁺', 'v⁺ (km·s⁻¹)', 'γ⁺ (°)', 'e⁺', 'a⁺ (km)', 'r_p⁺ (km)', 'Δω (°)', 'Δv_eq (km·s⁻¹)', 'α_eq (°)']
        rows = []
        for sn, o in d['outs'].items():
            c = o['c']; rows.append(['counter-clockwise' if sn > 0 else 'clockwise', o['kind'], num(np.linalg.norm(o['fb']['vinf_plus'])), num(np.linalg.norm(o['fb']['v_plus'])),
                                     num(c['gamma']), num(c['e']), num(c['a']), num(c['p'] / (1 + c['e'])), num(o['dw']), num(o['imp']['dv']), num(o['imp']['alpha'])])
        out.append(dict(name='Both senses', note='Passing behind the planet gains heliocentric energy; passing ahead loses it.', columns=cols, rows=rows, highlight=list(d['outs']).index(d['pick'])))
    return out
