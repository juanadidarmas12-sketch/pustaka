# Pustaka — Transisi Antar-Halaman & "Konstelasi Pengetahuan"

Dokumen desain + spesifikasi implementasi. Ditulis oleh Orchestrator (Opus) sebagai
checkpoint sebelum eksekusi oleh sub-agent Sonnet. Bahasa spec: campuran ID/EN; label UI: Bahasa Indonesia.

Target utama: **Android Chrome PWA** (terinstal). Mobile-first 375px. Vanilla JS, hash-router, tanpa build step.

---

## 0. Ringkasan Riset (Phase A)

### Referensi video YouTube (m-f56P_L660)
Judul video: **"Fable 5 is back and it just changed web design forever"** (diunggah ±1 minggu lalu).
Isinya adalah showcase desain web yang dihasilkan/di-bantu AI (model Fable 5), **bukan** tutorial teknik transisi
spesifik. Karena konten video tidak bisa ditonton (tak ada tool video), yang bisa disimpulkan dari judul/metadata
hanyalah: "desain web modern dengan transisi halaman yang mengesankan". Teknik konkret di dokumen ini berasal dari
pengetahuan sendiri + situs riset di bawah, **bukan** dari isi video.

### Situs interaktif yang dipelajari
1. **Deniz Cem Önduygu — "The History of Philosophy" (timeline)** — paling relevan. Filsuf disusun kronologis;
   ide-ide tercantum di bawah tiap filsuf. Garis **hijau = ide yang mendukung/serupa**, garis **merah = ide yang
   menentang/membantah**. Hover satu ide → semua kecuali ide itu + koneksinya memudar (focus). Klik → node terhubung
   mendekat. Ada zoom/pan + menu filter (kanan atas). Insight penting penulis: "garis menelusuri perkembangan sebuah
   ide sepanjang waktu, bukan selalu transfer langsung antar orang".
2. **The Philosopher's Web (Önduygu)** — force-directed graph; titik biru = filsuf, garis abu = pengaruh; press-hold
   untuk memperluas klaster; toggle "focus" untuk relasi sekunder/tersier.
3. **Philosophy Tree (philosophytree.org)** — 80+ ide saling terhubung, timeline Yunani Kuno → etika AI.
4. **Kumu network viz** — force graph, klaster otomatis muncul dari koneksi.

**Pola yang diadopsi:** (a) edge diwarnai per jenis relasi (hijau=pengaruh/dukungan, merah=menentang); (b) fokus
ego-network — sorot node + koneksi langsung; (c) sumbu-x kronologis = "milestone perjalanan ilmu" secara literal;
(d) tap node → recenter/navigasi. **Pola yang ditolak untuk mobile:** force-directed physics penuh (berat + kusut di 375px).

### View Transitions API (teknik transisi terpilih)
- **Same-document (SPA) view transitions** = cocok persis untuk arsitektur Pustaka (hash-router menukar `.hidden`).
- Dukungan: Chrome 111+, Safari 18+, Firefox 144+ (Baseline "Newly Available" Okt 2025). **Android Chrome (target utama) penuh.**
- Pola minimal:
  ```js
  if (!document.startViewTransition) { updateDOM(); return; }        // fallback
  document.startViewTransition(() => updateDOM());                    // callback boleh async (return promise)
  ```
- `view-transition-name: <nama-unik>` di CSS/inline → elemen dengan nama sama di state lama & baru akan **morph**
  (posisi+ukuran) alih-alih crossfade. Nama harus **unik per dokumen** dan **ada di kedua sisi**; jika hilang di satu
  sisi → fallback ke crossfade otomatis untuk elemen itu.
- Pseudo-elements: `::view-transition-old(<name>)` / `::view-transition-new(<name>)` untuk custom keyframes per grup.

---

## 1. Sistem Transisi Site-Wide (Phase B.1)

### 1.1 Prinsip
Semua perpindahan **route** (yang lewat `router()` akibat `hashchange`) dibungkus satu View Transition, dengan
arah (maju/mundur) yang menentukan animasi. Reader page-flip **TIDAK disentuh** (flip internal pakai
`history.replaceState`, tidak memicu `router()`). Hormati `prefers-reduced-motion` dan fallback bila API absen.

### 1.2 Helper baru di `app.js`
```js
const REDUCE_MOTION = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
function supportsVT() { return !!document.startViewTransition && !REDUCE_MOTION; }

// depth per route → menentukan arah transisi
function routeDepth(hash) {
  const p = (hash || '#/').replace(/^#\//,'').split('/')[0];
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
```

