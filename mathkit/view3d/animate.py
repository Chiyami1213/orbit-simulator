"""Interactive 3-D animation page: Plotly figure + play/pause, 0.1x-10x speed, time scrubber, view presets, auto-rotate, label/legend toggles,
a live t / r / v / gamma / theta* readout and an optional FPS monitor.

Frames are placed by solving Kepler's equation in Python (each Track.fn) at N equally spaced *times* (N = the animation resolution chosen in
the settings), so motion is uniform in time. The browser interpolates between those samples against a wall-clock time base, so the speed slider
rescales time continuously and a higher resolution only makes the path smoother. To stay smooth at high resolutions the page sends ONE batched
Plotly update per frame, draws trails from a decimated copy (<= 300 points), and refreshes them at ~12 Hz.
"""
from __future__ import annotations
import json
import numpy as np
import plotly.graph_objects as go
from ..scene import Scene, unit
from ..theme import THEMES
from .scene import build_figure
from .models import spacecraft_mesh, MODELS

MAX_FRAMES = 6000


def _round(a, nd=3):
    return np.round(np.asarray(a, float), nd).tolist()


def sample_tracks(sc: Scene, n: int = 480) -> dict:
    n = int(max(60, min(MAX_FRAMES, n))); T = sc.duration_s or 1.0; times = np.linspace(0.0, T, n); out = []
    for tr in sc.tracks:
        P = np.array([tr.fn(t) for t in times]); st = {}
        if tr.state is not None:
            S = [tr.state(t) for t in times]
            st = {k: _round([s[k] for s in S], 4) for k in S[0]}
        out.append(dict(name=tr.name, xyz=[_round(P[:, 0]), _round(P[:, 1]), _round(P[:, 2])], state=st))
    return dict(times=_round(times, 3), duration=T, tracks=out)


def view_presets(sc: Scene) -> dict:
    """Camera eye/up for: orbit-normal, along line of nodes, isometric. Based on the first orbit's plane."""
    Q = sc.orbits[0].Q if sc.orbits else np.eye(3); h = unit(Q[:, 2]); e = unit(Q[:, 0])
    node = np.cross([0, 0, 1.0], h); node = unit(node) if np.linalg.norm(node) > 1e-9 else np.array([1.0, 0, 0])
    k = 1.7
    return dict(normal=dict(eye=(k * h).tolist(), up=e.tolist()), nodes=dict(eye=(k * node).tolist(), up=[0, 0, 1]), iso=dict(eye=[1.1, -1.1, 0.78], up=[0, 0, 1]))


_CSS = """
html,body{height:100%%;margin:0;overflow:hidden}
body{display:flex;flex-direction:column;background:%(surface)s;color:%(ink)s;font-family:system-ui,-apple-system,'Segoe UI',sans-serif;font-size:12.5px}
::-webkit-scrollbar{display:none}*{scrollbar-width:none}
#bar{flex:none;display:flex;flex-wrap:wrap;gap:6px 12px;align-items:center;padding:6px 8px;border-bottom:1px solid %(grid)s;color:%(ink2)s}
button{background:%(surface)s;color:%(ink)s;border:1px solid %(axis)s;border-radius:6px;padding:3px 9px;cursor:pointer;font:inherit}
button:hover{background:%(grid)s} button.on{background:%(accent)s;color:#fff;border-color:%(accent)s}
#legendbar{flex:none;display:flex;flex-wrap:wrap;gap:4px 16px;padding:6px 10px;border-top:1px solid %(grid)s;color:%(ink2)s;font-size:13px;line-height:1.5}
.lg{display:flex;align-items:center;gap:7px;cursor:pointer;user-select:none}.lg.off{opacity:.35}.lg .sw{display:inline-block;width:26px;height:0;border-top:4px solid}.lg .sw.dot{width:11px;height:11px;border:0;border-radius:50%%}
.lg .katex{font-size:1.08em;color:%(ink)s}
input[type=range]{vertical-align:middle;accent-color:%(accent)s} label{white-space:nowrap}
#readout{flex:none;display:flex;flex-wrap:wrap;gap:4px 16px;padding:4px 8px;font-variant-numeric:tabular-nums;border-bottom:1px solid %(grid)s}
#readout b{color:%(ink)s;font-weight:600} #readout span{color:%(ink2)s}
#scrub{width:130px}#speed{width:90px}
#wrap{flex:1;min-height:0;position:relative;overflow:hidden}#wrap>div:not(#fps){height:100%%!important;width:100%%!important}.plotly-graph-div{height:100%%!important;width:100%%!important}
#fps{position:absolute;right:8px;top:6px;z-index:5;background:%(surface)s;border:1px solid %(axis)s;border-radius:6px;padding:2px 8px;font-variant-numeric:tabular-nums;color:%(ink2)s;display:none}
"""

