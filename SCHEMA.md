# Pustaka — Locked Content Schema (v1)

Konsumen: app.js (reader). Produsen: preprocessor (books_raw/*.txt → books/*.json).

## books/index.json
```jsonc
[
  {
    "id": "meditations",            // slug, nama file
    "title": "Meditations",
    "author": "Marcus Aurelius",
    "year": "±175 M",
    "category": "filsafat",         // "sejarah"|"politik"|"sosial"|"ekonomi"|"filsafat"
    "description": "1-2 kalimat Bahasa Indonesia, menjual kenapa buku ini menarik.",
    "words": 42000,                  // total kata konten
    "chapterCount": 12,
    "file": "books/meditations.json",
    "source": "Project Gutenberg #2680 (domain publik)"
  }
]
```

## books/{id}.json
```jsonc
{
  "id": "meditations",
  "title": "Meditations",
  "author": "Marcus Aurelius",
  "chapters": [
    {
      "title": "Buku I",            // judul bab; jika tidak terdeteksi: "Bagian 1"
      "words": 3500,
      "paragraphs": ["...", "..."]  // plain text per paragraf, tanpa HTML, tanpa header/footer Gutenberg
    }
  ]
}
```

## Aturan preprocessing (WAJIB)
1. Buang semuanya sebelum baris `*** START OF ...` dan sesudah `*** END OF ...` (header/footer lisensi Gutenberg). Buang juga transcriber's notes yang jelas bukan isi.
2. Deteksi bab: baris heading (CHAPTER/BOOK/PART/SECTION/angka Romawi/ALL-CAPS pendek) dengan aturan per-buku bila perlu. Fallback: potong per ±4000 kata jadi "Bagian N".
3. Paragraf = blok teks dipisah baris kosong; gabungkan hard-wrap Gutenberg (baris dalam satu paragraf di-join dengan spasi). Normalisasi kutip/dash boleh, jangan ubah isi.
4. Buang daftar isi (TOC) di awal file jika ada — reader membuat TOC sendiri.
5. JSON harus UTF-8 tanpa BOM. Validasi: setiap buku ≥3 chapter ATAU fallback "Bagian N"; tidak ada paragraf kosong; tidak ada baris `***`.
