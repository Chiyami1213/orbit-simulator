/* Space view for the Mission workspace (three.js, vendored under /vendor, MIT). Bodies, trajectories, a physically oriented Milky Way sky, time warp, overlays, recording.
   Axes are ICRF (z up). Positions are kilometers about the display center; the camera orbits a focus point, with a logarithmic depth buffer so a 100 km orbit
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


/* ---- body shapes: spheres, the two satellite models, a lumpy asteroid, a comet with a tail, a black hole with an accretion disk, a star with a glow, a ringed planet ---- */
const SATURN_POLE = [40.589, 83.537];
function lumpy(seed = 7, detail = 3) {                                    // an irregular rock: a noise-displaced icosphere, stretched
  const g = new THREE.IcosahedronGeometry(1, detail), pos = g.attributes.position; let a = seed;
  const rnd = () => { a = (a * 16807) % 2147483647; return a / 2147483647; }, wob = Array.from({ length: 12 }, () => [rnd() * 6.28, rnd() * 6.28, 0.04 + rnd() * 0.09]);
  for (let i = 0; i < pos.count; i++) { const v = new THREE.Vector3().fromBufferAttribute(pos, i).normalize(); let d = 1; for (const [p, q, k] of wob) d += k * Math.sin(p + 3 * v.x + 2 * v.y) * Math.cos(q + 3 * v.z + v.x); v.multiplyScalar(d); pos.setXYZ(i, v.x * 1.25, v.y * 0.85, v.z * 0.75); }
  g.computeVertexNormals(); return g;
}
function glowSprite(color, size) {
  const c = document.createElement('canvas'); c.width = c.height = 128; const x = c.getContext('2d'), g = x.createRadialGradient(64, 64, 0, 64, 64, 64); g.addColorStop(0, color); g.addColorStop(0.25, color + '88'); g.addColorStop(1, color + '00'); x.fillStyle = g; x.fillRect(0, 0, 128, 128);
  const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: new THREE.CanvasTexture(c), transparent: true, depthWrite: false, blending: THREE.AdditiveBlending })); sp.scale.setScalar(size); return sp;
}
export function buildShape(shape, color, models, loader) {
  const g = new THREE.Group(); const col = color || '#8aa0c8';
  if ((shape === 'comsat' || shape === 'probe') && models && models[shape]) {
    const m = models[shape], geo = new THREE.BufferGeometry(); geo.setAttribute('position', new THREE.Float32BufferAttribute(m.x.flatMap((x, i) => [x, m.y[i], m.z[i]]), 3));
    geo.setAttribute('color', new THREE.Float32BufferAttribute(m.colors.flatMap(h => { const c = new THREE.Color(h); return [c.r, c.g, c.b]; }), 3)); geo.setIndex(m.i.flatMap((x, n) => [x, m.j[n], m.k[n]])); geo.computeVertexNormals();
    const mesh = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({ vertexColors: true, flatShading: true, roughness: 0.6, metalness: 0.4, side: THREE.DoubleSide })); mesh.scale.setScalar(0.9); g.add(mesh); g.userData.orient = true; return g;
  }
  if (shape === 'asteroid' || shape === 'comet') {
    const rock = new THREE.Mesh(lumpy(shape === 'comet' ? 3 : 7), new THREE.MeshStandardMaterial({ color: shape === 'comet' ? '#9aa4b0' : '#8c8174', roughness: 1, flatShading: true })); g.add(rock);
    if (shape === 'comet') {
      const L = 16, tail = new THREE.Mesh(new THREE.ConeGeometry(1.6, L, 24, 1, true).translate(0, L / 2, 0), new THREE.MeshBasicMaterial({ color: '#bfe3ff', transparent: true, opacity: 0.28, depthWrite: false, side: THREE.DoubleSide, blending: THREE.AdditiveBlending }));
      g.add(tail); g.userData.tail = tail; g.add(glowSprite('#cfe8ff', 6));
    }
    return g;
  }
  if (shape === 'blackhole') {
    g.add(new THREE.Mesh(new THREE.SphereGeometry(1, 48, 32), new THREE.MeshBasicMaterial({ color: '#000000' })));
    const disk = new THREE.Mesh(new THREE.RingGeometry(1.5, 4.2, 96, 4), new THREE.MeshBasicMaterial({ vertexColors: true, side: THREE.DoubleSide, transparent: true, opacity: 0.95, depthWrite: false, blending: THREE.AdditiveBlending }));
    const pos = disk.geometry.attributes.position, cols = []; for (let i = 0; i < pos.count; i++) { const r = Math.hypot(pos.getX(i), pos.getY(i)), t = (r - 1.5) / 2.7, c = new THREE.Color().setHSL(0.09 - 0.07 * t, 1, 0.62 - 0.45 * t); cols.push(c.r, c.g, c.b); }
    disk.geometry.setAttribute('color', new THREE.Float32BufferAttribute(cols, 3)); disk.rotation.x = 1.25; g.add(disk);
    const ring = new THREE.Mesh(new THREE.RingGeometry(1.08, 1.16, 96), new THREE.MeshBasicMaterial({ color: '#ffe6c0', side: THREE.DoubleSide, transparent: true, opacity: 0.7, depthWrite: false })); ring.userData.billboard = true; g.add(ring); g.userData.ring = ring; return g;
  }
  const mat = new THREE.MeshStandardMaterial({ color: col, roughness: 1, metalness: 0 });
  const ball = new THREE.Mesh(new THREE.SphereGeometry(1, 48, 32), mat); ball.rotation.x = Math.PI / 2; g.add(ball); g.userData.ball = ball; g.userData.mat = mat;
  if (shape === 'star') { mat.emissive = new THREE.Color(col); mat.emissiveIntensity = 1; g.add(glowSprite(col.replace('#', '#').slice(0, 7), 5)); }
  if (shape === 'ring') {                                                               // Saturn: a flat ring in the equator plane, textured with the real ring strip
    const rg = new THREE.RingGeometry(1.25, 2.4, 128, 1), pos = rg.attributes.position, uv = rg.attributes.uv; for (let i = 0; i < pos.count; i++) uv.setXY(i, (Math.hypot(pos.getX(i), pos.getY(i)) - 1.25) / 1.15, 0.5);
    const rm = new THREE.MeshBasicMaterial({ color: '#d9c9a0', side: THREE.DoubleSide, transparent: true, opacity: 0.85, depthWrite: false }); if (loader) loader.load('/assets/textures/2k_saturn_ring_alpha.png', tx => { tx.colorSpace = THREE.SRGBColorSpace; rm.map = tx; rm.color.set('#ffffff'); rm.needsUpdate = true; });
    const ringMesh = new THREE.Mesh(rg, rm); const a = SATURN_POLE[0] * Math.PI / 180, d = SATURN_POLE[1] * Math.PI / 180; ringMesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, 0, 1), new THREE.Vector3(Math.cos(d) * Math.cos(a), Math.cos(d) * Math.sin(a), Math.sin(d))); g.add(ringMesh);
  }
  return g;
}
const isStar = d => d.kind === 'star' || d.shape === 'star' || d.name === 'Sun';
const ATMO = { 'Earth': ['#6bb3ff', 1.0], 'Venus': ['#ffd9a0', 0.9], 'Mars': ['#e0a27c', 0.35], 'Jupiter': ['#d8c0a0', 0.45], 'Saturn': ['#e8d8a8', 0.45], 'Uranus': ['#a8e8f0', 0.6], 'Neptune': ['#6a8cff', 0.6], 'Earth-like Planet': ['#7fd8ff', 0.9], 'Gas Giant': ['#d8c0a0', 0.45] };
function atmoMat(hex, k) {                                                           // a thin glow around the limb, brighter on the lit side; one extra sphere, very cheap
  return new THREE.ShaderMaterial({ transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, uniforms: { uColor: { value: new THREE.Color(hex) }, uSun: { value: new THREE.Vector3(1, 0, 0) }, uLit: { value: 1 }, uK: { value: k } },
    vertexShader: '#include <common>\n#include <logdepthbuf_pars_vertex>\nvarying vec3 vN; varying vec3 vP; void main(){ vN = normalize(normalMatrix * normal); vec4 mv = modelViewMatrix * vec4(position, 1.0); vP = mv.xyz; gl_Position = projectionMatrix * mv;\n#include <logdepthbuf_vertex>\n}',
    fragmentShader: '#include <logdepthbuf_pars_fragment>\nuniform vec3 uColor; uniform vec3 uSun; uniform float uLit; uniform float uK; varying vec3 vN; varying vec3 vP; void main(){\n#include <logdepthbuf_fragment>\n float rim = 1.0 - abs(dot(normalize(vN), normalize(-vP))); float a = pow(rim, 3.2) * uK; float lit = mix(1.0, smoothstep(-0.25, 0.35, dot(normalize(vN), uSun)), uLit); gl_FragColor = vec4(uColor, a * lit); }' });
}
const SKY_IMG = new Map();                                                          // decoded sky images, shared by every view that is opened
const skyImage = url => { if (!SKY_IMG.has(url)) SKY_IMG.set(url, new Promise((res, rej) => { const im = new Image(); im.onload = () => res(im); im.onerror = rej; im.src = url; })); return SKY_IMG.get(url); };
let thumbRenderer = null;
export function renderThumbs(list, models, size = 112) {                              // [{key, shape, color}] -> {key: dataURL}, drawn with one small off-screen renderer
  if (!thumbRenderer) { thumbRenderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, preserveDrawingBuffer: true }); thumbRenderer.setSize(size, size); }
  const out = {}, sc = new THREE.Scene(), cam = new THREE.PerspectiveCamera(32, 1, 0.1, 100); sc.add(new THREE.AmbientLight(0xffffff, 0.7)); const dl = new THREE.DirectionalLight(0xffffff, 2.2); dl.position.set(2, 1.5, 3); sc.add(dl);
  for (const it of list) {
    const obj = buildShape(it.shape, it.color, models, null), box = new THREE.Box3().setFromObject(obj), sphere = box.getBoundingSphere(new THREE.Sphere()); obj.position.sub(sphere.center); sc.add(obj);
    if (it.shape === 'comsat' || it.shape === 'probe') obj.rotation.set(0.35, -0.7, 0.2); if (it.shape === 'asteroid') obj.rotation.set(0.4, 0.5, 0); if (it.shape === 'comet') obj.rotation.set(0.1, 0, -0.5);
    if (it.shape === 'blackhole') obj.rotation.x = -0.25;
    const d = sphere.radius / Math.tan(cam.fov * Math.PI / 360) * 1.12; cam.position.set(0, 0, d); cam.lookAt(0, 0, 0); thumbRenderer.render(sc, cam); out[it.key] = thumbRenderer.domElement.toDataURL('image/png'); sc.remove(obj);
  }
  return out;
}

