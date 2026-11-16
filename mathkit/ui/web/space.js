/* Space view for the Mission workspace (three.js, vendored under /vendor, MIT). Bodies, trajectories, a physically oriented Milky Way sky, time warp, overlays, recording.
   Axes are ICRF (z up). Positions are kilometres about the display centre; the camera orbits a focus point, with a logarithmic depth buffer so a 100 km orbit
   and the whole Solar System can share one scene. */
import * as THREE from 'three';
import { OrbitControls } from '/vendor/OrbitControls.js';

// ICRS -> galactic (Hipparcos); identical to mathkit/sky.py. The sky maps are galactic, l increasing to the left and b downward (verified with the bright stars).
const GAL = [-0.0548755604162154, -0.8734370902348850, -0.4838350155487132, 0.4941094278755837, -0.4448296299600112, 0.7469822444972189, -0.8676661490190047, -0.1980763734312015, 0.4559837761750669];
const WARPS = [1, 10, 100, 1e3, 1e4, 1e5, 1e6, 1e7];
const jdToDate = jd => new Date((jd - 2440587.5) * 86400000);
const fmtDate = jd => jdToDate(jd).toISOString().replace('T', ' ').slice(0, 19) + ' UTC';

function interp(tr, jd) {                                   // position of a sampled track at a Julian date (clamped)
  const J = tr.jd, n = J.length; if (n === 1 || jd <= J[0]) return tr.r[0]; if (jd >= J[n - 1]) return tr.r[n - 1];
  let lo = 0, hi = n - 1; while (hi - lo > 1) { const m = (lo + hi) >> 1; if (J[m] <= jd) lo = m; else hi = m; }
  const f = (jd - J[lo]) / (J[hi] - J[lo]), a = tr.r[lo], b = tr.r[hi]; return [a[0] + f * (b[0] - a[0]), a[1] + f * (b[1] - a[1]), a[2] + f * (b[2] - a[2])];
}

