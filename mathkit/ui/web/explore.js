/* ---------- Explore: a 3D sandbox in the spirit of Universe Sandbox. Library on the left, object panel on the right, time and tools along the bottom. ---------- */
Object.assign(ICO, {
  play: '<path d="M7 4.5v15l12-7.5z"/>', pause: '<path d="M8 5v14M16 5v14"/>', addc: '<circle cx="12" cy="12" r="9"/><path d="M12 8v8M8 12h8"/>', eye: '<path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
  orb2: '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="3.2"/>', palette: '<path d="M12 3a9 9 0 1 0 0 18c1.4 0 2-1 1.6-2.2-.5-1.4.3-2.3 1.7-2.3H18a3 3 0 0 0 3-3C21 7 17 3 12 3z"/><circle cx="7.5" cy="11" r="1"/><circle cx="10" cy="7.5" r="1"/><circle cx="15" cy="7.5" r="1"/>',
  dots: '<circle cx="5" cy="12" r="1.6"/><circle cx="12" cy="12" r="1.6"/><circle cx="19" cy="12" r="1.6"/>', bolt: '<path d="M13 2 4 14h7l-1 8 9-12h-7z"/>', info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7.5v.5"/>',
  search: '<circle cx="11" cy="11" r="6.5"/><path d="M16 16l5 5"/>', camera: '<path d="M4 8h3l2-3h6l2 3h3v11H4z"/><circle cx="12" cy="13" r="3.5"/>', close: '<path d="M6 6l12 12M18 6L6 18"/>',
  undo: '<path d="M9 7 4 12l5 5"/><path d="M4 12h10a6 6 0 0 1 0 12"/>', redo: '<path d="M15 7l5 5-5 5"/><path d="M20 12H10a6 6 0 0 0 0 12"/>', rev: '<path d="M17 4.5v15L5 12z"/>',
  basic: '<path d="M7 4h10v17l-5-3.5L7 21z"/>', motion: '<circle cx="8" cy="12" r="3"/><path d="M13 12h8M18 8l3 4-3 4"/>', orbitt: '<ellipse cx="12" cy="12" rx="9.5" ry="5" transform="rotate(-25 12 12)"/><circle cx="12" cy="12" r="1.8"/>', forces: '<path d="M12 3v18M3 12h18M7 7l10 10M17 7 7 17"/>',
  actions: '<path d="M13 2 4 14h7l-1 8 9-12h-7z"/>',
  rocks: '<circle cx="9" cy="14" r="3.8"/><circle cx="17" cy="7" r="2.2"/><circle cx="18" cy="17" r="1.7"/>', sat: '<rect x="9" y="9" width="6" height="6" rx="1"/><path d="M9 12H2.5M15 12h6.5M4 8.5v7M20 8.5v7M12 9V5M12 19v-4"/>',
  whatif: '<circle cx="12" cy="12" r="9"/><path d="M9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.7.4-1 .9-1 1.7M12 17v.5"/>', star: '<circle cx="12" cy="12" r="4"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M5 5l2 2M17 17l2 2M19 5l-2 2M7 17l-2 2"/>'
});
const CAT_ICON = { 'All': 'grid', 'Solar System': 'star', 'Planets': 'globe', 'Moons': 'moon', 'Small Bodies': 'rocks', 'Spacecraft': 'sat', 'Custom': 'addc', 'What If': 'whatif' };
const MASS_UNITS = [['Earth masses', 5.9722e24], ['Moon masses', 7.342e22], ['Jupiter masses', 1.8982e27], ['Solar masses', 1.98847e30], ['kg', 1]];
const RAD_UNITS = [['km', 1], ['Earth radii', 6378.137], ['Moon radii', 1737.4], ['Jupiter radii', 71492], ['Solar radii', 695700]];
const G_KM = 6.6743e-20, KIND_NAME = { star: 'Star', planet: 'Planet', moon: 'Moon', small: 'Small Body', spacecraft: 'Spacecraft', custom: 'Custom Body' };
const EX = { scene: null, sim: null, sel: null, space: null, undo: [], redo: [], cat: 'All', q: '', libOpen: true, panelOpen: true, tab: 'Basic', meta: null, horizon: '1 year', busy: false, rateExp: 6.0, playing: false,
  view: { labels: true, paths: true, axes: false, ecl: false, markers: false }, thumbs: {}, mu: 'Earth masses', ru: 'km', pd: null, live: null, pop: null, sky: 'milkyway', bright: 3.0, exag: 1 };

