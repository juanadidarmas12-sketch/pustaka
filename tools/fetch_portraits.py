# -*- coding: utf-8 -*-
"""Unduh potret penulis dari Wikimedia -> assets/portraits/<slug>.jpg (2:3, ternormalisasi),
lalu arahkan field `photo` di books/authors.json ke path lokal (simpan asli di `photoSrc`).
Idempotent: aman dijalankan ulang; hanya unduh yang belum ada."""
import json, os, re, subprocess, sys, unicodedata, urllib.request, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUTH = os.path.join(ROOT, "books", "authors.json")
OUT  = os.path.join(ROOT, "assets", "portraits")
RAW  = os.path.join(OUT, "_raw")
UA   = "PustakaBot/1.0 (public-domain classics reader; contact juanadidarmas12@gmail.com)"
os.makedirs(RAW, exist_ok=True)

def slug(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    return s or "penulis"

def fetch(url, dest, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=30) as r:
                data = r.read()
            if len(data) < 3000:   # halaman error kecil
                raise ValueError("terlalu kecil (%d b)" % len(data))
            open(dest, "wb").write(data)
            return True
        except Exception as e:
            if i == tries - 1:
                print("   GAGAL:", e)
                return False
            time.sleep(1.5)

def normalize(src, dst):
    # crop-cover ke 2:3 (bias ke atas: wajah), lebar 500 -> 500x750
    vf = "scale=500:-1,crop=500:750:0:0"
    r = subprocess.run(["ffmpeg","-y","-v","error","-i",src,"-vf",vf,"-q:v","4",dst])
    if r.returncode != 0 or not os.path.exists(dst):
        # fallback: sekadar skala tanpa crop ketat
        subprocess.run(["ffmpeg","-y","-v","error","-i",src,"-vf","scale=500:-1","-q:v","4",dst])
    return os.path.exists(dst)

def main():
    authors = json.load(open(AUTH, encoding="utf-8"))
    total = len(authors); ok = 0; fail = []
    for i, (name, info) in enumerate(authors.items(), 1):
        src_url = info.get("photoSrc") or info.get("photo")
        if not src_url or not src_url.startswith("http"):
            # sudah lokal atau tak ada
            if info.get("photo","").startswith("assets/"):
                ok += 1
            continue
        sl = slug(name)
        raw = os.path.join(RAW, sl + ".img")
        jpg = os.path.join(OUT, sl + ".jpg")
        rel = "assets/portraits/" + sl + ".jpg"
        if not os.path.exists(jpg):
            print("[%d/%d] %s" % (i, total, name))
            time.sleep(1.2)  # throttle: hormati batas laju Wikimedia (hindari 429)
            if not fetch(src_url, raw):
                fail.append(name); continue
            if not normalize(raw, jpg):
                fail.append(name); continue
        # arahkan ulang ke lokal, simpan sumber asli
        info.setdefault("photoSrc", src_url)
        info["photo"] = rel
        ok += 1
    json.dump(authors, open(AUTH, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # bersihkan raw
    for f in os.listdir(RAW):
        try: os.remove(os.path.join(RAW, f))
        except OSError: pass
    try: os.rmdir(RAW)
    except OSError: pass
    print("\nSelesai: %d/%d berhasil, %d gagal." % (ok, total, len(fail)))
    if fail: print("Gagal:", fail)

if __name__ == "__main__":
    main()