_JS = r"""
const D = __DATA__, V = D.views, N = D.times.length, TR = D.tracks, IDX = D.idx;
const gd = document.getElementById('plot'); let t = 0, playing = false, speed = 1, last = null, auto = false, phi = 0, dirty = true;
let eye0 = {x:1.1,y:-1.1,z:0.78}; const $ = id => document.getElementById(id);
const fmt = (x, d=4) => { const a = Math.abs(x); if (a >= 1e7) return x.toExponential(3); if (a >= 1000) return x.toLocaleString('en-US', {maximumFractionDigits: 1}); if (a >= 1) return x.toFixed(3); return Number(x).toPrecision(d); };
function interp(arr, f){ const i = Math.min(N-2, Math.floor(f)), w = f - i; return arr[i]*(1-w) + arr[i+1]*w; }
const STRIDE = TR.map(() => Math.max(1, Math.ceil(N / 300)));           // trails are drawn from a decimated copy: smooth at any resolution
let lastTrail = 0;
const norm = v => { const n = Math.hypot(v[0], v[1], v[2]) || 1; return [v[0]/n, v[1]/n, v[2]/n]; };
const cross = (a, b) => [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]];
function modelVerts(f){                                                  // orient the satellite along the velocity, keep its "up" on the orbit normal
  const i = Math.min(N-2, Math.floor(f)), tr = TR[0], p = [0,1,2].map(a => interp(tr.xyz[a], f)), p1 = [0,1,2].map(a => tr.xyz[a][i+1]), p0 = [0,1,2].map(a => tr.xyz[a][i]);
  const fwd = norm([p1[0]-p0[0], p1[1]-p0[1], p1[2]-p0[2]]); let up = norm(cross(p, fwd)); if (!isFinite(up[0]) || Math.hypot(...cross(p, fwd)) < 1e-9) up = [0,0,1];
  const right = norm(cross(fwd, up)); up = cross(right, fwd), S = D.model.scale, M = D.model, X = [], Y = [], Z = [];
  for (let k = 0; k < M.x.length; k++) { const a = M.x[k], b = M.y[k], c = M.z[k];
    X.push(p[0] + S*(a*fwd[0] + b*right[0] + c*up[0])); Y.push(p[1] + S*(a*fwd[1] + b*right[1] + c*up[1])); Z.push(p[2] + S*(a*fwd[2] + b*right[2] + c*up[2])); }
  return [X, Y, Z];
}
function render(withTrail){
  const f = D.duration > 0 ? (t / D.duration) * (N-1) : 0; const k = Math.min(N-1, Math.floor(f)), X = [], Y = [], Z = [], ids = [];
  TR.forEach((tr, j) => { const x = interp(tr.xyz[0], f), y = interp(tr.xyz[1], f), z = interp(tr.xyz[2], f); X.push([x]); Y.push([y]); Z.push([z]); ids.push(IDX[j][1]); });
  if (withTrail) TR.forEach((tr, j) => { const xs = [], ys = [], zs = []; for (let i = 0; i <= k; i += STRIDE[j]) { xs.push(tr.xyz[0][i]); ys.push(tr.xyz[1][i]); zs.push(tr.xyz[2][i]); }
    xs.push(X[j][0]); ys.push(Y[j][0]); zs.push(Z[j][0]); X.push(xs); Y.push(ys); Z.push(zs); ids.push(IDX[j][0]); });
  if (D.model && TR.length) { const m = modelVerts(f); X.push(m[0]); Y.push(m[1]); Z.push(m[2]); ids.push(D.model.idx); }
  if (ids.length) Plotly.restyle(gd, {x: X, y: Y, z: Z}, ids);                                       // ONE batched update per frame
  $('scrub').value = D.duration > 0 ? 1000 * t / D.duration : 0;
  const s = TR.length && TR[0].state && TR[0].state.r ? TR[0].state : null; $('r_t').textContent = fmt(t) + ' s  (' + fmt(t/3600) + ' h)';
  if (s){ $('r_r').textContent = fmt(interp(s.r,f)) + ' km'; $('r_v').textContent = fmt(interp(s.v,f)) + ' km/s'; $('r_g').textContent = fmt(interp(s.gamma,f)) + ' °';
          const a = s.ths, i = Math.min(N-2, Math.floor(f)); let d = a[i+1]-a[i]; if (d>180) d -= 360; if (d<-180) d += 360; let th = a[i] + d*(f-i); th = ((th%360)+360)%360; $('r_th').textContent = th.toFixed(3) + ' °'; }
  dirty = false;
}
function rotateCam(){ phi += 0.006; const c = Math.cos(phi), s = Math.sin(phi); Plotly.relayout(gd, {'scene.camera.eye': {x: eye0.x*c - eye0.y*s, y: eye0.x*s + eye0.y*c, z: eye0.z}}); }
let frames = 0, fpsT = performance.now();
// Rotating or zooming while the animation plays: every frame restyles the scene, which resets the camera under the mouse. So frames are held back while you drag, scroll or pinch, and resume the moment you let go.
let busy = false, busyUntil = 0;
gd.addEventListener('pointerdown', () => { busy = true; }, true);
for (const ev of ['pointerup', 'pointercancel', 'lostpointercapture']) { window.addEventListener(ev, () => { busy = false; busyUntil = performance.now() + 120; }, true); }
gd.addEventListener('wheel', () => { busyUntil = performance.now() + 450; }, {capture: true, passive: true});
gd.addEventListener('touchstart', () => { busy = true; }, {capture: true, passive: true}); gd.addEventListener('touchend', () => { busy = false; busyUntil = performance.now() + 150; }, true);
function loop(now){
  if (playing){ if (last !== null && D.duration > 0){ t += (now-last)/1000 * (D.duration/20) * speed; if (t > D.duration){ if (D.repeat) t -= D.duration; else { t = D.duration; playing = false; $('play').textContent = '↻ Replay'; $('play').classList.remove('on'); } } dirty = true; } last = now; } else last = null;
  const held = busy || now < busyUntil;
  if (auto && !held) rotateCam();
  if (dirty && !held){ const wantTrail = now - lastTrail > 80; if (wantTrail) lastTrail = now; render(wantTrail); }
  frames++; if (now - fpsT >= 500){ const fps = Math.round(frames * 1000 / (now - fpsT)); frames = 0; fpsT = now; $('fps').textContent = fps + ' fps'; parent.postMessage({orbitFps: fps}, '*'); }
  requestAnimationFrame(loop);
}
$('play').onclick = () => { if (!playing && !D.repeat && t >= D.duration) { t = 0; lastTrail = 0; } playing = !playing; $('play').textContent = playing ? '⏸ Pause' : '▶ Play'; $('play').classList.toggle('on', playing); };
$('speed').oninput = e => { speed = Math.pow(10, parseFloat(e.target.value)); $('spd').textContent = speed.toFixed(speed < 1 ? 2 : 1) + '×'; };
$('speed').ondblclick = () => { $('speed').value = 0; $('speed').oninput({target: $('speed')}); };
$('scrub').ondblclick = () => { $('scrub').value = 0; $('scrub').oninput({target: $('scrub')}); };
$('scrub').oninput = e => { t = D.duration * e.target.value / 1000; dirty = true; lastTrail = 0; };
$('auto').onclick = () => { auto = !auto; $('auto').classList.toggle('on', auto); };
let labelsOn = true; $('labels').onclick = () => { labelsOn = !labelsOn; const u = {}; for (let k = 0; k < D.nlabels; k++) u['scene.annotations[' + k + '].visible'] = labelsOn; Plotly.relayout(gd, u); $('labels').classList.toggle('on', labelsOn); };
let legendOn = true; $('legend').onclick = () => { legendOn = !legendOn; $('legendbar').style.display = legendOn ? 'flex' : 'none'; $('legend').classList.toggle('on', legendOn); };
(function(){                                                          // the legend: swatch + LaTeX label (KaTeX), click to hide or show that item
  const LG = $('legendbar');
  const texNode = (src, plain) => { const span = document.createElement('span'); if (!window.katex) { span.textContent = plain; return span; }
    src.split('$').forEach((seg, i) => { if (i % 2) { const m = document.createElement('span'); try { katex.render(seg, m, {throwOnError: false}); } catch (e) { m.textContent = seg; } span.append(m); } else if (seg) span.append(document.createTextNode(seg)); }); return span; };
  (D.legend || []).forEach(e => { const d = document.createElement('div'); d.className = 'lg'; const sw = document.createElement('span'); sw.className = 'sw' + (e.kind === 'dot' ? ' dot' : '');
    if (e.kind === 'dot') sw.style.background = e.color; else { sw.style.borderTopColor = e.color; sw.style.borderTopStyle = e.dash === 'dash' ? 'dashed' : (e.dash === 'dot' ? 'dotted' : 'solid'); }
    d.append(sw, texNode(e.tex, e.plain)); let vis = true; d.onclick = () => { vis = !vis; d.classList.toggle('off', !vis); Plotly.restyle(gd, {visible: vis ? true : false}, e.idx); }; LG.append(d); });
})();
if (!D.nlabels) $('labels').style.display = 'none';
$('repeat').classList.toggle('on', !!D.repeat); $('repeat').onclick = () => { D.repeat = !D.repeat; $('repeat').classList.toggle('on', D.repeat); parent.postMessage({orbitRepeat: D.repeat}, '*'); };
function setView(v){ eye0 = {x:v.eye[0], y:v.eye[1], z:v.eye[2]}; phi = 0; Plotly.relayout(gd, {'scene.camera.eye': eye0, 'scene.camera.up': {x:v.up[0], y:v.up[1], z:v.up[2]}}); }
$('v_normal').onclick = () => setView(V.normal); $('v_nodes').onclick = () => setView(V.nodes); $('v_iso').onclick = () => setView(V.iso);
if (!TR.length) document.querySelectorAll('.anim').forEach(e => e.style.display = 'none');
if (D.showFps) $('fps').style.display = 'block';
addEventListener('keydown', e => {                                    // let the app's key bindings work while this frame has focus
  if (!/^F\d+$/.test(e.key) && !e.ctrlKey && !e.altKey && !/^[smSM]$/.test(e.key)) return;
  const k = e.key.length === 1 ? e.key.toUpperCase() : e.key; parent.postMessage({orbitKey: [e.ctrlKey && 'Ctrl', e.altKey && 'Alt', e.shiftKey && 'Shift', k].filter(Boolean).join('+')}, '*');
  if (/^F(2|5|11)$/.test(e.key)) e.preventDefault();
});
render(true); requestAnimationFrame(loop);
"""