function exDispose() { if (EX.live) { clearInterval(EX.live); EX.live = null; } if (EX.space) { try { EX.space.dispose(); } catch (e) { } EX.space = null; } closePop(); }
const fmtNum = (x, d = 6) => (Number.isFinite(x) ? (Math.abs(x) >= 1e-3 && Math.abs(x) < 1e9 || x === 0 ? +x.toPrecision(d) : x.toExponential(4)) : '–');
function fmtRate(sec) {
  const U = [['years', 31557600], ['days', 86400], ['hours', 3600], ['minutes', 60], ['seconds', 1]];
  for (const [n, s] of U) if (sec >= s * 0.999) { const v = sec / s; return `${v >= 100 ? v.toFixed(0) : v >= 10 ? v.toFixed(1) : v.toFixed(2)} ${n}`; } return '1 second';
}
const thumbStyle = b => EX.thumbs[b.name] && !b.texture ? `background-image:url(${EX.thumbs[b.name]});background-size:contain;background-repeat:no-repeat;background-position:center;box-shadow:none;${['sphere', 'star'].includes(b.shape) ? '' : 'border-radius:16px'}` : b.texture ? `background-image:url(/assets/textures/${b.texture});background-size:cover;background-position:center` : `background:radial-gradient(circle at 35% 30%, ${b.color || '#8aa0c8'}, #0b0f1c 120%)`;
async function exThumbs() {                                                          // real 3D shapes drawn once into small images for the library and the panel
  if (!EX.meta || EX.meta.thumbsDone) return; EX.meta.thumbsDone = true; const mod = await import('/space.js'); const list = EX.meta.catalog.filter(c => !c.texture && !c.whatif).map(c => ({ key: c.name, shape: c.shape, color: c.color }));
  try { EX.thumbs = mod.renderThumbs(list, EX.meta.models, 160); } catch (e) { EX.thumbs = {}; } exLib();
}

/* ---- popovers (view / more / actions) ---- */
function closePop() { document.querySelectorAll('.xpop').forEach(e => e.remove()); EX.pop = null; }
function openPop(name, anchor, ...kids) {
  if (EX.pop === name) { closePop(); return; } closePop(); EX.pop = name; const r = anchor.getBoundingClientRect();
  const d = el('div', { class: 'xpop', style: `left:${Math.min(innerWidth - 330, Math.max(8, r.left - 120))}px;bottom:${innerHeight - r.top + 10}px` }, ...kids); document.body.append(d);
}
document.addEventListener('click', e => { if (EX.pop && !e.target.closest('.xpop') && !e.target.closest('.xtool')) closePop(); });

