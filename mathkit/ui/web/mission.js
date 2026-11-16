/* ---------- Mission workspace: GMAT-style resources + command sequence, propagation, comparison, GMAT script import / export ---------- */
const MIS = { open: new Set(), space: null, refs: [], m: null, tab: 'Resources', res: null, cmp: null, script: null, busy: false, stale: true, meta: null, err: '' };
const MIS_TABS = ['Resources', 'Sequence', 'Plots', 'Reports', 'Compare', 'Porkchop', 'GMAT Script'];
const PK = { origin: 'Earth', target: 'Mars', dep_start: '2026-09-01', dep_days: 200, arr_start: '2027-05-01', arr_days: 250, n: 30, res: null, busy: false };
const KEP = ['SMA', 'ECC', 'INC', 'RAAN', 'AOP', 'TA'], CART = ['X', 'Y', 'Z', 'VX', 'VY', 'VZ'];
const KEP_TIP = { SMA: 'semi-major axis (km); negative for a hyperbola, as in GMAT', ECC: 'eccentricity', INC: 'inclination (deg)', RAAN: 'right ascension of the ascending node (deg)', AOP: 'argument of periapsis (deg)', TA: 'true anomaly (deg, 0 to 360 in GMAT)' };
const GBODY = b => (b === 'Moon' ? 'Luna' : b);

function misNew() {
  return { name: 'New Mission', convention: SET.convention || 'course', spacecraft: [{ name: 'Sat', date_format: 'UTCGregorian', epoch: '01 Jan 2026 12:00:00.000', coord: 'EarthMJ2000Eq', state_type: 'Keplerian', state: { SMA: 7000, ECC: 0, INC: 0, RAAN: 0, AOP: 0, TA: 0 }, mass: 1000, area: 10, cr: 1.8, color: '#ff6b4a' }],
    coords: [], propagators: [{ name: 'Prop', central: 'Earth', dynamics: 'two_body', gravity: ['Earth'], integrator: 'RungeKutta89', initial_step: 60, accuracy: 1e-12, min_step: 0.001, max_step: 86400, j2: false, srp: false, drag: false, cr3bp_primary: 'Earth', cr3bp_secondary: 'Moon' }],
    burns: [], reports: [{ name: 'RF', filename: 'report.txt', params: ['Sat.UTCGregorian', 'Sat.Earth.SMA', 'Sat.Earth.ECC', 'Sat.Earth.TA', 'Sat.Earth.RMAG'], precision: 8, active: true }],
    views: [{ name: 'View', objects: ['Sat', 'Earth'], coord: 'EarthMJ2000Eq', xy_plane: true, axes: true, grid: false }],
    commands: [{ kind: 'Propagate', enabled: true, synchronized: false, items: [['Prop', ['Sat']]], stops: ['Sat.Earth.Periapsis'], burn: '', sat: '', report: '', params: [], on: true }], notes: [], constants: 'Course table' };
}
const misSave = debounce(() => { SET.mission = MIS.m; saveSet(); }, 400);
function misTouch(rerender = false) { MIS.stale = true; misSave(); if (rerender) renderMission(); }
function misCS() {
  const base = ['EarthMJ2000Eq', 'EarthMJ2000Ec', ...Object.keys(META.bodies).filter(b => b !== 'Earth').map(b => GBODY(b) + 'MJ2000Eq')];
  return [...new Set([...MIS.m.coords.map(c => c.name), ...base])];
}
const cmd0 = kind => ({ kind, enabled: true, synchronized: false, items: [], stops: [], burn: '', sat: '', report: '', params: [], on: true });

/* ---- small form helpers ---- */
const mfield = (label, tip, ...ctl) => el('label', { class: 'mf', title: tip || '' }, el('span', { class: 'ml' }, label), ...ctl);
function minput(obj, key, { type = 'text', width, onch, step } = {}) {
  const i = el('input', { type, value: obj[key] ?? '', style: width ? `width:${width}px` : '', step: step || 'any' });
  i.onchange = () => { obj[key] = type === 'number' ? (+i.value) : i.value; if (onch) onch(); misTouch(); }; return i;
}
function mselect(obj, key, options, { onch, rerender } = {}) {
  const s = el('select', {}, ...options.map(o => el('option', { value: Array.isArray(o) ? o[0] : o, selected: (Array.isArray(o) ? o[0] : o) === obj[key] }, Array.isArray(o) ? o[1] : o)));
  s.onchange = () => { obj[key] = s.value; if (onch) onch(); misTouch(rerender); }; return s;
}
function mchips(obj, key, options) {
  return el('div', { class: 'mchips' }, ...options.map(o => { const on = (obj[key] || []).includes(o);
    return el('button', { class: 'chip' + (on ? ' on' : ''), onclick: e => { const a = new Set(obj[key] || []); on ? a.delete(o) : a.add(o); obj[key] = [...a]; misTouch(true); } }, o); }));
}
const mcard = (title, onDelete, ...kids) => el('div', { class: 'mcard' }, el('div', { class: 'mhead' }, el('b', {}, title), onDelete ? el('button', { class: 'mdel', title: 'delete', onclick: onDelete }, ico('trash')) : ''), ...kids);
const mrow = (...kids) => el('div', { class: 'mrow' }, ...kids);
const mbtn = (label, fn, cls = '') => el('button', { class: 'btn ' + cls, onclick: fn }, label);

