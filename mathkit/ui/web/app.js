'use strict';
/* OrbSim — front end. All maths runs in Python (mathkit.ui.api); this file only builds forms and shows results.
   Text style: headers and labels use APA title case (apa), explanatory text is lower case (lc); both come from textcase.js and are
   applied centrally by restyle(), so any string added later follows the same rules.
   Local data (settings, screenshots, exports, backups) is written by the backend to the per-user app data folder, never by this file. */
const $ = (s, r = document) => r.querySelector(s);
/* labels like r_p, v_D, TOF_min, Δv_A are shown with real subscripts (not in code, text boxes or option lists) */
const SUBRE = /(^|[^A-Za-z0-9_.\/\\])((?:[A-Za-z\u0391-\u03c9]\u0304?\*?){1,3})_([A-Za-z0-9\u0391-\u03c9]{1,6})(?![A-Za-z0-9_])/g;
const NOSUB = new Set(['CODE', 'PRE', 'TEXTAREA', 'OPTION', 'SCRIPT', 'STYLE', 'TITLE', 'INPUT', 'KBD']);
const PLAIN_TAGS = new Set(['BUTTON', 'A', 'LI', 'OPTION', 'SUMMARY']);                 // short names of buttons, list items and combo entries: normal font, true subscripts
const TEXC = new Map();
function texSym(sym, sb) {                                                              // "r_p" -> LaTeX: multi-letter capital names upright, a bar or star kept, long subscripts upright
  const bar = sym.includes('̄'), star = sym.endsWith('*'); let b = sym.replace(/[̄*]/g, '');
  if (/[A-Z]{2,}/.test(b)) b = '\\mathrm{' + b + '}'; if (bar) b = '\\bar{' + b + '}'; if (star) b += '^{*}';
  return b + '_{' + (/^[A-Za-z]{2,}$/.test(sb) ? '\\mathrm{' + sb + '}' : sb) + '}';
}
function texNode(tex) {
  const span = document.createElement('span'); span.className = 'mtex'; let h = TEXC.get(tex);
  if (h === undefined) { try { h = katex.renderToString(tex, { throwOnError: false, output: 'html' }); } catch (e) { h = null; } TEXC.set(tex, h); }
  if (h) span.innerHTML = h; else span.textContent = tex; return span;
}
function subText(str, plain) {
  if (str.indexOf('_') < 0) return document.createTextNode(str);
  const useTex = !plain && window.katex;
  const f = document.createDocumentFragment(); let last = 0, m, any = false; SUBRE.lastIndex = 0;
  while ((m = SUBRE.exec(str))) {
    any = true; const cut = m.index + m[1].length + m[2].length; const start = m.index + m[1].length; f.append(str.slice(last, useTex ? start : cut));
    if (useTex) f.append(texNode(texSym(m[2], m[3]))); else { const sb = document.createElement('sub'); sb.textContent = m[3]; f.append(sb); }
    last = m.index + m[0].length;
  }
  if (!any) return document.createTextNode(str); f.append(str.slice(last)); return f;
}
const el = (tag, attrs = {}, ...kids) => {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === 'class') e.className = v; else if (k === 'html') e.innerHTML = v; else if (k.startsWith('on')) e.addEventListener(k.slice(2), v);
    else if (v !== false && v != null) e.setAttribute(k, v === true ? '' : v);
  }
  const subs = !NOSUB.has(tag.toUpperCase());
  for (const c of kids.flat()) if (c != null && c !== false) e.append(c.nodeType ? c : (subs && typeof c === 'string' ? subText(c, PLAIN_TAGS.has(tag.toUpperCase())) : document.createTextNode(c)));
  return e;
};
const api = async (name, payload = {}) => {
  const r = await fetch('/api/' + name, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
  return r.json();
};
const debounce = (fn, ms) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; };
const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
const ICO = {
  cal: '<rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/>',
  orbit: '<circle cx="12" cy="12" r="2.4"/><ellipse cx="12" cy="12" rx="10" ry="4.6" transform="rotate(-30 12 12)"/>',
  check: '<path d="M22 11.1V12a10 10 0 1 1-5.9-9.1"/><path d="M22 4 12 14.01l-3-3"/>',
  gear: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/>',
  left: '<path d="M11 17l-5-5 5-5M18 17l-5-5 5-5"/>', right: '<path d="M13 17l5-5-5-5M6 17l5-5-5-5"/>',
  grid: '<rect x="3" y="3" width="7.5" height="7.5" rx="1.6"/><rect x="13.5" y="3" width="7.5" height="7.5" rx="1.6"/><rect x="3" y="13.5" width="7.5" height="7.5" rx="1.6"/><rect x="13.5" y="13.5" width="7.5" height="7.5" rx="1.6"/>',
  tools: '<path d="M4 6h9M19 6h1M4 12h3M13 12h7M4 18h11M21 18h-1"/><circle cx="16" cy="6" r="2.2"/><circle cx="10" cy="12" r="2.2"/><circle cx="18" cy="18" r="2.2"/>',
  down: '<path d="M6 9l6 6 6-6"/>', rc: '<path d="M9 6l6 6-6 6"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
  moon: '<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/>',
  monitor: '<rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8M12 17v4"/>',
  nbody: '<circle cx="6" cy="6.5" r="2.6"/><circle cx="18" cy="8" r="2"/><circle cx="11" cy="17.5" r="3.2"/>',
  twobody: '<circle cx="6" cy="12" r="3.2"/><circle cx="18.5" cy="12" r="2"/><path d="M9.5 12h6.5" stroke-dasharray="1.5 2.5"/>',
  conic: '<ellipse cx="12" cy="12" rx="9.5" ry="6"/><circle cx="8" cy="12" r="1.3"/><path d="M12 6v12" stroke-dasharray="1.5 2.5"/>',
  kepler: '<ellipse cx="12" cy="12" rx="9.5" ry="6.5"/><path d="M8 12 17.6 8.4M8 12l9.6 3.6"/><circle cx="8" cy="12" r="1.3"/>',
  hyper: '<path d="M3 1c2 8 6 10 18 10M3 19c2-8 6-10 18-10"/><circle cx="6.5" cy="10" r="1.3"/>',
  cube: '<path d="M12 2.5 3.5 7v10L12 21.5 20.5 17V7z"/><path d="M3.5 7 12 11.5 20.5 7M12 11.5v10"/>',
  zap: '<path d="M13 2 4 14h7l-1 8 9-12h-7z"/>',
  hohmann: '<circle cx="12" cy="12" r="3"/><circle cx="12" cy="12" r="9"/><path d="M12 3a6 9 0 0 1 0 18" stroke-dasharray="2 2.5"/>',
  layers: '<path d="M12 2.5 2.5 7.2 12 12l9.5-4.8z"/><path d="M2.5 12 12 16.8l9.5-4.8M2.5 16.8 12 21.5l9.5-4.7"/>',
  globe: '<circle cx="12" cy="12" r="9.5"/><path d="M2.5 12h19M12 2.5a14 14 0 0 1 0 19M12 2.5a14 14 0 0 0 0 19"/>',
  assist: '<path d="M3 19c6 0 8-12 18-13"/><circle cx="13" cy="13" r="3.2"/>',
  close: '<path d="M6 6l12 12M18 6L6 18"/>', trash: '<path d="M3 6h18M8 6V4h8v2M6 6l1 14h10l1-14M10 11v6M14 11v6"/>', check2: '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
  lambert: '<circle cx="5" cy="19" r="2"/><circle cx="19" cy="5" r="2"/><path d="M6.5 17.2C9 8 13.5 6 17.2 6.4"/>'
};
const MOD_ICO = { 1: 'nbody', 2: 'twobody', 3: 'conic', 4: 'kepler', 5: 'hyper', 6: 'cube', 7: 'zap', 8: 'hohmann', 9: 'layers', 10: 'globe', 11: 'assist', 12: 'lambert' };
const ico = n => { const s = document.createElementNS('http://www.w3.org/2000/svg', 'svg'); s.setAttribute('viewBox', '0 0 24 24'); s.innerHTML = ICO[n]; return s; };
const BODY_SYM = { Sun: '☉', Moon: '☽', Mercury: '☿', Venus: '♀', Earth: '⊕', Mars: '♂', Jupiter: '♃', Saturn: '♄', Uranus: '♅', Neptune: '♆', Pluto: '♇' };

const UTIL = [['jd', 'Julian Date', 'cal'], ['const', 'Body Constants', 'orbit'], ['tests', 'Test Cases', 'check']];
const OPT = { tof: 'TOF', radec: 'RA / Dec', ths: 'θ*', xy: 'x, y', polar: 'r, v_r, v_θ', h_eps: 'h, ε', rp_ra: 'r_p, r_a', a_e: 'a, e', p_e: 'p, e', ccw: 'counter-clockwise', cw: 'clockwise' };
const optText = o => OPT[o] || o;
const KEYS_DEFAULT = { refresh: 'F5', screenshot: 'F2', fullscreen: 'F11', settings: 'F9', menu: 'M', focus: 'F8', reset: 'F12', tour: 'F1', theme: 'F10', solve: 'Ctrl+R', quit: 'Ctrl+Q', spacefull: 'F6' };
const KEY_INFO = {
  refresh: ['Refresh Screen', 're-renders the current page and solves it again, keeping your inputs'],
  screenshot: ['Screenshot', 'saves a png of the app window to the screenshots folder in the app data folder'],
  fullscreen: ['Full Screen', 'switches between full screen and the normal window'],
  settings: ['Preferences', 'opens the preferences page (appearance, key bindings and more), or goes back to where you were'],
  spacefull: ['Space View Full Window', 'makes the space view fill the whole window and back (inside it: tab hides or shows the controls, esc leaves)'],
  quit: ['Quit', 'closes OrbSim; asks first unless confirm before quitting is turned off in the preferences'],
  solve: ['Solve and Draw', 'solves the current module and redraws the 3d and 2d views'],
  menu: ['Menu Bar', 'hides or shows the whole left menu bar'],
  theme: ['Color Theme', 'opens the color theme picker (Graphite, Ocean, Forest, Plum, Light)'],
  tour: ['Tutorial', 'starts the guided tour of the window; you can run it again whenever you need it'],
  reset: ['Reset Panels', 'puts every panel back in the default arrangement and brings back closed panels'],
  focus: ['Maximize Plot', 'hides every panel except the 3d or 2d view; esc leaves. bring panels back with the buttons in the plot header']
};
const LAY_DEFAULT = { dock: null, navw: 285, subw: 275, panelw: 384, f3d: 0.56, plotsh: 0, fold: false, hidden: false, sub: false, groups: {}, pins: {}, closed: [] };
const FRAME_PRESETS = [[240, 'Low'], [480, 'Medium'], [1200, 'High'], [3000, 'Ultra']];
const fresh = o => JSON.parse(JSON.stringify(o));
let META = null;
let SET = { const: 'Course table', unit: 'km', appearance: 'dark', name: '', label: '', sliders: true, confirmQuit: true, layout: {}, keys: {},
  view: 'both', palette: 'dark', repeat: true, convention: 'course', tourDone: false, ephemMode: 'auto', ephemPath: '', gmatPath: '', bodyNotation: 'symbol', frames: 480, textures: false, model: 'marker', fps: false, texq: '2k' };
const LAY = fresh(LAY_DEFAULT);
const S = { mode: 'solve', page: '12', prev: '12', canon: {}, tab: 'Plots', scene: 0, res: null, seq: 0, tests: null, rebind: null, cache: new Map(), last: {}, setTab: 'Appearance', backups: null, gpu: '', focus: null, fshow: { menu: false, inputs: false, results: false } };
const mod = () => META.modules.find(m => m.id === S.page);
const isMod = () => !!mod();

/* ---------- settings (stored by the backend in the app data folder) ---------- */
const saveSet = debounce(() => { SET.layout = LAY; api('settings_set', { settings: SET }); }, 300);
const keys = () => ({ ...KEYS_DEFAULT, ...(SET.keys || {}) });
const dark = matchMedia('(prefers-color-scheme: dark)');
const THEME_KEYS = ['dark', 'ocean', 'forest', 'plum', 'light'];                     // stored key, shown as Graphite, Ocean, Forest, Plum, Light
const themeKey = () => THEME_KEYS.includes(SET.palette) ? SET.palette : (SET.appearance === 'light' ? 'light' : 'dark');   // older saved settings (prussian, graphite, obsidian, device) fall back to Graphite or Light
const effTheme = () => themeKey() === 'light' ? 'light' : 'dark';
const solveOpts = () => ({ convention: S.conv || SET.convention || 'course', body: SET.bodyNotation, frames: SET.frames, textures: SET.textures, model: SET.model, fps: SET.fps, palette: SET.palette, repeat: SET.repeat !== false });

/* ---------- text style (headers: APA title case, explanations: lower case) ---------- */
const SEL_H = ['.title', '.nv .lbl', '.chip:not(#unitChip)', '.tab', '#panel h2', '.cardx > h3 b', '.sheet h3', '.tbl th', '.flab', '.fld-top label', '.seg button', 'a.btn', 'button.btn',
  'button.solve', '.sc .hd .t', '.sc .r .a', 'nav h4', '.subhead', '.tbl.c1 td:first-child', '.tbl.c12 td:nth-child(-n+2)', 'select option', '.sp-t', '.setrow .t', '.stab', '.sh1', '.sh2', '.acard .al'].join(',');
const SEL_X = ['.blurb', '.pnote', '.dim', '.chk span:not(.ic)', '.ovl', '.tbl td.eq', '.empty', '.spin', '.hint', '#splash-msg', '#toast'].join(',');
function restyle() {
  for (const [sel, fn] of [[SEL_H, apa], [SEL_X, lc]])
    document.querySelectorAll(sel).forEach(e => e.childNodes.forEach(n => { if (n.nodeType === 3) { const v = fn(n.nodeValue); if (v !== n.nodeValue) n.nodeValue = v; } }));
}
const restyleSoon = debounce(restyle, 16);
new MutationObserver(restyleSoon).observe(document.body, { childList: true, subtree: true });

