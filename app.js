/* ============ Pustaka — app.js ============ */
'use strict';

const WPM = 200; // kecepatan baca rata-rata utk estimasi
const LS_SETTINGS = 'pustaka.settings';
const LS_PROGRESS = 'pustaka.progress';
const FLIP_MS = 560; // durasi flip penuh 180° (selaras default turn.js 600ms)

const CAT_LABELS = {
  filsafat: 'Filsafat', politik: 'Politik', sejarah: 'Sejarah',
  ekonomi: 'Ekonomi', sosial: 'Sosial'
};

let INDEX = [];               // books/index.json
let AUTHORS = {};              // books/authors.json
const BOOK_CACHE = {};        // id -> book json
let currentBook = null;       // buku yg sedang dibaca
let currentChapter = 0;
let activeCategory = 'semua';
let groupMode = 'genre';       // 'genre' | 'author'
let activeAuthor = null;       // author string ketika drill-down dari daftar penulis
let searchQuery = '';
let currentGlobe = null;       // instance globe 3D #/konstelasi (dari globe.js), utk cleanup di routerDispatch
let hasInAppNav = false;       // true setelah navigasi hash pertama in-app; deep-link murni = false

const AVATAR_COLORS = ['#9a5b2e','#6b5fa8','#a8455a','#4f8a5c','#47899a','#b98a3e','#7a4b6d'];
function avatarColor(name) { return AVATAR_COLORS[hashCode(name) % AVATAR_COLORS.length]; }

/* ---------- util ---------- */
const $ = (sel) => document.querySelector(sel);

function loadJSONLS(key, fallback) {
  try { return JSON.parse(localStorage.getItem(key)) || fallback; }
  catch (e) { return fallback; }
}
function saveJSONLS(key, val) {
  try { localStorage.setItem(key, JSON.stringify(val)); } catch (e) { /* penuh/blokir: abaikan */ }
}
function getSettings() {
  const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
  return Object.assign({ fontSize: 18, theme: prefersDark ? 'gelap' : 'sepia' }, loadJSONLS(LS_SETTINGS, {}));
}
function setSettings(patch) {
  const s = Object.assign(getSettings(), patch);
  saveJSONLS(LS_SETTINGS, s);
  applySettings(true);
}
function getProgress() { return loadJSONLS(LS_PROGRESS, {}); }
function setBookProgress(bookId, ch, ratio) {
  const p = getProgress();
  p[bookId] = { ch, ratio: Math.max(0, Math.min(1, ratio)), updated: new Date().toISOString() };
  saveJSONLS(LS_PROGRESS, p);
}
function bookPercent(meta) {
  const p = getProgress()[meta.id];
  if (!p) return 0;
  const n = meta.chapterCount || 1;
  return Math.min(100, Math.round(((p.ch + p.ratio) / n) * 100));
}
function estMinutes(words) {
  const m = Math.round(words / WPM);
  if (m < 60) return '± ' + m + ' mnt';
  return '± ' + Math.floor(m / 60) + ' j ' + (m % 60) + ' mnt';
}
function hashCode(str) {
  let h = 0;
  for (let i = 0; i < str.length; i++) { h = ((h << 5) - h + str.charCodeAt(i)) | 0; }
  return Math.abs(h);
}

/* sampul buku: gradien per kategori dgn sudut bervariasi + monogram */
/* potret penulis (lokal) sebagai seni cover, jika ada */
function bookPortrait(meta) {
  const info = AUTHORS[meta.author];
  return (info && info.photo && info.photo.indexOf('assets/') === 0) ? info.photo : null;
}

function coverHTML(meta, vt) {
  const vtStyle = vt ? 'view-transition-name:book-cover;' : '';
  const portrait = bookPortrait(meta);
  if (portrait) {
    // cover potret + pita judul (seragam se-katalog)
    return (
      '<div class="cover portrait cat-' + meta.category + '" style="' + vtStyle + '">' +
        '<div class="cv-img" style="background-image:url(' + encodeURI(portrait) + ')"></div>' +
        '<div class="cv-band">' +
          '<div class="cv-band-title">' + escHTML(meta.title) + '</div>' +
          '<div class="cv-band-author">' + escHTML(meta.author) + '</div>' +
        '</div>' +
        '%%PROGRESS%%' +
      '</div>'
    );
  }
  // fallback gradien (jika potret tak tersedia)
  const angle = 130 + (hashCode(meta.id) % 55);
  return (
    '<div class="cover cat-' + meta.category + '" style="' + vtStyle + 'background:linear-gradient(' +
      angle + 'deg, var(--c-' + meta.category + '-1), var(--c-' + meta.category + '-2))">' +
      '<div class="cv-cat">' + CAT_LABELS[meta.category] + '</div>' +
      '<div class="cv-title">' + escHTML(meta.title) + '</div>' +
      '<div class="cv-rule"></div>' +
      '<div class="cv-author">' + escHTML(meta.author) + '</div>' +
      '<div class="cv-mark">' + escHTML(meta.title[0]) + '</div>' +
      '%%PROGRESS%%' +
    '</div>'
  );
}

/* ---------- routing ---------- */
const REDUCE_MOTION = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
// document.hidden: browser membatalkan view transition di tab tersembunyi
// (InvalidStateError) — navigasi dari background langsung tanpa transisi saja
function supportsVT() { return !!document.startViewTransition && !REDUCE_MOTION && !document.hidden; }

// depth per route → menentukan arah transisi
function routeDepth(hash) {
  const p = (hash || '#/').replace(/^#\//, '').split('/')[0];
  if (p === 'baca' || p === 'dengar') return 3;
  if (p === 'buku' || p === 'penulis' || p === 'konstelasi') return 2;
  return 1; // library
}
let lastDepth = 1;
let firstRoute = true;

// bungkus body dispatch router dalam VT + set arah
function runRouterVT(dispatch) {
  const newDepth = routeDepth(location.hash);
  const dir = newDepth >= lastDepth ? 'forward' : 'back';
  lastDepth = newDepth;
  if (firstRoute || !supportsVT()) { firstRoute = false; dispatch(); return; }
  document.documentElement.dataset.vt = dir;         // dipakai CSS
  const t = document.startViewTransition(dispatch);
  t.finished.finally(() => { delete document.documentElement.dataset.vt; });
}

/* ---------- Mode embed: lapor sesi baca ke aplikasi induk (mis. Reclaim) ----------
   Aktif hanya via ?embed=1 → tak memengaruhi pengguna web biasa. Mengirim DELTA
   (detik + halaman sejak laporan terakhir) via postMessage; induk mengakumulasi. */
const EMBED_MODE = /[?&]embed=1\b/.test(location.search);
const readSess = { tickStart: 0, pagesPending: 0, hb: null };

function readerIsActive() {
  return EMBED_MODE && !$('#view-reader').hidden && !!currentBook &&
    document.visibilityState === 'visible';
}
function emitReading(secondsDelta) {
  if (!EMBED_MODE) return;
  const pages = readSess.pagesPending; readSess.pagesPending = 0;
  const secs = Math.round(secondsDelta);
  if (secs < 1 && pages === 0) return;
  try {
    window.parent.postMessage({
      source: 'pustaka', type: 'reading',
      secondsDelta: secs, pagesDelta: pages,
      bookId: currentBook ? currentBook.meta.id : null,
      bookTitle: currentBook ? currentBook.meta.title : null
    }, '*');
  } catch (e) { /* bukan iframe / diblok: abaikan */ }
}
function flushReading() {
  if (readSess.tickStart) {
    const dt = (performance.now() - readSess.tickStart) / 1000;
    readSess.tickStart = 0;
    emitReading(dt);
  }
}
function syncReadTick() {
  if (!EMBED_MODE) return;
  const active = readerIsActive();
  if (active && !readSess.tickStart) {
    readSess.tickStart = performance.now();
    if (!readSess.hb) {
      readSess.hb = setInterval(() => {           // heartbeat 30 dtk: flush parsial
        if (readSess.tickStart) {
          const dt = (performance.now() - readSess.tickStart) / 1000;
          readSess.tickStart = performance.now();
          emitReading(dt);
        }
      }, 30000);
    }
  } else if (!active && readSess.tickStart) {
    flushReading();
    if (readSess.hb) { clearInterval(readSess.hb); readSess.hb = null; }
  }
}
if (EMBED_MODE) {
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden') flushReading();
    syncReadTick();
  });
  window.addEventListener('pagehide', flushReading);
}

function router() {
  runRouterVT(() => routerDispatch());
}

