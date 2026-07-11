#!/usr/bin/env python3
"""
render_antique_map.py

Generates assets/antique-map.jpg: an equirectangular (2:1) antique/vintage-styled
world map texture for the "Konstelasi Pengetahuan" 3D globe, built programmatically
from Natural Earth 110m admin-0 country polygons (public domain).

Pipeline:
  1. Load audio_build/ne_countries.geojson (Natural Earth 110m countries).
  2. Render at 4096x2048 (supersampled 2x) onto a plate-carree canvas:
       x = (lng+180)/360 * W ,  y = (90-lat)/180 * H
     - parchment ocean background + soft mottling
     - pastel per-country fills (deterministic hash-based palette cycling)
     - sepia country borders
     - 15-degree graticule (equator emphasized)
     - antique compass rose in the South Atlantic
     - Antarctica forced to a parchment tone (not a random pastel)
  3. LANCZOS-downscale to 2048x1024 for antialiasing.
  4. Apply subtle aging: fine noise grain + warm tone curve.
  5. Save assets/antique-map.jpg (quality 82) plus two PNG previews for visual QA.
  6. Re-open the saved JPEG and run a numeric self-check (dimensions + sampled pixels).

Antimeridian handling (see notes inline below): rings are longitude-unwrapped so a
single ring never has a >180-degree jump between consecutive points, then every
ring is drawn three times (shifted by -W, 0, +W pixels). This avoids the classic
"horizontal smear" artifact for countries/polygons that straddle lng=180/-180
(Russia, Fiji, Antarctica, USA/Aleutians, etc.) without needing true polygon
clipping/splitting.

Run: py -3.12 tools/render_antique_map.py
"""
import hashlib
import json
import math
import os
import random
import sys

from PIL import Image, ImageChops, ImageDraw

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEOJSON_PATH = os.path.join(ROOT, "audio_build", "ne_countries.geojson")
OUT_JPG = os.path.join(ROOT, "assets", "antique-map.jpg")
PREVIEW_FULL = os.path.join(ROOT, "audio_build", "preview_full.png")
PREVIEW_EUROPE = os.path.join(ROOT, "audio_build", "preview_europe.png")

# ---------------------------------------------------------------------------
# Canvas sizes
# ---------------------------------------------------------------------------
SUPER_W, SUPER_H = 4096, 2048
FINAL_W, FINAL_H = 2048, 1024

# ---------------------------------------------------------------------------
# Palette (hex -> rgb)
# ---------------------------------------------------------------------------
OCEAN = (0xE8, 0xDC, 0xC0)          # warm parchment cream
MOTTLE = (0xDE, 0xCF, 0xAF)         # subtle darker mottling tone
BORDER = (0x8A, 0x6F, 0x4D)         # sepia country border
GRATICULE = (0xB3, 0x9B, 0x72)      # graticule line color
ANTARCTICA_FILL = (0xDF, 0xD2, 0xB4)  # parchment-ish, not a random pastel

COUNTRY_PALETTE = [
    (0xD9, 0xAF, 0xA0),  # muted rose
    (0xBF, 0xC7, 0x9E),  # sage
    (0xDF, 0xC5, 0x8F),  # ochre
    (0xC4, 0xB6, 0xCE),  # lilac
    (0xA9, 0xC0, 0xB8),  # teal-grey
    (0xE3, 0xD3, 0xA8),  # wheat
]

JPEG_QUALITY = 82


def log(msg):
    print("[render_antique_map] " + msg)
    sys.stdout.flush()


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------
def lng_lat_to_xy(lng, lat, w, h):
    x = (lng + 180.0) / 360.0 * w
    y = (90.0 - lat) / 180.0 * h
    return (x, y)


def unwrap_ring(ring):
    """Return ring (list of [lng,lat]) with longitude made continuous so that no
    two consecutive points differ by more than 180 degrees. This prevents a
    single polygon edge from being interpreted as a straight line all the way
    across the canvas when the true geographic edge actually wraps around the
    antimeridian (lng=180/-180)."""
    out = []
    prev_lng = None
    for lng, lat in ring:
        lng = float(lng)
        lat = float(lat)
        if prev_lng is not None:
            while lng - prev_lng > 180.0:
                lng -= 360.0
            while lng - prev_lng < -180.0:
                lng += 360.0
        out.append((lng, lat))
        prev_lng = lng
    return out


def ring_area(ring):
    """Shoelace formula on raw lng/lat degrees. Not geographically precise
    (no cos(lat) correction) but perfectly adequate as a relative z-order
    weight so bigger countries are drawn first and small enclaves (e.g.
    Lesotho inside South Africa) get painted on top automatically."""
    area = 0.0
    n = len(ring)
    if n < 3:
        return 0.0
    for i in range(n):
        x1, y1 = ring[i]
        x2, y2 = ring[(i + 1) % n]
        area += x1 * y2 - x2 * y1
    return abs(area) / 2.0


