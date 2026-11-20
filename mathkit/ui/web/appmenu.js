/* ---------- the main menu, shared by all three modes: click the OrbSim icon at the top left. A drawer slides in from the left with big actions on top (tailored to the mode you are in)
   and the same small tools below (what's new, shortcuts, credits, feedback, debug tools, a performance test and help). ---------- */
const WHATS_NEW = [
  'One main menu for every mode: click the OrbSim icon at the top left.',
  'Sandbox: ready-made scenes, a placement preview (orbit, trajectory or drop), real lighting from the stars, body rotation from JPL data, object search, a date calendar, keyboard control (space, . , + - and Tab).',
  'Design: a one-row header, a faster Next Event, trails that stay attached to the spacecraft, and a panel layout shared with Solve.',
  'Solve: constants are always the JPL / GMAT table; the left menu opens when the mouse is over it; the 2D plot zooms and pans; you can rotate the 3D view while it plays.',
  'Sharper 8K planet textures can be downloaded under settings; four colour themes plus the new Obsidian theme; light and dark appearance everywhere.'];

function infoModal(title, ...kids) {
  const done = () => { document.removeEventListener('keydown', esc, true); ov.remove(); };
  const esc = e => { if (e.key === 'Escape') { e.stopPropagation(); done(); } }; document.addEventListener('keydown', esc, true);
  const ov = el('div', { class: 'modalov', onclick: e => { if (e.target === ov) done(); } }, el('div', { class: 'modal wide', role: 'dialog' }, el('h3', {}, title), ...kids, el('div', { class: 'btnrow' }, el('button', { class: 'btn pri', onclick: done }, 'Close'))));
  document.body.append(ov); return { close: done, body: ov.querySelector('.modal') };
}
const pickList = (title, intro, items, onPick) => {                               // a modal with a list of buttons: [{ label, sub }]
  const m = infoModal(title, intro ? el('div', { class: 'dim' }, intro) : '', el('div', { class: 'pklist' }, ...items.map((it, i) => el('button', { class: 'pkitem', onclick: () => { m.close(); onPick(i); } }, el('b', {}, it.label), it.sub ? el('span', {}, it.sub) : ''))));
  return m;
};

/* ---- the drawer ---- */
let menuPinned = false, menuTimer = 0;
function appMenuClose() { clearTimeout(menuTimer); menuPinned = false; const m = $('#xmenu'), o = $('#xmenuov'); if (m) { m.classList.remove('open'); setTimeout(() => m.remove(), 230); } if (o) o.remove(); const b = $('#logoBtn'); if (b) b.classList.remove('open'); }
// hover over the icon (or the menu) opens it as a peek and moving away closes it; a click pins it open (dimmed page behind it) until you click away, press esc or choose something
const menuSoon = ms => { clearTimeout(menuTimer); menuTimer = setTimeout(() => { if (!menuPinned) appMenuClose(); }, ms); };
document.addEventListener('mouseover', e => { const t = e.target.closest ? e.target.closest('#logoBtn, #xmenu') : null; if (!t) return; clearTimeout(menuTimer); if (t.id === 'logoBtn' && !$('#xmenu')) menuTimer = setTimeout(() => { if (!$('#xmenu')) appMenu(false); }, 130); });
document.addEventListener('mouseout', e => { const t = e.target.closest ? e.target.closest('#logoBtn, #xmenu') : null; if (!t) return; const to = e.relatedTarget && e.relatedTarget.closest ? e.relatedTarget.closest('#logoBtn, #xmenu') : null; if (to) return; if ($('#xmenu')) menuSoon(280); else clearTimeout(menuTimer); });
document.addEventListener('click', e => { if (!e.target.closest || !e.target.closest('#logoBtn')) return; if ($('#xmenu') && menuPinned) { appMenuClose(); return; } if ($('#xmenu')) { menuPinned = true; if (!$('#xmenuov')) document.body.append(el('div', { id: 'xmenuov', class: 'xmenuov', onclick: appMenuClose })); return; } appMenu(true); });
document.addEventListener('keydown', e => { if (e.key === 'Escape' && $('#xmenu')) { appMenuClose(); e.stopPropagation(); e.preventDefault(); } }, true);

