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


LEGACY_SMALL_PRINT_END_RE = re.compile(r"\*END\*")
LEGACY_FOOTER_RE = re.compile(r"(?im)^\s*End of (the )?Project Gutenberg")


def strip_header_footer(text):
    m1 = START_RE.search(text)
    m2 = END_RE.search(text)
    if not m1 or not m2:
        # Fallback for pre-2000 "legacy" Gutenberg etexts, which predate the
        # standardized "*** START/END OF ... ***" markers: the legal boilerplate
        # ends with the literal token "*END*" (from "...FOR PUBLIC DOMAIN
        # ETEXTS*Ver.xx.xx.xx*END*"), and the footer opens with an unmarked
        # "End of Project Gutenberg ..." line. Only used for new books whose
        # raw file genuinely lacks the modern markers -- the old 22 books all
        # have modern markers, so this branch never triggers for them.
        m1_legacy = LEGACY_SMALL_PRINT_END_RE.search(text)
        m2_legacy = LEGACY_FOOTER_RE.search(text, m1_legacy.end() if m1_legacy else 0)
        if not m1_legacy or not m2_legacy:
            raise ValueError("START/END marker not found (modern or legacy)")
        content = text[m1_legacy.end():m2_legacy.start()]
        content = TRANSCRIBER_RE.sub("", content, count=1)
        return content
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
    # Adaptive floor: for very short texts (total < 3*per_words), the fixed
    # per_words would yield <3 parts and fail validate_book()'s ">=3
    # chapters" rule. Shrink per_words so at least 3 "Bagian N" parts come
    # out, as long as there are enough paragraphs to split into 3 pieces.
    # None of the original 108 books ever hit this branch (they only reach
    # fallback_split_bagian when already >=3x per_words), so this is purely
    # additive for the short catalog-expansion-phase-2 texts (e.g. Crito,
    # The Right to Ignore the State).
    total_words = paragraphs_word_count(all_paragraphs)
    if total_words < 3 * per_words and len(all_paragraphs) >= 3:
        per_words = max(1, total_words // 3)
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
# Generic chapter-heading detector, used for the 86 new books added in the
# catalog-expansion pass. Built to work across diverse Gutenberg editions
# without a per-book extractor: tries several heading patterns in priority
# order (keyword+number, "I.--TITLE", bare roman numeral, monotonic bare
# arabic numeral, standalone ALL-CAPS line) and keeps the first one whose
# result passes a sanity check. Reuses this file's existing shared helpers
# (paragraphs_from_block, smart_title, word_count, paragraphs_word_count,
# ROMAN_ONLY_RE) -- do NOT duplicate or modify those, the old 22 books'
# extractors depend on their exact current behavior.
#
# NOTE: uses — (em dash) / – (en dash) escapes rather than literal
# characters in the DASH class -- literal non-ASCII in source has gotten
# mangled by intermediate tools/encodings during development.
# --------------------------------------------------------------------------

DASH = "—–\\-"

GENERIC_KEYWORD_PAT = re.compile(
    r"^[ \t]{0,40}(CHAPTER|BOOK|PART|SECTION|LETTER|ESSAY|LECTURE|CANTO|ARTICLE|"
    r"DIALOGUE|STAGE|DIVISION|FEDERALIST)[ \t]+(?:No\.?[ \t]*)?([IVXLCDM]+|\d{1,4})\b[.:]?"
    r"[ \t]*[" + DASH + r"]?[ \t]*(.*)$",
    re.MULTILINE,
)
GENERIC_ROMAN_DOT_TITLE_PAT = re.compile(
    r"^[ \t]{0,40}([IVXLCDM]{1,7})\.[ \t]*[" + DASH + r"]?[ \t]*"
    r"([A-Z][A-Za-z0-9 ,'().:!?" + DASH + r"]{2,90})$",
    re.MULTILINE,
)
GENERIC_ROMAN_ALONE_PAT = re.compile(r"^[ \t]{0,40}([IVXLCDM]+)\.?[ \t]*$", re.MULTILINE)
GENERIC_ARABIC_ALONE_PAT = re.compile(r"^[ \t]{0,40}(\d{1,4})\.?[ \t]*$", re.MULTILINE)
# standalone ALL-CAPS heading line (no numeral needed), e.g. "MAXIMS AND ARROWS"
GENERIC_ALLCAPS_LINE_PAT = re.compile(
    r"^[ \t]{0,40}([A-Z][A-Z0-9 ,:;'\"\-]{2,68})[ \t]*$", re.MULTILINE
)


def _generic_line_index(text):
    lines = text.split("\n")
    starts = []
    pos = 0
    for ln in lines:
        starts.append(pos)
        pos += len(ln) + 1
    return lines, starts


def _generic_line_idx_of(line_starts, offset):
    lo, hi = 0, len(line_starts) - 1
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if line_starts[mid] <= offset:
            lo = mid
        else:
            hi = mid - 1
    return lo


def _generic_guess_title_and_content_start(m, text, lines, line_starts, inline_title):
    """inline_title: text captured on the same line as the heading (may be
    empty). Returns (title_str_or_None, content_start_offset)."""
    inline_title = (inline_title or "").strip()
    inline_title = re.sub(r"^[.:\-—\s]+", "", inline_title).strip()
    if inline_title and len(inline_title) <= 90:
        return inline_title, m.end()

    head_line_idx = _generic_line_idx_of(line_starts, m.start())
    idx = head_line_idx + 1
    if idx < len(lines) and lines[idx].strip() == "":
        idx2 = idx + 1
        if (idx2 < len(lines) and lines[idx2].strip() != ""
                and len(lines[idx2].strip()) <= 90
                and (idx2 + 1 >= len(lines) or lines[idx2 + 1].strip() == "")):
            title = lines[idx2].strip()
            content_start = line_starts[idx2 + 1] if idx2 + 1 < len(line_starts) else len(text)
            return title, content_start
    return None, m.end()


def _generic_drop_empty_gap_matches(matches, text, min_words=3):
    """Drop any match whose content up to the NEXT match is essentially
    empty (a TOC listing, or a heading immediately followed by another
    heading, has ~0 words of real body text in between). This is a more
    reliable TOC/noise filter than line-distance heuristics since it
    doesn't care how close together headings are -- only whether there is
    real prose between them."""
    if not matches:
        return matches
    keep = []
    for i, m in enumerate(matches):
        nxt_start = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        gap_text = text[m.end():nxt_start]
        w = paragraphs_word_count(paragraphs_from_block(gap_text))
        if w >= min_words:
            keep.append(m)
    return keep


def _generic_build_from_matches(text, matches, label_fn, min_gap=40):
    if not matches:
        return []
    filtered = []
    for m in matches:
        if filtered and m.start() - filtered[-1].start() < min_gap:
            continue
        filtered.append(m)
    matches = _generic_drop_empty_gap_matches(filtered, text)
    if len(matches) < 3:
        return []

    lines, line_starts = _generic_line_index(text)
    chapters = []

    lead_end = matches[0].start()
    lead_paras = paragraphs_from_block(text[:lead_end])
    if paragraphs_word_count(lead_paras) > 150:
        chapters.append(("Pengantar", lead_paras))

    for i, m in enumerate(matches):
        inline = m.groups()[-1] if m.groups() else ""
        title, content_start = _generic_guess_title_and_content_start(
            m, text, lines, line_starts, inline
        )
        label = label_fn(m, title)
        content_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        paras = paragraphs_from_block(text[content_start:content_end])
        if paras:
            chapters.append((label, paras))
    return chapters


def _generic_reasonable(chapters):
    n = len(chapters)
    if n < 3 or n > 220:
        return False
    total = sum(paragraphs_word_count(p) for _, p in chapters)
    if total < 500:
        return False
    for _, p in chapters:
        w = paragraphs_word_count(p)
        if w > 0.92 * total and n > 3:
            return False
    return True


def generic_extract(text):
    """Generic chapter-heading detector for the 86 new catalog-expansion
    books. Tries several patterns in priority order, returns [] (triggering
    main()'s existing 'Bagian N' fallback) if none produce a sane split."""
    best = None

    def consider(chapters, priority):
        nonlocal best
        if chapters and _generic_reasonable(chapters):
            if best is None or priority > best[0]:
                best = (priority, chapters)

    kw_matches = list(GENERIC_KEYWORD_PAT.finditer(text))
    if len(kw_matches) >= 3:
        def kw_label(m, title):
            kw = smart_title(m.group(1))
            num = m.group(2)
            return f"{kw} {num}: {title}" if title else f"{kw} {num}"
        consider(_generic_build_from_matches(text, kw_matches, kw_label), 5)
    if best is not None:
        return best[1]

    rd_matches = [m for m in GENERIC_ROMAN_DOT_TITLE_PAT.finditer(text)
                  if ROMAN_ONLY_RE.match(m.group(1))]
    if len(rd_matches) >= 3:
        def rd_label(m, title):
            return f"Bab {m.group(1)}: {smart_title(m.group(2))}"
        consider(_generic_build_from_matches(text, rd_matches, rd_label), 4)
    if best is not None:
        return best[1]

    ra_matches = [m for m in GENERIC_ROMAN_ALONE_PAT.finditer(text)
                  if ROMAN_ONLY_RE.match(m.group(1))]
    if len(ra_matches) >= 3:
        def ra_label(m, title):
            return f"Bab {m.group(1)}: {title}" if title else f"Bab {m.group(1)}"
        consider(_generic_build_from_matches(text, ra_matches, ra_label), 3)
    if best is not None:
        return best[1]

    num_matches = list(GENERIC_ARABIC_ALONE_PAT.finditer(text))
    seq = []
    expected = 1
    for m in num_matches:
        n = int(m.group(1))
        if n == expected and (m.start() - text.rfind("\n", 0, m.start())) < 6:
            seq.append(m)
            expected += 1
        elif n == 1 and len(seq) >= 3:
            break
    if len(seq) >= 3:
        def num_label(m, title):
            return f"Bab {m.group(1)}: {title}" if title else f"Bab {m.group(1)}"
        consider(_generic_build_from_matches(text, seq, num_label, min_gap=20), 2)
    if best is not None:
        return best[1]

    ac_matches = [m for m in GENERIC_ALLCAPS_LINE_PAT.finditer(text)
                  if re.search(r"[A-Z]{2,}", m.group(1))]
    if len(ac_matches) >= 6:
        def ac_label(m, title):
            return smart_title(m.group(1))
        consider(_generic_build_from_matches(text, ac_matches, ac_label), 1)
    if best is not None:
        return best[1]

    # No heading pattern found at all (e.g. a headerless Jowett dialogue
    # translation). Return the WHOLE text as a single chapter rather than
    # an empty list -- main()'s "<3 chapters -> Bagian N fallback" logic
    # collects paragraphs FROM whatever the extractor returned, so an empty
    # list here would make it fall back to zero content instead of a
    # correct "Bagian N" split of the full book.
    whole = paragraphs_from_block(text)
    if whole:
        return [("Konten", whole)]
    return []


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

    dict(id="apology", raw="pg1656.txt", gid=1656, title="Apology",
         author="Plato", year="±390 SM", category="filsafat",
         extractor=generic_extract,
         description="Pembelaan Socrates di depan pengadilan Athena yang menuduhnya merusak moral pemuda dan tidak percaya dewa-dewa kota. Dia tidak minta ampun, malah balik menantang juri sampai akhirnya dijatuhi hukuman mati."),
    dict(id="symposium", raw="pg1600.txt", gid=1600, title="Symposium",
         author="Plato", year="±385 SM", category="filsafat",
         extractor=generic_extract,
         description="Sekumpulan orang mabuk-mabukan di sebuah pesta di Athena bergiliran berpidato tentang cinta, dan hasilnya adalah salah satu diskusi paling berpengaruh tentang apa itu cinta dalam sejarah pemikiran Barat. Puncaknya adalah pidato Socrates yang mengubah cinta jasmani jadi tangga menuju kebenaran abadi."),
    dict(id="phaedo", raw="pg1658.txt", gid=1658, title="Phaedo",
         author="Plato", year="±385 SM", category="filsafat",
         extractor=generic_extract,
         description="Kisah jam-jam terakhir Socrates sebelum minum racun, sambil tetap berdebat tenang soal jiwa itu abadi atau tidak. Cara seorang filsuf menghadapi ajalnya sendiri sebagai bahan diskusi filosofis, bukan tragedi yang perlu ditangisi."),
    dict(id="gorgias", raw="pg1672.txt", gid=1672, title="Gorgias",
         author="Plato", year="±380 SM", category="filsafat",
         extractor=generic_extract,
         description="Socrates menyudutkan tiga tokoh retorika ternama sampai mereka mengakui bahwa pandai bicara tanpa peduli benar-salah adalah bentuk manipulasi, bukan keahlian. Perdebatan soal kekuasaan, keadilan, dan apakah lebih baik menzalimi atau dizalimi ini masih relevan tiap kali orang pandai bicara dipercaya begitu saja."),
    dict(id="nicomachean-ethics", raw="pg8438.txt", gid=8438, title="Nicomachean Ethics",
         author="Aristotle", year="±340 SM", category="filsafat",
         extractor=generic_extract,
         description="Risalah paling sistematis Aristoteles tentang bagaimana manusia bisa mencapai eudaimonia, hidup yang benar-benar berjalan baik, lewat kebiasaan dan jalan tengah antara dua sikap ekstrem. Lebih praktis dibanding Plato: bukan tentang dunia ide, tapi tentang bagaimana benar-benar hidup sehari-hari."),
    dict(id="poetics", raw="pg1974.txt", gid=1974, title="Poetics",
         author="Aristotle", year="±335 SM", category="filsafat",
         extractor=generic_extract,
         description="Analisis teknis Aristoteles tentang mengapa tragedi Yunani bisa begitu menggugah, lengkap dengan konsep katarsis yang masih dipakai kritikus sastra dan pembuat film sampai sekarang. Buku pendek yang diam-diam menentukan cara Barat bercerita selama lebih dari dua ribu tahun."),
    dict(id="enchiridion", raw="pg45109.txt", gid=45109, title="The Enchiridion",
         author="Epictetus", year="±125 M", category="filsafat",
         extractor=generic_extract,
         description="Buku saku Stoic yang isinya sederhana: pisahkan apa yang bisa kau kendalikan dari apa yang tidak, lalu berhenti gelisah soal yang kedua. Ditulis oleh bekas budak yang berubah jadi guru filsafat, jadi nasihatnya bukan teori kosong."),
    dict(id="discourses-epictetus", raw="pg10661.txt", gid=10661, title="Discourses of Epictetus",
         author="Epictetus", year="±108 M", category="filsafat",
         extractor=generic_extract,
         description="Catatan kuliah lisan Epictetus yang direkam muridnya, jauh lebih panjang dan personal dibanding ringkasan Enchiridion. Gaya bicaranya blak-blakan dan sering menyindir muridnya sendiri yang cuma jago teori tapi lembek saat prakteknya."),
    dict(id="on-the-nature-of-things", raw="pg785.txt", gid=785, title="On the Nature of Things",
         author="Lucretius", year="±50 SM", category="filsafat",
         extractor=generic_extract,
         description="Puisi panjang yang menjelaskan seluruh alam semesta, dari atom sampai jiwa manusia, tanpa perlu campur tangan dewa-dewa. Filsafat Epicurean yang ditulis dengan ambisi seorang penyair sekaligus ilmuwan, dua ribu tahun sebelum sains modern membuktikan sebagian isinya benar."),
    dict(id="consolation-of-philosophy", raw="pg14328.txt", gid=14328, title="The Consolation of Philosophy",
         author="Boethius", year="±524 M", category="filsafat",
         extractor=generic_extract,
         description="Ditulis di sel penjara sambil menunggu eksekusi atas tuduhan pengkhianatan, buku ini adalah dialog Boethius dengan sosok Filsafat yang menghiburnya soal nasib, keberuntungan, dan kebahagiaan sejati. Salah satu buku paling berpengaruh di Abad Pertengahan, ditulis justru saat penulisnya kehilangan segalanya."),
    dict(id="discourse-on-method", raw="pg59.txt", gid=59, title="Discourse on the Method",
         author="René Descartes", year="1637", category="filsafat",
         extractor=generic_extract,
         description="Descartes meragukan segalanya sampai hanya satu hal yang tersisa untuk dipegang: dirinya sendiri sedang berpikir. Dari keraguan radikal inilah lahir 'Cogito, ergo sum' dan fondasi filsafat modern yang memisahkan pikiran dari dunia fisik."),
    dict(id="ethics-spinoza", raw="pg3800.txt", gid=3800, title="Ethics",
         author="Baruch Spinoza", year="1677", category="filsafat",
         extractor=generic_extract,
         description="Ditulis dengan gaya geometris ala pembuktian matematika, Spinoza membangun argumen bahwa Tuhan, alam, dan segala sesuatu sebenarnya satu substansi yang sama. Buku yang membuatnya dikucilkan komunitasnya sendiri, tapi kini dianggap salah satu karya filsafat paling berani yang pernah ditulis."),
    dict(id="enquiry-human-understanding", raw="pg9662.txt", gid=9662, title="An Enquiry Concerning Human Understanding",
         author="David Hume", year="1748", category="filsafat",
         extractor=generic_extract,
         description="Hume membongkar asumsi kita bahwa sebab-akibat itu sesuatu yang benar-benar kita amati, padahal yang kita amati cuma kebiasaan berpikir. Argumen skeptisnya begitu tajam sampai Kant sendiri mengaku 'dibangunkan dari tidur dogmatisnya' gara-gara buku ini."),
    dict(id="treatise-human-nature", raw="pg4705.txt", gid=4705, title="A Treatise of Human Nature",
         author="David Hume", year="1739", category="filsafat",
         extractor=generic_extract,
         description="Karya ambisius Hume di usia dua puluhan yang mencoba menjelaskan pikiran, emosi, dan moralitas manusia murni lewat pengalaman indrawi, tanpa sandaran metafisika. Ditulis begitu radikal untuk zamannya sampai, menurut pengakuannya sendiri, buku ini 'lahir mati dari percetakan'."),
    dict(id="metaphysic-of-morals", raw="pg5682.txt", gid=5682, title="Fundamental Principles of the Metaphysic of Morals",
         author="Immanuel Kant", year="1785", category="filsafat",
         extractor=generic_extract,
         description="Kant mencari satu prinsip moral yang berlaku untuk semua makhluk rasional, terlepas dari akibat atau perasaan, dan menemukannya dalam gagasan 'imperatif kategoris'. Padat dan berat, tapi jadi salah satu fondasi etika yang paling dipakai sampai sekarang, dari ruang kelas filsafat sampai debat hak asasi manusia."),
    dict(id="thus-spake-zarathustra", raw="pg1998.txt", gid=1998, title="Thus Spake Zarathustra",
         author="Friedrich Nietzsche", year="1883", category="filsafat",
         extractor=generic_extract,
         description="Nietzsche menyamar jadi nabi Persia kuno untuk mengumumkan matinya Tuhan dan lahirnya Übermensch, manusia yang menciptakan nilainya sendiri. Ditulis setengah filsafat setengah puisi, buku yang oleh Nietzsche sendiri disebut sebagai hadiah terbesarnya untuk umat manusia."),
    dict(id="genealogy-of-morals", raw="pg52319.txt", gid=52319, title="The Genealogy of Morals",
         author="Friedrich Nietzsche", year="1887", category="filsafat",
         extractor=generic_extract,
         description="Nietzsche menelusuri dari mana asal konsep 'baik' dan 'jahat', dan menyimpulkan bahwa moralitas yang kita anggap suci sebenarnya lahir dari kebencian kaum lemah terhadap yang kuat. Argumen paling sistematis dan provokatif Nietzsche, ditulis untuk membongkar akar psikologis di balik nilai-nilai yang kita anggap sudah pasti benar."),
    dict(id="twilight-of-the-idols", raw="pg52263.txt", gid=52263, title="Twilight of the Idols",
         author="Friedrich Nietzsche", year="1888", category="filsafat",
         extractor=generic_extract,
         description="Nietzsche menyebutnya 'berfilsafat dengan palu', menghantam satu per satu berhala filsafat Barat, dari Socrates sampai moralitas Kristen, dalam aforisme-aforisme pendek yang tajam. Ringkasan paling padat dari seluruh pemikirannya, ditulis menjelang keruntuhan mentalnya sendiri."),
    dict(id="the-antichrist", raw="pg19322.txt", gid=19322, title="The Antichrist",
         author="Friedrich Nietzsche", year="1888", category="filsafat",
         extractor=generic_extract,
         description="Serangan paling frontal Nietzsche terhadap Kekristenan, yang dia tuduh mengagungkan kelemahan dan penderitaan sebagai kebajikan. Ditulis dengan amarah yang nyaris personal, buku terakhir sebelum dia jatuh sakit jiwa secara permanen."),
    dict(id="studies-in-pessimism", raw="pg10732.txt", gid=10732, title="Studies in Pessimism",
         author="Arthur Schopenhauer", year="1851", category="filsafat",
         extractor=generic_extract,
         description="Kumpulan esai Schopenhauer yang berargumen bahwa penderitaan, bukan kebahagiaan, adalah kondisi dasar hidup manusia, dan kebahagiaan hanyalah jeda sesaat dari keinginan yang tak pernah puas. Suram tapi ditulis dengan wit yang tajam, jauh dari kesan membosankan yang biasanya melekat pada filsafat pesimisme."),
    dict(id="utilitarianism", raw="pg11224.txt", gid=11224, title="Utilitarianism",
         author="John Stuart Mill", year="1863", category="filsafat",
         extractor=generic_extract,
         description="Mill membela gagasan bahwa tindakan benar adalah yang menghasilkan kebahagiaan terbesar bagi jumlah orang terbanyak, sambil membedakan kesenangan 'tinggi' dan 'rendah' agar tidak disamakan dengan hedonisme murni. Kerangka etis yang sampai sekarang jadi rujukan default kebijakan publik, dari ekonomi sampai kesehatan."),
    dict(id="essays-bacon", raw="pg56463.txt", gid=56463, title="Essays",
         author="Francis Bacon", year="1625", category="filsafat",
         extractor=generic_extract,
         description="Kumpulan esai pendek Bacon tentang kebenaran, kematian, ambisi, sampai persahabatan, ditulis dengan kalimat-kalimat aforistik yang padat makna. Salah satu contoh awal esai gaya modern dalam bahasa Inggris, pendek-pendek tapi tiap kalimatnya bisa jadi bahan renungan sendiri."),
    dict(id="essay-humane-understanding", raw="pg10615.txt", gid=10615, title="An Essay Concerning Humane Understanding (Vol. 1)",
         author="John Locke", year="1689", category="filsafat",
         extractor=generic_extract,
         description="Locke membantah gagasan bahwa manusia lahir dengan ide bawaan, dan berargumen pikiran kita mulai sebagai 'kertas kosong' yang diisi lewat pengalaman indrawi. Volume pertama ini fondasi empirisme modern, yang kelak memengaruhi segalanya dari psikologi sampai teori pendidikan."),
    dict(id="human-knowledge-berkeley", raw="pg4723.txt", gid=4723, title="A Treatise Concerning the Principles of Human Knowledge",
         author="George Berkeley", year="1710", category="filsafat",
         extractor=generic_extract,
         description="Berkeley mengajukan klaim yang bikin banyak orang menggaruk kepala: benda-benda fisik hanya ada karena dipersepsi, 'esse est percipi'. Argumen idealisnya begitu licin sampai butuh berabad-abad filsuf lain untuk benar-benar membantahnya dengan meyakinkan."),
    dict(id="pragmatism", raw="pg5116.txt", gid=5116, title="Pragmatism",
         author="William James", year="1907", category="filsafat",
         extractor=generic_extract,
         description="James menawarkan cara praktis menilai kebenaran sebuah gagasan: lihat saja apakah gagasan itu benar-benar berguna dalam pengalaman hidup nyata. Filsafat Amerika yang lahir dari kegelisahan menengahi sains dan agama, tanpa harus memilih salah satu."),
    dict(id="problems-of-philosophy", raw="pg5827.txt", gid=5827, title="The Problems of Philosophy",
         author="Bertrand Russell", year="1912", category="filsafat",
         extractor=generic_extract,
         description="Pengantar filsafat paling jernih yang pernah ditulis, dimulai dari pertanyaan sederhana macam 'apakah meja di depanku benar-benar ada'. Russell menulisnya untuk orang awam, dan sampai sekarang tetap jadi buku pertama yang direkomendasikan untuk siapa pun yang penasaran soal filsafat."),
    dict(id="essays-first-series", raw="pg2944.txt", gid=2944, title="Essays: First Series",
         author="Ralph Waldo Emerson", year="1841", category="filsafat",
         extractor=generic_extract,
         description="Kumpulan esai Emerson, termasuk 'Self-Reliance' yang legendaris, yang mendesak pembaca untuk percaya pada intuisi dan jiwanya sendiri ketimbang mengikuti konvensi masyarakat. Fondasi filsafat transendentalisme Amerika, ditulis dengan semangat individualisme yang masih terasa relevan di era media sosial."),
    dict(id="analects-confucius", raw="pg3330.txt", gid=3330, title="The Analects",
         author="Confucius", year="±479 SM", category="filsafat",
         extractor=generic_extract,
         description="Kumpulan percakapan pendek Confucius dengan murid-muridnya tentang cara hidup bermoral, menghormati keluarga, dan menjalankan pemerintahan yang baik. Tidak sistematis seperti risalah filsafat Barat, tapi pengaruhnya membentuk peradaban Asia Timur selama lebih dari dua ribu tahun."),
    dict(id="pensees", raw="pg18269.txt", gid=18269, title="Pensees",
         author="Blaise Pascal", year="1670", category="filsafat",
         extractor=generic_extract,
         description="Kumpulan catatan dan renungan yang tidak sempat dirampungkan Pascal sebelum wafat, berisi argumen terkenalnya soal taruhan pada keberadaan Tuhan ('Pascal's Wager') dan kegelisahan manusia yang kecil di alam semesta yang luas. Fragmen-fragmennya terasa lebih jujur dan personal justru karena tidak pernah selesai dirapikan."),
    dict(id="politics-aristotle", raw="pg6762.txt", gid=6762, title="Politics",
         author="Aristotle", year="±350 SM", category="politik",
         extractor=generic_extract,
         description="Aristoteles membedah berbagai bentuk pemerintahan, dari monarki sampai demokrasi, dan menyimpulkan manusia pada dasarnya adalah 'hewan politik' yang cuma bisa berkembang penuh dalam kehidupan bernegara. Analisis empirisnya soal konstitusi berbagai negara kota Yunani jadi cikal bakal ilmu politik perbandingan."),
    dict(id="federalist-papers", raw="pg1404.txt", gid=1404, title="The Federalist Papers",
         author="Alexander Hamilton, James Madison & John Jay", year="1788", category="politik",
         extractor=generic_extract,
         description="Serangkaian esai yang ditulis diam-diam dengan nama samaran untuk meyakinkan rakyat New York menerima Konstitusi Amerika yang baru dirancang. Sampai sekarang jadi rujukan utama Mahkamah Agung AS tiap kali harus menafsirkan maksud asli para pendiri negara."),
    dict(id="social-contract", raw="pg46333.txt", gid=46333, title="The Social Contract",
         author="Jean-Jacques Rousseau", year="1762", category="politik",
         extractor=generic_extract,
         description="Rousseau berargumen bahwa kekuasaan sah hanya berasal dari 'kehendak umum' rakyat, bukan dari darah bangsawan atau restu gereja, kalimat pembukanya yang terkenal: 'Manusia lahir merdeka, tapi di mana-mana dia terbelenggu'. Buku yang ikut menyalakan sumbu Revolusi Prancis beberapa dekade kemudian."),
    dict(id="rights-of-man", raw="pg3742.txt", gid=3742, title="Rights of Man",
         author="Thomas Paine", year="1791", category="politik",
         extractor=generic_extract,
         description="Paine membela Revolusi Prancis sekaligus menyerang balik Edmund Burke yang mengecamnya, dengan argumen bahwa setiap generasi berhak menentukan bentuk pemerintahannya sendiri tanpa terikat masa lalu. Begitu dianggap berbahaya sampai Paine diadili in absentia di Inggris karena menerbitkannya."),
    dict(id="conciliation-with-america", raw="pg5655.txt", gid=5655, title="Speech on Conciliation with America",
         author="Edmund Burke", year="1775", category="politik",
         extractor=generic_extract,
         description="Pidato Burke di Parlemen Inggris yang memperingatkan bahwa memaksakan kekuasaan lewat kekerasan terhadap koloni Amerika akan berakhir buruk, dan menyarankan rekonsiliasi lewat pengakuan hak-hak mereka. Argumen konservatif klasik: bukan menolak perubahan, tapi curiga pada perubahan yang dipaksakan tergesa-gesa."),
    dict(id="representative-government", raw="pg5669.txt", gid=5669, title="Considerations on Representative Government",
         author="John Stuart Mill", year="1861", category="politik",
         extractor=generic_extract,
         description="Mill merancang cetak biru pemerintahan perwakilan yang ideal, lengkap dengan usulan yang saat itu radikal: memberi perempuan hak suara dan melindungi suara kelompok minoritas dari tirani mayoritas. Lebih teknis dibanding 'On Liberty', tapi sama gigihnya membela kebebasan lewat desain institusi yang tepat."),
    dict(id="discourses-on-livy", raw="pg10827.txt", gid=10827, title="Discourses on the First Decade of Titus Livius",
         author="Niccolò Machiavelli", year="1531", category="politik",
         extractor=generic_extract,
         description="Kalau 'The Prince' bicara soal cara seorang penguasa tunggal merebut kekuasaan, buku ini adalah sisi lain Machiavelli yang memuji republik Romawi dan kebebasan sipil. Lebih jarang dibaca dibanding 'The Prince', padahal mengungkap Machiavelli yang sebenarnya jauh lebih menyukai pemerintahan republik."),
    dict(id="anarchism-and-other-essays", raw="pg2162.txt", gid=2162, title="Anarchism and Other Essays",
         author="Emma Goldman", year="1910", category="politik",
         extractor=generic_extract,
         description="Goldman membela anarkisme bukan sebagai kekacauan, tapi sebagai penolakan terhadap segala bentuk otoritas yang menindas, dari negara sampai institusi pernikahan. Ditulis oleh seorang aktivis yang berulang kali dipenjara dan akhirnya dideportasi dari Amerika karena keyakinannya sendiri."),
    dict(id="english-constitution", raw="pg4351.txt", gid=4351, title="The English Constitution",
         author="Walter Bagehot", year="1867", category="politik",
         extractor=generic_extract,
         description="Bagehot membedah rahasia kecil di balik sistem monarki konstitusional Inggris: raja atau ratu 'memerintah tapi tidak berkuasa', sementara kekuasaan riil ada di tangan kabinet. Analisisnya begitu jernih sampai jadi rujukan standar tiap kali orang ingin memahami bagaimana monarki modern sebenarnya bekerja."),
    dict(id="god-and-the-state", raw="pg36568.txt", gid=36568, title="God and the State",
         author="Mikhail Bakunin", year="1882", category="politik",
         extractor=generic_extract,
         description="Bakunin berargumen bahwa gagasan tentang Tuhan dan gagasan tentang negara sama-sama alat untuk membuat manusia tunduk, dan kebebasan sejati hanya mungkin kalau keduanya ditolak. Naskah yang tidak pernah dia selesaikan ini diterbitkan setelah kematiannya, tapi tetap jadi salah satu manifesto anarkisme paling dikutip."),
    dict(id="conquest-of-bread", raw="pg23428.txt", gid=23428, title="The Conquest of Bread",
         author="Peter Kropotkin", year="1892", category="politik",
         extractor=generic_extract,
         description="Kropotkin, seorang pangeran Rusia yang jadi anarkis, membayangkan masyarakat tanpa negara yang mengatur diri lewat kerja sama sukarela, bukan lewat persaingan atau paksaan. Optimis dan konkret, bukan sekadar kritik tapi juga usulan tentang bagaimana sistem semacam itu bisa benar-benar berjalan."),
    dict(id="democracy-in-america-2", raw="pg816.txt", gid=816, title="Democracy in America (Vol. 2)",
         author="Alexis de Tocqueville", year="1840", category="politik",
         extractor=generic_extract,
         description="Kelanjutan analisis Tocqueville, kali ini berfokus pada bagaimana kesetaraan sosial membentuk cara berpikir, perasaan, dan kebiasaan orang Amerika sehari-hari. Lebih filosofis dibanding volume pertama, dan lebih meresahkan soal bagaimana demokrasi bisa diam-diam melahirkan keseragaman yang membosankan."),
    dict(id="discourse-on-inequality", raw="pg11136.txt", gid=11136, title="Discourse on the Origin of Inequality",
         author="Jean-Jacques Rousseau", year="1755", category="politik",
         extractor=generic_extract,
         description="Rousseau melacak bagaimana manusia yang awalnya hidup bebas dan setara di alam liar akhirnya terjebak dalam ketimpangan begitu properti pribadi dan masyarakat terbentuk. Argumen yang mengguncang asumsi zamannya: peradaban bukan kemajuan murni, tapi juga sumber penindasan baru."),
    dict(id="plutarchs-lives-1", raw="pg14033.txt", gid=14033, title="Plutarch's Lives (Vol. 1)",
         author="Plutarch", year="±100 M", category="sejarah",
         extractor=generic_extract,
         description="Plutarch memasangkan tokoh besar Yunani dan Romawi secara berpasangan, membandingkan karakter dan nasib mereka untuk menarik pelajaran moral, bukan sekadar mencatat fakta. Buku yang dibaca Shakespeare untuk menulis drama-drama Romawinya, dan masih jadi pintu masuk paling enak dibaca ke dunia kuno."),
    dict(id="gallic-war", raw="pg10657.txt", gid=10657, title="Commentaries on the Gallic War",
         author="Julius Caesar", year="±50 SM", category="sejarah",
         extractor=generic_extract,
         description="Caesar menulis laporan penaklukan Galia dengan gaya orang ketiga yang dingin dan objektif, padahal ini propaganda politik untuk memoles citranya sendiri di Roma. Naskah yang jadi bahan wajib belajar bahasa Latin selama berabad-abad, sekaligus contoh awal bagaimana penguasa mengarang narasinya sendiri."),
    dict(id="annals-tacitus", raw="pg7959.txt", gid=7959, title="The Annals",
         author="Tacitus", year="±116 M", category="sejarah",
         extractor=generic_extract,
         description="Tacitus mencatat era kelam awal Kekaisaran Romawi, mulai dari pemerintahan Tiberius, dengan nada sinis yang curiga pada setiap kekuasaan tak terkontrol. Edisi ini memuat bagian yang selamat dari masa Tiberius, ditulis oleh sejarawan yang tak segan menuduh kaisar sekaligus mengagumi kebajikan lama Romawi yang hilang."),
    dict(id="germany-and-agricola", raw="pg7524.txt", gid=7524, title="The Germany and the Agricola",
         author="Tacitus", year="±98 M", category="sejarah",
         extractor=generic_extract,
         description="Dua naskah pendek: satu tentang suku-suku Jermania yang dianggap Tacitus lebih murni moralnya dibanding Romawi yang sudah dekaden, satu lagi biografi mertuanya sendiri, seorang jenderal yang menaklukkan Britania. Campuran etnografi awal dan biografi keluarga yang jujur mengagumi sekaligus mengkritik."),
    dict(id="anabasis", raw="pg1170.txt", gid=1170, title="Anabasis",
         author="Xenophon", year="±370 SM", category="sejarah",
         extractor=generic_extract,
         description="Catatan perjalanan sepuluh ribu tentara bayaran Yunani yang terjebak jauh di jantung Persia setelah pemimpin mereka terbunuh, dan harus berbaris pulang lewat medan asing yang bermusuhan. Kisah bertahan hidup yang ditulis oleh salah satu tentara itu sendiri, salah satu narasi petualangan militer tertua yang masih bisa dinikmati seperti novel."),
    dict(id="twelve-caesars", raw="pg6400.txt", gid=6400, title="The Lives of the Twelve Caesars",
         author="Suetonius", year="±121 M", category="sejarah",
         extractor=generic_extract,
         description="Suetonius menulis biografi dua belas penguasa Romawi pertama lengkap dengan gosip, skandal, dan kebiasaan aneh mereka yang tidak akan ditemukan di catatan resmi. Lebih mirip tabloid istana dibanding sejarah formal, tapi justru karena itu jadi sumber paling berwarna soal sisi manusiawi para kaisar."),
    dict(id="french-revolution-carlyle", raw="pg1301.txt", gid=1301, title="The French Revolution: A History",
         author="Thomas Carlyle", year="1837", category="sejarah",
         extractor=generic_extract,
         description="Carlyle menulis ulang kekacauan Revolusi Prancis dengan gaya prosa yang menggebu-gebu, hampir seperti drama panggung, bukan catatan sejarah yang dingin. Konon naskah bagian pertamanya sempat terbakar tak sengaja jadi abu oleh pembantu rumah tangga temannya, dan Carlyle terpaksa menulis ulang semuanya dari ingatan."),
    dict(id="short-history-of-world", raw="pg35461.txt", gid=35461, title="A Short History of the World",
         author="H. G. Wells", year="1922", category="sejarah",
         extractor=generic_extract,
         description="Wells, yang lebih dikenal lewat novel fiksi ilmiahnya, mencoba merangkum seluruh sejarah manusia dari asal-usul bumi sampai Perang Dunia I dalam satu volume yang ringkas dan mudah dibaca. Ambisius sampai terdengar mustahil, tapi jadi salah satu buku sejarah populer paling laris di zamannya."),
    dict(id="autobiography-franklin", raw="pg148.txt", gid=148, title="The Autobiography of Benjamin Franklin",
         author="Benjamin Franklin", year="1791", category="sejarah",
         extractor=generic_extract,
         description="Franklin menceritakan perjalanan hidupnya dari tukang cetak miskin di Boston sampai jadi negarawan paling dihormati di Amerika, lengkap dengan daftar tiga belas kebajikan yang dia coba latih satu per satu. Salah satu memoar paling awal yang menjadikan 'kerja keras dan disiplin diri' sebagai mitos khas Amerika."),
    dict(id="narrative-frederick-douglass", raw="pg23.txt", gid=23, title="Narrative of the Life of Frederick Douglass",
         author="Frederick Douglass", year="1845", category="sejarah",
         extractor=generic_extract,
         description="Douglass menuliskan sendiri pengalamannya sebagai budak, termasuk bagaimana belajar membaca diam-diam justru membuatnya makin sadar akan penjaranya, sampai akhirnya melarikan diri menuju kebebasan. Kesaksian langsung yang begitu tajam sampai sebagian orang saat itu tidak percaya seorang mantan budak bisa menulis seindah ini."),
    dict(id="travels-marco-polo-1", raw="pg10636.txt", gid=10636, title="The Travels of Marco Polo (Vol. 1)",
         author="Marco Polo", year="±1300 M", category="sejarah",
         extractor=generic_extract,
         description="Catatan perjalanan pedagang Venesia yang menghabiskan bertahun-tahun di istana Kubilai Khan, penuh cerita tentang kekayaan, kota-kota megah, dan kebiasaan aneh Asia yang bagi pembaca Eropa abad pertengahan terdengar seperti dongeng. Sebagian dianggap dilebih-lebihkan, tapi tetap jadi jendela pertama Eropa ke dunia Timur jauh."),
    dict(id="histories-of-polybius-1", raw="pg44125.txt", gid=44125, title="The Histories of Polybius (Vol. 1)",
         author="Polybius", year="±150 SM", category="sejarah",
         extractor=generic_extract,
         description="Polybius, seorang tawanan Yunani yang dibawa ke Roma, menulis analisis tentang bagaimana Roma bisa naik begitu cepat menjadi kekuatan dominan Mediterania dalam waktu kurang dari seabad. Salah satu sejarawan pertama yang benar-benar berusaha menjelaskan sebab-akibat, bukan cuma mencatat peristiwa."),
    dict(id="herodotus-2", raw="pg2456.txt", gid=2456, title="The History of Herodotus (Vol. 2)",
         author="Herodotus", year="±430 SM", category="sejarah",
         extractor=generic_extract,
         description="Volume kedua catatan 'Bapak Sejarah' ini masuk ke jantung Perang Persia, dari invasi Xerxes sampai pertempuran-pertempuran legendaris yang menyelamatkan Yunani. Herodotus tetap setia pada gayanya: separuh sejarah, separuh cerita rakyat yang seru untuk didengar ulang."),
    dict(id="decline-and-fall-2", raw="pg732.txt", gid=732, title="The Decline and Fall of the Roman Empire (Vol. 2)",
         author="Edward Gibbon", year="1776", category="sejarah",
         extractor=generic_extract,
         description="Lanjutan mahakarya Gibbon, memasuki era ketika Kekaisaran Romawi mulai retak dari dalam sementara tekanan dari luar terus menghantam perbatasannya. Gaya prosa Gibbon yang megah tetap konsisten, tapi nadanya makin muram seiring kejatuhan yang dia ceritakan makin dekat."),
    dict(id="life-of-charlemagne", raw="pg59577.txt", gid=59577, title="Life of Charlemagne",
         author="Einhard", year="±830 M", category="sejarah",
         extractor=generic_extract,
         description="Ditulis oleh orang yang benar-benar mengenalnya secara pribadi, biografi ini menggambarkan Charlemagne bukan cuma sebagai kaisar penakluk, tapi juga sosok ayah, pembaca buku, dan penggemar musik di malam hari. Model biografi abad pertengahan yang jelas-jelas meniru gaya Suetonius, tapi tetap terasa hangat dan personal."),
    dict(id="wars-of-the-jews", raw="pg2850.txt", gid=2850, title="The Wars of the Jews",
         author="Flavius Josephus", year="±75 M", category="sejarah",
         extractor=generic_extract,
         description="Josephus, seorang jenderal Yahudi yang menyeberang ke pihak Romawi, menulis catatan saksi mata pemberontakan Yahudi melawan Roma yang berakhir dengan kehancuran Yerusalem. Posisinya yang berada di dua sisi bikin ceritanya kontroversial, tapi juga jadi salah satu sumber sejarah paling detail tentang peristiwa itu."),
    dict(id="critique-political-economy", raw="pg46423.txt", gid=46423, title="A Contribution to the Critique of Political Economy",
         author="Karl Marx", year="1859", category="ekonomi",
         extractor=generic_extract,
         description="Marx meletakkan dasar teori nilai kerja dan materialisme sejarah yang belakangan dia kembangkan penuh di 'Capital'. Lebih pendek dan lebih awal dibanding karya utamanya, tapi memuat kata pengantar terkenal yang meringkas seluruh pandangan hidupnya tentang bagaimana sejarah bergerak."),
    dict(id="principle-of-population", raw="pg4239.txt", gid=4239, title="An Essay on the Principle of Population",
         author="Thomas Robert Malthus", year="1798", category="ekonomi",
         extractor=generic_extract,
         description="Malthus berargumen populasi manusia selalu tumbuh lebih cepat dibanding pasokan makanan, sehingga kelaparan dan kemiskinan bukan kecelakaan tapi keniscayaan matematis. Ramalan suramnya terbukti meleset karena revolusi pertanian dan teknologi, tapi 'momok Malthusian' tetap jadi bahan perdebatan tiap kali orang bicara soal batas pertumbuhan."),
    dict(id="progress-and-poverty", raw="pg55308.txt", gid=55308, title="Progress and Poverty",
         author="Henry George", year="1879", category="ekonomi",
         extractor=generic_extract,
         description="George bertanya-tanya mengapa kemiskinan tetap ada bahkan saat kemajuan ekonomi berjalan pesat, dan jawabannya ada pada kepemilikan tanah: nilai tanah naik bukan karena kerja pemiliknya, tapi karena pertumbuhan masyarakat di sekitarnya. Solusinya, pajak tunggal atas tanah, sempat jadi gerakan politik besar di Amerika dan masih dibahas ekonom sampai sekarang."),
    dict(id="economic-consequences-peace", raw="pg15776.txt", gid=15776, title="The Economic Consequences of the Peace",
         author="John Maynard Keynes", year="1919", category="ekonomi",
         extractor=generic_extract,
         description="Keynes, yang ikut hadir sebagai delegasi di perundingan damai setelah Perang Dunia I, memperingatkan bahwa ganti rugi yang dibebankan ke Jerman terlalu berat dan akan menghancurkan ekonomi Eropa. Ramalannya soal bencana yang akan datang terbukti mengerikan tepat: krisis ekonomi Jerman ikut membuka jalan bagi kebangkitan Nazi."),
    dict(id="theory-of-moral-sentiments", raw="pg67363.txt", gid=67363, title="The Theory of Moral Sentiments",
         author="Adam Smith", year="1759", category="ekonomi",
         extractor=generic_extract,
         description="Sebelum menulis 'The Wealth of Nations', Smith lebih dulu menulis tentang bagaimana rasa simpati dan kepedulian terhadap orang lain membentuk moralitas manusia. Buku ini penting untuk memahami bahwa 'bapak ekonomi pasar bebas' sebenarnya percaya manusia bukan cuma makhluk egois yang mengejar untung sendiri."),
    dict(id="lombard-street", raw="pg4359.txt", gid=4359, title="Lombard Street",
         author="Walter Bagehot", year="1873", category="ekonomi",
         extractor=generic_extract,
         description="Bagehot membedah cara kerja pasar uang London dan merumuskan prinsip yang sampai sekarang jadi pegangan bank sentral saat krisis: pinjamkan dengan bebas, dengan jaminan bagus, dan dengan bunga tinggi. Buku teknis yang diam-diam jadi cetak biru bagaimana bank sentral modern menangani krisis keuangan."),
    dict(id="scientific-management", raw="pg6435.txt", gid=6435, title="The Principles of Scientific Management",
         author="Frederick Winslow Taylor", year="1911", category="ekonomi",
         extractor=generic_extract,
         description="Taylor mengusulkan agar pekerjaan pabrik diukur, dipecah, dan dioptimalkan dengan stopwatch layaknya eksperimen ilmiah demi efisiensi maksimal. Gagasan 'Taylorisme' ini membentuk lini produksi massal abad ke-20, sekaligus jadi simbol dehumanisasi tempat kerja yang terus dikritik sampai sekarang."),
    dict(id="unto-this-last", raw="pg36541.txt", gid=36541, title="Unto This Last",
         author="John Ruskin", year="1860", category="ekonomi",
         extractor=generic_extract,
         description="Ruskin menyerang ekonomi klasik yang menganggap manusia cuma mesin pengejar untung, dan berargumen 'tidak ada kekayaan selain kehidupan'. Buku yang awalnya dicemooh publik Inggris ini kelak sangat memengaruhi Gandhi, yang mengaku hidupnya berubah total setelah membacanya dalam perjalanan kereta."),
    dict(id="essentials-economic-theory", raw="pg31159.txt", gid=31159, title="Essentials of Economic Theory",
         author="John Bates Clark", year="1907", category="ekonomi",
         extractor=generic_extract,
         description="Clark meletakkan dasar teori produktivitas marjinal, gagasan bahwa upah dan keuntungan seharusnya mencerminkan nilai tambah yang benar-benar dihasilkan tiap faktor produksi. Jawaban langsung terhadap kritik sosialis macam Marx, dari salah satu ekonom Amerika paling berpengaruh di masanya."),
    dict(id="sophisms-protectionists", raw="pg20161.txt", gid=20161, title="Sophisms of the Protectionists",
         author="Frédéric Bastiat", year="1845", category="ekonomi",
         extractor=generic_extract,
         description="Bastiat membongkar argumen-argumen proteksionisme lewat sindiran tajam, termasuk satirenya yang terkenal soal petisi para pembuat lilin yang minta pemerintah memblokir sinar matahari karena dianggap 'pesaing tidak adil'. Cara paling menghibur untuk memahami mengapa ekonom masih berdebat soal tarif dan proteksi dagang sampai hari ini."),
    dict(id="up-from-slavery", raw="pg2376.txt", gid=2376, title="Up from Slavery",
         author="Booker T. Washington", year="1901", category="sosial",
         extractor=generic_extract,
         description="Washington menceritakan perjalanannya dari lahir sebagai budak sampai mendirikan Tuskegee Institute, sekolah yang mengajarkan keterampilan praktis untuk memberdayakan orang kulit hitam Amerika. Pendekatannya yang menekankan kerja keras dan akomodasi ketimbang konfrontasi politik langsung, sempat memicu perdebatan panjang dengan aktivis lain macam Du Bois."),
    dict(id="darkwater", raw="pg15210.txt", gid=15210, title="Darkwater",
         author="W. E. B. Du Bois", year="1920", category="sosial",
         extractor=generic_extract,
         description="Du Bois memadukan esai, puisi, dan cerita pendek untuk membongkar rasisme global dan menghubungkannya dengan perang, kolonialisme, dan posisi perempuan kulit hitam. Lebih eksperimental dan personal dibanding 'The Souls of Black Folk', ditulis di tengah kekecewaannya pada janji-janji pasca Perang Dunia I yang tak kunjung ditepati."),
    dict(id="hull-house", raw="pg1325.txt", gid=1325, title="Twenty Years at Hull-House",
         author="Jane Addams", year="1910", category="sosial",
         extractor=generic_extract,
         description="Addams menceritakan bagaimana dia dan rekan-rekannya mendirikan rumah komunitas di tengah kawasan miskin Chicago, tempat imigran bisa belajar, berkumpul, dan saling membantu. Salah satu catatan tangan pertama gerakan 'settlement house' yang jadi cikal bakal pekerjaan sosial modern."),
    dict(id="how-other-half-lives", raw="pg45502.txt", gid=45502, title="How the Other Half Lives",
         author="Jacob Riis", year="1890", category="sosial",
         extractor=generic_extract,
         description="Riis, seorang wartawan foto, mengungkap kondisi mengerikan permukiman kumuh New York yang selama ini tak terlihat oleh kelas menengah dan atas kota itu. Foto-fotonya yang mengejutkan publik ikut mendorong reformasi perumahan yang nyata, salah satu contoh awal jurnalisme investigatif mengubah kebijakan."),
    dict(id="women-and-economics", raw="pg57913.txt", gid=57913, title="Women and Economics",
         author="Charlotte Perkins Gilman", year="1898", category="sosial",
         extractor=generic_extract,
         description="Gilman berargumen ketergantungan ekonomi perempuan pada suami adalah akar dari ketidaksetaraan gender, bukan sekadar soal hak pilih atau hukum. Analisisnya menghubungkan feminisme dengan ekonomi jauh sebelum istilah itu populer, dan masih relevan tiap kali orang bicara soal kerja rumah tangga tak berbayar."),
    dict(id="subjection-of-women", raw="pg27083.txt", gid=27083, title="The Subjection of Women",
         author="John Stuart Mill", year="1869", category="sosial",
         extractor=generic_extract,
         description="Mill, dibantu istrinya Harriet Taylor, menulis argumen sistematis bahwa subordinasi perempuan bukan hukum alam melainkan kebiasaan yang dipaksakan sejak awal peradaban. Termasuk salah satu pembelaan hak perempuan paling awal dan paling gigih yang ditulis oleh seorang laki-laki di zamannya."),
    dict(id="the-crowd", raw="pg445.txt", gid=445, title="The Crowd",
         author="Gustave Le Bon", year="1895", category="sosial",
         extractor=generic_extract,
         description="Le Bon mengamati bagaimana individu yang tenang dan rasional bisa berubah jadi bagian dari massa yang impulsif dan mudah terbawa emosi begitu bergabung dalam kerumunan. Analisis psikologi massanya, walau kontroversial, jadi bacaan wajib diam-diam bagi banyak tokoh politik abad ke-20, termasuk yang menyalahgunakannya."),
    dict(id="dream-psychology", raw="pg15489.txt", gid=15489, title="Dream Psychology",
         author="Sigmund Freud", year="1920", category="sosial",
         extractor=generic_extract,
         description="Versi ringkas dan lebih ramah pembaca umum dari teori Freud tentang mimpi sebagai jendela ke alam bawah sadar dan keinginan yang direpresi. Pintu masuk paling gampang untuk memahami psikoanalisis, tanpa harus membaca 'The Interpretation of Dreams' yang jauh lebih tebal dan teknis."),
    dict(id="mutual-aid", raw="pg4341.txt", gid=4341, title="Mutual Aid: A Factor of Evolution",
         author="Peter Kropotkin", year="1902", category="sosial",
         extractor=generic_extract,
         description="Kropotkin membantah pembacaan Darwinisme sosial yang menekankan 'survival of the fittest' semata, dan menunjukkan lewat pengamatan alam bahwa kerja sama sama pentingnya dengan persaingan untuk bertahan hidup. Argumen ilmiah yang mendukung visi politiknya sendiri tentang masyarakat tanpa negara yang berbasis gotong royong."),
    dict(id="woman-and-labour", raw="pg1440.txt", gid=1440, title="Woman and Labour",
         author="Olive Schreiner", year="1911", category="sosial",
         extractor=generic_extract,
         description="Schreiner menyerukan agar perempuan diberi akses penuh ke semua jenis pekerjaan, dengan alasan masyarakat yang membiarkan separuh potensinya menganggur adalah masyarakat yang merugikan dirinya sendiri. Buku ini disebut sebagai 'kitab suci' gerakan suffragette pada masanya."),
    dict(id="self-help", raw="pg935.txt", gid=935, title="Self-Help",
         author="Samuel Smiles", year="1859", category="sosial",
         extractor=generic_extract,
         description="Smiles mengumpulkan kisah-kisah orang biasa yang berhasil lewat kerja keras, ketekunan, dan disiplin diri, tanpa bergantung pada bantuan negara atau warisan keluarga. Buku motivasi diri paling laris di era Victoria ini jadi cikal bakal seluruh genre self-help yang masih memenuhi rak toko buku sampai sekarang."),
    dict(id="kingdom-of-god-within-you", raw="pg43302.txt", gid=43302, title="The Kingdom of God Is Within You",
         author="Leo Tolstoy", year="1894", category="sosial",
         extractor=generic_extract,
         description="Tolstoy berargumen ajaran cinta kasih Yesus sebenarnya menuntut penolakan total terhadap kekerasan, termasuk kekerasan negara, dan mengkritik keras gereja resmi yang dianggapnya mengkhianati pesan itu. Buku yang kelak sangat memengaruhi Gandhi dalam merumuskan filosofi perlawanan tanpa kekerasan."),
    dict(id="what-is-art", raw="pg64908.txt", gid=64908, title="What Is Art?",
         author="Leo Tolstoy", year="1897", category="sosial",
         extractor=generic_extract,
         description="Tolstoy menolak gagasan seni untuk keindahan semata, dan berargumen seni sejati harus menyampaikan perasaan yang tulus dan menyatukan manusia, bukan sekadar hiburan kelas elite. Kriterianya begitu ketat sampai dia sendiri menolak sebagian karya besar Shakespeare dan bahkan novelnya sendiri."),
    dict(id="democracy-social-ethics", raw="pg15487.txt", gid=15487, title="Democracy and Social Ethics",
         author="Jane Addams", year="1902", category="sosial",
         extractor=generic_extract,
         description="Addams berargumen demokrasi sejati bukan cuma soal hak pilih di kotak suara, tapi harus terasa dalam hubungan sehari-hari antara majikan dan buruh, kaya dan miskin. Perspektifnya sebagai pekerja sosial lapangan membuat buku ini terasa jauh lebih membumi dibanding teori politik abstrak sezamannya."),
    dict(id="varieties-religious-experience", raw="pg621.txt", gid=621, title="The Varieties of Religious Experience",
         author="William James", year="1902", category="sosial",
         extractor=generic_extract,
         description="James meneliti pengalaman religius dari berbagai tradisi bukan untuk membuktikan atau membantah Tuhan, tapi untuk memahami mengapa pengalaman semacam itu begitu nyata dan transformatif bagi orang yang mengalaminya. Salah satu studi psikologi agama paling berpengaruh, ditulis oleh orang yang sendiri bergulat dengan depresi dan keraguan eksistensial."),
    dict(id="instinct-of-workmanship", raw="pg69888.txt", gid=69888, title="The Instinct of Workmanship",
         author="Thorstein Veblen", year="1914", category="sosial",
         extractor=generic_extract,
         description="Veblen berargumen manusia punya dorongan alami untuk bekerja secara efisien dan membuat sesuatu yang berguna, tapi dorongan ini terus dibelokkan oleh sistem kepemilikan dan status sosial. Pelengkap yang lebih optimis dari 'The Theory of the Leisure Class', kali ini menyoroti sisi produktif manusia, bukan cuma sisi pamernya."),
    dict(id="folkways", raw="pg24253.txt", gid=24253, title="Folkways",
         author="William Graham Sumner", year="1907", category="sosial",
         extractor=generic_extract,
         description="Sumner meneliti bagaimana kebiasaan sehari-hari yang tampak remeh, cara makan, tata krama, tabu, perlahan mengeras jadi norma moral yang dianggap mutlak oleh suatu masyarakat. Buku yang memperkenalkan istilah 'ethnocentrism', konsep yang sekarang jadi kosakata standar antropologi dan sosiologi."),
    dict(id="education-of-henry-adams", raw="pg2044.txt", gid=2044, title="The Education of Henry Adams",
         author="Henry Adams", year="1907", category="sosial",
         extractor=generic_extract,
         description="Adams menulis 'otobiografi' yang aneh: ditulis dalam sudut pandang orang ketiga, dan lebih banyak bicara soal kegagalan pendidikannya menghadapi dunia modern yang berubah begitu cepat lewat sains dan teknologi. Refleksi melankolis seorang keturunan presiden Amerika yang merasa dunia lama yang dia pahami sudah tak ada lagi."),

    # ------------------------------------------------------------------
    # Catalog-expansion PHASE 2: 51 new books appended after the 108
    # (22 fixed + 86 phase-1 expansion) above. Same generic_extract
    # pattern reused throughout; see NEW_BOOKS_ORDER_2 below for the
    # no-3-consecutive-category ordering.
    # ------------------------------------------------------------------
    dict(id="democracy-and-education", raw="pg852.txt", gid=852, title="Democracy and Education",
         author="John Dewey", year="1916", category="filsafat",
         extractor=generic_extract,
         description="Dewey berargumen sekolah bukan tempat menghafal fakta, tapi laboratorium demokrasi tempat anak belajar berpikir lewat pengalaman dan pemecahan masalah nyata. Salah satu buku filsafat pendidikan paling berpengaruh abad ke-20, masih dirujuk tiap kali orang mendebat kurikulum sekolah."),
    dict(id="life-of-reason", raw="pg15000.txt", gid=15000, title="The Life of Reason",
         author="George Santayana", year="1905", category="filsafat",
         extractor=generic_extract,
         description="Santayana mencoba memetakan bagaimana akal budi manusia berkembang lewat akal sehat, masyarakat, agama, seni, hingga sains, tanpa terjebak idealisme maupun materialisme kaku. Karya besar filsafat Amerika yang menyatukan naturalisme dengan penghargaan terhadap imajinasi dan nilai-nilai manusiawi."),
    dict(id="political-obligation-green", raw="pg61889.txt", gid=61889, title="Lectures on the Principles of Political Obligation",
         author="Thomas Hill Green", year="1895", category="politik",
         extractor=generic_extract,
         description="Green mempertanyakan dari mana sebenarnya kewajiban warga negara untuk taat pada hukum berasal, dan menjawabnya lewat gagasan bahwa negara ada untuk memungkinkan kebebasan sejati, bukan sekadar membatasinya. Fondasi penting liberalisme baru Inggris yang lebih menerima peran negara ketimbang liberalisme klasik sebelumnya."),
    dict(id="general-view-of-positivism", raw="pg53799.txt", gid=53799, title="A General View of Positivism",
         author="Auguste Comte", year="1848", category="filsafat",
         extractor=generic_extract,
         description="Comte, pencipta istilah 'sosiologi', merangkum visinya tentang tahap akhir perkembangan pemikiran manusia: meninggalkan teologi dan metafisika demi ilmu pengetahuan positif yang bisa diverifikasi. Ringkasan paling ringkas dari sistem filsafat yang ambisinya tak kurang dari menata ulang seluruh peradaban."),
    dict(id="methods-of-ethics", raw="pg46743.txt", gid=46743, title="The Methods of Ethics",
         author="Henry Sidgwick", year="1874", category="filsafat",
         extractor=generic_extract,
         description="Sidgwick membedah dengan sangat cermat tiga cara utama manusia menilai benar-salah, intuisi, egoisme, dan utilitarianisme, lalu jujur mengakui ketiganya sulit didamaikan sepenuhnya. Dianggap salah satu karya etika paling ketat dan berpengaruh dalam filsafat berbahasa Inggris."),
    dict(id="history-of-rome-mommsen-1", raw="pg10701.txt", gid=10701, title="The History of Rome, Book I",
         author="Theodor Mommsen", year="1854", category="sejarah",
         extractor=generic_extract,
         description="Mommsen menulis ulang sejarah Roma awal dengan ketelitian filologis yang belum pernah ada sebelumnya, sekaligus gaya bercerita yang membuatnya memenangkan Hadiah Nobel Sastra. Buku I ini mengupas era sebelum runtuhnya monarki, fondasi bagi salah satu karya sejarah Romawi paling berpengaruh yang pernah ditulis."),
    dict(id="human-nature-in-politics", raw="pg11634.txt", gid=11634, title="Human Nature in Politics",
         author="Graham Wallas", year="1908", category="politik",
         extractor=generic_extract,
         description="Wallas menantang asumsi bahwa manusia berpolitik secara rasional, dan berargumen kebiasaan, emosi, serta prasangka jauh lebih menentukan pilihan politik ketimbang argumen logis semata. Salah satu buku pertama yang menerapkan psikologi modern untuk memahami perilaku pemilih dan politisi."),
    dict(id="sources-of-religious-insight", raw="pg33677.txt", gid=33677, title="The Sources of Religious Insight",
         author="Josiah Royce", year="1912", category="filsafat",
         extractor=generic_extract,
         description="Royce, filsuf idealis Amerika, mencari dari mana wawasan religius sejati sebenarnya berasal, pengalaman pribadi, alam, akal, atau komunitas, dan berargumen loyalitas pada komunitas adalah kunci yang sering terlewat. Ditulis oleh salah satu pemikir paling dihormati di generasi filsuf Harvard bersama William James."),
    dict(id="oregon-trail", raw="pg1015.txt", gid=1015, title="The Oregon Trail",
         author="Francis Parkman", year="1849", category="sejarah",
         extractor=generic_extract,
         description="Parkman menempuh jalur pionir ke barat Amerika saat masih muda dan sedang sakit-sakitan, lalu menuliskan pengalamannya bertemu suku asli, pemburu bulu, dan pedagang di padang rumput yang belum banyak disentuh orang kulit putih. Catatan perjalanan yang jadi jendela langsung ke Amerika Barat sebelum benar-benar berubah oleh ekspansi rel kereta."),
    dict(id="socialism-social-movement", raw="pg35210.txt", gid=35210, title="Socialism and the Social Movement in the 19th Century",
         author="Werner Sombart", year="1909", category="ekonomi",
         extractor=generic_extract,
         description="Sombart, ekonom Jerman yang dekat dengan gerakan buruh, memetakan sejarah gagasan sosialisme dari utopis awal sampai Marxisme yang jadi kekuatan politik nyata di Eropa. Salah satu tinjauan paling jernih tentang bagaimana kritik terhadap kapitalisme berkembang jadi gerakan massa terorganisir."),
    dict(id="no-treason", raw="pg36145.txt", gid=36145, title="No Treason",
         author="Lysander Spooner", year="1867", category="politik",
         extractor=generic_extract,
         description="Spooner berargumen Konstitusi Amerika tidak bisa mengikat siapa pun yang tidak pernah benar-benar menandatanganinya secara sukarela, sehingga negara tidak punya otoritas moral sejati atas warganya. Salah satu argumen anarkis-individualis paling tajam yang pernah ditulis dari dalam tradisi hukum Amerika sendiri."),
    dict(id="essence-of-christianity", raw="pg47025.txt", gid=47025, title="The Essence of Christianity",
         author="Ludwig Feuerbach", year="1841", category="filsafat",
         extractor=generic_extract,
         description="Feuerbach berargumen Tuhan sebenarnya adalah proyeksi dari sifat-sifat terbaik manusia sendiri yang dilemparkan ke langit dan disembah seolah-olah asing. Buku yang mengguncang teologi Jerman abad ke-19 ini kelak jadi salah satu fondasi yang dibalik Marx untuk membangun materialisme historisnya sendiri."),
    dict(id="norman-conquest-freeman", raw="pg68963.txt", gid=68963, title="A Short History of the Norman Conquest of England",
         author="Edward A. Freeman", year="1880", category="sejarah",
         extractor=generic_extract,
         description="Freeman meringkas penaklukan Norman atas Inggris tahun 1066, peristiwa yang mengubah total bahasa, hukum, dan kelas penguasa Inggris dalam semalam. Versi ringkas dari karya multi-jilidnya yang jauh lebih tebal, ditulis untuk pembaca yang ingin memahami inti ceritanya tanpa tenggelam dalam detail teknis."),
    dict(id="society-in-america", raw="pg52621.txt", gid=52621, title="Society in America (Vol. 1)",
         author="Harriet Martineau", year="1837", category="sosial",
         extractor=generic_extract,
         description="Martineau, penulis Inggris yang tuli sejak muda, berkelana ke seluruh Amerika dan menulis pengamatan tajam tentang perbudakan, posisi perempuan, dan institusi demokrasi negara muda itu. Analisisnya kerap dibandingkan dengan Tocqueville, tapi lebih berani menyerang kemunafikan Amerika soal kesetaraan."),
    dict(id="economic-interpretation-constitution", raw="pg70677.txt", gid=70677, title="An Economic Interpretation of the Constitution of the United States",
         author="Charles A. Beard", year="1913", category="ekonomi",
         extractor=generic_extract,
         description="Beard mengejutkan Amerika dengan berargumen para pendiri bangsa yang merancang Konstitusi punya kepentingan ekonomi pribadi yang jelas, pemilik obligasi, tanah, budak, bukan cuma idealisme murni tanpa pamrih. Analisis kontroversial yang memaksa orang Amerika melihat dokumen paling sucinya dengan mata yang jauh lebih kritis."),
    dict(id="republic-of-cicero", raw="pg54161.txt", gid=54161, title="The Republic of Cicero",
         author="Cicero", year="±51 SM", category="politik",
         extractor=generic_extract,
         description="Cicero merancang dialog tentang negara ideal ala Romawi, memadukan pemikiran Yunani dengan pengalaman politik nyatanya sendiri sebagai negarawan Republik Roma yang sedang di ambang keruntuhan. Naskahnya sempat hilang berabad-abad dan baru ditemukan kembali di abad ke-19 tertimpa naskah lain di perpustakaan Vatikan."),
    dict(id="lives-eminent-philosophers", raw="pg57342.txt", gid=57342, title="The Lives and Opinions of Eminent Philosophers",
         author="Diogenes Laertius", year="±225 M", category="filsafat",
         extractor=generic_extract,
         description="Diogenes Laertius mengumpulkan gosip, anekdot, dan ajaran hampir semua filsuf Yunani penting, dari Thales sampai Epicurus, jadi satu koleksi biografi yang jadi sumber utama sejarawan filsafat berabad-abad kemudian. Kadang tidak akurat, tapi tanpa buku ini banyak detail hidup para filsuf kuno akan hilang total."),
    dict(id="history-of-england-ranke-1", raw="pg28546.txt", gid=28546, title="A History of England, Principally in the Seventeenth Century (Vol. 1)",
         author="Leopold von Ranke", year="1875", category="sejarah",
         extractor=generic_extract,
         description="Ranke, bapak sejarah modern yang bersikeras menulis 'sejarah sebagaimana sebenarnya terjadi', membedah Inggris abad ke-17 yang penuh gejolak perang saudara dan pergantian rezim. Volume pertama ini menunjukkan metode sumber primernya yang ketat, standar yang mengubah cara sejarawan bekerja di seluruh dunia."),
    dict(id="southern-horrors", raw="pg14975.txt", gid=14975, title="Southern Horrors: Lynch Law in All Its Phases",
         author="Ida B. Wells", year="1892", category="sosial",
         extractor=generic_extract,
         description="Wells membongkar dengan data dan nama-nama korban, bahwa tuduhan yang biasa dipakai untuk membenarkan pembunuhan massal (lynching) terhadap orang kulit hitam Amerika sebagian besar cuma kedok untuk kontrol ekonomi dan rasial. Pamflet berani yang membuat percetakan korannya dihancurkan massa dan dirinya diancam bunuh."),
    dict(id="accumulation-of-capital", raw="pg41405.txt", gid=41405, title="The Accumulation of Capital",
         author="Rosa Luxemburg", year="1913", category="ekonomi",
         extractor=generic_extract,
         description="Luxemburg berargumen kapitalisme tidak bisa bertahan hanya dengan mengeksploitasi kelas pekerjanya sendiri, dan karena itu selalu butuh menaklukkan pasar-pasar baru di luar sistemnya, penjelasan ekonomi di balik imperialisme. Karya teoretis paling ambisius dari salah satu pemikir Marxis perempuan paling berpengaruh, ditulis tak lama sebelum dia dibunuh milisi sayap kanan."),
    dict(id="news-from-nowhere", raw="pg3261.txt", gid=3261, title="News from Nowhere",
         author="William Morris", year="1890", category="politik",
         extractor=generic_extract,
         description="Morris membayangkan Inggris masa depan setelah revolusi sosialis, tempat pabrik-pabrik kotor diganti kerajinan tangan yang indah dan kerja jadi sumber kegembiraan, bukan keterpaksaan. Utopia romantis yang menolak industrialisasi modern demi visi masyarakat yang lebih manusiawi dan estetis."),
    dict(id="hegel-history-of-philosophy-1", raw="pg51635.txt", gid=51635, title="Hegel's Lectures on the History of Philosophy (Vol. 1)",
         author="G. W. F. Hegel", year="1892", category="filsafat",
         extractor=generic_extract,
         description="Hegel menelusuri sejarah filsafat sebagai proses akal budi yang perlahan-lahan menyadari dirinya sendiri lewat tesis, antitesis, dan sintesis dari satu pemikir ke pemikir berikutnya. Volume pertama ini dimulai dari para filsuf Yunani awal, ditulis dengan gaya sistematis khas Hegel yang terkenal berat tapi berpengaruh luas."),
    dict(id="critical-period-american-history", raw="pg27430.txt", gid=27430, title="The Critical Period of American History",
         author="John Fiske", year="1888", category="sejarah",
         extractor=generic_extract,
         description="Fiske menyoroti tahun-tahun genting antara kemenangan Revolusi Amerika dan pengesahan Konstitusi, masa ketika negara baru itu nyaris bubar karena utang, pemberontakan, dan pemerintah pusat yang terlalu lemah. Narasi populer yang menjelaskan mengapa para pendiri bangsa akhirnya sepakat butuh pemerintahan federal yang jauh lebih kuat."),
    dict(id="culture-and-anarchy", raw="pg4212.txt", gid=4212, title="Culture and Anarchy",
         author="Matthew Arnold", year="1869", category="sosial",
         extractor=generic_extract,
         description="Arnold mengkritik masyarakat Inggris Victorian yang menurutnya terlalu sibuk mengejar uang dan kebebasan individual tanpa arah, dan menyerukan 'kebudayaan', pengejaran kesempurnaan lewat yang terbaik dari pemikiran dan seni, sebagai penyeimbangnya. Salah satu kritik budaya paling berpengaruh abad ke-19 yang istilahnya masih dipakai sampai sekarang."),
    dict(id="political-economy-jevons", raw="pg33219.txt", gid=33219, title="Political Economy",
         author="William Stanley Jevons", year="1878", category="ekonomi",
         extractor=generic_extract,
         description="Jevons, salah satu bapak revolusi marjinalis dalam ekonomi, merangkum dalam buku pengantar singkat bagaimana nilai suatu barang sebenarnya ditentukan oleh kepuasan tambahan yang diberikan unit terakhirnya, bukan sekadar biaya produksi. Pengantar populer dari pemikiran yang mengubah total arah teori ekonomi di akhir abad ke-19."),
    dict(id="looking-backward", raw="pg624.txt", gid=624, title="Looking Backward, 2000 to 1887",
         author="Edward Bellamy", year="1888", category="politik",
         extractor=generic_extract,
         description="Bellamy membuat seorang pria Boston tertidur tahun 1887 dan bangun tahun 2000 di Amerika yang telah berubah jadi masyarakat sosialis tanpa kemiskinan atau persaingan kejam. Novel utopis yang begitu populer sampai memicu gerakan politik nyata bernama 'Nationalism' di seluruh Amerika."),
    dict(id="crito", raw="pg1657.txt", gid=1657, title="Crito",
         author="Plato", year="±399 SM", category="filsafat",
         extractor=generic_extract,
         description="Sahabat Socrates, Crito, menawarkan rencana pelarian dari penjara sebelum eksekusi, tapi Socrates menolak dengan argumen bahwa melarikan diri berarti mengkhianati kontrak sosialnya sendiri dengan hukum kota yang membesarkannya. Dialog pendek tentang kenapa kadang taat pada hukum yang tidak adil tetap lebih bermartabat daripada melanggarnya diam-diam."),
    dict(id="history-of-civil-society", raw="pg8646.txt", gid=8646, title="An Essay on the History of Civil Society",
         author="Adam Ferguson", year="1767", category="sejarah",
         extractor=generic_extract,
         description="Ferguson, salah satu tokoh Pencerahan Skotlandia, mengamati bagaimana masyarakat manusia bergerak dari kesukuan menuju peradaban lewat tahapan yang bisa dipelajari seperti ilmu alam. Salah satu cikal bakal sosiologi modern, ditulis jauh sebelum istilah itu sendiri ada."),
    dict(id="voice-from-the-south", raw="pg61741.txt", gid=61741, title="A Voice from the South",
         author="Anna Julia Cooper", year="1892", category="sosial",
         extractor=generic_extract,
         description="Cooper, salah satu perempuan kulit hitam Amerika pertama yang meraih gelar doktor, berargumen kemajuan sejati ras dan bangsa hanya mungkin kalau perempuan kulit hitam juga diberi pendidikan dan suara penuh. Salah satu teks feminisme kulit hitam paling awal, mendahului istilah 'intersectionality' hampir seabad."),
    dict(id="political-oeconomy-steuart-1", raw="pg60411.txt", gid=60411, title="An Inquiry into the Principles of Political Oeconomy (Vol. 1)",
         author="James Steuart", year="1767", category="ekonomi",
         extractor=generic_extract,
         description="Steuart menulis risalah sistematis pertama berbahasa Inggris tentang ekonomi politik, hampir sepuluh tahun sebelum 'The Wealth of Nations' karya Adam Smith yang kelak menenggelamkan namanya. Volume pertama ini menunjukkan pemikiran ekonomi yang jauh lebih percaya pada campur tangan negara ketimbang Smith yang menyusul setelahnya."),
    dict(id="right-to-ignore-the-state", raw="pg34649.txt", gid=34649, title="The Right to Ignore the State",
         author="Herbert Spencer", year="1851", category="politik",
         extractor=generic_extract,
         description="Spencer, sebelum jadi filsuf evolusi sosial yang lebih dikenal, sempat berargumen individu punya hak moral untuk menolak tunduk pada negara yang dianggapnya tidak sah. Esai awal yang kelak dia coba jauhi sendiri karena dianggap terlalu radikal dibanding pemikirannya di kemudian hari."),
    dict(id="critique-practical-reason", raw="pg5683.txt", gid=5683, title="The Critique of Practical Reason",
         author="Immanuel Kant", year="1788", category="filsafat",
         extractor=generic_extract,
         description="Kant melanjutkan proyek besarnya dengan bertanya bukan apa yang bisa kita ketahui, tapi apa yang seharusnya kita lakukan, dan menjawabnya lewat kehendak bebas serta hukum moral yang berlaku universal. Pelengkap penting 'Critique of Pure Reason', kali ini fokus penuh pada etika."),
    dict(id="civilisation-renaissance-italy", raw="pg2074.txt", gid=2074, title="The Civilisation of the Renaissance in Italy",
         author="Jacob Burckhardt", year="1860", category="sejarah",
         extractor=generic_extract,
         description="Burckhardt-lah yang pertama kali membingkai Renaissance Italia sebagai kelahiran kembali individualisme modern, era ketika manusia mulai melihat dirinya sebagai pribadi unik, bukan sekadar anggota kelompok atau kelas. Buku yang menciptakan cara orang memahami dan menyebut periode itu sampai sekarang."),
    dict(id="eighty-years-and-more", raw="pg11982.txt", gid=11982, title="Eighty Years and More",
         author="Elizabeth Cady Stanton", year="1898", category="sosial",
         extractor=generic_extract,
         description="Stanton menceritakan delapan dekade hidupnya sebagai salah satu penggerak utama gerakan hak pilih perempuan Amerika, dari konvensi Seneca Falls yang dia gagas sampai perjuangan panjang yang belum sepenuhnya dia lihat berhasil. Memoar penuh energi dari sosok yang menyulut gerakan feminis Amerika modern."),
    dict(id="what-is-property", raw="pg360.txt", gid=360, title="What is Property?",
         author="Pierre-Joseph Proudhon", year="1840", category="ekonomi",
         extractor=generic_extract,
         description="Proudhon menjawab pertanyaan judulnya sendiri dengan kalimat yang jadi terkenal: 'Properti adalah pencurian.' Argumen provokatif yang menuduh kepemilikan pribadi atas tanah dan modal sebagai bentuk eksploitasi terselubung, fondasi penting bagi tradisi pemikiran anarkis yang menyusul setelahnya."),
    dict(id="plato-laws", raw="pg1750.txt", gid=1750, title="Laws",
         author="Plato", year="±348 SM", category="politik",
         extractor=generic_extract,
         description="Karya terakhir dan terpanjang Plato ini meninggalkan raja-filsuf dari 'Republic' demi rancangan negara yang lebih realistis, diatur lewat hukum tertulis yang rinci ketimbang kebijaksanaan satu penguasa ideal. Plato yang lebih tua dan lebih pragmatis, menerima bahwa manusia biasa butuh aturan konkret, bukan cuma visi abstrak keadilan."),
    dict(id="dialogues-natural-religion", raw="pg4583.txt", gid=4583, title="Dialogues Concerning Natural Religion",
         author="David Hume", year="1779", category="filsafat",
         extractor=generic_extract,
         description="Diterbitkan setelah Hume wafat karena isinya dianggap terlalu berbahaya semasa hidupnya, tiga tokoh berdebat lewat dialog apakah keteraturan alam semesta benar-benar membuktikan keberadaan Tuhan yang bijaksana. Salah satu kritik paling elegan terhadap argumen desain yang pernah ditulis."),
    dict(id="history-of-rome-livy-1", raw="pg19725.txt", gid=19725, title="The History of Rome, Books 1 to 8",
         author="Livy", year="±25 SM", category="sejarah",
         extractor=generic_extract,
         description="Livy menulis ulang legenda pendirian Roma, dari Romulus dan Remus sampai perjuangan republik awal melawan tetangga-tetangganya, dengan gaya yang lebih mementingkan keteladanan moral ketimbang akurasi sejarah semata. Buku 1 sampai 8 ini salah satu sumber paling berpengaruh tentang bagaimana orang Romawi sendiri ingin mengingat asal-usul mereka."),
    dict(id="narrative-of-sojourner-truth", raw="pg1674.txt", gid=1674, title="The Narrative of Sojourner Truth",
         author="Sojourner Truth", year="1850", category="sosial",
         extractor=generic_extract,
         description="Sojourner Truth, yang tak pernah belajar membaca-menulis, mendiktekan kisah hidupnya sebagai budak yang lahir di negara bagian utara sebelum akhirnya bebas dan jadi penceramah keliling menentang perbudakan dan memperjuangkan hak perempuan. Kesaksian langsung yang jarang tandingannya soal perpotongan ras dan gender di Amerika abad ke-19."),
    dict(id="great-illusion", raw="pg38535.txt", gid=38535, title="The Great Illusion",
         author="Norman Angell", year="1910", category="ekonomi",
         extractor=generic_extract,
         description="Angell berargumen perang antarnegara industri modern secara ekonomi tidak masuk akal, karena penaklukan tidak lagi mendatangkan keuntungan sepadan di dunia yang saling terhubung lewat perdagangan dan keuangan. Diterbitkan hanya beberapa tahun sebelum Perang Dunia I meletus, ironi yang membuatnya jadi bahan perdebatan berabad-abad."),
    dict(id="eighteenth-brumaire", raw="pg1346.txt", gid=1346, title="The Eighteenth Brumaire of Louis Napoleon",
         author="Karl Marx", year="1852", category="politik",
         extractor=generic_extract,
         description="Marx menganalisis bagaimana Louis Napoleon bisa merebut kekuasaan lewat kudeta yang menurutnya lebih mirip lelucon ketimbang tragedi, mengulang gaya pamannya Napoleon Bonaparte tapi dalam skala yang jauh lebih murahan. Sumber kutipan terkenal 'sejarah berulang, pertama sebagai tragedi, lalu sebagai lelucon'."),
    dict(id="emile", raw="pg5427.txt", gid=5427, title="Emile",
         author="Jean-Jacques Rousseau", year="1762", category="filsafat",
         extractor=generic_extract,
         description="Rousseau merancang pendidikan ideal lewat kisah seorang anak fiktif bernama Emile, yang dibiarkan belajar dari pengalaman langsung dan alam ketimbang dijejali buku dan disiplin kaku sejak dini. Buku yang mengubah total cara Eropa memikirkan pendidikan anak, meski penulisnya sendiri menitipkan semua anaknya ke panti asuhan."),
    dict(id="history-of-england-macaulay-1", raw="pg1468.txt", gid=1468, title="The History of England, from the Accession of James II (Vol. 1)",
         author="Thomas Babington Macaulay", year="1848", category="sejarah",
         extractor=generic_extract,
         description="Macaulay menulis sejarah Inggris dengan gaya prosa begitu memikat sampai jadi buku terlaris di zamannya, dimulai dari naik takhtanya James II yang berujung pada Revolusi Agung. Volume pertama ini menunjukkan mengapa Macaulay dianggap salah satu penulis sejarah naratif paling enak dibaca dalam bahasa Inggris."),
    dict(id="my-own-story-pankhurst", raw="pg34856.txt", gid=34856, title="My Own Story",
         author="Emmeline Pankhurst", year="1914", category="sosial",
         extractor=generic_extract,
         description="Pankhurst menceritakan bagaimana dia dan gerakan suffragette Inggris beralih dari petisi sopan ke aksi militan, mogok makan, pemboman properti, penjara berulang kali, demi memaksa negara memberi perempuan hak suara. Memoar yang menunjukkan sisi paling radikal dan berani dari perjuangan hak pilih perempuan."),
    dict(id="unsettled-questions-political-economy", raw="pg12004.txt", gid=12004, title="Essays on Some Unsettled Questions of Political Economy",
         author="John Stuart Mill", year="1844", category="ekonomi",
         extractor=generic_extract,
         description="Mill menggarap sejumlah soal teknis yang belum tuntas dijawab ekonom-ekonom sebelumnya, dari perdagangan internasional sampai definisi produktif tidaknya kerja tertentu. Karya awal yang menunjukkan Mill sedang mengasah kemampuannya sebelum menulis karya-karya besarnya yang lebih terkenal."),
    dict(id="the-law-bastiat", raw="pg44800.txt", gid=44800, title="The Law",
         author="Frédéric Bastiat", year="1850", category="politik",
         extractor=generic_extract,
         description="Bastiat berargumen hukum seharusnya hanya melindungi hak-hak alami manusia, hidup, kebebasan, properti, dan berubah jadi alat perampokan terselubung begitu dipakai untuk mengambil dari satu kelompok demi menguntungkan kelompok lain. Esai pendek dan tajam yang masih jadi rujukan utama argumen pasar bebas melawan campur tangan negara."),
    dict(id="sartor-resartus", raw="pg1051.txt", gid=1051, title="Sartor Resartus",
         author="Thomas Carlyle", year="1836", category="filsafat",
         extractor=generic_extract,
         description="Carlyle menciptakan seorang filsuf Jerman fiktif yang berargumen segala institusi masyarakat, pakaian, agama, negara, cuma 'pakaian' simbolis yang membungkus kebenaran spiritual di baliknya. Ditulis dengan gaya eksentrik dan setengah bercanda, tapi jadi salah satu karya paling berpengaruh yang menjembatani Romantisisme Jerman ke sastra Inggris."),
    dict(id="my-bondage-my-freedom", raw="pg202.txt", gid=202, title="My Bondage and My Freedom",
         author="Frederick Douglass", year="1855", category="sejarah",
         extractor=generic_extract,
         description="Sepuluh tahun setelah 'Narrative' pertamanya, Douglass menulis ulang kisah hidupnya jauh lebih panjang dan tajam, kini sebagai orang bebas yang tak lagi perlu menahan diri demi keselamatan. Versi yang lebih matang dan lebih berani menyerang langsung institusi perbudakan serta kemunafikan yang menopangnya."),
    dict(id="autobiography-mill", raw="pg10378.txt", gid=10378, title="Autobiography",
         author="John Stuart Mill", year="1873", category="sosial",
         extractor=generic_extract,
         description="Mill menceritakan pendidikan ekstremnya sejak kecil, krisis mental yang nyaris menghancurkannya di usia dua puluhan, dan bagaimana dia menemukan kembali makna hidup lewat puisi dan cinta pada Harriet Taylor. Memoar intelektual yang jujur tentang harga yang harus dibayar seorang jenius didikan yang terlalu sempurna."),
    dict(id="fields-factories-workshops", raw="pg64353.txt", gid=64353, title="Fields, Factories and Workshops",
         author="Peter Kropotkin", year="1899", category="ekonomi",
         extractor=generic_extract,
         description="Kropotkin membayangkan masa depan tempat pertanian, industri, dan kerja intelektual digabung dalam komunitas kecil yang mandiri, alih-alih dipisah jauh seperti dalam kapitalisme industrial. Visi desentralisasi ekonomi yang optimis, ditulis oleh seorang pangeran Rusia yang memilih jadi anarkis."),
    dict(id="cyropaedia", raw="pg2085.txt", gid=2085, title="Cyropaedia",
         author="Xenophon", year="±370 SM", category="politik",
         extractor=generic_extract,
         description="Xenophon menulis semi-biografi Cyrus Agung, pendiri Kekaisaran Persia, sebagai model bagaimana seorang pemimpin ideal seharusnya dididik dan memerintah. Separuh sejarah separuh fiksi didaktik, buku ini jadi salah satu 'cermin bagi pangeran' paling awal yang memengaruhi pemikiran kepemimpinan berabad-abad kemudian."),

    # --- Tambahan anarkisme (politik & sosial) ---
    dict(id="anarchy", raw="pg40365.txt", gid=40365, title="Anarchy",
         author="Errico Malatesta", year="1891", category="politik",
         extractor=generic_extract,
         description="Pengantar anarkisme paling ringkas dan jernih yang pernah ditulis: Malatesta membongkar anggapan bahwa masyarakat mustahil hidup tanpa pemerintah, lalu menjelaskan bagaimana kerja sama sukarela bisa menggantikan paksaan negara. Ditulis untuk buruh biasa, bukan akademisi."),
    dict(id="ego-and-his-own", raw="pg34580.txt", gid=34580, title="The Ego and His Own",
         author="Max Stirner", year="1844", category="politik",
         extractor=generic_extract,
         description="Serangan filosofis radikal terhadap segala 'hantu' yang menuntut kepatuhan individu—negara, Tuhan, moralitas, bahkan kemanusiaan itu sendiri. Stirner menempatkan diri yang berdaulat di atas semua abstraksi, menjadikan buku ini fondasi anarkisme individualis dan mimpi buruk bagi setiap ideologi."),
    dict(id="prison-memoirs-anarchist", raw="pg34406.txt", gid=34406, title="Prison Memoirs of an Anarchist",
         author="Alexander Berkman", year="1912", category="sosial",
         extractor=generic_extract,
         description="Memoar mentah dari empat belas tahun di penjara Pennsylvania setelah upaya pembunuhan politik yang gagal. Berkman menuliskan kekerasan, persahabatan, dan perlahan runtuhnya keyakinannya pada kekerasan itu sendiri—salah satu kesaksian penjara paling jujur dalam literatur anarkis."),
    dict(id="civil-disobedience", raw="pg71.txt", gid=71, title="On the Duty of Civil Disobedience",
         author="Henry David Thoreau", year="1849", category="sosial",
         extractor=generic_extract,
         description="Esai singkat yang lahir dari semalam Thoreau di penjara karena menolak membayar pajak untuk perang dan perbudakan. Argumennya—bahwa hati nurani individu berdiri di atas hukum negara—kelak mengilhami Gandhi dan Martin Luther King, dan jadi teks wajib bagi setiap gerakan pembangkangan sipil."),
    dict(id="my-disillusionment-russia", raw="pg60315.txt", gid=60315, title="My Disillusionment in Russia",
         author="Emma Goldman", year="1923", category="sosial",
         extractor=generic_extract,
         description="Goldman menyambut Revolusi Rusia dengan penuh harap, lalu menyaksikan langsung bagaimana negara Bolshevik menindas kebebasan yang dijanjikannya. Catatan kekecewaan ini membuatnya dikucilkan kiri, tapi terbukti tajam meramalkan ke mana kekuasaan terpusat akan bermuara."),
]

