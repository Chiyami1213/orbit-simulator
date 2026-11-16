/* ---------- guided tour: starts on the first launch, and any time from Help → Start Tutorial, Settings → Help, or F1 ---------- */
const TOUR = { i: 0, steps: [], on: false };
const TOUR_STEPS = () => [
  { title: 'Welcome to Orbit Simulator', text: 'a one-minute tour of the window. you can leave at any time with esc, and start it again whenever you like from the help menu, from settings → help and feedback, or with F1.' },
  { sel: '#modesw', title: 'Three Modes', text: 'solve: the twelve course modules and the reference tools. explore: a live 3d sandbox where you add and edit bodies and run time forward or back. design: GMAT-style mission planning with real propagation and script import / export.' },
  { sel: '#menubar', title: 'The Menu Bar', text: 'file: screenshot, export, backup. edit: solve, copy results. view: show or close panels, maximise a plot, light / dark mode and the four colour themes. go: jump to any module. help: this tutorial, the issue form, licences.' },
  { sel: '#nav', title: 'Modules and Utilities', text: 'twelve modules for the course problems, the mission workspace, and utilities (julian date, body constants, test cases). press M to hide this menu, or fold it to icons with the arrow at its top.' },
  { sel: '#tile-inputs', title: 'Inputs', text: 'pick a homework or exam problem from the drop-down to load its numbers, or type your own. units can follow the body radius. sliders redraw the 2d figure live while you drag; the 3d view follows when you pause.', before: () => showPlots() },
  { sel: 'button.solve', title: 'Solve & Draw', text: 'press it to solve and draw. a progress bar runs while it works. if the solver meets a math problem you are warned: you can continue when the result is still usable, or adjust the inputs when it is not.' },
  { sel: '#tile-v3d', title: 'The 3D View', text: 'drag to rotate, scroll to zoom. play the animation, change its speed or repeat it. the grip at the top left moves the panel (drop it on another panel or a window edge), the trash icon at the top right closes it, and Focus (or F12) maximises the plot.' },
  { sel: '#tile-v2d', title: 'The 2D View', text: 'the submit-ready annotated figure with latex labels. every panel can be dragged anywhere and resized by dragging the gaps. F8 puts everything back in the default arrangement.' },
  { sel: '.tabtools', title: 'Course or GMAT', text: 'show this result with course names and angles or with GMAT parameter names (VFPA, TA 0–360 …); the numbers do not change. "Open in Mission" turns the result into a spacecraft, propagator, burns and stop conditions.' },
  { sel: '.tabs', title: 'Steps and Export', text: 'step-by-step lists every intermediate value with its equation and the quadrant checks. export figure saves png, pdf, a 3d page, python or matlab plotting scripts, and a GMAT script.' },
  { sel: '#modesw button[data-mode="design"]', title: 'Design Mode', text: 'build a mission with resources and a command sequence, run it with real numerical propagation (Moon, Sun, planets, three-body, patched conics), compare with the course answer and with GMAT, and import or export GMAT scripts.' },
  { sel: '#modesw button[data-mode="explore"]', title: 'Explore Mode', text: 'the sandbox: the real Solar System from the ephemeris, a library to add bodies and spacecraft, a side panel to edit mass, orbit and motion, and time warp in both directions.' },
  { sel: '#setBtn', title: 'Settings', text: 'appearance and colour themes, plot options, key bindings, constants, conventions, ephemeris and GMAT folder, backups, and licences. the tutorial can be started again from here, from the help menu, or with F1.' },
  { title: 'You are ready', text: 'that is the tour. try loading a homework problem from the inputs drop-down and press solve & draw. good luck!' }
];
async function showPlots() { if (!isMod()) await go(META.modules.some(m => m.id === SET.lastPage) ? SET.lastPage : '12'); S.tab = 'Plots'; if (S.focus) setFocus(null); if (!$('#tile-inputs')) renderMain(); }