/* ---- resources ---- */
function scCard(sc, i) {
  const m = MIS.m, cs = misCS();
  const swap = async to => { if (to === sc.state_type) return; const r = await api('mission_convert', { mission: m, index: i, to }); if (!r.ok) { toast(r.error, 'err'); return; } sc.state = r.state; sc.state_type = to; misTouch(true); };
  const keys = sc.state_type === 'Keplerian' ? KEP : CART;
  return mcard(`Spacecraft · ${sc.name}`, m.spacecraft.length > 1 ? () => { m.spacecraft.splice(i, 1); misTouch(true); } : null,
    mrow(mfield('Name', '', minput(sc, 'name', { width: 110, onch: () => renderMission() })), mfield('Date Format', 'UTCGregorian text, or a ModJulian number (GMAT: JD − 2430000.0)', mselect(sc, 'date_format', ['UTCGregorian', 'UTCModJulian', 'TAIModJulian', 'A1ModJulian'])),
      mfield('Epoch', 'e.g. 27 Sep 2024 00:00:00.000', minput(sc, 'epoch', { width: 220 })), mfield('Coordinate System', 'the frame the state below is given in', mselect(sc, 'coord', cs))),
    mrow(mfield('State Type', 'editing one form keeps the other in sync', el('div', { class: 'seg' }, ...['Keplerian', 'Cartesian'].map(t => el('button', { class: sc.state_type === t ? 'on' : '', onclick: () => swap(t) }, t))))),
    mrow(...keys.map(k => mfield(k, KEP_TIP[k] || (k.startsWith('V') ? 'km/s' : 'km'), minput(sc.state, k, { type: 'number', width: 120 })))),
    mrow(mfield('Mass (kg)', '', minput(sc, 'mass', { type: 'number', width: 90 })), mfield('SRP Area (m²)', '', minput(sc, 'area', { type: 'number', width: 90 })), mfield('Cr', 'reflectivity coefficient', minput(sc, 'cr', { type: 'number', width: 70 })),
      mfield('Color', '', minput(sc, 'color', { type: 'color' }))));
}
function propCard(p, i) {
  const m = MIS.m, B = Object.keys(META.bodies), integ = ['RungeKutta89', 'PrinceDormand78', 'PrinceDormand45', 'Kepler (analytic)'];
  return mcard(`Propagator · ${p.name}`, m.propagators.length > 1 ? () => { m.propagators.splice(i, 1); misTouch(true); } : null,
    mrow(mfield('Name', '', minput(p, 'name', { width: 110, onch: () => renderMission() })), mfield('Central Body', 'ForceModel.CentralBody', mselect(p, 'central', B, { rerender: true })),
      mfield('Dynamics', 'two-body is the course model; the others need an ephemeris (built-in or DE440s)', mselect(p, 'dynamics', [['two_body', 'Two-body (course)'], ['patched', 'Patched conics (SOI hand-offs)'], ['selected_nbody', 'Selected N-body'], ['solar_system', 'Full Solar System'], ['cr3bp', 'Restricted three-body']], { rerender: true })),
      mfield('Integrator', 'Kepler (analytic) solves the two-body problem exactly and instantly', mselect(p, 'integrator', integ))),
    p.dynamics === 'selected_nbody' ? mrow(mfield('Point Masses', 'bodies that attract the spacecraft (the central body always does)', mchips(p, 'gravity', B))) : '',
    p.dynamics === 'cr3bp' ? mrow(mfield('Primary', '', mselect(p, 'cr3bp_primary', B)), mfield('Secondary', '', mselect(p, 'cr3bp_secondary', B))) : '',
    mrow(mfield('Initial Step (s)', '', minput(p, 'initial_step', { type: 'number', width: 90 })), mfield('Accuracy', 'relative error tolerance per step (GMAT default 1e-12)', minput(p, 'accuracy', { type: 'number', width: 100 })),
      mfield('Min Step (s)', '', minput(p, 'min_step', { type: 'number', width: 90 })), mfield('Max Step (s)', '', minput(p, 'max_step', { type: 'number', width: 90 }))),
    mrow(...[['j2', 'J2 of the central body'], ['srp', 'Solar radiation pressure'], ['drag', 'Exponential-atmosphere drag']].map(([k, t]) => el('label', { class: 'mcheck', title: 'only in the N-body models' }, el('input', { type: 'checkbox', checked: !!p[k], onchange: e => { p[k] = e.target.checked; misTouch(); } }), t)),
      el('span', { class: 'dim', title: 'GMAT fields that this app does not model' }, 'spherical harmonics, finite thrust attitude: not modelled')));
}
function burnCard(b, i) {
  const m = MIS.m, B = Object.keys(META.bodies);
  const dab = () => { const dv = Math.hypot(b.e1, b.e2, b.e3); return dv ? [dv, Math.atan2(b.e3, b.e1) * 180 / Math.PI, Math.asin(Math.max(-1, Math.min(1, b.e2 / dv))) * 180 / Math.PI] : [0, 0, 0]; };
  const [dv, al, be] = dab(); const ab = { dv, al, be };
  const sync = () => { const a = ab.al * Math.PI / 180, c = ab.be * Math.PI / 180; b.e1 = ab.dv * Math.cos(c) * Math.cos(a); b.e2 = ab.dv * Math.sin(c); b.e3 = ab.dv * Math.cos(c) * Math.sin(a); misTouch(true); };
  return mcard(`Impulsive Burn · ${b.name}`, () => { m.burns.splice(i, 1); misTouch(true); },
    mrow(mfield('Name', '', minput(b, 'name', { width: 100, onch: () => renderMission() })), mfield('Origin', '', mselect(b, 'origin', B)), mfield('Axes', 'VNB: V along the velocity, N the orbit normal, B = V × N (the course Ĉ)', mselect(b, 'axes', ['VNB', 'LVLH', 'MJ2000Eq']))),
    mrow(mfield('Element1 (km/s)', b.axes === 'VNB' ? 'along V' : '', minput(b, 'e1', { type: 'number', width: 110, onch: () => renderMission() })), mfield('Element2 (km/s)', b.axes === 'VNB' ? 'along N' : '', minput(b, 'e2', { type: 'number', width: 110, onch: () => renderMission() })),
      mfield('Element3 (km/s)', b.axes === 'VNB' ? 'along B' : '', minput(b, 'e3', { type: 'number', width: 110, onch: () => renderMission() }))),
    b.axes === 'VNB' ? mrow(el('span', { class: 'dim' }, 'course form (VNC):'), mfield('Δv (km/s)', '', minput(ab, 'dv', { type: 'number', width: 90, onch: sync })), mfield('α (°)', 'in-plane angle from V toward Ĉ', minput(ab, 'al', { type: 'number', width: 80, onch: sync })),
      mfield('β (°)', 'out-of-plane angle toward the orbit normal', minput(ab, 'be', { type: 'number', width: 80, onch: sync }))) : '');
}
function csCard(c, i) {
  return mcard(`Coordinate System · ${c.name}`, () => { MIS.m.coords.splice(i, 1); misTouch(true); },
    mrow(mfield('Name', '', minput(c, 'name', { width: 150, onch: () => renderMission() })), mfield('Origin', '', mselect(c, 'origin', Object.keys(META.bodies))),
      mfield('Axes', 'GMAT note: <Body>MJ2000Eq keeps Earth\'s J2000 equator axes; BodyInertial uses the body\'s own pole (the course "Mars equatorial" frame)', mselect(c, 'axes', ['MJ2000Eq', 'MJ2000Ec', 'BodyInertial']))));
}
function repCard(r, i) {
  return mcard(`Report File · ${r.name}`, () => { MIS.m.reports.splice(i, 1); misTouch(true); },
    mrow(mfield('Name', '', minput(r, 'name', { width: 90, onch: () => renderMission() })), mfield('File Name', '', minput(r, 'filename', { width: 200 })), mfield('Precision', '', minput(r, 'precision', { type: 'number', width: 70 })),
      el('label', { class: 'mcheck' }, el('input', { type: 'checkbox', checked: r.active !== false, onchange: e => { r.active = e.target.checked; misTouch(); } }), 'active')),
    mrow(mfield('Parameters', 'GMAT dotted names, comma separated: Sat.UTCGregorian, Sat.Earth.SMA, Sat.Earth.TA, Sat.Earth.VFPA …', el('input', { type: 'text', style: 'width:min(640px,100%)', value: r.params.join(', '), onchange: e => { r.params = e.target.value.split(',').map(x => x.trim()).filter(Boolean); misTouch(); } }))));
}
function viewCard(v, i) {
  return mcard(`Orbit View · ${v.name}`, () => { MIS.m.views.splice(i, 1); misTouch(true); },
    mrow(mfield('Name', '', minput(v, 'name', { width: 100 })), mfield('Coordinate System', '', mselect(v, 'coord', misCS())), ...[['xy_plane', 'XY plane'], ['axes', 'Axes'], ['grid', 'Grid']].map(([k, t]) => el('label', { class: 'mcheck' }, el('input', { type: 'checkbox', checked: !!v[k], onchange: e => { v[k] = e.target.checked; misTouch(); } }), t))),
    mrow(mfield('Objects', 'spacecraft and bodies drawn', el('input', { type: 'text', style: 'width:min(420px,100%)', value: v.objects.join(', '), onchange: e => { v.objects = e.target.value.split(',').map(x => x.trim()).filter(Boolean); misTouch(); } }))));
}
function resourcesTab() {
  const m = MIS.m, sec = (t, add, ...cards) => el('section', { class: 'msec' }, el('div', { class: 'mshead' }, el('h3', {}, t), add), ...cards);
  const nm = (arr, base) => { let n = 1; while (arr.some(x => x.name === base + (n > 1 ? n : ''))) n++; return base + (n > 1 ? n : ''); };
  return el('div', { class: 'mwrap' },
    sec('Spacecraft', mbtn('+ Add', () => { const s = fresh(m.spacecraft[0] || misNew().spacecraft[0]); s.name = nm(m.spacecraft, 'Sat'); m.spacecraft.push(s); misTouch(true); }), ...m.spacecraft.map(scCard)),
    sec('Propagators', mbtn('+ Add', () => { const p = fresh(m.propagators[0] || misNew().propagators[0]); p.name = nm(m.propagators, 'Prop'); m.propagators.push(p); misTouch(true); }), ...m.propagators.map(propCard)),
    sec('Impulsive Burns', mbtn('+ Add', () => { m.burns.push({ name: nm(m.burns, 'DV'), origin: m.propagators[0]?.central || 'Earth', axes: 'VNB', e1: 0, e2: 0, e3: 0 }); misTouch(true); }), ...m.burns.map(burnCard)),
    sec('Coordinate Systems', el('div', { class: 'btnrow', style: 'margin:0' }, mbtn('+ Body MJ2000Eq', async () => { const b = await askText('central body of the new coordinate system (for example Mars)', { title: 'New Coordinate System', placeholder: 'Mars' }); if (b && META.bodies[b]) { m.coords.push({ name: GBODY(b) + 'MJ2000Eq', origin: b, axes: 'MJ2000Eq' }); misTouch(true); } }),
      mbtn('+ Body Inertial', async () => { const b = await askText('body whose own equator defines the axes (for example Mars)', { title: 'New Coordinate System', placeholder: 'Mars' }); if (b && META.bodies[b]) { m.coords.push({ name: GBODY(b) + 'BodyInertial', origin: b, axes: 'BodyInertial' }); misTouch(true); } })), ...m.coords.map(csCard),
      m.coords.length ? '' : el('div', { class: 'dim' }, 'EarthMJ2000Eq and the other built-in systems always exist; add more only when you need them.')),
    sec('Report Files', mbtn('+ Add', () => { m.reports.push({ name: nm(m.reports, 'RF'), filename: 'report.txt', params: ['Sat.UTCGregorian', 'Sat.Earth.SMA'], precision: 8, active: true }); misTouch(true); }), ...m.reports.map(repCard)),
    sec('Orbit Views', mbtn('+ Add', () => { m.views.push({ name: nm(m.views, 'View'), objects: ['Sat', 'Earth'], coord: 'EarthMJ2000Eq', xy_plane: true, axes: true, grid: false }); misTouch(true); }), ...m.views.map(viewCard)));
}