/* ---- scene operations ---- */
async function exNew() {
  EX.busy = true; exBusy(true); const r = await api('sandbox_new', { horizon: EX.horizon }); EX.busy = false; exBusy(false);
  if (!r.ok) { toast(r.error, 'err'); return; } EX.scene = r.scene; EX.sim = r.sim; EX.undo = []; EX.redo = []; EX.sel = null; await exBuild(false);
}
function exBusy(on) { const b = $('#xbusy'); if (b) b.classList.toggle('on', on); }
async function exEdit(edits, selectAfter) {
  if (EX.busy || !EX.scene) return false; EX.busy = true; exBusy(true);
  const jd = EX.space ? EX.space.jd : EX.scene.epoch_jd; const r = await api('sandbox_edit', { scene: EX.scene, jd, edits, horizon: EX.horizon, constants: SET.const }); EX.busy = false; exBusy(false);
  if (!r.ok) { toast(r.error, 'err'); return false; }
  EX.undo.push(EX.scene); if (EX.undo.length > 30) EX.undo.shift(); EX.redo = []; EX.scene = r.scene; EX.sim = r.sim;
  if (r.sim.limited_days) toast(`a fast orbit is in the scene, so the simulation covers ±${r.sim.limited_days} days (the longer lengths would take far too many steps)`, 'ok');
  if (selectAfter) { const ids = r.scene.bodies.map(b => b.id); EX.sel = selectAfter === 'last' ? ids[ids.length - 1] : (ids.includes(EX.sel) ? EX.sel : null); } else if (EX.sel && !r.scene.bodies.some(b => b.id === EX.sel)) EX.sel = null;
  await exBuild(true); return true;
}
async function exHistory(dir) {
  const from = dir < 0 ? EX.undo : EX.redo, to = dir < 0 ? EX.redo : EX.undo; if (!from.length || EX.busy) return;
  to.push(EX.scene); EX.scene = from.pop(); EX.busy = true; exBusy(true); const r = await api('sandbox_run', { scene: EX.scene, horizon: EX.horizon }); EX.busy = false; exBusy(false);
  if (!r.ok) { toast(r.error, 'err'); return; } EX.sim = r.sim; if (EX.sel && !EX.scene.bodies.some(b => b.id === EX.sel)) EX.sel = null; await exBuild(true);
}
async function exRerun() { EX.busy = true; exBusy(true); const r = await api('sandbox_edit', { scene: EX.scene, jd: EX.space ? EX.space.jd : EX.scene.epoch_jd, edits: [], horizon: EX.horizon, constants: SET.const }); EX.busy = false; exBusy(false); if (r.ok) { EX.scene = r.scene; EX.sim = r.sim; await exBuild(true); } }

/* ---- the 3D engine ---- */
async function exBuild(keepCam) {
  const host = $('#xview'); if (!host || !EX.sim) return; const cam = keepCam && EX.space ? EX.space.getCamera() : null;
  if (EX.space) { try { EX.space.dispose(); } catch (e) { } EX.space = null; }
  const inner = el('div', { class: 'xin' }); host.replaceChildren(inner);
  const bodies = EX.sim.bodies.map(b => ({ name: b.id, R: b.radius, texture: b.texture, color: b.color, path: b.path, parent: b.parent, visible: b.visible, orbitColor: b.color, shape: b.shape }));
  let ext = 1; for (const b of bodies) if (b.path) for (let i = 0; i < b.path.r.length; i += 7) ext = Math.max(ext, Math.abs(b.path.r[i][0]), Math.abs(b.path.r[i][1]), Math.abs(b.path.r[i][2]));
  const heavy = EX.sim.bodies.slice().sort((a, b) => b.mu - a.mu)[0];
  const data = { center: heavy ? heavy.id : 'Sun', jd0: EX.sim.jd0, jd1: EX.sim.jd1, bodies, tracks: [], extent: ext, events: [], lagrange: [], refs: [], markers: EX.meta.markers || [], models: EX.meta.models };
  let S3; try { const mod = await import('/space.js'); S3 = mod.createSpace(inner, data, { sky: EX.sky }); } catch (e) { inner.replaceChildren(el('div', { class: 'empty' }, 'the sandbox needs WebGL: ' + e)); return; }
  EX.space = S3; Object.assign(S3.state, EX.view, { bright: EX.bright, exag: EX.exag, focus: heavy ? heavy.id : 'Sun' }); S3.setJD(EX.scene.epoch_jd); S3.setRate(10 ** EX.rateExp); S3.play(EX.playing); S3.select(EX.sel);
  if (cam) S3.setCamera(cam); else S3.setCamera({ p: [2.6e8, -2.6e8, 1.7e8], t: [0, 0, 0] });
  S3.onPick(name => { EX.sel = name; S3.select(name); if (name) { EX.panelOpen = true; S3.state.focus = S3.state.focus; } exPanel(); });
  inner.addEventListener('space-time', exTime); inner.addEventListener('space-state', syncPlay); exTime(); syncPlay(); exPanel();
  if (!EX.live) EX.live = setInterval(exLive, 500);
}
function exTime() { const d = $('#xdate'); if (d && EX.space) d.textContent = EX.space.fmt(EX.space.jd).replace(' UTC', ''); }
function syncPlay() { const b = $('#xplay'); if (b && EX.space) { b.replaceChildren(ico(EX.space.state.playing ? 'pause' : 'play')); EX.playing = EX.space.state.playing; } }
function exLive() {                                                                                // live numbers for the selected body, from the simulated path
  if (!EX.space || !EX.sel) return; const b = EX.sim.bodies.find(x => x.id === EX.sel); if (!b || b.visible === false) return;
  const v = EX.space.velOf(EX.sel); const sp = $('#lv-speed'); if (sp) sp.textContent = fmtNum(Math.hypot(...v), 6);
  const pa = b.parent ? EX.space.posOf(b.parent) : null, p = EX.space.posOf(EX.sel); const dd = $('#lv-dist'); if (dd && pa) dd.textContent = fmtNum(Math.hypot(p[0] - pa[0], p[1] - pa[1], p[2] - pa[2]), 6);
}

