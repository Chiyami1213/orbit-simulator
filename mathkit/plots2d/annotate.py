"""2-D label placement with collision avoidance.

Labels are placed radially outward from the focus first, then other candidate offsets are tried; the candidate with the least overlap
against (a) already-placed labels and (b) sampled line geometry wins. A second pass re-places any label that still overlaps another.
Leader lines are added when a label ends up far from its anchor.
"""
from __future__ import annotations
import numpy as np


def _overlap_area(b, others):
    if len(others) == 0:
        return 0.0
    ox = np.clip(np.minimum(b[2], others[:, 2]) - np.maximum(b[0], others[:, 0]), 0, None)
    oy = np.clip(np.minimum(b[3], others[:, 3]) - np.maximum(b[1], others[:, 1]), 0, None)
    return float((ox * oy).sum())


def _points_inside(b, P):
    if len(P) == 0:
        return 0
    m = (P[:, 0] >= b[0]) & (P[:, 0] <= b[2]) & (P[:, 1] >= b[1]) & (P[:, 1] <= b[3])
    return int(m.sum())


N_DIR = 24
DISTS = (6, 14, 26, 42, 64, 90, 120, 160, 210)


def place_labels(ax, items, obstacles_data, focus_data, color_ink, fontsize=8.5, leader_color='#898781'):
    """items: list of dict(xy=(x,y) data, text=str, color=hex, pref=(dx,dy) or None). Must be called after the axis limits are final.
    Returns the Text artists (same order as items)."""
    fig = ax.figure; fig.canvas.draw(); rend = fig.canvas.get_renderer(); tr = ax.transData; inv = tr.inverted()
    obst = tr.transform(obstacles_data) if len(obstacles_data) else np.zeros((0, 2))
    ax_bb = ax.get_window_extent(rend); focus_px = tr.transform(np.asarray(focus_data)[:2])
    ang = 2 * np.pi * np.arange(N_DIR) / N_DIR; dirs = np.stack([np.cos(ang), np.sin(ang)], axis=1)
    n = len(items); texts = []; anchors = []; sizes = []; prefs = []
    for it in items:
        anchor = tr.transform(np.asarray(it['xy'])[:2]); anchors.append(anchor)
        t = ax.text(0, 0, it['text'], fontsize=fontsize, color=it['color'], zorder=10, ha='left', va='bottom',
                    bbox=dict(boxstyle='round,pad=0.15', fc=ax.get_facecolor(), ec='none', alpha=0.78))
        texts.append(t)
    fig.canvas.draw()
    for t, anchor, it in zip(texts, anchors, items):
        bb = t.get_window_extent(rend); sizes.append((bb.width, bb.height))
        pref = it.get('pref')
        if pref is None:
            v = anchor - focus_px; nv = np.linalg.norm(v); pref = v / nv if nv > 3 else np.array([0.7, 0.7])
        pref = np.asarray(pref, float); prefs.append(pref / (np.linalg.norm(pref) or 1))

    boxes = [None] * n; dist_used = [0.0] * n; leaders = [None] * n

    def choose(i, others):
        w, h = sizes[i]; anchor = anchors[i]; pref = prefs[i]; O = np.array(others) if others else np.zeros((0, 4))
        order = np.argsort(-(dirs @ pref)); best = (anchor[0] + 6, anchor[1] + 6, 6.0); best_cost = 1e18      # fallback if every candidate is non-finite
        for dist in DISTS:
            for j in order:
                d = dirs[j]
                x = anchor[0] + d[0] * dist - (w if d[0] < -0.3 else (w / 2 if abs(d[0]) <= 0.3 else 0))
                y = anchor[1] + d[1] * dist - (h if d[1] < -0.3 else (h / 2 if abs(d[1]) <= 0.3 else 0))
                b = (x, y, x + w, y + h)
                cost = 400.0 * _overlap_area(b, O) / max(w * h, 1) + 6.0 * _points_inside(b, obst) + 0.12 * dist - 0.8 * float(d @ pref)
                if b[0] < ax_bb.x0 + 2 or b[2] > ax_bb.x1 - 2 or b[1] < ax_bb.y0 + 2 or b[3] > ax_bb.y1 - 2:
                    cost += 600
                if np.isfinite(cost) and cost < best_cost:
                    best, best_cost = (x, y, dist), cost
            if best_cost < 0.12 * dist:            # a clean spot was found at this distance: stop searching farther
                break
        return best

    order = sorted(range(n), key=lambda i: -len(items[i]['text']))
    for i in order:
        x, y, dist = choose(i, [b for b in boxes if b is not None]); boxes[i] = (x, y, x + sizes[i][0], y + sizes[i][1]); dist_used[i] = dist
    # repair pass: re-place any label that still overlaps another
    for _ in range(2):
        for i in order:
            others = [boxes[j] for j in range(n) if j != i]
            if _overlap_area(boxes[i], np.array(others)) > 0:
                x, y, dist = choose(i, others); boxes[i] = (x, y, x + sizes[i][0], y + sizes[i][1]); dist_used[i] = dist
    for i in range(n):
        x, y, x1, y1 = boxes[i]; xd, yd = inv.transform((x, y)); texts[i].set_position((xd, yd))
        if dist_used[i] > 14:
            anchor = anchors[i]; ex = min(max(anchor[0], x), x1); ey = min(max(anchor[1], y), y1)
            a0 = inv.transform(anchor); a1 = inv.transform((ex, ey))
            ax.plot([a0[0], a1[0]], [a0[1], a1[1]], lw=0.6, color=leader_color, zorder=9)
    return texts


def export(fig, path: str, dpi: int = 300):
    fig.savefig(path, dpi=dpi, bbox_inches='tight', facecolor=fig.get_facecolor())