function routerDispatch() {
  if (currentGlobe) {
    currentGlobe.destroy();
    currentGlobe = null;
    $('#view-constellation').classList.remove('globe-mode');
  }
  const h = location.hash || '#/';
  const parts = h.replace(/^#\//, '').split('/');
  $('#view-library').hidden = true;
  $('#view-detail').hidden = true;
  $('#view-reader').hidden = true;
  $('#view-listen').hidden = true;
  $('#view-author').hidden = true;
  $('#view-constellation').hidden = true;
  if (parts[0] !== 'dengar') stopListening();
  document.body.style.overflow = '';

  if (parts[0] === 'buku' && parts[1]) {
    renderDetail(parts[1]);
  } else if (parts[0] === 'penulis' && parts[1]) {
    renderAuthorProfile(decodeURIComponent(parts[1]));
  } else if (parts[0] === 'konstelasi') {
    renderConstellationMap();
  } else if (parts[0] === 'baca' && parts[1]) {
    openReader(parts[1], parseInt(parts[2] || '0', 10) || 0);
  } else if (parts[0] === 'dengar' && parts[1]) {
    openListen(parts[1], parseInt(parts[2] || '0', 10) || 0);
  } else {
    currentBook = null;
    renderLibrary();
  }
  syncReadTick(); // mulai/hentikan pelacakan sesi baca (mode embed)
}

/* ---------- perpustakaan ---------- */
function renderLibrary() {
  $('#view-library').hidden = false;
  window.scrollTo(0, 0);
  document.querySelectorAll('.cover[style*="view-transition-name"]').forEach(c => {
    c.style.viewTransitionName = '';
  });
  renderStats();
  renderContinueCard();
  renderChips();
  renderAuthorList();
  applyGroupMode();
  renderShelf();
}

function applyGroupMode() {
  $('#category-chips').hidden = groupMode !== 'genre';
  $('#author-list').hidden = groupMode !== 'author' || !!activeAuthor;
  $('#shelf').hidden = groupMode === 'author' && !activeAuthor;
  document.querySelectorAll('.gt-btn').forEach(b => b.classList.toggle('active', b.dataset.group === groupMode));
}

function matchesSearch(meta, q) {
  if (!q) return true;
  return meta.title.toLowerCase().includes(q) || meta.author.toLowerCase().includes(q);
}

function filteredBooks() {
  const q = searchQuery.trim().toLowerCase();
  return INDEX.filter(b => {
    if (!matchesSearch(b, q)) return false;
    if (groupMode === 'author') return activeAuthor ? b.author === activeAuthor : false;
    return activeCategory === 'semua' || b.category === activeCategory;
  });
}

function renderAuthorList() {
  const q = searchQuery.trim().toLowerCase();
  const byAuthor = {};
  INDEX.forEach(b => { (byAuthor[b.author] = byAuthor[b.author] || []).push(b); });
  let names = Object.keys(byAuthor).sort((a, b) => a.localeCompare(b));
  if (q) names = names.filter(n => n.toLowerCase().includes(q) || byAuthor[n].some(b => b.title.toLowerCase().includes(q)));

  if (activeAuthor && !names.includes(activeAuthor) && !q) names = Object.keys(byAuthor).sort((a, b) => a.localeCompare(b));

  if (!names.length) {
    $('#author-list').innerHTML = '<p class="author-search-empty">Tidak ada penulis yang cocok.</p>';
    return;
  }

  let curLetter = '';
  let html = '';
  names.forEach(name => {
    const letter = name[0].toUpperCase();
    if (letter !== curLetter) { html += '<div class="author-group-label">' + letter + '</div>'; curLetter = letter; }
    const info = AUTHORS[name];
    const books = byAuthor[name];
    html +=
      '<button class="author-row" data-author="' + escHTML(name) + '">' +
        '<div class="author-avatar" style="background:' + avatarColor(name) + '">' + escHTML(name[0]) + '</div>' +
        '<div class="author-row-info">' +
          '<div class="author-row-name">' + escHTML(name) + '</div>' +
          '<div class="author-row-sub">' + books.length + ' buku' + (info && info.years ? ' · ' + escHTML(info.years) : '') + '</div>' +
        '</div>' +
        '<div class="author-row-chev">&#8250;</div>' +
      '</button>';
  });
  $('#author-list').innerHTML = html;
  $('#author-list').querySelectorAll('.author-row').forEach(btn => {
    btn.onclick = () => {
      activeAuthor = btn.dataset.author;
      applyGroupMode();
      renderShelf();
      $('#shelf').scrollIntoView({ behavior: 'smooth', block: 'start' });
    };
  });
}

function renderStats() {
  let reading = 0, done = 0;
  for (const meta of INDEX) {
    const pct = bookPercent(meta);
    if (pct >= 100) done++;
    else if (pct > 0) reading++;
  }
  $('#lib-stats').innerHTML =
    '<span class="stat-chip">' + INDEX.length + ' buku</span>' +
    (reading ? '<span class="stat-chip">' + reading + ' sedang dibaca</span>' : '') +
    (done ? '<span class="stat-chip">' + done + ' selesai</span>' : '');
}

function renderContinueCard() {
  const card = $('#continue-card');
  const prog = getProgress();
  let best = null;
  for (const meta of INDEX) {
    const p = prog[meta.id];
    if (!p) continue;
    const pct = bookPercent(meta);
    if (pct >= 100) continue;
    if (!best || p.updated > prog[best.id].updated) best = meta;
  }
  if (!best) { card.hidden = true; return; }
  const pct = bookPercent(best);
  card.className = 'continue-card cat-' + best.category;
  card.innerHTML =
    '<div class="cc-spine">' + escHTML(best.title[0]) + '</div>' +
    '<div class="cc-info">' +
      '<div class="cc-kicker">Lanjutkan membaca</div>' +
      '<div class="cc-title">' + escHTML(best.title) + '</div>' +
      '<div class="cc-bar"><div style="width:' + pct + '%"></div></div>' +
      '<div class="cc-pct">' + pct + '% selesai</div>' +
    '</div><div class="cc-go">&#8594;</div>';
  card.onclick = () => {
    const p = getProgress()[best.id];
    location.hash = '#/baca/' + best.id + '/' + (p ? p.ch : 0);
  };
  card.hidden = false;
}

function authorContextHTML(name) {
  const info = AUTHORS[name] || {};
  const count = INDEX.filter(b => b.author === name).length;
  return (
    '<div class="shelf-back-wrap">' +
      '<button class="shelf-back" id="shelf-back-authors">&#8592; Semua Penulis</button>' +
      '<div class="author-card">' +
        '<div class="author-avatar" style="background:' + avatarColor(name) + '">' + escHTML(name[0]) + '</div>' +
        '<div class="author-card-body">' +
          '<div class="author-card-name">' + escHTML(name) + '</div>' +
          '<div class="author-card-meta">' + (info.years ? escHTML(info.years) : '') +
            (info.nationality ? ' · ' + escHTML(info.nationality) : '') + ' · ' + count + ' buku</div>' +
          '<div class="author-card-bio">' + escHTML(info.bio || '') + '</div>' +
          '<a class="author-card-more" href="#/penulis/' + slugAuthor(name) + '">Lihat Profil Lengkap &#8250;</a>' +
        '</div>' +
      '</div>' +
    '</div>'
  );
}

function renderChips() {
  const cats = ['semua'].concat(Object.keys(CAT_LABELS).filter(c => INDEX.some(b => b.category === c)));
  $('#category-chips').innerHTML = cats.map(c =>
    '<button class="chip' + (c === activeCategory ? ' active' : '') + '" data-cat="' + c + '">' +
    (c === 'semua' ? 'Semua' : CAT_LABELS[c]) + '</button>'
  ).join('');
  $('#category-chips').querySelectorAll('.chip').forEach(btn => {
    btn.onclick = () => { activeCategory = btn.dataset.cat; renderChips(); renderShelf(); };
  });
}

function renderShelf() {
  const list = filteredBooks();
  if (groupMode === 'author' && !activeAuthor) { $('#shelf').innerHTML = ''; return; }
  if (!list.length) {
    $('#shelf').innerHTML = '<p class="author-search-empty" style="grid-column:1/-1">Tidak ada buku yang cocok.</p>';
    return;
  }
  const backRow = (groupMode === 'author' && activeAuthor) ? authorContextHTML(activeAuthor) : '';
  $('#shelf').innerHTML = backRow + list.map(meta => {
    const pct = bookPercent(meta);
    const cover = coverHTML(meta).replace('%%PROGRESS%%',
      pct > 0 ? '<div class="cv-progress"><div style="width:' + pct + '%"></div></div>' : '');
    return (
      '<button class="book-card" data-id="' + meta.id + '">' + cover +
        '<div class="book-meta">' +
          '<p class="bm-title">' + escHTML(meta.title) + '</p>' +
          '<p class="bm-sub">' + estMinutes(meta.words) + (pct > 0 ? ' · ' + pct + '%' : '') + '</p>' +
        '</div>' +
      '</button>'
    );
  }).join('');
  $('#shelf').querySelectorAll('.book-card').forEach(btn => {
    btn.onclick = () => {
      const cov = btn.querySelector('.cover');
      if (cov) cov.style.viewTransitionName = 'book-cover';
      location.hash = '#/buku/' + btn.dataset.id;
    };
  });
  const backBtn = $('#shelf-back-authors');
  if (backBtn) backBtn.onclick = () => { activeAuthor = null; applyGroupMode(); renderShelf(); };
}

function authorCardHTML(name) {
  const info = AUTHORS[name];
  if (!info) return '';
  return (
    '<div class="author-card">' +
      '<div class="author-avatar" style="background:' + avatarColor(name) + '">' + escHTML(name[0]) + '</div>' +
      '<div class="author-card-body">' +
        '<div class="author-card-name">' + escHTML(name) + '</div>' +
        '<div class="author-card-meta">' + (info.years ? escHTML(info.years) : '') +
          (info.nationality ? ' · ' + escHTML(info.nationality) : '') + '</div>' +
        '<div class="author-card-bio">' + escHTML(info.bio || '') + '</div>' +
        '<a class="author-card-more" href="#/penulis/' + slugAuthor(name) + '">Lihat Profil Lengkap &#8250;</a>' +
      '</div>' +
    '</div>'
  );
}

/* ---------- profil penulis (interaktif) ---------- */
let authorTab = 'ringkasan';
const TAB_ORDER = ['ringkasan', 'kisah', 'pengaruh', 'karya'];

function switchAuthorTab(newTab, doSwap) {
  const dir = TAB_ORDER.indexOf(newTab) >= TAB_ORDER.indexOf(authorTab) ? 'tab-fwd' : 'tab-back';
  authorTab = newTab;
  if (!supportsVT()) { doSwap(); return; }
  document.documentElement.dataset.vt = dir;
  const t = document.startViewTransition(doSwap);
  t.finished.finally(() => { delete document.documentElement.dataset.vt; });
}

function slugAuthor(name) { return encodeURIComponent(name); }

function renderAuthorProfile(name) {
  const info = AUTHORS[name];
  $('#view-author').hidden = false;
  window.scrollTo(0, 0);
  authorTab = 'ringkasan';

  if (!info) {
    $('#author-body').innerHTML = '<p style="padding:20px">Data penulis tidak ditemukan.</p>';
    return;
  }
  const books = INDEX.filter(b => b.author === name);
  const heroInner = info.photo
    ? '<img src="' + escHTML(info.photo) + '" alt="' + escHTML(name) + '" loading="lazy">'
    : (() => {
        const angle = 130 + (hashCode(name) % 55);
        const cat = books[0] ? books[0].category : 'filsafat';
        return '<div class="author-hero-fallback" style="background:linear-gradient(' + angle +
          'deg, var(--c-' + cat + '-1), var(--c-' + cat + '-2))">' +
          '<span class="hf-letter">' + escHTML(name[0]) + '</span></div>';
      })();
  const photo =
    '<div class="author-hero">' + heroInner +
      '<div class="author-hero-overlay"></div><div class="author-hero-text">' +
      '<h1 class="author-hero-name">' + escHTML(name) + '</h1>' +
      '<p class="author-hero-meta">' + (info.years ? escHTML(info.years) : '') +
      (info.nationality ? ' · ' + escHTML(info.nationality) : '') + '</p></div></div>';

  const hasLifeStory = info.lifeStory && info.lifeStory.length;
  const tabs = [
    ['ringkasan', 'Ringkasan'],
    hasLifeStory ? ['kisah', 'Kisah Hidup'] : null,
    ((info.connections && info.connections.length) || info.influencedBy || info.influenced) ? ['pengaruh', 'Koneksi'] : null,
    ['karya', 'Karya (' + books.length + ')']
  ].filter(Boolean);

  $('#author-body').innerHTML =
    photo +
    '<nav class="author-tabs" id="author-tabs">' +
      tabs.map(t => '<button class="at-btn' + (t[0] === authorTab ? ' active' : '') + '" data-tab="' + t[0] + '">' + t[1] + '</button>').join('') +
    '</nav>' +
    '<div class="author-panel" id="author-panel"></div>';

  $('#author-tabs').querySelectorAll('.at-btn').forEach(btn => {
    btn.onclick = () => {
      switchAuthorTab(btn.dataset.tab, () => {
        $('#author-tabs').querySelectorAll('.at-btn').forEach(b => b.classList.toggle('active', b === btn));
        renderAuthorPanel(name, info, books);
      });
    };
  });

  renderAuthorPanel(name, info, books);
}

function renderAuthorPanel(name, info, books) {
  const panel = $('#author-panel');
  let inner = '';
  if (authorTab === 'kisah' && info.lifeStory) {
    inner = '<div class="life-timeline">' + info.lifeStory.map((step, i) =>
      '<div class="life-step" style="--i:' + i + '"><h3>' + escHTML(step.heading) + '</h3><p>' + escHTML(step.text) + '</p></div>'
    ).join('') + '</div>';
  } else if (authorTab === 'pengaruh') {
    inner = renderConstellationEgo(name, info, books);
  } else if (authorTab === 'karya') {
    if (!books.length) {
      inner = '<p class="influence-empty">Belum ada buku.</p>';
    } else {
      inner = '<div class="shelf">' + books.map((meta, i) => {
        const pct = bookPercent(meta);
        const cover = coverHTML(meta).replace('%%PROGRESS%%',
          pct > 0 ? '<div class="cv-progress"><div style="width:' + pct + '%"></div></div>' : '');
        return '<button class="book-card" data-id="' + meta.id + '" style="--ci:' + i + '">' + cover +
          '<div class="book-meta"><p class="bm-title">' + escHTML(meta.title) + '</p>' +
          '<p class="bm-sub">' + estMinutes(meta.words) + (pct > 0 ? ' · ' + pct + '%' : '') + '</p></div></button>';
      }).join('') + '</div>';
    }
  } else { // ringkasan
    inner =
      (info.quote ? '<div class="author-quote"><p>&#8220;' + escHTML(info.quote.text) + '&#8221;</p>' +
        '<cite>— ' + escHTML(info.quote.bookTitle || name) + '</cite></div>' : '') +
      '<div class="author-stat-row">' +
        '<span class="stat-pill">' + books.length + ' buku di Pustaka</span>' +
        (info.years ? '<span class="stat-pill">' + escHTML(info.years) + '</span>' : '') +
        (info.nationality ? '<span class="stat-pill">' + escHTML(info.nationality) + '</span>' : '') +
      '</div>' +
      '<p class="author-summary-bio">' + escHTML(info.bio || '') + '</p>';
  }

  panel.innerHTML = '<div class="panel-fade">' + inner + '</div>';
  panel.querySelectorAll('[data-goto]').forEach(btn => {
    btn.onclick = () => { location.hash = '#/penulis/' + slugAuthor(btn.dataset.goto); };
  });
  panel.querySelectorAll('.book-card').forEach(btn => {
    btn.onclick = () => {
      const cov = btn.querySelector('.cover');
      if (cov) cov.style.viewTransitionName = 'book-cover';
      location.hash = '#/buku/' + btn.dataset.id;
    };
  });

  if (authorTab === 'pengaruh') {
    panel.querySelectorAll('[data-conn-note]').forEach(el => {
      el.onclick = () => showToast(el.dataset.connNote);
    });
    panel.querySelectorAll('.cx-node[tabindex]').forEach(el => {
      el.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          if (el.dataset.goto) location.hash = '#/penulis/' + slugAuthor(el.dataset.goto);
          else if (el.dataset.connNote) showToast(el.dataset.connNote);
        }
      });
    });
    const egoScroll = panel.querySelector('.constellation-scroll');
    egoScroll.classList.add('cx-map-bg');
    initScrollReveal(egoScroll);
    bindDragPan(egoScroll);
  }
}