export function createSpace(host, data, opts = {}) {
  host.replaceChildren(); host.classList.add('spacehost');
  const W = () => Math.max(300, host.clientWidth), H = () => Math.max(260, host.clientHeight);
  const renderer = new THREE.WebGLRenderer({ antialias: true, logarithmicDepthBuffer: true, preserveDrawingBuffer: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 1.75)); renderer.setSize(W(), H()); host.append(renderer.domElement); renderer.domElement.className = 'spacecanvas';
  const scene = new THREE.Scene(), camera = new THREE.PerspectiveCamera(50, W() / H(), 1e-3, 1e14); camera.up.set(0, 0, 1);
  const controls = new OrbitControls(camera, renderer.domElement); controls.enableDamping = true; controls.dampingFactor = 0.08; controls.zoomSpeed = 1.2;
  const world = new THREE.Group(); scene.add(world);
  controls.addEventListener('start', () => { flyTo = null; });                        // the moment you drag or scroll, the fly-to stops and the mouse is in charge again (zoom in and out freely)
  const state = { warp: 3, playing: false, sky: opts.sky || 'milkyway', bright: 1.0, markers: false, exag: 1, labels: true, soi: true, lag: true, axes: false, ecl: false, paths: true, focus: data.center, t: 0, dir: 1, light: 'even', atmo: true, spin: true, equ: false };
  const loader = new THREE.TextureLoader(), t0 = data.jd0, t1 = data.jd1, span = Math.max(1e-9, t1 - t0);
  let jd = t0, raf = 0, last = 0, flyTo = null; let disposed = false;
  let ghostGrp = null, ghostMk = null;                                                  // the placement preview of the sandbox (marker, orbit ring, aim arrow)

  // ---- sky: a sphere that follows the camera, sampling the galactic map along the ICRF direction
  const skyMat = new THREE.ShaderMaterial({ side: THREE.BackSide, depthWrite: false, depthTest: false,
    uniforms: { map: { value: null }, gal: { value: new THREE.Matrix3().set(...GAL) }, gain: { value: state.bright }, mode: { value: 0 }, flip: { value: 1 }, themeColor: { value: new THREE.Vector3(0.06, 0.09, 0.16) } },
    vertexShader: 'varying vec3 vDir; void main(){ vDir = position; vec4 p = projectionMatrix * modelViewMatrix * vec4(position,1.0); gl_Position = p.xyww; }',
    fragmentShader: 'uniform sampler2D map; uniform mat3 gal; uniform float gain; uniform float mode; uniform float flip; uniform vec3 themeColor; varying vec3 vDir; const float PI = 3.14159265359;' +
      'void main(){ if (mode > 1.5) { gl_FragColor = vec4(0.0,0.0,0.0,1.0); return; } if (mode > 0.5) { gl_FragColor = vec4(themeColor, 1.0); return; } vec3 g = gal * normalize(vDir); float l = atan(g.y, g.x); float b = asin(clamp(g.z,-1.0,1.0));' +
      'vec2 uv = vec2(0.5 - l/(2.0*PI), 0.5 + flip * b/PI); vec3 c = texture2D(map, uv).rgb * gain; gl_FragColor = vec4(c,1.0); }' });
  const skyMesh = new THREE.Mesh(new THREE.SphereGeometry(1, 48, 24), skyMat); skyMesh.renderOrder = -10; skyMesh.frustumCulled = false; scene.add(skyMesh);
  // NASA SVS "Deep Star Maps 2020" (galactic, latitude up, display-referred): 8k when the GPU allows it, else 4k. The older 2k star map has latitude downward and needs a gain.
  const big = renderer.capabilities.maxTextureSize >= 8192; let skyScale = 1;
  // Switching the background must be instant: the sky images are decoded once (kept across view rebuilds), turned into textures once, and uploaded to the GPU in the idle time after the view opens,
  // so a switch only swaps a uniform.
  const skyTex = {}, skyName = legacy => legacy ? '2k_stars.jpg' : (big ? 'sky_milkyway_8k.jpg' : 'sky_milkyway_4k.jpg');
  const getSky = async (name, legacy) => {
    if (skyTex[name]) return skyTex[name]; const img = await skyImage('/assets/textures/' + name), tx = new THREE.Texture(img);
    tx.generateMipmaps = false; tx.minFilter = THREE.LinearFilter; tx.colorSpace = legacy ? THREE.SRGBColorSpace : THREE.NoColorSpace; tx.needsUpdate = true; skyTex[name] = tx;
    try { renderer.initTexture(tx); } catch (e) { } return tx;
  };
  const loadSky = (name, legacy) => { if (skyTex[name]) skyMat.uniforms.map.value = skyTex[name]; else getSky(name, legacy).then(tx => { if (skyName(state.sky === 'stars') === name && state.sky !== 'black' && state.sky !== 'theme') skyMat.uniforms.map.value = tx; }); };
  const setSky = k => { state.sky = k; skyMat.uniforms.mode.value = k === 'black' ? 2 : k === 'theme' ? 1 : 0; const legacy = k === 'stars'; skyMat.uniforms.flip.value = legacy ? -1 : 1; skyScale = legacy ? 3 : 1;
    if (k === 'theme') { const hex = (getComputedStyle(document.body).getPropertyValue('--bg') || '#0f1628').trim().replace('#', ''); const n = parseInt(hex.length === 3 ? hex.split('').map(c => c + c).join('') : hex, 16); skyMat.uniforms.themeColor.value.set(((n >> 16) & 255) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255); }       // the app's background color, flat: no stars, no galaxy
    if (k !== 'black' && k !== 'theme') loadSky(legacy ? '2k_stars.jpg' : (big ? 'sky_milkyway_8k.jpg' : 'sky_milkyway_4k.jpg'), legacy); };
  setTimeout(() => { if (!disposed) getSky(skyName(false), false); }, 1500); setTimeout(() => { if (!disposed) getSky(skyName(true), true); }, 3200);        // preload both star backgrounds
  let lightUI = opts.theme === 'light';
  function refreshTheme() {
    const lb = lightUI && state.sky === 'theme'; host.classList.toggle('lightbg', lb);
    const css = (getComputedStyle(document.body).getPropertyValue('--bg') || '').trim(), hx = /^#([0-9a-f]{6})$/i.exec(css);                   // the Theme Color background is the page color of the chosen color theme
    if (hx) skyMat.uniforms.themeColor.value.set(parseInt(hx[1].slice(0, 2), 16) / 255, parseInt(hx[1].slice(2, 4), 16) / 255, parseInt(hx[1].slice(4, 6), 16) / 255); else skyMat.uniforms.themeColor.value.set(lightUI ? 0.93 : 0.06, lightUI ? 0.95 : 0.09, lightUI ? 0.98 : 0.16);
    if (typeof ring !== 'undefined') { ring.material.color.set(lb ? '#16203a' : '#ffffff'); hring.material.color.set(lb ? '#b86a00' : '#ffd27a'); }
  }
  setSky(state.sky);

  // ---- lights
  // Lighting: every star in the scene is a point light at its own position (up to two), so planets have a real day side, night side and terminator.
  //   real = inverse-square fall-off (outer planets are dim), even = the same brightness everywhere but the true direction, full = no shading at all.
  //   A scene without a star keeps one fixed sun light.
  const ambient = new THREE.AmbientLight(0xffffff, 0.45), sun = new THREE.DirectionalLight(0xffffff, 2.4); scene.add(ambient); sun.position.set(1, 0.3, 0.4); world.add(sun); world.add(sun.target);
  const starDefs = data.bodies.filter(d => d.visible !== false && isStar(d)).sort((a, b) => (b.mu || b.R || 0) - (a.mu || a.R || 0)).slice(0, 2), REFD = 1.496e8;
  const starLights = starDefs.map(d => { const L = new THREE.PointLight(d.color || '#ffffff', 1, 0, 0); world.add(L); return { def: d, L, rel: Math.min(3, Math.max(0.03, Math.pow((d.mu || 1) / (starDefs[0].mu || 1), 3))) }; });
  let litMode = '';
  function applyLighting() {
    litMode = state.light; const full = state.light === 'full', real = state.light === 'real';
    ambient.intensity = full ? 3.2 : (starLights.length ? 0.28 : 0.45); sun.visible = !full && !starLights.length;
    for (const s of starLights) { s.L.visible = !full; s.L.decay = real ? 2 : 0; s.L.intensity = (real ? 2.4 * REFD * REFD : 2.6) * s.rel; }
  }
  applyLighting();
  // texture helpers: every map is kept as a slot so a sharper (downloaded) version can be swapped in for the body that is big on screen
  const configTex = (tx, srgb) => { tx.colorSpace = srgb ? THREE.SRGBColorSpace : THREE.NoColorSpace; tx.anisotropy = Math.min(8, renderer.capabilities.getMaxAnisotropy()); };
  function loadSlot(slots, mat, prop, file, done, srgb = true) {
    const sl = { mat, prop, file, baseTex: null, hiTex: null, loading: false }; slots.push(sl);
    loader.load('/assets/textures/' + file, tx => { configTex(tx, srgb); sl.baseTex = tx; if (!sl.hiTex) mat[prop] = tx; mat.needsUpdate = true; if (done) done(tx); }); return sl;
  }

  // ---- bodies
  const bodies = {}; const labelHost = el('div', { class: 'spacelabels' }); host.append(labelHost);
  const mkLabel = (text, color) => { const d = el('div', { class: 'slabel', style: `color:${color || '#fff'}` }, text); labelHost.append(d); return d; };
  for (const b of data.bodies) {
    if (b.visible === false) continue;
    const mat = new THREE.MeshStandardMaterial({ color: !b.texture && b.clouds ? '#0b1a33' : (b.color || '#6b7fb5'), roughness: 1, metalness: 0 }), slots = [];
    if (b.texture) loadSlot(slots, mat, 'map', b.texture, () => mat.color.set('#ffffff'));
    let nightU = null;
    if (b.night) {                                                                     // city lights: only on the side that faces away from the star
      nightU = { uSun: { value: new THREE.Vector3(1, 0, 0) }, uNight: { value: 1 } };
      loadSlot(slots, mat, 'emissiveMap', b.night, () => { mat.emissive.set('#ffffff'); mat.emissiveIntensity = 1.5; });
      mat.onBeforeCompile = sh => { sh.uniforms.uSun = nightU.uSun; sh.uniforms.uNight = nightU.uNight; sh.fragmentShader = 'uniform vec3 uSun; uniform float uNight;\n' + sh.fragmentShader.replace('#include <emissivemap_fragment>', '#include <emissivemap_fragment>\n  totalEmissiveRadiance *= uNight * smoothstep(0.12, -0.2, dot(normalize(vNormal), uSun));'); };
    }
    if (b.name === 'Sun') { mat.emissive = new THREE.Color('#ffd27a'); mat.emissiveIntensity = 1; mat.color.set('#ffd27a'); }
    let mesh; const shape = b.shape || (b.name === 'Sun' ? 'star' : 'sphere');
    if (shape === 'sphere' || shape === 'star' && false) { mesh = new THREE.Mesh(new THREE.SphereGeometry(1, 48, 32), mat); mesh.rotation.x = Math.PI / 2; }              // texture poles along z
    else { mesh = buildShape(shape, b.color, data.models, loader); const ball = mesh.userData.ball; if (ball) { ball.material = mat; ball.material.needsUpdate = true; } }
    const shells = [];
    if (shape === 'sphere') {
      if (b.clouds) { const cm = new THREE.MeshStandardMaterial({ color: '#ffffff', transparent: true, depthWrite: false, roughness: 1, metalness: 0 }); loadSlot(slots, cm, 'alphaMap', b.clouds, null, false); mesh.add(new THREE.Mesh(new THREE.SphereGeometry(1.012, 48, 32), cm)); }
      const am = ATMO[b.name]; if (am) { const sh = new THREE.Mesh(new THREE.SphereGeometry(1.045, 48, 32), atmoMat(am[0], am[1])); mesh.add(sh); shells.push(sh); }
      if (isStar(b)) mesh.add(glowSprite('#ffd27a', 4.5));
    }
    world.add(mesh);
    const o = { def: b, mesh, label: mkLabel(b.name, '#cfe0ff'), soi: null, slots, nightU, shells, hiOn: false, spinTarget: shape === 'sphere' ? mesh : (mesh.userData.ball || null) };
    if (b.soi) { o.soi = new THREE.Mesh(new THREE.SphereGeometry(1, 40, 20), new THREE.MeshBasicMaterial({ color: '#4c8df6', wireframe: true, transparent: true, opacity: 0.12 })); world.add(o.soi); }
    const par = b.parent ? data.bodies.find(x => x.name === b.parent) : null;                                      // orbit drawn relative to the parent, around its current position
    const osc = !!(opts.osc && par && par.path && b.path && b.path.r.length > 1 && (par.mu || 0) > 0);
    if (osc) {
      const NV = 181, g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.BufferAttribute(new Float32Array(NV * 3), 3)); g.setDrawRange(0, 0);
      o.orb = new THREE.Line(g, new THREE.LineBasicMaterial({ color: b.orbitColor || '#7b8bb0', transparent: true, opacity: 0.55 })); o.orb.frustumCulled = false; world.add(o.orb);
      o.hStep = 1.5 * (b.path.jd[b.path.jd.length - 1] - b.path.jd[0]) / Math.max(1, b.path.jd.length - 1);
    }
    if (!osc && b.path && b.path.r.length > 1) {
      const pts = par && par.path ? b.path.r.map((p, i) => new THREE.Vector3(p[0] - par.path.r[i][0], p[1] - par.path.r[i][1], p[2] - par.path.r[i][2])) : b.path.r.map(p => new THREE.Vector3(...p));
      if (par && par.path) { let ang = 0; for (let i = 1; i < pts.length; i++) { const a = pts[i - 1], c = pts[i], d = a.dot(c) / Math.max(1e-12, a.length() * c.length()); ang += Math.acos(Math.max(-1, Math.min(1, d))); if (ang >= 2 * Math.PI * 1.005) { pts.length = i + 1; break; } } }       // one revolution is enough: a fast orbit must not fill the screen
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
    const tip = new THREE.Line(new THREE.BufferGeometry().setAttribute('position', new THREE.BufferAttribute(new Float32Array(6), 3)), new THREE.LineBasicMaterial({ color: tr.color })); tip.frustumCulled = false; world.add(tip);       // the last piece, from the last sample to the spacecraft
    const model = opts.model && opts.model !== 'marker' && data.models && data.models[opts.model] ? opts.model : null;                    // 'comsat' | 'probe' (the same models as the 3d plots) or a plain marker
    const mk = model ? buildShape(model, tr.color, data.models, loader) : new THREE.Mesh(new THREE.SphereGeometry(1, 16, 12), new THREE.MeshBasicMaterial({ color: tr.color })); world.add(mk);
    return { def: tr, full, done, tip, pts, mk, label: mkLabel(tr.name, tr.color), n: pts.length };
  });
  const refs = (data.refs || []).map(rf => { const g = new THREE.BufferGeometry().setFromPoints(rf.r.map(p => new THREE.Vector3(...p))); const l = new THREE.Line(g, new THREE.LineDashedMaterial({ color: '#b37bf0', dashSize: 1, gapSize: 1 })); l.computeLineDistances(); world.add(l); return l; });
  // ---- overlays: Lagrange points, axes, ecliptic plane, event markers
  const lag = (data.lagrange || []).map(L => ({ def: L, mk: new THREE.Mesh(new THREE.OctahedronGeometry(1), new THREE.MeshBasicMaterial({ color: '#f5b73b' })), label: mkLabel(L.name, '#f5b73b') })); lag.forEach(l => world.add(l.mk));
  const axes = new THREE.Group(); for (const [c, v] of [['#ff6161', [1, 0, 0]], ['#3ecf8e', [0, 1, 0]], ['#4c8df6', [0, 0, 1]]]) { const g = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), new THREE.Vector3(...v)]); axes.add(new THREE.Line(g, new THREE.LineBasicMaterial({ color: c }))); } axes.visible = false; world.add(axes);
  const ecl = new THREE.GridHelper(2, 20, '#556', '#334'); ecl.rotation.x = Math.PI / 2 + 0.40909280; ecl.visible = false; world.add(ecl);               // ecliptic: tilted by the obliquity from the equator (z up)
  const equ = new THREE.GridHelper(2, 24, '#3ec9b0', '#2a6f66'); equ.visible = false; equ.material.transparent = true; equ.material.opacity = 0.55; world.add(equ);                        // equatorial plane of the focus body
  const evMarks = (data.events || []).map(e => { const m = new THREE.Mesh(new THREE.OctahedronGeometry(1), new THREE.MeshBasicMaterial({ color: e.kind === 'burn' ? '#ff6161' : '#ffffff' })); m.position.set(...e.r); world.add(m); return { def: e, m }; });

  // ---- sky markers (debug aid for the sky orientation): bright stars, the galactic center and Polaris, drawn on the sky sphere
  const dirOf = (ra, dec) => { const a = ra * Math.PI / 180, d = dec * Math.PI / 180; return new THREE.Vector3(Math.cos(d) * Math.cos(a), Math.cos(d) * Math.sin(a), Math.sin(d)); };
  const markers = (data.markers || []).map(m => ({ def: m, dir: dirOf(m.ra, m.dec), label: mkLabel(m.name, '#9dffb0'), mk: new THREE.Mesh(new THREE.RingGeometry(0.8, 1, 24), new THREE.MeshBasicMaterial({ color: '#9dffb0', side: THREE.DoubleSide, depthTest: false })) }));
  markers.forEach(m => { m.mk.renderOrder = 5; scene.add(m.mk); });
  const this_velOf = name => { const o = bodies[name]; if (!o || !o.def.path) return [0, 0, 0]; const d = 0.01, a = interp(o.def.path, Math.max(t0, jd - d)), b = interp(o.def.path, Math.min(t1, jd + d)); return [b[0] - a[0], b[1] - a[1], b[2] - a[2]]; };
  const posOf = name => { if (bodies[name]) return interp(bodies[name].def.path || { jd: [0], r: [[0, 0, 0]] }, jd); const tr = tracks.find(t => t.def.name === name); return tr ? interp(tr.def, jd) : [0, 0, 0]; };
  const names = () => [...Object.keys(bodies), ...tracks.map(t => t.def.name)];
  const ext = data.extent || 1e5;
  camera.position.set(ext * 1.6, -ext * 1.6, ext * 1.1); controls.target.set(0, 0, 0); controls.update();

  state.selected = null; state.hover = null;
  const ring = new THREE.Mesh(new THREE.RingGeometry(0.94, 1, 64), new THREE.MeshBasicMaterial({ color: '#ffffff', side: THREE.DoubleSide, depthTest: false, transparent: true, opacity: 0.9 })); ring.renderOrder = 6; ring.visible = false; scene.add(ring);
  const hring = new THREE.Mesh(new THREE.RingGeometry(0.9, 1, 64), new THREE.MeshBasicMaterial({ color: '#ffd27a', side: THREE.DoubleSide, depthTest: false, transparent: true, opacity: 0.95 })); hring.renderOrder = 6; hring.visible = false; scene.add(hring); refreshTheme();       // the circle that shows what a click would pick
  const label = (el_, v3, show) => {                                             // project a label; hide it when it falls off screen
    if (!show || !state.labels) { el_.style.display = 'none'; return null; }
    const p = v3.clone().project(camera); if (p.z > 1 || p.z < -1 || Math.abs(p.x) > 1.05 || Math.abs(p.y) > 1.05) { el_.style.display = 'none'; return null; }
    el_.style.display = 'block'; el_.style.transform = `translate(${(p.x * 0.5 + 0.5) * W() + 8}px, ${(-p.y * 0.5 + 0.5) * H() - 8}px)`; return el_;
  };
  const sl0pos = () => posOf(starLights[0].def.name);
  // Body rotation: the IAU / JPL pole and prime meridian (def.spin). The body-fixed frame is Rz(ra+90) Rx(90-dec) Rz(W); the sphere's poles lie along z and its texture center (longitude 0) along +x.
  const DEG = Math.PI / 180, qa = new THREE.Quaternion(), qb = new THREE.Quaternion(), AX = new THREE.Vector3(1, 0, 0), AZ = new THREE.Vector3(0, 0, 1), BASEQ = new THREE.Quaternion().setFromAxisAngle(AX, Math.PI / 2);
  function spinBody(o) {
    const sp = o.def.spin, d = jd - 2451545.0, T = d / 36525, ra = (sp.ra + (sp.ra_rate || 0) * T) * DEG, dec = (sp.dec + (sp.dec_rate || 0) * T) * DEG; let W = sp.w0 + sp.rate * d;
    const perSec = state.playing ? Math.abs(sp.rate * (state.rate != null ? state.rate : WARPS[state.warp]) / 86400) : 0;
    if (perSec > 200) W = sp.w0 + Math.sign(sp.rate) * performance.now() / 1000 * 40;         // too fast to follow at this time warp: a slow steady turn instead of a flicker
    const q = o.spinTarget.quaternion; q.setFromAxisAngle(AZ, ra + Math.PI / 2); qa.setFromAxisAngle(AX, Math.PI / 2 - dec); q.multiply(qa); qb.setFromAxisAngle(AZ, W * DEG); q.multiply(qb); q.multiply(BASEQ);
  }
  // The osculating orbit of a body about its parent: from the relative position and velocity at the current time (the velocity from the sampled path), the conic is drawn from its
  // elements. The body is on this curve by definition, so the line can never come loose from the body, however the orbit changes (perturbations, close encounters, edits).
  function updateOsc(o) {
    const par = bodies[o.def.parent], mu = par ? (par.def.mu || 0) + (o.def.mu || 0) : 0; if (!par || !(mu > 0)) { o.orb.visible = false; return; }
    const tp = Math.min(t1, jd + o.hStep), tm = Math.max(t0, jd - o.hStep), dts = (tp - tm) * 86400; if (!(dts > 0)) { o.orb.visible = false; return; }
    const r1 = interp(o.def.path, jd), q1 = interp(par.def.path, jd), r = [r1[0] - q1[0], r1[1] - q1[1], r1[2] - q1[2]];
    const a1 = interp(o.def.path, tp), b1 = interp(par.def.path, tp), a0 = interp(o.def.path, tm), b0 = interp(par.def.path, tm);
    const v = [((a1[0] - b1[0]) - (a0[0] - b0[0])) / dts, ((a1[1] - b1[1]) - (a0[1] - b0[1])) / dts, ((a1[2] - b1[2]) - (a0[2] - b0[2])) / dts];
    const rn = Math.hypot(r[0], r[1], r[2]), v2 = v[0] * v[0] + v[1] * v[1] + v[2] * v[2], rv = r[0] * v[0] + r[1] * v[1] + r[2] * v[2];
    const hx = r[1] * v[2] - r[2] * v[1], hy = r[2] * v[0] - r[0] * v[2], hz = r[0] * v[1] - r[1] * v[0], h2 = hx * hx + hy * hy + hz * hz; if (!(rn > 0) || !(h2 > 1e-18)) { o.orb.visible = false; return; }
    const ex = ((v2 - mu / rn) * r[0] - rv * v[0]) / mu, ey = ((v2 - mu / rn) * r[1] - rv * v[1]) / mu, ez = ((v2 - mu / rn) * r[2] - rv * v[2]) / mu, e = Math.hypot(ex, ey, ez), pp = h2 / mu;
    const hn = Math.sqrt(h2), hh = [hx / hn, hy / hn, hz / hn]; const P = e > 1e-7 ? [ex / e, ey / e, ez / e] : [r[0] / rn, r[1] / rn, r[2] / rn];
    const Q = [hh[1] * P[2] - hh[2] * P[1], hh[2] * P[0] - hh[0] * P[2], hh[0] * P[1] - hh[1] * P[0]];
    let nu0 = 0, nu1 = 2 * Math.PI; if (e >= 1) { const m = Math.acos(-1 / e) * 0.985; nu0 = -m; nu1 = m; } else { nu0 = Math.atan2(r[0] * Q[0] + r[1] * Q[1] + r[2] * Q[2], r[0] * P[0] + r[1] * P[1] + r[2] * P[2]); nu1 = nu0 + 2 * Math.PI; }       // start at the body itself
    const pos = o.orb.geometry.attributes.position, NV = pos.count;
    for (let k = 0; k < NV; k++) { const nu = nu0 + (nu1 - nu0) * k / (NV - 1), rr = pp / (1 + e * Math.cos(nu)), c = Math.cos(nu) * rr, sn = Math.sin(nu) * rr; pos.setXYZ(k, c * P[0] + sn * Q[0], c * P[1] + sn * Q[1], c * P[2] + sn * Q[2]); }
    pos.needsUpdate = true; o.orb.geometry.setDrawRange(0, NV); o.orb.visible = state.paths; o.orb.position.set(q1[0], q1[1], q1[2]); o.orb.material.opacity = state.selected === o.def.name ? 1 : 0.45;
  }
  function layout() {
    const cp = camera.position.clone().add(world.position.clone().negate()), tgt = controls.target.clone();
    const tgtD = camera.position.distanceTo(controls.target), unit = tgtD * 0.012, placed = [];
    camera.updateMatrixWorld(); if (litMode !== state.light) applyLighting();
    for (const sl of starLights) sl.L.position.set(...posOf(sl.def.name));
    const sp = starLights.length ? sl0pos() : sun.position.toArray(), dirV = new THREE.Vector3();
    if (ghostMk) ghostMk.scale.setScalar(unit * 0.9);
    for (const o of Object.values(bodies)) {
      const p = posOf(o.def.name); o.mesh.position.set(...p); const minS = o.mesh.userData.orient ? 3.5 : (o.def.shape === 'asteroid' || o.def.shape === 'comet' ? 1.1 : 0.6); const r = Math.max(o.def.R * state.exag, unit * minS); o.mesh.scale.setScalar(r);
      if (o.mesh.userData.orient) { const v = this_velOf(o.def.name); const n = Math.hypot(...v); if (n > 0) o.mesh.quaternion.setFromUnitVectors(new THREE.Vector3(1, 0, 0), new THREE.Vector3(v[0] / n, v[1] / n, v[2] / n)); }
      if (o.mesh.userData.tail) { const sp = bodies.Sun ? posOf('Sun') : [0, 0, 0], a = new THREE.Vector3(p[0] - sp[0], p[1] - sp[1], p[2] - sp[2]).normalize(); o.mesh.userData.tail.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), a); }
      if (o.mesh.userData.ring) o.mesh.userData.ring.quaternion.copy(camera.quaternion);
      if (o.soi) { o.soi.position.set(...p); o.soi.scale.setScalar(o.def.soi); o.soi.visible = state.soi; }
      if (o.orb) updateOsc(o);
      if (o.line) { o.line.visible = state.paths; if (o.rel) o.line.position.set(...posOf(o.def.parent)); o.line.material.opacity = state.selected === o.def.name ? 1 : 0.45; } const l = label(o.label, o.mesh.position, true); if (l) placed.push(l);
      if (o.spinTarget && o.def.spin && state.spin) spinBody(o);
      if (o.nightU || o.shells.length) { dirV.set(sp[0] - p[0], sp[1] - p[1], sp[2] - p[2]).transformDirection(camera.matrixWorldInverse); const lit = state.light === 'full' ? 0 : 1;
        if (o.nightU) { o.nightU.uSun.value.copy(dirV); o.nightU.uNight.value = lit; } for (const sh of o.shells) { sh.visible = state.atmo; sh.material.uniforms.uSun.value.copy(dirV); sh.material.uniforms.uLit.value = lit; } }
      if (o.def.name === 'Sun' && !starLights.length) { const c = o.mesh.position; sun.position.copy(c); sun.target.position.set(0, 0, 0); }
    }
    if (!bodies.Sun) sun.position.set(1e8, 3e7, 4e7);
    for (const t of tracks) {
      const p = interp(t.def, jd); t.mk.position.set(...p); t.mk.scale.setScalar(unit * (t.mk.userData.orient ? 3.5 : 0.9));
      if (t.mk.userData.orient) { const q = interp(t.def, Math.min(t.def.jd[t.def.jd.length - 1], jd + 0.01)), q0 = interp(t.def, Math.max(t.def.jd[0], jd - 0.01)), v = new THREE.Vector3(q[0] - q0[0], q[1] - q0[1], q[2] - q0[2]); if (v.length() > 0) t.mk.quaternion.setFromUnitVectors(new THREE.Vector3(1, 0, 0), v.normalize()); } const k = sampleAt(t.def.jd, jd);
      t.done.geometry.setDrawRange(0, k + 1); { const a = t.pts[k], at = t.tip.geometry.attributes.position; at.setXYZ(0, a.x, a.y, a.z); at.setXYZ(1, p[0], p[1], p[2]); at.needsUpdate = true; }
      t.full.visible = t.done.visible = t.tip.visible = state.paths; const l = label(t.label, t.mk.position, true); if (l) placed.push(l);
    }
    for (const l of lag) { l.mk.position.set(...interp(l.def, jd)); l.mk.scale.setScalar(unit * 0.8); l.mk.visible = state.lag; label(l.label, l.mk.position, state.lag); }
    { equ.visible = state.equ; if (state.equ) { const fb = bodies[state.focus], sp = fb && fb.def.spin; let nz = new THREE.Vector3(0, 0, 1); if (sp) { const T = (jd - 2451545.0) / 36525, ra = (sp.ra + (sp.ra_rate || 0) * T) * Math.PI / 180, dec = (sp.dec + (sp.dec_rate || 0) * T) * Math.PI / 180; nz.set(Math.cos(dec) * Math.cos(ra), Math.cos(dec) * Math.sin(ra), Math.sin(dec)); }
        equ.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), nz); const c = fb ? posOf(state.focus) : [0, 0, 0]; equ.position.set(c[0], c[1], c[2]); equ.scale.setScalar(ext * 1.5); } }
    axes.visible = state.axes; axes.scale.setScalar(ext * 0.6); ecl.visible = state.ecl; ecl.scale.setScalar(ext * 1.5);
    for (const e of evMarks) e.m.scale.setScalar(unit * 0.6);
    if (nodeMk) nodeMk.scale.setScalar(unit * 0.9);
    for (const rf of refs) rf.material.dashSize = rf.material.gapSize = ext * 0.01;
    // declutter: a later label that overlaps an earlier one is hidden
    const boxes = []; for (const el_ of placed) { const b = el_.getBoundingClientRect(); if (boxes.some(q => !(b.right < q.left || b.left > q.right || b.bottom < q.top || b.top > q.bottom))) el_.style.display = 'none'; else boxes.push(b); }
    skyMesh.position.copy(camera.position); skyMesh.scale.setScalar(1e5);
    if (state.selected && bodies[state.selected]) { const o = bodies[state.selected], rr = Math.max(o.mesh.scale.x * 1.25, unit * 1.6); ring.visible = true; ring.position.copy(o.mesh.position); ring.quaternion.copy(camera.quaternion); ring.scale.setScalar(rr); } else ring.visible = false;
    if (state.hover && state.hover !== state.selected && bodies[state.hover]) { const o = bodies[state.hover], rr = Math.max(o.mesh.scale.x * 1.3, unit * 2.4); hring.visible = true; hring.position.copy(o.mesh.position); hring.quaternion.copy(camera.quaternion); hring.scale.setScalar(rr); } else hring.visible = false;
    for (const m of markers) { m.mk.visible = state.markers; const p = camera.position.clone().add(m.dir.clone().multiplyScalar(5e4)); m.mk.position.copy(p); m.mk.quaternion.copy(camera.quaternion); m.mk.scale.setScalar(900); label(m.label, p, state.markers); }
  }
  // sharper maps (downloaded 8K / 4K): only the one body that is large on screen gets them, the rest keep the 2K maps, so GPU memory stays small
  let hiMap = opts.hires || null; const gpu8k = renderer.capabilities.maxTextureSize >= 8192;
  const hiNameFor = file => { const h = hiMap && hiMap[file]; return h && (gpu8k || !h.startsWith('8k_')) ? h : null; };
  function ensureHi(o) {
    o.hiOn = true;
    for (const sl of o.slots) { const h = hiNameFor(sl.file); if (!h || sl.hiTex || sl.loading) continue; sl.loading = true;
      loader.load('/usertex/' + h, tx => { sl.loading = false; configTex(tx, sl.prop !== 'alphaMap'); if (!o.hiOn) { tx.dispose(); return; } sl.hiTex = tx; sl.mat[sl.prop] = tx; sl.mat.needsUpdate = true; }, undefined, () => { sl.loading = false; }); }
  }
  function dropHi(o) { o.hiOn = false; for (const sl of o.slots) if (sl.hiTex) { sl.mat[sl.prop] = sl.baseTex; sl.hiTex.dispose(); sl.hiTex = null; sl.mat.needsUpdate = true; } }
  function hiUpdate() {
    const all = Object.values(bodies); if (!hiMap) { for (const o of all) if (o.hiOn) dropHi(o); return; }
    const hpx = renderer.domElement.clientHeight || 600, cp = camera.position.clone().sub(world.position), tf = 2 * Math.tan(camera.fov * Math.PI / 360);
    const best = all.filter(o => o.slots.some(sl => hiNameFor(sl.file))).map(o => ({ o, px: o.mesh.scale.x / (tf * Math.max(1e-9, cp.distanceTo(o.mesh.position))) * hpx })).filter(c => c.px > 110).sort((a, b) => b.px - a.px)[0];
    for (const o of all) { if (best && o === best.o) { if (!o.hiOn) ensureHi(o); } else if (o.hiOn) dropHi(o); }
  }
  // keeps the frame rate up on weak graphics cards: the render resolution drops a little when frames get slow and comes back when they are fast again
  const prBase = Math.min(window.devicePixelRatio || 1, 1.75); let pr = prBase, emaMs = 16.7, perfT = 0, lastNow = 0, frameN = 0;
  function perf(now) {
    const d = now - lastNow; lastNow = now; if (d > 0 && d < 500) emaMs = emaMs * 0.92 + d * 0.08;
    if (document.hidden || now - perfT < 2500) return; perfT = now; const fps = 1000 / emaMs;
    if (fps < 28 && pr > 0.6) { pr = Math.max(0.6, pr * 0.8); renderer.setPixelRatio(pr); } else if (fps > 55 && pr < prBase) { pr = Math.min(prBase, pr * 1.15); renderer.setPixelRatio(pr); }
  }
  let preview = null, nodeMk = null;
  const clamp01 = x => Math.max(0, Math.min(1, x));
  const sampleAt = (arr, v) => { let lo = 0, hi = arr.length - 1; while (lo < hi) { const m = (lo + hi + 1) >> 1; if (arr[m] <= v) lo = m; else hi = m - 1; } return lo; };            // the last sample at or before a time

  // ---- focus: the controls target follows the chosen object (smooth fly-to)
  function followFocus(dt) {
    const p = posOf(state.focus), want = new THREE.Vector3(...p), delta = want.clone().sub(controls.target);
    if (flyTo) { const k = Math.min(1, dt * 3); controls.target.add(delta.clone().multiplyScalar(k)); camera.position.add(delta.clone().multiplyScalar(k)); const d = camera.position.distanceTo(controls.target); flyTo.dist += (flyTo.want - flyTo.dist) * k;
      camera.position.sub(controls.target).setLength(flyTo.dist).add(controls.target); if (Math.abs(flyTo.want - flyTo.dist) < 0.02 * flyTo.want) flyTo = null; }                  // arrived (a moving body must not keep the camera locked at this distance)
    else { controls.target.add(delta); camera.position.add(delta); }
  }
  function frame(now) {
    raf = requestAnimationFrame(frame); const dt = last ? Math.min(0.1, (now - last) / 1000) : 0; last = now;
    if (state.playing) { jd += state.dir * dt * (state.rate != null ? state.rate : WARPS[state.warp]) / 86400; if (jd > t1) { jd = t1; state.playing = false; host.dispatchEvent(new CustomEvent('space-state')); } if (jd < t0) { jd = t0; state.playing = false; host.dispatchEvent(new CustomEvent('space-state')); } host.dispatchEvent(new CustomEvent('space-time')); }
    { const fb = bodies[state.focus], rF = fb ? Math.max(fb.def.R * state.exag, 1e-6) : ext * 0.01, ratio = camera.position.distanceTo(controls.target) / rF; controls.minDistance = fb ? rF * 1.05 : 0; controls.zoomSpeed = ratio > 30 ? Math.min(11, 1.2 + 2.5 * Math.log10(ratio / 30)) : 1.2; }
    followFocus(dt); controls.update(); layout(); if (++frameN % 24 === 0) hiUpdate(); perf(now); skyMat.uniforms.gain.value = state.bright * skyScale; renderer.render(scene, camera);
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
    setPreview(pts, node) {                                                            // the predicted path of a maneuver node (dashed white) and the node marker
      if (preview) { world.remove(preview); preview.geometry.dispose(); preview = null; } if (nodeMk) { world.remove(nodeMk); nodeMk = null; }
      if (pts && pts.length > 1) { const g = new THREE.BufferGeometry().setFromPoints(pts.map(p => new THREE.Vector3(...p))); preview = new THREE.Line(g, new THREE.LineDashedMaterial({ color: '#ffffff', dashSize: ext * 0.01, gapSize: ext * 0.006 })); preview.computeLineDistances(); world.add(preview); }
      if (node) { nodeMk = new THREE.Mesh(new THREE.OctahedronGeometry(1), new THREE.MeshBasicMaterial({ color: '#ff6161' })); nodeMk.position.set(...node); world.add(nodeMk); }
    },
    planePoint(cx, cy, center, incDeg) {                                              // where the mouse ray meets the plane through a body (tilted by inc about the x axis): the spot a placed object would go
      const rect = renderer.domElement.getBoundingClientRect(), ndc = new THREE.Vector2(((cx - rect.left) / rect.width) * 2 - 1, -((cy - rect.top) / rect.height) * 2 + 1);
      const rc = new THREE.Raycaster(); rc.setFromCamera(ndc, camera); const o = rc.ray.origin.clone().sub(world.position), d = rc.ray.direction, c = posOf(center), i = (incDeg || 0) * Math.PI / 180;
      const n = new THREE.Vector3(0, -Math.sin(i), Math.cos(i)), dn = n.dot(d); if (Math.abs(dn) < 1e-6) return null; const t = n.dot(new THREE.Vector3(c[0] - o.x, c[1] - o.y, c[2] - o.z)) / dn; if (t < 0) return null;
      return [o.x + d.x * t, o.y + d.y * t, o.z + d.z * t];
    },
    setGhost(g) {                                                                      // g = { p, color, ring: { c, r, inc }, arrow: [from, to] } or null
      if (ghostGrp) { world.remove(ghostGrp); ghostGrp.traverse(o => { if (o.geometry) o.geometry.dispose(); }); ghostGrp = null; ghostMk = null; } if (!g) return;
      ghostGrp = new THREE.Group(); const col = g.color || '#ffffff';
      ghostMk = new THREE.Mesh(new THREE.SphereGeometry(1, 16, 12), new THREE.MeshBasicMaterial({ color: col, transparent: true, opacity: 0.85 })); ghostMk.position.set(...g.p); ghostGrp.add(ghostMk);
      if (g.ring) { const { c, r, inc } = g.ring, i = (inc || 0) * Math.PI / 180, pts = []; for (let k = 0; k <= 160; k++) { const t = k / 160 * 2 * Math.PI, u = r * Math.cos(t), w = r * Math.sin(t); pts.push(new THREE.Vector3(c[0] + u, c[1] + w * Math.cos(i), c[2] + w * Math.sin(i))); }
        ghostGrp.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), new THREE.LineBasicMaterial({ color: col, transparent: true, opacity: 0.7 }))); }
      if (g.arrow) ghostGrp.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(g.arrow.map(q => new THREE.Vector3(...q))), new THREE.LineBasicMaterial({ color: '#ffffff' })));
      world.add(ghostGrp);
    },
    select(name) { state.selected = name; }, hover(name) { state.hover = name; }, setHires(m) { hiMap = m || null; hiUpdate(); }, setRate(r) { state.rate = r; }, getCamera() { return { p: camera.position.toArray(), t: controls.target.toArray() }; },
    setCamera(c) { camera.position.fromArray(c.p); controls.target.fromArray(c.t); controls.update(); },
    pick(cx, cy) {                                                                    // nearest body to a screen point (within 18 px), preferring the larger on-screen body
      const rect = renderer.domElement.getBoundingClientRect(), x = cx - rect.left, y = cy - rect.top; let best = null, bd = 18;
      for (const o of Object.values(bodies)) { const p = o.mesh.position.clone().project(camera); if (p.z > 1) continue; const sx = (p.x * 0.5 + 0.5) * rect.width, sy = (-p.y * 0.5 + 0.5) * rect.height; const d = Math.hypot(sx - x, sy - y);
        const rs = o.mesh.scale.x / (2 * Math.tan(camera.fov * Math.PI / 360) * camera.position.distanceTo(o.mesh.position)) * rect.height; const dd = d - rs; if (dd < bd) { bd = dd; best = o.def.name; } }
      return best;
    },
    onPick(cb) { let dn = null; const c = renderer.domElement; c.addEventListener('pointerdown', e => { dn = [e.clientX, e.clientY]; }); c.addEventListener('pointerup', e => { if (dn && Math.hypot(e.clientX - dn[0], e.clientY - dn[1]) < 4) cb(this.pick(e.clientX, e.clientY), e); dn = null; }); },
    posOf: name => posOf(name), velOf(name) { const d = 0.01, a = posOf(name); const sv = interp(bodies[name].def.path, Math.max(t0, jd - d)), sb = interp(bodies[name].def.path, Math.min(t1, jd + d)); const dtS = (Math.min(t1, jd + d) - Math.max(t0, jd - d)) * 86400 || 1; return [(sb[0] - sv[0]) / dtS, (sb[1] - sv[1]) / dtS, (sb[2] - sv[2]) / dtS]; },
    orbitPoints(name) { const o = bodies[name]; if (!o || !o.orb) return null; const a = o.orb.geometry.attributes.position, c = o.orb.position, out = []; for (let k = 0; k < a.count; k++) out.push([a.getX(k) + c.x, a.getY(k) + c.y, a.getZ(k) + c.z]); return out; },
    perf() { return { pixelRatio: pr, baseRatio: prBase, fps: Math.round(1000 / emaMs), bodies: Object.keys(bodies).length, width: renderer.domElement.width, height: renderer.domElement.height }; },
    zoomBy(f) { flyTo = null; const t = controls.target, v = camera.position.clone().sub(t), d = v.length(); if (d <= 0) return; camera.position.copy(t).addScaledVector(v.normalize(), Math.max(controls.minDistance || d * 1e-6, d * f)); controls.update(); },
    setSky(k) { setSky(k); refreshTheme(); }, setTheme(t) { lightUI = t === 'light'; refreshTheme(); }, set(k, v) { state[k] = v; }, nextEvent() { const ts = (data.events || []).map(e => e.jd).filter(t => t > jd + 1e-9).sort((a, b) => a - b); if (ts.length) { jd = ts[0]; host.dispatchEvent(new CustomEvent('space-time')); return true; } return false; },
    png() { return renderer.domElement.toDataURL('image/png'); },
    record(on, done) {
      if (on) { const stream = renderer.domElement.captureStream(30); const chunks = []; const rec = new MediaRecorder(stream, { mimeType: MediaRecorder.isTypeSupported('video/webm;codecs=vp9') ? 'video/webm;codecs=vp9' : 'video/webm', videoBitsPerSecond: 8e6 });
        rec.ondataavailable = e => chunks.push(e.data); rec.onstop = () => done(new Blob(chunks, { type: 'video/webm' })); rec.start(250); this._rec = rec; } else if (this._rec) { this._rec.stop(); this._rec = null; }
    },
    dispose() {                                                                       // free the GPU memory (the sandbox rebuilds the view after every edit)
      disposed = true; cancelAnimationFrame(raf); ro.disconnect(); controls.dispose();
      for (const o of Object.values(bodies)) { dropHi(o); for (const sl of o.slots) if (sl.baseTex) sl.baseTex.dispose(); } for (const k of Object.keys(skyTex)) skyTex[k].dispose();
      renderer.dispose(); try { renderer.forceContextLoss(); } catch (e) { } host.replaceChildren();
    }
  };
}