### 1.3 Titik pemanggilan (call site) — modifikasi `router()`
`router()` saat ini: sembunyikan semua view lalu dispatch ke render function. Refactor jadi:
```js
function router() {
  runRouterVT(() => routerDispatch());   // routerDispatch = isi router() lama (hide all + panggil render fn)
}
```
`routerDispatch()` = **isi persis** fungsi `router()` yang sekarang (baris hide-all + if/else dispatch). Render
function async (`renderDetail`, `openReader`, `openListen`) dipanggil **tanpa await** di dalamnya — bagian sinkron
(set `.hidden=false`, tulis innerHTML hero) sudah cukup untuk snapshot VT; bagian async (muat TOC/isi buku) selesai
belakangan tanpa masalah.

> Catatan: `openReader`/`openListen` menampilkan overlay fixed (z-index 10) di atas library — VT tetap aman karena
> snapshot mengambil frame penuh. Untuk membuka reader, arah = forward.

### 1.4 CSS transisi root (di `styles.css`)
```css
/* durasi & easing global */
::view-transition-group(root){ animation-duration:.34s; }
@media (prefers-reduced-motion: reduce){ ::view-transition-group(*){ animation:none !important; } }

/* FORWARD: halaman baru geser-masuk dari kanan + fade; lama sedikit mengecil */
html[data-vt="forward"]::view-transition-old(root){
  animation: vt-old-out .30s cubic-bezier(.4,0,.2,1) both;
}
html[data-vt="forward"]::view-transition-new(root){
  animation: vt-in-right .34s cubic-bezier(.22,.61,.36,1) both;
}
/* BACK: kebalikannya (masuk dari kiri) */
html[data-vt="back"]::view-transition-old(root){
  animation: vt-old-out-r .30s cubic-bezier(.4,0,.2,1) both;
}
html[data-vt="back"]::view-transition-new(root){
  animation: vt-in-left .34s cubic-bezier(.22,.61,.36,1) both;
}
@keyframes vt-in-right{ from{opacity:.4; transform:translateX(28px) scale(.98);} to{opacity:1; transform:none;} }
@keyframes vt-in-left { from{opacity:.4; transform:translateX(-28px) scale(.98);} to{opacity:1; transform:none;} }
@keyframes vt-old-out { from{opacity:1;} to{opacity:0; transform:translateX(-14px) scale(.99);} }
@keyframes vt-old-out-r{ from{opacity:1;} to{opacity:0; transform:translateX(14px)  scale(.99);} }
```

### 1.5 Shared-element morph — **transisi andalan (marquee)**: cover buku → hero detail
Perlakuan istimewa hanya untuk **library/rak → detail buku** (dan sebaliknya): sampul buku yang di-tap **morph**
menjadi cover besar di hero halaman detail.

- Di HTML hero detail (fungsi `renderDetail`), cover hero sudah ada (`.detail-hero .cover`). Beri
  `style="view-transition-name:book-cover"` pada elemen cover hero itu (SATU-satunya pemilik nama di halaman detail).
- Saat sebuah `.book-card` di-tap (handler di `renderShelf` dan di panel "Karya"), **sebelum** mengubah hash:
  ```js
  btn.querySelector('.cover').style.viewTransitionName = 'book-cover';
  ```
  lalu set `location.hash`. Setelah transisi selesai, **bersihkan** nama itu agar unik lagi:
  ```js
  const t = ... // tidak selalu tersedia di call site; alternatif:
  ```
  Karena penetapan nama terjadi di card lama yang akan hilang dari DOM saat library disembunyikan, cukup aman.
  Namun untuk kembali (detail → library) tanpa duplikasi: di awal `renderLibrary`, loop bersihkan
  `.cover[style*="view-transition-name"]` → hapus properti. Sederhana & idempoten.
- Karena hanya cover yang di-tap yang bernama `book-cover`, dan hero detail juga `book-cover`, morph terjadi tepat
  antara keduanya. Cover lain (crossfade root) tidak terpengaruh.

**Author profile**: TIDAK pakai shared-element (avatar huruf vs foto hero = mismatch, risiko tinggi). Author
navigations pakai forward/back slide root + animasi `heroReveal` yang sudah ada. (Keputusan: shared-element author = **CUT**.)