/* ---------- toast ---------- */
let toastTimer = null;
function showToast(msg) {
  const t = $('#toast');
  if (!t || !msg) return;
  t.textContent = msg;
  t.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { t.hidden = true; }, 2600);
}

/* ---------- Konstelasi Pengetahuan ---------- */

/* parser tahun bebas-teks → integer (SM = negatif). Lihat DESIGN_CONNECTIONS.md §3.2. */
function yearToNum(years) {
  if (!years || typeof years !== 'string') return null;
  const s = years.replace(/±/g, '').trim();

  // "abad ke-N" (century) — SM/M ditentukan dari keberadaan token "SM"
  const abadMatch = s.match(/abad\s+ke-?\s*(\d+)/i);
  if (abadMatch) {
    const n = parseInt(abadMatch[1], 10);
    const isSM = /\bSM\b/i.test(s);
    return isSM ? -(n * 100 - 50) : (n * 100 - 50);
  }

  // angka bermakna pertama (mulai/lahir); gagal total → null (node tetap dirender, tidak crash)
  const numMatch = s.match(/\d{1,4}/);
  if (!numMatch) return null;
  const n = parseInt(numMatch[0], 10);
  const isSM = /\bSM\b/i.test(s);
  return isSM ? -n : n;
}

function formatYearLabel(y) {
  if (y == null) return '?';
  return y < 0 ? (Math.abs(y) + ' SM') : String(y);
}

const CONN_TYPE_META = {
  guru:        { color: 'var(--rel-guru)',        label: 'Guru' },
  murid:       { color: 'var(--rel-murid)',       label: 'Murid' },
  pengaruh:    { color: 'var(--rel-pengaruh)',    label: 'Pengaruh' },
  sezaman:     { color: 'var(--rel-sezaman)',     label: 'Sezaman' },
  menentang:   { color: 'var(--rel-menentang)',   label: 'Menentang' },
  kolaborator: { color: 'var(--rel-kolaborator)', label: 'Kolaborator' }
};

/* alias ringan utk ejaan Indonesia → kunci katalog persis (fallback, tak perlu lengkap) */
const CONN_ALIASES = {
  'Aristoteles': 'Aristotle',
  'Thomas Malthus': 'Thomas Robert Malthus'
};

function connTypeFromHint(hint) {
  if (!hint) return null;
  const h = hint.toLowerCase();
  if (/\bguru(nya)?\b/.test(h) || /mengajar/.test(h)) return 'guru';
  if (/\bmurid(nya)?\b/.test(h)) return 'murid';
  if (/menentang|berbalik|berseteru|mengkritik|kritik/.test(h)) return 'menentang';
  if (/kolaborat|menulis bersama|rekan penulis/.test(h)) return 'kolaborator';
  return null;
}

function splitConnNames(base) {
  return base.split(/\s+dan\s+|\s*,\s*|\s+&\s+/).map(s => s.trim()).filter(Boolean);
}

/* bangun connections-shaped array dari influencedBy/influenced lama, dipakai bila
   info.connections belum ada/lengkap. Versi ringan dari DESIGN_CONNECTIONS.md §2.5. */
function deriveFromLegacy(info, selfName) {
  if (!info) return [];
  const out = [];
  const seen = new Set();
  const addFrom = (list) => {
    (list || []).forEach(raw => {
      const m = raw.match(/^(.*?)\s*\(([^)]*)\)\s*$/);
      const base = (m ? m[1] : raw).trim();
      const hint = m ? m[2].trim() : '';
      const type = connTypeFromHint(hint) || 'pengaruh';
      splitConnNames(base).forEach(rawName => {
        if (!rawName) return;
        const to = CONN_ALIASES[rawName] || rawName;
        if (selfName && to.toLowerCase() === selfName.toLowerCase()) return;
        const key = to + '|' + type;
        if (seen.has(key)) return;
        seen.add(key);
        out.push({ to, type, inCatalog: !!AUTHORS[to], note: hint || '' });
      });
    });
  };
  addFrom(info.influencedBy);
  addFrom(info.influenced);
  return out;
}

/* susun x per entitas sepanjang sumbu tahun + paksa jarak minimum antar node (beeswarm sederhana) */
function layoutTimeline(entities, opts) {
  opts = opts || {};
  const marginX = opts.marginX || 56;
  const minGap = opts.minGap || 92;
  const minWidth = opts.minWidth || 360;
  const years = entities.map(e => e.year).filter(y => y != null);
  const minY = years.length ? Math.min.apply(null, years) : 0;
  const maxY = years.length ? Math.max.apply(null, years) : 1;
  const span = Math.max(1, maxY - minY);
  let width = Math.max(minWidth, entities.length * minGap + marginX * 2);
  const scale = (y) => marginX + ((y - minY) / span) * (width - marginX * 2);

  const withX = entities.map(e => Object.assign({}, e, {
    x: e.year != null ? scale(e.year) : width - marginX
  }));
  const order = withX.slice().sort((a, b) => a.x - b.x);
  for (let i = 1; i < order.length; i++) {
    if (order[i].x - order[i - 1].x < minGap) order[i].x = order[i - 1].x + minGap;
  }
  const maxX = order.length ? order[order.length - 1].x + marginX : width;
  width = Math.max(width, maxX);
  return { width, nodes: withX, minYear: minY, maxYear: maxY };
}

function pickAxisStep(span) {
  const steps = [50, 100,200,250,500, 1000];
  for (let i = 0; i < steps.length; i++) { if (span / steps[i] <= 8) return steps[i]; }
  return 1000;
}

/* sumbu waktu bersama (garis + penanda abad) — dipakai ego-view & peta besar */
function buildAxisTicks(minY, maxY, width, axisY, marginX) {
  marginX = marginX || 56;
  const span = Math.max(1, maxY - minY);
  const scale = (y) => marginX + ((y - minY) / span) * (width - marginX * 2);
  const step = pickAxisStep(span);
  const start = Math.ceil(minY / step) * step;
  let ticks = '';
  for (let y = start; y <= maxY; y += step) {
    const x = scale(y);
    ticks +=
      '<line class="cx-axis-tick" x1="' + x.toFixed(1) + '" y1="' + (axisY - 6) + '" x2="' + x.toFixed(1) + '" y2="' + (axisY + 6) + '"></line>' +
      '<text class="cx-axis-label" x="' + x.toFixed(1) + '" y="' + (axisY + 20) + '" text-anchor="middle">' + escHTML(formatYearLabel(y)) + '</text>';
  }
  return '<line class="cx-axis-line" x1="' + marginX + '" y1="' + axisY + '" x2="' + (width - marginX) + '" y2="' + axisY + '"></line>' + ticks;
}

/* lajur anti-tumpuk utk ego-view: guru/lebih tua ke atas, murid/lebih muda ke bawah, sezaman dekat tengah */
function assignEgoLanes(nodes, centerY) {
  const above = [], below = [], mid = [];
  nodes.forEach(n => {
    if (n.type === 'sezaman') { mid.push(n); return; }
    if (n.type === 'murid') { below.push(n); return; }
    if (n.type === 'guru') { above.push(n); return; }
    if (n.year != null && n._centerYear != null) {
      (n.year <= n._centerYear ? above : below).push(n);
    } else mid.push(n);
  });
  const place = (arr, sign) => {
    arr.sort((a, b) => a.x - b.x);
    arr.forEach((n, i) => { n.y = centerY + sign * (44 + (i % 3) * 38); });
  };
  place(above, -1);
  place(below, 1);
  mid.forEach((n, i) => { n.y = centerY + (i % 2 === 0 ? -20 : 20); });
}

/* lajur anti-tumpuk utk peta besar: penempatan greedy per-x, tanpa makna semantik lajur */
function assignMapLanes(nodes, laneH, maxLanes, topPad) {
  const sorted = nodes.slice().sort((a, b) => a.x - b.x);
  const laneLastX = new Array(maxLanes).fill(-Infinity);
  const minGapSameLane = 64;
  sorted.forEach(n => {
    let lane = 0, bestGap = -Infinity;
    for (let l = 0; l < maxLanes; l++) {
      const gap = n.x - laneLastX[l];
      if (gap >= minGapSameLane) { lane = l; break; }
      if (gap > bestGap) { bestGap = gap; lane = l; }
    }
    laneLastX[lane] = n.x;
    n.lane = lane;
    n.y = topPad + lane * laneH;
  });
}

/* reveal bertahap saat scroll (scrollytelling ringan, §3.5b). Fallback: semua .revealed langsung
   bila IntersectionObserver tak tersedia atau prefers-reduced-motion aktif. */
function initScrollReveal(container) {
  if (!container) return;
  const nodes = container.querySelectorAll('.cx-node, .cx-edge, .cx-edge-label');
  if (REDUCE_MOTION || !('IntersectionObserver' in window)) {
    nodes.forEach(n => n.classList.add('revealed'));
    return;
  }
  try {
    const io = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('revealed');
          io.unobserve(entry.target);
        }
      });
    }, { root: container, threshold: 0.15 });
    nodes.forEach(n => io.observe(n));
  } catch (e) {
    nodes.forEach(n => n.classList.add('revealed'));
  }
}

