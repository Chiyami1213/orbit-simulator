"""Interactive 3-D animation page: Plotly figure + play/pause, 0.1x-10x speed slider, time scrubber, view presets,
auto-rotate and a live t / r / v / gamma / theta* readout.

Frames are placed by solving Kepler's equation in Python (each Track.fn), at N equally spaced *times*, so motion is
uniform in time (fast at periapsis, slow at apoapsis). The browser interpolates between those samples against a
wall-clock time base, so the speed slider rescales time continuously - it never skips or re-orders frames.
"""
from __future__ import annotations
import json
import numpy as np
from ..scene import Scene, unit
from ..theme import THEMES
from .scene import build_figure


def _round(a, nd=3):
    return np.round(np.asarray(a, float), nd).tolist()


def sample_tracks(sc: Scene, n: int = 480) -> dict:
    T = sc.duration_s or 1.0; times = np.linspace(0.0, T, n); out = []
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
    k = 2.0
    return dict(normal=dict(eye=(k * h).tolist(), up=e.tolist()),
                nodes=dict(eye=(k * node).tolist(), up=[0, 0, 1]),
                iso=dict(eye=[1.5, -1.5, 1.1], up=[0, 0, 1]))


_CSS = """
body{margin:0;background:%(surface)s;color:%(ink)s;font-family:system-ui,-apple-system,'Segoe UI',sans-serif;font-size:13px}
#bar{display:flex;flex-wrap:wrap;gap:10px 14px;align-items:center;padding:8px 10px;border-bottom:1px solid %(grid)s;color:%(ink2)s}
button{background:%(surface)s;color:%(ink)s;border:1px solid %(axis)s;border-radius:6px;padding:4px 10px;cursor:pointer;font:inherit}
button:hover{background:%(grid)s} button.on{background:%(accent)s;color:#fff;border-color:%(accent)s}
input[type=range]{vertical-align:middle;accent-color:%(accent)s} label{white-space:nowrap}
#readout{display:flex;flex-wrap:wrap;gap:6px 18px;padding:6px 10px;font-variant-numeric:tabular-nums;border-bottom:1px solid %(grid)s}
#readout b{color:%(ink)s;font-weight:600} #readout span{color:%(ink2)s}
#scrub{width:min(46vw,420px)}
"""