/* ---- left drawer: the library ---- */
function exLib() {
  const L = $('#xleft'); if (!L) return; L.classList.toggle('shut', !EX.libOpen);
  const items = EX.meta.catalog.filter(it => (EX.cat === 'All' || it.cat === EX.cat) && (!EX.q || it.name.toLowerCase().includes(EX.q.toLowerCase())));
  const inScene = it => EX.scene && EX.scene.bodies.some(b => b.name === it.name);
  const file = el('input', { type: 'file', accept: '.orbitscene,.json', style: 'display:none', onchange: async e => { const f = e.target.files[0]; if (!f) return; try { const o = JSON.parse(await f.text()); EX.scene = o.scene; EX.undo = []; EX.redo = []; EX.sel = null; await exRerunFromScene(); } catch (x) { toast('not a valid scene file', 'err'); } e.target.value = ''; } });
  L.replaceChildren(el('div', { class: 'xhead' }, el('b', {}, 'Add'), el('span', { class: 'xsp' }), el('button', { class: 'xib', title: 'new Solar System', onclick: () => { if (confirm('replace the current scene with the real Solar System?')) exNew(); } }, ico('orb2')),
      el('button', { class: 'xib', title: 'open a saved scene', onclick: () => file.click() }, ico('basic')), file, el('button', { class: 'xib', title: 'close', onclick: () => { EX.libOpen = false; exLib(); } }, ico('close'))),
    el('div', { class: 'xsearch' }, ico('search'), el('input', { id: 'xq', type: 'text', placeholder: 'search bodies', value: EX.q, oninput: e => { EX.q = e.target.value; exLibGrid(); } })),
    el('div', { class: 'xcats' }, ...EX.meta.categories.map(c => el('button', { class: 'xcat' + (EX.cat === c ? ' on' : ''), title: c, 'aria-label': c, onclick: () => { EX.cat = c; exLib(); } }, ico(CAT_ICON[c] || 'grid')))), el('div', { class: 'xcatname' }, EX.cat),
    el('div', { class: 'xgrid', id: 'xgrid' }));
  exLibGrid(); function exLibGrid() {
    const g = $('#xgrid'); if (!g) return; const its = EX.meta.catalog.filter(it => (EX.cat === 'All' || it.cat === EX.cat) && (!EX.q || it.name.toLowerCase().includes(EX.q.toLowerCase())));
    g.replaceChildren(...its.map(it => el('button', { class: 'xitem' + (EX.sel && EX.scene && EX.scene.bodies.some(b => b.id === EX.sel && b.name === it.name) ? ' sel' : ''), title: it.whatif ? 'a what-if edit of the current scene' : (it.real ? 'real body from the ephemeris' : 'add on an orbit about the selected body'), onclick: () => exAdd(it) },
      el('span', { class: 'xthumb', style: it.whatif ? 'background:linear-gradient(135deg,#ff6b4a,#9b8cf2);box-shadow:none' : thumbStyle(it) }, it.whatif ? el('i', {}, '?') : ''), el('span', { class: 'xname' }, it.name))));
    if (!its.length) g.append(el('div', { class: 'dim', style: 'padding:14px' }, 'nothing matches'));
  }
}
async function exRerunFromScene() { EX.busy = true; exBusy(true); const r = await api('sandbox_run', { scene: EX.scene, horizon: EX.horizon }); EX.busy = false; exBusy(false); if (!r.ok) { toast(r.error, 'err'); return; } EX.sim = r.sim; await exBuild(false); }
async function exAdd(it) {
  if (it.whatif && it.whatif !== 'rogue') { await exEdit([{ op: 'whatif', name: it.whatif }]); toast('what-if applied; press undo (actions) to go back', 'ok'); return; }
  if (it.real && EX.scene.bodies.some(b => b.name === it.name)) { EX.sel = EX.scene.bodies.find(b => b.name === it.name).id; EX.space.select(EX.sel); EX.space.focus(EX.sel); EX.panelOpen = true; exPanel(); return; }
  const ok = await exEdit([{ op: 'add', item: it, parent: EX.sel || undefined, orbit: {} }], 'last'); if (ok) { EX.panelOpen = true; EX.space.select(EX.sel); exPanel(); toast(`${it.name} added${EX.sel ? '' : ''}; edit it in the panel on the right`, 'ok'); }
}