/* ---------- units and constants ---------- */
function bodyR(name) {
  return META.bodies[name] ? META.bodies[name].R : 1;
}
function factor(m) {
  if (SET.unit === 'km') return 1;
  if (SET.unit === 'AU') return META.AU;
  const bk = m.body_key; return bk ? bodyR(S.canon[m.id][bk]) : 1;
}
const unitLabel = f => f.dist ? (SET.unit === 'R_body' ? 'R' : SET.unit) : f.unit;
const clean = x => String(+(+x).toPrecision(10));
const parseVec = t => t.replace(/[\[\];]/g, ',').split(',').map(s => s.trim()).filter(Boolean).map(Number);

/* ---------- toast ---------- */
let toastTimer;
function toast(msg, kind = '') {
  const t = $('#toast'); t.textContent = msg; t.className = 'on ' + kind; clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove('on'), kind === 'err' ? 6500 : 4500);
}

/* ---------- layout: hide / fold, sub-menu bar and draggable borders ---------- */
function applyLayout() {
  const r = document.documentElement.style, a = $('#app'), subOpen = false;
  r.setProperty('--navw', LAY.navw + 'px'); r.setProperty('--panelw', LAY.panelw + 'px'); r.setProperty('--subw', subOpen ? LAY.subw + 'px' : '0px');
  a.classList.toggle('nonav', S.mode !== 'solve');
  a.classList.toggle('fold', !!LAY.fold); a.classList.toggle('menuhidden', !!LAY.hidden); 
}
function drag(handle, onmove, reset) {
  handle.addEventListener('pointerdown', e => {
    e.preventDefault(); handle.setPointerCapture(e.pointerId); document.body.classList.add('dragging'); handle.classList.add('on');
    const mv = ev => onmove(ev);
    const up = ev => { try { handle.releasePointerCapture(ev.pointerId); } catch (x) { } handle.removeEventListener('pointermove', mv); handle.removeEventListener('pointerup', up);
      document.body.classList.remove('dragging'); handle.classList.remove('on'); saveSet(); };
    handle.addEventListener('pointermove', mv); handle.addEventListener('pointerup', up);
  });
  if (reset) handle.addEventListener('dblclick', () => { reset(); saveSet(); });
}
function initSplitters() {
  const navNow = () => LAY.fold ? 60 : LAY.navw, subNow = () => 0;
  const maxPanel = () => Math.max(300, Math.min(660, innerWidth - navNow() - subNow() - 520));
  drag($('#sp1'), e => { LAY.navw = clamp(e.clientX, 170, 420); LAY.panelw = clamp(LAY.panelw, 300, maxPanel()); applyLayout(); }, () => { LAY.navw = LAY_DEFAULT.navw; applyLayout(); });
  drag($('#sp2'), e => { LAY.panelw = clamp(e.clientX - navNow() - subNow(), 300, maxPanel()); applyLayout(); }, () => { LAY.panelw = LAY_DEFAULT.panelw; applyLayout(); });
  applyLayout();
}
new ResizeObserver(() => { const p = $('.plots'), m = $('#main'); if (p && m) p.classList.toggle('stack', m.clientWidth < 960 && SET.view === 'both'); }).observe(document.documentElement);

/* ---------- menu bar (file / edit / view / go / help) ---------- */
const goto = (page, tab) => { if (tab) S.setTab = tab; if (page === 'settings' && S.page !== 'settings') S.prev = S.page; go(page); };
const copyText = async txt => { try { await navigator.clipboard.writeText(txt); toast('copied to the clipboard', 'ok'); } catch (e) { toast('could not copy: ' + e, 'err'); } };
const setPalette = id => { SET.palette = id; SET.appearance = id === 'light' ? 'light' : 'dark'; saveSet(); syncChrome(); retheme3d(); S.cache.clear(); S.last = {}; if (S.page === 'settings') renderUtil(); else if (isMod()) solveNow(); };
const retheme3d = () => { try { const t = effTheme(); if (typeof MIS !== 'undefined' && MIS.space) MIS.space.setTheme(t); } catch (e) { } };
const setAppearance = v => { SET.appearance = v; saveSet(); syncChrome(); retheme3d(); S.cache.clear(); S.last = {}; if (S.page === 'settings') renderUtil(); else if (isMod()) solveNow(); };
function menuDefs() {
  const K = keys(), res = S.res && !S.res.error ? S.res : null, M = isMod(), tile = id => ({ label: TILE_NAME[id], check: () => !isClosed(id), run: () => (isClosed(id) ? openTile(id) : closeTile(id)), dis: !M });
  return {
    'File': [
      { label: 'Save Screenshot', key: K.screenshot, run: ACTIONS.screenshot },
      { label: 'Export Figure', dis: !res, run: () => { S.tab = 'Export Figure'; renderMain(); } },
      { sep: 1 },
      { label: 'Restore Last Session', run: restoreSession },
      { label: 'Create Backup', run: async () => { const r = await busy('creating backup', () => api('backup_create', {})); toast(r.ok ? 'backup created' : r.error, r.ok ? 'ok' : 'err'); S.backups = null; } },
      { label: 'Open Data Folder', run: async () => { const r = await api('open_folder', {}); if (!r.ok) toast(r.error, 'err'); } },
      ],
    'Edit': [
      { label: 'Reset Inputs', dis: !M, run: () => { const m = mod(); delete S.canon[m.id]; renderPanel(); solveNow(); } },
      { sep: 1 },
      { label: 'Copy Results as Text', dis: !res, run: () => copyText(res.groups.map(g => g.name + '\n' + g.rows.map(r => `  ${r[0]} = ${r[2]}${r[3] ? ' ' + r[3] : ''}`).join('\n')).join('\n\n')) },
      { label: 'Copy Inputs', dis: !M, run: () => copyText(JSON.stringify(S.canon[S.page], null, 1)) },
      { sep: 1 },
      { label: 'Preferences', key: K.settings, run: ACTIONS.settings }],
    'View': [
      { label: 'Menu Bar', key: K.menu, check: () => !LAY.hidden, run: ACTIONS.menu },
      { label: 'Maximize Plot', key: K.focus, dis: !res, run: ACTIONS.focus },
      { label: 'Full Screen', key: K.fullscreen, run: ACTIONS.fullscreen },
      { label: 'Space View Full Window', key: K.spacefull, run: ACTIONS.spacefull },
      { sep: 1 }, { head: 'Panels' }, tile('inputs'), tile('v3d'), tile('v2d'), tile('results'),
      { label: 'Reset Panel Layout', key: K.reset, run: resetPanels },
      { sep: 1 }, { head: 'Color Theme' },
      ...PALETTES.map(([id, name]) => ({ label: name, check: () => themeKey() === id, run: () => setPalette(id) })),
      { sep: 1 }, { label: 'Refresh', key: K.refresh, run: ACTIONS.refresh }],
    'Design': [{ label: 'Mission Design', check: () => S.page === 'mission', run: () => go('mission') }],
    'Analysis': [{ label: 'Solve and Draw', key: K.solve, dis: !M, run: () => solveNow(false, true) }, { sep: 1 }, { head: 'Modules' }, ...META.modules.map(m => ({ label: m.short, check: () => S.page === m.id, run: () => go(m.id) })),
      { sep: 1 }, { head: 'Reference' }, ...UTIL.map(([id, name]) => ({ label: name, check: () => S.page === id, run: () => go(id) }))],
    'Help': [
      { label: 'Start Tutorial', key: K.tour, run: () => startTour() },
      { sep: 1 },
      { label: 'Help Page', run: () => goto('settings', 'Help') },
      { label: 'Report an Issue', run: () => goto('settings', 'Help') },
      { label: 'Key Bindings', run: () => goto('settings', 'Key Bindings') },
      { sep: 1 },
      { label: 'About and Licenses', run: () => goto('settings', 'About') }]
  };
}
let openMenu = null;
function closeMenu() { document.querySelectorAll('.mdrop').forEach(d => d.remove()); document.querySelectorAll('#menubar>button.open').forEach(b => b.classList.remove('open')); openMenu = null; }
function showMenu(name, btn) {
  closeMenu(); openMenu = name; btn.classList.add('open'); const r = btn.getBoundingClientRect();
  const d = el('div', { class: 'mdrop', style: `left:${r.left}px;top:${r.bottom + 4}px;max-height:${innerHeight - r.bottom - 16}px;overflow:auto` });
  for (const it of menuDefs()[name]) {
    if (it.sep) { d.append(el('div', { class: 'msep' })); continue; } if (it.head) { d.append(el('div', { class: 'mh' }, it.head)); continue; }
    d.append(el('button', { class: 'mi', disabled: !!it.dis, onclick: () => { closeMenu(); it.run(); } }, el('span', { class: 'ck' }, it.check && it.check() ? ico('check2') : ''), el('span', { class: 'ml' }, it.label), it.key ? el('kbd', {}, it.key) : ''));
  }
  document.body.append(d);
}
function syncSettingsBtn() { const b = $('#setBtn'); if (b) b.classList.toggle('on', S.page === 'settings'); }
function buildMenubar() {
  const sb = $('#setBtn'); sb.replaceChildren(ico('gear'), el('span', {}, 'Preferences')); sb.onclick = () => ACTIONS.settings(); syncSettingsBtn();
  const bar = $('#menubar'); bar.replaceChildren(...['File', 'Edit', 'View', 'Design', 'Analysis', 'Help'].map(n => el('button', { role: 'menuitem',
    onclick: e => { e.stopPropagation(); if (openMenu === n) closeMenu(); else showMenu(n, e.currentTarget); }, onmouseenter: e => { if (openMenu && openMenu !== n) showMenu(n, e.currentTarget); } }, n)));
  document.addEventListener('click', e => { if (openMenu && !e.target.closest('.mdrop')) closeMenu(); });
  window.addEventListener('blur', closeMenu);
}

/* ---------- modes: Solve (the course modules) and Design (GMAT-style missions and the real Solar System) ---------- */
const MODES = [['solve', 'Solve', 'compute homework and exam problems with the twelve course modules'],
  ['design', 'Design', 'plan missions: resources, command sequence, numerical propagation, GMAT script import and export']];
const modeOfPage = pg => (META.modules.some(m => m.id === pg) || ['jd', 'const', 'tests'].includes(pg)) ? 'solve' : pg === 'mission' ? 'design' : S.mode;
function syncMode() {
  S.mode = modeOfPage(S.page); document.querySelectorAll('#modesw button').forEach(b => b.classList.toggle('on', b.dataset.mode === S.mode)); applyLayout();
}
function setMode(m) {
  if (m === S.mode && S.page !== 'settings') return;
  if (m === 'solve') go(META.modules.some(x => x.id === S.lastSolve) || ['jd', 'const', 'tests'].includes(S.lastSolve) ? S.lastSolve : (META.modules.some(x => x.id === SET.lastPage) ? SET.lastPage : '12'));
  else go('mission');
}
function buildModeSwitch() {
  $('#modesw').replaceChildren(...MODES.map(([id, label, tip]) => el('button', { 'data-mode': id, title: tip, class: id === S.mode ? 'on' : '', onclick: () => setMode(id) }, label)));
}

/* ---------- the 2D plot: scroll to zoom about the cursor, drag to pan, double-click to reset (Solve and Design) ---------- */
(() => {
  const st = new WeakMap(), SEL = '.c2d .svgw', hostOf = e => (e.target && e.target.closest ? e.target.closest(SEL) : null);
  const get = svg => { let v = st.get(svg); if (!v) { v = { k: 1, x: 0, y: 0 }; st.set(svg, v); } return v; };
  const apply = (svg, v) => { svg.style.transformOrigin = '0 0'; svg.style.transform = v.k === 1 && !v.x && !v.y ? '' : `translate(${v.x}px,${v.y}px) scale(${v.k})`; svg.style.cursor = v.k > 1 ? 'grab' : ''; };
  let drag = null;
  document.addEventListener('wheel', e => {
    const host = hostOf(e), svg = host && host.querySelector('svg'); if (!svg) return; e.preventDefault();
    const v = get(svg), r = svg.getBoundingClientRect(), px = e.clientX - r.left, py = e.clientY - r.top, k2 = clamp(v.k * Math.exp(-e.deltaY * 0.0015), 1, 14), f = k2 / v.k;
    v.x = f * v.x + px * (1 - f); v.y = f * v.y + py * (1 - f); v.k = k2; if (k2 === 1) { v.x = 0; v.y = 0; } apply(svg, v);
  }, { passive: false });
  document.addEventListener('pointerdown', e => {
    const host = hostOf(e), svg = host && host.querySelector('svg'); if (!svg || e.button !== 0) return; const v = get(svg); if (v.k <= 1) return;
    drag = { svg, v, x0: e.clientX - v.x, y0: e.clientY - v.y }; svg.style.cursor = 'grabbing'; e.preventDefault();
  });
  document.addEventListener('pointermove', e => { if (drag) { drag.v.x = e.clientX - drag.x0; drag.v.y = e.clientY - drag.y0; apply(drag.svg, drag.v); } });
  window.addEventListener('pointerup', () => { if (drag) { apply(drag.svg, drag.v); drag = null; } });
  document.addEventListener('dblclick', e => { const host = hostOf(e), svg = host && host.querySelector('svg'); if (svg) { const v = get(svg); v.k = 1; v.x = 0; v.y = 0; apply(svg, v); } });
  document.addEventListener('mouseover', e => { const host = hostOf(e); if (host && !host.title) host.title = 'scroll to zoom, drag to pan, double-click to reset'; });
})();

