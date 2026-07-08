/* ============ Pustaka — app.js ============ */
'use strict';

const WPM = 200; // kecepatan baca rata-rata utk estimasi
const LS_SETTINGS = 'pustaka.settings';
const LS_PROGRESS = 'pustaka.progress';

const CAT_LABELS = {
  filsafat: 'Filsafat', politik: 'Politik', sejarah: 'Sejarah',
  ekonomi: 'Ekonomi', sosial: 'Sosial'
};

let INDEX = [];               // books/index.json
const BOOK_CACHE = {};        // id -> book json
let currentBook = null;       // buku yg sedang dibaca
let currentChapter = 0;
let activeCategory = 'semua';

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

/* ---------- routing ---------- */
function router() {
  const h = location.hash || '#/';
  const parts = h.replace(/^#\//, '').split('/');
  $('#view-library').hidden = true;
  $('#view-detail').hidden = true;
  $('#view-reader').hidden = true;
  document.body.style.overflow = '';

  if (parts[0] === 'buku' && parts[1]) {
    renderDetail(parts[1]);
  } else if (parts[0] === 'baca' && parts[1]) {
    openReader(parts[1], parseInt(parts[2] || '0', 10) || 0);
  } else {
    currentBook = null;
    renderLibrary();
  }
}

/* ---------- perpustakaan ---------- */
function renderLibrary() {
  $('#view-library').hidden = false;
  window.scrollTo(0, 0);
  renderContinueCard();
  renderChips();
  renderShelf();
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
  const list = INDEX.filter(b => activeCategory === 'semua' || b.category === activeCategory);
  $('#shelf').innerHTML = list.map(meta => {
    const pct = bookPercent(meta);
    return (
      '<button class="book-card" data-id="' + meta.id + '">' +
        '<div class="cover cat-' + meta.category + '">' +
          '<div class="cv-cat">' + CAT_LABELS[meta.category] + '</div>' +
          '<div class="cv-title">' + escHTML(meta.title) + '</div>' +
          '<div class="cv-author">' + escHTML(meta.author) + '</div>' +
          (pct > 0 ? '<div class="cv-progress"><div style="width:' + pct + '%"></div></div>' : '') +
        '</div>' +
        '<div class="book-meta">' +
          '<p class="bm-title">' + escHTML(meta.title) + '</p>' +
          '<p class="bm-sub">' + estMinutes(meta.words) + (pct > 0 ? ' · ' + pct + '%' : '') + '</p>' +
        '</div>' +
      '</button>'
    );
  }).join('');
  $('#shelf').querySelectorAll('.book-card').forEach(btn => {
    btn.onclick = () => { location.hash = '#/buku/' + btn.dataset.id; };
  });
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
    '<div class="detail-hero">' +
      '<div class="cover cat-' + meta.category + '">' +
        '<div class="cv-cat">' + CAT_LABELS[meta.category] + '</div>' +
        '<div class="cv-title">' + escHTML(meta.title) + '</div>' +
        '<div class="cv-author">' + escHTML(meta.author) + '</div>' +
      '</div>' +
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
    '<p class="detail-source">Sumber: ' + escHTML(meta.source) + '</p>' +
    '<button class="btn-primary" id="btn-read">' + startLabel + '</button>' +
    '<div class="detail-toc"><h3>Daftar Bab</h3><ol id="detail-toc-list"><li>Memuat…</li></ol></div>';

  $('#btn-read').onclick = () => {
    location.hash = '#/baca/' + id + '/' + (p ? p.ch : 0);
  };

  try {
    const book = await loadBook(meta);
    $('#detail-toc-list').innerHTML = book.chapters.map((c, i) =>
      '<li><button data-ch="' + i + '"' + (p && p.ch === i ? ' class="toc-current"' : '') + '>' +
      '<span>' + escHTML(c.title) + '</span><span class="toc-min">' + estMinutes(c.words) + '</span>' +
      '</button></li>'
    ).join('');
    $('#detail-toc-list').querySelectorAll('button').forEach(btn => {
      btn.onclick = () => { location.hash = '#/baca/' + id + '/' + btn.dataset.ch; };
    });
  } catch (e) {
    $('#detail-toc-list').innerHTML = '<li>Gagal memuat isi buku. Periksa koneksi lalu coba lagi.</li>';
  }
}

/* ---------- pembaca (paginasi ala e-reader) ---------- */
const pageState = {
  page: 0, pages: 1, stride: 1,
  dragging: false, dragStartX: 0, dragStartY: 0, dragDX: 0, dragT0: 0,
  horizontal: null, pendingLastPage: false
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
  renderChapter(!sameBook);
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

  // layout sinkron: akses scrollWidth memaksa reflow, tak perlu menunggu frame
  // (rAF ditangguhkan di tab tersembunyi — jangan bergantung padanya)
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
  // paksa reflow sebelum ukur
  const sw = content.scrollWidth;
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

/* balik halaman; melewati batas bab berpindah bab otomatis */
function goPage(delta) {
  if (!currentBook) return;
  const target = pageState.page + delta;
  if (target < 0) {
    if (currentChapter > 0) {
      pageState.pendingLastPage = true;
      gotoChapter(currentChapter - 1);
    } else {
      setPage(0, true);
    }
    return;
  }
  if (target > pageState.pages - 1) {
    if (currentChapter < currentBook.book.chapters.length - 1) {
      gotoChapter(currentChapter + 1);
    } else {
      setPage(pageState.pages - 1, true);
    }
    return;
  }
  setPage(target, true);
}

function gotoChapter(i) {
  const { book, meta } = currentBook;
  if (i < 0 || i >= book.chapters.length) return;
  currentChapter = i;
  history.replaceState(null, '', '#/baca/' + meta.id + '/' + i);
  renderChapter(false);
}

/* geser mengikuti jari (pointer events: sentuh + mouse) */
function bindPagerGestures() {
  const pager = $('#pager');
  const content = $('#reader-content');

  pager.addEventListener('pointerdown', (e) => {
    if ($('#view-reader').hidden || !currentBook) return;
    pageState.dragging = true;
    pageState.horizontal = null;
    pageState.dragStartX = e.clientX;
    pageState.dragStartY = e.clientY;
    pageState.dragDX = 0;
    pageState.dragT0 = performance.now();
  });

  pager.addEventListener('pointermove', (e) => {
    if (!pageState.dragging) return;
    const dx = e.clientX - pageState.dragStartX;
    const dy = e.clientY - pageState.dragStartY;
    if (pageState.horizontal === null && (Math.abs(dx) > 8 || Math.abs(dy) > 8)) {
      pageState.horizontal = Math.abs(dx) > Math.abs(dy);
      if (pageState.horizontal) pager.setPointerCapture(e.pointerId);
    }
    if (!pageState.horizontal) return;
    let drag = dx;
    const atStart = pageState.page === 0 && currentChapter === 0;
    const atEnd = pageState.page >= pageState.pages - 1 &&
                  currentChapter >= currentBook.book.chapters.length - 1;
    if ((drag > 0 && atStart) || (drag < 0 && atEnd)) drag = drag / 3; // resistensi di ujung
    pageState.dragDX = drag;
    content.style.transition = 'none';
    content.style.transform = 'translateX(' + (-pageState.page * pageState.stride + drag) + 'px)';
  });

  const endDrag = () => {
    if (!pageState.dragging) return;
    pageState.dragging = false;
    const content2 = $('#reader-content');
    content2.style.transition = '';
    if (!pageState.horizontal) return;
    const dx = pageState.dragDX;
    const dt = performance.now() - pageState.dragT0;
    const velocity = Math.abs(dx) / Math.max(dt, 1); // px per ms
    const far = Math.abs(dx) > pageState.stride * 0.22;
    const fast = velocity > 0.45 && Math.abs(dx) > 24;
    if ((far || fast) && dx < 0) goPage(1);
    else if ((far || fast) && dx > 0) goPage(-1);
    else setPage(pageState.page, true); // kembali ke tempat
  };
  pager.addEventListener('pointerup', endDrag);
  pager.addEventListener('pointercancel', endDrag);

  // tap di tepi layar = balik halaman (tanpa drag)
  pager.addEventListener('click', (e) => {
    if ($('#view-reader').hidden || !currentBook) return;
    if (Math.abs(e.clientX - pageState.dragStartX) > 8) return; // itu drag, bukan tap
    const x = e.clientX / pager.clientWidth;
    if (x < 0.3) goPage(-1);
    else if (x > 0.7) goPage(1);
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
  $('#reader-back').onclick = () => {
    if (currentBook) location.hash = '#/buku/' + currentBook.meta.id;
    else location.hash = '#/';
  };
  $('#reader-settings-btn').onclick = () => {
    $('#reader-settings').hidden = !$('#reader-settings').hidden;
  };
  $('#font-dec').onclick = () => setSettings({ fontSize: Math.max(15, getSettings().fontSize - 1) });
  $('#font-inc').onclick = () => setSettings({ fontSize: Math.min(24, getSettings().fontSize + 1) });
  document.querySelectorAll('.theme-dot').forEach(d => {
    d.onclick = () => setSettings({ theme: d.dataset.theme });
  });
  $('#page-prev').onclick = () => goPage(-1);
  $('#page-next').onclick = () => goPage(1);
  $('#page-pos').onclick = () => openTOC();
  $('#toc-close').onclick = () => { $('#toc-sheet').hidden = true; };
  $('#toc-sheet').onclick = (e) => { if (e.target === $('#toc-sheet')) $('#toc-sheet').hidden = true; };

  bindPagerGestures();

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
    setTimeout(() => { wheelLock = false; }, 450);
    goPage((e.deltaY || e.deltaX) > 0 ? 1 : -1);
  }, { passive: true });

  window.addEventListener('resize', () => {
    if ($('#view-reader').hidden || !currentBook) return;
    const ratio = pageState.pages > 1 ? pageState.page / (pageState.pages - 1) : 0;
    layoutPages();
    setPage(Math.round(ratio * (pageState.pages - 1)), false);
  });

  window.addEventListener('hashchange', router);

  // service worker (jangan crash di file://; skip di localhost supaya dev tidak kena cache basi)
  const isLocalDev = /^(localhost|127\.)/.test(location.hostname);
  if ('serviceWorker' in navigator && location.protocol.indexOf('http') === 0 && !isLocalDev) {
    navigator.serviceWorker.register('sw.js').catch(() => {});
  }

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

function openTOC() {
  const { book, meta } = currentBook;
  $('#toc-list').innerHTML = book.chapters.map((c, i) =>
    '<li><button data-ch="' + i + '"' + (i === currentChapter ? ' class="toc-current"' : '') + '>' +
    '<span>' + escHTML(c.title) + '</span><span class="toc-min">' + estMinutes(c.words) + '</span>' +
    '</button></li>'
  ).join('');
  $('#toc-list').querySelectorAll('button').forEach(btn => {
    btn.onclick = () => gotoChapter(parseInt(btn.dataset.ch, 10));
  });
  $('#toc-sheet').hidden = false;
}

boot();