/* ---- right drawer: the object panel ---- */
async function exPanel() {
  const P = $('#xright'); if (!P) return; const sel = EX.sel && EX.scene && EX.scene.bodies.find(b => b.id === EX.sel);
  P.classList.toggle('shut', !sel || !EX.panelOpen); if (!sel) { P.replaceChildren(); return; }
  const r = await api('sandbox_panel', { scene: EX.scene, id: sel.id, jd: EX.space ? EX.space.jd : EX.scene.epoch_jd }); if (!r.ok) { P.replaceChildren(el('div', { class: 'dim', style: 'padding:16px' }, r.error)); return; }
  const pd = EX.pd = r.panel, tabs = [['Basic', 'basic'], ['Motion', 'motion'], ['Orbit', 'orbitt'], ['Forces', 'forces'], ['Actions', 'actions']];
  const row = (label, ...ctl) => el('div', { class: 'xrow' }, el('span', { class: 'xl' }, label), el('span', { class: 'xc' }, ...ctl));
  const num = (v, on, w = 120) => el('input', { type: 'number', value: v, step: 'any', style: `width:${w}px`, onchange: e => on(+e.target.value) });
  const apply = (fields, sa) => exEdit([{ op: 'set', id: sel.id, fields }], sa);
  const sel2 = (opts, cur, on) => el('select', { onchange: e => on(e.target.value) }, ...opts.map(([n]) => el('option', { value: n, selected: n === cur }, n)));
  const mu = MASS_UNITS.find(u => u[0] === EX.mu), ru = RAD_UNITS.find(u => u[0] === EX.ru);
  let body;
  if (EX.tab === 'Basic') body = [row('Name', el('input', { type: 'text', value: pd.name, onchange: e => apply({ name: e.target.value }) })),
    row('Mass', num(+(pd.mass_kg / mu[1]).toPrecision(6), v => apply({ mu: v * mu[1] * G_KM })), sel2(MASS_UNITS, EX.mu, v => { EX.mu = v; exPanel(); })),
    row('Radius', num(+(pd.radius / ru[1]).toPrecision(6), v => apply({ radius: v * ru[1] })), sel2(RAD_UNITS, EX.ru, v => { EX.ru = v; exPanel(); })),
    row('Density', el('span', { class: 'xv' }, pd.density_gcc ? fmtNum(pd.density_gcc, 4) + ' g/cm³' : '–')), row('Color', el('input', { type: 'color', value: sel.color || '#8aa0c8', onchange: e => apply({ color: e.target.value }) })),
    row('Type', sel2([...Object.entries(KIND_NAME).map(([k, v]) => [k])], sel.kind, v => apply({ kind: v })))];
  else if (EX.tab === 'Motion') body = [row('Distance to ' + (pd.parent || 'origin'), el('span', { class: 'xv' }, el('b', { id: 'lv-dist' }, '–'), ' km')), row('Total Velocity', el('span', { class: 'xv' }, el('b', { id: 'lv-speed' }, fmtNum(pd.speed)), ' km/s')),
    ...['x', 'y', 'z'].map((a, i) => row('Position ' + a.toUpperCase(), num(+pd.r[i].toPrecision(10), v => { const r2 = pd.r.slice(); r2[i] = v; apply({ r: r2 }); }, 150), el('span', { class: 'xu' }, 'km'))),
    ...['x', 'y', 'z'].map((a, i) => row('Velocity ' + a.toUpperCase(), num(+pd.v[i].toPrecision(9), v => { const v2 = pd.v.slice(); v2[i] = v; apply({ v: v2 }); }, 150), el('span', { class: 'xu' }, 'km/s'))),
    el('div', { class: 'xnote' }, 'positions and velocities are at the current simulation time, about the system barycentre (ICRF axes). editing them re-runs the simulation from now.')];
  else if (EX.tab === 'Orbit') {
    const o = pd.orbit, par = el('select', {}, ...EX.scene.bodies.filter(b => b.mu > 0 && b.id !== sel.id).map(b => el('option', { value: b.id, selected: b.id === pd.parent }, b.name)));
    const ins = {}; body = [row('Orbits', par)];
    if (!o) body.push(el('div', { class: 'xnote' }, 'this body has no parent to orbit.'));
    else { for (const [k, u, tip] of [['SMA', 'km', 'semi-major axis (negative = hyperbola)'], ['ECC', '', 'eccentricity'], ['INC', '°', 'inclination to the equator'], ['RAAN', '°', 'ascending node'], ['AOP', '°', 'argument of periapsis'], ['TA', '°', 'true anomaly']])
      body.push(row(k, (ins[k] = el('input', { type: 'number', step: 'any', value: +(+o[k]).toPrecision(10), style: 'width:150px', title: tip })), el('span', { class: 'xu' }, u)));
      body.push(row('Period', el('span', { class: 'xv' }, Number.isFinite(o.period) ? fmtRate(o.period) : 'unbound')), row('Distance / speed', el('span', { class: 'xv' }, `${fmtNum(o.dist, 6)} km · ${fmtNum(o.speed, 5)} km/s`)),
        el('div', { class: 'xbtns' }, el('button', { class: 'btn pri small', onclick: () => exEdit([{ op: 'orbit', id: sel.id, parent: par.value, elements: Object.fromEntries(Object.entries(ins).map(([k, i]) => [k, +i.value])) }]) }, 'Apply Orbit'),
          el('button', { class: 'btn small', onclick: () => exEdit([{ op: 'orbit', id: sel.id, parent: par.value, elements: { ...Object.fromEntries(Object.entries(ins).map(([k, i]) => [k, +i.value])), ECC: 0 } }]) }, 'Circularize'))); }
  } else if (EX.tab === 'Forces') body = [row('Gravity', el('label', { class: 'tgl', title: 'when off this body still feels gravity but pulls on nothing (hidden bodies can still pull)' }, el('span', { class: 'dim', style: 'margin:0' }, 'attracts other bodies'), el('input', { type: 'checkbox', checked: sel.gravity !== false && sel.mu > 0, disabled: !(sel.mu > 0), onchange: e => apply({ gravity: e.target.checked }) }))),
    row('Visibility', el('label', { class: 'tgl' }, el('span', { class: 'dim', style: 'margin:0' }, 'draw this body'), el('input', { type: 'checkbox', checked: sel.visible !== false, onchange: e => apply({ visible: e.target.checked }) }))),
    el('div', { class: 'xnote' }, 'a body with zero mass is a test particle (a spacecraft): it follows the others and pulls on nothing.')];
  else body = [el('div', { class: 'xbtns col' }, el('button', { class: 'btn', onclick: () => { EX.space.focus(sel.id); } }, 'Focus the Camera Here'),
    el('button', { class: 'btn', onclick: () => exEdit([{ op: 'add', item: EX.meta.catalog.find(c => c.name === 'Spacecraft'), parent: sel.id, orbit: {} }], 'last') }, 'Add a Spacecraft in Orbit'),
    el('button', { class: 'btn', onclick: async () => { const x = await api('sandbox_to_mission', { scene: EX.scene, id: sel.id, constants: SET.const }); if (!x.ok) { toast(x.error, 'err'); return; } MIS.m = x.mission; MIS.res = null; MIS.cmp = null; misTouch(); MIS.tab = 'Sequence'; go('mission'); } }, 'Send to Design (Mission)'),
    el('button', { class: 'btn danger', onclick: async () => { if (confirm(`delete ${sel.name}?`)) { EX.sel = null; await exEdit([{ op: 'remove', id: sel.id }]); } } }, 'Delete'))];
  P.replaceChildren(el('div', { class: 'xhead' }, el('b', {}, pd.name), el('span', { class: 'xsp' }), el('button', { class: 'xib', title: 'hide the panel', onclick: () => { EX.panelOpen = false; exPanel(); } }, ico('close'))),
    el('div', { class: 'xprev' }, el('span', { class: 'xball', style: thumbStyle(sel) }), el('span', { class: 'xkind' }, KIND_NAME[sel.kind] || sel.kind)),
    el('div', { class: 'xtabs' }, ...tabs.map(([t, ic]) => el('button', { class: 'xtab' + (EX.tab === t ? ' on' : ''), onclick: () => { EX.tab = t; exPanel(); } }, ico(ic), el('span', {}, t)))), el('div', { class: 'xbody' }, ...body));
}