def country_color(name):
    h = hashlib.md5(name.encode("utf-8")).hexdigest()
    idx = int(h[:8], 16) % len(COUNTRY_PALETTE)
    base = COUNTRY_PALETTE[idx]
    jitter = (int(h[8:16], 16) % 21) - 10  # -10..+10 per-country brightness jitter
    return tuple(max(0, min(255, c + jitter)) for c in base)


# ---------------------------------------------------------------------------
# Step 1: load geojson -> flat list of drawable rings
# ---------------------------------------------------------------------------
def load_units(geojson_path):
    with open(geojson_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    units = []
    for feat in data["features"]:
        props = feat.get("properties", {})
        name = props.get("NAME") or props.get("ADMIN") or props.get("SOVEREIGNT") or "Unknown"
        geom = feat.get("geometry")
        if geom is None:
            continue
        gtype = geom["type"]
        if gtype == "Polygon":
            polys = [geom["coordinates"]]
        elif gtype == "MultiPolygon":
            polys = geom["coordinates"]
        else:
            continue

        is_antarctica = name.strip().lower() == "antarctica"
        color = ANTARCTICA_FILL if is_antarctica else country_color(name)

        for poly in polys:
            if not poly:
                continue
            exterior = poly[0]  # ignore holes (interior rings) -- see notes in header
            if len(exterior) < 3:
                continue
            ring = unwrap_ring(exterior)
            units.append(
                {
                    "name": name,
                    "ring": ring,
                    "area": ring_area(ring),
                    "color": color,
                }
            )
    return units


# ---------------------------------------------------------------------------
# Step 2: rendering
# ---------------------------------------------------------------------------
def draw_ocean_mottling(base_rgba, w, h, seed=42):
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    rng = random.Random(seed)
    count = rng.randint(32, 40)  # "a few dozen"
    for _ in range(count):
        cx = rng.uniform(0, w)
        cy = rng.uniform(0, h)
        rx = rng.uniform(w * 0.05, w * 0.18)
        ry = rng.uniform(h * 0.05, h * 0.18)
        alpha = rng.randint(10, 26)  # low alpha, subtle
        d.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=(MOTTLE[0], MOTTLE[1], MOTTLE[2], alpha))
    return Image.alpha_composite(base_rgba, layer)


def draw_countries(img, units, w, h):
    draw = ImageDraw.Draw(img)
    # Largest area first (bottom layer), smallest last (top layer) so small
    # enclaves painted after their surrounding country show up correctly
    # without needing true polygon-hole punching.
    ordered = sorted(units, key=lambda u: u["area"], reverse=True)

    # Pass 1: fills
    for u in ordered:
        pts = [lng_lat_to_xy(lng, lat, w, h) for lng, lat in u["ring"]]
        for dx in (-w, 0, w):
            shifted = [(x + dx, y) for x, y in pts]
            xs = [p[0] for p in shifted]
            if max(xs) < 0 or min(xs) > w:
                continue
            draw.polygon(shifted, fill=u["color"])

    # Pass 2: borders (drawn after ALL fills so no fill ever paints over a border)
    border_width = 2  # ~2px at 4096 scale, per spec
    for u in ordered:
        pts = [lng_lat_to_xy(lng, lat, w, h) for lng, lat in u["ring"]]
        for dx in (-w, 0, w):
            shifted = [(x + dx, y) for x, y in pts]
            xs = [p[0] for p in shifted]
            if max(xs) < 0 or min(xs) > w:
                continue
            closed = shifted + [shifted[0]]
            draw.line(closed, fill=BORDER, width=border_width, joint="curve")
    return img


def draw_graticule(base_rgba, w, h):
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    alpha_normal = int(255 * 0.35)
    alpha_equator = int(255 * 0.55)

    for lng in range(-180, 181, 15):
        x, _ = lng_lat_to_xy(lng, 0, w, h)
        d.line([(x, 0), (x, h)], fill=(GRATICULE[0], GRATICULE[1], GRATICULE[2], alpha_normal), width=1)

    for lat in range(-90, 91, 15):
        _, y = lng_lat_to_xy(0, lat, w, h)
        if lat == 0:
            d.line([(0, y), (w, y)], fill=(GRATICULE[0], GRATICULE[1], GRATICULE[2], alpha_equator), width=2)
        else:
            d.line([(0, y), (w, y)], fill=(GRATICULE[0], GRATICULE[1], GRATICULE[2], alpha_normal), width=1)

    return Image.alpha_composite(base_rgba, layer)