function tourEnd(done = true) {
  TOUR.on = false; document.querySelectorAll('.tourov, .tourcard, .tourhl').forEach(e => e.remove()); window.removeEventListener('resize', tourPlace);
  if (done && !SET.tourDone) { SET.tourDone = true; saveSet(); }
}
function tourPlace() {
  if (!TOUR.on) return; const st = TOUR.steps[TOUR.i], card = $('.tourcard'), hl = $('.tourhl'); if (!card || !hl) return;
  const t = st.sel ? document.querySelector(st.sel) : null, vw = innerWidth, vh = innerHeight, r = t && t.offsetParent !== null ? t.getBoundingClientRect() : null;
  if (r && r.width > 0) {
    const pad = 6; Object.assign(hl.style, { display: 'block', left: r.left - pad + 'px', top: r.top - pad + 'px', width: r.width + 2 * pad + 'px', height: r.height + 2 * pad + 'px' });
    const cw = card.offsetWidth, ch = card.offsetHeight; let x = r.right + 16, y = r.top;
    if (x + cw > vw - 12) x = Math.max(12, r.left - cw - 16);                                   // not enough room on the right: try the left
    if (x < 12 || x + cw > vw - 12) { x = clamp(r.left, 12, vw - cw - 12); y = r.bottom + 16; if (y + ch > vh - 12) y = Math.max(12, r.top - ch - 16); }
    card.style.left = x + 'px'; card.style.top = clamp(y, 12, vh - ch - 12) + 'px';
  } else { hl.style.display = 'none'; card.style.left = Math.max(12, (vw - card.offsetWidth) / 2) + 'px'; card.style.top = Math.max(12, (vh - card.offsetHeight) / 2) + 'px'; }
}
async function tourShow(i) {
  const steps = TOUR.steps; TOUR.i = clamp(i, 0, steps.length - 1); const st = steps[TOUR.i];
  if (st.before) await st.before();
  await new Promise(r => setTimeout(r, 120));
  let t = st.sel ? document.querySelector(st.sel) : null; if (t && t.scrollIntoView) t.scrollIntoView({ block: 'nearest', inline: 'nearest' });
  document.querySelectorAll('.tourcard').forEach(e => e.remove());
  const last = TOUR.i === steps.length - 1, first = TOUR.i === 0;
  const card = el('div', { class: 'tourcard', role: 'dialog' }, el('div', { class: 'tcount' }, `${TOUR.i + 1} / ${steps.length}  ·  use the ← → arrow keys to move, esc to leave`), el('h3', {}, st.title), el('p', {}, st.text),
    el('div', { class: 'tbtns' }, first ? el('button', { class: 'btn', onclick: () => tourEnd() }, 'Skip') : el('button', { class: 'btn', onclick: () => tourShow(TOUR.i - 1) }, 'Back'),
      el('button', { class: 'btn pri', onclick: () => (last ? tourEnd() : tourShow(TOUR.i + 1)) }, last ? 'Finish' : first ? 'Start the Tour' : 'Next')));
  document.body.append(card); tourPlace();
}
async function startTour() {
  if (TOUR.on) tourEnd(false); closeMenu(); TOUR.on = true; TOUR.steps = TOUR_STEPS();
  if (S.page === 'settings' || !isMod()) await go(META.modules.some(m => m.id === SET.lastPage) ? SET.lastPage : '12');
  if (LAY.hidden) { LAY.hidden = false; applyLayout(); }
  document.body.append(el('div', { class: 'tourov', onclick: e => e.stopPropagation() }), el('div', { class: 'tourhl' }));
  window.addEventListener('resize', tourPlace); tourShow(0);
}
document.addEventListener('keydown', e => {                                                      // ← and → (or Enter / Backspace) move through the steps, esc leaves
  if (!TOUR.on) return; const k = e.key;
  if (k === 'Escape') { tourEnd(); e.stopPropagation(); e.preventDefault(); return; }
  if (k === 'ArrowRight' || k === 'Enter') { if (TOUR.i >= TOUR.steps.length - 1) tourEnd(); else tourShow(TOUR.i + 1); e.stopPropagation(); e.preventDefault(); }
  else if (k === 'ArrowLeft' || k === 'Backspace') { tourShow(TOUR.i - 1); e.stopPropagation(); e.preventDefault(); }
}, true);