const MODE_TILES = {
  solve: () => [
    ['orbit', 'Modules', 'the twelve course modules', () => pickList('Modules', 'jump to a module', META.modules.map(m => ({ label: m.short, sub: m.name || '' })), i => go(META.modules[i].id))],
    ['basic', 'Problems', 'load a homework or exam problem', () => { const m = typeof mod === 'function' ? mod() : null; if (!m || !m.presets || !m.presets.length) { toast('open a module first: problems belong to the module you are in'); return; } pickList('Problems — ' + m.short, 'load the inputs of a printed problem', m.presets.map(p => ({ label: p.label })), i => loadPreset(m, i)); }],
    ['check', 'Test Cases', 'computed vs printed answers', () => go('tests')],
    ['guide', 'Guides', 'tutorial and tips', () => startTour()]],
  design: () => [
    ['newf', 'New', 'an empty mission', () => { MIS.m = misNew(); MIS.res = null; MIS.cmp = null; misTouch(); MIS.tab = 'Resources'; go('mission'); }],
    ['openf', 'Open', 'a mission file or GMAT script', () => appFile('.script,.orbitmission,.txt', f => { go('mission'); misImportFile(f); })],
    ['scene', 'Starters', 'ready-made missions', async () => { if (!MIS.meta) MIS.meta = await api('mission_meta', {}); pickList('Starter Missions', 'start from a ready-made mission', MIS.meta.starters.map(s => ({ label: s })), async i => { const r = await api('mission_starter', { name: MIS.meta.starters[i] }); MIS.m = r.mission; MIS.m.convention = SET.convention || 'course'; MIS.res = null; MIS.cmp = null; misTouch(); MIS.tab = 'Resources'; go('mission'); }); }],
    ['guide', 'Guides', 'tutorial and tips', () => startTour()]],
  explore: () => [
    ['newf', 'New', 'a single star to build on', async () => { if (EX.undo.length && !await askConfirm('start a new scene? your changes will be lost (save the scene first to keep them).', 'New Scene', 'New Scene')) return; exNew('Single Star'); }],
    ['openf', 'Open', 'a saved scene file', () => appFile('.orbitscene,.json', f => exOpenFile(f))],
    ['scene', 'Scenes', 'ready-made starting points', () => scenePop($('#logoBtn'))],
    ['guide', 'Guides', 'tutorial and tips', () => startTour()]]
};
const otherModes = mode => [['solve', 'Solve', 'orbit', 'the twelve course modules'], ['design', 'Design', 'sat', 'plan and fly a mission'], ['explore', 'Sandbox', 'globe', 'a live 3D sandbox']].filter(m => m[0] !== mode);
function appFile(accept, fn) {
  let inp = $('#appfile'); if (inp) inp.remove();
  inp = el('input', { id: 'appfile', type: 'file', accept, style: 'display:none', onchange: e => { const f = e.target.files[0]; if (f) fn(f); e.target.value = ''; } }); document.body.append(inp); inp.click();
}

