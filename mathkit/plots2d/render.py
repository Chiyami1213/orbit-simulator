"""Draw a Scene as a Cartesian, equal-axis matplotlib figure (never polar)."""
from __future__ import annotations
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch
from ..scene import Scene
from ..ui.latex import tex

plt.rcParams.update({'mathtext.fontset': 'cm', 'mathtext.fallback': 'stixsans'})       # LaTeX look for all maths in figures
from ..theme import THEMES, color
from .annotate import place_labels


def _proj(sc: Scene, X):
    X = np.asarray(X, float); e1, e2 = sc.plane2d
    return np.stack([X @ e1, X @ e2], axis=-1)


def _clip(p0, p1, xlim, ylim):
    """Liang-Barsky clip of segment p0-p1 to the view box; returns (q0, q1) or None."""
    d = p1 - p0; t0, t1 = 0.0, 1.0
    for pk, qk in ((-d[0], p0[0] - xlim[0]), (d[0], xlim[1] - p0[0]), (-d[1], p0[1] - ylim[0]), (d[1], ylim[1] - p0[1])):
        if abs(pk) < 1e-15:
            if qk < 0: return None
        else:
            t = qk / pk
            if pk < 0: t0 = max(t0, t)
            else: t1 = min(t1, t)
    if t0 >= t1: return None
    return p0 + t0 * d, p0 + t1 * d