**Reader/Listen**: buka = forward slide root. Page-flip internal **tidak disentuh**.

### 1.6 Transisi tab di profil penulis (enhance dari `fadeSlideUp` sekarang)
`renderAuthorPanel` menukar `#author-panel.innerHTML`. Bungkus penukaran itu dalam VT lokal + arah berdasar indeks tab:
```js
const TAB_ORDER = ['ringkasan','kisah','pengaruh','karya'];
function switchAuthorTab(newTab, doSwap){
  const dir = TAB_ORDER.indexOf(newTab) >= TAB_ORDER.indexOf(authorTab) ? 'tab-fwd' : 'tab-back';
  authorTab = newTab;
  if (!supportsVT()) { doSwap(); return; }
  document.documentElement.dataset.vt = dir;
  const t = document.startViewTransition(doSwap);
  t.finished.finally(()=> delete document.documentElement.dataset.vt);
}
```
Beri `#author-panel { view-transition-name: author-panel; }` supaya panel lama/baru jadi grup sendiri (tidak ikut root),
lalu:
```css
html[data-vt="tab-fwd"]::view-transition-old(author-panel){ animation: vt-old-out .22s both; }
html[data-vt="tab-fwd"]::view-transition-new(author-panel){ animation: vt-in-right .26s both; }
html[data-vt="tab-back"]::view-transition-old(author-panel){ animation: vt-old-out-r .22s both; }
html[data-vt="tab-back"]::view-transition-new(author-panel){ animation: vt-in-left .26s both; }
```
Stagger konten di dalam panel (life-step, chips, dsb.) tetap seperti sekarang. Karena tab bukan perubahan route,
JANGAN lewat `router()`; panggil `switchAuthorTab` dari handler tombol tab. Saat tab route (`#/penulis/...`) di-load
ulang, `authorTab` reset ke 'ringkasan' seperti sekarang.

---

## 2. Model Data Koneksi (Phase B.2)

### 2.1 Keputusan besar
- **TAMBAH** field `connections: [...]` ke tiap author di `books/authors.json`. **PERTAHANKAN** `influencedBy` /
  `influenced` (tidak dihapus) sebagai sumber + fallback. Non-destruktif.
- UI "Pengaruh"/Konstelasi membaca `connections`. Jika `connections` tidak ada untuk seorang author → fallback ke UI
  chip lama (`influencedBy`/`influenced`). Ini menjaga app tetap berfungsi meski data belum lengkap.

### 2.2 Skema `connections`
```json
"connections": [
  {
    "to": "Epictetus",             // KUNCI author.json persis, atau nama bebas bila di luar katalog
    "type": "guru",                // salah satu enum di bawah
    "inCatalog": true,             // true jika `to` == kunci authors.json (dihitung/diverifikasi)
    "note": "memperkenalkan Stoisisme lewat catatannya"  // opsional, frasa pendek Bahasa Indonesia
  }
]
```

### 2.3 Enum `type` (semantik + warna edge)
| type | arti (dari sudut pandang author ini) | warna edge | simetri reciprocal |
|------|--------------------------------------|-----------|--------------------|
| `guru` | `to` adalah guru/pengajar author ini | emas (naik) | inverse → `murid` |
| `murid` | `to` adalah murid author ini | emas (turun) | inverse → `guru` |
| `pengaruh` | ada ikatan pengaruh intelektual (arah diimplikasikan kronologi) | aksen/hijau | **simetris** → `pengaruh` |
| `sezaman` | rekan sezaman / satu lingkungan | biru | **simetris** → `sezaman` |
| `menentang` | menentang / mengkritik / berseteru | merah | **simetris** → `menentang` |
| `kolaborator` | rekan penulis / kolaborasi | ungu | **simetris** → `kolaborator` |

### 2.4 Aturan rekonsiliasi bidirectional (WAJIB, untuk graf koheren)
Hanya berlaku untuk `to` yang `inCatalog:true`:
- Jika A punya `{to:B, type:'guru'}` maka B **harus** punya `{to:A, type:'murid'}`. (dan sebaliknya)
- Jika A punya `{to:B, type:'pengaruh'|'sezaman'|'menentang'|'kolaborator'}` maka B **harus** punya `{to:A,
  type:<sama>}`.
