"""Draw a Scene as an interactive Plotly 3-D figure (static geometry). Animation lives in ``animate.py``."""
from __future__ import annotations
import re
import numpy as np
import plotly.graph_objects as go
from ..scene import Scene, unit
from ..theme import THEMES, color
from .models import has_texture, sphere_mesh


def _line(P, c, name='', width=3, dash=None, text=None, showlegend=True, textpos='top center', legendgroup=None):
    P = np.asarray(P, float)
    kw = dict(x=P[:, 0], y=P[:, 1], z=P[:, 2], mode='lines' + ('+text' if text else ''), name=name or ' ',
              line=dict(color=c, width=width, dash=dash or 'solid'), showlegend=bool(name) and showlegend,
              hoverinfo='name', legendgroup=legendgroup or name or None)
    if text:
        kw['text'] = [text if i == len(P) // 2 else '' for i in range(len(P))]
        kw['textposition'] = textpos; kw['textfont'] = dict(color=c, size=12)
    return go.Scatter3d(**kw)


def _arrow(origin, tip, c, name='', width=5, head_frac=0.12, text=None, showlegend=True):
    """Shaft + 4-prong head built from lines (deterministic geometry, no cone sizing surprises)."""
    origin = np.asarray(origin, float); tip = np.asarray(tip, float); d = tip - origin; L = np.linalg.norm(d)
    traces = []
    if L == 0: return traces
    u = d / L
    a = np.array([1.0, 0, 0]) if abs(u[0]) < 0.9 else np.array([0, 1.0, 0]); p1 = unit(np.cross(u, a)); p2 = np.cross(u, p1)
    h = head_frac * L; xs, ys, zs = [origin[0], tip[0]], [origin[1], tip[1]], [origin[2], tip[2]]
    for k in range(4):
        pp = p1 if k % 2 == 0 else p2; sgn = 1 if k < 2 else -1
        b = tip - h * u + 0.45 * h * sgn * pp
        xs += [None, tip[0], b[0]]; ys += [None, tip[1], b[1]]; zs += [None, tip[2], b[2]]
    kw = dict(x=xs, y=ys, z=zs, mode='lines+text' if text else 'lines', line=dict(color=c, width=width), name=name or text or ' ',
              showlegend=bool(name) and showlegend, hoverinfo='name', legendgroup=name or None)
    if text:
        kw['text'] = [''] * len(xs); kw['text'][1] = text; kw['textposition'] = 'top center'; kw['textfont'] = dict(color=c, size=12)
    traces.append(go.Scatter3d(**kw)); return traces


def legend_dot(name, c, symbol='circle'):
    """A legend-only marker, so the legend shows a plain circle instead of the mesh's odd icon."""
    return go.Scatter3d(x=[None], y=[None], z=[None], mode='markers', marker=dict(size=8, color=c, symbol=symbol, line=dict(width=0)), name=name, showlegend=True, hoverinfo='skip')


def sphere(center, radius, c, n=28, name=''):
    u = np.linspace(0, 2 * np.pi, n); v = np.linspace(0, np.pi, n // 2 + 1)
    x = center[0] + radius * np.outer(np.cos(u), np.sin(v)); y = center[1] + radius * np.outer(np.sin(u), np.sin(v))
    z = center[2] + radius * np.outer(np.ones_like(u), np.cos(v))
    return go.Surface(x=x, y=y, z=z, showscale=False, opacity=0.95, colorscale=[[0, c], [1, c]], name=name or 'body',
                      hoverinfo='name', showlegend=False, lighting=dict(ambient=0.75, diffuse=0.5))


LABEL_POS = ['top center', 'bottom center', 'middle right', 'middle left', 'top right', 'top left', 'bottom right', 'bottom left']
ANCHOR = {'top center': ('center', 'bottom', 0, 9), 'bottom center': ('center', 'top', 0, -9), 'middle right': ('left', 'middle', 12, 0), 'middle left': ('right', 'middle', -12, 0),
          'top right': ('left', 'bottom', 10, 10), 'top left': ('right', 'bottom', -10, 10), 'bottom right': ('left', 'top', 10, -10), 'bottom left': ('right', 'top', -10, -10)}
BODY_NAMES = {'⊕': 'earth', '☉': 'sun', '☽': 'moon', '☿': 'mercury', '♀': 'venus', '♂': 'mars', '♃': 'jupiter', '♄': 'saturn', '♅': 'uranus', '♆': 'neptune', '♇': 'pluto'}


def html_label(text: str, body: str = 'symbol') -> str:
    """Plotly annotation HTML with real sub/superscripts: v_D -> v<sub>D</sub>, a^2 -> a<sup>2</sup>; body marks as symbol or name subscript."""
    s_ = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    if body == 'name':
        s_ = re.sub('([' + ''.join(BODY_NAMES) + '])', lambda m: '<sub>' + BODY_NAMES[m.group(1)] + '</sub>', s_)
    s_ = re.sub(r'_\{([^}]*)\}', r'<sub>\1</sub>', s_); s_ = re.sub(r'_([A-Za-z0-9]+)', r'<sub>\1</sub>', s_)
    s_ = re.sub(r'\^\{([^}]*)\}', r'<sup>\1</sup>', s_); s_ = re.sub(r'\^([A-Za-z0-9+\-]+)', r'<sup>\1</sup>', s_)
    return s_


def stagger_labels(labels, thr):
    """labels: [(pos(3), text, color)]. Anchors closer than ``thr`` form a cluster; each member of a cluster gets a different Plotly
    ``textposition`` (top, bottom, right, left, diagonals), so labels on (almost) coincident points never print on top of each other
    whatever the camera angle. Returns [(pos, text, color, textposition)]."""
    clusters = []
    for pos, text, c in labels:
        pos = np.asarray(pos, float)
        for cl in clusters:
            if np.linalg.norm(cl['pos'] - pos) < thr: cl['items'].append((pos, text, c)); break
        else: clusters.append(dict(pos=pos, items=[(pos, text, c)]))
    out = []
    for cl in clusters:
        for k, (pos, text, c) in enumerate(cl['items']): out.append((pos, text, c, LABEL_POS[k % len(LABEL_POS)]))
    return out


def build_figure(sc: Scene, theme: str = 'light', user_name: str = '', body: str = 'symbol', textures: bool = False) -> tuple[go.Figure, dict]:
    T = THEMES[theme]; fig = go.Figure(); col = lambda r: color(theme, r)
    ext = sc.extent(); allp = []; labs = []; spin = None

    for d in sc.disks:
        if textures and d.body and has_texture(d.body):                       # real surface map sampled onto a sphere mesh
            x, y, z, i, j, k, colors = sphere_mesh(d.body, 80, 40)                                  # a slightly lighter mesh: it is redrawn while it spins
            fig.add_trace(go.Mesh3d(x=d.center[0] + d.radius * x, y=d.center[1] + d.radius * y, z=d.center[2] + d.radius * z, i=i, j=j, k=k, vertexcolor=colors,
                                    flatshading=False, lighting=dict(ambient=0.95, diffuse=0.3, specular=0.0), name=d.body, showlegend=False, hoverinfo='name'))
            fig.add_trace(legend_dot(d.body, T['body']))
            from ..spin import spin_for
            sp = spin_for(d.body)
            if sp and spin is None: spin = dict(idx=len(fig.data) - 2, x=np.round(x, 5).tolist(), y=np.round(y, 5).tolist(), z=np.round(z, 5).tolist(), c=[float(v) for v in d.center], R=float(d.radius), rate=float(sp['rate']), name=d.body)
        else:
            fig.add_trace(sphere(d.center, d.radius, T['body'], name=d.label or 'central body'))
            fig.add_trace(legend_dot(d.label or 'central body', T['body']))
    for o in sc.orbits:
        P = o.sample(721); allp.append(P)
        ths = o.label_ths if o.label_ths is not None else 0
        fig.add_trace(_line(P, col(o.role), o.name, 4, 'dash' if o.dash else None))
    for p in sc.polys:
        fig.add_trace(_line(p.pts, col(p.role), p.label, max(2, p.width * 2), 'dash' if p.dash else None, showlegend=bool(p.label)))
    for l in sc.lines:
        P = np.array([l.p0, l.p1]); allp.append(P)
        fig.add_trace(_line(P, col(l.role), l.label, max(2, l.width * 2), 'dash' if l.dash else None))
    for a in sc.arcs:
        pts, ang = a.points()
        if ang == 0: continue
        fig.add_trace(_line(pts, col(a.role), '', 3, None))
        if a.label: labs.append((pts[len(pts) // 2], a.label, col(a.role)))
    for v in sc.vecs:
        tip = v.origin + v.vec * v.scale; allp.append(np.array([v.origin, tip]))
        for t in _arrow(v.origin, tip, col(v.role), v.label, 6, showlegend=True): fig.add_trace(t)
    for t in sc.triads:
        for k in range(3):
            tip = t.origin + t.length * t.axes[:, k]; labs.append((tip, t.names[k], col(t.role)))
            for tr in _arrow(t.origin, tip, col(t.role), '', 3): fig.add_trace(tr)
    for p in sc.pts:
        allp.append(np.atleast_2d(p.pos))
        sym = {'o': 'circle', 'x': 'x', 'D': 'diamond', '+': 'cross', 's': 'square'}.get(p.marker, 'circle')
        c = T['ink'] if p.role == 'ink' else col(p.role)
        fig.add_trace(go.Scatter3d(x=[p.pos[0]], y=[p.pos[1]], z=[p.pos[2]], mode='markers', marker=dict(size=max(3, p.size * 0.8), color=c, symbol=sym),
                                   name=p.label or 'point', showlegend=False, hoverinfo='name'))
        if p.label: labs.append((p.pos, p.label, c))
    for pl in sc.planes:
        s = pl.size; n = unit(pl.normal); a = np.array([1.0, 0, 0]) if abs(n[0]) < 0.9 else np.array([0, 1.0, 0])
        e1 = unit(np.cross(n, a)); e2 = np.cross(n, e1)
        C = [pl.center + s * (sx * e1 + sy * e2) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        C = np.array(C)
        fig.add_trace(go.Mesh3d(x=C[:, 0], y=C[:, 1], z=C[:, 2], i=[0, 0], j=[1, 2], k=[2, 3], opacity=0.10, color=T['muted'],
                                name=pl.label or 'plane', showlegend=bool(pl.label), hoverinfo='name'))
    track_idx = []
    for tr in sc.tracks:
        p0 = tr.fn(0.0); c = col(tr.role)
        fig.add_trace(go.Scatter3d(x=[p0[0]], y=[p0[1]], z=[p0[2]], mode='lines', line=dict(color=c, width=7),
                                   name=f'{tr.name} trail', showlegend=False, hoverinfo='skip'))
        fig.add_trace(go.Scatter3d(x=[p0[0]], y=[p0[1]], z=[p0[2]], mode='markers', marker=dict(size=8, color=c, line=dict(color=T['surface'], width=2)),
                                   name=tr.name, showlegend=True, hoverinfo='name'))
        track_idx.append((len(fig.data) - 2, len(fig.data) - 1))

    P = np.vstack(allp) if allp else np.array([[-ext, -ext, -ext], [ext, ext, ext]])
    P = P[np.all(np.isfinite(P), axis=1)]
    ctr = (P.min(axis=0) + P.max(axis=0)) / 2; half = float(np.max(P.max(axis=0) - P.min(axis=0))) / 2 * 1.1 or 1.0
    annots = []                                             # labels: scene annotations (HTML overlay) are never clipped by the axis panes
    for pos, text, c, tp in stagger_labels(labs, 0.12 * half):
        xa, ya, xs, ys = ANCHOR[tp]
        annots.append(dict(x=float(pos[0]), y=float(pos[1]), z=float(pos[2]), text=html_label(text, body), showarrow=False, xanchor=xa, yanchor=ya, xshift=xs, yshift=ys,
                           font=dict(color=c, size=12), bgcolor='rgba(0,0,0,0)', captureevents=False))
    ax = lambda c0, title: dict(range=[c0 - half, c0 + half], title=title, color=T['ink2'], gridcolor=T['grid'], zerolinecolor=T['axis'],
                                backgroundcolor=T['surface'], showbackground=True)
    ttl = f'{user_name} — {sc.label}: {sc.title}' if user_name else f'{sc.label}: {sc.title}'
    fig.update_layout(title=dict(text=ttl.strip(' —:'), font=dict(color=T['ink'], size=13), x=0.01),
                      scene=dict(xaxis=ax(ctr[0], f'x ({sc.units})'), yaxis=ax(ctr[1], f'y ({sc.units})'), zaxis=ax(ctr[2], f'z ({sc.units})'),
                                 aspectmode='cube', annotations=annots, camera=dict(eye=dict(x=1.1, y=-1.1, z=0.78))),
                      paper_bgcolor=T['surface'], plot_bgcolor=T['surface'], font=dict(color=T['ink2']), margin=dict(l=0, r=0, t=34, b=0),
                      legend=dict(font=dict(color=T['ink2'], size=11), bgcolor='rgba(0,0,0,0)', orientation='h', x=0.0, y=-0.02, yanchor='top', itemsizing='constant', tracegroupgap=0), uirevision='keep', autosize=True)
    return fig, dict(track_idx=track_idx, n_labels=len(annots), center=ctr.tolist(), half=half, spin=spin)