INDEX_ORDER = [
    "the-prince", "meditations", "art-of-war", "wealth-of-nations", "utopia",
    "communist-manifesto", "republic", "decline-and-fall", "political-economy",
    "democracy-in-america", "on-liberty", "beyond-good-and-evil", "herodotus",
    "leisure-class", "souls-black-folk", "second-treatise", "tao-te-ching",
    "peloponnesian-war", "rights-of-woman", "leviathan", "walden", "common-sense",
]

# The 86 new catalog-expansion books, appended AFTER the fixed 22 above.
# Order precomputed so no 3 consecutive books (across the whole index,
# including the old/new boundary) share the same category. See
# order_new_books.py in the scratch dir for the scheduling algorithm.
NEW_BOOKS_ORDER = [
    "apology", "symposium", "up-from-slavery", "phaedo", "gorgias", "darkwater", "nicomachean-ethics", "poetics", "plutarchs-lives-1", "enchiridion", "discourses-epictetus", "hull-house", "on-the-nature-of-things", "consolation-of-philosophy", "gallic-war", "discourse-on-method", "ethics-spinoza", "how-other-half-lives", "enquiry-human-understanding", "treatise-human-nature", "annals-tacitus", "metaphysic-of-morals", "thus-spake-zarathustra", "women-and-economics", "genealogy-of-morals", "politics-aristotle", "germany-and-agricola", "subjection-of-women", "twilight-of-the-idols", "federalist-papers", "anabasis", "the-crowd", "the-antichrist", "social-contract", "twelve-caesars", "dream-psychology", "studies-in-pessimism", "rights-of-man", "french-revolution-carlyle", "critique-political-economy", "mutual-aid", "utilitarianism", "conciliation-with-america", "short-history-of-world", "principle-of-population", "woman-and-labour", "essays-bacon", "representative-government", "autobiography-franklin", "progress-and-poverty", "self-help", "essay-humane-understanding", "discourses-on-livy", "narrative-frederick-douglass", "economic-consequences-peace", "kingdom-of-god-within-you", "human-knowledge-berkeley", "anarchism-and-other-essays", "travels-marco-polo-1", "theory-of-moral-sentiments", "what-is-art", "pragmatism", "english-constitution", "histories-of-polybius-1", "lombard-street", "democracy-social-ethics", "problems-of-philosophy", "god-and-the-state", "herodotus-2", "scientific-management", "varieties-religious-experience", "essays-first-series", "conquest-of-bread", "decline-and-fall-2", "unto-this-last", "instinct-of-workmanship", "analects-confucius", "democracy-in-america-2", "life-of-charlemagne", "essentials-economic-theory", "folkways", "pensees", "discourse-on-inequality", "wars-of-the-jews", "sophisms-protectionists", "education-of-henry-adams"
]