/* ---- sequence ---- */
function cmdCard(c, i) {
  const m = MIS.m, sats = m.spacecraft.map(s => s.name), props = m.propagators.map(p => p.name);
  const move = d => { const j = i + d; if (j < 0 || j >= m.commands.length) return; [m.commands[i], m.commands[j]] = [m.commands[j], m.commands[i]]; misTouch(true); };
  const txt = (() => { if (c.kind === 'Propagate') return `Propagate ${c.synchronized ? 'Synchronized ' : ''}${c.items.map(([p, s]) => `${p}(${s.join(', ')})`).join(' ')} {${c.stops.join(', ')}}`;
    if (c.kind === 'Maneuver') return `Maneuver ${c.burn}(${c.sat})`; if (c.kind === 'Report') return `Report ${c.report} ${c.params.join(' ')}`; return `Toggle ${c.report} ${c.on ? 'On' : 'Off'}`; })();
  let body;
  if (c.kind === 'Propagate') {
    const stopQuick = (label, t) => mbtn(label, () => { c.stops.push(t); misTouch(true); });
    body = [mrow(el('label', { class: 'mcheck', title: 'step the first propagator, then bring the others to the same epoch' }, el('input', { type: 'checkbox', checked: c.synchronized, onchange: e => { c.synchronized = e.target.checked; misTouch(true); } }), 'Synchronized')),
      ...c.items.map((it, k) => mrow(mfield('Propagator', '', (() => { const s = el('select', {}, ...props.map(p => el('option', { value: p, selected: p === it[0] }, p))); s.onchange = () => { it[0] = s.value; misTouch(true); }; return s; })()),
        mfield('Spacecraft', '', el('div', { class: 'mchips' }, ...sats.map(sn => el('button', { class: 'chip' + (it[1].includes(sn) ? ' on' : ''), onclick: () => { const a = new Set(it[1]); a.has(sn) ? a.delete(sn) : a.add(sn); it[1] = [...a]; misTouch(true); } }, sn)))),
        c.items.length > 1 ? mbtn('remove', () => { c.items.splice(k, 1); misTouch(true); }) : '')),
      mrow(mbtn('+ propagator', () => { c.items.push([props[0], [sats[0]]]); misTouch(true); })),
      mrow(mfield('Stop Conditions', 'several conditions stop at whichever occurs first. examples: Sat.Earth.Periapsis · Sat.Earth.TA = 120 · Sat.Earth.RMAG = 80000 · Sat.ElapsedSecs = 3600 · Sat.ElapsedDays = 2',
        el('textarea', { rows: Math.max(2, c.stops.length), style: 'width:min(520px,100%)', onchange: e => { c.stops = e.target.value.split('\n').map(x => x.trim()).filter(Boolean); misTouch(true); } }, c.stops.join('\n')))),
      mrow(el('span', { class: 'dim' }, 'add:'), stopQuick('Periapsis', `${sats[0]}.${m.propagators[0]?.central || 'Earth'}.Periapsis`), stopQuick('Apoapsis', `${sats[0]}.${m.propagators[0]?.central || 'Earth'}.Apoapsis`),
        stopQuick('TA =', `${sats[0]}.${m.propagators[0]?.central || 'Earth'}.TA = 120`), stopQuick('RMAG =', `${sats[0]}.${m.propagators[0]?.central || 'Earth'}.RMAG = 50000`), stopQuick('ElapsedSecs =', `${sats[0]}.ElapsedSecs = 3600`), stopQuick('ElapsedDays =', `${sats[0]}.ElapsedDays = 1`))];
  } else if (c.kind === 'Maneuver') body = [mrow(mfield('Burn', '', (() => { const s = el('select', {}, ...m.burns.map(b => el('option', { value: b.name, selected: b.name === c.burn }, b.name))); s.onchange = () => { c.burn = s.value; misTouch(true); }; if (!c.burn && m.burns[0]) c.burn = m.burns[0].name; return s; })()),
    mfield('Spacecraft', '', (() => { const s = el('select', {}, ...sats.map(b => el('option', { value: b, selected: b === c.sat }, b))); s.onchange = () => { c.sat = s.value; misTouch(true); }; if (!c.sat) c.sat = sats[0]; return s; })()))];
  else if (c.kind === 'Report') body = [mrow(mfield('Report File', '', (() => { const s = el('select', {}, ...m.reports.map(b => el('option', { value: b.name, selected: b.name === c.report }, b.name))); s.onchange = () => { c.report = s.value; misTouch(true); }; if (!c.report && m.reports[0]) c.report = m.reports[0].name; return s; })()),
    mfield('Parameters', '', el('input', { type: 'text', style: 'width:min(520px,100%)', value: c.params.join(' '), onchange: e => { c.params = e.target.value.split(/[\s,]+/).filter(Boolean); misTouch(true); } })))];
  else body = [mrow(mfield('Report File', '', (() => { const s = el('select', {}, ...m.reports.map(b => el('option', { value: b.name, selected: b.name === c.report }, b.name))); s.onchange = () => { c.report = s.value; misTouch(true); }; if (!c.report && m.reports[0]) c.report = m.reports[0].name; return s; })()),
    el('label', { class: 'mcheck' }, el('input', { type: 'checkbox', checked: c.on, onchange: e => { c.on = e.target.checked; misTouch(true); } }), 'on'))];
  const open = MIS.open.has(i), kc = { Propagate: 'blue', Maneuver: 'orange', Report: 'green', Toggle: 'amber' }[c.kind] || 'blue', ik = { Propagate: 'orb2', Maneuver: 'bolt', Report: 'basic', Toggle: 'forces' }[c.kind] || 'orb2';
  const ctlNode = el('span', { class: 'mctl' }, el('label', { class: 'mcheck', title: 'disabled commands are skipped (and written as comments in the GMAT script)' }, el('input', { type: 'checkbox', checked: c.enabled, onchange: e => { c.enabled = e.target.checked; misTouch(true); } }), 'enabled'),
      el('button', { class: 'mdel', title: 'move up', onclick: () => move(-1) }, '↑'), el('button', { class: 'mdel', title: 'move down', onclick: () => move(1) }, '↓'),
      el('button', { class: 'mdel', title: 'insert a copy after this command', onclick: () => { m.commands.splice(i + 1, 0, fresh(c)); misTouch(true); } }, '⧉'),
      el('button', { class: 'mdel', title: 'delete', onclick: () => { m.commands.splice(i, 1); misTouch(true); } }, ico('trash')));
  return el('div', { class: 'sitem ' + kc + (c.enabled ? '' : ' off') + (open ? ' open' : '') }, el('div', { class: 'snode', title: c.kind }, ico(ik), el('i', {}, String(i + 1))),
    el('div', { class: 'scard' }, el('div', { class: 'shead', onclick: () => { MIS.open.has(i) ? MIS.open.delete(i) : MIS.open.add(i); renderMission(); } }, el('span', { class: 'schev' }, ico(open ? 'down' : 'rc')), el('b', {}, c.kind), el('code', {}, txt), ctlNode),
      open ? el('div', { class: 'sbody' }, ...body) : ''));
}
function sequenceTab() {
  const m = MIS.m;
  return el('div', { class: 'mwrap' }, el('div', { class: 'dim' }, 'commands run top to bottom after BeginMissionSequence. a propagate command stops at the first of its stop conditions. click a step to open it.'),
    el('div', { class: 'btnrow', style: 'margin:0' }, mbtn('Expand All', () => { m.commands.forEach((_, i) => MIS.open.add(i)); renderMission(); }), mbtn('Collapse All', () => { MIS.open.clear(); renderMission(); })),
    el('div', { class: 'seq' }, el('div', { class: 'sitem start' }, el('div', { class: 'snode small' }, ico('play')), el('div', { class: 'scard seqlabel' }, 'BeginMissionSequence')), ...m.commands.map(cmdCard), el('div', { class: 'sitem end' }, el('div', { class: 'snode small' }, ico('check2')), el('div', { class: 'scard seqlabel' }, 'End of the sequence'))),
    el('div', { class: 'btnrow' }, ...['Propagate', 'Maneuver', 'Report', 'Toggle'].map(k => mbtn('+ ' + k, () => { const c = cmd0(k); if (k === 'Propagate') { c.items = [[m.propagators[0]?.name, [m.spacecraft[0]?.name]]]; c.stops = [`${m.spacecraft[0]?.name}.ElapsedSecs = 3600`]; } m.commands.push(c); misTouch(true); }))));
}