/* ego-network kronologis: menggantikan isi tab "Koneksi" di profil penulis */
/* avatar node: foto asli (clip lingkaran) dgn fallback warna kategori + inisial */
let cxClipSeq = 0;
function nodeAvatarHTML(x, y, r, photoUrl, fallbackFill, initial) {
  const fx = x.toFixed(1), fy = y.toFixed(1);
  if (!photoUrl) {
    return '<circle cx="' + fx + '" cy="' + fy + '" r="' + r + '" fill="' + fallbackFill + '"></circle>' +
      (initial ? '<text class="cx-node-initial" x="' + fx + '" y="' + (y + r * 0.35).toFixed(1) + '" text-anchor="middle">' + escHTML(initial) + '</text>' : '');
  }
  const id = 'cxclip' + (cxClipSeq++);
  return (
    '<defs><clipPath id="' + id + '"><circle cx="' + fx + '" cy="' + fy + '" r="' + r + '"/></clipPath></defs>' +
    '<circle cx="' + fx + '" cy="' + fy + '" r="' + r + '" fill="' + fallbackFill + '"></circle>' +
    '<image class="cx-node-photo" href="' + escHTML(photoUrl) + '" x="' + (x - r).toFixed(1) + '" y="' + (y - r).toFixed(1) +
      '" width="' + (r * 2) + '" height="' + (r * 2) + '" clip-path="url(#' + id + ')" preserveAspectRatio="xMidYMid slice"></image>' +
    '<circle cx="' + fx + '" cy="' + fy + '" r="' + r + '" fill="none" class="cx-node-ring"></circle>'
  );
}

/* drag-to-pan: geser peta dgn mouse/jari, bukan scrollbar */
function bindDragPan(el) {
  if (!el || el.dataset.dragBound) return;
  el.dataset.dragBound = '1';
  let down = false, moved = false, startX = 0, startScroll = 0;
  el.addEventListener('pointerdown', (e) => {
    down = true; moved = false;
    startX = e.clientX; startScroll = el.scrollLeft;
    el.classList.add('dragging');
  });
  el.addEventListener('pointermove', (e) => {
    if (!down) return;
    const dx = e.clientX - startX;
    if (Math.abs(dx) > 4) moved = true;
    el.scrollLeft = startScroll - dx;
  });
  const end = (e) => {
    if (!down) return;
    down = false;
    el.classList.remove('dragging');
    if (moved) {
      const suppress = (ev) => { ev.stopPropagation(); el.removeEventListener('click', suppress, true); };
      el.addEventListener('click', suppress, true);
    }
  };
  el.addEventListener('pointerup', end);
  el.addEventListener('pointerleave', end);
  el.addEventListener('pointercancel', end);
}

function renderConstellationEgo(name, info, books) {
  const conns = (info.connections && info.connections.length) ? info.connections : deriveFromLegacy(info, name);
  if (!conns || !conns.length) {
    return '<p class="influence-empty">Belum ada data pengaruh untuk penulis ini.</p>';
  }

  const centerYear = yearToNum(info.years);
  const centerCat = books[0] ? books[0].category : null;

  const entities = conns.map(c => {
    const otherInfo = AUTHORS[c.to];
    const year = c.inCatalog && otherInfo ? yearToNum(otherInfo.years) : centerYear;
    const otherBook = c.inCatalog ? INDEX.find(b => b.author === c.to) : null;
    return {
      to: c.to, type: c.type || 'pengaruh', inCatalog: !!c.inCatalog, note: c.note || '',
      year, cat: otherBook ? otherBook.category : null
    };
  });

  const all = [{ isCenter: true, year: centerYear, cat: centerCat, to: name }].concat(entities);
  const { width, nodes } = layoutTimeline(all, { marginX: 56, minGap: 92, minWidth: 360 });
  const height = 360;
  const centerY = 180;
  const centerNode = nodes[0];
  const others = nodes.slice(1);
  others.forEach(n => { n._centerYear = centerYear; });
  assignEgoLanes(others, centerY);

  const typesPresent = Array.from(new Set(entities.map(e => e.type)));
  const legendHTML = '<div class="constellation-legend">' +
    typesPresent.map(t => {
      const meta = CONN_TYPE_META[t] || CONN_TYPE_META.pengaruh;
      return '<span class="cx-legend-item"><span class="cx-legend-dot" style="background:' + meta.color + '"></span>' + meta.label + '</span>';
    }).join('') + '</div>';

  const years = all.map(n => n.year).filter(y => y != null);
  const minY = years.length ? Math.min.apply(null, years) : 0;
  const maxY = years.length ? Math.max.apply(null, years) : 1;
  const axisHTML = buildAxisTicks(minY, maxY, width, height - 26);

  let edgesHTML = '';
  others.forEach(n => {
    const meta = CONN_TYPE_META[n.type] || CONN_TYPE_META.pengaruh;
    const midX = (centerNode.x + n.x) / 2;
    const solidCls = n.inCatalog ? ' cx-edge-solid' : ' cx-edge-dashed';
    const dash = n.inCatalog ? '' : ' stroke-dasharray="5 4"';
    const pathLen = n.inCatalog ? ' pathLength="1"' : '';
    edgesHTML +=
      '<path class="cx-edge' + solidCls + '" d="M ' + centerNode.x.toFixed(1) + ' ' + centerY.toFixed(1) +
      ' Q ' + midX.toFixed(1) + ' ' + centerY.toFixed(1) + ' ' + n.x.toFixed(1) + ' ' + n.y.toFixed(1) + '"' +
      ' stroke="' + meta.color + '" stroke-width="2" fill="none"' + dash + pathLen + '></path>';
    // notasi tipe relasi, ditulis langsung di garis (warna guru=murid identik,
    // jadi teks perlu, bukan sekadar warna). Digeser ke arah node (~t=0.62) agar
    // menyebar mengikuti lajur — guru ke atas, murid ke bawah — mengurangi tumpukan.
    const lblX = 0.4 * centerNode.x + 0.6 * n.x;
    const lblY = 0.6 * centerY + 0.4 * n.y;
    const lblW = meta.label.length * 6.2 + 14;
    edgesHTML +=
      '<g class="cx-edge-label" aria-hidden="true">' +
        '<rect x="' + (lblX - lblW / 2).toFixed(1) + '" y="' + (lblY - 8.5).toFixed(1) + '" width="' + lblW.toFixed(1) + '" height="17" rx="8.5" fill="var(--card)" stroke="' + meta.color + '"></rect>' +
        '<text x="' + lblX.toFixed(1) + '" y="' + (lblY + 3.4).toFixed(1) + '" text-anchor="middle" fill="' + meta.color + '">' + escHTML(meta.label) + '</text>' +
      '</g>';
  });

  let nodesHTML = '';
  others.forEach(n => {
    const r = 22;
    const fill = n.inCatalog && n.cat ? 'var(--c-' + n.cat + '-2)' : 'var(--line)';
    const photo = n.inCatalog && AUTHORS[n.to] ? AUTHORS[n.to].photo : null;
    const dimmed = n.inCatalog ? '' : ' cx-node-dim';
    const label = n.to.length > 14 ? n.to.slice(0, 13) + '…' : n.to;
    const yearLabel = n.year != null ? formatYearLabel(n.year) : '';
    const tmeta = CONN_TYPE_META[n.type] || CONN_TYPE_META.pengaruh;
    // teks penjelas: "Guru: Socrates" atau "Menentang: Wagner · awalnya kagum, lalu berbalik"
    const relText = tmeta.label + ': ' + n.to + (n.note ? ' · ' + n.note : '');
    const attrs = n.inCatalog
      ? ' data-goto="' + escHTML(n.to) + '"'
      : ' data-conn-note="' + escHTML(relText) + '"';
    nodesHTML +=
      '<g class="cx-node' + dimmed + '" tabindex="0" role="button" aria-label="' + escHTML(relText) + '"' + attrs + '>' +
        '<title>' + escHTML(relText) + '</title>' +
        '<rect class="cx-node-hit" x="' + (n.x - 46).toFixed(1) + '" y="' + (n.y - 28).toFixed(1) + '" width="92" height="80" fill="transparent"></rect>' +
        nodeAvatarHTML(n.x, n.y, r, photo, fill, n.to[0]) +
        '<text class="cx-node-label" x="' + n.x.toFixed(1) + '" y="' + (n.y + r + 13).toFixed(1) + '" text-anchor="middle">' + escHTML(label) + '</text>' +
        (yearLabel ? '<text class="cx-node-year" x="' + n.x.toFixed(1) + '" y="' + (n.y + r + 25).toFixed(1) + '" text-anchor="middle">' + escHTML(yearLabel) + '</text>' : '') +
      '</g>';
  });

  const centerLabel = name.length > 16 ? name.slice(0, 15) + '…' : name;
  const centerPhoto = info.photo || null;
  const centerHTML =
    '<g class="cx-node cx-node-center" aria-hidden="true">' +
      '<circle class="cx-center-ring" cx="' + centerNode.x.toFixed(1) + '" cy="' + centerY.toFixed(1) + '" r="34" fill="none"></circle>' +
      nodeAvatarHTML(centerNode.x, centerY, 30, centerPhoto, (centerCat ? 'var(--c-' + centerCat + '-2)' : 'var(--accent)'), name[0]) +
      '<text class="cx-node-label cx-node-label-center" x="' + centerNode.x.toFixed(1) + '" y="' + (centerY + 30 + 15).toFixed(1) + '" text-anchor="middle">' + escHTML(centerLabel) + '</text>' +
    '</g>';

  const svg =
    '<svg class="constellation-svg" viewBox="0 0 ' + width + ' ' + height + '" width="' + width + '" height="' + height + '" role="img">' +
      '<title>Konstelasi koneksi ' + escHTML(name) + '</title>' +
      '<desc>Peta koneksi intelektual ' + escHTML(name) + ' dengan ' + others.length + ' tokoh lain sepanjang garis waktu.</desc>' +
      axisHTML + edgesHTML + nodesHTML + centerHTML +
    '</svg>';

  return legendHTML + '<div class="constellation-scroll cx-map-bg">' + svg + '</div>';
}

/* #/konstelasi: globe 3D (globe.js) dgn fallback ke peta SVG datar jika gagal dimuat */
async function renderConstellationMap() {
  $('#view-constellation').hidden = false;
  $('#view-constellation').classList.add('globe-mode');
  document.body.style.overflow = 'hidden';
  window.scrollTo(0, 0);
  const body = $('#constellation-body');
  body.innerHTML = '<div id="globe-root">Memuat globe...</div>';
  try {
    const res = await fetch('books/geo.json');
    if (!res.ok) throw new Error('HTTP ' + res.status);
    const geo = await res.json();
    const catOf = {};
    INDEX.forEach(b => { if (!(b.author in catOf)) catOf[b.author] = b.category; });
    const mod = await import('./globe.js');
    const rootEl = $('#globe-root');
    currentGlobe = await mod.initGlobe(rootEl, {
      geo, AUTHORS, catOf,
      onNavigate: (n) => { location.hash = '#/penulis/' + encodeURIComponent(n); },
      reducedMotion: REDUCE_MOTION
    });
  } catch (e) {
    console.warn('globe fallback', e);
    $('#view-constellation').classList.remove('globe-mode');
    document.body.style.overflow = '';
    renderConstellationMapLegacy();
  }
}