# The 51 new catalog-expansion-phase-2 books, appended AFTER the 108
# above (22 fixed + 86 phase-1). Order precomputed (round-robin by
# category, largest-remaining-first) so no 3 consecutive books share a
# category across the FULL final index, including the boundary with the
# phase-1 tail above (which ends in "sosial").
NEW_BOOKS_ORDER_2 = [
    "democracy-and-education", "life-of-reason", "political-obligation-green", "general-view-of-positivism", "methods-of-ethics", "history-of-rome-mommsen-1", "human-nature-in-politics", "sources-of-religious-insight", "oregon-trail", "socialism-social-movement", "no-treason", "essence-of-christianity", "norman-conquest-freeman", "society-in-america", "economic-interpretation-constitution", "republic-of-cicero", "lives-eminent-philosophers", "history-of-england-ranke-1", "southern-horrors", "accumulation-of-capital", "news-from-nowhere", "hegel-history-of-philosophy-1", "critical-period-american-history", "culture-and-anarchy", "political-economy-jevons", "looking-backward", "crito", "history-of-civil-society", "voice-from-the-south", "political-oeconomy-steuart-1", "right-to-ignore-the-state", "critique-practical-reason", "civilisation-renaissance-italy", "eighty-years-and-more", "what-is-property", "plato-laws", "dialogues-natural-religion", "history-of-rome-livy-1", "narrative-of-sojourner-truth", "great-illusion", "eighteenth-brumaire", "emile", "history-of-england-macaulay-1", "my-own-story-pankhurst", "unsettled-questions-political-economy", "the-law-bastiat", "sartor-resartus", "my-bondage-my-freedom", "autobiography-mill", "fields-factories-workshops", "cyropaedia", "prison-memoirs-anarchist", "anarchy", "civil-disobedience", "ego-and-his-own", "my-disillusionment-russia"
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
            paras_clean = [p for p in paras_clean if p.strip()]
            # Safety net against digitizer/transcriber-note leakage (e.g.
            # "E-text prepared by ...", "Note: Project Gutenberg also has an
            # HTML version ..."). None of these 108 source texts predate
            # Project Gutenberg, so any paragraph mentioning it is always
            # boilerplate metadata, never original content -- safe to drop
            # unconditionally for both old and new books.
            paras_clean = [p for p in paras_clean if "gutenberg" not in p.lower()]
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
    full_order = INDEX_ORDER + NEW_BOOKS_ORDER + NEW_BOOKS_ORDER_2
    missing_order = set(index_by_id) - set(full_order)
    missing_entries = set(full_order) - set(index_by_id)
    if missing_order or missing_entries:
        raise ValueError(
            "INDEX_ORDER mismatch. In index but not ordered: %r. "
            "Ordered but no entry: %r" % (missing_order, missing_entries)
        )
    ordered_index_entries = [index_by_id[i] for i in full_order]

    # sanity-check the no-3-consecutive-category constraint on the FINAL order
    cats = [e["category"] for e in ordered_index_entries]
    for i in range(len(cats) - 2):
        if cats[i] == cats[i + 1] == cats[i + 2]:
            raise ValueError(
                "3 consecutive books share category %r starting at index %d (ids: %r)"
                % (cats[i], i, [ordered_index_entries[j]["id"] for j in range(i, i + 3)])
            )

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

    low_threshold_ids = {
        "communist-manifesto": 5000, "tao-te-ching": 4000, "common-sense": 4000,
        "right-to-ignore-the-state": 5000, "crito": 8000,
        "civil-disobedience": 8000,  # esai pendek Thoreau (~9.4rb kata), sengaja disertakan
    }
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