- Larangan kontradiksi: satu pasang (A,B) tidak boleh punya dua tipe berbeda yang bentrok (mis. A→B `guru` sekaligus
  `menentang`). Bila sumber menyiratkan lebih dari satu, pilih **satu** relasi paling menonjol (guru/murid > menentang
  > pengaruh > sezaman) dan tulis nuansanya di `note`.
- Duplikat dilarang: maksimum satu edge per pasangan (A,B).

Koneksi `inCatalog:false` (nama bebas: "Neoplatonisme", "Socrates", "G.W.F. Hegel", dst.) **tidak** butuh reciprocal —
mereka node konteks satu arah (milestone di luar katalog).

### 2.5 Cara menurunkan `connections` dari data lama (tugas LLM sub-agent)
Sumber: `influencedBy` + `influenced` tiap author. Langkah:
1. **Normalisasi nama** ke kunci katalog persis. Contoh nyata: `"Aristoteles (muridnya)"` → `to:"Aristotle"`,
   `type:"murid"`, note dari "(muridnya)". `"Adam Smith dan David Ricardo"` → **dua** koneksi terpisah. Ejaan
   Indonesia→kunci EN: Aristoteles→Aristotle, Sokrates/Socrates (Socrates TIDAK di katalog → inCatalog:false), dsb.
   Cek exact-match ke daftar 77 kunci; hanya set `inCatalog:true` bila persis cocok.
2. **Ekstrak tipe dari petunjuk kurung**: "(gurunya)"→guru, "(muridnya)"→murid, "(via perseteruan)"/"(lalu
   berbalik menentang...)"→menentang, "(pendiri ...)"/"(gurunya ...)" → set tipe + pindahkan sisa ke `note`. Bersihkan
   kurung dari `to`.
3. **Tentukan tipe default**: item dari `influencedBy` yang tak berpetunjuk → `pengaruh` (author dipengaruhi `to`).
   Item dari `influenced` tanpa petunjuk → `pengaruh` juga (relasi pengaruh simetris; arah dibaca dari tahun). Bila
   petunjuk guru/murid ada, pakai itu.
4. **Gabungkan** influencedBy+influenced → dedup per `to` (bila `to` sama muncul dua arah, jadikan satu edge
   `pengaruh`, kecuali ada petunjuk guru/murid yang lebih spesifik).
5. **Rekonsiliasi seluruh 77 author** (dua-arah) sesuai §2.4. Pilih guru/murid berdasarkan tahun & konteks sejarah
   (mis. Plato `guru` Aristotle; jadi Aristotle punya `pengaruh`? tidak — Aristotle→Plato `guru`, Plato→Aristotle
   `murid`).
6. Jaga `note` **ringkas** (≤ ~8 kata), Bahasa Indonesia, opsional. Boleh kosong/absen.

### 2.6 Validator (skrip node, dijalankan sub-agent setelah pass)
Buat `tools/validate_connections.js` (boleh dihapus setelah dipakai; JANGAN di-cache SW) yang mengecek:
- Setiap `connections[].to` dengan `inCatalog:true` benar-benar kunci di authors.json.
- Reciprocity §2.4 terpenuhi untuk semua pasangan in-catalog (laporkan yang hilang/bentrok).
- Tidak ada duplikat edge.
- `type` ∈ enum.
Cetak ringkasan: jumlah edge, jumlah in-catalog vs free-text, daftar pelanggaran. Sub-agent memperbaiki sampai 0 pelanggaran.

### 2.7 Contoh nyata (Marcus Aurelius) — target output
```json
"connections": [
  { "to": "Epictetus", "type": "guru", "inCatalog": true, "note": "fondasi Stoisisme batinnya" },
  { "to": "Seneca", "type": "pengaruh", "inCatalog": true, "note": "sesama penulis Stoa" },
  { "to": "Zeno dari Citium", "type": "pengaruh", "inCatalog": false, "note": "pendiri Stoisisme" },
  { "to": "Junius Rusticus", "type": "guru", "inCatalog": false, "note": "mengenalkan catatan Epictetus" }
]
```
(Epictetus, karena in-catalog, wajib punya reciprocal `{ to:"Marcus Aurelius", type:"murid", inCatalog:true }`.)

---

## 3. "Konstelasi Pengetahuan" — UI Interaktif (Phase B.3)