/* ---- results ---- */
const fmtN = (x, d = 8) => (typeof x === 'number' ? (Number.isFinite(x) ? (Math.abs(x) >= 1e-3 || x === 0 ? +x.toPrecision(d) : x.toExponential(4)) : '–') : (x ?? '–'));
/* ---- the Plots tab is a dock: space view, maneuver planner, 3D, 2D and the tables can be dragged anywhere, resized and closed ---- */
const DDOCK = makeDock({ key: 'ddock', closedKey: 'dclosed', ids: ['space', 'planner', 'v3d', 'v2d', 'tables'],
  names: { space: 'Space View', planner: 'Maneuver Planner', v3d: '3D View', v2d: '2D View', tables: 'Tables and Exports' },
  min: { space: [420, 340], planner: [360, 240], v3d: [340, 280], v2d: [320, 280], tables: [360, 150] }, stackH: { space: 640, planner: 520, v3d: 520, v2d: 520, tables: 460 },
  height: 'max(1100px, calc(100vh - 230px))', minHeight: 700,
  def: { t: 's', d: 'v', r: 0.74, a: { t: 's', d: 'h', r: 0.6, a: { t: 's', d: 'v', r: 0.72, a: { t: 't', id: 'space' }, b: { t: 't', id: 'planner' } }, b: { t: 's', d: 'v', r: 0.5, a: { t: 't', id: 'v3d' }, b: { t: 't', id: 'v2d' } } }, b: { t: 't', id: 'tables' } },
  onChange: () => refreshDesignChips() });
