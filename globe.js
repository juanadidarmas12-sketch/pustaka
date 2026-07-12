/* ============ Pustaka — globe.js ============ */
/* Globe 3D interaktif utk #/konstelasi. Modul ES; dipanggil via import() dinamis dari app.js. */
'use strict';

import * as THREE from './vendor/three.module.min.js';

const CAT_LABELS = {
  filsafat: 'Filsafat', politik: 'Politik', sejarah: 'Sejarah',
  ekonomi: 'Ekonomi', sosial: 'Sosial'
};
const CAT_COLORS = {
  filsafat: 0x6b5fa8, politik: 0xa8455a, sejarah: 0xb98a3e,
  ekonomi: 0x4f8a5c, sosial: 0x47899a
};
const FALLBACK_COLOR = 0x9a8d7a;
const ERA_LABELS = ['Kuno', 'Klasik', 'Pertengahan', 'Renaisans', 'Pencerahan', 'Modern'];

const YEAR_MIN = -700, YEAR_MAX = 1970, YEAR_STEP = 5, YEAR_DEFAULT = -400;
const AUTO_ROTATE_SPEED = 0.04;   // rad/s saat idle
const ROTATE_SENS = 0.006;        // rad per px drag
const TILT_SENS = 0.006;
const TILT_CLAMP = 0.5;
const INERTIA_DAMP = 0.95;
const SCALE_LERP = 0.12;
const HORIZON_DOT = 0.05;
const TAP_MAX_MOVE = 8;
const TAP_HIT_PX = 28;
const MARKER_R_HIDDEN = 0.985;
const MARKER_R_SHOWN = 1.005;
const ZOOM_MIN = 1, ZOOM_MAX = 3;

function hashStr(s) {
  let h = 0;
  for (let i = 0; i < s.length; i++) { h = ((h << 5) - h + s.charCodeAt(i)) | 0; }
  return Math.abs(h);
}

function formatYear(y) {
  return Math.abs(y) + (y < 0 ? ' SM' : ' M');
}

function latLngToVec3(lat, lng, r) {
  const phi = (90 - lat) * Math.PI / 180;
  const theta = (lng + 180) * Math.PI / 180;
  const x = -r * Math.sin(phi) * Math.cos(theta);
  const z = r * Math.sin(phi) * Math.sin(theta);
  const y = r * Math.cos(phi);
  return new THREE.Vector3(x, y, z);
}

function escHTML(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[c]));
}

