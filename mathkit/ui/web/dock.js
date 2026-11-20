/* ---------- a reusable dock: tiles you can drag anywhere (grip, top left), resize (drag the gaps), close (trash, top right) and put back.
   The layout is a binary split tree kept in LAY[key]; tiles never move in the DOM tree, so iframes and WebGL views are not reloaded when you rearrange them. ---------- */
function makeDock(cfg) {
  const GAP = 8, ids = cfg.ids, tree0 = () => JSON.parse(JSON.stringify(cfg.def)); let host = null, inner = null, rects = {}, ro = null;
  const closed = () => (LAY[cfg.closedKey] || []).filter(i => ids.includes(i));
  const visible = () => new Set(ids.filter(i => !closed().includes(i)));
  function valid(n, seen) {
    if (!n || (n.t !== 't' && n.t !== 's')) return false;
    if (n.t === 't') { if (!ids.includes(n.id) || seen.has(n.id)) return false; seen.add(n.id); return true; }
    return (n.d === 'h' || n.d === 'v') && typeof n.r === 'number' && valid(n.a, seen) && valid(n.b, seen);
  }
  function tree() { const seen = new Set(); if (!LAY[cfg.key] || !valid(LAY[cfg.key], seen) || seen.size !== ids.length) LAY[cfg.key] = tree0(); return LAY[cfg.key]; }
  const prune = (n, vis) => { if (n.t === 't') return vis.has(n.id) ? n : null; const a = prune(n.a, vis), b = prune(n.b, vis); if (!a) return b; if (!b) return a; return { t: 's', d: n.d, r: n.r, a, b, src: n.src || n }; };
  const minSize = n => { if (n.t === 't') return cfg.min[n.id] || [260, 200]; const A = minSize(n.a), B = minSize(n.b); return n.d === 'h' ? [A[0] + B[0] + GAP, Math.max(A[1], B[1])] : [Math.max(A[0], B[0]), A[1] + B[1] + GAP]; };
  function place(n, x, y, w, h, out, splits) {
    if (n.t === 't') { out[n.id] = { x, y, w, h }; return; }
    const A = minSize(n.a), B = minSize(n.b);
    if (n.d === 'h') { const avail = w - GAP, wa = clamp(avail * n.r, A[0], Math.max(A[0], avail - B[0])); splits.push({ n, d: 'h', x: x + wa, y, w: GAP, h, start: x, size: avail }); place(n.a, x, y, wa, h, out, splits); place(n.b, x + wa + GAP, y, avail - wa, h, out, splits); }
    else { const avail = h - GAP, ha = clamp(avail * n.r, A[1], Math.max(A[1], avail - B[1])); splits.push({ n, d: 'v', x, y: y + ha, w, h: GAP, start: y, size: avail }); place(n.a, x, y, w, ha, out, splits); place(n.b, x, y + ha + GAP, w, avail - ha, out, splits); }
  }
  function layout() {
    if (!host || !host.isConnected) return;
    const W = host.clientWidth, H = host.clientHeight, vis = visible(), t = prune(tree(), vis); inner.querySelectorAll('.dsplit').forEach(e => e.remove());
    const out = {}, splits = []; let totalH = H;
    if (t) {
      const [mw, mh] = minSize(t);
      if (vis.size > 1 && (W < mw || H < mh)) { let y = 0; for (const id of ids.filter(i => vis.has(i))) { const sh = (cfg.stackH && cfg.stackH[id]) || 420; out[id] = { x: 0, y, w: W, h: sh }; y += sh + GAP; } totalH = Math.max(H, y - GAP); }       // too small: stack and scroll
      else place(t, 0, 0, W, H, out, splits);
    }
    inner.style.height = totalH + 'px'; host.classList.toggle('stacked', totalH > H + 1); rects = out;
    for (const id of ids) {
      const el_ = inner.querySelector(`[data-dt="${id}"]`), r = out[id]; if (!el_) continue;
      if (!r) { el_.style.display = 'none'; continue; }
      el_.style.display = ''; Object.assign(el_.style, { left: r.x + 'px', top: r.y + 'px', width: r.w + 'px', height: r.h + 'px' });
    }
    for (const sp of splits) { const d = el('div', { class: 'dsplit ' + sp.d }); Object.assign(d.style, { left: sp.x + 'px', top: sp.y + 'px', width: sp.w + 'px', height: sp.h + 'px' }); d.onpointerdown = e => splitDrag(e, sp); inner.append(d); }
  }
  function drag(onmove, onup) {
    document.body.classList.add('dragging');
    const mv = e => onmove(e), up = e => { window.removeEventListener('pointermove', mv); window.removeEventListener('pointerup', up); document.body.classList.remove('dragging'); onup && onup(e); };
    window.addEventListener('pointermove', mv); window.addEventListener('pointerup', up);
  }
  function splitDrag(e, sp) {
    e.preventDefault(); const src = sp.n.src || sp.n;
    drag(ev => { const b = host.getBoundingClientRect(); const pos = sp.d === 'h' ? ev.clientX - b.left : ev.clientY - b.top + host.scrollTop; src.r = clamp((pos - sp.start) / sp.size, 0.04, 0.96); layout(); }, () => saveSet());
  }
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
    for (const [id, r] of Object.entries(rects)) {
      if (id === dragId || px < r.x || px > r.x + r.w || py < r.y || py > r.y + r.h) continue;
      const u = (px - r.x) / r.w, v = (py - r.y) / r.h, zone = u < 0.28 ? 'l' : u > 0.72 ? 'r' : v < 0.28 ? 't' : v > 0.72 ? 'b' : 'c';
      const rect = zone === 'l' ? { x: r.x, y: r.y, w: r.w / 2, h: r.h } : zone === 'r' ? { x: r.x + r.w / 2, y: r.y, w: r.w / 2, h: r.h } : zone === 't' ? { x: r.x, y: r.y, w: r.w, h: r.h / 2 } : zone === 'b' ? { x: r.x, y: r.y + r.h / 2, w: r.w, h: r.h / 2 } : r;
      return { id, zone, rect };
    }
    return null;
  }
  function applyDrop(id, tgt) {
    let t = JSON.parse(JSON.stringify(tree()));
    if (tgt.zone === 'c') swapTiles(t, id, tgt.id);
    else { t = removeTile(t, id); if (tgt.edge) { const first = tgt.zone === 'l' || tgt.zone === 't'; const T = { t: 't', id }; t = { t: 's', d: tgt.zone === 'l' || tgt.zone === 'r' ? 'h' : 'v', r: first ? 0.3 : 0.7, a: first ? T : t, b: first ? t : T }; } else t = insertAt(t, tgt.id, id, tgt.zone); }
    LAY[cfg.key] = t; saveSet(); layout();
  }
  function startDrag(id, e) {
    e.preventDefault(); const sx = e.clientX, sy = e.clientY, dz = el('div', { class: 'dz' }), ov = el('div', { class: 'dropov' }, dz); let moved = false, tgt = null;
    drag(ev => {
      if (!moved && Math.hypot(ev.clientX - sx, ev.clientY - sy) < 5) return;
      if (!moved) { moved = true; host.append(ov); const t = inner.querySelector(`[data-dt="${id}"]`); if (t) t.classList.add('lifted'); }
      const b = host.getBoundingClientRect(), px = ev.clientX - b.left + host.scrollLeft, py = ev.clientY - b.top + host.scrollTop; tgt = dropTarget(px, py, id, host.clientWidth, host.clientHeight);
      if (tgt) { dz.style.display = 'block'; Object.assign(dz.style, { left: tgt.rect.x + 'px', top: tgt.rect.y + 'px', width: tgt.rect.w + 'px', height: tgt.rect.h + 'px' }); } else dz.style.display = 'none';
    }, () => { ov.remove(); const t = inner.querySelector(`[data-dt="${id}"]`); if (t) t.classList.remove('lifted'); if (moved && tgt) applyDrop(id, tgt); });
  }
  return {
    /** Build the dock (one tile per id) and return its element; ``bodies[id]`` is where the caller puts each tile's content. */
    mount() {
      const bodies = {}; inner = el('div', { class: 'dockin' }); host = el('div', { class: 'dock dock2', style: `height:${cfg.height || 'calc(100vh - 260px)'};min-height:${cfg.minHeight || 640}px` }, inner);
      for (const id of ids) {
        const body = el('div', { class: 'tbody' }); bodies[id] = body;
        inner.append(el('div', { class: 'tile', 'data-dt': id }, body, el('button', { class: 'trash', title: 'close this panel (bring it back with the buttons above, or press f8 to reset the layout)', onclick: () => this.close(id) }, ico('close')),
          el('button', { class: 'grip', title: 'drag to move this panel: drop it on another panel (left, right, top, bottom, or the center to swap) or on an edge of the area', onpointerdown: e => startDrag(id, e) }, '⠿')));
      }
      if (ro) ro.disconnect(); ro = new ResizeObserver(() => layout()); ro.observe(host); setTimeout(layout, 0); return { el: host, bodies };
    },
    layout, closed, names: cfg.names,
    close(id) { LAY[cfg.closedKey] = [...new Set([...closed(), id])]; saveSet(); layout(); if (cfg.onChange) cfg.onChange(); },
    open(id) { LAY[cfg.closedKey] = closed().filter(x => x !== id); saveSet(); layout(); if (cfg.onChange) cfg.onChange(); },
    reset() { LAY[cfg.key] = tree0(); LAY[cfg.closedKey] = []; saveSet(); layout(); if (cfg.onChange) cfg.onChange(); },
    destroy() { if (ro) ro.disconnect(); ro = null; host = null; inner = null; }
  };
}