### 3.1 Keputusan bentuk
- **PRIMER (in scope):** *ego-network kronologis* per author, menggantikan isi tab **"Pengaruh"** (label tab diganti
  **"Koneksi"**). SVG horizontal-scroll: author saat ini = bintang pusat; koneksi langsung = bintang lain diletakkan
  di sumbu-x menurut **tahun** mereka; edge melengkung berwarna per tipe; legenda kecil; node in-catalog bisa di-tap →
  navigasi ke profil author itu (lewat VT forward). Ini membuat "penulis sebagai milestone perjalanan ilmu" literal.
- **SEKUNDER (in scope, fidelity dibatasi):** *peta besar semua 77 author* di route baru `#/konstelasi`, dijangkau
  dari beranda library. Semua author sebagai bintang pada **satu sumbu waktu** horizontal-scroll, diwarnai per
  kategori, di-tap → profil. **Tanpa edge global** (hindari "hairball"); relasi hanya muncul di ego-view profil.
  Rasional pemangkasan ada di pre-mortem §4.
- **DICUT:** force-directed physics graph, zoom-pan gestural kompleks, edge global di peta besar. (Alasan: berat +
  kusut di 375px, risiko perf & waktu.)

### 3.2 Parser tahun (kritis — dipakai kedua view)
`years` bebas-teks. Buat `function yearToNum(years)` → integer (SM = negatif). Aturan:
- Ambil angka pertama yang bermakna "mulai/lahir".
- Deteksi "SM" (Sebelum Masehi) → negatif. "M"/Masehi atau tanpa penanda & 3-4 digit → positif.
- "abad ke-N SM" → `-(N*100 - 50)` (mis. abad ke-6 SM → -550). "abad ke-N M" → `N*100 - 50`.
- "±" / "legendaris" diabaikan (tetap parse angkanya).
- Rentang "121-180" → 121. Multi-orang "Marx 1818-..., Engels 1820-..." → 1818 (angka pertama).
- Gagal total → return `null`; node tetap dirender di posisi default (paling kanan) & tidak meng-crash.
Uji terhadap contoh nyata: `"±428-348 SM"→-428`, `"121-180 M"→121`, `"1818-1883"→1818`,
`"±abad ke-6 SM (legendaris)"→-550`, `"Marx 1818-1883, Engels 1820-1895"→1818`, `"±544-496 SM"→-544`.

### 3.3 Ego-view (tab "Koneksi") — layout & interaksi
Render `renderConstellationEgo(name, info, books)` menggantikan cabang `authorTab==='pengaruh'` (rename ke `'koneksi'`).
- **Data:** `conns = info.connections || deriveFromLegacy(info)`. Bila kosong → tampilkan pesan lama.
- **Kanvas:** `<div class="constellation-scroll">` (overflow-x:auto, -webkit-overflow-scrolling:touch) berisi satu
  `<svg>` dengan `width` dihitung dinamis, `height` ±320px.
- **Penempatan x:** kumpulkan {author saat ini} ∪ {semua `to`}. Untuk in-catalog pakai `yearToNum` dari authors.json;
  untuk free-text, pakai perkiraan dari `note`/urutan (atau letak dekat author pusat bila tak ada tahun). map
  [minYear..maxYear] → [56 .. width-56]. Spasi minimum antar node 92px → `width = max(360, span*perlu)`; kalau node
  menumpuk, lebarkan width (scrollable).
- **Penempatan y:** garis tengah `y=center`. Node pusat di center, node besar (r≈26). Koneksi didistribusi ke lajur:
  `guru`/`pengaruh`(lebih tua) condong ke atas; `murid`/(lebih muda) ke bawah; `sezaman` dekat center; hindari tumpang
  tindih dgn 2-3 lajur tiap sisi (alternasi berdasar urutan x). Node koneksi r≈18.
- **Edge:** kurva Bézier kuadratik dari pusat ke tiap node, `stroke` per tipe (§2.3), lebar 2px, opacity .7. Node
  di luar katalog: stroke putus-putus + node redup.
- **Node visual:** lingkaran isi warna kategori (in-catalog: pakai kategori buku pertama author itu; free-text: abu),
  label nama (font kecil, dipangkas) + tahun kecil di bawah. Bintang pusat diberi cincin aksen.
- **Legenda:** baris chip kecil di atas SVG memetakan warna→label ("Guru", "Murid", "Pengaruh", "Sezaman",
  "Menentang", "Kolaborator") — hanya tampilkan tipe yang benar-benar ada.