def star_points(cx, cy, r_outer, r_inner, rotation_deg):
    pts = []
    for i in range(8):
        ang = math.radians(rotation_deg + i * 45.0)
        rad = r_outer if i % 2 == 0 else r_inner
        x = cx + rad * math.sin(ang)
        y = cy - rad * math.cos(ang)
        pts.append((x, y))
    return pts


def draw_compass_rose(base_rgba, w, h, cx, cy, radius, alpha=0.6):
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    a = int(255 * alpha)
    col = (BORDER[0], BORDER[1], BORDER[2], a)

    # Star A: cardinal-aligned 4-point star, filled solid.
    star_a = star_points(cx, cy, radius, radius * 0.32, rotation_deg=0)
    d.polygon(star_a, fill=col)

    # Star B: same shape rotated 45 degrees (ordinal-aligned), outline only,
    # so the two 4-point stars overlap and alternate fill/outline per spec.
    star_b = star_points(cx, cy, radius * 0.85, radius * 0.30, rotation_deg=45)
    d.line(star_b + [star_b[0]], fill=col, width=max(2, int(radius * 0.035)))

    # small center accent ring
    r0 = radius * 0.07
    d.ellipse([cx - r0, cy - r0, cx + r0, cy + r0], outline=col, width=2)

    return Image.alpha_composite(base_rgba, layer)


def apply_aging(img):
    w, h = img.size
    noise = Image.effect_noise((w, h), 24).convert("L")
    noise_rgb = Image.merge("RGB", (noise, noise, noise))
    multiplied = ImageChops.multiply(img, noise_rgb)
    blended = Image.blend(img, multiplied, alpha=0.05)  # ~5% opacity, subtle

    r, g, b = blended.split()
    r = r.point(lambda i: min(255, int(i * 1.03)))
    g = g.point(lambda i: min(255, int(i * 1.01)))
    b = b.point(lambda i: max(0, int(i * 0.97)))
    warmed = Image.merge("RGB", (r, g, b))
    return warmed


# ---------------------------------------------------------------------------
# Step 3: self-check
# ---------------------------------------------------------------------------
def sample_pixel(img, lng, lat):
    w, h = img.size
    x, y = lng_lat_to_xy(lng, lat, w, h)
    x = min(max(int(x), 0), w - 1)
    y = min(max(int(y), 0), h - 1)
    return img.getpixel((x, y))