/* peta besar #/konstelasi (fallback SVG): 115 pemikir pada satu sumbu waktu, tanpa edge global */
function renderConstellationMapLegacy() {
  $('#view-constellation').hidden = false;
  window.scrollTo(0, 0);
  const body = $('#constellation-body');

  const names = Object.keys(AUTHORS);
  const entities = names.map(name => {
    const info = AUTHORS[name];
    const year = yearToNum(info.years);
    const b = INDEX.find(bk => bk.author === name);
    return { to: name, year, cat: b ? b.category : null };
  });
  const { width, nodes } = layoutTimeline(entities, { marginX: 60, minGap: 46, minWidth: 700 });
  const laneH = 46, maxLanes = 8, topPad = 40;
  assignMapLanes(nodes, laneH, maxLanes, topPad);
  const height = topPad + maxLanes * laneH + 60;
  const axisY = height - 34;

  const years = nodes.map(n => n.year).filter(y => y != null);
  const minY = years.length ? Math.min.apply(null, years) : 0;
  const maxY = years.length ? Math.max.apply(null, years) : 1;
  const axisHTML = buildAxisTicks(minY, maxY, width, axisY, 60);

  let nodesHTML = '';
  nodes.forEach(n => {
    const r = 15;
    const fill = n.cat ? 'var(--c-' + n.cat + '-2)' : 'var(--ink-soft)';
    const photo = AUTHORS[n.to] ? AUTHORS[n.to].photo : null;
    const label = n.to.length > 12 ? n.to.slice(0, 11) + '…' : n.to;
    nodesHTML +=
      '<g class="cx-node cx-map-node" tabindex="0" role="button" aria-label="' + escHTML(n.to) + '" data-goto="' + escHTML(n.to) + '">' +
        '<title>' + escHTML(n.to + (n.year != null ? ' (' + formatYearLabel(n.year) + ')' : '')) + '</title>' +
        '<rect class="cx-node-hit" x="' + (n.x - 40).toFixed(1) + '" y="' + (n.y - 34).toFixed(1) + '" width="80" height="54" fill="transparent"></rect>' +
        nodeAvatarHTML(n.x, n.y, r, photo, fill, n.to[0]) +
        '<text class="cx-map-label" x="' + n.x.toFixed(1) + '" y="' + (n.y - r - 5).toFixed(1) + '" text-anchor="middle">' + escHTML(label) + '</text>' +
      '</g>';
  });

  const svg =
    '<svg class="constellation-svg" viewBox="0 0 ' + width + ' ' + height + '" width="' + width + '" height="' + height + '" role="img">' +
      '<title>Konstelasi Pengetahuan — semua pemikir</title>' +
      '<desc>Peta ' + nodes.length + ' pemikir pada satu sumbu waktu bersama, diwarnai per kategori.</desc>' +
      axisHTML + nodesHTML +
    '</svg>';

  const legendCats = Object.keys(CAT_LABELS).filter(c => INDEX.some(b => b.category === c));
  const legendHTML = '<div class="constellation-legend">' + legendCats.map(c =>
    '<span class="cx-legend-item"><span class="cx-legend-dot" style="background:var(--c-' + c + '-2)"></span>' + CAT_LABELS[c] + '</span>'
  ).join('') + '</div>';

  body.innerHTML =
    '<h2 class="cx-map-title">Konstelasi Pengetahuan</h2>' +
    '<p class="cx-map-sub">' + names.length + ' pemikir sepanjang &plusmn;2.500 tahun</p>' +
    legendHTML +
    '<div class="constellation-scroll cx-map-bg">' + svg + '</div>';

  body.querySelectorAll('[data-goto]').forEach(el => {
    el.onclick = () => { location.hash = '#/penulis/' + slugAuthor(el.dataset.goto); };
    el.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); location.hash = '#/penulis/' + slugAuthor(el.dataset.goto); }
    });
  });
  const mapScroll = body.querySelector('.constellation-scroll');
  initScrollReveal(mapScroll);
  bindDragPan(mapScroll);
}

/* ---------- detail buku ---------- */
async function renderDetail(id) {
  const meta = INDEX.find(b => b.id === id);
  if (!meta) { location.hash = '#/'; return; }
  $('#view-detail').hidden = false;
  window.scrollTo(0, 0);
  const p = getProgress()[id];
  const pct = bookPercent(meta);
  const startLabel = p ? 'Lanjutkan Membaca (' + pct + '%)' : 'Mulai Membaca';

  $('#detail-body').innerHTML =
    '<div class="detail-hero" style="--tint:var(--c-' + meta.category + '-2)">' +
      coverHTML(meta, true).replace('%%PROGRESS%%', '') +
      '<div class="detail-hd">' +
        '<h2>' + escHTML(meta.title) + '</h2>' +
        '<p class="dt-author">' + escHTML(meta.author) + ' · ' + escHTML(meta.year) + '</p>' +
        '<div class="detail-stats">' +
          '<span class="stat-pill">' + meta.chapterCount + ' bab</span>' +
          '<span class="stat-pill">' + estMinutes(meta.words) + '</span>' +
          '<span class="stat-pill">Domain publik</span>' +
        '</div>' +
      '</div>' +
    '</div>' +
    '<p class="detail-desc">' + escHTML(meta.description) + '</p>' +
    authorCardHTML(meta.author) +
    '<p class="detail-source">Sumber: ' + escHTML(meta.source) + '</p>' +
    '<button class="btn-primary" id="btn-read">' + startLabel + '</button>' +
    '<button class="btn-ghost" id="btn-listen">&#127911; Dengarkan' +
      (AUDIO_MANIFEST[id] ? ' <span class="badge-audio">Audio HD</span>' : '') + '</button>' +
    '<div class="detail-toc"><h3>Daftar Bab</h3><ol id="detail-toc-list"><li>Memuat…</li></ol></div>';

  $('#btn-read').onclick = () => {
    location.hash = '#/baca/' + id + '/' + (p ? p.ch : 0);
  };
  $('#btn-listen').onclick = () => {
    const ap = getListenPos()[id];
    location.hash = '#/dengar/' + id + '/' + (ap ? ap.ch : (p ? p.ch : 0));
  };

  try {
    const book = await loadBook(meta);
    $('#detail-toc-list').innerHTML = book.chapters.map((c, i) =>
      '<li><button data-ch="' + i + '"' + (p && p.ch === i ? ' class="toc-current"' : '') + '>' +
      '<span class="toc-no">' + (i + 1) + '</span>' +
      '<span style="flex:1">' + escHTML(c.title) + '</span><span class="toc-min">' + estMinutes(c.words) + '</span>' +
      '</button></li>'
    ).join('');
    $('#detail-toc-list').querySelectorAll('button').forEach(btn => {
      btn.onclick = () => { location.hash = '#/baca/' + id + '/' + btn.dataset.ch; };
    });
  } catch (e) {
    $('#detail-toc-list').innerHTML = '<li>Gagal memuat isi buku. Periksa koneksi lalu coba lagi.</li>';
  }
}

/* ---------- pembaca (paginasi + flip 3D) ---------- */
const pageState = {
  page: 0, pages: 1, stride: 1, pageW: 300, padX: 22,
  animating: false, pendingLastPage: false,
  dragging: false, dragStartX: 0, dragStartY: 0, dragDX: 0, dragT0: 0,
  horizontal: null, dragMode: null, dragOverlay: null, dragFromPage: 0
};

async function loadBook(meta) {
  if (BOOK_CACHE[meta.id]) return BOOK_CACHE[meta.id];
  const res = await fetch(meta.file);
  if (!res.ok) throw new Error('HTTP ' + res.status);
  const book = await res.json();
  BOOK_CACHE[meta.id] = book;
  return book;
}

async function openReader(id, ch) {
  const meta = INDEX.find(b => b.id === id);
  if (!meta) { location.hash = '#/'; return; }
  $('#view-reader').hidden = false;
  $('#view-reader').classList.remove('chrome-hidden');
  document.body.style.overflow = 'hidden';
  $('#reader-content').innerHTML = '<p style="font-family:var(--sans);color:var(--r-soft)">Memuat…</p>';
  let book;
  try { book = await loadBook(meta); }
  catch (e) {
    $('#reader-content').innerHTML = '<p style="font-family:var(--sans)">Gagal memuat buku. Periksa koneksi lalu coba lagi.</p>';
    return;
  }
  const sameBook = currentBook && currentBook.meta.id === id;
  currentBook = { meta, book };
  currentChapter = Math.max(0, Math.min(ch, book.chapters.length - 1));
  clearFlips();
  renderChapter(!sameBook);
  syncReadTick(); // currentBook baru siap → mulai hitung waktu baca (mode embed)
}

function renderChapter(restorePosition) {
  const { meta, book } = currentBook;
  const chap = book.chapters[currentChapter];
  applySettings(false);

  $('#reader-book-title').textContent = meta.title;

  const isLast = currentChapter >= book.chapters.length - 1;
  $('#reader-content').innerHTML =
    '<h2 class="chapter-title">' + escHTML(chap.title) + '</h2>' +
    '<p class="chapter-meta">' + escHTML(meta.author) + ' · ' + estMinutes(chap.words) + '</p>' +
    chap.paragraphs.map(p => '<p>' + escHTML(p) + '</p>').join('') +
    '<div class="chapter-end">' + (isLast
      ? 'Tamat — kamu menyelesaikan “' + escHTML(meta.title) + '”.'
      : 'Akhir ' + escHTML(chap.title)) + '</div>';

  $('#reader-settings').hidden = true;
  $('#toc-sheet').hidden = true;

  // layout sinkron: akses scrollWidth memaksa reflow (rAF ditangguhkan di tab tersembunyi)
  layoutPages();
  let page = 0;
  if (pageState.pendingLastPage) {
    page = pageState.pages - 1;
    pageState.pendingLastPage = false;
  } else if (restorePosition) {
    const p = getProgress()[meta.id];
    if (p && p.ch === currentChapter) page = Math.round(p.ratio * (pageState.pages - 1));
  }
  setPage(Math.max(0, Math.min(page, pageState.pages - 1)), false);
}

/* ukur & susun halaman: konten jadi kolom selebar halaman */
function layoutPages() {
  const pager = $('#pager');
  const content = $('#reader-content');
  const cw = pager.clientWidth;
  const pageW = Math.min(cw - 44, 620);
  const padX = Math.round((cw - pageW) / 2);
  const gap = padX * 2;
  pager.style.paddingLeft = padX + 'px';
  pager.style.paddingRight = padX + 'px';
  content.style.columnWidth = pageW + 'px';
  content.style.columnGap = gap + 'px';
  const stride = pageW + gap;
  const sw = content.scrollWidth; // memaksa reflow
  pageState.pageW = pageW;
  pageState.padX = padX;
  pageState.stride = stride;
  pageState.pages = Math.max(1, Math.round((sw + gap) / stride));
}

function setPage(page, animate) {
  const content = $('#reader-content');
  pageState.page = Math.max(0, Math.min(page, pageState.pages - 1));
  content.style.transition = animate ? '' : 'none';
  content.style.transform = 'translateX(' + (-pageState.page * pageState.stride) + 'px)';
  if (!animate) {
    void content.offsetWidth; // flush style sebelum transisi diaktifkan lagi
    content.style.transition = '';
  }
  updateReaderChrome();
  saveReadingPosition();
}

function saveReadingPosition() {
  if (!currentBook) return;
  const ratio = pageState.pages > 1 ? pageState.page / (pageState.pages - 1) : 1;
  setBookProgress(currentBook.meta.id, currentChapter, ratio);
}

function updateReaderChrome() {
  const { book } = currentBook;
  const chap = book.chapters[currentChapter];
  $('#reader-chapter-label').textContent = chap.title + ' · ' + (currentChapter + 1) + '/' + book.chapters.length;
  $('#page-pos').textContent = 'Hal ' + (pageState.page + 1) + '/' + pageState.pages + ' · ' + chap.title;
  const ratio = pageState.pages > 1 ? pageState.page / (pageState.pages - 1) : 1;
  $('#reader-progress-fill').style.width = Math.round(ratio * 100) + '%';
  $('#page-prev').disabled = currentChapter === 0 && pageState.page === 0;
  $('#page-next').disabled = currentChapter >= book.chapters.length - 1 && pageState.page >= pageState.pages - 1;
}

/* ---------- mesin flip 3D ---------- */
let flipNodes = [];
const FLIP_SLICES = 8; // halaman dipotong jadi pita vertikal berantai supaya bisa menekuk
const FLIP_BEND = 24;  // total derajat lengkung saat halaman tegak (0 di kedua ujung)