const DCHIPS = { el: null };
function refreshDesignChips() {
  if (!DCHIPS.el) return; const c = DDOCK.closed();
  DCHIPS.el.replaceChildren(...c.map(id => el('button', { class: 'chip', onclick: () => DDOCK.open(id) }, '+ ' + DDOCK.names[id])), ...(c.length ? [] : []));
}
function plotsTab() {
  const r = MIS.res; if (!r) return el('div', { class: 'empty' }, 'press run mission to propagate the sequence');
  const sc = r.scene, fr = el('iframe'); fr.srcdoc = sc.html3d || '';
  const conv = r.convention === 'gmat';
  const evRows = r.events.map(e => [e.when, e.sat, e.text]);
  const burnRows = r.burns.map(b => [b.when, b.sat, b.burn, fmtN(b.dv), conv ? `E1 ${fmtN(b.vnb[0], 7)} · E2 ${fmtN(b.vnb[1], 7)} · E3 ${fmtN(b.vnb[2], 7)} (VNB)` : `α ${fmtN(b.alpha, 6)}° · β ${fmtN(b.beta, 6)}°`, conv ? `course: α ${fmtN(b.alpha, 6)}°, β ${fmtN(b.beta, 6)}°` : `GMAT VNB: ${b.vnb.map(x => fmtN(x, 7)).join(', ')}`]);
  const fin = r.final.map(f => [f.sat, f.epoch, fmtN(f.elapsed, 10) + ' s', ...(conv ? [`SMA ${fmtN(f.values.SMA, 9)} · ECC ${fmtN(f.values.ECC, 8)} · INC ${fmtN(f.values.INC, 8)}°`, `TA ${fmtN(f.values.TA, 8)}° · VFPA ${fmtN(f.values.VFPA, 8)}° (course γ ${fmtN(f.values.HFPA, 8)}°)`, `r ${fmtN(f.values.RMAG, 9)} km · v ${fmtN(f.values.VMAG, 9)} km/s · C3 ${fmtN(f.values.C3Energy, 8)} km²/s²`]
    : [`a ${fmtN(f.values.SMA, 9)} km · e ${fmtN(f.values.ECC, 8)} · i ${fmtN(f.values.INC, 8)}°`, `θ* ${fmtN(f.values.TA, 8)}° · γ ${fmtN(f.values.gamma, 8)}°`, `r ${fmtN(f.values.RMAG, 9)} km · v ${fmtN(f.values.VMAG, 9)} km/s · ε ${fmtN(f.values.Energy, 8)} km²/s²`])]);
  const DK = DDOCK.mount();
  DK.bodies.space.append(spaceCard(r)); DK.bodies.planner.append(plannerCard(r));
  DK.bodies.v3d.append(el('div', { class: 'cardx c3d' }, el('h3', {}, el('b', {}, '3D View'), el('span', { class: 'hint' }, ' · ' + r.ephemeris)), el('div', { class: 'body' }, fr)));
  DK.bodies.v2d.append(el('div', { class: 'cardx c2d' }, el('h3', {}, el('b', {}, '2D View')), el('div', { class: 'body' }, el('div', { class: 'svgw', html: sc.svg }))));
  DK.bodies.tables.append(
    el('div', { class: 'sheet' }, el('h3', {}, 'Final States'), table(['Spacecraft', 'Epoch (UTC)', 'Elapsed', 'Elements', 'Angles', 'Magnitudes'], fin)),
    r.burns.length ? el('div', { class: 'sheet' }, el('h3', {}, 'Maneuvers'), table(['When', 'Spacecraft', 'Burn', 'Δv (km·s⁻¹)', conv ? 'GMAT ImpulsiveBurn' : 'Course form', 'Other form'], burnRows)) : '',
    el('div', { class: 'sheet' }, el('h3', {}, 'Events'), table(['When (UTC)', 'Spacecraft', 'Event'], evRows)),
    el('div', { class: 'sheet' }, el('h3', {}, 'Reference Trajectories'), el('div', { class: 'dim' }, 'import a CSV (utc or jd, x, y, z …), a CCSDS OEM file, or an SPK kernel to draw it dashed next to the mission and measure the difference. only ICRF / EME2000 inertial frames in utc are accepted.'),
      el('div', { class: 'btnrow' }, (() => { const f = el('input', { type: 'file', accept: '.csv,.oem,.txt', style: 'display:none', onchange: async e => { const fl = e.target.files[0]; if (!fl) return; const x = await api('mission_import_trajectory', { filename: fl.name, text: await fl.text() }); e.target.value = '';
          if (!x.ok) { toast(x.error, 'err'); return; } MIS.refs.push(x.ref); toast(`imported ${x.points} points; run the mission to draw it`, 'ok'); renderMission(); } }); return el('span', {}, f, mbtn('Import CSV or OEM…', () => f.click())); })(),
        mbtn('Import SPK Kernel…', async () => { const path = await askText('full path of a .bsp kernel', { title: 'Import SPK Kernel', placeholder: 'C:\\path\\to\\kernel.bsp' }); if (!path) return; const x = await api('mission_import_trajectory', { path }); if (!x.ok) { toast(x.error, 'err'); return; } MIS.refs.push(x.ref); toast(`imported ${x.points} points`, 'ok'); renderMission(); }),
        ...(MIS.refs.length ? [mbtn('Clear Imported', () => { MIS.refs = []; renderMission(); })] : [])),
      ...(MIS.refs.length ? [table(['Imported', 'Centre', 'Points', 'Max difference (km)', 'RMS (km)', 'At the end (km)'], MIS.refs.map((rf, i) => { const d = (r.ref_diff || []).find(x => x.name === rf.name) || {}; return [rf.name, rf.center, rf.jd.length, d.points ? fmtN(d.max_km, 6) : '–', d.points ? fmtN(d.rms_km, 6) : '–', d.points ? fmtN(d.end_km, 6) : (d.error || 'run the mission')]; }))] : [])),
    el('div', { class: 'btnrow' }, ...MIS.m.spacecraft.flatMap(sc => [['csv', 'CSV'], ['oem', 'CCSDS OEM'], ['cosmo', 'Cosmographia SPK']].map(([k, l]) => mbtn(`${sc.name} Trajectory (${l})`, async () => { const x = k === 'cosmo' ? await api('mission_cosmographia', { mission: MIS.m, sat: sc.name }) : await api('mission_trajectory', { mission: MIS.m, sat: sc.name, kind: k }); toast(x.ok ? 'saved to ' + (x.path || x.spk) : x.error, x.ok ? 'ok' : 'err'); })))),
    el('div', { class: 'dim' }, `ephemeris: ${r.ephemeris} — ${r.ephemeris_accuracy}`));
  const chips = el('div', { class: 'closedchips', id: 'dchips' }); DCHIPS.el = chips; refreshDesignChips();
  return el('div', { class: 'mwrap' }, ...(r.warnings.length ? [el('div', { class: 'chk warn' }, el('span', { class: 'ic' }, '!'), el('span', {}, r.warnings.join(' · ')))] : []), chips, DK.el);
}
function porkchopTab() {
  const o = Object.keys(META.bodies).filter(b => b !== 'Sun' && b !== 'Moon'); const host = el('div', { class: 'mwrap' });
  const inp = (k, w, type = 'text') => el('input', { type, value: PK[k], style: `width:${w}px`, onchange: e => { PK[k] = type === 'number' ? +e.target.value : e.target.value; } });
  const sel = k => { const s = el('select', {}, ...o.map(b => el('option', { value: b, selected: b === PK[k] }, b))); s.onchange = () => { PK[k] = s.value; }; return s; };
  host.append(el('div', { class: 'dim' }, 'a departure × arrival date grid: every cell is a Lambert transfer (the same solver as module 12) between the two planets at those dates, using the active ephemeris. the star marks the lowest departure C3.'),
    el('div', { class: 'mcard' }, mrow(mfield('From', '', sel('origin')), mfield('To', '', sel('target')), mfield('Departure Start', 'YYYY-MM-DD', inp('dep_start', 120)), mfield('Departure Span (days)', '', inp('dep_days', 90, 'number')),
      mfield('Arrival Start', 'YYYY-MM-DD', inp('arr_start', 120)), mfield('Arrival Span (days)', '', inp('arr_days', 90, 'number')), mfield('Grid', 'cells per side (8 to 60)', inp('n', 70, 'number')),
      el('button', { class: 'btn pri', onclick: async () => { if (PK.busy) return; PK.busy = true; toast('computing the porkchop grid…');
        const r = await api('mission_porkchop', { ...PK, theme: effTheme(), palette: SET.palette, constants: SET.const }); PK.busy = false; PK.res = r; if (!r.ok) toast(r.error, 'err'); renderMission(); } }, 'Compute'))));
  const r = PK.res;
  if (r && r.ok) host.append(el('div', { class: 'sheet' }, el('h3', {}, `${r.origin} to ${r.target}`), el('div', { class: 'svgw', html: r.svg }),
    table(['Best cell', 'Value'], [['Departure (UTC)', r.best.dep], ['Arrival (UTC)', r.best.arr], ['Time of flight', `${r.best.tof_days.toFixed(1)} days`], ['Departure C3', `${r.best.c3.toFixed(4)} km²·s⁻²`], ['Arrival v∞', `${r.best.vinf_arr.toFixed(4)} km·s⁻¹`], ['Total v∞ sum', `${r.best.dv.toFixed(4)} km·s⁻¹`]]),
    el('div', { class: 'btnrow' }, el('button', { class: 'btn pri', onclick: async () => { const m = await api('mission_from_porkchop', { origin: r.origin, target: r.target, dep_jd: r.best.dep_jd, arr_jd: r.best.arr_jd, constants: SET.const }); if (!m.ok) { toast(m.error, 'err'); return; }
      MIS.m = m.mission; MIS.res = null; MIS.cmp = null; misTouch(); MIS.tab = 'Sequence'; renderMission(); } }, 'Create Transfer From Best Cell')), el('div', { class: 'dim' }, `ephemeris: ${r.ephemeris}`)));
  return host;
}
function reportsTab() {
  const r = MIS.res; if (!r) return el('div', { class: 'empty' }, 'run the mission to fill its report files');
  const names = Object.keys(r.reports); if (!names.length) return el('div', { class: 'empty' }, 'this mission has no report files');
  return el('div', { class: 'mwrap' }, ...names.map(n => { const rep = r.reports[n];
    return el('div', { class: 'sheet' }, el('h3', {}, `${n} · ${rep.filename}`), el('div', { class: 'btnrow' }, mbtn('Save CSV', async () => { const x = await api('mission_save', { mission: MIS.m, kind: 'csv', report: rep }); toast(x.ok ? 'saved to ' + x.path : x.error, x.ok ? 'ok' : 'err'); }),
      mbtn('Save Text Table', async () => { const x = await api('mission_save', { mission: MIS.m, kind: 'txt', report: rep }); toast(x.ok ? 'saved to ' + x.path : x.error, x.ok ? 'ok' : 'err'); }), el('span', { class: 'dim' }, `${rep.rows.length} rows`)),
      el('div', { class: 'tscroll' }, table(rep.columns.map((c, i) => c + (rep.units[i] ? ` (${rep.units[i]})` : '')), rep.rows.slice(0, 400).map(row => row.map(x => fmtN(x, rep.precision || 8)))))); }));
}
async function compareTab() {
  const host = el('div', { class: 'mwrap' }, el('div', { class: 'btnrow' }, mbtn('Run Comparison', () => runCompare(), 'pri'), el('span', { class: 'dim' }, 'runs the exact course (Kepler) solution and the mission as built, and compares the final states')));
  if (MIS.cmp) {
    if (MIS.cmp.error) host.append(el('div', { class: 'chk err' }, el('span', { class: 'ic' }, '✕'), el('span', {}, MIS.cmp.error)));
    else host.append(el('div', { class: 'sheet' }, el('h3', {}, 'Calculated vs Propagated vs GMAT'), el('div', { class: 'dim' }, MIS.cmp.model), el('div', { class: 'dim' }, MIS.cmp.note),
      table(['Spacecraft', 'Quantity', 'Calculated (course, exact)', 'Propagated', 'GMAT', 'Difference'], MIS.cmp.rows.map(r => [r.sat, `${r.quantity}${r.unit ? ' (' + r.unit + ')' : ''}`, fmtN(r.calculated, 10), fmtN(r.propagated, 10), r.gmat == null ? el('span', { class: 'dim' }, MIS.cmp.gmat_status || 'GMAT not configured') : fmtN(r.gmat, 10), fmtN(r.diff, 4)])),
      el('div', { class: 'dim' }, 'position difference at the end: ' + Object.entries(MIS.cmp.position_difference_km).map(([k, v]) => `${k} ${v.toPrecision(4)} km`).join(' · ')),
      el('div', { class: 'dim' }, 'quantities that only approach a limit (v∞, θ*∞ of a flyby after a finite arc) are not mismatches: they approach the asymptote.')));
  }
  return host;
}
async function runCompare() { const r = await api('mission_compare', { mission: MIS.m }); MIS.cmp = r; renderMission(); }
async function scriptTab() {
  const host = el('div', { class: 'mwrap' });
  const r = await api('mission_script', { mission: MIS.m }); MIS.script = r;
  host.append(el('div', { class: 'btnrow' }, mbtn('Copy', () => copyText(r.script)), mbtn('Save .script', async () => { const x = await api('mission_save', { mission: MIS.m, kind: 'script' }); toast(x.ok ? 'saved to ' + x.path : x.error, x.ok ? 'ok' : 'err'); }, 'pri'),
    mbtn('Save Mission File', async () => { const x = await api('mission_save', { mission: MIS.m, kind: 'orbitmission' }); toast(x.ok ? 'saved to ' + x.path : x.error, x.ok ? 'ok' : 'err'); }),
    el('span', { class: 'dim' }, r.round_trip_commands ? 'checked: this script imports back to the same command list' : 'warning: the script did not import back to the same command list')),
    ...(MIS.m.constants === 'Exam rounded' ? [el('div', { class: 'chk warn' }, el('span', { class: 'ic' }, '!'), el('span', {}, 'exam rounded constants are on: GMAT uses its own gravitational parameters, so its results differ slightly from the printed answers'))] : []),
    el('pre', { class: 'script' }, r.script));
  return host;
}