- **Interaksi:**
  - Tap node in-catalog → `setSharedNameThenNavigate` → `#/penulis/<slug>` (VT forward). (Tak perlu shared-element;
    cukup root slide.)
  - Tap node free-text → tampilkan `note` sebagai toast kecil (pakai `#toast` yang sudah ada) — tidak navigasi.
  - Tap bintang pusat → no-op (atau highlight semua edge).
  - Sumbu waktu: garis tipis horizontal + penanda abad ("500 SM", "1", "1500", "1900") di bawah, sejajar skala x.
- **Aksesibilitas:** SVG punya `role="img"` + `<title>`/`<desc>`; node in-catalog juga hadir sebagai daftar teks
  tersembunyi/visually-hidden tombol untuk keyboard/screen-reader (progressive enhancement), atau minimal fokusable.
- **prefers-reduced-motion:** matikan animasi masuk edge/node (render statis).
- **Animasi masuk (opsional, halus):** edge digambar dengan `stroke-dashoffset` animasi (draw-in) + node `popIn`
  bertahap. Ringan, CSS-only via kelas.

### 3.4 Peta besar `#/konstelasi` (sekunder)
- View baru `#view-constellation` di `index.html` (pola sama: `<main class="view" hidden>` + topbar back).
- Route di `router()`: `parts[0]==='konstelasi'` → `renderConstellationMap()`. `routeDepth`=2.
- Konten: judul "Konstelasi Pengetahuan — 77 pemikir sepanjang ±2.500 tahun", legenda kategori, lalu
  `constellation-scroll` berisi SVG semua author sebagai bintang pada sumbu waktu (x=`yearToNum`, y=lajur anti-tumpuk
  per kategori atau alternasi). Node di-tap → `#/penulis/<slug>`. Tanpa edge global.
- Entry point dari beranda: tambah tombol/kartu di `#view-library` (mis. setelah `.lib-stats` atau sebagai kartu di
  bawah header) `<a href="#/konstelasi" class="constellation-entry">✦ Jelajahi Konstelasi Pengetahuan</a>`.
- Reuse `yearToNum`, skala x, dan komponen node dari ego-view (satu modul util bersama).

### 3.5b Scroll-linked reveal (scrollytelling) — folded-in dari referensi video
Konteks: video referensi (m-f56P_L660, "Claude Fable 5 Built a $10K Website…" oleh Zubair Trabzada) ternyata BUKAN
soal transisi route SPA, melainkan situs marketing "cinematic 3D scroll" yang isinya digerakkan scroll (scrollytelling)
memakai aset video AI (MCP "Higsfield") — tooling itu TIDAK tersedia & TIDAK cocok untuk app baca sastra yang tenang.
Yang DIAMBIL hanyalah IDE UX-nya: **reveal bertahap yang terkait posisi scroll**, bukan sekadar animasi sekali saat
load. Terapkan seperlunya, ringan, tanpa aset video:
- **Ego-view & peta besar:** saat pengguna men-scroll sumbu waktu (horizontal), node & garis koneksi **draw-in
  progресif** begitu masuk viewport — pakai `IntersectionObserver` pada tiap node/edge (atau observer di sentinel
  per-node) menambah kelas `.revealed` yang memicu `popIn`/`stroke-dashoffset`→0. Ini membuat "perjalanan menyusuri
  sejarah ide" literal: milestone menyala satu per satu saat dilewati. WAJIB no-op saat `prefers-reduced-motion`.
- **Hero profil penulis (opsional, halus):** parallax ringan pada foto hero saat halaman profil di-scroll ke bawah —
  geser `object-position`/`translateY` foto sedikit relatif scrollY (via satu listener scroll ber-throttle rAF, atau
  `background-attachment`-style). Kecil, jangan berlebihan; matikan saat reduced-motion. Ini pengembangan dari
  fade+slide hero yang sudah ada.
- Implementasi harus tetap performant di Android (gunakan `transform`/`opacity` saja, hindari layout thrash;
  IntersectionObserver > scroll-handler bila memungkinkan). Ini enhancement, bukan syarat fungsional: bila observer
  tak tersedia, node/edge tampil langsung (fallback = semua `.revealed`).

### 3.5 CSS baru (ringkas, tema-aware pakai var yang ada)
Tambahkan blok `/* Konstelasi */` di `styles.css`: `.constellation-scroll{overflow-x:auto}`,
`.constellation-legend`, warna edge sebagai CSS vars `--rel-guru`, `--rel-murid`, `--rel-pengaruh`, `--rel-sezaman`,
`--rel-menentang`, `--rel-kolaborator` (definisikan di `:root` + dark). Node/label pakai `--ink`, `--card`, `--line`.
`.constellation-entry` = kartu kecil dgn ikon bintang, konsisten gaya `.continue-card`/chip.