function makePageClone(pageIndex) {
  const content = $('#reader-content');
  const clone = content.cloneNode(true);
  clone.removeAttribute('id');
  clone.classList.add('flip-clone');
  clone.style.transform = 'translateX(' + (-pageIndex * pageState.stride) + 'px)';
  clone.style.height = '100%';
  return clone;
}

function makeOverlay(pageIndex, extraClass) {
  const pager = $('#pager');
  const wrap = document.createElement('div');
  wrap.className = 'flip-page' + (extraClass ? ' ' + extraClass : '');
  wrap.style.left = pageState.padX + 'px';
  wrap.style.width = pageState.pageW + 'px';

  // Lembaran dibangun dari pita vertikal BERANTAI (tiap pita anak dari pita
  // sebelumnya). setFlipAngle memberi rotasi kecil di tiap sambungan sehingga
  // halaman menekuk membusur seperti kertas sungguhan (efek curl ala turn.js),
  // bukan papan datar. Tiap pita punya muka depan (konten) + punggung kertas.
  const sliceW = pageState.pageW / FLIP_SLICES;
  const joints = [], shadesF = [], dimsB = [];
  let parent = wrap;
  for (let i = 0; i < FLIP_SLICES; i++) {
    const seg = document.createElement('div');
    seg.className = 'flip-seg';
    seg.style.width = (sliceW + 0.6) + 'px'; // tumpang tindih tipis menutup celah antar pita
    seg.style.left = (i === 0 ? 0 : sliceW) + 'px';
    if (i > 0) joints.push(seg);

    const front = document.createElement('div');
    front.className = 'flip-seg-face';
    const holder = document.createElement('div');
    holder.style.cssText = 'position:absolute;top:0;bottom:0;left:' + (-i * sliceW) +
      'px;width:' + pageState.pageW + 'px;';
    holder.appendChild(makePageClone(pageIndex));
    front.appendChild(holder);
    const shade = document.createElement('div'); // potongan gradien global, digeser per pita
    shade.className = 'flip-shade';
    shade.style.left = (-i * sliceW) + 'px';
    shade.style.width = pageState.pageW + 'px';
    front.appendChild(shade);
    shadesF.push(shade);

    const back = document.createElement('div');
    back.className = 'flip-seg-face flip-seg-back';
    const dim = document.createElement('div');
    dim.className = 'flip-dim';
    back.appendChild(dim);
    dimsB.push(dim);

    seg.append(front, back);
    parent.appendChild(seg);
    parent = seg;
  }

  // bayangan yang JATUH ke halaman di bawahnya (bshadow ala turn.js),
  // paling pekat saat halaman tegak lurus
  const cast = document.createElement('div');
  cast.className = 'flip-cast';
  cast.style.left = pageState.padX + 'px';
  cast.style.width = pageState.pageW + 'px';
  pager.appendChild(cast);

  // cache referensi utk setFlipAngle (dipanggil tiap frame rAF/drag)
  wrap._joints = joints;
  wrap._shadesF = shadesF;
  wrap._dimsB = dimsB;
  wrap._cast = cast;

  pager.appendChild(wrap);
  flipNodes.push(wrap, cast);
  return wrap;
}

function clearFlips() {
  flipNodes.forEach(n => n.remove());
  flipNodes = [];
}

function setFlipAngle(el, deg) {
  const a = Math.abs(deg);
  const t = Math.max(0, Math.min(1, a / 180));
  const bulge = Math.sin(t * Math.PI); // 0 di kedua ujung, puncak saat halaman tegak (90°)
  el.style.transform = 'rotateY(' + deg + 'deg)';

  // lengkungan: tiap sambungan pita menyumbang sebagian kecil dari total lengkung.
  // Ujung halaman "tertinggal" dari pangkalnya — persis kertas yang ditekuk
  const joints = el._joints || [];
  if (joints.length) {
    const per = 'rotateY(' + (bulge * FLIP_BEND / joints.length).toFixed(3) + 'deg)';
    for (let i = 0; i < joints.length; i++) joints[i].style.transform = per;
  }

  const frontT = Math.min(a, 90) / 90;             // fase depan  (0..90°)
  const backT = Math.max(0, (a - 90) / 90);        // fase belakang (90..180°)
  const oF = (frontT * 0.45).toFixed(3);
  const oB = ((1 - backT) * 0.4).toFixed(3);
  (el._shadesF || []).forEach(s => { s.style.opacity = oF; });
  (el._dimsB || []).forEach(s => { s.style.opacity = oB; });
  if (el._cast) el._cast.style.opacity = (bulge * 0.4).toFixed(3);
}

/* animasi via rAF (bukan transisi CSS) supaya SEMUA efek — bayangan depan/belakang,
   bayangan jatuh, kilau, curl — dihitung ulang tiap frame, konsisten dgn saat drag.
   Easing easeOutCirc = easing bawaan turn.js */
function animateFlip(el, fromDeg, toDeg, done) {
  pageState.animating = true;
  const span = Math.abs(toDeg - fromDeg);
  const dur = Math.max(180, FLIP_MS * span / 180); // proporsional sisa sudut (rilis dari drag)
  const t0 = performance.now();
  setFlipAngle(el, fromDeg);
  function step(now) {
    if (!el.isConnected) { pageState.animating = false; return; }
    const p = Math.min(1, (now - t0) / dur);
    const e = Math.sqrt(1 - (p - 1) * (p - 1)); // easeOutCirc (turn.js)
    setFlipAngle(el, fromDeg + (toDeg - fromDeg) * e);
    if (p < 1) { requestAnimationFrame(step); return; }
    pageState.animating = false;
    if (done) done();
  }
  requestAnimationFrame(step);
}

/* balik halaman; melewati batas bab berpindah bab otomatis */
function goPage(delta) {
  if (!currentBook || pageState.animating || pageState.dragging) return;
  if (delta > 0 && EMBED_MODE) readSess.pagesPending++; // hitung halaman maju (mode embed)
  const nCh = currentBook.book.chapters.length;
  const target = pageState.page + delta;

  if (target >= 0 && target <= pageState.pages - 1) {
    if (delta > 0) { // halaman ini melipat ke kiri, halaman baru di baliknya
      const ov = makeOverlay(pageState.page);
      setPage(target, false);
      animateFlip(ov, 0, -180, clearFlips);
    } else {         // halaman sebelumnya melipat masuk dari kiri
      const ov = makeOverlay(target);
      animateFlip(ov, -180, 0, () => { setPage(target, false); clearFlips(); });
    }
    return;
  }
  if (target > pageState.pages - 1) {
    if (currentChapter < nCh - 1) {
      const ov = makeOverlay(pageState.page); // halaman lama (dari konten lama)
      gotoChapter(currentChapter + 1);        // bab baru dirender di baliknya
      animateFlip(ov, 0, -180, clearFlips);
    }
    return;
  }
  if (currentChapter > 0) {
    makeOverlay(pageState.page, 'flip-underlay'); // halaman lama, statis di bawah
    pageState.pendingLastPage = true;
    gotoChapter(currentChapter - 1);              // render bab sebelumnya (hal terakhir)
    const ov = makeOverlay(pageState.page);       // halaman tujuan, melipat masuk
    animateFlip(ov, -180, 0, clearFlips);
  }
}

function gotoChapter(i) {
  const { book, meta } = currentBook;
  if (i < 0 || i >= book.chapters.length) return;
  currentChapter = i;
  history.replaceState(null, '', '#/baca/' + meta.id + '/' + i);
  renderChapter(false);
}

/* ---------- gesture: drag mengikuti jari ---------- */
function bindPagerGestures() {
  const pager = $('#pager');

  pager.addEventListener('pointerdown', (e) => {
    if ($('#view-reader').hidden || !currentBook || pageState.animating) return;
    pageState.dragging = true;
    pageState.horizontal = null;
    pageState.dragMode = null;
    pageState.dragOverlay = null;
    pageState.dragStartX = e.clientX;
    pageState.dragStartY = e.clientY;
    pageState.dragDX = 0;
    pageState.dragT0 = performance.now();
    pageState.dragFromPage = pageState.page;
  });

  pager.addEventListener('pointermove', (e) => {
    if (!pageState.dragging) return;
    const dx = e.clientX - pageState.dragStartX;
    const dy = e.clientY - pageState.dragStartY;
    if (pageState.horizontal === null && (Math.abs(dx) > 8 || Math.abs(dy) > 8)) {
      pageState.horizontal = Math.abs(dx) > Math.abs(dy);
      if (pageState.horizontal) {
        try { pager.setPointerCapture(e.pointerId); } catch (err) { /* abaikan */ }
        // tentukan mode drag sekali di awal
        const canFwd = pageState.page < pageState.pages - 1;
        const canBack = pageState.page > 0;
        if (dx < 0 && canFwd) {
          pageState.dragMode = 'flip-fwd';
          pageState.dragOverlay = makeOverlay(pageState.dragFromPage);
          setFlipAngle(pageState.dragOverlay, 0);
          setPage(pageState.dragFromPage + 1, false); // halaman baru menunggu di balik
        } else if (dx > 0 && canBack) {
          pageState.dragMode = 'flip-back';
          pageState.dragOverlay = makeOverlay(pageState.dragFromPage - 1);
          setFlipAngle(pageState.dragOverlay, -180);
        } else {
          pageState.dragMode = 'slide'; // di ujung buku/bab: geser dengan resistensi
        }
      }
    }
    if (!pageState.horizontal) return;
    pageState.dragDX = dx;

    if (pageState.dragMode === 'flip-fwd') {
      const t = Math.max(-1, Math.min(0, dx / pageState.pageW));
      setFlipAngle(pageState.dragOverlay, t * 180);
    } else if (pageState.dragMode === 'flip-back') {
      const t = Math.max(0, Math.min(1, dx / pageState.pageW));
      setFlipAngle(pageState.dragOverlay, -180 + t * 180);
    } else if (pageState.dragMode === 'slide') {
      const content = $('#reader-content');
      content.style.transition = 'none';
      content.style.transform = 'translateX(' + (-pageState.dragFromPage * pageState.stride + dx / 3) + 'px)';
    }
  });

  const endDrag = () => {
    if (!pageState.dragging) return;
    pageState.dragging = false;
    if (!pageState.horizontal) return;
    const dx = pageState.dragDX;
    const dt = performance.now() - pageState.dragT0;
    const velocity = Math.abs(dx) / Math.max(dt, 1);
    const flick = velocity > 0.45 && Math.abs(dx) > 24;
    const ov = pageState.dragOverlay;

    if (pageState.dragMode === 'flip-fwd') {
      const angle = Math.max(-180, Math.min(0, (dx / pageState.pageW) * 180));
      const commit = angle < -50 || (flick && dx < 0);
      if (commit) {
        animateFlip(ov, angle, -180, clearFlips); // pageState.page sudah di target
      } else {
        animateFlip(ov, angle, 0, () => { setPage(pageState.dragFromPage, false); clearFlips(); });
      }
    } else if (pageState.dragMode === 'flip-back') {
      const angle = -180 + Math.max(0, Math.min(1, dx / pageState.pageW)) * 180;
      const commit = angle > -130 || (flick && dx > 0);
      if (commit) {
        animateFlip(ov, angle, 0, () => { setPage(pageState.dragFromPage - 1, false); clearFlips(); });
      } else {
        animateFlip(ov, angle, -180, clearFlips);
      }
    } else if (pageState.dragMode === 'slide') {
      const content = $('#reader-content');
      content.style.transition = '';
      const far = Math.abs(dx) > pageState.stride * 0.22;
      if ((far || flick) && dx < 0) goPage(1);       // lintas bab maju (flip)
      else if ((far || flick) && dx > 0) goPage(-1); // lintas bab mundur (flip)
      else setPage(pageState.dragFromPage, true);    // kembali dengan animasi
    }
    pageState.dragMode = null;
    pageState.dragOverlay = null;
  };
  pager.addEventListener('pointerup', endDrag);
  pager.addEventListener('pointercancel', endDrag);

  // tap: tepi = balik halaman, tengah = mode imersif (sembunyikan bar)
  pager.addEventListener('click', (e) => {
    if ($('#view-reader').hidden || !currentBook) return;
    if (Math.abs(e.clientX - pageState.dragStartX) > 8) return; // itu drag, bukan tap
    const x = e.clientX / pager.clientWidth;
    if (x < 0.3) goPage(-1);
    else if (x > 0.7) goPage(1);
    else $('#view-reader').classList.toggle('chrome-hidden');
  });
}