def render(sc: Scene, theme: str = 'light', user_name: str = '', figsize=(8.2, 7.2), show_labels=True, body: str = 'symbol'):
    T = THEMES[theme]
    fig, ax = plt.subplots(figsize=figsize, facecolor=T['surface'])
    ax.set_facecolor(T['surface']); ax.set_aspect('equal', adjustable='box')
    for s in ax.spines.values():
        s.set_color(T['axis'])
    ax.tick_params(colors=T['muted'], labelsize=8); ax.grid(True, color=T['grid'], lw=0.6)
    ax.set_xlabel(f'x ({sc.units})', color=T['ink2']); ax.set_ylabel(f'y ({sc.units})', color=T['ink2'])
    col = lambda r: color(theme, r) if r not in ('body',) else T['body']

    bounds = []                      # geometry that sets the view limits
    obstacles = []                   # geometry labels should avoid
    items = []                       # labels to place
    line_labels = []                 # (p0, p1, Line): placed after the view limits are known

    def seg(p0, p1, n=60):
        return _proj(sc, np.linspace(p0, p1, n))

    # --- bodies / focus ---
    for d in sc.disks:
        c = _proj(sc, d.center)
        ax.add_patch(Circle(c, d.radius, fc=T['body'], ec=T['axis'], lw=0.8, zorder=1))
        bounds += [c + d.radius, c - d.radius]
    # --- planes are 3-D only ---
    # --- orbits ---
    for o in sc.orbits:
        P = _proj(sc, o.sample(721)); c = col(o.role)
        ax.plot(P[:, 0], P[:, 1], color=c, lw=1.8, ls='--' if o.dash else '-', zorder=3)
        bounds.append(P); obstacles.append(P)
        if o.name:
            ths = o.label_ths if o.label_ths is not None else (0 if o.e >= 1 else 180)
            if o.ths_range is not None and o.label_ths is None:
                a0, a1 = o.ths_range; ths = (a0 + (a1 + (360 if a1 < a0 else 0) - a0) / 2)
            items.append(dict(xy=_proj(sc, o.pos(ths)), text=o.name, color=c))
    # --- polylines ---
    for p in sc.polys:
        P = _proj(sc, p.pts); ax.plot(P[:, 0], P[:, 1], color=col(p.role), lw=p.width, ls='--' if p.dash else '-', zorder=2)
        obstacles.append(P)
        if p.role not in ('muted',): bounds.append(P)
        else: bounds.append(P)
        if p.label: items.append(dict(xy=P[int(p.label_frac * (len(P) - 1))], text=p.label, color=T['muted']))
    # --- lines ---
    for l in sc.lines:
        P = seg(l.p0, l.p1)
        ax.plot(P[:, 0], P[:, 1], color=col(l.role), lw=l.width, ls='--' if l.dash else '-', zorder=2)
        obstacles.append(P[::3])
        if l.label: line_labels.append((_proj(sc, l.p0), _proj(sc, l.p1), l))
    # --- arcs (angle marks) ---
    for a in sc.arcs:
        if a.only3d: continue
        pts, ang = a.points()
        if ang == 0: continue
        P = _proj(sc, pts)
        ax.plot(P[:, 0], P[:, 1], color=col(a.role), lw=1.2, zorder=4); obstacles.append(P); bounds.append(P)
        if a.label: items.append(dict(xy=P[len(P) // 2], text=a.label, color=col(a.role)))
    # --- vectors ---
    for v in sc.vecs:
        o = _proj(sc, v.origin); tip = _proj(sc, v.origin + v.vec * v.scale)
        ar = FancyArrowPatch(o, tip, arrowstyle='-|>', mutation_scale=11, lw=1.6, color=col(v.role), zorder=5,
                             ls='--' if v.dash else '-', shrinkA=0, shrinkB=0)
        ax.add_patch(ar); bounds += [o, tip]; obstacles.append(np.linspace(o, tip, 25))
        if v.label: items.append(dict(xy=tip, text=v.label, color=col(v.role)))
    # --- triads ---
    for t in sc.triads:
        if t.only3d: continue
        o = _proj(sc, t.origin)
        for k in range(3):
            tip = _proj(sc, t.origin + t.length * t.axes[:, k])
            if np.linalg.norm(tip - o) < 0.25 * t.length: continue
            ax.add_patch(FancyArrowPatch(o, tip, arrowstyle='-|>', mutation_scale=9, lw=1.1, color=col(t.role), zorder=4,
                                         shrinkA=0, shrinkB=0))
            bounds += [tip]; obstacles.append(np.linspace(o, tip, 15))
            items.append(dict(xy=tip, text=t.names[k], color=col(t.role)))
    # --- points ---
    for p in sc.pts:
        P = _proj(sc, p.pos); c = col(p.role) if p.role != 'ink' else T['ink']
        ax.plot([P[0]], [P[1]], marker=p.marker, ms=p.size, color=c, mec=c if p.marker in 'x+' else T['surface'], mew=1.6 if p.marker in 'x+' else 0.8, ls='none', zorder=6)
        bounds.append(P); obstacles.append(np.atleast_2d(P))
        if p.label: items.append(dict(xy=P, text=p.label, color=T['ink'] if p.role == 'ink' else col(p.role)))

    B = np.vstack([np.atleast_2d(b) for b in bounds]) if bounds else np.array([[-1, -1], [1, 1]])
    B = B[np.all(np.isfinite(B), axis=1)]
    lo, hi = B.min(axis=0), B.max(axis=0); ctr = (lo + hi) / 2; half = float(np.max(hi - lo)) / 2 * 1.22 or 1.0
    ax.set_xlim(ctr[0] - half, ctr[0] + half); ax.set_ylim(ctr[1] - half, ctr[1] + half)
    for q0, q1, l in line_labels:          # clip each labelled line to the view so its label stays on screen
        c = _clip(q0, q1, ax.get_xlim(), ax.get_ylim())
        if c is not None:
            xy = c[0] + l.label_frac * (c[1] - c[0])
            items.append(dict(xy=xy, text=l.label, color=T['muted'] if l.role == 'muted' else col(l.role)))
    ttl = f'{user_name} — {sc.label}: {sc.title}' if user_name else f'{sc.label}: {sc.title}'
    ax.set_title(tex(ttl.strip(' —:'), body), color=T['ink'], fontsize=11, loc='left')
    for it in items: it['text'] = tex(it['text'], body)               # symbols / subscripts -> real LaTeX ($a_{\mathrm{tot}}$, $\bar{r}$ ...)
    if show_labels and items:
        obs = np.vstack([np.atleast_2d(o) for o in obstacles]) if obstacles else np.zeros((0, 2))
        texts = place_labels(ax, items, obs, _proj(sc, np.zeros(3)), T['ink'])
        fig.tight_layout(); fig.canvas.draw(); rend = fig.canvas.get_renderer()
        bbs = [t.get_window_extent(rend) for t in texts if t is not None]
        fig.label_overlaps = sum(1 for i in range(len(bbs)) for j in range(i + 1, len(bbs)) if bbs[i].overlaps(bbs[j]))
        fig.n_labels = len(bbs)
    else:
        fig.tight_layout(); fig.label_overlaps = 0; fig.n_labels = 0
    return fig