---

## 4. Pre-mortem (Phase B.4) — apa yang paling mungkin gagal + mitigasi (sudah dibakukan di spec)

1. **Peta 77-node kusut di 375px.** → Peta besar **tanpa edge global** (nodes-only + warna kategori + tap), scroll-x
   dengan spasi longgar; ego-view hanya ~3-8 koneksi (sparse). (§3.1, §3.4)
2. **Data koneksi kontradiktif / tidak simetris.** → Aturan reciprocity eksplisit (§2.4) + **validator node**
   `tools/validate_connections.js` yang gagal bila ada pelanggaran; sub-agent perbaiki sampai 0. (§2.6)
3. **View Transitions tak didukung (Android WebView lama).** → `supportsVT()` feature-detect; fallback = swap instan
   (perilaku sekarang). Tanpa regresi fungsional. `prefers-reduced-motion` dimatikan. (§1.2)
4. **Salah normalisasi nama (Aristoteles vs Aristotle).** → Normalisasi ke kunci persis; validator cek setiap
   `inCatalog:true` benar-benar kunci. Mismatch → di-flag & diperbaiki. (§2.5, §2.6)
5. **Parser tahun rusak untuk kasus aneh (SM/±/abad/legendaris/rentang/multi-orang).** → `yearToNum` tahan-banting
   dengan fallback `null` → node tak crash; ada test-vektor eksplisit. (§3.2)
6. **Shared-element cover morph rusak karena nama ganda.** → Nama `book-cover` diset **hanya** di cover yang di-tap
   saat klik, dibersihkan saat kembali ke library; hero detail satu-satunya pemilik nama di halaman detail. (§1.5)
7. **Regresi fitur reader/listen/search/toggle.** → Reader flip pakai `replaceState` (bukan router) → tak tersentuh
   VT. Sub-agent wajib `node --check` semua .js + smoke test manual jalur: rak→detail→baca (flip)→dengar→cari→
   toggle genre/penulis→profil→tab→konstelasi.
8. **Snapshot VT membekukan interaksi/asinkron reader load.** → Callback VT hanya jalankan bagian sinkron; muat buku
   async setelah transisi. Reader menampilkan "Memuat…" seperti sekarang. (§1.3)

---

## 5. Rencana Eksekusi (Phase C) — pembagian sub-agent
- **SA-1 (data):** turunkan + rekonsiliasi `connections` untuk 77 author di `books/authors.json` (§2), buat & jalankan
  validator sampai 0 pelanggaran. **Dependency: harus selesai sebelum UI konstelasi final** (UI perlu data), tapi UI
  bisa dikembangkan paralel dgn fallback legacy.
- **SA-2 (transisi):** sistem transisi site-wide + shared-element cover + transisi tab (§1) di `app.js` + `styles.css`.
- **SA-3 (konstelasi):** `yearToNum`, ego-view (tab "Koneksi"), peta `#/konstelasi`, entry point, CSS (§3) —
  memakai data dari SA-1 (dengan fallback legacy bila belum ada).
- **Orchestrator:** review, `node --check`, smoke test (Chrome/preview bila tersedia), perbaiki, **bump SW cache
  `pustaka-v9` → `pustaka-v10`** sebagai langkah terakhir.

### Batasan keselamatan untuk SEMUA sub-agent (WAJIB diulang di prompt tiap SA)
- JANGAN sentuh `books/meditations.json`, `books/the-prince.json`, `books/art-of-war.json`, folder `books_raw/`,
  `audio/`, `audio_build/`, `preprocess.py` — struktur bab menopang manifest audio.
- JANGAN rusak fitur: page-flip reader, listen/TTS, search, toggle genre/penulis, profil penulis.
- JANGAN commit/push git. JANGAN ubah CLAUDE.md/konfigurasi.
- Verifikasi: `node --check app.js`, `node -e "JSON.parse(require('fs').readFileSync('books/authors.json'))"` valid,
  jelaskan smoke test manual yang dilakukan.
- Anti-stall: model tiering sudah disetujui user; JANGAN berhenti untuk proposal/approval — langsung eksekusi.
