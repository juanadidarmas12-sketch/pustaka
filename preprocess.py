#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pustaka preprocessor: convert Project Gutenberg plaintext books into
chaptered JSON matching SCHEMA.md.

Windows console is cp1252 -> keep all print() output ASCII-only (AP-23).
"""
import json
import os
import re
import sys

BASE = r"C:\Users\juana\projects\pustaka"
RAW_DIR = os.path.join(BASE, "books_raw")
OUT_DIR = os.path.join(BASE, "books")

os.makedirs(OUT_DIR, exist_ok=True)

# --------------------------------------------------------------------------
# Generic utilities
# --------------------------------------------------------------------------

START_RE = re.compile(r"\*\*\* START OF[^\n]*\*\*\*\s*\n")
END_RE = re.compile(r"\*\*\* END OF[^\n]*\*\*\*")
TRANSCRIBER_RE = re.compile(
    r"^Produced by[^\n]*\n(?:[^\n]*\n)*?\n\n", re.MULTILINE
)
HTML_TAG_RE = re.compile(r"</?[a-zA-Z][a-zA-Z0-9]*\s*/?>")

SMALL_WORDS = {
    "a", "an", "the", "of", "in", "on", "at", "to", "for", "and", "or",
    "nor", "but", "by", "with", "is", "are", "from", "as", "into", "upon",
    "than", "that", "this",
}
ROMAN_ONLY_RE = re.compile(r"^[IVXLCDM]+$")


def read_raw(filename):
    path = os.path.join(RAW_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def strip_header_footer(text):
    m1 = START_RE.search(text)
    m2 = END_RE.search(text)
    if not m1 or not m2:
        raise ValueError("START/END marker not found")
    content = text[m1.end():m2.start()]
    content = TRANSCRIBER_RE.sub("", content, count=1)
    # some editions leave a stray unmarked "End of Project Gutenberg's ..."
    # line just before the real *** END OF ... *** marker; drop it.
    content = re.sub(r"(?im)^\s*End of (the )?Project Gutenberg.*$\n?", "", content)
    return content


def clean_inline(s):
    s = HTML_TAG_RE.sub("", s)
    # decorative asterisk dividers/ornaments inside authored text (e.g. an
    # epigraph's typographic break, always 3+ in a row) are not Gutenberg
    # markers; drop them. Genuine footnote markers like "**" (exactly two)
    # are left untouched.
    s = re.sub(r"\*{3,}", " ", s)
    s = re.sub(r"[ \t]+", " ", s)
    return s.strip()


def paragraphs_from_block(block):
    """Split block into paragraphs on blank lines; join hard-wrapped lines."""
    block = HTML_TAG_RE.sub("", block)
    chunks = re.split(r"\n\s*\n+", block)
    paragraphs = []
    for chunk in chunks:
        lines = [ln.strip() for ln in chunk.split("\n")]
        lines = [ln for ln in lines if ln != ""]
        if not lines:
            continue
        para = " ".join(lines)
        para = re.sub(r"[ \t]+", " ", para).strip()
        if para:
            paragraphs.append(para)
    return paragraphs


def word_count(s):
    return len(s.split())


def paragraphs_word_count(paragraphs):
    return sum(word_count(p) for p in paragraphs)


def smart_title(s):
    s = s.strip()
    s = re.sub(r"\s+", " ", s)
    s = s.rstrip(".")
    s = s.strip(" -—")
    if not s:
        return s
    words = s.split(" ")
    out = []
    for i, w in enumerate(words):
        if w == "":
            continue
        lower = w.lower()
        if i != 0 and i != len(words) - 1 and lower in SMALL_WORDS:
            out.append(lower)
            continue
        chars = list(w)
        done = False
        for idx, ch in enumerate(chars):
            if ch.isalpha():
                chars[idx] = ch.upper() if not done else ch.lower()
                done = True
        out.append("".join(chars))
    return " ".join(out)


def slice_by_anchor(text, start_pat, end_pat, search_from=0):
    """Find start_pat (end of match) .. end_pat (start of match) and return
    (content, end_index_of_end_pat_match_or_len)."""
    ms = re.search(start_pat, text[search_from:], re.MULTILINE)
    if not ms:
        raise ValueError("start anchor not found: %r" % start_pat)
    start_idx = search_from + ms.end()
    me = re.search(end_pat, text[start_idx:], re.MULTILINE)
    if not me:
        end_idx = len(text)
    else:
        end_idx = start_idx + me.start()
    return text[start_idx:end_idx], start_idx, end_idx


def read_title_no_blank_continuation(lines, idx):
    """From idx (first line after the heading number line), collect
    consecutive NON-blank lines (no blank line separates them from the
    heading) as title continuation. Stops at first blank line."""
    collected = []
    i = idx
    while i < len(lines) and lines[i].strip() != "":
        collected.append(lines[i].strip())
        i += 1
    return collected, i


def read_title_skip_one_blank(lines, idx):
    """From idx (right after heading number line, expected to be blank),
    skip blank lines, then collect the following non-blank line(s) (title)
    until the next blank line."""
    i = idx
    while i < len(lines) and lines[i].strip() == "":
        i += 1
    collected = []
    while i < len(lines) and lines[i].strip() != "":
        collected.append(lines[i].strip())
        i += 1
    return collected, i


def strip_part_suffix(title):
    title = re.sub(
        r"[\.\s]*[—-]?\s*Part\s+[IVXLCDM]+\.?\s*$",
        "", title, flags=re.IGNORECASE
    ).strip()
    title = title.rstrip(".").strip()
    return title


def dedupe_toc_matches(offsets, full_text, max_gap_lines=10):
    """offsets: list of character-offsets (start of match) in order.
    Compute line numbers, detect a dense leading run (TOC dump) and drop
    it; if the whole set is one dense run, keep only the LAST item."""
    if not offsets:
        return offsets
    line_no = [full_text.count("\n", 0, off) for off in offsets]
    # find extent of leading dense cluster
    i = 0
    while i + 1 < len(line_no) and (line_no[i + 1] - line_no[i]) <= max_gap_lines:
        i += 1
    cluster_size = i + 1
    if cluster_size >= len(offsets):
        # whole thing is one dense cluster -> keep only last (real heading)
        return offsets[-1:]
    if cluster_size >= 2:
        return offsets[cluster_size:]
    return offsets


# --------------------------------------------------------------------------
# Length management
# --------------------------------------------------------------------------

def split_long_chapter(title, paragraphs, max_words=9000, target_words=6000):
    total = paragraphs_word_count(paragraphs)
    if total <= max_words:
        return [(title, paragraphs)]
    parts = []
    current = []
    current_words = 0
    for p in paragraphs:
        pw = word_count(p)
        if current and current_words + pw > target_words:
            parts.append(current)
            current = []
            current_words = 0
        current.append(p)
        current_words += pw
    if current:
        parts.append(current)
    # merge a tiny trailing part into the previous one
    if len(parts) >= 2 and paragraphs_word_count(parts[-1]) < target_words * 0.25:
        parts[-2].extend(parts[-1])
        parts.pop()
    result = []
    for i, part_paragraphs in enumerate(parts):
        if i == 0:
            result.append((title, part_paragraphs))
        else:
            result.append((f"{title} (lanjutan {i})", part_paragraphs))
    return result


def fallback_split_bagian(all_paragraphs, per_words=4000):
    parts = []
    current = []
    current_words = 0
    for p in all_paragraphs:
        pw = word_count(p)
        if current and current_words + pw > per_words:
            parts.append(current)
            current = []
            current_words = 0
        current.append(p)
        current_words += pw
    if current:
        parts.append(current)
    return [(f"Bagian {i+1}", part) for i, part in enumerate(parts)]


# --------------------------------------------------------------------------
# Per-book extractors. Each returns list of (title, paragraphs) IN ORDER,
# BEFORE length-based splitting (applied uniformly afterward).
# --------------------------------------------------------------------------

def extract_meditations(text):
    chapters = []
    intro, _, end_idx = slice_by_anchor(
        text, r"^INTRODUCTION\s*$", r"^THE FIRST BOOK\s*$"
    )
    chapters.append(("Pengantar", paragraphs_from_block(intro)))

    word_to_roman = {
        "FIRST": "I", "SECOND": "II", "THIRD": "III", "FOURTH": "IV",
        "FIFTH": "V", "SIXTH": "VI", "SEVENTH": "VII", "EIGHTH": "VIII",
        "NINTH": "IX", "TENTH": "X", "ELEVENTH": "XI", "TWELFTH": "XII",
    }
    pat = re.compile(
        r"^THE (FIRST|SECOND|THIRD|FOURTH|FIFTH|SIXTH|SEVENTH|EIGHTH|NINTH|TENTH|ELEVENTH|TWELFTH) BOOK\s*$",
        re.MULTILINE,
    )
    matches = list(pat.finditer(text))
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        # stop before NOTES section for the last book
        notes_m = re.search(r"^NOTES\s*$", text[start:end], re.MULTILINE)
        if notes_m:
            end = start + notes_m.start()
        roman = word_to_roman[m.group(1)]
        chapters.append((f"Buku {roman}", paragraphs_from_block(text[start:end])))

    notes_m = re.search(r"^NOTES\s*$", text, re.MULTILINE)
    if notes_m:
        notes_block = text[notes_m.end():]
        chapters.append(("Catatan", paragraphs_from_block(notes_block)))
    return chapters


def extract_the_prince(text):
    chapters = []
    intro, _, _ = slice_by_anchor(text, r"^INTRODUCTION\s*$", r"^DEDICATION\s*$")
    chapters.append(("Pengantar Penerjemah", paragraphs_from_block(intro)))

    dedi, _, _ = slice_by_anchor(text, r"^DEDICATION\s*$", r"^THE PRINCE\s*$")
    chapters.append(("Persembahan", paragraphs_from_block(dedi)))

    # hard cutoff before bonus works appended in this edition
    cutoff_m = re.search(r"^DESCRIPTION OF THE METHODS ADOPTED", text, re.MULTILINE)
    hard_end = cutoff_m.start() if cutoff_m else len(text)

    pat = re.compile(r"^CHAPTER ([IVXL]+)\.(?:\[\d+\])?\s*$", re.MULTILINE)
    matches = [m for m in pat.finditer(text) if m.start() < hard_end]
    lines = text.split("\n")
    line_starts = []
    pos = 0
    for ln in lines:
        line_starts.append(pos)
        pos += len(ln) + 1

    def line_idx_of(offset):
        lo, hi = 0, len(line_starts) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if line_starts[mid] <= offset:
                lo = mid
            else:
                hi = mid - 1
        return lo

    for i, m in enumerate(matches):
        roman = m.group(1)
        head_line_idx = line_idx_of(m.start())
        cont, next_idx = read_title_no_blank_continuation(lines, head_line_idx + 1)
        title = smart_title(" ".join(cont)) if cont else f"Bab {roman}"
        content_start = line_starts[next_idx]
        content_end = matches[i + 1].start() if i + 1 < len(matches) else hard_end
        chapters.append((f"Bab {roman}: {title}", paragraphs_from_block(text[content_start:content_end])))
    return chapters


def extract_republic(text):
    chapters = []
    intro, _, _ = slice_by_anchor(text, r"^\s*INTRODUCTION AND ANALYSIS\.\s*$", r"^\s*THE REPUBLIC\.\s*$")
    # the anchor above will match the TOC one first; redo with dedupe
    pat_intro = re.compile(r"^\s*INTRODUCTION AND ANALYSIS\.\s*$", re.MULTILINE)
    intro_matches = list(pat_intro.finditer(text))
    intro_start = intro_matches[-1].end()
    pat_republic_title = re.compile(r"^\s*THE REPUBLIC\.\s*$", re.MULTILINE)
    republic_offsets = [m.start() for m in pat_republic_title.finditer(text)]
    republic_offsets = [o for o in republic_offsets if o > intro_start]
    intro_end = republic_offsets[0] if republic_offsets else len(text)
    chapters.append(("Pengantar & Analisis (Jowett)", paragraphs_from_block(text[intro_start:intro_end])))

    pat_book = re.compile(r"^\s*BOOK ([IVXL]+)\.\s*$", re.MULTILINE)
    offsets = [m.start() for m in pat_book.finditer(text)]
    offsets = dedupe_toc_matches(offsets, text)
    matches = [pat_book.match(text, o) for o in offsets]
    for i, m in enumerate(matches):
        roman = m.group(1)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        chapters.append((f"Buku {roman}", paragraphs_from_block(text[start:end])))
    return chapters


def extract_art_of_war(text):
    chapters = []
    intro, _, _ = slice_by_anchor(text, r"^Preface by Lionel Giles\s*$", r"^Chapter I\. LAYING PLANS\s*$")
    chapters.append(("Pengantar Penerjemah", paragraphs_from_block(intro)))

    pat = re.compile(r"^Chapter ([IVXL]+)\.\s+(.*)$", re.MULTILINE)
    matches = [m for m in pat.finditer(text) if m.group(2).strip().isupper() and m.group(2).strip()]
    for i, m in enumerate(matches):
        roman = m.group(1)
        title = smart_title(m.group(2))
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        chapters.append((f"Bab {roman}: {title}", paragraphs_from_block(text[start:end])))
    return chapters


def extract_communist_manifesto(text):
    pat = re.compile(r"^([IVXL]+)\.\s*$", re.MULTILINE)
    matches = list(pat.finditer(text))
    lines = text.split("\n")
    line_starts = []
    pos = 0
    for ln in lines:
        line_starts.append(pos)
        pos += len(ln) + 1

    def line_idx_of(offset):
        lo, hi = 0, len(line_starts) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if line_starts[mid] <= offset:
                lo = mid
            else:
                hi = mid - 1
        return lo

    chapters = []
    preamble_end = matches[0].start() if matches else 0
    preamble_paras = paragraphs_from_block(text[:preamble_end])

    for i, m in enumerate(matches):
        roman = m.group(1)
        head_line_idx = line_idx_of(m.start())
        cont, next_idx = read_title_no_blank_continuation(lines, head_line_idx + 1)
        title = smart_title(" ".join(cont)) if cont else roman
        content_start = line_starts[next_idx]
        content_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        paras = paragraphs_from_block(text[content_start:content_end])
        if i == 0:
            paras = preamble_paras + paras
        chapters.append((f"Bab {roman}: {title}", paras))
    return chapters


def extract_on_liberty(text):
    chapters = []
    ded_start_m = re.search(r"_To the beloved and deplored memory", text)
    intro_end_m = re.search(r"^CHAPTER I\.\s*$", text, re.MULTILINE)
    intro_start = ded_start_m.start() if ded_start_m else 0
    # need the REAL Chapter I (dedupe against TOC)
    pat_ch = re.compile(r"^CHAPTER ([IVXL]+)\.\s*$", re.MULTILINE)
    offsets = [m.start() for m in pat_ch.finditer(text)]
    offsets = dedupe_toc_matches(offsets, text)
    intro_end = offsets[0]
    chapters.append(("Pengantar", paragraphs_from_block(text[intro_start:intro_end])))

    matches = [pat_ch.match(text, o) for o in offsets]
    lines = text.split("\n")
    line_starts = []
    pos = 0
    for ln in lines:
        line_starts.append(pos)
        pos += len(ln) + 1

    def line_idx_of(offset):
        lo, hi = 0, len(line_starts) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if line_starts[mid] <= offset:
                lo = mid
            else:
                hi = mid - 1
        return lo

    for i, m in enumerate(matches):
        roman = m.group(1)
        head_line_idx = line_idx_of(m.start())
        cont, next_idx = read_title_skip_one_blank(lines, head_line_idx + 1)
        title = smart_title(" ".join(cont)) if cont else roman
        content_start = line_starts[next_idx]
        content_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        chapters.append((f"Bab {roman}: {title}", paragraphs_from_block(text[content_start:content_end])))
    return chapters


def extract_wealth_of_nations(text):
    chapters = []
    intro, _, _ = slice_by_anchor(
        text, r"^INTRODUCTION AND PLAN OF THE WORK\.\s*$", r"^BOOK I\.\s*$"
    )
    chapters.append(("Pendahuluan: Rencana Karya Ini", paragraphs_from_block(intro)))

    lines = text.split("\n")
    line_starts = []
    pos = 0
    for ln in lines:
        line_starts.append(pos)
        pos += len(ln) + 1

    def line_idx_of(offset):
        lo, hi = 0, len(line_starts) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if line_starts[mid] <= offset:
                lo = mid
            else:
                hi = mid - 1
        return lo

    pat_book = re.compile(r"^BOOK ([IVXL]+)\.\s*$", re.MULTILINE)
    pat_chap = re.compile(r"^CHAPTER ([IVXL]+)\.\s*$", re.MULTILINE)
    book_matches = list(pat_book.finditer(text))
    chap_matches = list(pat_chap.finditer(text))

    for bi, bm in enumerate(book_matches):
        book_roman = bm.group(1)
        b_head_idx = line_idx_of(bm.start())
        b_cont, b_next_idx = read_title_no_blank_continuation(lines, b_head_idx + 1)
        book_start = line_starts[b_next_idx]
        book_end = book_matches[bi + 1].start() if bi + 1 < len(book_matches) else len(text)

        book_chaps = [cm for cm in chap_matches if book_start <= cm.start() < book_end]
        if not book_chaps:
            continue
        # any text between book_start and first chapter heading -> prepend to first chapter
        pre_text = text[book_start:book_chaps[0].start()]

        for ci, cm in enumerate(book_chaps):
            chap_roman = cm.group(1)
            c_head_idx = line_idx_of(cm.start())
            c_cont, c_next_idx = read_title_no_blank_continuation(lines, c_head_idx + 1)
            c_title = smart_title(" ".join(c_cont)) if c_cont else chap_roman
            content_start = line_starts[c_next_idx]
            content_end = book_chaps[ci + 1].start() if ci + 1 < len(book_chaps) else book_end
            paras = paragraphs_from_block(text[content_start:content_end])
            if ci == 0 and pre_text.strip():
                paras = paragraphs_from_block(pre_text) + paras
            title = f"Buku {book_roman} — Bab {chap_roman}: {c_title}"
            chapters.append((title, paras))
    return chapters


def extract_beyond_good_and_evil(text):
    chapters = []
    intro, _, _ = slice_by_anchor(text, r"^PREFACE\s*$", r"^CHAPTER I\.\s+PREJUDICES OF PHILOSOPHERS\s*$")
    chapters.append(("Kata Pengantar", paragraphs_from_block(intro)))

    poem_m = re.search(r"^FROM THE HEIGHTS\s*$", text, re.MULTILINE)
    hard_end = poem_m.start() if poem_m else len(text)

    pat = re.compile(r"^CHAPTER ([IVXL]+):?\.?\s+(.*)$", re.MULTILINE)
    matches = [m for m in pat.finditer(text) if m.group(2).strip().isupper() and m.start() < hard_end]
    for i, m in enumerate(matches):
        roman = m.group(1)
        title = smart_title(m.group(2))
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else hard_end
        chapters.append((f"Bab {roman}: {title}", paragraphs_from_block(text[start:end])))

    if poem_m:
        poem_block = text[poem_m.end():]
        chapters.append(("From the Heights (Puisi Penutup)", paragraphs_from_block(poem_block)))
    return chapters


def extract_second_treatise(text):
    chapters = []
    intro, _, _ = slice_by_anchor(text, r"^PREFACE\s*$", r"^Book II\s*$")
    chapters.append(("Kata Pengantar", paragraphs_from_block(intro)))

    lines = text.split("\n")
    line_starts = []
    pos = 0
    for ln in lines:
        line_starts.append(pos)
        pos += len(ln) + 1

    def line_idx_of(offset):
        lo, hi = 0, len(line_starts) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if line_starts[mid] <= offset:
                lo = mid
            else:
                hi = mid - 1
        return lo

    pat = re.compile(r"^CHAPTER\.\s+([IVXL]+)\.\s*$", re.MULTILINE)
    matches = list(pat.finditer(text))
    for i, m in enumerate(matches):
        roman = m.group(1)
        head_line_idx = line_idx_of(m.start())
        cont, next_idx = read_title_skip_one_blank(lines, head_line_idx + 1)
        title = smart_title(" ".join(cont)) if cont else roman
        content_start = line_starts[next_idx]
        content_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        chapters.append((f"Bab {roman}: {title}", paragraphs_from_block(text[content_start:content_end])))
    return chapters


def extract_utopia(text):
    chapters = []
    intro, _, _ = slice_by_anchor(
        text, r"^INTRODUCTION\s*$",
        r"^DISCOURSES OF RAPHAEL HYTHLODAY, OF THE BEST STATE OF A COMMONWEALTH\s*$",
    )
    chapters.append(("Pengantar", paragraphs_from_block(intro)))

    headers = [
        "DISCOURSES OF RAPHAEL HYTHLODAY, OF THE BEST STATE OF A COMMONWEALTH",
        "OF THEIR TOWNS, PARTICULARLY OF AMAUROT",
        "OF THEIR MAGISTRATES",
        "OF THEIR TRADES, AND MANNER OF LIFE",
        "OF THEIR TRAFFIC",
        "OF THE TRAVELLING OF THE UTOPIANS",
        "OF THEIR SLAVES, AND OF THEIR MARRIAGES",
        "OF THEIR MILITARY DISCIPLINE",
        "OF THE RELIGIONS OF THE UTOPIANS",
    ]
    offsets = []
    for h in headers:
        m = re.search(r"^" + re.escape(h) + r"\s*$", text, re.MULTILINE)
        offsets.append(m.start() if m else None)

    for i, off in enumerate(offsets):
        if off is None:
            continue
        m = re.match(r"^" + re.escape(headers[i]) + r"\s*$", text[off:], re.MULTILINE)
        start = off + m.end()
        end = offsets[i + 1] if (i + 1 < len(offsets) and offsets[i + 1] is not None) else len(text)
        content = paragraphs_from_block(text[start:end])
        if i == 0:
            title = f"Buku I: {smart_title(headers[0])}"
        else:
            title = f"Buku II — Bab {i}: {smart_title(headers[i])}"
        chapters.append((title, content))
    return chapters


def extract_democracy_in_america(text):
    chapters = []
    intro, _, _ = slice_by_anchor(text, r"^\s*Introductory Chapter\s*$", r"^\s*Chapter I:")
    # dedupe the intro anchor (TOC has "Introductory Chapter" too)
    pat_intro = re.compile(r"^\s*Introductory Chapter\s*$", re.MULTILINE)
    intro_m = list(pat_intro.finditer(text))[-1]

    pat_ch = re.compile(r"^[ \t]?Chapter ([IVXL]+):[ \t]?(.*)$", re.MULTILINE)
    offsets = [m.start() for m in pat_ch.finditer(text)]
    offsets = dedupe_toc_matches(offsets, text)
    intro_end = offsets[0]
    chapters.append(("Pendahuluan (Introductory Chapter)", paragraphs_from_block(text[intro_m.end():intro_end])))

    matches = [pat_ch.match(text, o) for o in offsets]
    lines = text.split("\n")
    line_starts = []
    pos = 0
    for ln in lines:
        line_starts.append(pos)
        pos += len(ln) + 1

    def line_idx_of(offset):
        lo, hi = 0, len(line_starts) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if line_starts[mid] <= offset:
                lo = mid
            else:
                hi = mid - 1
        return lo

    grouped = []  # list of [roman, title, [content_pieces]]
    for i, m in enumerate(matches):
        roman = m.group(1)
        head_line_idx = line_idx_of(m.start())
        cont, next_idx = read_title_no_blank_continuation(lines, head_line_idx + 1)
        raw_title = (m.group(2).strip() + " " + " ".join(cont)).strip()
        clean_title = strip_part_suffix(raw_title)
        content_start = line_starts[next_idx]
        content_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        content = text[content_start:content_end]
        if grouped and grouped[-1][0] == roman:
            grouped[-1][2].append(content)
            if clean_title and len(clean_title) > len(grouped[-1][1]):
                grouped[-1][1] = clean_title
        else:
            grouped.append([roman, clean_title, [content]])

    for roman, title, pieces in grouped:
        title_disp = smart_title(title) if title else roman
        paras = []
        for piece in pieces:
            paras.extend(paragraphs_from_block(piece))
        # source formatting oddity: a stray one-word title fragment (e.g.
        # "States") can land as the first "paragraph" when a title wraps
        # across a double blank line; fold it back into the title.
        if paras and paras[0].isalpha() and paras[0][:1].isupper() and len(paras[0]) <= 20:
            title_disp = f"{title_disp} {paras[0]}".strip()
            paras = paras[1:]
        chapters.append((f"Bab {roman}: {title_disp}", paras))
    return chapters


def extract_decline_and_fall(text):
    chapters = []
    intro, _, _ = slice_by_anchor(
        text, r"^ {6}Preface By The Editor\.\s*$", r"^ {6}Chapter I: "
    )
    chapters.append(("Prakata", paragraphs_from_block(intro)))

    pat = re.compile(r"^ {6}Chapter ([IVXL]+): ?(.*)$", re.MULTILINE)
    matches = list(pat.finditer(text))
    lines = text.split("\n")
    line_starts = []
    pos = 0
    for ln in lines:
        line_starts.append(pos)
        pos += len(ln) + 1

    def line_idx_of(offset):
        lo, hi = 0, len(line_starts) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if line_starts[mid] <= offset:
                lo = mid
            else:
                hi = mid - 1
        return lo

    grouped = []
    for i, m in enumerate(matches):
        roman = m.group(1)
        head_line_idx = line_idx_of(m.start())
        cont, next_idx = read_title_no_blank_continuation(lines, head_line_idx + 1)
        raw_title = (m.group(2).strip() + " " + " ".join(cont)).strip()
        clean_title = strip_part_suffix(raw_title)
        content_start = line_starts[next_idx]
        content_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        content = text[content_start:content_end]
        if grouped and grouped[-1][0] == roman:
            grouped[-1][2].append(content)
            if clean_title and len(clean_title) > len(grouped[-1][1]):
                grouped[-1][1] = clean_title
        else:
            grouped.append([roman, clean_title, [content]])

    for roman, title, pieces in grouped:
        title_disp = smart_title(title) if title else roman
        paras = []
        for piece in pieces:
            paras.extend(paragraphs_from_block(piece))
        chapters.append((f"Bab {roman}: {title_disp}", paras))
    return chapters


def extract_leviathan(text):
    chapters = []
    ded, _, _ = slice_by_anchor(
        text, r"^TO MY MOST HONOR.D FRIEND.*$", r"^CONTENTS OF THE CHAPTERS\s*$"
    )
    chapters.append(("Persembahan", paragraphs_from_block(ded)))

    intro, _, _ = slice_by_anchor(text, r"^THE INTRODUCTION\s*$", r"^CHAPTER I\. ")
    chapters.append(("Pengantar", paragraphs_from_block(intro)))

    review_m = re.search(r"^A REVIEW, AND CONCLUSION\s*$", text, re.MULTILINE)
    hard_end = review_m.start() if review_m else len(text)

    pat = re.compile(r"^CHAPTER ([IVXL]+)\.? ?(.*)$", re.MULTILINE)
    matches = [m for m in pat.finditer(text) if m.start() < hard_end]

    lines = text.split("\n")
    line_starts = []
    pos = 0
    for ln in lines:
        line_starts.append(pos)
        pos += len(ln) + 1

    def line_idx_of(offset):
        lo, hi = 0, len(line_starts) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if line_starts[mid] <= offset:
                lo = mid
            else:
                hi = mid - 1
        return lo

    for i, m in enumerate(matches):
        roman = m.group(1)
        head_line_idx = line_idx_of(m.start())
        cont, next_idx = read_title_no_blank_continuation(lines, head_line_idx + 1)
        inline_title = m.group(2).strip()
        combined = (inline_title + " " + " ".join(cont)).strip()
        title = smart_title(combined) if combined else roman
        content_start = line_starts[next_idx]
        content_end = matches[i + 1].start() if i + 1 < len(matches) else hard_end
        chapters.append((f"Bab {roman}: {title}", paragraphs_from_block(text[content_start:content_end])))

    if review_m:
        review_block = text[review_m.end():]
        review_block = re.sub(r"\n\s*FINIS\.?\s*$", "", review_block)
        chapters.append(("Tinjauan dan Kesimpulan", paragraphs_from_block(review_block)))
    return chapters


def extract_common_sense(text):
    chapters = []
    intro, _, _ = slice_by_anchor(
        text, r"^INTRODUCTION\.\s*$",
        r"OF THE ORIGIN AND DESIGN OF GOVERNMENT IN GENERAL,\nWITH CONCISE REMARKS ON THE ENGLISH CONSTITUTION\.",
    )
    chapters.append(("Pengantar", paragraphs_from_block(intro)))

    headers = [
        "OF THE ORIGIN AND DESIGN OF GOVERNMENT IN GENERAL,\nWITH CONCISE REMARKS ON THE ENGLISH CONSTITUTION.",
        "OF MONARCHY AND HEREDITARY SUCCESSION.",
        "THOUGHTS ON THE PRESENT STATE OF AMERICAN AFFAIRS.",
        "OF THE PRESENT ABILITY OF AMERICA,\nWITH SOME MISCELLANEOUS REFLEXIONS.",
        "APPENDIX.",
    ]
    titles_disp = [
        "Asal Usul dan Rancangan Pemerintahan pada Umumnya, dengan Catatan Ringkas tentang Konstitusi Inggris",
        "Tentang Monarki dan Suksesi Turun-Temurun",
        "Renungan tentang Keadaan Terkini Urusan Amerika",
        "Tentang Kemampuan Amerika Saat Ini, dengan Beberapa Renungan Tambahan",
        "Lampiran",
    ]
    hard_end_m = re.search(r"^F {2}I {2}N {2}I {2}S\.\s*$", text, re.MULTILINE)
    hard_end = hard_end_m.start() if hard_end_m else len(text)

    offsets = []
    for h in headers:
        m = re.search(re.escape(h), text)
        offsets.append(m.end() if m else None)

    for i, start in enumerate(offsets):
        if start is None:
            continue
        end = offsets[i + 1] if (i + 1 < len(offsets) and offsets[i + 1] is not None) else hard_end
        # offsets[i+1] is the END of next header's match, not its start;
        # recompute actual next-header start for slicing purposes.
        if i + 1 < len(offsets) and offsets[i + 1] is not None:
            next_m = re.search(re.escape(headers[i + 1]), text)
            end = next_m.start()
        else:
            end = hard_end
        chapters.append((titles_disp[i], paragraphs_from_block(text[start:end])))
    return chapters


def extract_tao_te_ching(text):
    pat = re.compile(r"^(?:Ch\. )?(\d+)\.(.*)$", re.MULTILINE)
    cands = [(m.start(), int(m.group(1)), m.group(2)) for m in pat.finditer(text)]

    expected_section = 1
    next_verse_expected = None
    section_starts = {}
    for offset, n, remainder in cands:
        is_embedded = bool(re.match(r"^\s*1\.\s", remainder))
        if n == expected_section and is_embedded:
            section_starts[n] = offset
            expected_section = n + 1
            next_verse_expected = 2
        elif next_verse_expected is not None and n == next_verse_expected:
            next_verse_expected += 1
        elif n == expected_section:
            section_starts[n] = offset
            expected_section = n + 1
            next_verse_expected = 1
        # else: noise (a verse number that doesn't continue the chain)

    missing = sorted(set(range(1, 82)) - set(section_starts))
    if missing:
        raise ValueError("Tao Te Ching: missing sections %r" % missing)

    chapters = []
    group_size = 9
    for g in range(0, 81, group_size):
        group_nums = list(range(g + 1, min(g + group_size, 81) + 1))
        start = section_starts[group_nums[0]]
        end = section_starts[group_nums[-1] + 1] if group_nums[-1] < 81 else len(text)
        title = f"Bab {group_nums[0]}-{group_nums[-1]}"
        chapters.append((title, paragraphs_from_block(text[start:end])))
    return chapters


def extract_walden(text):
    chapters = []
    titles = [
        "Economy", "Where I Lived, and What I Lived For", "Reading", "Sounds",
        "Solitude", "Visitors", "The Bean-Field", "The Village", "The Ponds",
        "Baker Farm", "Higher Laws", "Brute Neighbors", "House-Warming",
        "Former Inhabitants and Winter Visitors", "Winter Animals",
        "The Pond in Winter", "Spring", "Conclusion",
    ]
    civil_matches = [m.start() for m in re.finditer(
        r"^ON THE DUTY OF CIVIL DISOBEDIENCE\s*$", text, re.MULTILINE)]
    civil_start = civil_matches[-1]

    offsets = []
    for t in titles:
        m = re.search(r"^" + re.escape(t) + r"\s*$", text, re.MULTILINE)
        offsets.append(m.start() if m else None)

    for i, off in enumerate(offsets):
        if off is None:
            continue
        m = re.match(r"^" + re.escape(titles[i]) + r"\s*$", text[off:], re.MULTILINE)
        start = off + m.end()
        end = offsets[i + 1] if (i + 1 < len(offsets) and offsets[i + 1] is not None) else civil_start
        chapters.append((f"Bab {i + 1}: {titles[i]}", paragraphs_from_block(text[start:end])))

    civil_content = text[civil_start:]
    m2 = re.match(r"^ON THE DUTY OF CIVIL DISOBEDIENCE\s*$", civil_content, re.MULTILINE)
    civil_body = civil_content[m2.end():]
    civil_body = re.sub(r"\n\s*THE END\s*$", "", civil_body)
    chapters.append((f"Bab {len(titles) + 1}: On the Duty of Civil Disobedience", paragraphs_from_block(civil_body)))
    return chapters


def extract_political_economy(text):
    chapters = []
    preface, _, _ = slice_by_anchor(text, r"^PREFACE\.\s*$", r"^CHAPTER I\.\s*$")
    chapters.append(("Prakata", paragraphs_from_block(preface)))

    hard_end_m = re.search(r"^THE END\.\s*$", text, re.MULTILINE)
    hard_end = hard_end_m.start() if hard_end_m else len(text)

    pat = re.compile(r"^CHAPTER ([IVXL]+\*?)\.\s*$", re.MULTILINE)
    matches = [m for m in pat.finditer(text) if m.start() < hard_end]

    lines = text.split("\n")
    line_starts = []
    pos = 0
    for ln in lines:
        line_starts.append(pos)
        pos += len(ln) + 1

    def line_idx_of(offset):
        lo, hi = 0, len(line_starts) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if line_starts[mid] <= offset:
                lo = mid
            else:
                hi = mid - 1
        return lo

    seen_labels = {}
    for i, m in enumerate(matches):
        roman = m.group(1)
        head_line_idx = line_idx_of(m.start())
        cont, next_idx = read_title_skip_one_blank(lines, head_line_idx + 1)
        title = smart_title(" ".join(cont)) if cont else roman
        content_start = line_starts[next_idx]
        content_end = matches[i + 1].start() if i + 1 < len(matches) else hard_end
        label = roman.rstrip("*")
        count = seen_labels.get(label, 0) + 1
        seen_labels[label] = count
        disp_roman = roman if count == 1 else f"{label} (lanjutan penomoran asli)"
        chapters.append((f"Bab {disp_roman}: {title}", paragraphs_from_block(text[content_start:content_end])))
    return chapters


def extract_leisure_class(text):
    chapters = []
    word_to_num = {
        "One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5, "Six": 6,
        "Seven": 7, "Eight": 8, "Nine": 9, "Ten": 10, "Eleven": 11,
        "Twelve": 12, "Thirteen": 13, "Fourteen": 14,
    }
    pat = re.compile(r"^Chapter (\w+) ~~ (.*)$", re.MULTILINE)
    matches = list(pat.finditer(text))

    lines = text.split("\n")
    line_starts = []
    pos = 0
    for ln in lines:
        line_starts.append(pos)
        pos += len(ln) + 1

    def line_idx_of(offset):
        lo, hi = 0, len(line_starts) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if line_starts[mid] <= offset:
                lo = mid
            else:
                hi = mid - 1
        return lo

    for i, m in enumerate(matches):
        num = word_to_num.get(m.group(1), i + 1)
        head_line_idx = line_idx_of(m.start())
        cont, next_idx = read_title_no_blank_continuation(lines, head_line_idx + 1)
        combined = (m.group(2).strip() + " " + " ".join(cont)).strip()
        title = smart_title(combined) if combined else str(num)
        content_start = line_starts[next_idx]
        content_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        chapters.append((f"Bab {num}: {title}", paragraphs_from_block(text[content_start:content_end])))
    return chapters


def extract_herodotus(text):
    chapters = []
    preface, _, _ = slice_by_anchor(text, r"^PREFACE\s*$", r"^BOOK I\. ")
    chapters.append(("Prakata Penerjemah", paragraphs_from_block(preface)))

    pat = re.compile(r"^BOOK ([IVXL]+)\. (.*)$", re.MULTILINE)
    matches = list(pat.finditer(text))
    for i, m in enumerate(matches):
        roman = m.group(1)
        title = smart_title(m.group(2))
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        chapters.append((f"Buku {roman}: {title}", paragraphs_from_block(text[start:end])))
    return chapters


def extract_peloponnesian_war(text):
    chapters = []
    pat_book = re.compile(r"^BOOK ([IVXL]+)\s*$", re.MULTILINE)
    pat_chap = re.compile(r"^CHAPTER ([IVXL]+)\s*$", re.MULTILINE)
    book_matches = list(pat_book.finditer(text))
    chap_matches = list(pat_chap.finditer(text))

    lines = text.split("\n")
    line_starts = []
    pos = 0
    for ln in lines:
        line_starts.append(pos)
        pos += len(ln) + 1

    def line_idx_of(offset):
        lo, hi = 0, len(line_starts) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if line_starts[mid] <= offset:
                lo = mid
            else:
                hi = mid - 1
        return lo

    for bi, bm in enumerate(book_matches):
        book_roman = bm.group(1)
        book_start = bm.end()
        book_end = book_matches[bi + 1].start() if bi + 1 < len(book_matches) else len(text)
        book_chaps = [cm for cm in chap_matches if book_start <= cm.start() < book_end]
        for ci, cm in enumerate(book_chaps):
            chap_roman = cm.group(1)
            head_line_idx = line_idx_of(cm.start())
            cont, next_idx = read_title_skip_one_blank(lines, head_line_idx + 1)
            title = smart_title(" ".join(cont)) if cont else chap_roman
            content_start = line_starts[next_idx]
            content_end = book_chaps[ci + 1].start() if ci + 1 < len(book_chaps) else book_end
            chapters.append((
                f"Buku {book_roman} — Bab {chap_roman}: {title}",
                paragraphs_from_block(text[content_start:content_end]),
            ))
    return chapters


def extract_souls_of_black_folk(text):
    chapters = []
    fore, _, _ = slice_by_anchor(text, r"^The Forethought\s*$", r"^I\.\s*$")
    chapters.append(("Kata Pembuka (The Forethought)", paragraphs_from_block(fore)))

    after_m = re.search(r"^The Afterthought\s*$", text, re.MULTILINE)
    hard_end = after_m.start() if after_m else len(text)

    pat = re.compile(r"^([IVXL]+)\.\s*$", re.MULTILINE)
    matches = [m for m in pat.finditer(text) if m.start() < hard_end]

    lines = text.split("\n")
    line_starts = []
    pos = 0
    for ln in lines:
        line_starts.append(pos)
        pos += len(ln) + 1

    def line_idx_of(offset):
        lo, hi = 0, len(line_starts) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if line_starts[mid] <= offset:
                lo = mid
            else:
                hi = mid - 1
        return lo

    for i, m in enumerate(matches):
        roman = m.group(1)
        head_line_idx = line_idx_of(m.start())
        cont, next_idx = read_title_no_blank_continuation(lines, head_line_idx + 1)
        title = smart_title(" ".join(cont)) if cont else roman
        content_start = line_starts[next_idx]
        content_end = matches[i + 1].start() if i + 1 < len(matches) else hard_end
        chapters.append((f"Bab {roman}: {title}", paragraphs_from_block(text[content_start:content_end])))

    if after_m:
        after_block = text[after_m.end():]
        after_block = re.sub(r"\n\s*THE END\s*$", "", after_block)
        chapters.append(("Kata Penutup (The Afterthought)", paragraphs_from_block(after_block)))
    return chapters


def extract_rights_of_woman(text):
    chapters = []
    bio, _, _ = slice_by_anchor(
        text, r"^A BRIEF SKETCH OF THE LIFE OF MARY WOLLSTONECRAFT\.\s*$",
        r"^INTRODUCTION\.\s*$",
    )
    chapters.append(("Sketsa Biografi Mary Wollstonecraft", paragraphs_from_block(bio)))

    intro, _, _ = slice_by_anchor(text, r"^INTRODUCTION\.\s*$", r"^CHAPTER 1\.\s*$")
    chapters.append(("Pengantar", paragraphs_from_block(intro)))

    pat = re.compile(r"^CHAPTER (\d+)\.\s*$", re.MULTILINE)
    matches = list(pat.finditer(text))

    lines = text.split("\n")
    line_starts = []
    pos = 0
    for ln in lines:
        line_starts.append(pos)
        pos += len(ln) + 1

    def line_idx_of(offset):
        lo, hi = 0, len(line_starts) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if line_starts[mid] <= offset:
                lo = mid
            else:
                hi = mid - 1
        return lo

    for i, m in enumerate(matches):
        num = m.group(1)
        head_line_idx = line_idx_of(m.start())
        cont, next_idx = read_title_skip_one_blank(lines, head_line_idx + 1)
        title = smart_title(" ".join(cont)) if cont else num
        content_start = line_starts[next_idx]
        content_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        chapters.append((f"Bab {num}: {title}", paragraphs_from_block(text[content_start:content_end])))
    return chapters


# --------------------------------------------------------------------------
# Book registry
# --------------------------------------------------------------------------

BOOKS = [
    dict(id="meditations", raw="pg2680.txt", gid=2680, title="Meditations",
         author="Marcus Aurelius", year="±175 M", category="filsafat",
         extractor=extract_meditations,
         description="Catatan pribadi seorang kaisar Romawi untuk dirinya sendiri, berisi renungan Stoic tentang cara menjalani hidup dengan tenang di tengah kekuasaan dan kefanaan. Dua ribu tahun kemudian, isinya masih terasa seperti panduan praktis mengelola pikiran di hari yang buruk."),
    dict(id="the-prince", raw="pg1232.txt", gid=1232, title="The Prince",
         author="Niccolò Machiavelli", year="1532", category="politik",
         extractor=extract_the_prince,
         description="Panduan mentah dan tanpa basa-basi tentang cara merebut serta mempertahankan kekuasaan, yang mengubah nama Machiavelli sendiri menjadi julukan abadi untuk politik realis. Lebih jujur daripada nyaman dibaca."),
    dict(id="republic", raw="pg1497.txt", gid=1497, title="The Republic",
         author="Plato", year="±375 SM", category="filsafat",
         extractor=extract_republic,
         description="Dialog Sokratik yang menggali makna keadilan lewat rancangan negara ideal, dari alegori gua sampai gagasan raja-filsuf yang masih diperdebatkan hingga sekarang. Salah satu fondasi filsafat Barat yang paling sering dikutip, jarang benar-benar dibaca utuh."),
    dict(id="art-of-war", raw="pg132.txt", gid=132, title="The Art of War",
         author="Sun Tzu", year="±500 SM", category="sejarah",
         extractor=extract_art_of_war,
         description="Risalah strategi militer Tiongkok kuno yang kini lebih sering dikutip di ruang rapat dan lapangan olahraga ketimbang medan perang. Padat, taktis, dan mengejutkan relevan untuk apa pun yang melibatkan lawan dan sumber daya terbatas."),
    dict(id="communist-manifesto", raw="pg61.txt", gid=61, title="The Communist Manifesto",
         author="Karl Marx & Friedrich Engels", year="1848", category="politik",
         extractor=extract_communist_manifesto,
         description="Pamflet politik paling berpengaruh (dan paling ditakuti) abad ke-19, yang meletakkan dasar analisis kelas dan ikut menyulut gerakan-gerakan yang mengubah wajah dunia. Singkat, tapi bahannya berat."),
    dict(id="on-liberty", raw="pg34901.txt", gid=34901, title="On Liberty",
         author="John Stuart Mill", year="1859", category="politik",
         extractor=extract_on_liberty,
         description="Argumen paling tajam tentang mengapa masyarakat, bukan cuma negara, bisa mengancam kebebasan individu, dan mengapa membiarkan ide yang salah tetap boleh bicara itu penting. Klasik liberal yang jadi rujukan wajib perdebatan kebebasan berpendapat."),
    dict(id="wealth-of-nations", raw="pg3300.txt", gid=3300, title="The Wealth of Nations",
         author="Adam Smith", year="1776", category="ekonomi",
         extractor=extract_wealth_of_nations,
         description="Buku yang meletakkan fondasi ilmu ekonomi modern lewat gagasan pembagian kerja dan 'tangan tak kelihatan' pasar, ditulis di tahun yang sama dengan kemerdekaan Amerika. Panjang, tapi argumennya masih dipakai untuk membela dan menyerang kapitalisme sampai hari ini."),
    dict(id="beyond-good-and-evil", raw="pg4363.txt", gid=4363, title="Beyond Good and Evil",
         author="Friedrich Nietzsche", year="1886", category="filsafat",
         extractor=extract_beyond_good_and_evil,
         description="Serangan telak Nietzsche terhadap moralitas konvensional dan filsafat sebelumnya, ditulis dalam aforisme tajam yang menuntut pembaca berpikir ulang soal benar dan salah. Bukan bacaan santai, tapi sulit dilupakan."),
    dict(id="second-treatise", raw="pg7370.txt", gid=7370, title="Second Treatise of Government",
         author="John Locke", year="1689", category="politik",
         extractor=extract_second_treatise,
         description="Argumen fondasional tentang hak alami, hak milik, dan pemerintahan atas persetujuan yang rakyatnya perintah, teks yang ikut menginspirasi Deklarasi Kemerdekaan Amerika. Akar dari banyak ide yang kini dianggap common sense."),
    dict(id="utopia", raw="pg2130.txt", gid=2130, title="Utopia",
         author="Thomas More", year="1516", category="sosial",
         extractor=extract_utopia,
         description="Kisah pulau khayalan yang menciptakan kata 'utopia' itu sendiri, sekaligus sindiran tajam More terhadap ketimpangan sosial Eropa abad ke-16. Separuh satire, separuh cetak biru masyarakat ideal, dan tetap bikin bingung mana yang dia maksud sungguhan."),
    dict(id="democracy-in-america", raw="pg815.txt", gid=815, title="Democracy in America (Vol. 1)",
         author="Alexis de Tocqueville", year="1835", category="sosial",
         extractor=extract_democracy_in_america,
         description="Catatan perjalanan seorang bangsawan Prancis muda yang berkembang jadi salah satu analisis paling tajam tentang demokrasi, kesetaraan, dan bahaya tirani mayoritas. Ditulis oleh orang luar, tapi lebih memahami Amerika daripada banyak orang dalam."),
    dict(id="decline-and-fall", raw="pg731.txt", gid=731, title="The Decline and Fall of the Roman Empire (Vol. 1)",
         author="Edward Gibbon", year="1776", category="sejarah",
         extractor=extract_decline_and_fall,
         description="Kisah epik kemunduran Kekaisaran Romawi sejak puncak kejayaan Zaman Antonine, ditulis dengan gaya prosa begitu megah hingga jadi standar penulisan sejarah selama dua abad. Vol. 1 ini saja sudah cukup panjang untuk membuktikan betapa ambisiusnya proyek Gibbon."),
    dict(id="leviathan", raw="pg3207.txt", gid=3207, title="Leviathan",
         author="Thomas Hobbes", year="1651", category="politik",
         extractor=extract_leviathan,
         description="Argumen paling tegas tentang mengapa manusia butuh negara berdaulat yang kuat untuk keluar dari 'perang semua melawan semua' di alam bebas. Fondasi teori kontrak sosial yang masih jadi rujukan tiap kali orang berdebat soal batas kekuasaan negara."),
    dict(id="common-sense", raw="pg147.txt", gid=147, title="Common Sense",
         author="Thomas Paine", year="1776", category="politik",
         extractor=extract_common_sense,
         description="Pamflet tipis yang menyulut opini publik koloni Amerika untuk berani memutuskan hubungan dengan Inggris, ditulis dengan bahasa yang sengaja dibuat mudah dipahami orang kebanyakan. Salah satu contoh paling jelas bagaimana tulisan populer bisa mengubah arah sejarah."),
    dict(id="tao-te-ching", raw="pg216.txt", gid=216, title="Tao Te Ching",
         author="Laozi", year="±400 SM", category="filsafat",
         extractor=extract_tao_te_ching,
         description="Kumpulan 81 bait pendek tentang mengalir bersama Tao alih-alih melawannya, ditulis dengan bahasa yang sengaja ambigu dan puitis. Singkat di halaman, tapi maknanya terus dikupas ulang selama lebih dari dua ribu tahun."),
    dict(id="walden", raw="pg205.txt", gid=205, title="Walden",
         author="Henry David Thoreau", year="1854", category="filsafat",
         extractor=extract_walden,
         description="Catatan dua tahun hidup menyendiri di tepi danau, tempat Thoreau menguji gagasan bahwa hidup sederhana justru membuka ruang paling luas untuk berpikir. Edisi ini juga memuat 'On the Duty of Civil Disobedience', esainya tentang kapan seseorang berhak menolak patuh pada negara."),
    dict(id="political-economy", raw="pg33310.txt", gid=33310, title="Principles of Political Economy",
         author="David Ricardo", year="1817", category="ekonomi",
         extractor=extract_political_economy,
         description="Risalah teknis yang merumuskan teori nilai kerja dan keunggulan komparatif, gagasan yang sampai sekarang jadi dasar argumen perdagangan bebas antarnegara. Lebih berat dari Adam Smith, tapi jauh lebih presisi soal mengapa harga dan sewa tanah bergerak seperti itu."),
    dict(id="leisure-class", raw="pg833.txt", gid=833, title="The Theory of the Leisure Class",
         author="Thorstein Veblen", year="1899", category="ekonomi",
         extractor=extract_leisure_class,
         description="Bedah sinis tentang mengapa orang kaya suka memamerkan kemewahan yang tidak terlalu berguna, lengkap dengan istilah 'konsumsi mencolok' yang diciptakan buku ini dan masih dipakai sampai sekarang. Membaca buku ini bikin sulit melihat belanja orang lain, atau diri sendiri, dengan cara yang sama."),
    dict(id="herodotus", raw="pg2707.txt", gid=2707, title="The History of Herodotus (Vol. 1)",
         author="Herodotus", year="±430 SM", category="sejarah",
         extractor=extract_herodotus,
         description="Volume pertama dari catatan perjalanan dan Perang Persia oleh sosok yang sering disebut 'Bapak Sejarah', campuran laporan saksi mata, gosip lintas negeri, dan cerita yang jelas dilebih-lebihkan. Sejarah paling awal yang ditulis bukan sebagai daftar raja, tapi sebagai kisah yang memang ingin dibaca orang."),
    dict(id="peloponnesian-war", raw="pg7142.txt", gid=7142, title="The History of the Peloponnesian War",
         author="Thucydides", year="±400 SM", category="sejarah",
         extractor=extract_peloponnesian_war,
         description="Catatan perang saudara Yunani antara Athena dan Sparta oleh seorang jenderal yang ikut kalah perang dan menulis dengan jarak dingin dari kekalahannya sendiri. Analisis paling awal tentang bagaimana kekuasaan, ketakutan, dan kepentingan bisa menyeret negara ke perang panjang."),
    dict(id="souls-black-folk", raw="pg408.txt", gid=408, title="The Souls of Black Folk",
         author="W. E. B. Du Bois", year="1903", category="sosial",
         extractor=extract_souls_of_black_folk,
         description="Esai yang memperkenalkan gagasan 'double consciousness', kesadaran ganda orang kulit hitam Amerika yang harus melihat diri sendiri lewat mata masyarakat yang memandang rendah mereka. Ditulis dengan campuran analisis sosial dan prosa yang nyaris seperti puisi."),
    dict(id="rights-of-woman", raw="pg3420.txt", gid=3420, title="A Vindication of the Rights of Woman",
         author="Mary Wollstonecraft", year="1792", category="sosial",
         extractor=extract_rights_of_woman,
         description="Argumen paling awal dan paling tajam bahwa perempuan tampak lemah dan dangkal bukan karena kodrat, melainkan karena pendidikan yang sengaja dirancang untuk membuat mereka begitu. Ditulis satu generasi sebelum gerakan hak perempuan punya nama, tapi argumennya sudah lengkap."),
]

INDEX_ORDER = [
    "the-prince", "meditations", "art-of-war", "wealth-of-nations", "utopia",
    "communist-manifesto", "republic", "decline-and-fall", "political-economy",
    "democracy-in-america", "on-liberty", "beyond-good-and-evil", "herodotus",
    "leisure-class", "souls-black-folk", "second-treatise", "tao-te-ching",
    "peloponnesian-war", "rights-of-woman", "leviathan", "walden", "common-sense",
]


# --------------------------------------------------------------------------
# Validation helpers
# --------------------------------------------------------------------------

def validate_book(book_id, chapters_json):
    problems = []
    if len(chapters_json) < 3:
        problems.append("chapter count < 3")
    for ch in chapters_json:
        if not ch["paragraphs"]:
            problems.append(f"chapter '{ch['title']}' has zero paragraphs")
        for p in ch["paragraphs"]:
            if not p.strip():
                problems.append(f"empty paragraph in chapter '{ch['title']}'")
            if "***" in p:
                problems.append(f"stray *** in chapter '{ch['title']}'")
            if "Project Gutenberg" in p or "PROJECT GUTENBERG" in p.upper():
                problems.append(f"Gutenberg leakage in chapter '{ch['title']}'")
    return problems


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main():
    index_entries = []
    summary_rows = []
    fallback_used = []
    all_problems = {}

    for meta in BOOKS:
        book_id = meta["id"]
        raw_path = os.path.join(RAW_DIR, meta["raw"])
        size_kb = os.path.getsize(raw_path) / 1024.0

        raw_text = read_raw(meta["raw"])
        text = strip_header_footer(raw_text)

        raw_chapters = meta["extractor"](text)

        # apply length-based splitting per chapter
        final_chapters = []
        for title, paras in raw_chapters:
            final_chapters.extend(split_long_chapter(title, paras))

        # fallback if too few chapters detected
        if len(final_chapters) < 3:
            all_paras = []
            for _, paras in raw_chapters:
                all_paras.extend(paras)
            final_chapters = fallback_split_bagian(all_paras)
            fallback_used.append(book_id)

        chapters_json = []
        total_words = 0
        for title, paras in final_chapters:
            paras_clean = [clean_inline(p) for p in paras if p.strip()]
            w = paragraphs_word_count(paras_clean)
            total_words += w
            chapters_json.append({"title": title, "words": w, "paragraphs": paras_clean})

        problems = validate_book(book_id, chapters_json)
        if problems:
            all_problems[book_id] = problems

        book_json = {
            "id": book_id,
            "title": meta["title"],
            "author": meta["author"],
            "chapters": chapters_json,
        }
        out_path = os.path.join(OUT_DIR, f"{book_id}.json")
        with open(out_path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(book_json, f, ensure_ascii=False, indent=2)

        index_entries.append({
            "id": book_id,
            "title": meta["title"],
            "author": meta["author"],
            "year": meta["year"],
            "category": meta["category"],
            "description": meta["description"],
            "words": total_words,
            "chapterCount": len(chapters_json),
            "file": f"books/{book_id}.json",
            "source": f"Project Gutenberg #{meta['gid']} (domain publik)",
        })

        summary_rows.append((book_id, len(chapters_json), total_words, size_kb))

    index_by_id = {e["id"]: e for e in index_entries}
    missing_order = set(index_by_id) - set(INDEX_ORDER)
    missing_entries = set(INDEX_ORDER) - set(index_by_id)
    if missing_order or missing_entries:
        raise ValueError(
            "INDEX_ORDER mismatch. In index but not ordered: %r. "
            "Ordered but no entry: %r" % (missing_order, missing_entries)
        )
    ordered_index_entries = [index_by_id[i] for i in INDEX_ORDER]

    index_path = os.path.join(OUT_DIR, "index.json")
    with open(index_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(ordered_index_entries, f, ensure_ascii=False, indent=2)

    # -------------------- summary print (ASCII only) --------------------
    print("")
    print("=" * 78)
    print("PUSTAKA PREPROCESS SUMMARY")
    print("=" * 78)
    print(f"{'id':<24}{'chapters':>9}{'words':>10}{'raw_kb':>10}")
    print("-" * 78)
    for book_id, n_ch, words, size_kb in summary_rows:
        print(f"{book_id:<24}{n_ch:>9}{words:>10}{size_kb:>10.1f}")
    print("-" * 78)

    if fallback_used:
        print("Fallback 'Bagian N' splitter used for: " + ", ".join(fallback_used))
    else:
        print("Fallback splitter: not needed for any book.")

    low_threshold_ids = {"communist-manifesto": 5000, "tao-te-ching": 4000, "common-sense": 4000}
    min_words_map = {b["id"]: low_threshold_ids.get(b["id"], 10000) for b in BOOKS}
    print("")
    print("Word-count threshold check:")
    for book_id, n_ch, words, size_kb in summary_rows:
        threshold = min_words_map[book_id]
        status = "OK" if words > threshold else "FAIL"
        print(f"  {book_id:<24} words={words:<8} threshold>{threshold:<7} [{status}]")

    print("")
    if all_problems:
        print("VALIDATION PROBLEMS FOUND:")
        for book_id, problems in all_problems.items():
            print(f"  {book_id}:")
            for p in problems[:10]:
                print(f"    - {p}")
    else:
        print("Validation: no problems found (chapters>=3, no empty paragraphs, no '***', no Gutenberg leakage).")

    print("")
    print("Index written to: " + index_path)
    print("Done.")


if __name__ == "__main__":
    main()