/* ---- bottom bar ---- */
function exBottom() {
  const B = $('#xbottom'); if (!B) return; const tool = (icon, tip, fn, on) => el('button', { class: 'xtool' + (on ? ' on' : ''), title: tip, onclick: fn }, ico(icon));
  const rate = el('input', { type: 'range', min: 0, max: 100, value: EX.rateExp / 9.5 * 100, oninput: e => { EX.rateExp = e.target.value * 0.095; if (EX.space) EX.space.setRate(10 ** EX.rateExp); rl.textContent = fmtRate(10 ** EX.rateExp) + ' / s'; }, title: 'simulated time per real second' });
  const rl = el('span', { class: 'xrate' }, fmtRate(10 ** EX.rateExp) + ' / s');
  const chk = (k, label) => el('label', { class: 'mcheck' }, el('input', { type: 'checkbox', checked: !!EX.view[k], onchange: e => { EX.view[k] = e.target.checked; if (EX.space) EX.space.set(k, e.target.checked); } }), label);
  B.replaceChildren(el('button', { class: 'xplay', id: 'xplay', title: 'play / pause', onclick: () => { if (EX.space) { EX.space.play(); syncPlay(); } } }, ico(EX.playing ? 'pause' : 'play')),
    el('button', { class: 'xtool', title: 'run time backwards', onclick: () => { if (EX.space) { EX.space.state.dir = -EX.space.state.dir; toast(EX.space.state.dir < 0 ? 'time runs backwards' : 'time runs forwards'); } } }, ico('rev')),
    el('span', { class: 'xdate', id: 'xdate' }, '–'), el('span', { class: 'xrateWrap' }, rate, rl), el('span', { class: 'xsp' }),
    tool('addc', 'library: add bodies', e => { EX.libOpen = !EX.libOpen; exLib(); }, EX.libOpen),
    tool('eye', 'view options', e => openPop('view', e.currentTarget, el('div', { class: 'xpt' }, 'View'), chk('labels', 'Labels'), chk('paths', 'Orbits'), chk('axes', 'Axes'), chk('ecl', 'Ecliptic plane'), chk('markers', 'Sky markers (check the sky orientation)'),
      el('label', { class: 'mf' }, el('span', { class: 'ml' }, 'Look Toward'), el('select', { onchange: e => { const v = e.target.value; if (v && EX.space) { EX.view.markers = true; EX.space.set('markers', true); EX.space.look(...v.split(',').map(Number)); } e.target.value = ''; } }, el('option', { value: '' }, '…'), ...(EX.meta.markers || []).map(m => el('option', { value: m.ra + ',' + m.dec }, m.name)))))),
    tool('orb2', 'show or hide orbits', e => { EX.view.paths = !EX.view.paths; if (EX.space) EX.space.set('paths', EX.view.paths); }, EX.view.paths),
    tool('palette', 'background: Milky Way, stars, black', () => { const o = ['milkyway', 'stars', 'black']; EX.sky = o[(o.indexOf(EX.sky) + 1) % o.length]; if (EX.space) EX.space.setSky(EX.sky); toast('background: ' + EX.sky.replace('milkyway', 'milky way')); }),
    tool('dots', 'more', e => openPop('more', e.currentTarget, el('div', { class: 'xpt' }, 'Simulation and Display'),
      el('label', { class: 'mf' }, el('span', { class: 'ml' }, 'Simulation Length (each way)'), el('select', { onchange: e2 => { EX.horizon = e2.target.value; exRerun(); } }, ...EX.meta.horizons.map(h => el('option', { value: h, selected: h === EX.horizon }, h)))),
      el('label', { class: 'mf' }, el('span', { class: 'ml' }, 'Body Size'), el('input', { type: 'range', min: 1, max: 100, value: EX.exag, oninput: e2 => { EX.exag = +e2.target.value; if (EX.space) EX.space.set('exag', EX.exag); } })),
      el('label', { class: 'mf' }, el('span', { class: 'ml' }, 'Sky Brightness'), el('input', { type: 'range', min: 0, max: 80, value: EX.bright * 10, oninput: e2 => { EX.bright = e2.target.value / 10; if (EX.space) EX.space.set('bright', EX.bright); } })),
      el('button', { class: 'btn small', onclick: () => exRecord() }, 'Record Video'))),
    tool('bolt', 'actions', e => openPop('actions', e.currentTarget, el('div', { class: 'xpt' }, 'Actions'),
      el('button', { class: 'btn small', disabled: !EX.undo.length, onclick: () => { closePop(); exHistory(-1); } }, '↶ Undo'), el('button', { class: 'btn small', disabled: !EX.redo.length, onclick: () => { closePop(); exHistory(1); } }, '↷ Redo'),
      el('button', { class: 'btn small', onclick: async () => { closePop(); const x = await api('sandbox_save', { scene: EX.scene }); toast(x.ok ? 'saved to ' + x.path : x.error, x.ok ? 'ok' : 'err'); } }, 'Save Scene'),
      el('button', { class: 'btn small', onclick: () => { closePop(); if (confirm('replace the current scene with the real Solar System?')) exNew(); } }, 'New Solar System'))),
    el('span', { class: 'xsp' }), tool('info', 'show or hide the side panels', () => { EX.panelOpen = !EX.panelOpen; EX.libOpen = !EX.libOpen; exLib(); exPanel(); }),
    tool('search', 'search the library', () => { EX.libOpen = true; exLib(); setTimeout(() => $('#xq') && $('#xq').focus(), 50); }),
    tool('camera', 'save a picture of the view', async () => { if (!EX.space) return; const x = await api('save_blob', { kind: 'png', name: 'explore', data: EX.space.png() }); toast(x.ok ? 'saved to ' + x.path : x.error, x.ok ? 'ok' : 'err'); }));
  exTime(); syncPlay();
}
function exRecord() {
  const S3 = EX.space; if (!S3) return; if (!EX.rec) { EX.rec = true; toast('recording; open actions → more and press again to stop'); S3.record(true); return; }
  EX.rec = false; S3.record(false, async blob => { const b64 = await new Promise(res => { const fr = new FileReader(); fr.onload = () => res(fr.result); fr.readAsDataURL(blob); }); const x = await api('save_blob', { kind: 'webm', name: 'explore', data: b64 }); toast(x.ok ? 'saved to ' + x.path : x.error, x.ok ? 'ok' : 'err'); });
}

/* ---- page ---- */
async function renderExplore() {
  const main = $('#main'); main.replaceChildren(); exDispose();
  if (!EX.meta) EX.meta = await api('sandbox_meta', { constants: SET.const });
  exThumbs();
  main.append(el('div', { class: 'xp' }, el('div', { id: 'xview', class: 'xview' }), el('aside', { id: 'xleft', class: 'xside xleft' }), el('aside', { id: 'xright', class: 'xside xright shut' }), el('div', { id: 'xbottom', class: 'xbottom' }),
    el('div', { id: 'xbusy', class: 'xbusy' }, el('span', {}, 'simulating…'))));
  exLib(); exBottom();
  if (!EX.scene) await exNew(); else await exBuild(false);
}