/* ---- running ---- */
async function runMission() {
  if (MIS.busy) return; if (!$('#mbar')) await renderMission(); MIS.busy = true; MIS.err = ''; const bar = $('#mbar'), i = bar.querySelector('i'), t = bar.querySelector('span'); bar.classList.add('on'); i.style.width = '4%'; let stop = false;
  (async () => { while (!stop) { try { const g = await api('mission_progress', {}); i.style.width = Math.max(4, g.frac * 100) + '%'; t.textContent = (g.stage || '') + ' · ' + Math.round(g.frac * 100) + '%'; } catch (e) { } await new Promise(r => setTimeout(r, 150)); } })();
  let r; try { r = await api('mission_run', { mission: MIS.m, theme: effTheme(), refs: MIS.refs, opts: { ...solveOpts(), convention: MIS.m.convention || SET.convention || 'course', name: SET.name } }); } catch (e) { r = { error: String(e) }; }
  stop = true; MIS.busy = false; bar.classList.remove('on');
  if (r.error) { MIS.err = r.error; await askDialog({ title: 'The Mission Could Not Run', intro: r.error, lines: ['nothing was propagated', 'check the command sequence and the propagator, or press undo with the starter missions'], actions: [{ label: 'Adjust Mission', value: 'adjust', pri: true }] }); MIS.res = null; }
  else { MIS.res = r; MIS.stale = false; MIS.cmp = null; if (MIS.tab !== 'Plots' && MIS.tab !== 'Reports') MIS.tab = 'Plots'; }
  renderMission();
}
async function misImportFile(file) {
  const text = await file.text(); const r = await api('mission_import', { filename: file.name, text });
  if (!r.ok) { toast(r.error, 'err'); return; }
  MIS.m = r.mission; MIS.m.convention = SET.convention || 'course'; MIS.res = null; MIS.cmp = null; misTouch(); MIS.tab = 'Resources'; renderMission();
  const lines = [...(r.skipped || []).slice(0, 14).map(s => 'skipped: ' + s), ...(r.notes || [])]; if ((r.skipped || []).length > 14) lines.push(`… and ${r.skipped.length - 14} more skipped`);
  if (lines.length) await askDialog({ title: 'Imported With Notes', intro: `${r.mission.spacecraft.length} spacecraft, ${r.mission.commands.length} commands imported.`, lines, actions: [{ label: 'OK', value: 1, pri: true }] }); else toast('script imported', 'ok');
}
async function openInMission() {
  const r = await api('mission_from_module', {}); if (!r.ok) { toast(r.error, 'err'); return; }
  MIS.m = r.mission; MIS.m.convention = S.res?.convention || SET.convention || 'course'; MIS.res = null; MIS.cmp = null; misTouch(); MIS.tab = 'Sequence'; go('mission'); await renderMission(); await runMission();
}