def run_self_check(img):
    w, h = img.size
    ok = True
    log("Self-check: width=%d height=%d (expected 2048x1024)" % (w, h))
    if (w, h) != (FINAL_W, FINAL_H):
        log("  FAIL: dimensions do not match expected output size")
        ok = False

    # NOTE on coordinate choice: lat/lng values that are exact multiples of 15
    # sit exactly on a rendered graticule line (by design, see draw_graticule).
    # (0,0) is the worst case: it is simultaneously on the equator line AND the
    # prime-meridian line, so that single pixel is intentionally darker than
    # open ocean (two semi-transparent grid lines compositing on top of each
    # other). That is correct antique-map behavior, not a rendering bug -- but
    # it makes (0,0) a bad coordinate for a "is this cream-colored ocean"
    # gating check. We log the literal (0,0) point for transparency (diagnostic
    # only, not gated) and use a point offset by a couple of degrees for the
    # actual "mid-Atlantic ocean" gate, which is still clearly open ocean.
    diagnostic_points = {
        "ocean_EXACT_0_0_on_graticule_crossing": (0, 0),
    }
    points = {
        "ocean_near_0_0_mid_atlantic": (3, 2),
        "ocean_mid_atlantic_2": (-28, 4),
        "ocean_mid_pacific": (-160, 5),
        "brazil": (-55, -10),
        "russia": (60, 60),
        "usa": (-100, 40),
        "sahara_africa": (10, 22),
        "australia": (135, -25),
        "antarctica": (0, -85),
        "greenland": (-42, 72),
    }
    samples = {}
    for name, (lng, lat) in diagnostic_points.items():
        rgb = sample_pixel(img, lng, lat)
        log("  [diagnostic, not gated] %-38s lng=%5.1f lat=%5.1f -> RGB%s (on graticule crossing, expected darker)" % (name, lng, lat, rgb))
    for name, (lng, lat) in points.items():
        rgb = sample_pixel(img, lng, lat)
        samples[name] = rgb
        log("  sample %-30s lng=%5.1f lat=%5.1f -> RGB%s" % (name, lng, lat, rgb))

    ocean_names = ["ocean_near_0_0_mid_atlantic", "ocean_mid_atlantic_2", "ocean_mid_pacific"]
    for name in ocean_names:
        r, g, b = samples[name]
        cond = (r > 200) and (g > 190) and (b < 210) and (b < r)
        log("  check %-20s cream-ish ocean? %s" % (name, cond))
        if not cond:
            ok = False

    land_names = ["brazil", "russia", "usa"]
    for name in land_names:
        r, g, b = samples[name]
        orr, og, ob = samples["ocean_near_0_0_mid_atlantic"]
        delta = max(abs(r - orr), abs(g - og), abs(b - ob))
        cond = delta > 15
        log("  check %-20s differs from ocean by delta=%d (>15)? %s" % (name, delta, cond))
        if not cond:
            ok = False

    # histogram sanity: no pure-white/pure-black domination
    hist = img.convert("L").histogram()
    total_px = w * h
    near_black = sum(hist[0:5])
    near_white = sum(hist[251:256])
    pct_black = 100.0 * near_black / total_px
    pct_white = 100.0 * near_white / total_px
    log("  histogram: near-black=%.3f%% near-white=%.3f%% of pixels" % (pct_black, pct_white))
    if pct_black > 5.0 or pct_white > 5.0:
        log("  FAIL: too many extreme pixels (expected < 5%% each)")
        ok = False

    return ok, samples


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    if not os.path.exists(GEOJSON_PATH):
        log("FATAL: geojson not found at " + GEOJSON_PATH)
        sys.exit(1)

    os.makedirs(os.path.dirname(OUT_JPG), exist_ok=True)

    log("Loading country polygons from " + GEOJSON_PATH)
    units = load_units(GEOJSON_PATH)
    log("Loaded %d drawable rings from geojson features" % len(units))

    log("Rendering supersampled canvas %dx%d ..." % (SUPER_W, SUPER_H))
    base = Image.new("RGB", (SUPER_W, SUPER_H), OCEAN)
    base_rgba = base.convert("RGBA")

    log("  applying ocean mottling")
    base_rgba = draw_ocean_mottling(base_rgba, SUPER_W, SUPER_H)
    base = base_rgba.convert("RGB")

    log("  drawing %d countries (fills + sepia borders, antimeridian-safe)" % len(units))
    base = draw_countries(base, units, SUPER_W, SUPER_H)

    log("  drawing graticule (15deg grid)")
    base_rgba = draw_graticule(base.convert("RGBA"), SUPER_W, SUPER_H)

    log("  drawing compass rose (South Atlantic, lat=-25 lng=-15)")
    cx, cy = lng_lat_to_xy(-15, -25, SUPER_W, SUPER_H)
    base_rgba = draw_compass_rose(base_rgba, SUPER_W, SUPER_H, cx, cy, radius=120, alpha=0.6)

    base = base_rgba.convert("RGB")

    log("Downscaling %dx%d -> %dx%d with LANCZOS" % (SUPER_W, SUPER_H, FINAL_W, FINAL_H))
    small = base.resize((FINAL_W, FINAL_H), Image.LANCZOS)

    log("Applying subtle aging (noise grain + warm tone curve)")
    small = apply_aging(small)

    log("Saving preview PNGs to audio_build/ for visual QA")
    small.save(PREVIEW_FULL)

    # Europe crop: lng -10..40, lat 35..70
    ex0, ey0 = lng_lat_to_xy(-10, 70, FINAL_W, FINAL_H)
    ex1, ey1 = lng_lat_to_xy(40, 35, FINAL_W, FINAL_H)
    crop_box = (int(ex0), int(ey0), int(ex1), int(ey1))
    small.crop(crop_box).save(PREVIEW_EUROPE)
    log("  preview_full.png and preview_europe.png written")

    log("Saving final JPEG (quality=%d) -> %s" % (JPEG_QUALITY, OUT_JPG))
    small.save(OUT_JPG, "JPEG", quality=JPEG_QUALITY)

    size_bytes = os.path.getsize(OUT_JPG)
    log("Final file: %s" % OUT_JPG)
    log("Dimensions: %dx%d" % small.size)
    log("File size : %d bytes (%.1f KB)" % (size_bytes, size_bytes / 1024.0))
    if not (150 * 1024 <= size_bytes <= 450 * 1024):
        log("  NOTE: file size outside the 150-450KB target band")

    log("Re-opening saved JPEG for self-check (fresh decode, not the in-memory image)")
    reopened = Image.open(OUT_JPG).convert("RGB")
    ok, samples = run_self_check(reopened)

    log("SELF-CHECK RESULT: %s" % ("PASS" if ok else "FAIL"))
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