function appMenu(pin) {
  if ($('#xmenu')) { appMenuClose(); return; } menuPinned = !!pin; const lb = $('#logoBtn'); if (lb) lb.classList.add('open');
  const mode = S.mode || 'solve', tile = (icon, title, sub, fn) => el('button', { class: 'mtile', onclick: () => { appMenuClose(); fn(); } }, ico(icon), el('span', {}, el('b', {}, title), el('i', {}, sub)));
  const item = (icon, title, fn) => el('button', { class: 'mitem', onclick: () => { appMenuClose(); fn(); } }, ico(icon), el('span', {}, title));
  const modeName = { solve: 'Solve', design: 'Design', explore: 'Sandbox' }[mode];
  const drawer = el('aside', { id: 'xmenu', class: 'xmenu' },
    el('div', { class: 'mhead' }, el('span', { class: 'mlogo' }, ico('orbit')), el('div', {}, el('b', {}, 'OrbSim'), el('span', {}, modeName + ' · version ' + (META.version || ''))), el('button', { class: 'xib', title: 'close the menu (esc)', onclick: appMenuClose }, ico('close'))),
    el('div', { class: 'mtiles' },
      el('div', { class: 'mcol' }, ...MODE_TILES[mode]().map(t => tile(...t))),
      el('div', { class: 'mcol small' }, tile('savef', 'Save and Share', saveHint(mode), () => appShare(mode)), tile('gear', 'Preferences', 'appearance, textures, keys', () => goto('settings')),
        ...otherModes(mode).map(([id, name, icon, sub]) => tile(icon, name + ' Mode', sub, () => setMode(id))))),
    el('div', { class: 'mlist' },
      item('news', "What's New", () => infoModal("What's New", el('ul', { class: 'mnews' }, ...WHATS_NEW.map(t => el('li', {}, t))))),
      item('keys', 'Keyboard Shortcuts', () => appKeys(mode)),
      item('credits', 'Credits', () => goto('settings', 'About')),
      item('feedback', 'Send Feedback', () => goto('settings', 'Help')),
      item('debug', 'Debug Tools', () => appDebug(mode)),
      item('perf', 'Performance Test', () => appPerf()),
      item('whatif', 'Help', () => goto('settings', 'Help'))),
    el('div', { class: 'mfoot' }, 'OrbSim ' + (META.version || '') + ' · ephemeris: ' + ((MIS.meta && MIS.meta.ephemeris && MIS.meta.ephemeris.name) || (typeof EX !== 'undefined' && EX.meta && EX.meta.ephemeris && EX.meta.ephemeris.name) || 'built in or DE440s, see settings')));
  document.body.append(...(pin ? [el('div', { id: 'xmenuov', class: 'xmenuov', onclick: appMenuClose })] : []), drawer); requestAnimationFrame(() => drawer.classList.add('open'));
}
const saveHint = mode => mode === 'explore' ? 'scene, picture, video' : mode === 'design' ? 'mission, GMAT script, picture' : 'figure, script, picture';

function appShare(mode) {
  const rows = { explore: () => exShare(),
    design: () => { const m = infoModal('Save and Share', el('div', { class: 'dim' }, 'files go to your OrbSim folder (settings → local files).'), el('div', { class: 'btnrow' },
      el('button', { class: 'btn', onclick: async () => { const x = await api('mission_save', { mission: MIS.m, kind: 'orbitmission' }); toast(x.ok ? 'saved to ' + x.path : x.error, x.ok ? 'ok' : 'err'); } }, 'Save Mission File'),
      el('button', { class: 'btn', onclick: async () => { const x = await api('mission_save', { mission: MIS.m, kind: 'script' }); toast(x.ok ? 'saved to ' + x.path : x.error, x.ok ? 'ok' : 'err'); } }, 'Save GMAT Script'),
      el('button', { class: 'btn', onclick: () => { m.close(); ACTIONS.screenshot(); } }, 'Save Screenshot'))); },
    solve: () => { const m = infoModal('Save and Share', el('div', { class: 'dim' }, 'files go to your OrbSim folder (settings → local files).'), el('div', { class: 'btnrow' },
      el('button', { class: 'btn', onclick: () => { m.close(); if (isMod()) { S.tab = 'Export Figure'; renderMain(); } else toast('open a module first'); } }, 'Export Figures'),
      el('button', { class: 'btn', onclick: () => { m.close(); if (isMod()) openInMission(); else toast('open a module first'); } }, 'Open in Design'),
      el('button', { class: 'btn', onclick: () => { m.close(); ACTIONS.screenshot(); } }, 'Save Screenshot'),
      el('button', { class: 'btn', onclick: () => { m.close(); goto('settings', 'Backup'); } }, 'Backup My Files'))); } };
  rows[mode]();
}