/* ---- page ---- */
async function renderMission() {
  const main = $('#main'); unmountDock(); main.replaceChildren();
  if (!MIS.meta) MIS.meta = await api('mission_meta', {});
  if (!MIS.m) MIS.m = SET.mission && SET.mission.spacecraft ? SET.mission : misNew();
  const m = MIS.m, conv = m.convention || SET.convention || 'course';
  const starter = el('select', { class: 'preset', style: 'max-width:260px', onchange: async e => { if (!e.target.value) return; const r = await api('mission_starter', { name: e.target.value }); MIS.m = r.mission; MIS.m.convention = conv; MIS.res = null; MIS.cmp = null; misTouch(); MIS.tab = 'Resources'; renderMission(); } },
    el('option', { value: '' }, 'Start from a mission…'), ...MIS.meta.starters.map(s => el('option', { value: s }, s)));
  const file = el('input', { type: 'file', accept: '.script,.orbitmission,.txt', style: 'display:none', onchange: e => { if (e.target.files[0]) misImportFile(e.target.files[0]); e.target.value = ''; } });
  const tabs = el('div', { class: 'tabs' }, ...MIS_TABS.map(t => el('button', { class: 'tab' + (MIS.tab === t ? ' on' : ''), onclick: () => { MIS.tab = t; renderMission(); } }, t)));
  const head = el('div', { class: 'mtool' }, el('div', { class: 'mt1' }, el('input', { class: 'mname', type: 'text', value: m.name, title: 'mission name', onchange: e => { m.name = e.target.value; misTouch(); } }), starter,
    mbtn('Import…', () => file.click(), ''), file, mbtn('New', () => { MIS.m = misNew(); MIS.res = null; MIS.cmp = null; misTouch(); renderMission(); }),
    el('div', { class: 'seg', title: 'how angles and names are shown: the course convention or GMAT parameter names (the script export is always GMAT)' }, ...[['course', 'Course'], ['gmat', 'GMAT']].map(([v, l]) => el('button', { class: conv === v ? 'on' : '', onclick: () => { m.convention = v; misTouch(); renderMission(); if (MIS.res) runMission(); } }, l))),
    el('button', { class: 'solve msolve', onclick: () => runMission() }, 'Run Mission')),
    el('div', { id: 'mbar', class: 'pbar' }, el('div', { class: 'track' }, el('i')), el('span', {})),
    el('div', { class: 'dim' }, `ephemeris: ${MIS.meta.ephemeris.name}${MIS.meta.kernel.path ? '' : ' — download DE440s under settings → ephemeris for metre-level planets'}`));
  main.append(head, tabs, el('div', { class: 'mbody', id: 'mbody' }));
  const body = $('#mbody');
  const t = MIS.tab; if (t === 'Resources') body.append(resourcesTab()); else if (t === 'Sequence') body.append(sequenceTab()); else if (t === 'Plots') body.append(plotsTab()); else if (t === 'Reports') body.append(reportsTab());
  else if (t === 'Compare') body.append(await compareTab()); else if (t === 'Porkchop') body.append(porkchopTab()); else body.append(await scriptTab());
  if (MIS.stale && MIS.res && t !== 'Resources' && t !== 'Sequence') body.prepend(el('div', { class: 'chk warn' }, el('span', { class: 'ic' }, '!'), el('span', {}, 'the mission changed since the last run; press run mission to update these results')));
}


/* ---- three.js space view ---- */
function spaceCard(r) {
  const sp = r.space; if (!sp || sp.error || !sp.tracks || !sp.tracks.length) return el('div', { class: 'dim' }, sp && sp.error ? 'the space view could not be built: ' + sp.error : '');
  const host = el('div', { class: 'spaceview' }), bar = el('div', { class: 'spacebar' }), card = el('div', { class: 'cardx spacecard' }, el('h3', {}, el('b', {}, 'Space View'), el('span', { class: 'hint' }, ' · drag to orbit, scroll to zoom, right-drag to pan; time warp up to 10⁷×')), bar, host);
  setTimeout(async () => {
    if (MIS.space) { try { MIS.space.dispose(); } catch (e) { } MIS.space = null; }
    let S3; try { const mod = await import('/space.js'); S3 = mod.createSpace(host, sp, { sky: SET.sky || 'milkyway', model: SET.model, hires: texHires() }); } catch (e) { host.replaceChildren(el('div', { class: 'empty' }, 'the space view needs WebGL: ' + e)); return; }
    MIS.space = S3; const st = S3.state;
    const btn = (label, fn, title) => el('button', { class: 'btn small', title: title || '', onclick: fn }, label);
    const play = btn('▶ Play', () => { S3.play(); sync(); }), rev = btn('◀ Reverse', () => { st.dir = -st.dir; if (!st.playing) S3.play(true); sync(); }, 'play backwards');
    const date = el('span', { class: 'sdate' }), slider = el('input', { type: 'range', min: 0, max: 10000, value: 0, 'data-default': 0, class: 'sslider', oninput: e => S3.setJD(S3.t0 + (S3.t1 - S3.t0) * e.target.value / 10000) });
    const warp = el('input', { type: 'range', min: 0, max: 7, step: 1, value: st.warp, 'data-default': 3, oninput: e => { S3.setWarp(+e.target.value); sync(); } }), wl = el('b', {});
    const focus = el('select', { onchange: e => S3.focus(e.target.value) }, ...S3.names().map(n => el('option', { value: n, selected: n === st.focus }, n)));
    const chk = (k, label, tip) => el('label', { class: 'mcheck', title: tip || '' }, el('input', { type: 'checkbox', checked: !!st[k], onchange: e => S3.set(k, e.target.checked) }), label);
    const skysel = el('select', { onchange: e => { SET.sky = e.target.value; saveSet(); S3.setSky(e.target.value); } }, ...[['milkyway', 'Milky Way'], ['stars', 'Stars Only'], ['theme', 'Theme Color'], ['black', 'Black']].map(([v, l]) => el('option', { value: v, selected: (SET.sky || 'milkyway') === v }, l)));
    const rec = btn('● Record', () => { if (!st.rec) { st.rec = true; rec.textContent = '■ Stop'; S3.record(true); } else { st.rec = false; rec.textContent = '● Record'; S3.record(false, async blob => { const b64 = await new Promise(res => { const fr = new FileReader(); fr.onload = () => res(fr.result); fr.readAsDataURL(blob); }); const x = await api('save_blob', { kind: 'webm', name: MIS.m.name + '_space', data: b64 }); toast(x.ok ? 'saved to ' + x.path : x.error, x.ok ? 'ok' : 'err'); }); } }, 'record the view as a webm video while it plays');
    function sync() { play.textContent = st.playing ? '⏸ Pause' : '▶ Play'; wl.textContent = S3.warpLabel() + (st.dir < 0 ? ' (reverse)' : ''); }
    host.addEventListener('space-time', () => { slider.value = 10000 * (S3.jd - S3.t0) / Math.max(1e-9, S3.t1 - S3.t0); date.textContent = S3.fmt(S3.jd); }); host.addEventListener('space-state', sync); date.textContent = S3.fmt(S3.jd); sync();
    bar.append(el('div', { class: 'srow' }, play, rev, btn('Next Event', () => S3.nextEvent(), 'jump to the next burn or stop'), el('label', { class: 'mf' }, el('span', { class: 'ml' }, 'Time Warp'), warp), wl, date),
      el('div', { class: 'srow' }, slider),
      el('div', { class: 'srow' }, el('label', { class: 'mf' }, el('span', { class: 'ml' }, 'Focus'), focus), btn('Top', () => S3.view('top')), btn('Isometric', () => S3.view('iso')), btn('Side', () => S3.view('side')),
        chk('labels', 'Labels'), chk('paths', 'Orbits'), chk('soi', 'SOI'), chk('lag', 'Lagrange'), chk('axes', 'Axes'), chk('ecl', 'Ecliptic'),
        el('label', { class: 'mf' }, el('span', { class: 'ml' }, 'Background'), skysel),
        el('label', { class: 'mf', title: 'draw bodies larger than life' }, el('span', { class: 'ml' }, 'Body Size'), el('input', { type: 'range', min: 1, max: 100, value: 1, 'data-default': 1, oninput: e => S3.set('exag', +e.target.value) })),
        el('label', { class: 'mf' }, el('span', { class: 'ml' }, 'Sky Brightness'), el('input', { type: 'range', min: 0, max: 40, value: 10, 'data-default': 10, oninput: e => S3.set('bright', e.target.value / 10) })),
        chk('markers', 'Sky Markers', 'label the galactic centre, Polaris and bright stars on the sky (checks the sky orientation)'),
        el('label', { class: 'mf' }, el('span', { class: 'ml' }, 'Look Toward'), el('select', { onchange: e => { if (e.target.value) { st.markers = true; S3.look(...e.target.value.split(',').map(Number)); } e.target.value = ''; } }, el('option', { value: '' }, '…'), ...sp.markers.map(mk => el('option', { value: mk.ra + ',' + mk.dec }, mk.name)))),
        el('label', { class: 'mf', title: 'how spacecraft are drawn (also under settings → figures and animation)' }, el('span', { class: 'ml' }, 'Spacecraft Model'), el('select', { onchange: e => { SET.model = e.target.value; saveSet(); S.cache.clear(); renderMission(); } }, ...[['marker', 'Simple Marker'], ['comsat', 'Satellite A'], ['probe', 'Satellite B (Probe)']].map(([v, l]) => el('option', { value: v, selected: (SET.model || 'marker') === v }, l)))),
        rec, btn('Save Image', async () => { const x = await api('save_blob', { kind: 'png', name: MIS.m.name + '_space', data: S3.png() }); toast(x.ok ? 'saved to ' + x.path : x.error, x.ok ? 'ok' : 'err'); })));
  }, 0);
  return card;
}