/* ---------- every slider: the filled part follows the thumb (the solve sliders set --pct themselves; this covers all the others) ---------- */
function syncRange(r) { const lo = +r.min || 0, hi = r.max === '' ? 100 : +r.max; r.style.setProperty('--f', clamp((+r.value - lo) / ((hi - lo) || 1), 0, 1)); }
(() => { const d = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value'); Object.defineProperty(HTMLInputElement.prototype, 'value', { ...d, set(v) { d.set.call(this, v); if (this.type === 'range') syncRange(this); } }); })();
document.addEventListener('input', e => { if (e.target && e.target.matches && e.target.matches('input[type=range]')) syncRange(e.target); }, true);
new MutationObserver(() => document.querySelectorAll('input[type=range]').forEach(syncRange)).observe(document.documentElement, { childList: true, subtree: true, attributes: true, attributeFilter: ['min', 'max', 'value'] });

/* ---------- every slider: double-click puts it back to its default value ---------- */
document.addEventListener('dblclick', e => {
  const r = e.target.closest && e.target.closest('input[type=range]'); if (!r) return;
  const d = r.dataset.default !== undefined ? r.dataset.default : r.defaultValue; if (d === '' || d == null) return;
  r.value = d; r.dispatchEvent(new Event('input', { bubbles: true })); r.dispatchEvent(new Event('change', { bubbles: true }));
});
document.addEventListener('mouseover', e => { const r = e.target; if (r && r.matches && r.matches('input[type=range]') && !r.title) r.title = 'double-click to reset'; });

/* ---------- loading screen ---------- */
const SPLASH = { t0: performance.now(), real: 0, done: false };
function splashTick() {
  const bar = $('#splash-bar'); if (!bar) return;
  const shown = Math.min(SPLASH.real, (performance.now() - SPLASH.t0) / 1200 * 100);              // never faster than 1.2 s overall
  bar.style.width = shown + '%'; $('#splash-pct').textContent = Math.round(shown) + '%';
  if (shown >= 100 && SPLASH.done) { const s = $('#splash'); s.classList.add('out'); setTimeout(() => s.remove(), 500); return; }
  requestAnimationFrame(splashTick);
}
const splash = (p, msg) => { SPLASH.real = Math.max(SPLASH.real, p); if (msg) $('#splash-msg').textContent = msg; };

/* ---------- FPS monitor (this page + the 3-D frame) ---------- */
const FPS = { ui: 0, d3: 0 }; let fpsN = 0, fpsT = performance.now();
function fpsLoop(now) {
  if (SET.fps) { fpsN++; if (now - fpsT >= 500) { FPS.ui = Math.round(fpsN * 1000 / (now - fpsT)); fpsN = 0; fpsT = now; showFps(); } } else fpsN = 0;
  requestAnimationFrame(fpsLoop);
}
function showFps() {
  const b = $('#fpsb'); b.hidden = !SET.fps; if (SET.fps) b.textContent = `UI ${FPS.ui} fps` + (FPS.d3 ? ` · 3D ${FPS.d3} fps` : '');
}
window.addEventListener('message', e => { if (e.data && e.data.orbitRepeat != null) { SET.repeat = e.data.orbitRepeat; saveSet(); S.cache.clear(); } if (e.data && e.data.orbitFps != null) { FPS.d3 = e.data.orbitFps; showFps(); } });
function gpuInfo() {
  if (S.gpu) return S.gpu;
  try {
    const c = document.createElement('canvas'), gl = c.getContext('webgl2') || c.getContext('webgl'); if (!gl) return (S.gpu = 'WebGL not available (3D view will not work)');
    const x = gl.getExtension('WEBGL_debug_renderer_info'); const name = x ? gl.getParameter(x.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER);
    return (S.gpu = `${name} (${c.getContext('webgl2') ? 'WebGL 2' : 'WebGL 1'})`);
  } catch (e) { return (S.gpu = 'unknown'); }
}

/* ---------- chrome and navigation ---------- */
const PALETTES = [['dark', 'Graphite', ['#0d1014', '#22324a', '#4ea1ff', '#ff9d3c']], ['ocean', 'Ocean', ['#08121c', '#1c3f63', '#38a8ff', '#2e8bff']], ['forest', 'Forest', ['#091210', '#1f4535', '#3ec48a', '#2fae78']], ['plum', 'Plum', ['#0e0b14', '#3a2d5e', '#a97bff', '#9b5de5']], ['light', 'Light', ['#e9eef5', '#dbe9f8', '#1d6cb0', '#e6761a']]];
function syncChrome() {
  const th = effTheme(); document.body.dataset.theme = th; document.body.dataset.palette = themeKey(); document.documentElement.dataset.boot = th;
  $('#unitChip').innerHTML = 'Units: ' + String(SET.unit).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/_([A-Za-z0-9]+)/, '<sub>$1</sub>') + ' · s'; showFps();
}
function navItem(id, label, iconNode, tip, on) {
  return el('button', { class: 'nv' + ((on ?? S.page === id) ? ' on' : ''), title: tip || label, onclick: () => go(id) }, el('span', { class: 'n' }, iconNode), el('span', { class: 'lbl' }, label));
}
function navGroup(key, label, icon, items, ids) {                                    // sub-items appear while the mouse is over the group and fold when it leaves; a click pins a group open
  LAY.pins = LAY.pins || {}; const pinned = !!LAY.pins[key], act = (ids || []).includes(S.page);
  return el('div', { class: 'ngrp' + (pinned ? ' pinned' : '') + (act ? ' hasact' : '') },
    el('button', { class: 'nv grp', title: label + ' (hover to show, click to keep open)', 'aria-expanded': String(pinned), onclick: () => { LAY.pins[key] = !pinned; saveSet(); buildNav(); } },
      el('span', { class: 'n' }, ico(icon)), el('span', { class: 'lbl' }, label), el('span', { class: 'chev' }, ico('rc'))),
    el('div', { class: 'nsub' }, ...items));
}
let peekTimer = null;
function initNavPeek() {                                                           // a folded menu opens while the mouse is over it and folds again when the mouse leaves
  const nav = $('#nav'), app = $('#app');
  nav.addEventListener('mouseenter', () => { clearTimeout(peekTimer); if (app.classList.contains('fold')) { app.classList.remove('closing'); app.classList.add('peek'); } });
  nav.addEventListener('mouseleave', () => { clearTimeout(peekTimer); peekTimer = setTimeout(() => { app.classList.remove('peek'); app.classList.add('closing'); setTimeout(() => app.classList.remove('closing'), 260); }, 160); });
}
function buildNav() {
  $('#nav').replaceChildren(
    el('div', { class: 'navtop' }, el('button', { class: 'navtoggle', title: LAY.fold ? 'expand menu' : 'collapse menu', onclick: () => { LAY.fold = !LAY.fold; $('#app').classList.remove('peek'); applyLayout(); buildNav(); saveSet(); } }, ico(LAY.fold ? 'right' : 'left'))),
    el('div', { class: 'navlist' },
      navGroup('modules', 'Modules', 'grid', META.modules.map(m => navItem(m.id, m.short, ico(MOD_ICO[m.id]), m.short)), META.modules.map(m => m.id)),
      navGroup('utilities', 'Reference', 'tools', UTIL.map(([id, name, ic]) => navItem(id, name, ico(ic))), UTIL.map(u => u[0]))),
    '');                                                                                 // settings now live in the top bar
}
async function go(page) {
  if (META.modules.some(m => m.id === page) || ['jd', 'const', 'tests'].includes(page)) S.lastSolve = page;
  setFocus(null); if (page !== S.page) S.conv = null;                                   // the per-result convention toggle lasts for one result
  S.page = page; S.scene = 0; syncMode(); buildNav(); syncSettingsBtn();
  $('#app').classList.toggle('wide', !isMod());
  if (isMod()) {
    renderPanel(); S.res = S.last[page] || null; if (S.res) showChecks(S.res); renderMain();      // show the last result instantly, refresh behind it
    return solveNow();
  }
  S.res = null; unmountDock(); $('#panel').replaceChildren(); renderUtil();
}
function setSet(patch, resolve = true) {
  Object.assign(SET, patch); saveSet(); syncChrome();
  if (isMod()) { renderFields(); if (resolve) { S.cache.clear(); solveSoon(); } } else renderUtil();
}

/* ---------- panel / fields ---------- */
function ensureCanon(m) {
  if (!S.canon[m.id]) S.canon[m.id] = Object.fromEntries(m.fields.map(f => [f.key, JSON.parse(JSON.stringify(f.default))]));
  return S.canon[m.id];
}
function renderPanel() {
  const m = mod(); ensureCanon(m); const p = $('#panel');
  const sel = el('select', { class: 'preset', onchange: e => { if (e.target.value !== '') loadPreset(m, +e.target.value); } },
    el('option', { value: '' }, 'Load a homework / exam problem'), ...m.presets.map((pr, i) => el('option', { value: i }, pr.label)));
  p.replaceChildren(el('h2', {}, m.short), el('div', { class: 'blurb' }, m.blurb), m.presets.length ? sel : '', el('div', { class: 'pnote', id: 'pnote' }),
    el('div', { id: 'fields' }), el('button', { class: 'solve', onclick: () => solveNow(false, true) }, 'Solve & Draw'), el('div', { id: 'pbar', class: 'pbar' }, el('div', { class: 'track' }, el('i')), el('span', {})), el('div', { id: 'checks' }));
  renderFields();
}
function loadPreset(m, i) {
  const pr = m.presets[i]; S.canon[m.id] = Object.fromEntries(m.fields.map(f => [f.key, JSON.parse(JSON.stringify(f.default))]));
  Object.assign(S.canon[m.id], JSON.parse(JSON.stringify(pr.vals)));
  SET.label = pr.label.split(' — ')[0]; saveSet(); syncChrome();
  $('#pnote').textContent = pr.note ? 'ℹ ' + pr.note : ''; renderFields(); solveNow();
}
function renderFields() {
  const m = mod(), c = ensureCanon(m), box = $('#fields'); if (!box) return; const fac = factor(m);
  box.replaceChildren(...m.fields.map(f => fieldEl(m, f, c, fac)));
  refreshVisible();
}
function fieldEl(m, f, c, fac) {
  const wrap = el('div', { class: 'fld', 'data-key': f.key }); const commit = v => { c[f.key] = v; changed(m, f); };
  if (f.kind === 'choice') {
    const short = f.options.length <= 4 && f.options.map(optText).join('').length <= 38;
    if (short) {
      wrap.append(el('div', { class: 'flab' }, f.label), el('div', { class: 'seg' }, ...f.options.map(o => el('button', { class: o === c[f.key] ? 'on' : '', onclick: e => { commit(o); e.target.parentNode.querySelectorAll('button').forEach(b => b.classList.toggle('on', b === e.target)); } }, optText(o)))));
    } else wrap.append(el('div', { class: 'flab' }, f.label), el('select', { onchange: e => commit(e.target.value) }, ...f.options.map(o => el('option', { value: o, selected: o === c[f.key] }, optText(o)))));
  } else if (f.kind === 'bool') {
    wrap.append(el('label', { class: 'tgl' }, el('span', { class: 'flab' }, f.label), el('input', { type: 'checkbox', checked: !!c[f.key], onchange: e => commit(e.target.checked) })));
  } else if (f.kind === 'text') {
    wrap.append(el('div', { class: 'flab' }, f.label), el('input', { type: 'text', class: 'wide', value: c[f.key], onchange: e => commit(e.target.value) }));
  } else if (f.kind === 'vec') {
    const k = f.dist ? fac : 1;
    wrap.append(el('div', { class: 'flab' }, `${f.label} (${unitLabel(f)})`), el('input', {
      type: 'text', class: 'wide', value: c[f.key].map(x => clean(x / k)).join(', '),
      oninput: e => { const v = parseVec(e.target.value); const ok = v.length && v.every(Number.isFinite); e.target.classList.toggle('bad', !ok); if (ok) commit(v.map(x => x * k)); }
    }));
  } else {                                    // float / int
    const k = f.dist ? factor(m) : 1; const useSlider = f.rng && SET.sliders && f.kind === 'float';
    const num = el('input', { type: 'text', class: 'num', inputmode: 'decimal', value: clean(c[f.key] / k) });
    const rng = useSlider ? el('input', { type: 'range', min: f.rng[0], max: f.rng[1], step: f.rng[2], 'data-default': f.default }) : null;
    const pct = () => { if (rng) rng.style.setProperty('--f', clamp((c[f.key] - f.rng[0]) / (f.rng[1] - f.rng[0]), 0, 1)); };
    if (rng) { rng.value = c[f.key]; pct(); rng.oninput = () => { c[f.key] = +rng.value; num.value = clean(rng.value); num.classList.remove('bad'); pct(); changed(m, f, true); }; rng.onchange = () => changed(m, f); }
    num.oninput = () => { const v = Number(num.value.replace(',', '.')); const ok = num.value.trim() !== '' && Number.isFinite(v); num.classList.toggle('bad', !ok); if (ok) { c[f.key] = f.kind === 'int' ? Math.round(v) : v * k; if (rng) { rng.value = c[f.key]; pct(); } changed(m, f); } };
    wrap.append(el('div', { class: 'fld-top' }, el('label', {}, f.label), el('span', { class: 'val' }, num, el('span', { class: 'u' }, unitLabel(f)))), rng || '');
  }
  return wrap;
}
const solveLive = debounce(() => solveNow(true), 90), solveFull = debounce(() => solveNow(false), 650), solveSoon = debounce(() => solveNow(), 220);
function changed(m, f, live) {
  if (!live) refreshVisible();
  if (f.key === m.body_key && SET.unit === 'R_body') renderFields();
  if (live) { solveLive(); solveFull(); } else solveSoon();                     // while dragging a slider only the cheap 2-D view updates; the 3-D page follows once you pause
}
const refreshVisible = debounce(async () => {
  const m = mod(); if (!m) return; const r = await api('visible', { mid: m.id, vals: S.canon[m.id] }); if (r.error) return;
  document.querySelectorAll('#fields .fld').forEach(e => e.classList.toggle('hidden', !r.visible.includes(e.dataset.key)));
}, 40);

/* ---------- solving (cached; live drags skip the 3-D page) ---------- */
function progressStart() {
  const bar = $('#pbar'); if (!bar) return () => { };
  const i = bar.querySelector('i'), t = bar.querySelector('span'); bar.classList.add('on'); i.style.width = '4%'; t.textContent = 'starting';
  let stop = false, shown = 4;
  (async () => {
    while (!stop) {
      try { const g = await api('progress', {}); const target = Math.max(4, Math.min(96, (g.frac || 0) * 100)); shown = Math.max(shown, target); i.style.width = shown + '%'; if (g.stage) t.textContent = g.stage + ' · ' + Math.round(shown) + '%'; } catch (e) { }
      await new Promise(r => setTimeout(r, 110));
    }
  })();
  return () => { stop = true; i.style.width = '100%'; t.textContent = 'done · 100%'; setTimeout(() => bar.classList.remove('on'), 500); };
}
function askDialog({ title, lines, intro, actions }) {
  return new Promise(res => {
    const done = v => { document.removeEventListener('keydown', esc, true); ov.remove(); res(v); };
    const esc = e => { if (e.key === 'Escape') { e.stopPropagation(); done(actions[actions.length - 1].value); } }; document.addEventListener('keydown', esc, true);
    const ov = el('div', { class: 'modalov', onclick: e => { if (e.target === ov) done(actions[actions.length - 1].value); } },
      el('div', { class: 'modal', role: 'alertdialog' }, el('h3', {}, title), intro ? el('p', {}, intro) : '', lines && lines.length ? el('ul', {}, ...lines.map(l => el('li', {}, l))) : '',
        el('div', { class: 'btnrow' }, ...actions.map(a => el('button', { class: 'btn' + (a.pri ? ' pri' : ''), onclick: () => done(a.value) }, a.label)))));
    document.body.append(ov); const b = ov.querySelector('button.pri') || ov.querySelector('button'); if (b) b.focus();
  });
}
/** In-app replacements for the browser's confirm() and prompt() (the browser versions show "127.0.0.1:port says" in the packaged app). */
const askConfirm = (message, okLabel = 'OK', title = 'Please Confirm') => askDialog({ title, intro: message, actions: [{ label: okLabel, value: true, pri: true }, { label: 'Cancel', value: false }] });
function askText(message, { title = 'Enter a Value', placeholder = '', okLabel = 'OK' } = {}) {
  return new Promise(res => {
    const inp = el('input', { type: 'text', class: 'wide', placeholder, onkeydown: e => { if (e.key === 'Enter') done(inp.value.trim()); if (e.key === 'Escape') { e.stopPropagation(); done(null); } } });
    const done = v => { ov.remove(); res(v); };
    const ov = el('div', { class: 'modalov', onclick: e => { if (e.target === ov) done(null); } }, el('div', { class: 'modal', role: 'dialog' }, el('h3', {}, title), el('p', {}, message), inp,
      el('div', { class: 'btnrow' }, el('button', { class: 'btn pri', onclick: () => done(inp.value.trim()) }, okLabel), el('button', { class: 'btn', onclick: () => done(null) }, 'Cancel'))));
    document.body.append(ov); inp.focus();
  });
}
/** Esc cancels a running solve or mission: the page drops the answer and the server stops at its next stage. */
function cancelSolve() {
  const mis = typeof MIS !== 'undefined' && MIS.busy; if (!S.solving && !mis) return false;
  S.seq++; S.solving = false; $('#spin').classList.remove('on'); if (S.endBar) S.endBar(); S.endBar = null; api('cancel', {}); toast(mis ? 'mission run cancelled' : 'solve cancelled'); return true;
}
/** The open session (page, inputs, mission) is saved as you work and brought back by File > Restore Last Session. */
const saveSession = debounce(() => api('session_save', { session: { page: S.page, canon: S.canon, mission: typeof MIS !== 'undefined' ? MIS.m : null } }), 1200);
async function restoreSession() {
  const r = await api('session_load', {}); if (!r.ok) { toast(r.error, 'err'); return; }
  const s = r.session || {}; if (s.canon) S.canon = s.canon; if (s.mission && typeof MIS !== 'undefined') { MIS.m = s.mission; MIS.res = null; misTouch(); }
  S.cache.clear(); S.last = {}; await go(s.page || S.page); toast('last session restored', 'ok');
}
async function solveNow(live = false, explicit = false) {
  const m = mod(); if (!m) return; const id = ++S.seq;
  const payload = { mid: m.id, vals: S.canon[m.id], consts: { mode: 'Course table' }, theme: effTheme(), name: SET.name, label: SET.label, opts: solveOpts() };
  const key = JSON.stringify(payload);
  if (!live && S.cache.has(key)) { const r = S.cache.get(key); S.cache.delete(key); S.cache.set(key, r); S.res = S.last[m.id] = r; showChecks(r); renderMain(); return; }
  $('#spin').classList.add('on'); const endBar = (!live) ? progressStart() : () => { }; if (!live) { S.solving = true; S.endBar = endBar; }
  let r; try { r = await api('solve', live ? { ...payload, opts: { ...payload.opts, skip3d: true } } : payload); } catch (e) { r = { error: String(e), fatal: true }; }
  endBar(); if (id !== S.seq) return; S.solving = false; $('#spin').classList.remove('on');
  if (explicit && !live) {                                                                 // the Solve button: tell the user about math problems instead of silently drawing them
    if (r.error) {
      await askDialog({ title: 'Cannot Solve With These Inputs', intro: r.error, lines: ['nothing was drawn, so there is nothing to continue with', 'adjust the inputs (the values, the body, or the root choice) and press solve & draw again'], actions: [{ label: 'Adjust Inputs', value: 'adjust', pri: true }] });
    } else if ((r.problems || []).length) {
      const go = await askDialog({ title: 'The Solver Reported a Problem', intro: 'the calculation finished but something may be wrong with these inputs:', lines: [...r.problems, ...r.warnings], actions: [{ label: 'Adjust Inputs', value: 'adjust' }, { label: 'Continue Anyway', value: 'go', pri: true }] });
      if (go !== 'go') { if (S.last[m.id]) { S.res = S.last[m.id]; showChecks(S.res); renderMain(); } return; }
    }
  }
  showChecks(r); saveSession();
  if (live && !r.error && updateLive(r)) return;                                  // in-place 2-D update, 3-D frame untouched
  S.res = r; if (S.scene >= (r.scenes || []).length) S.scene = 0;
  if (!r.error) { S.last[m.id] = r; S.cache.set(key, r); if (S.cache.size > 14) S.cache.delete(S.cache.keys().next().value); }
  renderMain();
}
function updateLive(r) {
  const sc = r.scenes[S.scene], host = $('.c2d .svgw'); if (!host || S.tab !== 'Plots' || !sc) return false;
  host.innerHTML = sc.svg; const c4 = $('.cards4'); if (c4) c4.replaceWith(cardsEl(r.cards)); return true;
}
function showChecks(r) {
  const c = $('#checks'); if (!c) return; c.replaceChildren();
  if (r.error) { c.append(chk('err', '✕', r.error)); return; }
  for (const w of [...(r.problems || []), ...r.warnings]) c.append(chk('warn', '!', w));
  for (const k of r.checks) c.append(chk('ok', '✓', k));
}
const chk = (cls, ic, t) => el('div', { class: 'chk ' + cls }, el('span', { class: 'ic' }, ic), el('span', {}, t));

/* ---------- main area: the Plots tab is a dock of movable tiles, the other tabs are plain pages ---------- */
function tabRow(r) {
  const tabs = ['Plots', 'Step-by-Step', ...r.tabs.map(t => apa(t.name)), 'Export Figure'];
  const closed = ['inputs', 'v3d', 'v2d', 'results'].filter(isClosed);
  const views = el('div', { class: 'seg viewseg', title: 'choose the 3d view, the 2d figure, or both' }, ...[['3d', '3D'], ['2d', '2D'], ['both', '3D + 2D']].map(([v, l]) =>
    el('button', { class: SET.view === v ? 'on' : '', onclick: () => { SET.view = v; saveSet(); setFocus(null); renderMain(); } }, l)));
  const chips = S.tab === 'Plots' && closed.length ? el('div', { class: 'closedchips', title: 'closed panels: click to bring one back' }, ...closed.map(id => el('button', { class: 'chip', onclick: () => openTile(id) }, '+ ' + TILE_NAME[id]))) : '';
  const convSeg = el('div', { class: 'seg convseg', title: 'show this result with the default names and angles, or with GMAT parameter names (VFPA, TA 0 to 360 …). the values behind it do not change' }, ...[['course', 'Default'], ['gmat', 'GMAT']].map(([v, l]) =>
    el('button', { class: (S.conv || SET.convention || 'course') === v ? 'on' : '', onclick: () => { S.conv = v; S.cache.clear(); solveNow(); } }, l)));
  const toMission = el('button', { class: 'btn small', title: 'build the matching spacecraft, propagator, burns and stop conditions in the Mission workspace', onclick: () => openInMission() }, 'Open in Mission');
  return el('div', { class: 'tabrow' }, el('div', { class: 'tabs' }, ...tabs.map(t => el('button', { class: 'tab' + (t === S.tab ? ' on' : ''), onclick: () => { S.tab = t; renderMain(); } }, t))), chips, el('div', { class: 'tabtools' }, convSeg, toMission), S.tab === 'Plots' ? views : '');
}
function renderMain() {
  const main = $('#main'), r = S.res;
  if (S.focus && S.tab !== 'Plots') setFocus(null);
  if (!r || r.error || S.tab === undefined) {
    unmountDock(); main.replaceChildren(); if (!r) return;
    main.append(el('div', { class: 'empty' }, r.error)); if (r.trace) main.append(el('pre', {}, r.trace)); return;
  }
  const tabs = ['Plots', 'Step-by-Step', ...r.tabs.map(t => apa(t.name)), 'Export Figure']; if (!tabs.includes(S.tab)) S.tab = 'Plots';
  if (S.tab !== 'Plots') {
    unmountDock(); main.replaceChildren(tabRow(r));
    if (S.tab === 'Step-by-Step') steps(main, r); else if (S.tab === 'Export Figure') exportTab(main, r); else extra(main, r.tabs.find(t => apa(t.name) === S.tab));
    return;
  }
  ensureDock(main);
  $('#tabhost').replaceChildren(tabRow(r)); const sc = r.scenes[S.scene];
  $('#scenehost').replaceChildren(...(r.scenes.length > 1 ? [el('div', { class: 'scenebar' }, ...r.scenes.map((s, i) => el('button', { class: 'chip' + (i === S.scene ? ' on' : ''), onclick: () => { S.scene = i; renderMain(); } }, s.name === 'main' ? 'Overview' : s.name)))] : []),
    ...(sc.notes || []).map(n => el('div', { class: 'dim', style: 'margin:0 0 8px' }, n)));
  const vis = visibleTiles();
  $('#tile-v3d .tbody').replaceChildren(...(vis.has('v3d') ? [card3d(sc)] : []));
  $('#tile-v2d .tbody').replaceChildren(...(vis.has('v2d') ? [card2d(sc)] : []));
  $('#tile-results .tbody').replaceChildren(el('div', { class: 'tilehead' }, 'Results'), cardsEl(r.cards), ...r.figs.map(f => el('div', { class: 'cardx', style: 'margin-top:14px;padding:12px;flex:none' }, el('div', { class: 'svgw', html: f.svg }))));
  layoutDock();
}
function cardsEl(cards) {
  return el('div', { class: 'cards4' }, ...cards.map(c => el('div', { class: 'cardx sc' },
    el('div', { class: 'hd' }, el('span', { class: 't' }, c.title), c.pill ? el('span', { class: 'bp' }, c.pill) : el('span', { class: 'h' }, c.headline || '')),
    ...c.rows.map(([a, b]) => el('div', { class: 'r' }, el('span', { class: 'a' }, a), typeof b === 'object' ? el('span', { class: 'bp g' }, b.pill) : el('span', { class: 'b' }, b))))));
}
function card3d(sc) {
  const fr = el('iframe'); fr.srcdoc = sc.html3d;
  return el('div', { class: 'cardx c3d' }, el('h3', {}, el('b', {}, '3D View'), el('span', { class: 'hint' }, ' · rotate with mouse'), fbar('v3d')), el('div', { class: 'body' }, fr));
}
function card2d(sc) {
  return el('div', { class: 'cardx c2d' }, el('h3', {}, el('b', {}, '2D View'), el('span', { class: 'hint' }, ' · submit-ready'), fbar('v2d')),
    el('div', { class: 'body' }, el('div', { class: 'svgw', html: sc.svg }), sc.overlaps ? el('div', { class: 'ovl' }, `${sc.overlaps} label overlap(s)`) : null));
}

/* ---------- dock: tiles you can drag anywhere; the layout adapts so every tile keeps a usable size ---------- */
const TILE_IDS = ['inputs', 'v3d', 'v2d', 'results'];
const TILE_MIN = { inputs: [300, 320], v3d: [340, 300], v2d: [300, 300], results: [280, 150] };       // minimum [width, height] in px
const STACK_H = { inputs: 520, v3d: 540, v2d: 540, results: 380 };                                    // heights when the window is too small and tiles stack
const GAP = 8;
const DOCK_DEFAULT = { t: 's', d: 'h', r: 0.27, a: { t: 't', id: 'inputs' }, b: { t: 's', d: 'v', r: 0.73, a: { t: 's', d: 'h', r: 0.56, a: { t: 't', id: 'v3d' }, b: { t: 't', id: 'v2d' } }, b: { t: 't', id: 'results' } } };
const DOCK = { rects: {} };
function dockValid(n, seen = new Set()) {
  if (!n || (n.t !== 't' && n.t !== 's')) return false;
  if (n.t === 't') { if (!TILE_IDS.includes(n.id) || seen.has(n.id)) return false; seen.add(n.id); return true; }
  return (n.d === 'h' || n.d === 'v') && typeof n.r === 'number' && dockValid(n.a, seen) && dockValid(n.b, seen) && (!n.a || true) && seen.size >= 0;
}
function getDock() {
  const seen = new Set(); if (!LAY.dock || !dockValid(LAY.dock, seen) || seen.size !== TILE_IDS.length) LAY.dock = fresh(DOCK_DEFAULT);
  return LAY.dock;
}
const TILE_NAME = { inputs: 'Inputs', v3d: '3D View', v2d: '2D View', results: 'Results' };
const isClosed = id => (LAY.closed || []).includes(id);
function visibleTiles() {
  const v = new Set(); if (!isClosed('inputs')) v.add('inputs'); if (!isClosed('results')) v.add('results');
  if (SET.view !== '2d' && !isClosed('v3d')) v.add('v3d'); if (SET.view !== '3d' && !isClosed('v2d')) v.add('v2d');
  if (!S.focus) return v;
  const f = new Set([S.focus]); if (S.fshow.inputs) f.add('inputs'); if (S.fshow.results) f.add('results'); return f;
}
function closeTile(id) { if (S.focus) setFocus(null); LAY.closed = [...new Set([...(LAY.closed || []), id])]; saveSet(); renderMain(); }
function openTile(id) { LAY.closed = (LAY.closed || []).filter(x => x !== id); saveSet(); renderMain(); }
function resetPanels() { if (S.page === 'mission' && typeof DDOCK !== 'undefined') { DDOCK.reset(); toast('panels reset to the default arrangement'); return; } setFocus(null); LAY.dock = fresh(DOCK_DEFAULT); LAY.closed = []; saveSet(); if (S.tab === 'Plots' && isMod()) renderMain(); toast('panels reset to the default arrangement'); }
const prune = (n, vis) => {
  if (n.t === 't') return vis.has(n.id) ? n : null;
  const a = prune(n.a, vis), b = prune(n.b, vis); if (!a) return b; if (!b) return a; return { t: 's', d: n.d, r: n.r, a, b, src: n.src || n };
};
function minSize(n) {
  if (n.t === 't') return TILE_MIN[n.id];
  const A = minSize(n.a), B = minSize(n.b); return n.d === 'h' ? [A[0] + B[0] + GAP, Math.max(A[1], B[1])] : [Math.max(A[0], B[0]), A[1] + B[1] + GAP];
}
function place(n, x, y, w, h, rects, splits) {
  if (n.t === 't') { rects[n.id] = { x, y, w, h }; return; }
  const A = minSize(n.a), B = minSize(n.b);
  if (n.d === 'h') {
    const avail = w - GAP, wa = clamp(avail * n.r, A[0], Math.max(A[0], avail - B[0]));
    splits.push({ n, d: 'h', x: x + wa, y, w: GAP, h, start: x, size: avail }); place(n.a, x, y, wa, h, rects, splits); place(n.b, x + wa + GAP, y, avail - wa, h, rects, splits);
  } else {
    const avail = h - GAP, ha = clamp(avail * n.r, A[1], Math.max(A[1], avail - B[1]));
    splits.push({ n, d: 'v', x, y: y + ha, w, h: GAP, start: y, size: avail }); place(n.a, x, y, w, ha, rects, splits); place(n.b, x, y + ha + GAP, w, avail - ha, rects, splits);
  }
}
function ensureDock(main) {
  if ($('#dock')) return;
  unmountDock(); main.replaceChildren(el('div', { id: 'tabhost' }), el('div', { id: 'scenehost' }), el('div', { id: 'dock' }, el('div', { id: 'dockin' })));
  for (const id of TILE_IDS) $('#dockin').append(el('div', { class: 'tile', id: 'tile-' + id, 'data-id': id }, el('div', { class: 'tbody' }),
    el('button', { class: 'trash', title: 'close this panel (bring it back with the buttons above the plots, view menu, or f8)', onclick: () => closeTile(id) }, ico('close')),
    el('button', { class: 'grip', title: 'drag to move this panel: drop it on another panel (left, right, top, bottom or center to swap) or on a window edge', onpointerdown: e => startTileDrag(id, e) }, '⠿')));
  $('#tile-inputs .tbody').append($('#panel')); $('#app').classList.add('docked');
  new ResizeObserver(() => layoutDock()).observe($('#dock'));
}
function unmountDock() {
  const d = $('#dock'); if (!d) return;
  const panel = $('#panel'); if (panel) $('#app').insertBefore(panel, $('#main'));              // the input panel goes back to its own column
  $('#app').classList.remove('docked'); d.remove();
}
function layoutDock() {
  const dock = $('#dock'); if (!dock) return;
  const W = dock.clientWidth, H = dock.clientHeight, vis = visibleTiles(), tree = prune(getDock(), vis), din = $('#dockin');
  din.querySelectorAll('.dsplit').forEach(e => e.remove());
  const rects = {}, splits = []; let totalH = H;
  if (tree) {
    const [mw, mh] = minSize(tree);
    if (vis.size > 1 && (W < mw || H < mh)) { let y = 0; for (const id of TILE_IDS.filter(i => vis.has(i))) { rects[id] = { x: 0, y, w: W, h: STACK_H[id] }; y += STACK_H[id] + GAP; } totalH = Math.max(H, y - GAP); }   // too small: stack and scroll
    else place(tree, 0, 0, W, H, rects, splits);
  }
  din.style.height = totalH + 'px'; dock.classList.toggle('stacked', totalH > H + 1); DOCK.rects = rects;
  for (const id of TILE_IDS) {
    const t = $('#tile-' + id), r = rects[id]; if (!t) continue;
    if (!r) { t.style.display = 'none'; continue; }
    t.style.display = ''; Object.assign(t.style, { left: r.x + 'px', top: r.y + 'px', width: r.w + 'px', height: r.h + 'px' });
  }
  for (const sp of splits) { const d = el('div', { class: 'dsplit ' + sp.d }); Object.assign(d.style, { left: sp.x + 'px', top: sp.y + 'px', width: sp.w + 'px', height: sp.h + 'px' }); d.onpointerdown = e => splitDrag(e, sp); din.append(d); }
}
function dragWindow(onmove, onup) {
  document.body.classList.add('dragging');
  const mv = e => onmove(e), up = e => { window.removeEventListener('pointermove', mv); window.removeEventListener('pointerup', up); document.body.classList.remove('dragging'); onup && onup(e); };
  window.addEventListener('pointermove', mv); window.addEventListener('pointerup', up);
}
function splitDrag(e, sp) {
  e.preventDefault(); const dock = $('#dock'), src = sp.n.src || sp.n;
  dragWindow(ev => { const b = dock.getBoundingClientRect(); const pos = sp.d === 'h' ? ev.clientX - b.left : ev.clientY - b.top + dock.scrollTop; src.r = clamp((pos - sp.start) / sp.size, 0.04, 0.96); layoutDock(); }, () => saveSet());
}
/* tree edits (always on the full stored tree, hidden tiles included) */
function removeTile(n, id) { if (n.t === 't') return n.id === id ? null : n; const a = removeTile(n.a, id), b = removeTile(n.b, id); if (!a) return b; if (!b) return a; n.a = a; n.b = b; return n; }
function insertAt(n, target, id, zone) {
  if (n.t === 't') { if (n.id !== target) return n; const T = { t: 't', id }, first = zone === 'l' || zone === 't'; return { t: 's', d: zone === 'l' || zone === 'r' ? 'h' : 'v', r: 0.5, a: first ? T : n, b: first ? n : T }; }
  n.a = insertAt(n.a, target, id, zone); n.b = insertAt(n.b, target, id, zone); return n;
}
function swapTiles(n, x, y) { if (n.t === 't') { if (n.id === x) n.id = y; else if (n.id === y) n.id = x; return; } swapTiles(n.a, x, y); swapTiles(n.b, x, y); }
function dropTarget(px, py, dragId, W, H) {
  const E = 36;
  if (px < E) return { zone: 'l', edge: true, rect: { x: 0, y: 0, w: Math.min(W * 0.3, 420), h: H } };
  if (px > W - E) return { zone: 'r', edge: true, rect: { x: W - Math.min(W * 0.3, 420), y: 0, w: Math.min(W * 0.3, 420), h: H } };
  if (py < E) return { zone: 't', edge: true, rect: { x: 0, y: 0, w: W, h: Math.min(H * 0.3, 320) } };
  if (py > H - E) return { zone: 'b', edge: true, rect: { x: 0, y: H - Math.min(H * 0.3, 320), w: W, h: Math.min(H * 0.3, 320) } };
  for (const [id, r] of Object.entries(DOCK.rects)) {
    if (id === dragId || px < r.x || px > r.x + r.w || py < r.y || py > r.y + r.h) continue;
    const u = (px - r.x) / r.w, v = (py - r.y) / r.h, zone = u < 0.28 ? 'l' : u > 0.72 ? 'r' : v < 0.28 ? 't' : v > 0.72 ? 'b' : 'c';
    const rect = zone === 'l' ? { x: r.x, y: r.y, w: r.w / 2, h: r.h } : zone === 'r' ? { x: r.x + r.w / 2, y: r.y, w: r.w / 2, h: r.h } : zone === 't' ? { x: r.x, y: r.y, w: r.w, h: r.h / 2 } : zone === 'b' ? { x: r.x, y: r.y + r.h / 2, w: r.w, h: r.h / 2 } : r;
    return { id, zone, rect };
  }
  return null;
}
function applyDrop(id, tgt) {
  let t = fresh(getDock());
  if (tgt.zone === 'c') swapTiles(t, id, tgt.id);
  else {
    t = removeTile(t, id);
    if (tgt.edge) { const first = tgt.zone === 'l' || tgt.zone === 't'; const T = { t: 't', id }; t = { t: 's', d: tgt.zone === 'l' || tgt.zone === 'r' ? 'h' : 'v', r: first ? 0.3 : 0.7, a: first ? T : t, b: first ? t : T }; }
    else t = insertAt(t, tgt.id, id, tgt.zone);
  }
  LAY.dock = t; saveSet(); layoutDock();
}
function startTileDrag(id, e) {
  e.preventDefault(); const dock = $('#dock'), sx = e.clientX, sy = e.clientY, dz = el('div', { class: 'dz' }), ov = el('div', { id: 'dropov' }, dz); let moved = false, tgt = null;
  dragWindow(ev => {
    if (!moved && Math.hypot(ev.clientX - sx, ev.clientY - sy) < 5) return;
    if (!moved) { moved = true; dock.append(ov); $('#tile-' + id).classList.add('lifted'); }
    const b = dock.getBoundingClientRect(), px = ev.clientX - b.left + dock.scrollLeft, py = ev.clientY - b.top + dock.scrollTop;
    tgt = dropTarget(px, py, id, dock.clientWidth, dock.clientHeight);
    if (tgt) { dz.style.display = 'block'; Object.assign(dz.style, { left: tgt.rect.x + 'px', top: tgt.rect.y + 'px', width: tgt.rect.w + 'px', height: tgt.rect.h + 'px' }); } else dz.style.display = 'none';
  }, () => { ov.remove(); const t = $('#tile-' + id); if (t) t.classList.remove('lifted'); if (moved && tgt) applyDrop(id, tgt); });
}

/* ---------- focus mode: only the chosen tile stays (menu / inputs / results come back when switched on) ---------- */
function fbar(kind) {
  const w = el('div', { class: 'fbtns', 'data-kind': kind });
  if (S.focus !== kind) { w.append(el('button', { title: 'hide every panel except this view (esc leaves)', onclick: () => setFocus(kind) }, '⤢ Focus')); return w; }
  const t = (k, label) => el('button', { class: S.fshow[k] ? 'on' : '', title: 'show or hide', onclick: () => { S.fshow[k] = !S.fshow[k]; applyFocus(); } }, label);
  w.append(t('menu', 'Menu'), t('inputs', 'Inputs'), t('results', 'Results'), el('button', { onclick: () => ACTIONS.fullscreen() }, 'Full Screen'), el('button', { class: 'pri', onclick: () => setFocus(null) }, 'Exit'));
  return w;
}
function applyFocus() {
  const b = document.body; b.classList.toggle('plotfocus', !!S.focus); b.dataset.focus = S.focus || '';
  for (const k of ['menu', 'inputs', 'results']) b.classList.toggle('fshow-' + k, !!S.fshow[k]);
  document.querySelectorAll('.fbtns[data-kind]').forEach(w => w.replaceWith(fbar(w.dataset.kind)));            // buttons update in place: the 3-D page is not reloaded
  layoutDock();
}
function setFocus(kind) { S.focus = kind; if (!kind) S.fshow = { menu: false, inputs: false, results: false }; applyFocus(); }

function table(cols, rows, hl, cls = 'c1') {
  return el('table', { class: 'tbl ' + cls }, el('thead', {}, el('tr', {}, ...cols.map(c => el('th', {}, c)))),
    el('tbody', {}, ...rows.map((r, i) => el('tr', { class: i === hl ? 'hl' : '' }, ...r.map(v => el('td', {}, v))))));
}
function steps(main, r) {
  for (const g of r.groups) {
    const t = el('table', { class: 'tbl c1' }, el('thead', {}, el('tr', {}, ...['Quantity', 'Symbol', 'Value', 'Units', 'Equation / Note'].map(c => el('th', {}, c)))),
      el('tbody', {}, ...g.rows.map(([n, s, v, u, eq, no]) => el('tr', {}, el('td', {}, n), el('td', { class: 's' }, s), el('td', { class: 'v' }, v.replace(/ \(.*\)$/, '')), el('td', { class: 's' }, u === '—' ? '' : u), el('td', { class: 'eq' }, [eq, no].filter(Boolean).join('  ·  '))))));
    main.append(el('div', { class: 'sheet' }, g.name ? el('h3', {}, g.name) : null, t));
  }
  if (r.checks.length) main.append(el('div', { class: 'sheet' }, el('h3', {}, 'Quadrant and Sanity Checks'), ...r.checks.map(k => chk('ok', '✓', k))));
}
function extra(main, t) {
  main.append(el('div', { class: 'sheet' }, el('h3', {}, t.name), el('div', { class: 'dim' }, t.note), table(t.columns, t.rows, t.highlight)));
}
/** Busy bar: a slim status bar at the bottom of the window plus a busy cursor while a slow action the user started is running (exports, backups). */
let BUSY = 0;
async function busy(text, work) {
  const bar = $('#busybar'); BUSY++; document.body.classList.add('busy'); bar.querySelector('span').textContent = text; bar.classList.add('on');
  try { return await work(); } finally { if (--BUSY === 0) { bar.classList.remove('on'); document.body.classList.remove('busy'); } }
}
/** Quit: asks first (Preferences > Appearance can turn that off); the window host calls this when the window's close button is pressed. */
async function askQuit() {
  if (SET.confirmQuit !== false && !await askConfirm('your session is saved automatically; File > Restore Last Session brings it back next time.', 'Quit', 'Quit OrbSim')) return;
  await api('session_save', { session: { page: S.page, canon: S.canon, mission: typeof MIS !== 'undefined' ? MIS.m : null } });
  const r = await api('quit', {}); if (r.mode === 'browser') window.close();
}
async function saveExport(idx, fmt, theme) {
  const r = await busy('exporting', () => api('export_save', { idx, fmt, theme })); toast(r.ok ? 'saved to ' + r.path : r.error, r.ok ? 'ok' : 'err');
}
function exportTab(main, r) {
  main.append(el('div', { class: 'sheet' }, el('h3', {}, 'Export Figures'),
    el('div', { class: 'dim' }, 'png and pdf files are rendered at 300 dpi. python and matlab scripts redraw the 3d and 2d plots with latex labels. the figure title carries your name and the problem label (set both under settings).'),
    el('div', { class: 'dim' }, 'files are saved to ' + META.paths.exports),
    el('div', { class: 'btnrow' }, el('button', { class: 'btn', onclick: () => api('open_folder', { which: 'exports' }) }, 'Open Exports Folder'))));
  r.scenes.forEach((s, i) => main.append(el('div', { class: 'sheet' }, el('h3', {}, s.name === 'main' ? 'Overview' : s.name),
    el('div', { class: 'btnrow' }, ...['light', 'dark'].flatMap(t => ['png', 'pdf'].map(f => el('button', { class: 'btn', onclick: () => saveExport(i, f, t) }, `${f.toUpperCase()} · ${t}`))),
      el('button', { class: 'btn', onclick: () => saveExport(i, 'html', 'light') }, '3D Page (.html)'),
      el('button', { class: 'btn', onclick: () => saveExport(i, 'py', 'light') }, 'Python Script (.py)'),
      el('button', { class: 'btn', onclick: () => saveExport(i, 'm', 'light') }, 'MATLAB Script (.m)'),
      i === 0 ? el('button', { class: 'btn', title: 'a GMAT R2022a script that rebuilds this result (always in GMAT convention)', onclick: () => saveExport(i, 'script', 'light') }, 'GMAT Script (.script)') : ''))));
  if (!SET.name) main.append(el('div', { class: 'chk warn' }, el('span', { class: 'ic' }, '!'), el('span', {}, 'enter your name under settings: homework figures must carry it.')));
}

/* ---------- utility pages ---------- */
function renderUtil() {
  unmountDock(); const main = $('#main'); main.replaceChildren();
  if (S.page === 'const') return constPage(main);
  if (S.page === 'jd') return jdPage(main);
  if (S.page === 'settings') return settingsPage(main);
  if (S.page === 'mission') return renderMission();
  return testsPage(main);
}
function constPage(main) {
  const rows = Object.entries(META.bodies).map(([n, b]) => {
    const mu = b.mu, R = b.R;
    return [n, el('span', { class: 'bsym' }, (BODY_SYM[n] || '') + '︎'), mu.toLocaleString('en-US', { maximumFractionDigits: 6 }), R.toLocaleString('en-US'), b.a ? b.a.toLocaleString('en-US') : '—', b.e != null ? String(b.e) : '—'];
  });
  main.append(el('div', { class: 'sheet' }, el('h3', {}, 'Body Constants — JPL / GMAT 2020a'), table(['Body', 'Symbol', 'μ (km³·s⁻²)', 'R (km)', 'a (km)', 'e'], rows),
    el('div', { class: 'dim', style: 'margin-top:10px' }, `1 au = ${META.AU.toLocaleString('en-US')} km (reproduces the hw4 numbers). the table lists earth’s a = 149 597 898 km: use that for “earth’s orbit radius”. julian year = 365.25 d, hw4 months = 30 d, jd day = 86 400 s.`)));
}
function jdPage(main) {
  const out = () => el('div', { class: 'big' }, '—'), f = (id, v, w) => el('input', { type: 'number', id, value: v, style: w ? `width:${w}px` : '' });
  const o1 = out(), o2 = out(), o3 = out(), s1 = el('div', { class: 'dim' }), s2 = el('div', { class: 'dim' }), s3 = el('div', { class: 'dim' });
  const val = id => $('#' + id).value;
  const c1 = async () => { const r = await api('jd', { type: 'cal2jd', Y: val('y1'), M: val('m1'), D: val('d1'), h: val('h1'), mi: val('i1'), s: val('s1') }); o1.textContent = r.error ? r.error : r.jd.toFixed(6); s1.textContent = (r.weekday || '').toLowerCase(); };
  const c2 = async () => { const r = await api('jd', { type: 'jd2cal', jd: val('j2') }); o2.textContent = r.error ? r.error : r.text; s2.textContent = (r.weekday || '').toLowerCase(); };
  const c3 = async () => { const r = await api('jd', { type: 'et2ut', Y: val('y3'), M: val('m3'), D: val('d3'), h: val('h3'), mi: val('i3') }); o3.textContent = r.error ? r.error : r.text; s3.textContent = r.jd ? 'jd ' + r.jd.toFixed(5) : ''; };
  main.append(el('div', { class: 'grid3' },
    el('div', { class: 'sheet' }, el('h3', {}, 'Calendar (UT) → Julian Date'), el('div', { class: 'row', oninput: c1 }, f('y1', 2000), f('m1', 1), f('d1', 1), f('h1', 12), f('i1', 0), f('s1', 0)), el('div', { class: 'dim' }, 'year · month · day · h · min · s'), o1, s1),
    el('div', { class: 'sheet' }, el('h3', {}, 'Julian Date → Calendar (UT)'), el('div', { class: 'row', oninput: c2 }, f('j2', 2451545, 200)), o2, s2),
    el('div', { class: 'sheet' }, el('h3', {}, 'US Eastern → UT (“Friday 9:30 am ET”)'), el('div', { class: 'row', oninput: c3 }, f('y3', 2024), f('m3', 10), f('d3', 4), f('h3', 9), f('i3', 30)), el('div', { class: 'dim' }, 'year · month · day · et hour · et min (daylight saving applied)'), o3, s3)));
  c1(); c2(); c3();
}
async function testsPage(main) {
  main.append(el('div', { class: 'sheet' }, el('h3', {}, 'Test Cases — Computed vs. Printed Solution Values'),
    el('div', { class: 'dim' }, 'every preset runs through the same code as the module pages. tolerance is relative 2×10⁻⁴ unless the solution prints fewer digits. corrected (erratum) values are noted on the problems they affect.'),
    el('div', { class: 'btnrow' }, el('button', { class: 'btn pri', id: 'runT', onclick: runTests }, 'Run All Test Cases'))), el('div', { id: 'tres' }));
  if (S.tests) showTests(S.tests); else runTests();
}
async function runTests() { $('#spin').classList.add('on'); S.tests = await api('tests'); $('#spin').classList.remove('on'); showTests(S.tests); }
function showTests(t) {
  const box = $('#tres'); if (!box) return; const det = {}; t.detail.forEach(d => det[d.mid + ':' + d.idx] = d.rows);
  const fmt = x => x == null ? '—' : (+x).toPrecision(8).replace(/\.?0+$/, '').replace(/\.?0+e/, 'e');
  const tb = el('tbody'); t.summary.forEach(s => {
    const key = s.mid + ':' + s.idx; const row = el('tr', { class: 'clk' }, el('td', {}, 'M' + s.mid + ' · ' + s.module), el('td', {}, s.problem), el('td', {}, `${s.passed}/${s.checks}`), el('td', {}, el('span', { class: 'badge ' + (s.status === 'pass' ? 'pass' : 'fail') }, s.status === 'pass' ? 'pass' : s.status)));
    const d = el('tr', { hidden: true }, el('td', { colspan: 4 })); row.onclick = () => {
      d.hidden = !d.hidden; if (d.hidden || d.firstChild.childNodes.length) return; const rows = det[key] || [];
      d.firstChild.append(el('div', { class: 'sheet', style: 'margin:8px 0' }, s.note ? el('div', { class: 'pnote' }, 'ℹ ' + s.note) : null,
        table(['Quantity', 'Computed', 'Expected', 'Rel. Error', 'Tol.', ''], rows.map(q => [q.name, fmt(q.got), fmt(q.expected), q.got == null ? '—' : (Math.abs(q.got - q.expected) / Math.abs(q.expected)).toExponential(1), q.rtol.toExponential(0), q.ok ? '✓' : '✕ ' + (q.error || '')])),
        el('div', { class: 'btnrow', style: 'margin:10px 0 0' }, el('button', { class: 'btn', onclick: ev => { ev.stopPropagation(); const m = META.modules.find(x => x.id === s.mid); S.page = s.mid; buildNav(); $('#app').classList.remove('wide'); renderPanel(); loadPreset(m, s.idx); } }, 'Open in Module'))));
    };
    tb.append(row, d);
  });
  box.replaceChildren(el('div', { class: 'sheet' }, el('h3', {}, `${t.passed} / ${t.total} Checks Passed`), el('table', { class: 'tbl c12' }, el('thead', {}, el('tr', {}, ...['Module', 'Problem', 'Checks', ''].map(c => el('th', {}, c)))), tb)));
}

/* ---------- settings page ---------- */
const seg = (opts, cur, pick) => { const w = el('div', { class: 'seg' }); opts.forEach(([v, label]) => w.append(el('button', { class: v === cur ? 'on' : '', onclick: () => { pick(v); w.querySelectorAll('button').forEach((b, i) => b.classList.toggle('on', opts[i][0] === v)); } }, label))); return w; };
const setRow = (title, desc, ...ctl) => el('div', { class: 'setrow' }, el('div', { class: 'lt' }, el('div', { class: 't' }, title), desc ? el('div', { class: 'dim' }, desc) : null), el('div', { class: 'ctl' }, ...ctl));
const SET_TABS = ['Appearance', 'Figures and Animation', 'Figure Title', 'Constants and Units', 'Conventions', 'Ephemeris and GMAT', 'Inputs', 'Key Bindings', 'Layout', 'Backup', 'Local Files', 'Help', 'About'];
const redo3d = () => { S.cache.clear(); S.last = {}; };
async function refreshBackups() { const r = await api('backup_list'); S.backups = r.ok ? r.backups : []; if (S.page === 'settings' && S.setTab === 'Backup') renderUtil(); }
function afterRestore(r) {
  Object.assign(SET, r.settings || {}); SET.const = 'Course table'; Object.assign(LAY, fresh(LAY_DEFAULT), SET.layout || {}); LAY.groups = { ...LAY_DEFAULT.groups, ...(LAY.groups || {}) }; SET.layout = LAY;
  S.backups = r.backups; S.cache.clear(); S.last = {}; applyLayout(); syncChrome(); buildNav(); renderUtil();
}
function backupPage() {
  if (S.backups === null) { refreshBackups(); return el('div', { class: 'sheet' }, el('div', { class: 'dim' }, 'loading backups…')); }
  const file = el('input', { type: 'file', accept: '.zip', style: 'display:none', onchange: async e => {
    const f = e.target.files[0]; if (!f) return; const buf = new Uint8Array(await f.arrayBuffer()); let bin = ''; for (let i = 0; i < buf.length; i += 0x8000) bin += String.fromCharCode.apply(null, buf.subarray(i, i + 0x8000));
    const r = await api('backup_import', { filename: f.name, data: btoa(bin) }); e.target.value = '';
    if (r.ok) { afterRestore(r); toast(`imported ${r.restored} files; a safety backup was made first (${r.safety})`, 'ok'); } else toast(r.error, 'err');
  } });
  const rows = S.backups.map(b => [b.name, b.modified, b.invalid ? 'not a valid backup' : `${b.files} files`, `${(b.size / 1024).toFixed(0)} kb`,
    el('span', { class: 'btnrow', style: 'margin:0;gap:6px' },
      el('button', { class: 'btn', disabled: !!b.invalid, onclick: async () => { if (!await askConfirm(`restore "${b.name}"? your current data is backed up first.`, 'Restore', 'Restore Backup')) return; const r = await api('backup_restore', { name: b.name }); if (r.ok) { afterRestore(r); toast(`restored ${r.restored} files (safety backup: ${r.safety})`, 'ok'); } else toast(r.error, 'err'); } }, 'Restore'),
      el('a', { class: 'btn', href: '/backup/' + encodeURIComponent(b.name), download: '' }, 'Save Copy'),
      el('button', { class: 'btn', onclick: async () => { if (!await askConfirm(`delete "${b.name}"?`, 'Delete', 'Delete Backup')) return; const r = await api('backup_delete', { name: b.name }); if (r.ok) { S.backups = r.backups; renderUtil(); } else toast(r.error, 'err'); } }, 'Delete'))]);
  return el('div', {},
    el('div', { class: 'sheet' },
      setRow('Create a Backup', 'zips your settings, exports and screenshots into the backups folder', el('button', { class: 'btn pri', onclick: async () => { const r = await busy('creating backup', () => api('backup_create', {})); if (r.ok) { S.backups = r.backups; renderUtil(); toast('backup saved to ' + r.path, 'ok'); } else toast(r.error, 'err'); } }, 'Create Backup')),
      setRow('Import a Backup', 'choose a backup zip from anywhere (for example from another computer). your current data is backed up automatically first', file, el('button', { class: 'btn', onclick: () => file.click() }, 'Import Backup…')),
      setRow('Backups Folder', 'kept in the app data folder; copy files out of it to store them elsewhere', el('button', { class: 'btn', onclick: () => api('open_folder', { which: 'backups' }) }, 'Open'))),
    el('div', { class: 'sheet' }, el('h3', {}, 'Your Backups'), S.backups.length ? table(['File', 'Created', 'Contents', 'Size', ''], rows, -1, 'c1') : el('div', { class: 'dim' }, 'no backups yet')));
}
function helpPage() {
  const title = el('input', { type: 'text', placeholder: 'short summary of the problem', style: 'width:100%' }), desc = el('textarea', { placeholder: 'what happened, and what did you expect?', rows: 5 });
  const log = el('input', { type: 'checkbox', checked: true });
  return el('div', {},
    el('div', { class: 'sheet' }, el('h3', {}, 'Tutorial'), el('div', { class: 'dim' }, 'a guided tour of the window: menus, panels, solving, the 3d and 2d views, the mission workspace and settings. it also starts once on your first launch.'),
      el('div', { class: 'btnrow' }, el('button', { class: 'btn pri', onclick: () => startTour() }, 'Start the Tutorial'), el('label', { class: 'tgl' }, el('span', { class: 'dim', style: 'margin:0' }, 'show it at every launch'), el('input', { type: 'checkbox', checked: SET.tourDone === false, onchange: e => { SET.tourDone = !e.target.checked; saveSet(); } })))),
    el('div', { class: 'sheet' }, el('h3', {}, 'Report an Issue'),
      el('div', { class: 'dim' }, 'this opens a pre-filled issue form on github (public, searchable, no email needed). you review it and press submit yourself; nothing is sent automatically. your home folder name is removed from log lines.'),
      el('div', { class: 'flab' }, 'Title'), title, el('div', { class: 'flab', style: 'margin-top:10px' }, 'Description'), desc,
      el('label', { class: 'tgl', style: 'margin:10px 0' }, el('span', { class: 'dim', style: 'margin:0' }, 'include the last log lines'), log),
      el('div', { class: 'btnrow' }, el('button', { class: 'btn pri', onclick: async () => {
        const r = await api('report_issue', { title: title.value, description: desc.value, include_log: log.checked, gpu: gpuInfo(), page: isMod() ? mod().short : S.page, consts: SET.const });
        toast(r.ok ? 'opened the issue form in your browser' : r.error, r.ok ? 'ok' : 'err'); } }, 'Open Issue Form on GitHub'),
        el('button', { class: 'btn', onclick: () => api('open_folder', { which: 'logs' }) }, 'Open Logs Folder'))),
    el('div', { class: 'sheet' }, el('h3', {}, 'Graphics'),
      setRow('Graphics Card', 'the 3d view needs webgl; a dedicated gpu helps at high animation resolutions', el('span', { class: 'path' }, gpuInfo())),
      setRow('Repeat Animation', 'loop the animation when it reaches the end, or stop there (there is also a repeat button in the 3d view)', el('input', { type: 'checkbox', checked: SET.repeat !== false, onchange: e => { SET.repeat = e.target.checked; saveSet(); reRender(); } })),
      setRow('Frame Rate Monitor', 'shows the page and 3d animation frame rates in the title bar', el('input', { type: 'checkbox', checked: SET.fps, onchange: e => { SET.fps = e.target.checked; saveSet(); redo3d(); showFps(); } }))));
}
function settingsPage(main) {
  const K = keys(); const tab = SET_TABS.includes(S.setTab) ? S.setTab : 'Appearance';
  const kbd = a => el('kbd', { id: 'kbd-' + a, class: S.rebind === a ? 'wait' : '' }, S.rebind === a ? 'press a key' : K[a]);
  const reRender = () => { redo3d(); if (isMod()) solveSoon(); };
  const frames = SET.frames, custom = !FRAME_PRESETS.some(p => p[0] === frames);
  const pages = {
    'Appearance': () => el('div', { class: 'sheet' },
      el('div', { class: 'sh3' }, 'Color Theme'),
      el('div', { class: 'dim', style: 'margin:0 0 12px' }, 'the colors of the whole app and its figures (F10)'),
      el('div', { class: 'pcards' }, ...PALETTES.map(([id, name, sw]) => el('button', { class: 'pcard' + (themeKey() === id ? ' on' : ''), title: name,
        onclick: () => setPalette(id) },
        el('div', { class: 'sw' }, ...sw.map(c => el('i', { style: 'background:' + c }))), el('span', { class: 'al' }, name)))),
      el('div', { class: 'sh3', style: 'margin-top:28px' }, 'Quitting'),
      setRow('Confirm Before Quitting', 'ask before the window closes (Ctrl+Q and the close button)', el('input', { type: 'checkbox', checked: SET.confirmQuit !== false, onchange: e => { SET.confirmQuit = e.target.checked; saveSet(); } }))),
    'Figures and Animation': () => el('div', { class: 'sheet' },
      setRow('Plot Layout', 'show the 3d view, the 2d figure, or both side by side', seg([['3d', '3D'], ['2d', '2D'], ['both', '3D + 2D']], SET.view, v => { SET.view = v; saveSet(); })),
      setRow('Clouds on Earth and Venus', 'show the cloud layers in the space view (also the Clouds box in the space view controls)', el('input', { type: 'checkbox', checked: SET.clouds !== false, onchange: e => { SET.clouds = e.target.checked; saveSet(); if (typeof MIS !== 'undefined' && MIS.space) MIS.space.set('clouds', SET.clouds); } })),
      setRow('Mars Dust Storms', 'show a stylized dust haze with patchy storms on Mars in the space view (also the Dust Storms box in the space view controls)', el('input', { type: 'checkbox', checked: !!SET.dust, onchange: e => { SET.dust = e.target.checked; saveSet(); if (typeof MIS !== 'undefined' && MIS.space) MIS.space.set('dust', SET.dust); } })),
      setRow('Body Notation', 'celestial bodies in labels: astronomical symbols (r⊕) or name subscripts (r_earth)', seg([['symbol', 'Symbols'], ['name', 'Name Subscripts']], SET.bodyNotation, v => { SET.bodyNotation = v; saveSet(); reRender(); })),
      setRow('Animation Resolution', 'frames per animation: higher is smoother but heavier on the graphics card', seg([...FRAME_PRESETS.map(([n, l]) => [n, l]), ['custom', 'Custom']], custom ? 'custom' : frames, v => { if (v !== 'custom') { SET.frames = v; saveSet(); reRender(); renderUtil(); } else renderUtil(); }),
        el('input', { type: 'number', min: 60, max: 6000, step: 60, value: frames, style: 'width:90px', title: 'frames (60 to 6000)', onchange: e => { SET.frames = clamp(Math.round(+e.target.value || 480), 60, 6000); saveSet(); reRender(); renderUtil(); } })),
      setRow('3D Bodies', 'plain color spheres, or real surface textures (sun, moon and the planets except pluto)', seg([[false, 'Plain Color'], [true, 'Real Textures']], !!SET.textures, v => { SET.textures = v; saveSet(); reRender(); })),
      texQualityRows(),
      setRow('Spacecraft', 'a simple marker, or a 3d satellite model that points along the velocity', seg([['marker', 'Marker'], ['comsat', 'Satellite A'], ['probe', 'Satellite B']], SET.model, v => { SET.model = v; saveSet(); reRender(); })),
      setRow('Frame Rate Monitor', 'show frames per second for the page and the 3d animation', el('input', { type: 'checkbox', checked: SET.fps, onchange: e => { SET.fps = e.target.checked; saveSet(); redo3d(); showFps(); } })),
      el('div', { class: 'dim', style: 'margin:8px 0 0' }, 'planet textures: solar system scope (2k maps), cc by 4.0, https://www.solarsystemscope.com/textures/')),
    'Conventions': () => el('div', { class: 'sheet' },
      setRow('Convention', 'how angles and names are shown in results, steps and the mission workspace. the numbers behind them, the presets and the test cases always stay in the default convention',
        seg([['course', 'Default'], ['gmat', 'GMAT']], SET.convention || 'course', v => { SET.convention = v; S.conv = null; saveSet(); redo3d(); if (isMod()) solveSoon(); renderUtil(); })),
      el('div', { class: 'dim', style: 'margin:10px 0 6px' }, 'what changes in gmat mode (each converted line also shows the default value):'),
      table(['Quantity', 'Default', 'GMAT'], [['Flight-path angle', 'γ from the local horizon, positive when ṙ > 0', 'HFPA = γ and VFPA = 90° − γ (from the radius vector)'], ['Anomalies', 'θ*, M, E in (−180°, 180°]', 'TA, MA, EA in [0°, 360°)'],
        ['Impulse', 'Δv, α, β in VNC (α from v̄⁻ toward Ĉ)', 'Element1..3 in VNB: E1 = Δv cosβ cosα, E2 = Δv sinβ, E3 = Δv cosβ sinα'], ['Energy', 'ε', 'Energy and C3Energy = 2ε'], ['Moon', 'Moon', 'Luna'],
        ['Dates', 'calendar / Julian date', 'UTCGregorian and UTCModJulian = JD − 2430000.0']]),
      el('div', { class: 'dim', style: 'margin-top:10px' }, 'exported gmat scripts are always written in gmat convention.')),
    'Ephemeris and GMAT': () => ephemPage(),
    'Figure Title': () => el('div', { class: 'sheet' },
      setRow('Your Name', 'printed in every figure title (homework figures must carry it)', el('input', { type: 'text', value: SET.name, placeholder: 'your name', oninput: e => { SET.name = e.target.value; saveSet(); } })),
      setRow('Problem Label', 'for example hw7 p2; also printed in the figure title', el('input', { type: 'text', value: SET.label, placeholder: 'problem label', oninput: e => { SET.label = e.target.value; saveSet(); } }))),
    'Constants and Units': () => el('div', { class: 'sheet' },
      setRow('Distance Units', 'how distances are entered and shown in the input panels', seg([['km', 'km'], ['R_body', 'R_body'], ['AU', 'AU']], SET.unit, v => setSet({ unit: v }, false)))),
    'Inputs': () => el('div', { class: 'sheet' },
      setRow('Sliders for Angles and Time', 'turn off to use plain number boxes only', el('input', { type: 'checkbox', checked: SET.sliders, onchange: e => { SET.sliders = e.target.checked; saveSet(); } }))),
    'Key Bindings': () => el('div', { class: 'sheet' }, ...Object.keys(KEYS_DEFAULT).map(a => setRow(KEY_INFO[a][0], KEY_INFO[a][1], kbd(a),
        el('button', { class: 'btn', onclick: () => { S.rebind = S.rebind === a ? null : a; renderUtil(); } }, S.rebind === a ? 'Cancel' : 'Change'))),
      setRow('Defaults', 'press esc while changing a key to cancel. on a mac the function keys may need the fn key.', el('button', { class: 'btn', onclick: () => { SET.keys = {}; S.rebind = null; saveSet(); renderUtil(); toast('key bindings reset to defaults'); } }, 'Reset Key Bindings'))),
    'Layout': () => el('div', { class: 'sheet' },
      setRow('Panel Layout', 'drag a panel by its grip (⠿) onto another panel or a window edge to dock it there; drag the gaps between panels to resize', el('button', { class: 'btn', onclick: () => resetPanels() }, 'Reset Panel Layout')),
      setRow('Panel Sizes', 'drag the borders between panels to resize them; double-click a border to reset it', el('button', { class: 'btn', onclick: () => { Object.assign(LAY, fresh(LAY_DEFAULT)); applyLayout(); buildNav(); saveSet(); toast('panel sizes reset'); } }, 'Reset Panel Sizes')),
      setRow('Side Menu', 'fold the menu bar down to icons with the arrow at its top, or hide it completely', el('button', { class: 'btn', onclick: () => { LAY.fold = !LAY.fold; applyLayout(); buildNav(); saveSet(); renderUtil(); } }, LAY.fold ? 'Expand Menu' : 'Fold Menu'),
        el('button', { class: 'btn', onclick: () => { LAY.hidden = !LAY.hidden; applyLayout(); saveSet(); renderUtil(); } }, LAY.hidden ? 'Show Menu' : 'Hide Menu'))),
    'Backup': backupPage,
    'Local Files': () => el('div', { class: 'sheet' },
      setRow('App Data Folder', 'settings, screenshots, exports, backups and logs are stored here and never uploaded', el('span', { class: 'path' }, META.paths.root), el('button', { class: 'btn', onclick: () => api('open_folder', { which: 'root' }) }, 'Open')),
      setRow('Screenshots', 'saved by the screenshot key', el('span', { class: 'path' }, META.paths.screenshots), el('button', { class: 'btn', onclick: () => api('open_folder', { which: 'screenshots' }) }, 'Open')),
      setRow('Exports', 'png, pdf, 3d pages, python and matlab scripts saved from the export tab', el('span', { class: 'path' }, META.paths.exports), el('button', { class: 'btn', onclick: () => api('open_folder', { which: 'exports' }) }, 'Open'))),
    'Help': helpPage,
    'About': () => aboutPage()
  };
  /* search: type in the box to list every matching preference from all tabs (rows, and the sections they belong to), each still live; clear the box to go back to the tabs */
  const SEARCHED = SET_TABS.filter(x => !['Backup', 'Help', 'About'].includes(x)), body = el('div', { id: 'setbody' });
  const hay = c => (c.textContent + ' ' + [...c.querySelectorAll('[title]')].map(e => e.title).join(' ')).toLowerCase();
  const fill = () => {
    const terms = (S.setQuery || '').trim().toLowerCase().split(/\s+/).filter(Boolean);
    if (!terms.length) { body.replaceChildren(el('div', { class: 'sh2' }, tab), pages[tab]()); return; }
    const ok = s => terms.every(w => s.includes(w)), out = [];
    SET_TABS.filter(t => ok(t.toLowerCase())).forEach(t => out.push(el('div', { class: 'setrow' }, el('div', { class: 'lt' }, el('div', { class: 't' }, t), el('div', { class: 'dim' }, 'preferences tab')), el('div', { class: 'ctl' }, el('button', { class: 'btn', onclick: () => { S.setQuery = ''; S.setTab = t; if (t === 'Backup') S.backups = null; renderUtil(); } }, 'Open')))));
    for (const t of SEARCHED) {
      let root = pages[t](); while (root.children.length === 1) root = root.firstElementChild;
      const hits = []; let head = null, headPushed = false, secAll = false;
      for (const c of root.children) {
        if (c.classList.contains('sh3')) { head = c; headPushed = false; secAll = ok(hay(c)); if (secAll) { hits.push(c); headPushed = true; } continue; }
        if (secAll || ok(hay(c))) { if (head && !headPushed) { hits.push(head); headPushed = true; } hits.push(c); }
      }
      if (hits.length) out.push(el('div', { class: 'sh2 srh' }, el('button', { class: 'linkbtn', title: 'open this tab', onclick: () => { S.setQuery = ''; S.setTab = t; renderUtil(); } }, t)), ...hits);
    }
    body.replaceChildren(...(out.length ? out : [el('div', { class: 'dim', style: 'margin-top:16px' }, 'no preferences match “' + S.setQuery.trim() + '”')]));
  };
  const box = el('input', { type: 'search', class: 'setsearch', id: 'setsearch', placeholder: 'Search Preferences', value: S.setQuery || '', 'aria-label': 'search preferences',
    oninput: debounce(() => { S.setQuery = box.value; fill(); document.querySelector('.stabs')?.classList.toggle('dimmed', !!box.value.trim()); }, 140), onkeydown: e => { if (e.key === 'Escape' && box.value) { e.stopPropagation(); box.value = ''; S.setQuery = ''; fill(); document.querySelector('.stabs')?.classList.remove('dimmed'); } } });
  fill();
  main.append(el('div', { class: 'setp' }, el('div', { class: 'shead' }, el('div', { class: 'sh1' }, 'Preferences'), box),
    el('div', { class: 'stabs' + ((S.setQuery || '').trim() ? ' dimmed' : '') }, ...SET_TABS.map(t => el('button', { class: 'stab' + (t === tab ? ' on' : ''), onclick: () => { S.setQuery = ''; S.setTab = t; if (t === 'Backup') S.backups = null; renderUtil(); } }, t))), body));
}

/* ---------- key bindings (rebindable in settings) ---------- */
function keyName(e) {
  let k = e.key; if (['Control', 'Shift', 'Alt', 'Meta'].includes(k)) return '';
  if (k.length === 1) k = k.toUpperCase(); if (k === ' ') k = 'Space';
  return [e.ctrlKey && 'Ctrl', e.altKey && 'Alt', e.shiftKey && 'Shift', k].filter(Boolean).join('+');
}
const ACTIONS = {
  refresh: async () => { S.cache.clear(); if (isMod()) await solveNow(); else renderUtil(); toast('screen refreshed'); },
  screenshot: async () => {
    $('#toast').classList.remove('on'); await new Promise(r => setTimeout(r, 120));               // keep the toast out of the picture
    const r = await api('screenshot'); toast(r.ok ? 'screenshot saved to ' + r.path : r.error, r.ok ? 'ok' : 'err');
  },
  fullscreen: async () => {
    const r = await api('fullscreen');
    if (r.mode === 'browser') { if (document.fullscreenElement) document.exitFullscreen(); else document.documentElement.requestFullscreen().catch(() => { }); }
  },
  settings: () => { if (S.page === 'settings') go(S.prev || '12'); else { S.prev = S.page; go('settings'); } },
  menu: () => { LAY.hidden = !LAY.hidden; applyLayout(); saveSet(); },
  reset: () => resetPanels(),
  theme: () => goto('settings', 'Appearance'),
  solve: () => { if (isMod()) solveNow(false, true); },
  quit: () => askQuit(),
  spacefull: () => { if (window.spaceFullToggle && window.spaceFullToggle()) return; toast('open a space view first (design mode: plots or solar system)'); },
  tour: () => startTour(),
  focus: () => { if (S.focus) setFocus(null); else if (isMod() && S.res && !S.res.error) { S.tab = 'Plots'; setFocus(SET.view === '2d' ? 'v2d' : 'v3d'); } }
};
function handleKey(name, e) {
  if (name === 'Escape' && openMenu) { closeMenu(); return true; }
  if (name === 'Escape' && !S.rebind && cancelSolve()) return true;
  if (name === 'Escape' && S.focus && !S.rebind) { setFocus(null); return true; }
  if (S.rebind) {                                                         // capturing a new binding
    if (name === 'Escape') { S.rebind = null; renderUtil(); return true; }
    if (!name) return true;
    const taken = Object.entries(keys()).find(([a, k]) => k === name && a !== S.rebind);
    if (taken) { toast(`${name} is already used by ${KEY_INFO[taken[0]][0].toLowerCase()}`, 'err'); return true; }
    SET.keys = { ...keys(), [S.rebind]: name }; S.rebind = null; saveSet(); renderUtil(); toast('key binding saved'); return true;
  }
  const hit = Object.entries(keys()).find(([, k]) => k === name); if (!hit) return false;
  const typing = e && /^(INPUT|TEXTAREA|SELECT)$/.test(e.target?.tagName || '');
  if (typing && !/^F\d+$/.test(name) && !/^(Ctrl|Alt)\+/.test(name)) return false;                 // never steal normal typing
  if (e) e.preventDefault(); ACTIONS[hit[0]](); return true;
}
document.addEventListener('keydown', e => { if (handleKey(keyName(e), e)) e.stopPropagation(); }, true);
window.addEventListener('message', e => { if (e.data && e.data.orbitKey) handleKey(e.data.orbitKey, null); });          // keys pressed inside the 3-d frame

/* ---------- boot ---------- */
/* ---------- planet texture quality: 2K maps are built in; sharper (8K) maps are downloaded on request and used only for the body that fills the view ---------- */
const texHires = () => (SET.texq === '8k' && S.tex && S.tex.map && Object.keys(S.tex.map).length ? S.tex.map : null);
function applyTexQuality() { try { if (typeof MIS !== 'undefined' && MIS.space) MIS.space.setHires(texHires()); } catch (e) { } }
function texQualityRows() {
  const host = el('div', {});
  const draw = async () => {
    const r = await api('textures_status', {}); if (r.ok) S.tex = r; const g = r.progress, have = r.count === r.total;
    host.replaceChildren(
      setRow('Space View Texture Quality', '2k maps are built in. 8k maps give sharper close-ups of the earth, moon, mars, the giant planets and more; they are loaded only for the one body that fills the view, so memory use stays low. applies to the sandbox and the design space view', seg([['2k', '2K (Built In)'], ['8k', '8K (Downloaded)']], SET.texq || '2k', v => { SET.texq = v; saveSet(); applyTexQuality(); draw(); })),
      setRow('8K Texture Files', `${r.count} of ${r.total} downloaded${r.count ? ` (${r.size_mb} MB)` : ', about 100 MB in total'}. fetched from solarsystemscope.com (cc by 4.0) only when you press the button. stored in ${r.folder}`,
        el('span', { style: 'display:flex;gap:8px;align-items:center' }, have ? el('b', {}, 'installed') : el('button', { class: 'btn pri', disabled: g.state === 'running', onclick: async () => {
          if (!await askConfirm('download the sharper planet textures (about 100 MB) from solarsystemscope.com now?', 'Download', 'Download Textures')) return; await api('textures_download', {}); draw();
          const t = setInterval(async () => { const q = await api('textures_status', {}); if (q.progress.state !== 'running') { clearInterval(t); if (q.progress.state === 'done') { SET.texq = '8k'; saveSet(); toast('textures downloaded', 'ok'); } S.tex = q; applyTexQuality(); draw(); } else draw(); }, 1500); } },
          g.state === 'running' ? `downloading… ${g.done}/${g.total}` : (r.count ? 'Download The Rest' : 'Download 8K Textures')),
          r.count ? el('button', { class: 'btn', onclick: async () => { if (!await askConfirm('delete the downloaded textures? the built-in 2k maps stay.', 'Delete', 'Delete Textures')) return; const q = await api('textures_delete', {}); S.tex = q; SET.texq = '2k'; saveSet(); applyTexQuality(); draw(); } }, 'Delete') : '')),
      g.state === 'error' ? el('div', { class: 'chk err' }, el('span', { class: 'ic' }, '✕'), el('span', {}, 'download failed: ' + g.error)) : '');
  };
  draw(); return host;
}
async function boot() {
  requestAnimationFrame(splashTick); requestAnimationFrame(fpsLoop); splash(8, 'loading modules');
  META = await api('meta'); api('textures_status', {}).then(r => { if (r && r.ok) { S.tex = r; applyTexQuality(); } }).catch(() => { });
  Object.assign(SET, META.settings || {}); SET.const = 'Course table'; Object.assign(LAY, fresh(LAY_DEFAULT), SET.layout || {}); LAY.groups = { ...LAY_DEFAULT.groups, ...(LAY.groups || {}) }; SET.layout = LAY; splash(38, 'preparing the interface');
  $('#unitChip').onclick = () => setSet({ unit: { km: 'R_body', R_body: 'AU', AU: 'km' }[SET.unit] });
  initSplitters(); syncChrome(); buildNav(); buildMenubar(); buildModeSwitch(); initNavPeek(); splash(58, 'drawing the first transfer');
  await go(META.modules.some(m => m.id === SET.lastPage) ? SET.lastPage : S.page); splash(100, 'ready'); SPLASH.done = true; restyle(); if (!SET.tourDone) setTimeout(() => startTour(), 1800);
}
boot();


/* ---------- settings: ephemeris + GMAT, About with the licenses ---------- */
function ephemPage() {
  const host = el('div', { class: 'sheet' }); const draw = async () => {
    const r = await api('ephem_status', {}); const k = r.kernel, g = r.progress; host.replaceChildren(
      setRow('Active Ephemeris', r.ephemeris.accuracy, el('b', {}, r.ephemeris.name)),
      setRow('Source', 'auto uses the DE440s kernel when it is present; built-in always uses the offline analytic model', seg([['auto', 'Auto'], ['analytic', 'Built-in']], SET.ephemMode || 'auto', v => { SET.ephemMode = v; saveSet(); MIS.meta = null; draw(); })),
      setRow('DE440s Kernel', `JPL planetary ephemeris, 1849–2150, about ${(k.expected_size / 1e6).toFixed(0)} MB, downloaded from ${k.url} only when you press the button. stored in ${k.folder}`,
        k.path ? el('span', {}, el('b', {}, 'installed'), el('span', { class: 'dim' }, ` ${(k.size / 1e6).toFixed(1)} MB`)) : el('button', { class: 'btn pri', disabled: g.state === 'running' || !k.jplephem, onclick: async () => {
          if (!await askConfirm(`download the DE440s kernel (${(k.expected_size / 1e6).toFixed(0)} MB) from NASA/JPL NAIF now?`, 'Download', 'Download Ephemeris')) return; await api('ephem_download', {}); draw(); const t = setInterval(async () => { const q = await api('ephem_status', {}); if (q.progress.state !== 'running') { clearInterval(t); MIS.meta = null; draw(); } else { host.querySelector('.dlp')?.replaceChildren(`${(q.progress.done / 1e6).toFixed(1)} / ${(q.progress.total / 1e6).toFixed(1)} MB`); } }, 700); } }, 'Download DE440s')),
      g.state === 'running' ? el('div', { class: 'dim dlp' }, 'starting…') : '', g.state === 'error' ? el('div', { class: 'chk err' }, el('span', { class: 'ic' }, '✕'), el('span', {}, 'download failed: ' + g.error)) : '',
      g.state === 'done' ? el('div', { class: 'dim' }, 'downloaded; sha-256 ' + g.sha256) : '', !k.jplephem ? el('div', { class: 'chk warn' }, el('span', { class: 'ic' }, '!'), el('span', {}, 'the jplephem package is not available in this installation, so only the built-in ephemeris can be used')) : '',
      setRow('My Own Kernel', 'path to a .bsp file (for example de440s.bsp or a mission kernel); leave empty to use the downloaded one', el('input', { type: 'text', value: SET.ephemPath || '', style: 'width:300px', placeholder: 'C:\\path\\de440s.bsp', onchange: e => { SET.ephemPath = e.target.value.trim(); saveSet(); MIS.meta = null; draw(); } })),
      el('div', { class: 'sh2', style: 'margin-top:26px' }, 'GMAT'),
      setRow('GMAT Folder', 'optional: the folder of an installed GMAT (the one that contains bin/GmatConsole). when set, the mission comparison also runs your exported script in GMAT and fills the GMAT column. nothing is bundled and nothing is downloaded',
        el('input', { type: 'text', value: SET.gmatPath || '', style: 'width:300px', placeholder: 'C:\\GMAT\\R2022a', onchange: async e => { SET.gmatPath = e.target.value.trim(); saveSet(); const c = await api('gmat_check', { path: SET.gmatPath }); toast(SET.gmatPath ? (c.ok ? 'GMAT console found' : 'GmatConsole was not found in that folder') : 'GMAT path cleared', c.ok || !SET.gmatPath ? 'ok' : 'err'); } })));
  }; draw(); return host;
}
let LIC = null;
function aboutPage() {
  const host = el('div', { class: 'sheet' }, setRow('OrbSim', 'version ' + META.version), setRow('Project Page', 'source code, installation notes and the issue tracker', el('span', { class: 'path' }, 'github.com/Chiyami1213/orbsim')),
    el('div', { class: 'sh2', style: 'margin-top:22px' }, 'Licenses and Credits'),
    el('div', { class: 'dim', style: 'margin-bottom:8px' }, 'this program contains portions derived from nasa gmat (general mission analysis tool), licensed under the apache license 2.0: the runge-kutta coefficient tables of its integrators, translated and modified. it is not affiliated with or endorsed by nasa, and no gmat binaries are included. the jpl ephemeris kernel, if you download it, comes from nasa/jpl naif.'));
  const draw = items => { host.append(...items.map(it => el('details', { class: 'lic' }, el('summary', {}, it.name), el('pre', {}, it.text)))); };
  if (LIC) draw(LIC); else api('licenses', {}).then(r => { LIC = r.items; if (S.page === 'settings' && S.setTab === 'About') draw(LIC); });
  return host;
}