/* ---------- pengaturan pembaca ---------- */
function applySettings(relayout) {
  const s = getSettings();
  const reader = $('#view-reader');
  reader.dataset.rtheme = s.theme;
  reader.style.setProperty('--reader-font', s.fontSize + 'px');
  document.querySelectorAll('.theme-dot').forEach(d =>
    d.classList.toggle('active', d.dataset.theme === s.theme));
  const themeBtn = $('#reader-theme-btn');
  if (themeBtn) {
    themeBtn.innerHTML = s.theme === 'gelap' ? '&#9788;' : '&#9790;'; // ☼ / ☾
    themeBtn.setAttribute('aria-label', s.theme === 'gelap' ? 'Ganti ke mode terang' : 'Ganti ke mode gelap');
  }
  if (relayout && currentBook && !reader.hidden) {
    const ratio = pageState.pages > 1 ? pageState.page / (pageState.pages - 1) : 0;
    layoutPages();
    setPage(Math.round(ratio * (pageState.pages - 1)), false);
  }
}

/* ---------- keamanan render ---------- */
function escHTML(str) {
  return String(str).replace(/[&<>"']/g, c =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

/* ---------- boot ---------- */
async function boot() {
  $('#detail-back').onclick = () => { location.hash = '#/'; };
  $('#constellation-back').onclick = () => { location.hash = '#/'; };
  // profil penulis bisa dicapai dari globe, daftar penulis, atau profil lain (tab Koneksi) —
  // kembali ke halaman asal via history. Deep-link (belum ada navigasi in-app) jangan pakai
  // history.back(): itu bisa melempar keluar aplikasi (mis. balik ke tab kosong/situs lain)
  $('#author-back').onclick = () => {
    if (hasInAppNav) history.back();
    else location.hash = '#/';
  };
  $('#reader-back').onclick = () => {
    if (currentBook) location.hash = '#/buku/' + currentBook.meta.id;
    else location.hash = '#/';
  };
  $('#reader-settings-btn').onclick = () => {
    $('#reader-settings').hidden = !$('#reader-settings').hidden;
  };
  // toggle cepat gelap⇄terang tanpa membuka panel pengaturan (tema sepia tetap di panel)
  $('#reader-theme-btn').onclick = () => {
    setSettings({ theme: getSettings().theme === 'gelap' ? 'terang' : 'gelap' });
  };

  /* hero landing: tombol jelajah + hemat daya video background */
  $('#hero-explore').onclick = () => {
    $('#search-input').closest('.search-row').scrollIntoView({ behavior: 'smooth', block: 'start' });
  };
  const heroVideo = $('#hero-video');
  if (heroVideo) {
    if (REDUCE_MOTION) {
      heroVideo.removeAttribute('autoplay'); // poster saja utk prefers-reduced-motion
    } else {
      // ditunda sesaat: listener ini terdaftar sebelum router, tunggu view selesai berganti
      const syncHeroVideo = () => setTimeout(() => {
        const active = !$('#view-library').hidden && !document.hidden;
        if (active) heroVideo.play().catch(() => { /* autoplay ditolak: poster tampil */ });
        else heroVideo.pause();
      }, 60);
      window.addEventListener('hashchange', syncHeroVideo);
      document.addEventListener('visibilitychange', syncHeroVideo);
    }
  }
  $('#font-dec').onclick = () => setSettings({ fontSize: Math.max(15, getSettings().fontSize - 1) });
  $('#font-inc').onclick = () => setSettings({ fontSize: Math.min(24, getSettings().fontSize + 1) });
  document.querySelectorAll('.theme-dot').forEach(d => {
    d.onclick = () => setSettings({ theme: d.dataset.theme });
  });
  $('#search-input').addEventListener('input', () => {
    searchQuery = $('#search-input').value;
    $('#search-clear').hidden = !searchQuery;
    if (groupMode === 'author') renderAuthorList();
    renderShelf();
  });
  $('#search-clear').onclick = () => {
    searchQuery = ''; $('#search-input').value = ''; $('#search-clear').hidden = true;
    if (groupMode === 'author') renderAuthorList();
    renderShelf();
  };
  document.querySelectorAll('.gt-btn').forEach(btn => {
    btn.onclick = () => {
      groupMode = btn.dataset.group;
      if (groupMode === 'genre') activeAuthor = null;
      applyGroupMode();
      if (groupMode === 'author') renderAuthorList();
      renderShelf();
    };
  });

  $('#page-prev').onclick = () => goPage(-1);
  $('#page-next').onclick = () => goPage(1);
  $('#page-pos').onclick = () => openTOC();
  $('#toc-close').onclick = () => { $('#toc-sheet').hidden = true; };
  $('#toc-sheet').onclick = (e) => { if (e.target === $('#toc-sheet')) $('#toc-sheet').hidden = true; };

  $('#reader-listen-btn').onclick = () => {
    if (currentBook) location.hash = '#/dengar/' + currentBook.meta.id + '/' + currentChapter;
  };

  bindPagerGestures();
  bindListenControls();

  window.addEventListener('keydown', (e) => {
    if ($('#view-reader').hidden || !currentBook) return;
    if (e.key === 'ArrowRight' || e.key === 'PageDown' || e.key === ' ') { e.preventDefault(); goPage(1); }
    if (e.key === 'ArrowLeft' || e.key === 'PageUp') { e.preventDefault(); goPage(-1); }
  });

  let wheelLock = false;
  window.addEventListener('wheel', (e) => {
    if ($('#view-reader').hidden || !currentBook || wheelLock) return;
    if (Math.abs(e.deltaY) < 12 && Math.abs(e.deltaX) < 12) return;
    wheelLock = true;
    setTimeout(() => { wheelLock = false; }, FLIP_MS + 60);
    goPage((e.deltaY || e.deltaX) > 0 ? 1 : -1);
  }, { passive: true });

  window.addEventListener('resize', () => {
    if ($('#view-reader').hidden || !currentBook) return;
    clearFlips();
    const ratio = pageState.pages > 1 ? pageState.page / (pageState.pages - 1) : 0;
    layoutPages();
    setPage(Math.round(ratio * (pageState.pages - 1)), false);
  });

  window.addEventListener('hashchange', () => { hasInAppNav = true; });
  window.addEventListener('hashchange', router);

  // service worker (jangan crash di file://; skip di localhost supaya dev tidak kena cache basi)
  const isLocalDev = /^(localhost|127\.)/.test(location.hostname);
  if ('serviceWorker' in navigator && location.protocol.indexOf('http') === 0 && !isLocalDev) {
    navigator.serviceWorker.register('sw.js').then((reg) => {
      // deteksi SW baru → suruh aktif segera; reload sekali saat controller berganti
      reg.addEventListener('updatefound', () => {
        const nw = reg.installing;
        if (!nw) return;
        nw.addEventListener('statechange', () => {
          if (nw.state === 'installed' && navigator.serviceWorker.controller) {
            nw.postMessage('skipWaiting');
          }
        });
      });
      // cek update tiap app dibuka kembali
      reg.update().catch(() => {});
    }).catch(() => {});
    let reloadedForSW = false;
    navigator.serviceWorker.addEventListener('controllerchange', () => {
      if (reloadedForSW) return;
      reloadedForSW = true;
      location.reload();
    });
  }

  try { AUDIO_MANIFEST = await (await fetch('audio/index.json')).json(); }
  catch (e) { AUDIO_MANIFEST = {}; }

  try { AUTHORS = await (await fetch('books/authors.json')).json(); }
  catch (e) { AUTHORS = {}; }

  try {
    const res = await fetch('books/index.json');
    INDEX = await res.json();
  } catch (e) {
    document.body.innerHTML =
      '<div style="padding:40px 24px;font-family:system-ui;text-align:center">' +
      '<h2>Pustaka</h2><p>Katalog buku belum tersedia. Buka lewat server (bukan file://) ' +
      'dan pastikan folder <code>books/</code> ada.</p></div>';
    return;
  }
  router();
}

/* ============ Dengarkan (audiobook / TTS) ============ */
let AUDIO_MANIFEST = {};
const LS_AUDIO = 'pustaka.audio';
const SPEEDS = [0.8, 0.9, 1, 1.1, 1.25, 1.5];
const SLEEPS = [0, 15, 30, 60];

const listen = {
  active: false, mode: null, bookId: null, ch: 0,
  sents: [], idx: 0, playing: false,
  rate: 1, sleepDeadline: 0, saveTick: 0
};

function getListenPos() { return loadJSONLS(LS_AUDIO, {}); }
function saveListenPos() {
  if (!listen.bookId) return;
  const all = getListenPos();
  all[listen.bookId] = {
    ch: listen.ch,
    idx: listen.idx,
    sec: listen.mode === 'audio' ? Math.floor($('#audio-el').currentTime) : 0,
    updated: new Date().toISOString()
  };
  saveJSONLS(LS_AUDIO, all);
}

function splitSentences(text) {
  const m = text.match(/[^.!?…]+[.!?…]+["')\]]*\s*|[^.!?…]+$/g);
  return (m || [text]).map(s => s.trim()).filter(Boolean);
}

async function openListen(id, ch) {
  const meta = INDEX.find(b => b.id === id);
  if (!meta) { location.hash = '#/'; return; }
  let book;
  try { book = await loadBook(meta); }
  catch (e) { location.hash = '#/buku/' + id; return; }

  const wasPlaying = listen.playing && listen.bookId === id;
  stopListening(true);

  $('#view-listen').hidden = false;
  document.body.style.overflow = 'hidden';
  listen.active = true;
  listen.bookId = id;
  listen.ch = Math.max(0, Math.min(ch, book.chapters.length - 1));
  const chap = book.chapters[listen.ch];

  const cover = $('#listen-cover');
  const lp = bookPortrait(meta);
  if (lp) {
    cover.style.background = 'center top / cover no-repeat url("' + encodeURI(lp) + '")';
    cover.textContent = '';
  } else {
    const angle = 130 + (hashCode(id) % 55);
    cover.style.background = 'linear-gradient(' + angle + 'deg, var(--c-' + meta.category + '-1), var(--c-' + meta.category + '-2))';
    cover.textContent = meta.title[0];
  }
  $('#listen-book').textContent = meta.title;
  $('#listen-chapter').textContent = chap.title + ' · ' + (listen.ch + 1) + '/' + book.chapters.length;

  const manifest = AUDIO_MANIFEST[id];
  const episode = manifest && (manifest.episodes || []).find(e => e.ch === listen.ch);
  const audio = $('#audio-el');
  const saved = getListenPos()[id];

  if (episode) {
    listen.mode = 'audio';
    $('#listen-seek-wrap').hidden = false;
    $('#listen-engine').textContent = 'Audio HD · narasi neural (Andrew)';
    $('#listen-live').textContent = '\u{1F3A7}';
    if (audio.dataset.url !== episode.url) {
      audio.src = episode.url;
      audio.dataset.url = episode.url;
      if (saved && saved.ch === listen.ch && saved.sec > 5) {
        audio.addEventListener('loadedmetadata', () => { audio.currentTime = saved.sec; }, { once: true });
      }
    }
    audio.playbackRate = listen.rate;
    setMediaSession(meta, chap);
    if (wasPlaying) audio.play().catch(() => {});
  } else {
    listen.mode = 'tts';
    $('#listen-seek-wrap').hidden = true;
    $('#listen-engine').textContent = 'Text-to-Speech perangkat · pilih suara di ⚙';
    listen.sents = [chap.title + '.'].concat(
      chap.paragraphs.map(p => splitSentences(p)).flat());
    listen.idx = (saved && saved.ch === listen.ch && saved.idx < listen.sents.length) ? saved.idx : 0;
    renderLive();
    if (wasPlaying) startTTS();
  }
  updatePlayIcon();
}

function stopListening(keepView) {
  if (!listen.active && !keepView) return;
  listen.playing = false;
  try { speechSynthesis.cancel(); } catch (e) { /* tidak tersedia */ }
  const audio = $('#audio-el');
  if (audio && !audio.paused) audio.pause();
  if (!keepView) listen.active = false;
  updatePlayIcon();
}

function renderLive() {
  if (listen.mode !== 'tts') return;
  const el = $('#listen-live');
  el.textContent = listen.sents[listen.idx] || '';
}

function updatePlayIcon() {
  const audio = $('#audio-el');
  const playing = listen.mode === 'audio' ? !audio.paused : listen.playing;
  $('#listen-play').innerHTML = playing ? '&#9208;' : '&#9654;';
}

function checkSleep() {
  if (listen.sleepDeadline && Date.now() > listen.sleepDeadline) {
    listen.sleepDeadline = 0;
    $('#listen-sleep').textContent = 'Timer: Off';
    stopListening(true);
    return true;
  }
  return false;
}

function pickVoice() {
  const want = getSettings().voiceURI;
  const voices = speechSynthesis.getVoices();
  if (want) { const v = voices.find(v => v.voiceURI === want); if (v) return v; }
  return voices.find(v => /en[-_]/i.test(v.lang) && /natural|neural/i.test(v.name)) ||
         voices.find(v => /en[-_]US/i.test(v.lang)) ||
         voices.find(v => /^en/i.test(v.lang)) || null;
}

function startTTS() {
  listen.playing = true;
  updatePlayIcon();
  speakCurrent();
}

function speakCurrent() {
  if (!listen.playing || checkSleep()) return;
  if (listen.idx >= listen.sents.length) { listenNextChapter(true); return; }
  const u = new SpeechSynthesisUtterance(listen.sents[listen.idx]);
  u.rate = listen.rate;
  const v = pickVoice();
  if (v) u.voice = v;
  const advance = () => {
    if (!listen.playing) return;
    listen.idx++;
    saveListenPos();
    renderLive();
    speakCurrent();
  };
  u.onend = advance;
  u.onerror = advance;
  renderLive();
  speechSynthesis.speak(u);
}

function listenPlayPause() {
  if (listen.mode === 'audio') {
    const audio = $('#audio-el');
    if (audio.paused) audio.play().catch(() => {});
    else audio.pause();
  } else {
    if (listen.playing) { listen.playing = false; speechSynthesis.cancel(); }
    else startTTS();
  }
  updatePlayIcon();
}

function listenSeekBy(delta) {
  if (listen.mode === 'audio') {
    const audio = $('#audio-el');
    audio.currentTime = Math.max(0, audio.currentTime + delta);
  } else {
    const step = delta > 0 ? 1 : -1;
    listen.idx = Math.max(0, Math.min(listen.sents.length - 1, listen.idx + step));
    saveListenPos();
    if (listen.playing) { speechSynthesis.cancel(); listen.playing = true; speakCurrent(); }
    else renderLive();
  }
}

function listenNextChapter(auto) {
  const book = BOOK_CACHE[listen.bookId];
  if (!book) return;
  if (listen.ch >= book.chapters.length - 1) {
    stopListening(true);
    $('#listen-live').textContent = 'Tamat — kamu menyelesaikan buku ini. \u{1F389}';
    return;
  }
  const keep = auto || listen.playing || (listen.mode === 'audio' && !$('#audio-el').paused);
  listen.playing = keep;
  const all = getListenPos();
  all[listen.bookId] = { ch: listen.ch + 1, idx: 0, sec: 0, updated: new Date().toISOString() };
  saveJSONLS(LS_AUDIO, all);
  history.replaceState(null, '', '#/dengar/' + listen.bookId + '/' + (listen.ch + 1));
  openListen(listen.bookId, listen.ch + 1);
}

function listenPrevChapter() {
  if (listen.ch <= 0) return;
  const keep = listen.playing || (listen.mode === 'audio' && !$('#audio-el').paused);
  listen.playing = keep;
  const all = getListenPos();
  all[listen.bookId] = { ch: listen.ch - 1, idx: 0, sec: 0, updated: new Date().toISOString() };
  saveJSONLS(LS_AUDIO, all);
  history.replaceState(null, '', '#/dengar/' + listen.bookId + '/' + (listen.ch - 1));
  openListen(listen.bookId, listen.ch - 1);
}

function setMediaSession(meta, chap) {
  if (!('mediaSession' in navigator)) return;
  navigator.mediaSession.metadata = new MediaMetadata({
    title: chap.title, artist: meta.author, album: meta.title
  });
  navigator.mediaSession.setActionHandler('play', () => listenPlayPause());
  navigator.mediaSession.setActionHandler('pause', () => listenPlayPause());
  navigator.mediaSession.setActionHandler('seekbackward', () => listenSeekBy(-15));
  navigator.mediaSession.setActionHandler('seekforward', () => listenSeekBy(15));
  navigator.mediaSession.setActionHandler('previoustrack', () => listenPrevChapter());
  navigator.mediaSession.setActionHandler('nexttrack', () => listenNextChapter(false));
}

function fmtTime(s) {
  if (!isFinite(s)) return '0:00';
  s = Math.floor(s);
  const m = Math.floor(s / 60), sec = s % 60;
  return m + ':' + String(sec).padStart(2, '0');
}

function openListenSheet(type) {
  const sheet = $('#voice-sheet');
  const listEl = $('#voice-list');
  const title = sheet.querySelector('.toc-head h2');
  if (type === 'voices') {
    title.textContent = 'Pilih Suara';
    const cur = getSettings().voiceURI;
    const voices = speechSynthesis.getVoices().filter(v => /^en/i.test(v.lang));
    listEl.innerHTML = voices.length
      ? voices.map(v =>
          '<button data-uri="' + escHTML(v.voiceURI) + '"' +
          ((cur ? v.voiceURI === cur : v === pickVoice()) ? ' class="voice-active"' : '') + '>' +
          escHTML(v.name) + ' <small>(' + escHTML(v.lang) + ')</small></button>'
        ).join('')
      : '<p style="padding:16px 4px;color:var(--ink-soft)">Suara belum termuat — coba lagi sebentar.</p>';
    listEl.querySelectorAll('button').forEach(b => {
      b.onclick = () => {
        const s = getSettings(); s.voiceURI = b.dataset.uri; saveJSONLS(LS_SETTINGS, s);
        sheet.hidden = true;
        if (listen.playing && listen.mode === 'tts') { speechSynthesis.cancel(); speakCurrent(); }
      };
    });
  } else {
    title.textContent = 'Daftar Bab';
    const book = BOOK_CACHE[listen.bookId];
    listEl.innerHTML = book.chapters.map((c, i) =>
      '<button data-ch="' + i + '"' + (i === listen.ch ? ' class="voice-active"' : '') + '>' +
      (i + 1) + '. ' + escHTML(c.title) + '</button>').join('');
    listEl.querySelectorAll('button').forEach(b => {
      b.onclick = () => {
        sheet.hidden = true;
        history.replaceState(null, '', '#/dengar/' + listen.bookId + '/' + b.dataset.ch);
        openListen(listen.bookId, parseInt(b.dataset.ch, 10));
      };
    });
  }
  sheet.hidden = false;
}

function bindListenControls() {
  const audio = $('#audio-el');
  $('#listen-back').onclick = () => { location.hash = '#/buku/' + (listen.bookId || ''); };
  $('#listen-play').onclick = listenPlayPause;
  $('#listen-rew').onclick = () => listenSeekBy(-15);
  $('#listen-ffw').onclick = () => listenSeekBy(15);
  $('#listen-prevch').onclick = listenPrevChapter;
  $('#listen-nextch').onclick = () => listenNextChapter(false);
  $('#listen-voice-btn').onclick = () => openListenSheet('voices');
  $('#listen-chlist').onclick = () => openListenSheet('chapters');
  $('#voice-close').onclick = () => { $('#voice-sheet').hidden = true; };
  $('#voice-sheet').onclick = (e) => { if (e.target === $('#voice-sheet')) $('#voice-sheet').hidden = true; };

  $('#listen-speed').onclick = () => {
    const i = SPEEDS.indexOf(listen.rate);
    listen.rate = SPEEDS[(i + 1) % SPEEDS.length];
    $('#listen-speed').textContent = listen.rate.toFixed(listen.rate === 1 ? 1 : 2).replace(/0$/, '') + '×';
    audio.playbackRate = listen.rate;
    if (listen.playing && listen.mode === 'tts') { speechSynthesis.cancel(); speakCurrent(); }
  };
  $('#listen-sleep').onclick = () => {
    const cur = SLEEPS.findIndex(m => listen.sleepDeadline
      ? Math.abs((listen.sleepDeadline - Date.now()) / 60000 - m) < m * 0.5 + 1 : m === 0);
    const next = SLEEPS[(Math.max(0, cur) + 1) % SLEEPS.length];
    listen.sleepDeadline = next ? Date.now() + next * 60000 : 0;
    $('#listen-sleep').textContent = 'Timer: ' + (next ? next + 'm' : 'Off');
  };

  audio.addEventListener('play', updatePlayIcon);
  audio.addEventListener('pause', updatePlayIcon);
  audio.addEventListener('ended', () => listenNextChapter(true));
  audio.addEventListener('timeupdate', () => {
    if (listen.mode !== 'audio') return;
    if (checkSleep()) return;
    $('#listen-cur').textContent = fmtTime(audio.currentTime);
    $('#listen-dur').textContent = fmtTime(audio.duration);
    if (audio.duration) $('#listen-seek').value = Math.round(audio.currentTime / audio.duration * 1000);
    const now = Date.now();
    if (now - listen.saveTick > 3000) { listen.saveTick = now; saveListenPos(); }
  });
  $('#listen-seek').addEventListener('input', () => {
    if (audio.duration) audio.currentTime = $('#listen-seek').value / 1000 * audio.duration;
  });
  if (typeof speechSynthesis !== 'undefined') {
    speechSynthesis.onvoiceschanged = () => { /* daftar suara siap */ };
  }
}

function openTOC() {
  const { book, meta } = currentBook;
  $('#toc-list').innerHTML = book.chapters.map((c, i) =>
    '<li><button data-ch="' + i + '"' + (i === currentChapter ? ' class="toc-current"' : '') + '>' +
    '<span class="toc-no">' + (i + 1) + '</span>' +
    '<span style="flex:1">' + escHTML(c.title) + '</span><span class="toc-min">' + estMinutes(c.words) + '</span>' +
    '</button></li>'
  ).join('');
  $('#toc-list').querySelectorAll('button').forEach(btn => {
    btn.onclick = () => gotoChapter(parseInt(btn.dataset.ch, 10));
  });
  $('#toc-sheet').hidden = false;
}

boot();