export function createSpace(host, data, opts = {}) {
  host.replaceChildren(); host.classList.add('spacehost');
  const W = () => Math.max(300, host.clientWidth), H = () => Math.max(260, host.clientHeight);
  const renderer = new THREE.WebGLRenderer({ antialias: true, logarithmicDepthBuffer: true, preserveDrawingBuffer: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2)); renderer.setSize(W(), H()); host.append(renderer.domElement); renderer.domElement.className = 'spacecanvas';
  const scene = new THREE.Scene(), camera = new THREE.PerspectiveCamera(50, W() / H(), 1e-3, 1e14); camera.up.set(0, 0, 1);
  const controls = new OrbitControls(camera, renderer.domElement); controls.enableDamping = true; controls.dampingFactor = 0.08; controls.zoomSpeed = 1.2;
  const world = new THREE.Group(); scene.add(world);
  const state = { warp: 3, playing: false, sky: opts.sky || 'milkyway', bright: 3.0, markers: false, exag: 1, labels: true, soi: true, lag: true, axes: false, ecl: false, paths: true, focus: data.center, t: 0, dir: 1 };
  const loader = new THREE.TextureLoader(), t0 = data.jd0, t1 = data.jd1, span = Math.max(1e-9, t1 - t0);
  let jd = t0, raf = 0, last = 0, flyTo = null;

  // ---- sky: a sphere that follows the camera, sampling the galactic map along the ICRF direction
  const skyMat = new THREE.ShaderMaterial({ side: THREE.BackSide, depthWrite: false, depthTest: false,
    uniforms: { map: { value: null }, gal: { value: new THREE.Matrix3().set(...GAL) }, gain: { value: state.bright }, mode: { value: 0 } },
    vertexShader: 'varying vec3 vDir; void main(){ vDir = position; vec4 p = projectionMatrix * modelViewMatrix * vec4(position,1.0); gl_Position = p.xyww; }',
    fragmentShader: 'uniform sampler2D map; uniform mat3 gal; uniform float gain; uniform float mode; varying vec3 vDir; const float PI = 3.14159265359;' +
      'void main(){ if (mode > 1.5) { gl_FragColor = vec4(0.0,0.0,0.0,1.0); return; } vec3 g = gal * normalize(vDir); float l = atan(g.y, g.x); float b = asin(clamp(g.z,-1.0,1.0));' +
      'vec2 uv = vec2(0.5 - l/(2.0*PI), 0.5 - b/PI); vec3 c = texture2D(map, uv).rgb * gain; if (mode > 0.5) c = vec3(0.02,0.03,0.07) + c; gl_FragColor = vec4(c,1.0); }' });
  const skyMesh = new THREE.Mesh(new THREE.SphereGeometry(1, 48, 24), skyMat); skyMesh.renderOrder = -10; skyMesh.frustumCulled = false; scene.add(skyMesh);
  const loadSky = name => loader.load('/assets/textures/' + name, tx => { tx.generateMipmaps = false; tx.minFilter = THREE.LinearFilter; tx.colorSpace = THREE.SRGBColorSpace; skyMat.uniforms.map.value = tx; });
  const setSky = k => { state.sky = k; skyMat.uniforms.mode.value = k === 'black' ? 2 : k === 'theme' ? 1 : 0; loadSky(k === 'stars' ? '2k_stars.jpg' : '2k_stars_milky_way.jpg'); };
  setSky(state.sky);

  // ---- lights
  scene.add(new THREE.AmbientLight(0xffffff, 0.45)); const sun = new THREE.DirectionalLight(0xffffff, 2.4); sun.position.set(1, 0.3, 0.4); world.add(sun); world.add(sun.target);

  // ---- bodies
  const bodies = {}; const labelHost = el('div', { class: 'spacelabels' }); host.append(labelHost);
  const mkLabel = (text, color) => { const d = el('div', { class: 'slabel', style: `color:${color || '#fff'}` }, text); labelHost.append(d); return d; };
  for (const b of data.bodies) {
    if (b.visible === false) continue;
    const mat = new THREE.MeshStandardMaterial({ color: b.color || '#6b7fb5', roughness: 1, metalness: 0 }); if (b.texture) loader.load('/assets/textures/' + b.texture, tx => { tx.colorSpace = THREE.SRGBColorSpace; mat.map = tx; mat.color.set('#ffffff'); mat.needsUpdate = true; });
    if (b.name === 'Sun') { mat.emissive = new THREE.Color('#ffd27a'); mat.emissiveIntensity = 1; mat.color.set('#ffd27a'); }
    const mesh = new THREE.Mesh(new THREE.SphereGeometry(1, 48, 32), mat); mesh.rotation.x = Math.PI / 2; world.add(mesh);                       // texture poles along z
    const o = { def: b, mesh, label: mkLabel(b.name, '#cfe0ff'), soi: null };
    if (b.soi) { o.soi = new THREE.Mesh(new THREE.SphereGeometry(1, 40, 20), new THREE.MeshBasicMaterial({ color: '#4c8df6', wireframe: true, transparent: true, opacity: 0.12 })); world.add(o.soi); }
    const par = b.parent ? data.bodies.find(x => x.name === b.parent) : null;                                      // orbit drawn relative to the parent, around its current position
    if (b.path && b.path.r.length > 1) {
      const pts = par && par.path ? b.path.r.map((p, i) => new THREE.Vector3(p[0] - par.path.r[i][0], p[1] - par.path.r[i][1], p[2] - par.path.r[i][2])) : b.path.r.map(p => new THREE.Vector3(...p));
      o.line = new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), new THREE.LineBasicMaterial({ color: b.orbitColor || '#7b8bb0', transparent: true, opacity: 0.55 })); o.rel = !!(par && par.path); world.add(o.line);
    }
    if (b.parent && b.path && b.path.r.length > 1) { o.parentId = b.parent; }
    bodies[b.name] = o;
  }
  // ---- spacecraft tracks
  const tracks = data.tracks.map(tr => {
    const pts = tr.r.map(p => new THREE.Vector3(...p)); const g = new THREE.BufferGeometry().setFromPoints(pts);
    const full = new THREE.Line(g, new THREE.LineBasicMaterial({ color: tr.color, transparent: true, opacity: 0.35 })); world.add(full);
    const g2 = new THREE.BufferGeometry().setFromPoints(pts); const done = new THREE.Line(g2, new THREE.LineBasicMaterial({ color: tr.color })); world.add(done);
    const mk = new THREE.Mesh(new THREE.SphereGeometry(1, 16, 12), new THREE.MeshBasicMaterial({ color: tr.color })); world.add(mk);
    return { def: tr, full, done, mk, label: mkLabel(tr.name, tr.color), n: pts.length };
  });
  const refs = (data.refs || []).map(rf => { const g = new THREE.BufferGeometry().setFromPoints(rf.r.map(p => new THREE.Vector3(...p))); const l = new THREE.Line(g, new THREE.LineDashedMaterial({ color: '#b37bf0', dashSize: 1, gapSize: 1 })); l.computeLineDistances(); world.add(l); return l; });
  // ---- overlays: Lagrange points, axes, ecliptic plane, event markers
  const lag = (data.lagrange || []).map(L => ({ def: L, mk: new THREE.Mesh(new THREE.OctahedronGeometry(1), new THREE.MeshBasicMaterial({ color: '#f5b73b' })), label: mkLabel(L.name, '#f5b73b') })); lag.forEach(l => world.add(l.mk));
  const axes = new THREE.Group(); for (const [c, v] of [['#ff6161', [1, 0, 0]], ['#3ecf8e', [0, 1, 0]], ['#4c8df6', [0, 0, 1]]]) { const g = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), new THREE.Vector3(...v)]); axes.add(new THREE.Line(g, new THREE.LineBasicMaterial({ color: c }))); } axes.visible = false; world.add(axes);
  const ecl = new THREE.GridHelper(2, 20, '#556', '#334'); ecl.rotation.x = Math.PI / 2 + 0.40909280; ecl.visible = false; world.add(ecl);               // ecliptic: tilted by the obliquity from the equator (z up)
  const evMarks = (data.events || []).map(e => { const m = new THREE.Mesh(new THREE.OctahedronGeometry(1), new THREE.MeshBasicMaterial({ color: e.kind === 'burn' ? '#ff6161' : '#ffffff' })); m.position.set(...e.r); world.add(m); return { def: e, m }; });

  // ---- sky markers (debug aid for the sky orientation): bright stars, the galactic centre and Polaris, drawn on the sky sphere
  const dirOf = (ra, dec) => { const a = ra * Math.PI / 180, d = dec * Math.PI / 180; return new THREE.Vector3(Math.cos(d) * Math.cos(a), Math.cos(d) * Math.sin(a), Math.sin(d)); };
  const markers = (data.markers || []).map(m => ({ def: m, dir: dirOf(m.ra, m.dec), label: mkLabel(m.name, '#9dffb0'), mk: new THREE.Mesh(new THREE.RingGeometry(0.8, 1, 24), new THREE.MeshBasicMaterial({ color: '#9dffb0', side: THREE.DoubleSide, depthTest: false })) }));
  markers.forEach(m => { m.mk.renderOrder = 5; scene.add(m.mk); });
  const posOf = name => { if (bodies[name]) return interp(bodies[name].def.path || { jd: [0], r: [[0, 0, 0]] }, jd); const tr = tracks.find(t => t.def.name === name); return tr ? interp(tr.def, jd) : [0, 0, 0]; };
  const names = () => [...Object.keys(bodies), ...tracks.map(t => t.def.name)];
  const ext = data.extent || 1e5;
  camera.position.set(ext * 1.6, -ext * 1.6, ext * 1.1); controls.target.set(0, 0, 0); controls.update();

  state.selected = null;
  const ring = new THREE.Mesh(new THREE.RingGeometry(0.94, 1, 64), new THREE.MeshBasicMaterial({ color: '#ffffff', side: THREE.DoubleSide, depthTest: false, transparent: true, opacity: 0.9 })); ring.renderOrder = 6; ring.visible = false; scene.add(ring);
  const label = (el_, v3, show) => {                                             // project a label; hide it when it falls off screen
    if (!show || !state.labels) { el_.style.display = 'none'; return null; }
    const p = v3.clone().project(camera); if (p.z > 1 || p.z < -1 || Math.abs(p.x) > 1.05 || Math.abs(p.y) > 1.05) { el_.style.display = 'none'; return null; }
    el_.style.display = 'block'; el_.style.transform = `translate(${(p.x * 0.5 + 0.5) * W() + 8}px, ${(-p.y * 0.5 + 0.5) * H() - 8}px)`; return el_;
  };
  function layout() {
    const cp = camera.position.clone().add(world.position.clone().negate()), tgt = controls.target.clone();
    const tgtD = camera.position.distanceTo(controls.target), unit = tgtD * 0.012, placed = [];
    for (const o of Object.values(bodies)) {
      const p = posOf(o.def.name); o.mesh.position.set(...p); const r = Math.max(o.def.R * state.exag, unit * 0.6); o.mesh.scale.setScalar(r);
      if (o.soi) { o.soi.position.set(...p); o.soi.scale.setScalar(o.def.soi); o.soi.visible = state.soi; }
      if (o.line) { o.line.visible = state.paths; if (o.rel) o.line.position.set(...posOf(o.def.parent)); o.line.material.opacity = state.selected === o.def.name ? 1 : 0.45; } const l = label(o.label, o.mesh.position, true); if (l) placed.push(l);
      if (o.def.name === 'Sun') { const c = o.mesh.position; sun.position.copy(c); sun.target.position.set(0, 0, 0); }
    }
    if (!bodies.Sun) sun.position.set(1e8, 3e7, 4e7);
    for (const t of tracks) {
      const p = interp(t.def, jd); t.mk.position.set(...p); t.mk.scale.setScalar(unit * 0.9); const f = Math.max(2, Math.floor(t.n * clamp01((jd - t.def.jd[0]) / Math.max(1e-9, t.def.jd[t.def.jd.length - 1] - t.def.jd[0]))));
      t.done.geometry.setDrawRange(0, f); t.full.visible = t.done.visible = state.paths; const l = label(t.label, t.mk.position, true); if (l) placed.push(l);
    }
    for (const l of lag) { l.mk.position.set(...interp(l.def, jd)); l.mk.scale.setScalar(unit * 0.8); l.mk.visible = state.lag; label(l.label, l.mk.position, state.lag); }
    axes.visible = state.axes; axes.scale.setScalar(ext * 0.6); ecl.visible = state.ecl; ecl.scale.setScalar(ext * 1.5);
    for (const e of evMarks) e.m.scale.setScalar(unit * 0.6);
    for (const rf of refs) rf.material.dashSize = rf.material.gapSize = ext * 0.01;
    // declutter: a later label that overlaps an earlier one is hidden
    const boxes = []; for (const el_ of placed) { const b = el_.getBoundingClientRect(); if (boxes.some(q => !(b.right < q.left || b.left > q.right || b.bottom < q.top || b.top > q.bottom))) el_.style.display = 'none'; else boxes.push(b); }
    skyMesh.position.copy(camera.position); skyMesh.scale.setScalar(1e5);
    if (state.selected && bodies[state.selected]) { const o = bodies[state.selected], rr = Math.max(o.mesh.scale.x * 1.25, unit * 1.6); ring.visible = true; ring.position.copy(o.mesh.position); ring.quaternion.copy(camera.quaternion); ring.scale.setScalar(rr); } else ring.visible = false;
    for (const m of markers) { m.mk.visible = state.markers; const p = camera.position.clone().add(m.dir.clone().multiplyScalar(5e4)); m.mk.position.copy(p); m.mk.quaternion.copy(camera.quaternion); m.mk.scale.setScalar(900); label(m.label, p, state.markers); }
  }
  const clamp01 = x => Math.max(0, Math.min(1, x));

  // ---- focus: the controls target follows the chosen object (smooth fly-to)
  function followFocus(dt) {
    const p = posOf(state.focus), want = new THREE.Vector3(...p), delta = want.clone().sub(controls.target);
    if (flyTo) { const k = Math.min(1, dt * 3); controls.target.add(delta.clone().multiplyScalar(k)); camera.position.add(delta.clone().multiplyScalar(k)); const d = camera.position.distanceTo(controls.target); flyTo.dist += (flyTo.want - flyTo.dist) * k;
      camera.position.sub(controls.target).setLength(flyTo.dist).add(controls.target); if (delta.length() < 1e-6 * Math.max(1, flyTo.dist) && Math.abs(flyTo.want - flyTo.dist) < 1e-3 * flyTo.want) flyTo = null; }
    else { controls.target.add(delta); camera.position.add(delta); }
  }
  function frame(now) {
    raf = requestAnimationFrame(frame); const dt = last ? Math.min(0.1, (now - last) / 1000) : 0; last = now;
    if (state.playing) { jd += state.dir * dt * (state.rate != null ? state.rate : WARPS[state.warp]) / 86400; if (jd > t1) { jd = t1; state.playing = false; host.dispatchEvent(new CustomEvent('space-state')); } if (jd < t0) { jd = t0; state.playing = false; host.dispatchEvent(new CustomEvent('space-state')); } host.dispatchEvent(new CustomEvent('space-time')); }
    followFocus(dt); controls.update(); layout(); skyMat.uniforms.gain.value = state.bright; renderer.render(scene, camera);
  }
  frame(0);
  const ro = new ResizeObserver(() => { renderer.setSize(W(), H()); camera.aspect = W() / H(); camera.updateProjectionMatrix(); }); ro.observe(host);

  return {
    state, names, t0, t1, get jd() { return jd; }, fmt: fmtDate, canvas: renderer.domElement,
    setJD(v) { jd = Math.max(t0, Math.min(t1, v)); }, play(on) { state.playing = on === undefined ? !state.playing : on; },
    setWarp(i) { state.warp = Math.max(0, Math.min(WARPS.length - 1, i)); }, warpLabel: () => WARPS[state.warp] + '×',
    focus(name) { state.focus = name; const o = bodies[name]; let want = Math.max(((o && o.def.R) || ext * 0.02) * 6, 1e-3);
      if (o && o.def.parent && bodies[o.def.parent]) { const pp = posOf(o.def.parent), pb = posOf(name); want = Math.max(want, 0.6 * Math.hypot(pp[0] - pb[0], pp[1] - pb[1], pp[2] - pb[2])); }       // tiny bodies: frame their whole orbit
      flyTo = { dist: camera.position.distanceTo(controls.target), want }; if (o === undefined) flyTo.want = ext * 0.12; },
    view(kind) { const d = camera.position.distanceTo(controls.target), t = controls.target; if (kind === 'top') camera.position.set(t.x, t.y, t.z + d); else if (kind === 'iso') camera.position.set(t.x + d * 0.62, t.y - d * 0.62, t.z + d * 0.48); else if (kind === 'side') camera.position.set(t.x, t.y - d, t.z); controls.update(); },
    look(ra, dec) { const d = camera.position.distanceTo(controls.target), dir = dirOf(ra, dec); camera.position.copy(controls.target).addScaledVector(dir, -d); controls.update(); },
    markerList: () => markers.map(m => m.def.name),
    select(name) { state.selected = name; }, setRate(r) { state.rate = r; }, getCamera() { return { p: camera.position.toArray(), t: controls.target.toArray() }; },
    setCamera(c) { camera.position.fromArray(c.p); controls.target.fromArray(c.t); controls.update(); },
    pick(cx, cy) {                                                                    // nearest body to a screen point (within 18 px), preferring the larger on-screen body
      const rect = renderer.domElement.getBoundingClientRect(), x = cx - rect.left, y = cy - rect.top; let best = null, bd = 18;
      for (const o of Object.values(bodies)) { const p = o.mesh.position.clone().project(camera); if (p.z > 1) continue; const sx = (p.x * 0.5 + 0.5) * rect.width, sy = (-p.y * 0.5 + 0.5) * rect.height; const d = Math.hypot(sx - x, sy - y);
        const rs = o.mesh.scale.x / (2 * Math.tan(camera.fov * Math.PI / 360) * camera.position.distanceTo(o.mesh.position)) * rect.height; const dd = d - rs; if (dd < bd) { bd = dd; best = o.def.name; } }
      return best;
    },
    onPick(cb) { let dn = null; const c = renderer.domElement; c.addEventListener('pointerdown', e => { dn = [e.clientX, e.clientY]; }); c.addEventListener('pointerup', e => { if (dn && Math.hypot(e.clientX - dn[0], e.clientY - dn[1]) < 4) cb(this.pick(e.clientX, e.clientY), e); dn = null; }); },
    posOf: name => posOf(name), velOf(name) { const d = 0.01, a = posOf(name); const sv = interp(bodies[name].def.path, Math.max(t0, jd - d)), sb = interp(bodies[name].def.path, Math.min(t1, jd + d)); const dtS = (Math.min(t1, jd + d) - Math.max(t0, jd - d)) * 86400 || 1; return [(sb[0] - sv[0]) / dtS, (sb[1] - sv[1]) / dtS, (sb[2] - sv[2]) / dtS]; },
    setSky, set(k, v) { state[k] = v; }, nextEvent() { const ts = (data.events || []).map(e => e.jd).filter(t => t > jd + 1e-9).sort((a, b) => a - b); if (ts.length) jd = ts[0]; },
    png() { return renderer.domElement.toDataURL('image/png'); },
    record(on, done) {
      if (on) { const stream = renderer.domElement.captureStream(30); const chunks = []; const rec = new MediaRecorder(stream, { mimeType: MediaRecorder.isTypeSupported('video/webm;codecs=vp9') ? 'video/webm;codecs=vp9' : 'video/webm', videoBitsPerSecond: 8e6 });
        rec.ondataavailable = e => chunks.push(e.data); rec.onstop = () => done(new Blob(chunks, { type: 'video/webm' })); rec.start(250); this._rec = rec; } else if (this._rec) { this._rec.stop(); this._rec = null; }
    },
    dispose() { cancelAnimationFrame(raf); ro.disconnect(); controls.dispose(); renderer.dispose(); host.replaceChildren(); }
  };
}