def build_html(sc: Scene, theme: str = 'light', user_name: str = '', n_frames: int = 480, plotlyjs: str = 'cdn', body: str = 'symbol',
               textures: bool = False, model: str = 'marker', show_fps: bool = False, repeat: bool = True) -> str:
    """Return a self-contained HTML page for an <iframe>. ``model``: 'marker' (simple dot) or a key of models.MODELS ('comsat', 'probe')."""
    T = THEMES[theme]; fig, meta = build_figure(sc, theme, user_name, body, textures)
    data = sample_tracks(sc, n_frames) if sc.tracks else dict(times=[0, 1], duration=0, tracks=[])
    data['views'] = view_presets(sc); data['idx'] = meta['track_idx']; data['nlabels'] = meta['n_labels']; data['showFps'] = bool(show_fps); data['repeat'] = bool(repeat); data['model'] = None
    if model in MODELS and sc.tracks:
        m = spacecraft_mesh(model); fig.add_trace(go.Mesh3d(x=m['x'], y=m['y'], z=m['z'], i=m['i'], j=m['j'], k=m['k'], vertexcolor=m['colors'], flatshading=True, name=MODELS[model],
                                                             showlegend=False, hoverinfo='name', lighting=dict(ambient=0.7, diffuse=0.6, specular=0.2)))
        from .scene import legend_dot; fig.add_trace(legend_dot(MODELS[model], T['body'], 'diamond'))
        fig.data[meta['track_idx'][0][1]].visible = False                      # the dot is replaced by the model
        data['model'] = dict(x=m['x'], y=m['y'], z=m['z'], idx=len(fig.data) - 2, scale=0.05 * meta['half'])
    from ..ui.latex import tex                                                  # the legend is HTML so its labels can be real LaTeX (KaTeX); WebGL text cannot be typeset
    entries: dict = {}
    for i, tr in enumerate(fig.data):
        if getattr(tr, 'showlegend', False) and tr.name:
            line, marker = getattr(tr, 'line', None), getattr(tr, 'marker', None)
            col = (getattr(line, 'color', None) if line is not None else None) or (getattr(marker, 'color', None) if marker is not None else None)
            col = col if isinstance(col, str) else T['ink2']
            e = entries.setdefault(tr.name, dict(plain=tr.name, tex=tex(tr.name, body), color=col, dash=(getattr(line, 'dash', None) if line is not None else None) or 'solid',
                                                 kind='dot' if getattr(tr, 'mode', '') == 'markers' else 'line', idx=[]))
            e['idx'].append(i)
    data['legend'] = list(entries.values()); fig.update_traces(showlegend=False); fig.update_layout(showlegend=False)
    plot_html = fig.to_html(full_html=False, include_plotlyjs=plotlyjs, div_id='plot', default_height='100%', default_width='100%', config=dict(displaylogo=False, responsive=True))
    css = _CSS % dict(surface=T['surface'], ink=T['ink'], ink2=T['ink2'], grid=T['grid'], axis=T['axis'], accent=T['series'][0])
    controls = """
<div id="bar">
  <span class="anim"><button id="play">▶ Play</button></span>
  <label class="anim">Speed <input id="speed" type="range" min="-1" max="1" step="0.01" value="0"> <b id="spd">1.0×</b></label>
  <label class="anim">Time <input id="scrub" type="range" min="0" max="1000" step="1" value="0"></label>
  <span>View: <button id="v_normal">Orbit Normal</button> <button id="v_nodes">Along Line of Nodes</button> <button id="v_iso">Isometric</button></span>
  <button id="auto">⟳ Auto-Rotate</button> <button id="repeat" class="anim" title="loop the animation, or stop at the end">Repeat</button> <button id="labels" class="on">Labels</button> <button id="legend" class="on">Legend</button>
</div>
<div id="readout" class="anim"><span>t <b id="r_t">0</b></span><span>r <b id="r_r">–</b></span><span>v <b id="r_v">–</b></span>
  <span>γ <b id="r_g">–</b></span><span>θ* <b id="r_th">–</b></span></div>"""
    js = _JS.replace('__DATA__', json.dumps(data))
    return (f'<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/vendor/katex/katex.min.css"><script src="/vendor/katex/katex.min.js"></script><style>{css}</style></head>'
            f'<body>{controls}<div id="wrap"><div id="fps">– fps</div>{plot_html}</div><div id="legendbar"></div><script>{js}</script></body></html>')