/* ---- maneuver-node planner: pick a point on the trajectory, drag the V / N / B handles, watch the predicted path ---- */
const NODE = { sat: null, pos: 0, e: [0, 0, 0], busy: false, last: null };
function plannerCard(r) {
  const sp = r.space; if (!sp || !sp.tracks || !sp.tracks.length) return '';
  const trk = sp.tracks.find(t => t.name === NODE.sat) || sp.tracks[0]; NODE.sat = trk.name; NODE.pos = Math.max(0, Math.min(trk.idx.length - 1, NODE.pos));
  const out = el('div', { class: 'nodeout' }), card = el('div', { class: 'cardx nodecard' }, el('h3', {}, el('b', {}, 'Maneuver Planner'), el('span', { class: 'hint' }, ' · place a burn anywhere on the trajectory and see where it leads')));
  const sat = el('select', { onchange: e => { NODE.sat = e.target.value; NODE.pos = 0; NODE.e = [0, 0, 0]; renderMission(); } }, ...sp.tracks.map(t => el('option', { value: t.name, selected: t.name === NODE.sat }, t.name)));
  const when = el('span', { class: 'dim' });
  const pos = el('input', { type: 'range', min: 0, max: trk.idx.length - 1, value: NODE.pos, 'data-default': 0, class: 'sslider', oninput: e => { NODE.pos = +e.target.value; preview(); } });
  const rng = 3.0, mk = (label, tip, k) => { const num = el('input', { type: 'number', step: 'any', value: NODE.e[k], style: 'width:110px', onchange: e => { NODE.e[k] = +e.target.value; sl.value = NODE.e[k]; preview(); } });
    const sl = el('input', { type: 'range', min: -rng, max: rng, step: 0.001, value: NODE.e[k], 'data-default': 0, class: 'sslider', oninput: e => { NODE.e[k] = +e.target.value; num.value = NODE.e[k]; previewSoon(); } });
    return el('div', { class: 'srow', title: tip }, el('span', { class: 'ml', style: 'width:150px' }, label), sl, num, el('span', { class: 'dim' }, 'km/s')); };
  let timer = null; const previewSoon = () => { clearTimeout(timer); timer = setTimeout(preview, 220); };
  async function preview() {
    if (NODE.busy) { previewSoon(); return; } NODE.busy = true; const idx = trk.idx[NODE.pos];
    const x = await api('mission_node_preview', { mission: MIS.m, sat: NODE.sat, index: idx, e: NODE.e }); NODE.busy = false; if (!out.isConnected) return; if (!x.ok) { out.replaceChildren(el('div', { class: 'chk err' }, el('span', { class: 'ic' }, '✕'), el('span', {}, x.error))); return; }
    NODE.last = x; when.textContent = `${x.epoch} UTC · ${(x.elapsed / 3600).toFixed(2)} h into command ${x.command + 1} · about ${x.central}`;
    if (MIS.space) { MIS.space.setPreview(x.path.r, x.node.r); MIS.space.setJD(x.node.jd); }
    const f = (v, d = 6) => (v == null ? '–' : fmtN(v, d)), a = x.after, b = x.before;
    out.replaceChildren(table(['', 'Before the burn', 'After the burn'], [['Semi-major axis (km)', f(b.SMA), f(a.SMA)], ['Eccentricity', f(b.ECC, 7), f(a.ECC, 7)], ['Inclination (°)', f(b.INC), f(a.INC)], ['Periapsis radius (km)', f(b.RadPer), f(a.RadPer)],
      ['Apoapsis radius (km)', f(b.RadApo), f(a.RadApo)], ['Period (h)', b.OrbitPeriod ? f(b.OrbitPeriod / 3600) : '–', a.OrbitPeriod ? f(a.OrbitPeriod / 3600) : '–'], ['Speed (km/s)', f(b.VMAG, 7), f(a.VMAG, 7)]]),
      el('div', { class: 'dim' }, `Δv ${x.dv.toFixed(6)} km/s · GMAT ImpulsiveBurn Element1..3 = ${NODE.e.map(v => v.toFixed(6)).join(', ')} (VNB)`));
  }
  card.append(el('div', { class: 'srow' }, el('label', { class: 'mf' }, el('span', { class: 'ml' }, 'Spacecraft'), sat), el('label', { class: 'mf', style: 'flex:1' }, el('span', { class: 'ml' }, 'Place the node along the trajectory'), pos), when),
    mk('Prograde  (V)', 'along the velocity: raises the opposite side of the orbit', 0), mk('Normal  (N)', 'along the orbit normal: changes the inclination', 1), mk('Radial out  (B = V × N)', 'out of the orbit plane direction of Ĉ: the course Ĉ axis', 2), out,
    el('div', { class: 'btnrow' }, el('button', { class: 'btn pri', onclick: async () => { const x = await api('mission_node_insert', { mission: MIS.m, sat: NODE.sat, index: trk.idx[NODE.pos], e: NODE.e }); if (!x.ok) { toast(x.error, 'err'); return; }
        MIS.m = x.mission; misTouch(); NODE.e = [0, 0, 0]; toast('node inserted into the sequence; running the mission', 'ok'); runMission(); } }, 'Insert Node Into Sequence'),
      el('button', { class: 'btn', onclick: () => { NODE.e = [0, 0, 0]; renderMission(); } }, 'Reset')));
  setTimeout(() => { if (NODE.e.some(v => v !== 0) || true) preview(); }, 600); return card;
}