function appKeys(mode) {
  const common = Object.entries(keys()).map(([a, k]) => [k, (KEY_INFO[a] || [a])[0]]);
  const extra = mode === 'explore' ? [['Space', 'play or pause'], ['.  /  ,', 'speed up / slow down (twice or half as fast)'], ['+  /  −', 'zoom in / out'], ['Tab', 'hide or show the interface'], ['Esc', 'cancel placing an object, close menus']]
    : mode === 'design' ? [['Esc', 'close menus and dialogs']] : [['← / →', 'previous / next step of the tutorial'], ['Esc', 'leave focus mode, close menus']];
  infoModal('Keyboard Shortcuts', el('table', { class: 'mkeys' }, ...[...extra, ...common].map(([k, d]) => el('tr', {}, el('td', {}, el('kbd', {}, k)), el('td', {}, d)))), el('div', { class: 'dim' }, 'every key above can be changed under settings → key bindings.'));
}

function appDebug(mode) {
  if (mode === 'explore' && typeof exDebug === 'function') { exDebug(); return; }
  const rows = [['Version', META.version], ['Mode', mode === 'design' ? 'Design' : 'Solve'], ['Page', S.page], ['Appearance', effTheme() + ' · ' + (SET.palette || 'prussian')], ['Convention', S.conv || SET.convention || 'course'], ['Constants', 'JPL / GMAT table'],
    ['Last result', mode === 'design' ? (MIS.res ? 'mission has run' : 'not run yet') : (S.res && !S.res.error ? 'solved' : 'none')], ['Graphics', gpuInfo() || 'unknown']];
  const text = rows.map(([a, b]) => a + ': ' + b).join('\n');
  infoModal('Debug Tools', el('table', { class: 'mkeys' }, ...rows.map(([a, b]) => el('tr', {}, el('td', {}, a), el('td', {}, String(b))))),
    el('div', { class: 'btnrow' }, el('label', { class: 'tgl' }, el('span', { class: 'dim', style: 'margin:0' }, 'show the frame rate in the title bar'), el('input', { type: 'checkbox', checked: !!SET.fps, onchange: e => { SET.fps = e.target.checked; saveSet(); redo3d(); showFps(); } })),
      el('button', { class: 'btn', onclick: () => { try { navigator.clipboard.writeText(text); toast('copied', 'ok'); } catch (e) { toast('could not copy', 'err'); } } }, 'Copy Report')));
}

function appPerf() {
  const out = el('div', { class: 'dim' }, 'measuring the frame rate for 4 seconds…'), m = infoModal('Performance Test', out); const d = []; let last = performance.now(); const t0 = last;
  const view = (typeof EX !== 'undefined' && S.mode === 'explore' && EX.space) ? EX.space : (typeof MIS !== 'undefined' && S.mode === 'design' && MIS.space) ? MIS.space : null;
  const step = now => {
    d.push(now - last); last = now; if (now - t0 < 4000) { requestAnimationFrame(step); return; }
    const s = d.slice(2).sort((a, b) => a - b), avg = s.reduce((a, b) => a + b, 0) / s.length, low = s[Math.floor(s.length * 0.99)] || avg, p = view ? view.perf() : null, fps = 1000 / avg;
    const verdict = fps >= 55 ? 'smooth' : fps >= 30 ? 'fine, but not smooth: use the 2K textures or lower the animation resolution' : 'slow: use the 2K textures, hide atmosphere glow, or lower the animation resolution';
    out.replaceChildren(el('table', { class: 'mkeys' }, ...[['Average', fps.toFixed(1) + ' fps'], ['1% low', (1000 / low).toFixed(1) + ' fps'], ['Slowest frame', Math.max(...s).toFixed(0) + ' ms'], ...(p ? [['Bodies in the 3D view', p.bodies], ['Render scale', p.pixelRatio.toFixed(2) + ' of ' + p.baseRatio.toFixed(2)], ['3D view size', p.width + ' × ' + p.height + ' px']] : []), ['Graphics', gpuInfo() || 'unknown']].map(([a, b]) => el('tr', {}, el('td', {}, a), el('td', {}, String(b))))), el('div', { class: 'dim', style: 'margin-top:10px' }, 'verdict: ' + verdict));
  };
  requestAnimationFrame(step);
}