_JS = r"""
const D = __DATA__, V = D.views, N = D.times.length, TR = D.tracks, IDX = D.idx;
const gd = document.getElementById('plot'); let t = 0, playing = false, speed = 1, last = null, auto = false, phi = 0, dirty = true;
let eye0 = {x:1.5,y:-1.5,z:1.0};
const $ = id => document.getElementById(id);
const fmt = (x, d=4) => { const a = Math.abs(x); if (a >= 1e7) return x.toExponential(3); if (a >= 1000) return x.toLocaleString('en-US', {maximumFractionDigits: 1}); if (a >= 1) return x.toFixed(3); return Number(x).toPrecision(d); };
function interp(arr, f){ const i = Math.min(N-2, Math.floor(f)), w = f - i; return arr[i]*(1-w) + arr[i+1]*w; }
function render(){
  const f = D.duration > 0 ? (t / D.duration) * (N-1) : 0; const X=[],Y=[],Z=[],TX=[],TY=[],TZ=[];
  const k = Math.min(N-1, Math.floor(f)); const mi = [], ti = [];
  TR.forEach((tr, j) => {
    const x = interp(tr.xyz[0], f), y = interp(tr.xyz[1], f), z = interp(tr.xyz[2], f);
    X.push([x]); Y.push([y]); Z.push([z]); mi.push(IDX[j][1]);
    TX.push(tr.xyz[0].slice(0,k+1).concat([x])); TY.push(tr.xyz[1].slice(0,k+1).concat([y])); TZ.push(tr.xyz[2].slice(0,k+1).concat([z])); ti.push(IDX[j][0]);
  });
  if (TR.length){ Plotly.restyle(gd, {x:X, y:Y, z:Z}, mi); Plotly.restyle(gd, {x:TX, y:TY, z:TZ}, ti); }
  $('scrub').value = D.duration > 0 ? 1000 * t / D.duration : 0;
  const s = TR.length && TR[0].state && TR[0].state.r ? TR[0].state : null;
  $('r_t').textContent = fmt(t) + ' s  (' + fmt(t/3600) + ' h)';
  if (s){ $('r_r').textContent = fmt(interp(s.r,f)) + ' km'; $('r_v').textContent = fmt(interp(s.v,f)) + ' km/s';
          $('r_g').textContent = fmt(interp(s.gamma,f)) + ' °';
          const a=s.ths, i=Math.min(N-2,Math.floor(f)); let d=a[i+1]-a[i]; if(d>180)d-=360; if(d<-180)d+=360;
          let th=a[i]+d*(f-i); th=((th%360)+360)%360; $('r_th').textContent = th.toFixed(3) + ' °'; }
  dirty = false;
}
function rotateCam(){
  phi += 0.006; const c = Math.cos(phi), s = Math.sin(phi);
  Plotly.relayout(gd, {'scene.camera.eye': {x: eye0.x*c - eye0.y*s, y: eye0.x*s + eye0.y*c, z: eye0.z}});
}
function loop(now){
  if (playing){ if (last !== null && D.duration > 0){ t += (now-last)/1000 * (D.duration/20) * speed; if (t > D.duration) t -= D.duration; dirty = true; } last = now; }
  else last = null;
  if (auto) rotateCam();
  if (dirty) render();
  requestAnimationFrame(loop);
}
$('play').onclick = () => { playing = !playing; $('play').textContent = playing ? '⏸ Pause' : '▶ Play'; $('play').classList.toggle('on', playing); };
$('speed').oninput = e => { speed = Math.pow(10, parseFloat(e.target.value)); $('spd').textContent = speed.toFixed(speed < 1 ? 2 : 1) + '×'; };
$('scrub').oninput = e => { t = D.duration * e.target.value / 1000; dirty = true; };
$('auto').onclick = () => { auto = !auto; $('auto').classList.toggle('on', auto); };
function setView(v){ eye0 = {x:v.eye[0], y:v.eye[1], z:v.eye[2]}; phi = 0;
  Plotly.relayout(gd, {'scene.camera.eye': eye0, 'scene.camera.up': {x:v.up[0], y:v.up[1], z:v.up[2]}}); }
$('v_normal').onclick = () => setView(V.normal); $('v_nodes').onclick = () => setView(V.nodes); $('v_iso').onclick = () => setView(V.iso);
if (!TR.length) document.querySelectorAll('.anim').forEach(e => e.style.display = 'none');
render(); requestAnimationFrame(loop);
"""


def build_html(sc: Scene, theme: str = 'light', user_name: str = '', n_frames: int = 480, plotlyjs: str = 'cdn') -> str:
    """Return a self-contained HTML page (use with st.components.v1.html, height ~ 800)."""
    T = THEMES[theme]; fig, meta = build_figure(sc, theme, user_name)
    data = sample_tracks(sc, n_frames) if sc.tracks else dict(times=[0, 1], duration=0, tracks=[])
    data['views'] = view_presets(sc); data['idx'] = meta['track_idx']
    plot_html = fig.to_html(full_html=False, include_plotlyjs=plotlyjs, div_id='plot', config=dict(displaylogo=False, responsive=True))
    css = _CSS % dict(surface=T['surface'], ink=T['ink'], ink2=T['ink2'], grid=T['grid'], axis=T['axis'], accent=T['series'][0])
    controls = """
<div id="bar">
  <span class="anim"><button id="play">▶ Play</button></span>
  <label class="anim">Speed <input id="speed" type="range" min="-1" max="1" step="0.01" value="0"> <b id="spd">1.0×</b></label>
  <label class="anim">Time <input id="scrub" type="range" min="0" max="1000" step="1" value="0"></label>
  <span>View: <button id="v_normal">Orbit normal</button> <button id="v_nodes">Along line of nodes</button> <button id="v_iso">Isometric</button></span>
  <button id="auto">⟳ Auto-rotate</button>
</div>
<div id="readout" class="anim"><span>t <b id="r_t">0</b></span><span>r <b id="r_r">–</b></span><span>v <b id="r_v">–</b></span>
  <span>γ <b id="r_g">–</b></span><span>θ* <b id="r_th">–</b></span></div>"""
    js = _JS.replace('__DATA__', json.dumps(data))
    return f'<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>{css}</style></head><body>{controls}{plot_html}<script>{js}</script></body></html>'