export async function initGlobe(root, ctx) {
  const { geo, AUTHORS, catOf, onNavigate, reducedMotion } = ctx;

  /* ---------- DOM ---------- */
  root.innerHTML = '';
  root.classList.add('globe-root');

  const title = document.createElement('h2');
  title.className = 'cx-map-title';
  title.textContent = 'Konstelasi Pengetahuan';

  const subtitle = document.createElement('p');
  subtitle.className = 'cx-map-sub';
  subtitle.textContent = '115 pemikir - putar globe, geser waktu';

  const stage = document.createElement('div');
  stage.className = 'globe-stage';

  const popupEl = document.createElement('div');
  popupEl.className = 'globe-popup';
  popupEl.hidden = true;
  stage.appendChild(popupEl);

  const chip = document.createElement('div');
  chip.className = 'globe-year-chip';
  chip.textContent = formatYear(YEAR_DEFAULT);

  const slider = document.createElement('input');
  slider.type = 'range';
  slider.className = 'globe-year-range';
  slider.min = String(YEAR_MIN);
  slider.max = String(YEAR_MAX);
  slider.step = String(YEAR_STEP);
  slider.value = String(YEAR_DEFAULT);
  slider.setAttribute('aria-label', 'Tahun');

  const eraRow = document.createElement('div');
  eraRow.className = 'globe-era-row';
  eraRow.innerHTML = ERA_LABELS.map(l => '<span>' + l + '</span>').join('');

  const counter = document.createElement('p');
  counter.className = 'globe-counter';

  const legend = document.createElement('div');
  legend.className = 'constellation-legend';
  legend.innerHTML = Object.keys(CAT_LABELS).map(c =>
    '<span class="cx-legend-item"><span class="cx-legend-dot" style="background:var(--c-' + c + '-2)"></span>' + CAT_LABELS[c] + '</span>'
  ).join('');

  const hudTop = document.createElement('div');
  hudTop.className = 'globe-hud-top';
  hudTop.append(title, subtitle);

  const hudBottom = document.createElement('div');
  hudBottom.className = 'globe-hud-bottom';
  hudBottom.append(chip, slider, eraRow, counter, legend);

  const zoomCtl = document.createElement('div');
  zoomCtl.className = 'globe-zoom-ctl';
  const zoomInBtn = document.createElement('button');
  zoomInBtn.type = 'button';
  zoomInBtn.textContent = '+';
  zoomInBtn.setAttribute('aria-label', 'Perbesar');
  const zoomOutBtn = document.createElement('button');
  zoomOutBtn.type = 'button';
  zoomOutBtn.textContent = '−';
  zoomOutBtn.setAttribute('aria-label', 'Perkecil');
  zoomCtl.append(zoomInBtn, zoomOutBtn);

  root.append(stage, hudTop, hudBottom, zoomCtl);

  /* ---------- three.js setup ---------- */
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.setSize(window.innerWidth, window.innerHeight);
  let markerBoost = 1; // kompensasi ukuran marker saat kamera menjauh (layar sempit)
  stage.insertBefore(renderer.domElement, popupEl);

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(32, 1, 0.1, 10);
  camera.position.set(0, 0, 3.05);

  const group = new THREE.Group();
  // rotasi awal menghadap Mediterania (lng ~20BT) — pusat dunia kuno,
  // tempat hampir semua pemikir di tahun default -400 berada
  group.rotation.y = -1.92;
  scene.add(group);

  const sphereGeo = new THREE.SphereGeometry(1, 64, 48);
  const sphereMat = new THREE.MeshBasicMaterial({ color: 0xffffff });
  const sphereMesh = new THREE.Mesh(sphereGeo, sphereMat);
  group.add(sphereMesh);

  let mapTexture = null;
  const texLoader = new THREE.TextureLoader();
  texLoader.load(
    './assets/antique-map.jpg',
    (tex) => { mapTexture = tex; sphereMat.map = tex; sphereMat.needsUpdate = true; },
    undefined,
    (err) => {
      sphereMat.color.setHex(0xE8DCC0);
      sphereMat.needsUpdate = true;
      console.warn('[globe] gagal memuat tekstur peta, pakai warna fallback', err);
    }
  );

  /* ---------- markers ---------- */
  const names = Object.keys(geo).filter(n => geo[n]);
  const groups = new Map();
  names.forEach((name) => {
    const g = geo[name];
    const key = g.lat.toFixed(1) + ',' + g.lng.toFixed(1);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(name);
  });

  const markers = [];
  groups.forEach((arr, key) => {
    const groupHash = (hashStr(key) % 1000) / 1000 * Math.PI * 2;
    arr.forEach((name, i) => {
      const g = geo[name];
      let lat = g.lat, lng = g.lng;
      if (i > 0) {
        const angle = 2 * Math.PI * i / 6 + groupHash;
        lat = lat + 0.9 * Math.cos(angle);
        lng = lng + 0.9 * Math.sin(angle) / Math.cos(lat * Math.PI / 180);
      }
      const cat = catOf && catOf[name];
      const info = AUTHORS[name] || {};
      markers.push({
        name, lat, lng,
        born: g.born, died: g.died,
        baseDir: latLngToVec3(lat, lng, 1),
        color: (cat && CAT_COLORS[cat] != null) ? CAT_COLORS[cat] : FALLBACK_COLOR,
        photo: info.photo || null,
        currentScale: 0, targetScale: 0,
        el: null, elVisible: false
      });
    });
  });

  /* ---------- foto marker (overlay HTML, mengikuti proyeksi 3D tiap frame) ---------- */
  const markerLayer = document.createElement('div');
  markerLayer.className = 'globe-marker-layer';
  markers.forEach((m) => {
    const colorHex = '#' + m.color.toString(16).padStart(6, '0');
    const pin = document.createElement('div');
    pin.className = 'globe-marker-pin';
    pin.style.borderColor = colorHex;
    const fallback = document.createElement('span');
    fallback.className = 'globe-marker-fallback';
    fallback.style.background = colorHex;
    fallback.textContent = m.name[0];
    pin.appendChild(fallback);
    if (m.photo) {
      const img = document.createElement('img');
      img.loading = 'lazy';
      img.decoding = 'async';
      img.alt = '';
      img.src = m.photo;
      img.onerror = () => { img.style.display = 'none'; };
      pin.appendChild(img);
    }
    markerLayer.appendChild(pin);
    m.el = pin;
  });
  stage.insertBefore(markerLayer, popupEl);

  const markerGeo = new THREE.SphereGeometry(0.014, 12, 12);
  const markerMat = new THREE.MeshBasicMaterial();
  const instMesh = new THREE.InstancedMesh(markerGeo, markerMat, markers.length);
  instMesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
  const tmpColor = new THREE.Color();
  markers.forEach((m, i) => {
    tmpColor.setHex(m.color);
    instMesh.setColorAt(i, tmpColor);
  });
  if (instMesh.instanceColor) instMesh.instanceColor.needsUpdate = true;
  group.add(instMesh);

  /* ---------- state ---------- */
  let year = YEAR_DEFAULT;
  let dragging = false;
  let lastX = 0, lastY = 0, downX = 0, downY = 0, totalMove = 0;
  let velY = 0;
  let zoom = 1;
  const pointers = new Map(); // pointerId -> {x,y}; utk deteksi cubit dua jari
  let pinching = false, pinchDist = 0, pinchZoom0 = 1;
  const HOME_TILT = 0.32; // condong ke utara: mayoritas pemikir di belahan utara
  let tiltX = HOME_TILT;
  let popupMarker = null;
  let rafId = null;
  let destroyed = false;

  const tmpMatrix = new THREE.Matrix4();
  const tmpPos = new THREE.Vector3();
  const tmpScale = new THREE.Vector3();
  const IDENTITY_Q = new THREE.Quaternion();
  const tmpNormal = new THREE.Vector3();
  const tmpWorld = new THREE.Vector3();
  const tmpQuat = new THREE.Quaternion();
  const tmpEuler = new THREE.Euler();

  function updateCounter() {
    const n = markers.reduce((acc, m) => acc + ((m.born <= year && year <= m.died) ? 1 : 0), 0);
    counter.textContent = n + ' pemikir hidup pada tahun ini';
  }

  function setYear(y) {
    year = Math.max(YEAR_MIN, Math.min(YEAR_MAX, y));
    chip.textContent = formatYear(year);
    markers.forEach((m) => { m.targetScale = (m.born <= year && year <= m.died) ? 1 : 0; });
    if (popupMarker && popupMarker.targetScale === 0) closePopup();
    updateCounter();
  }

  function onSliderInput() { setYear(parseInt(slider.value, 10)); }
  slider.addEventListener('input', onSliderInput);

  /* ---------- rotation / drag ---------- */
  function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }

  function onPointerDown(e) {
    // tap di kartu popup (mis. "Lihat Profil") jangan dianggap gestur drag/tap globe —
    // biarkan event click native pada popupEl yang menangani navigasi
    if (popupEl.contains(e.target)) return;
    pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
    try { stage.setPointerCapture(e.pointerId); } catch (err) { /* ignore */ }
    if (pointers.size === 2) {
      // jari kedua turun → beralih dari drag ke cubit-zoom
      const [a, b] = [...pointers.values()];
      pinchDist = Math.hypot(a.x - b.x, a.y - b.y);
      pinchZoom0 = zoom;
      pinching = true;
      dragging = false;
      stage.classList.remove('dragging');
      return;
    }
    dragging = true;
    totalMove = 0;
    lastX = downX = e.clientX;
    lastY = downY = e.clientY;
    velY = 0;
    stage.classList.add('dragging');
  }
  function onPointerMove(e) {
    const pt = pointers.get(e.pointerId);
    if (pt) { pt.x = e.clientX; pt.y = e.clientY; }
    if (pinching) {
      if (pointers.size === 2 && pinchDist > 0) {
        const [a, b] = [...pointers.values()];
        setZoom(pinchZoom0 * Math.hypot(a.x - b.x, a.y - b.y) / pinchDist);
      }
      return;
    }
    if (!dragging) return;
    const dx = e.clientX - lastX, dy = e.clientY - lastY;
    lastX = e.clientX; lastY = e.clientY;
    totalMove += Math.abs(dx) + Math.abs(dy);
    group.rotation.y += dx * ROTATE_SENS / zoom;
    velY = dx * ROTATE_SENS / zoom;
    // saat zoom, izinkan kemiringan lebih jauh supaya lintang tinggi (mis. Eropa Utara)
    // bisa ditempatkan di tengah layar
    const tiltMax = zoom > 1.05 ? 1.3 : TILT_CLAMP;
    tiltX = clamp(tiltX + dy * TILT_SENS / zoom, -tiltMax, tiltMax);
  }
  function onPointerUp(e) {
    pointers.delete(e.pointerId);
    if (pinching) {
      if (pointers.size < 2) pinching = false;
      return;
    }
    if (!dragging) return;
    dragging = false;
    stage.classList.remove('dragging');
    const moved = Math.abs(e.clientX - downX) + Math.abs(e.clientY - downY);
    if (moved < TAP_MAX_MOVE) handleTap(e);
  }

  function setZoom(z) {
    zoom = clamp(z, ZOOM_MIN, ZOOM_MAX);
    fitCamera();
  }
  function onWheel(e) {
    e.preventDefault();
    setZoom(zoom * Math.exp(-e.deltaY * 0.0016));
  }
  function onDblClick(e) {
    if (popupEl.contains(e.target)) return;
    setZoom(zoom > 1.05 ? 1 : 2.2);
  }
  stage.addEventListener('wheel', onWheel, { passive: false });
  stage.addEventListener('dblclick', onDblClick);
  function onZoomIn() { setZoom(zoom * 1.4); }
  function onZoomOut() { setZoom(zoom / 1.4); }
  zoomInBtn.addEventListener('click', onZoomIn);
  zoomOutBtn.addEventListener('click', onZoomOut);

  stage.addEventListener('pointerdown', onPointerDown);
  stage.addEventListener('pointermove', onPointerMove);
  window.addEventListener('pointerup', onPointerUp);
  window.addEventListener('pointercancel', onPointerUp);

  /* ---------- popup / tap ---------- */
  function projectMarker(m, q, rect) {
    tmpNormal.copy(m.baseDir).applyQuaternion(q);
    if (tmpNormal.z <= HORIZON_DOT) return null;
    const r = MARKER_R_HIDDEN + (MARKER_R_SHOWN - MARKER_R_HIDDEN) * m.currentScale;
    tmpWorld.copy(m.baseDir).multiplyScalar(r).applyQuaternion(q);
    tmpWorld.project(camera);
    return {
      x: (tmpWorld.x * 0.5 + 0.5) * rect.width,
      y: (-tmpWorld.y * 0.5 + 0.5) * rect.height
    };
  }

  function handleTap(e) {
    const rect = renderer.domElement.getBoundingClientRect();
    const px = e.clientX - rect.left, py = e.clientY - rect.top;
    const ndc = new THREE.Vector2((px / rect.width) * 2 - 1, -(py / rect.height) * 2 + 1);
    const raycaster = new THREE.Raycaster();
    raycaster.setFromCamera(ndc, camera);
    const hits = raycaster.intersectObject(sphereMesh);
    if (!hits.length) { closePopup(); return; }

    tmpEuler.copy(group.rotation);
    tmpQuat.setFromEuler(tmpEuler);
    let best = null, bestDist = TAP_HIT_PX;
    markers.forEach((m) => {
      if (m.currentScale < 0.4) return;
      const p = projectMarker(m, tmpQuat, rect);
      if (!p) return;
      const d = Math.hypot(p.x - px, p.y - py);
      if (d < bestDist) { bestDist = d; best = m; }
    });
    if (best) openPopup(best); else closePopup();
  }

  let closeTimer = null;

  function openPopup(m) {
    if (closeTimer) { clearTimeout(closeTimer); closeTimer = null; }
    popupMarker = m;
    const info = AUTHORS[m.name] || {};
    const g = geo[m.name] || {};
    const metaBits = [info.years, [g.place, g.country].filter(Boolean).join(', ')].filter(Boolean);
    const colorHex = '#' + m.color.toString(16).padStart(6, '0');
    const avatarInner = info.photo
      ? '<img src="' + escHTML(info.photo) + '" alt="' + escHTML(m.name) + '" loading="lazy" style="border-color:' + colorHex + '">'
      : '<span class="globe-popup-fallback" style="background:' + colorHex + ';border-color:' + colorHex + '">' + escHTML(m.name[0]) + '</span>';
    popupEl.innerHTML =
      '<div class="gp-card">' +
        '<div class="gp-head">' + avatarInner +
          '<div class="gp-headtext"><div class="gp-name">' + escHTML(m.name) + '</div>' +
          '<div class="gp-meta">' + escHTML(metaBits.join(' · ')) + '</div>' +
          '</div></div>' +
        '<div class="gp-footer">Lihat Profil &rarr;</div>' +
        '<span class="gp-hairline gp-hairline-1"></span>' +
        '<span class="gp-hairline gp-hairline-2"></span>' +
      '</div>';
    const tiltDeg = (Math.random() * 6 - 3).toFixed(2);
    popupEl.style.setProperty('--gp-tilt', tiltDeg + 'deg');
    popupEl.hidden = false;
    popupEl.style.display = '';
    popupEl.onclick = () => { if (typeof onNavigate === 'function') onNavigate(m.name); };
  }
  function closePopup() {
    if (!popupMarker) return;
    popupMarker = null;
    const cardEl = popupEl.querySelector('.gp-card');
    if (!cardEl) { popupEl.hidden = true; return; }
    cardEl.classList.add('gp-exit');
    closeTimer = setTimeout(() => { popupEl.hidden = true; closeTimer = null; }, 160);
  }

  /* ---------- resize / fit fullscreen ---------- */
  function fitCamera() {
    const w = stage.clientWidth || window.innerWidth;
    const h = stage.clientHeight || window.innerHeight;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    // jarak kamera dihitung agar globe mengisi ~90% sisi tersempit viewport
    const vHalf = (32 / 2) * Math.PI / 180;
    const hHalf = Math.atan(Math.tan(vHalf) * camera.aspect);
    const limit = Math.min(vHalf, hHalf);
    // zoom mendekatkan kamera ke permukaan (radius 1), bukan sekadar memotong jarak total,
    // supaya 3x zoom terasa proporsional dan tidak menembus bola
    const baseZ = 1 / Math.sin(limit * 0.86);
    camera.position.z = 1 + (baseZ - 1) / zoom;
    camera.setViewOffset(w, h, 0, Math.round(h * 0.04), w, h); // globe sedikit naik, memberi ruang HUD bawah
    camera.updateProjectionMatrix();
    markerBoost = Math.max(1, camera.position.z / 3.4);
    markers.forEach((m, i) => {
      const r = MARKER_R_HIDDEN + (MARKER_R_SHOWN - MARKER_R_HIDDEN) * m.currentScale;
      tmpPos.copy(m.baseDir).multiplyScalar(r);
      const s = m.currentScale * markerBoost;
      tmpScale.set(s, s, s);
      tmpMatrix.compose(tmpPos, IDENTITY_Q, tmpScale);
      instMesh.setMatrixAt(i, tmpMatrix);
    });
    instMesh.instanceMatrix.needsUpdate = true;
  }
  function onResize() { fitCamera(); }
  window.addEventListener('resize', onResize);
  fitCamera();

  /* ---------- animation loop ---------- */
  const clock = new THREE.Clock();

  function updateRotation(dt) {
    if (!dragging) {
      if (!popupMarker) {
        if (Math.abs(velY) > 0.0002) {
          group.rotation.y += velY;
          velY *= INERTIA_DAMP;
        } else {
          velY = 0;
          group.rotation.y += AUTO_ROTATE_SPEED * dt / zoom;
        }
      }
      // ease-back kemiringan hanya saat tidak zoom — saat zoom, kemiringan pilihan
      // pengguna dipertahankan agar area yang sedang diamati tidak "lari" sendiri
      if (zoom <= 1.05) tiltX += (HOME_TILT - tiltX) * 0.05;
    }
    group.rotation.x = tiltX;
  }

  function updateMarkers(snap) {
    let dirty = snap;
    markers.forEach((m, i) => {
      if (snap || reducedMotion) {
        if (m.currentScale !== m.targetScale) dirty = true;
        m.currentScale = m.targetScale;
      } else if (Math.abs(m.currentScale - m.targetScale) > 0.001) {
        m.currentScale += (m.targetScale - m.currentScale) * SCALE_LERP;
        dirty = true;
      } else if (m.currentScale !== m.targetScale) {
        m.currentScale = m.targetScale;
        dirty = true;
      }
      if (!dirty) return;
      const r = MARKER_R_HIDDEN + (MARKER_R_SHOWN - MARKER_R_HIDDEN) * m.currentScale;
      tmpPos.copy(m.baseDir).multiplyScalar(r);
      tmpScale.set(m.currentScale * markerBoost, m.currentScale * markerBoost, m.currentScale * markerBoost);
      tmpMatrix.compose(tmpPos, IDENTITY_Q, tmpScale);
      instMesh.setMatrixAt(i, tmpMatrix);
    });
    if (dirty) instMesh.instanceMatrix.needsUpdate = true;
    return dirty;
  }
  updateMarkers(true); // posisi awal langsung tanpa animasi masuk

  function updatePopup(rect, quat) {
    if (!popupMarker) return;
    const p = projectMarker(popupMarker, quat, rect);
    if (!p) { popupEl.style.display = 'none'; return; }
    popupEl.style.display = '';
    popupEl.style.left = p.x + 'px';
    popupEl.style.top = p.y + 'px';
  }

  function updateMarkerDom(rect, quat) {
    // pin ikut membesar saat zoom (parsial, bukan linier) agar detail foto terlihat
    // tanpa membuat klaster padat saling tumpuk berlebihan
    const pinScale = 1 + (zoom - 1) * 0.35;
    markers.forEach((m) => {
      if (m.currentScale < 0.05) {
        if (m.elVisible) { m.el.style.display = 'none'; m.elVisible = false; }
        return;
      }
      const p = projectMarker(m, quat, rect);
      if (!p) {
        if (m.elVisible) { m.el.style.display = 'none'; m.elVisible = false; }
        return;
      }
      // 'block' eksplisit — CSS class-nya default display:none, jadi '' (hapus inline
      // style) akan jatuh balik ke none dan pin tak pernah tampil
      if (!m.elVisible) { m.el.style.display = 'block'; m.elVisible = true; }
      m.el.style.transform =
        'translate3d(' + p.x.toFixed(1) + 'px,' + p.y.toFixed(1) + 'px,0) translate(-50%,-50%) scale(' + (m.currentScale * pinScale).toFixed(3) + ')';
    });
  }

  function animate() {
    if (destroyed) return;
    rafId = requestAnimationFrame(animate);
    const dt = Math.min(clock.getDelta(), 0.1);
    updateRotation(dt);
    updateMarkers(false);
    const rect = renderer.domElement.getBoundingClientRect();
    tmpEuler.copy(group.rotation);
    tmpQuat.setFromEuler(tmpEuler);
    updatePopup(rect, tmpQuat);
    updateMarkerDom(rect, tmpQuat);
    renderer.render(scene, camera);
  }

  setYear(YEAR_DEFAULT);
  rafId = requestAnimationFrame(animate);
  // remeasur ulang setelah 2 frame: mitigasi viewport height yg belum stabil saat cold-launch
  // (mis. iOS Safari toolbar yg baru menyusut / preview harness pd first paint)
  requestAnimationFrame(() => requestAnimationFrame(() => { if (!destroyed) onResize(); }));

  /* ---------- destroy ---------- */
  function destroy() {
    destroyed = true;
    if (rafId != null) cancelAnimationFrame(rafId);
    if (closeTimer != null) clearTimeout(closeTimer);
    slider.removeEventListener('input', onSliderInput);
    stage.removeEventListener('pointerdown', onPointerDown);
    stage.removeEventListener('pointermove', onPointerMove);
    stage.removeEventListener('wheel', onWheel);
    stage.removeEventListener('dblclick', onDblClick);
    zoomInBtn.removeEventListener('click', onZoomIn);
    zoomOutBtn.removeEventListener('click', onZoomOut);
    window.removeEventListener('pointerup', onPointerUp);
    window.removeEventListener('pointercancel', onPointerUp);
    window.removeEventListener('resize', onResize);
    sphereGeo.dispose();
    sphereMat.dispose();
    if (mapTexture) mapTexture.dispose();
    markerGeo.dispose();
    markerMat.dispose();
    instMesh.dispose();
    renderer.dispose();
    root.innerHTML = '';
    root.classList.remove('globe-root');
  }

  return { destroy };
}
