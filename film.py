"""world.execute(me); - dark yandere film (v3, progressive corruption)

Original renderer. The whale girl is a digital life form living inside a
data-visualisation mindscape. The film follows the song's five-act arc:

    love offering (blue, ordered) -> possessiveness (purple) ->
    abandonment (red seeping in) -> blackened execution (red, language
    rampage) -> self destruction (dark red -> black silence).

Every frame is a pure function of song time. A global corruption value c(t)
drives colour, mosaic glitches, text rampage and post-processing so the
yandere state changes gradually instead of being dark from the first frame.

Word timings: data/timeline.json (derived from MisakaZentai/world-execute-me-dsh-pv, MIT).
Character art: dsh-deep-whale / dsh-whale-galgame, CC BY-NC-SA 4.0 (see NOTICE.md).
"""
from __future__ import annotations

import bisect
import json
import math
import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parent
W, H, FPS = 1280, 720, 24
END = 211.9
CHIME_T = 207.873
MAIN_Y0, MAIN_Y1 = 54, 612
REDLINE_AT = 110.41          # subtitle underline flips blue -> red here

# palette (dark digital life)
VOID = (5, 6, 10)
ABYSS = (10, 16, 31)
DEEP = (7, 11, 20)
INKBLUE = (22, 48, 94)
DSBLUE = (77, 107, 254)
PURPLE = (109, 63, 192)
RED = (196, 30, 58)
DEEPRED = (122, 18, 38)
BONE = (232, 230, 223)
ASH = (138, 147, 168)
GRID = (30, 44, 80)

FONT_PATHS = {
    "mono": "C:/Windows/Fonts/consola.ttf",
    "bold": "C:/Windows/Fonts/consolab.ttf",
    "cjk": "C:/Windows/Fonts/msyh.ttc",
    "cjkb": "C:/Windows/Fonts/msyhbd.ttc",
}
_fonts: dict = {}


def font(size: int, kind: str = "mono") -> ImageFont.FreeTypeFont:
    key = (size, kind)
    if key not in _fonts:
        _fonts[key] = ImageFont.truetype(FONT_PATHS[kind], size)
    return _fonts[key]


_timeline = json.loads((ROOT / "data" / "timeline.json").read_text("utf8"))
LINES = {line["id"]: line for line in _timeline["lines"]}
LINES_SORTED = sorted(LINES.values(), key=lambda line: line["start"])
ZH = json.loads((ROOT / "data" / "zh.json").read_text("utf8"))


# ---------------------------------------------------------------- easing
def clamp01(x: float) -> float:
    return 0.0 if x < 0 else (1.0 if x > 1 else x)


def lerp(a, b, u):
    return a + (b - a) * u


def mixc(ca, cb, u):
    return tuple(int(round(lerp(ca[i], cb[i], u))) for i in range(3))


def smooth(u):
    u = clamp01(u)
    return u * u * (3 - 2 * u)


def ease_out(u):
    u = clamp01(u)
    return 1 - (1 - u) ** 3


def back_out(u):
    u = clamp01(u)
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (u - 1) ** 3 + c1 * (u - 1) ** 2


def prog(t, a, b):
    return clamp01((t - a) / max(b - a, 1e-6))


def span(t, a, b):
    return smooth(prog(t, a, b))


def span_out(t, a, b):
    return ease_out(prog(t, a, b))


def pulse(t, at, half=0.12):
    return math.exp(-(t - at) / half) if t >= at else 0.0


def beat_at(t, i=0):
    """Nearest 0.465s beat grid to t, shifted i beats."""
    return 0.23 + 0.465 * round((t - 0.23) / 0.465) + i * 0.465


# ---------------------------------------------------------------- corruption
_CORR = [(0.0, 0.0), (44.0, 0.08), (59.0, 0.12), (110.0, 0.38), (118.0, 0.45),
         (134.0, 0.55), (148.0, 0.70), (163.0, 0.85), (177.0, 0.90), (192.0, 0.92),
         (205.4, 0.95), (211.5, 1.0)]


def corruption(t: float) -> float:
    ts = [c[0] for c in _CORR]
    k = bisect.bisect_right(ts, t) - 1
    if k < 0:
        return _CORR[0][1]
    if k >= len(_CORR) - 1:
        return _CORR[-1][1]
    return lerp(_CORR[k][1], _CORR[k + 1][1], prog(t, _CORR[k][0], _CORR[k + 1][0]))


def accent(t: float):
    """The film's single living colour: blue -> purple -> red -> deep red -> void."""
    c = corruption(t)
    if c < 0.35:
        return mixc(DSBLUE, PURPLE, c / 0.35)
    if c < 0.6:
        return mixc(PURPLE, RED, (c - 0.35) / 0.25)
    if c < 0.9:
        return mixc(RED, DEEPRED, (c - 0.6) / 0.3)
    return mixc(DEEPRED, (18, 5, 12), clamp01((c - 0.9) / 0.1))


def accent_soft(t: float):
    c = accent(t)
    return mixc(c, VOID, 0.35)


# ---------------------------------------------------------------- drawing
def _reveal_points(points, reveal):
    if reveal >= 1:
        return points
    reveal = clamp01(reveal)
    total = 0.0
    for a, b in zip(points, points[1:]):
        total += math.hypot(b[0] - a[0], b[1] - a[1])
    if total <= 0:
        return points
    keep, acc = [points[0]], 0.0
    target = total * reveal
    for a, b in zip(points, points[1:]):
        seg = math.hypot(b[0] - a[0], b[1] - a[1])
        if acc + seg >= target:
            u = (target - acc) / max(seg, 1e-9)
            keep.append((lerp(a[0], b[0], u), lerp(a[1], b[1], u)))
            break
        acc += seg
        keep.append(b)
    return keep


def line(d, p0, p1, fill=BONE, w=2, dash=None, reveal=1.0):
    if dash:
        x0, y0, x1, y1 = *p0, *p1
        total = math.hypot(x1 - x0, y1 - y0)
        n = max(1, int(total / (dash[0] + dash[1])))
        t = total * reveal
        for i in range(n + 1):
            s0 = i * (dash[0] + dash[1])
            s1 = min(s0 + dash[0], t)
            if s1 <= s0:
                continue
            u0, u1 = s0 / total, s1 / total
            d.line([(lerp(x0, x1, u0), lerp(y0, y1, u0)), (lerp(x0, x1, u1), lerp(y0, y1, u1))], fill=fill, width=w)
        return
    pts = _reveal_points([p0, p1], reveal)
    if len(pts) > 1:
        d.line(pts, fill=fill, width=w)


def poly(d, points, fill=BONE, w=2, reveal=1.0):
    d.line(_reveal_points(points, reveal), fill=fill, width=w)


def arc_points(c, r, a0, a1, n=48):
    pts = []
    for i in range(n + 1):
        a = math.radians(lerp(a0, a1, i / n))
        pts.append((c[0] + r * math.cos(a), c[1] + r * math.sin(a)))
    return pts


def circle(d, c, r, outline=BONE, w=2, a0=0, a1=360, reveal=1.0):
    d.line(_reveal_points(arc_points(c, r, a0, a1), reveal), fill=outline, width=w)


def rr(d, box, radius=10, fill=None, outline=None, w=2):
    d.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=w)


def text(img, xy, s, size=20, kind="mono", fill=BONE, anchor="la", alpha=255, spacing=0):
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    ld.text(xy, s, font=font(size, kind), fill=fill + (alpha,), anchor=anchor, spacing=spacing)
    if img.mode == "RGBA":
        img.alpha_composite(layer)
    else:
        img.paste(layer, (0, 0), layer)


def arrow(d, p0, p1, fill=BONE, w=2, head=8):
    line(d, p0, p1, fill, w)
    a = math.atan2(p1[1] - p0[1], p1[0] - p0[0])
    for s in (-1, 1):
        hx = p1[0] - head * math.cos(a - s * 0.5)
        hy = p1[1] - head * math.sin(a - s * 0.5)
        d.line([p1, (hx, hy)], fill=fill, width=w)


def heart(d, cx, cy, s, fill=RED, outline=None, w=2, reveal=1.0):
    pts = []
    for i in range(33):
        a = 2 * math.pi * i / 32
        x = 16 * math.sin(a) ** 3
        y = 13 * math.cos(a) - 5 * math.cos(2 * a) - 2 * math.cos(3 * a) - math.cos(4 * a)
        pts.append((cx + x * s / 17, cy - y * s / 17))
    if fill is None:
        d.line(_reveal_points(pts, reveal), fill=outline or RED, width=w)
    else:
        d.polygon(pts, fill=fill)


def sparkle(img, x, y, s, u, fill=DSBLUE):
    if u <= 0:
        return
    u = smooth(clamp01(u))
    d = ImageDraw.Draw(img)
    r = s * (0.4 + 0.6 * u)
    d.line([(x - r, y), (x + r, y)], fill=fill, width=2)
    d.line([(x, y - r), (x, y + r)], fill=fill, width=2)


def note(img, x, y, s, u, fill=DSBLUE, alpha=255):
    if u <= 0:
        return
    d = ImageDraw.Draw(img)
    d.ellipse([x - 4 * s, y - 3 * s, x + 4 * s, y + 3 * s], fill=fill + (alpha,))
    d.line([(x + 3 * s, y - 3 * s), (x + 3 * s, y - 14 * s), (x + 9 * s, y - 11 * s)], fill=fill + (alpha,), width=2)


def wob(p0, p1, n=18, seed=0, amp=1.2):
    rnd = random.Random(seed)
    return [(lerp(p0[0], p1[0], i / n) + rnd.uniform(-amp, amp),
             lerp(p0[1], p1[1], i / n) + rnd.uniform(-amp, amp)) for i in range(n + 1)]


# ---------------------------------------------------------------- background
_bg = None
_grain = None
_vign = None
_scan = None


def _prebuild():
    global _bg, _grain, _vign, _scan
    _bg = Image.new("RGB", (W, H), ABYSS)
    rnd = np.random.default_rng(7102026)
    _grain = rnd.normal(0, 1, (H, W, 1)).astype(np.float32)
    # vignette
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    rr_ = np.sqrt(((xx - W / 2) / (W * 0.62)) ** 2 + ((yy - H / 2) / (H * 0.62)) ** 2)
    _vign = np.clip(rr_ - 0.55, 0, 1).astype(np.float32)[..., None]
    # scanlines
    sl = np.ones((H, W), np.float32)
    sl[2::3, :] = 0.93
    _scan = sl[..., None]


def base(t: float) -> Image.Image:
    if _bg is None:
        _prebuild()
    img = _bg.copy()
    c = corruption(t)
    d = ImageDraw.Draw(img)
    gc = mixc(GRID, accent(t), min(0.35, 0.12 + 0.3 * c))
    # grid: clean early, broken late
    for x in range(64, W, 64):
        if c > 0.55 and (x // 64) % 3 == 0:
            continue
        for seg in range(0, 4):
            y0 = MAIN_Y0 + seg * 140
            y1 = min(y0 + 140, MAIN_Y1)
            jx = 0 if c < 0.3 else ((x * 7 + seg * 13) % 5 - 2) * c
            d.line([(x + jx, y0), (x + jx, y1)], fill=gc, width=1)
    for y in range(MAIN_Y0 + 8, MAIN_Y1, 64):
        if c > 0.55 and (y // 64) % 4 == 0:
            continue
        for seg in range(0, 4):
            x0 = seg * 320
            x1 = min(x0 + 320, W)
            jy = 0 if c < 0.3 else ((y * 11 + seg * 7) % 5 - 2) * c
            d.line([(x0, y + jy), (x1, y + jy)], fill=gc, width=1)
    # data streams
    for i in range(16):
        x = 40 + i * 80
        yoff = int((t * (34 + (i % 5) * 9) + i * 53) % (MAIN_Y1 - MAIN_Y0 - 60)) + MAIN_Y0
        for k in range(3):
            yy = yoff + k * 9
            d.rectangle([x, yy, x + 2, yy + 5], fill=ASH + (26,))
    # synapse pulses
    nodes = [(110, 130), (300, 210), (540, 150), (760, 260), (990, 160), (1160, 250)]
    for i in range(5):
        a0, b0 = nodes[i], nodes[i + 1]
        ph = 0.5 + 0.5 * math.sin(t * 2.2 + i * 1.3)
        col = mixc(mixc(DSBLUE, ASH, 0.5), accent(t), c)
        line(d, a0, b0, col, 1, dash=(6, 5))
        mid = ((a0[0] + b0[0]) / 2, (a0[1] + b0[1]) / 2 - 18)
        d.ellipse([mid[0] - 2 - 2 * ph, mid[1] - 2 - 2 * ph, mid[0] + 2 + 2 * ph, mid[1] + 2 + 2 * ph],
                  outline=col, width=1)
    # cracks
    if c > 0.12:
        rnd = random.Random(99)
        for i in range(int(c * 9)):
            x0 = rnd.uniform(0, W)
            y0 = rnd.uniform(MAIN_Y0, MAIN_Y1)
            pts = [(x0, y0)]
            for k in range(6):
                pts.append((pts[-1][0] + rnd.uniform(-46, 46), pts[-1][1] + rnd.uniform(20, 70)))
            d.line(pts, fill=accent_soft(t), width=1)
    d.rectangle([24, MAIN_Y0 - 8, W - 24, MAIN_Y1 + 8], outline=mixc(INKBLUE, VOID, 0.3), width=1)
    return img


# ---------------------------------------------------------------- character
CHAR_DIR = ROOT / "assets" / "char"
_char_cache: dict = {}
_mask_cache: dict = {}


def char_image(name: str, h: int) -> Image.Image:
    key = (name, h)
    if key not in _char_cache:
        im = Image.open(CHAR_DIR / f"{name}.png").convert("RGBA")
        w = int(im.width * h / im.height)
        im = im.resize((w, h), Image.LANCZOS)
        rgb = np.asarray(im.convert("RGB"), np.float32)
        lum = rgb.mean(2, keepdims=True)
        # dark relight: keep cold white highlights, sink shadows into abyss blue
        out = 0.62 * rgb + 0.30 * np.array(ABYSS, np.float32) + 0.08 * (lum * np.array([0.25, 0.35, 0.62], np.float32))
        rgb = np.clip(out, 0, 255).astype(np.uint8)
        im = Image.fromarray(rgb, "RGB")
        im.putalpha(_char_mask(name, h))
        _char_cache[key] = im
    return _char_cache[key]


def _char_mask(name: str, h: int) -> Image.Image:
    key = (name, h)
    if key not in _mask_cache:
        im = Image.open(CHAR_DIR / f"{name}.png").convert("RGBA")
        w = int(im.width * h / im.height)
        _mask_cache[key] = im.resize((w, h), Image.LANCZOS).getchannel("A")
    return _mask_cache[key]


def _char_outline_mask(name: str, h: int):
    key = ("outline", name, h)
    if key not in _mask_cache:
        a = _char_mask(name, h)
        dilated = a.filter(ImageFilter.MaxFilter(7))
        _mask_cache[key] = ImageChops.subtract(dilated, a)
    return _mask_cache[key]


EXPRS = [
    (0.0, "whale-shy"), (1.79, "whale-serious"), (3.86, "whale-serious"), (5.42, "whale-cheerful"),
    (10.13, "whale-starry"), (16.12, "whale-serious"), (24.5, "whale-shy"), (29.77, "whale-starry"),
    (33.45, "whale-shy"), (37.10, "whale-cheerful"), (44.41, "whale-cheerful"), (55.08, "whale-shy"),
    (59.06, "whale-cheerful"), (73.93, "whale-cheerful"), (85.13, "whale-serious"),
    (88.54, "whale-confused"), (103.52, "whale-shy"), (110.41, "whale-frightened"),
    (117.97, "whale-frightened"), (125.58, "whale-angry"), (133.45, "whale-serious"),
    (147.89, "whale-starry"), (153.43, "whale-cheerful"), (162.59, "whale-cheerful"),
    (177.44, "whale-shy"), (191.88, "whale-serious"), (205.37, "whale-starry"),
]


def expr_at(t: float) -> str:
    name = EXPRS[0][1]
    for t0, n in EXPRS:
        if t >= t0:
            name = n
    return name


def expr_pop(t: float) -> float:
    k = 1.0
    for t0, _n in EXPRS:
        if t0 > t:
            break
        k = 1.0 + 0.03 * pulse(t, t0, 0.08)
    return min(k, 1.05)


def paste_char(img, name, x, y, h, alpha=1.0, shadow=True, scale=1.0, outline_c=0.0):
    im = char_image(name, h)
    w, hh = im.size
    if scale != 1.0:
        im = im.resize((int(w * scale), int(hh * scale)), Image.LANCZOS)
        w, hh = im.size
    if shadow:
        sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
        sil = Image.new("RGBA", (w, hh), (0, 0, 0, 180))
        sil.putalpha(im.getchannel("A").point(lambda v: int(v * 0.45 * alpha)))
        sh.paste(sil, (int(x) + 14, int(y) + 18), sil)
        img.paste(sh, (0, 0), sh) if img.mode == "RGBA" else None
    if outline_c > 0.02:
        oc = accent(outline_c)
        om = _char_outline_mask(name, h).point(lambda v: int(v * (0.25 + 0.75 * corruption(outline_c)) * alpha))
        ol = Image.new("RGBA", img.size, (0, 0, 0, 0))
        sil = Image.new("RGBA", (om.size[0], om.size[1]), oc + (255,))
        sil.putalpha(om)
        ol.paste(sil, (int(x), int(y)), sil)
        img.paste(ol, (0, 0), ol) if img.mode == "RGBA" else None
    if alpha < 1:
        im.putalpha(im.getchannel("A").point(lambda v: int(v * alpha)))
    if img.mode == "RGBA":
        img.alpha_composite(im, (int(x), int(y)))
    else:
        img.paste(im, (int(x), int(y)), im)


def _place_char(img, t, h=420, x=None, y=None):
    c = corruption(t)
    if x is None:
        x = W - h * 935 / 1683 - 48
    if y is None:
        y = MAIN_Y1 - h
    if c > 0.9 and t > 191.9:
        # dissolving: alpha drops in S20-S22
        alpha = 1.0
        if t > 205.37:
            alpha = 1.0 - prog(t, 205.37, 207.9) * 0.9
        elif t > 200.0:
            alpha = 1.0 - prog(t, 200.0, 205.37) * 0.25
        paste_char(img, expr_at(t), x, y, h, alpha=alpha, scale=expr_pop(t), outline_c=t)
    else:
        paste_char(img, expr_at(t), x, y, h, scale=expr_pop(t), outline_c=t)
    return x, y, h


def _face_anchors(x, y, h):
    w = h * 935 / 1683
    return {
        "eyeL": (x + w * 0.435, y + h * 0.088),
        "eyeR": (x + w * 0.565, y + h * 0.088),
        "mouth": (x + w * 0.50, y + h * 0.145),
        "handL": (x + w * 0.22, y + h * 0.62),
        "handR": (x + w * 0.78, y + h * 0.60),
    }


def _face_fx(img, t, x, y, h):
    """Progressive glitch on the girl: spiral eyes in trance, scanline pupils,
    cracked mouth in mania, red tears."""
    c = corruption(t)
    d = ImageDraw.Draw(img)
    f = _face_anchors(x, y, h)
    if 99.26 <= t < 103.18:  # trance spirals
        u = span(t, 101.28, 102.6)
        for key in ("eyeL", "eyeR"):
            ex, ey = f[key]
            for i in range(int(1 + 5 * u)):
                a0 = i * 0.7 + (t - 101.2) * 6
                circle(d, (ex, ey), 3 + i * 3.2, accent(t), 1, a0=math.degrees(a0), a1=math.degrees(a0 + 4.4))
    if 125.58 <= t < 133.45:  # scanline pupils (judgement)
        y0 = f["eyeL"][1] - 8
        for k in range(4):
            yy = y0 + k * 5
            d.line([(x + 20, yy), (x + h * 935 / 1683 - 20, yy)], fill=accent_soft(t), width=1)
    if 147.89 <= t < 162.59:  # cracked mouth in mania
        u = clamp01((t - 148.5) / 2.0)
        mx, my = f["mouth"]
        d.line([(mx, my), (mx + 18 * u, my + 26 * u)], fill=RED, width=2)
        d.line([(mx + 18 * u, my + 26 * u), (mx + 10 * u, my + 40 * u)], fill=RED, width=2)
    if (162.59 <= t < 177.44) or (191.88 <= t < 205.37):  # red tear lines
        for key, s in (("eyeL", -1), ("eyeR", 1)):
            ex, ey = f[key]
            tr = (t * 40) % 24
            d.line([(ex + s * 7, ey + 12), (ex + s * 8, ey + 16 + tr * 0.6)], fill=RED, width=2)


# ---------------------------------------------------------------- stamps
def stamp(img, cx, cy, s, sub=None, color=None, u=1.0, rot=-8.0, scale=1.0, size=23,
          jitter=0, kind="bold"):
    u = clamp01(u)
    if u <= 0:
        return
    color = color or RED
    sc = back_out(u) * scale
    rnd = random.Random(int(cx * 3 + cy * 5 + jitter * 91))
    jx = rnd.uniform(-jitter, jitter)
    jy = rnd.uniform(-jitter, jitter)
    cx, cy = cx + jx, cy + jy
    f = font(size, kind)
    w = int(max(96 * scale, f.getlength(s) + 38 * scale))
    h = int(58 * scale)
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    st = Image.new("RGBA", (w + 40, h + 40), (0, 0, 0, 0))
    sd = ImageDraw.Draw(st)
    alpha = int(255 * min(1, u * 4))
    sd.rounded_rectangle([4, 4, w + 36, h + 36], radius=int(10 * scale),
                         outline=color + (alpha,), width=max(3, int(4 * scale)))
    sd.rounded_rectangle([10, 10, w + 30, h + 30], radius=int(7 * scale),
                         outline=color + (int(alpha * 0.85),), width=1)
    sd.text((w / 2 + 20, h / 2 + 20), s, font=f, fill=color + (alpha,), anchor="mm")
    if sub:
        sd.text((w / 2 + 20, h / 2 + 20 + size + 4), sub, font=font(max(12, size - 9), "cjk"),
                fill=color + (int(alpha * 0.9),), anchor="mm")
    st = st.rotate(rot * (1 - clamp01((u - 0.85) / 0.15) * 0.55), resample=Image.BICUBIC,
                   center=(w / 2 + 20, h / 2 + 20))
    layer.paste(st, (int(cx - w / 2 - 20), int(cy - h / 2 - 20)), st)
    if u >= 1:
        dd = ImageDraw.Draw(layer)
        for _ in range(10):
            a = rnd.uniform(0, 2 * math.pi)
            r = rnd.uniform(w / 2 - 8 * scale, w / 2 + 16 * scale)
            px, py = cx + r * math.cos(a), cy + r * math.sin(a)
            dd.ellipse([px - 2, py - 2, px + 2, py + 2], fill=color + (140,))
    img.paste(layer, (0, 0), layer) if img.mode == "RGBA" else None


# ---------------------------------------------------------------- feed
FEED = [
    (0.0, "BOOT SEQUENCE…"), (1.2, "power line: CONNECTED"),
    (3.86, "OBJECT CREATION…"), (7.38, "params: you / +inf / serve"),
    (10.13, "WORLD ONLINE"), (12.76, "simulation: RUNNING"),
    (16.12, "tracing…"), (21.0, "anomaly: 1 extra stroke"),
    (29.77, "dimensionality: 2→3"), (33.45, "orbit locked"),
    (37.10, "heart rate: 129bpm"), (44.41, "current: AC/DC"),
    (51.45, "merge protocol…"), (59.06, "checklist: 3 items"),
    (68.20, "RUN #1"), (70.12, "containment: optional"),
    (73.93, "dependency: 100%"), (85.13, "throne: occupied"),
    (88.54, "state: altered"), (99.26, "trance: entering"),
    (103.52, "lock: acquired"), (110.41, "lock: unstable"),
    (116.01, "link severed"), (117.97, "lock: lost / searching…"),
    (123.83, "fragments: erasing"), (125.58, "verdict: rejection"),
    (131.21, "clause 12: you shall not leave"), (133.45, "recovery: 99% … 1% missing"),
    (147.89, "EXECUTING…"), (161.67, "EXECUTION #13"),
    (162.59, "input: you / output: tears"), (176.5, "buffer overflow"),
    (177.44, "love := trapped"), (188.29, "you are free"),
    (191.88, "heartbeat: …"), (205.37, "final execution"),
    (207.873, "blue returned to you"), (209.0, "process terminated. love = trapped."),
]


def draw_feed(img, t):
    c = corruption(t)
    if t > 210.2:
        return
    shown = [f for f in FEED if f[0] <= t][-3:]
    y = MAIN_Y0 + 18
    col = mixc(ASH, RED, clamp01((c - 0.35) / 0.3))
    for i, (at, s) in enumerate(shown):
        alpha = 255 if i == len(shown) - 1 else int(110 + 60 * i)
        s2 = s
        if c > 0.55 and len(shown) - 1 == i:
            rnd = random.Random(int(t * 24))
            s2 = "".join(ch if rnd.random() > 0.12 * c else rnd.choice("#%&@!?") for ch in s)
        text(img, (40, y), s2, 14, "mono", col, alpha=alpha)
        if c > 0.55 and i == len(shown) - 1:
            text(img, (41, y + 1), s2, 14, "mono", RED, alpha=60)
        y += 22


# ---------------------------------------------------------------- rampage
GARBLE = "world.execute(me); Execution you love lim ∫you me strange err 0x7F ∞ ∂you 你 我 愛 �"


def rampage(img, t, level):
    level = int(level)
    if level <= 0 or t > 211.2:
        return
    rnd = random.Random(1000 + int(t * 24))
    d = ImageDraw.Draw(img)
    acc = accent(t)
    n = 4 + level * 5
    for i in range(n):
        x = rnd.uniform(-80, W - 40)
        y = rnd.uniform(MAIN_Y0, MAIN_Y1 - 30)
        size = rnd.choice([12, 14, 16, 20, 24, 30, 38, 46])
        s = rnd.choice(GARBLE.split())
        s = s if rnd.random() > 0.4 else "".join(rnd.choice("▓▒░#%&@!?") for _ in range(rnd.randint(2, 9)))
        col = rnd.choice([acc, RED, BONE, ASH, PURPLE])
        text(img, (x, y), s, size, "bold" if size > 28 else "mono", col,
             alpha=rnd.randint(70, 210))
        if rnd.random() < 0.35:
            text(img, (x + rnd.randint(-3, 3), y + rnd.randint(-3, 3)), s, size, "mono",
                 mixc(col, RED, 0.5), alpha=90)
    if level >= 8 and t < 176.5:
        for i in range(level - 6):
            yy = MAIN_Y0 + 20 + i * 26
            text(img, (W / 2, yy), " ".join(GARBLE.split()[i % 9:] + GARBLE.split()[:i % 9]),
                 24, "bold", mixc(RED, BONE, 0.3), anchor="mm", alpha=120)


def rampage_level(t):
    c = corruption(t)
    if 147.89 <= t < 162.59:
        return lerp(6, 9, prog(t, 147.89, 162.59))
    if 162.59 <= t < 176.5:
        return 10
    if 176.5 <= t < 177.44:
        return lerp(8, 1, prog(t, 176.5, 177.44))
    if 125.58 <= t < 133.45:
        return 3
    if 44.41 <= t < 58.7:
        return 1
    return 0


# ---------------------------------------------------------------- mosaic
def pixelate(img, box, block):
    x0, y0, x1, y1 = box
    x0, y0, x1, y1 = int(x0), int(y0), int(x1), int(y1)
    if x1 <= x0 or y1 <= y0:
        return
    region = img.crop((x0, y0, x1, y1))
    small = region.resize((max(1, (x1 - x0) // block), max(1, (y1 - y0) // block)), Image.BILINEAR)
    img.paste(small.resize((x1 - x0, y1 - y0), Image.NEAREST), (x0, y0))


def mosaic(img, t, char_rect=None):
    c = corruption(t)
    if c < 0.06:
        return
    # screen edges creep inward
    edge = int(8 + c * 150)
    b = max(3, int(3 + c * 7))
    if edge > 12:
        pixelate(img, (0, MAIN_Y0, edge, MAIN_Y1), b)
        pixelate(img, (W - edge, MAIN_Y0, W, MAIN_Y1), b)
        pixelate(img, (edge, MAIN_Y0, W - edge, MAIN_Y0 + edge // 2), b)
        pixelate(img, (edge, MAIN_Y1 - edge // 2, W - edge, MAIN_Y1), b)
    if char_rect:
        x, y, h = char_rect
        f = _face_anchors(x, y, h)
        if c > 0.25:
            for key in ("eyeL", "eyeR", "mouth"):
                ex, ey = f[key]
                r = int(4 + c * 10)
                pixelate(img, (ex - r, ey - r, ex + r, ey + r), max(2, int(c * 5)))
        if c > 0.38:
            for key in ("handL", "handR"):
                hx, hy = f[key]
                r = int(6 + c * 12)
                pixelate(img, (hx - r, hy - r, hx + r, hy + r), max(2, int(c * 5)))
        if c > 0.9 and t > 191.9:
            # body dissolving into data blocks
            u = prog(t, 192.0, 207.9)
            rnd = random.Random(int(t * 8))
            for _ in range(int(u * 42)):
                px = x + rnd.uniform(0, h * 935 / 1683)
                py = y + rnd.uniform(0, h)
                sz = rnd.uniform(4, 12)
                pixelate(img, (px - sz, py - sz, px + sz, py + sz), max(2, int(3 + u * 4)))


# ---------------------------------------------------------------- lyric band
def active_line(t):
    k = bisect.bisect_right([line["start"] for line in LINES_SORTED], t) - 1
    if k < 0:
        return None
    line_ = LINES_SORTED[k]
    if line_["start"] <= t < line_["end"] + 0.6:
        return line_
    return None


def draw_band(img, t):
    if t >= 207.9 or active_line(t) is None:
        return
    c = corruption(t)
    d = ImageDraw.Draw(img)
    band_top = 612
    jit = 0
    if 147.89 <= t < 177.44:
        jit = (int(t * 24) % 3) - 1
    d.rectangle([0, band_top, W, H], fill=(6, 8, 14))
    d.line([(36, band_top + jit), (W - 36, band_top + jit)], fill=mixc(INKBLUE, accent(t), 0.35 * c), width=1)
    line_ = active_line(t)
    if line_ is None:
        return
    x = 56
    mono = font(21, "bold")
    underline = DSBLUE if t < REDLINE_AT else RED
    for word in line_.get("words", []):
        if t < word["start"]:
            break
        text(img, (x, band_top + 22 + jit), word["text"], 21, "bold", BONE)
        tw = mono.getlength(word["text"]) + mono.getlength(" ")
        if word["start"] <= t < word["end"]:
            u = prog(t, word["start"], word["end"])
            x1 = max(x + 2, x + tw * u - 6)
            d.rectangle([x, band_top + 50 + jit, x1, band_top + 54 + jit], fill=underline)
        x += tw
    zh = ZH.get(str(line_["id"]))
    if zh and t >= line_["start"] + 0.05:
        text(img, (56, band_top + 62 + jit), zh, 17, "cjk",
             mixc(ASH, BONE, 0.2), alpha=220)
    text(img, (W - 48, band_top + 26 + jit), f"L{line_['id']:03d}", 13, "mono", ASH, anchor="ra")


def draw_header(img, t):
    c = corruption(t)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 50], fill=(5, 7, 13))
    d.line([(0, 50), (0, 0)], fill=accent(t), width=3)
    text(img, (24, 12), "world.execute(me);", 17, "bold", BONE)
    text(img, (248, 16), "digital-life mindscape · v3", 13, "mono", ASH)
    mm, ss = int(t // 60), int(t % 60)
    text(img, (W - 40, 12), f"{mm}:{ss:02d}", 14, "mono", BONE, anchor="ra")
    text(img, (W - 40, 30), f"corruption {c * 100:02.0f}%", 12, "mono", accent(t), anchor="ra")
    d.rectangle([0, 48, int(W * clamp01(t / END)), 50], fill=accent(t))


# ---------------------------------------------------------------- scenes
def _scene_layer():
    return Image.new("RGBA", (W, H), (0, 0, 0, 0))


def s01(img, t):
    """S01 通电 0-3.86 (L0-L1) blue, ordered."""
    d = ImageDraw.Draw(img)
    cx, cy = 520, 320
    u0 = span_out(t, 0.06, 1.0)
    rr(d, [cx - 130, cy - 44, cx + 130, cy + 44], 12, fill=(8, 12, 24), outline=DSBLUE, w=2)
    text(img, (cx, cy - 28), "MAIN POWER", 15, "bold", DSBLUE, anchor="mm")
    lever = -38 + 76 * u0
    a = math.radians(lever)
    line(d, (cx, cy), (cx + 84 * math.cos(a), cy + 84 * math.sin(a)), BONE, 5)
    d.ellipse([cx - 9, cy - 9, cx + 9, cy + 9], fill=DSBLUE)
    if u0 >= 1:
        sparkle(img, cx + 110, cy - 28, 8, pulse(t, 1.05, 0.25), DSBLUE)
    # current travels along synapses to her silhouette
    line(d, (cx + 130, cy), (790, cy), DSBLUE, 3, reveal=span(t, 0.2, 1.3))
    for k in range(3):
        yy = cy + 10 + k * 9
        line(d, (620 + k * 50, cy), (620 + k * 50 + 12, yy), DSBLUE, 2)
        line(d, (620 + k * 50 + 12, yy), (620 + k * 50 + 24, yy - 9), DSBLUE, 2)
    _place_char(img, t)
    text(img, (cx, 430), "switch on the power line", 15, "mono", ASH, anchor="mm")


def s02(img, t):
    """S02 造物 3.86-10.13 (L2-L5): code fragments form her skeleton, parameter form."""
    d = ImageDraw.Draw(img)
    frags = ["if you:", "def love():", "class Her:", "while(you):", "return me"]
    for i, s in enumerate(frags):
        at = 3.86 + i * 0.3
        u = back_out(prog(t, at, at + 0.28))
        if u <= 0:
            continue
        x0 = 70 + i * 78
        y0 = 260 - 150 * u
        rr(d, [x0, y0, x0 + 66, y0 + 30], 5, fill=(9, 14, 28), outline=DSBLUE, w=1)
        text(img, (x0 + 33, y0 + 8), s, 10, "mono", DSBLUE, anchor="mm")
    # parameter form
    f = span(t, 7.38, 9.93)
    if f > 0:
        rr(d, [480, 110, 920, 480], 10, fill=(8, 12, 24), outline=INKBLUE, w=2)
        text(img, (500, 130), "DATA PARAMETERS", 15, "bold", DSBLUE)
        rows = [("NAME", "you", 7.38), ("AFFECTION", "+∞", 7.9), ("SEED", "her heart", 8.4), ("MODE", "serve", 8.9)]
        y = 168
        for i, (key, val, at) in enumerate(rows):
            rr(d, [500, y, 900, y + 54], 6, fill=(10, 16, 31), outline=GRID, w=1)
            text(img, (518, y + 10), key, 15, "bold", BONE)
            if t >= at:
                text(img, (680, y + 10), val, 18, "mono", DSBLUE)
            y += 68
        bar = prog(t, 7.9, 10.13)
        rr(d, [500, 446, 900, 462], 4, fill=DEEP, outline=GRID, w=1)
        d.rectangle([504, 450, 504 + 392 * bar, 458], fill=DSBLUE)
    _place_char(img, t)


def s03(img, t):
    """S03 世界 10.13-16.12 (L6-L7): star map world, synapse lines."""
    d = ImageDraw.Draw(img)
    cx, cy = 430, 320
    u = span(t, 10.13, 12.2)
    stars = [(90, 120), (220, 90), (360, 140), (180, 210), (70, 280), (250, 360), (110, 440), (300, 470)]
    for i, (sx, sy) in enumerate(stars):
        if t >= 10.13 + i * 0.08:
            d.ellipse([sx - 3, sy - 3, sx + 3, sy + 3], fill=BONE)
            line(d, (sx, sy), (cx, cy), INKBLUE, 1)
    circle(d, (cx, cy), 92 * u, BONE, 3, reveal=u)
    orbit = span(t, 12.76, 14.5)
    if orbit > 0:
        circle(d, (cx, cy), 140, DSBLUE, 2, a0=0, a1=360 * orbit)
        a = 2 * math.pi * ease_out(prog(t, 12.76, 14.82)) - math.pi / 2
        mx, my = cx + 140 * math.cos(a), cy + 140 * math.sin(a)
        d.ellipse([mx - 7, my - 7, mx + 7, my + 7], fill=BONE)
    _place_char(img, t)
    text(img, (cx, 520), "our new world", 15, "bold", ASH, anchor="mm")


def s04(img, t):
    """S04 凝视 16.12-29.77 interlude: she traces 'you'; one extra stroke."""
    d = ImageDraw.Draw(img)
    # scanline sweeping over her
    yy = MAIN_Y0 + ((t * 42) % (MAIN_Y1 - MAIN_Y0))
    d.line([(0, yy), (W, yy)], fill=DSBLUE, width=1)
    # silhouette of "you" being traced
    u = prog(t, 16.2, 25.0)
    cx, cy = 300, 310
    head = arc_points((cx, cy - 60), 42, 0, 360)
    d.line(_reveal_points(head, clamp01(u * 1.2)), fill=BONE, width=2)
    d.line([(cx - 34, cy + 8), (cx + 34, cy + 8)], fill=BONE, width=2, )
    if u >= 1.0 and t > 21.0:
        # the extra stroke: one line that escapes the silhouette
        d.line([(cx + 40, cy - 30), (cx + 78, cy - 66)], fill=RED, width=2)
    _place_char(img, t)
    text(img, (cx, 500), "tracing you…", 14, "mono", ASH, anchor="mm")


def s05(img, t):
    """S05 点集 29.77-33.29 (L9-L10): points align onto data axes as her face."""
    d = ImageDraw.Draw(img)
    if t >= 29.77:
        for i in range(11):
            at = 29.77 + i * 0.05
            px = 90 + (i * 47) % 260
            py = 140 + (i * 31) % 100
            if t >= 31.29:
                px = 100 + i * 26
                py = 220 + (i % 4) * 16 - (i // 4) * 10
            d.ellipse([px - 3, py - 3, px + 3, py + 3], fill=DSBLUE if t >= 31.29 else BONE)
    if t >= 31.29:
        arrow(d, (88, 240), (390, 240), ASH, 1)
        arrow(d, (100, 320), (100, 130), ASH, 1)
        text(img, (382, 248), "you", 13, "bold", BONE)
        text(img, (108, 122), "me", 13, "bold", BONE)
    _place_char(img, t)


def s06(img, t):
    """S06 圆周 33.45-36.92 (L11-L12): orbit ring; 'you' walks the circumference."""
    d = ImageDraw.Draw(img)
    cx, cy = 430, 310
    u = prog(t, 33.45, 34.8)
    circle(d, (cx, cy), 96, DSBLUE, 2, a0=-90, a1=-90 + 360 * u)
    if t >= 34.99:
        a = -90 + 360 * prog(t, 34.99, 36.92)
        px, py = cx + 96 * math.cos(math.radians(a)), cy + 96 * math.sin(math.radians(a))
        d.ellipse([px - 5, py - 5, px + 5, py + 5], fill=BONE)
        d.line([(px, py), (px + 20, py - 12)], fill=RED, width=1)
    # first red noise pixel inside the ring (unease #2)
    if t > 35.0:
        rnd = random.Random(5)
        for _ in range(3):
            px = cx - 90 + rnd.random() * 176
            py = cy - 90 + rnd.random() * 176
            d.rectangle([px, py, px + 3, py + 3], fill=RED)
    _place_char(img, t)


def s07(img, t):
    """S07 正弦·无穷 37.10-44.22 (L13-L16): heartbeat sine, tangent gifts, infinity."""
    d = ImageDraw.Draw(img)
    if t >= 37.10:
        u = prog(t, 37.10, 38.6)
        pts = [(90 + j * 9, 250 - 44 * math.sin(j / 4.4)) for j in range(int(42 * u) + 1)]
        poly(d, pts, DSBLUE, 2)
    if t >= 38.69:
        for j in (7, 20):
            x = 90 + j * 9
            y = 250 - 44 * math.sin(j / 4.4)
            line(d, (x - 28, y - 36), (x + 28, y + 36), BONE, 1)
            d.ellipse([x - 4, y - 38, x + 4, y - 30], outline=BONE, width=1)
    if t >= 40.82:
        text(img, (620, 260), "∞", 40, "bold", DSBLUE, anchor="mm")
        circle(d, (620, 260), 70, DSBLUE, 1, a0=0, a1=360 * prog(t, 40.82, 44.0))
    _place_char(img, t)


def s08(img, t):
    """S08 电流·旅程·合一 44.41-58.70 (L17-L24): AC/DC ribbons, chromatic sight, paper plane, double helix."""
    d = ImageDraw.Draw(img)
    mode = "AC" if t < 47.6 else "DC"
    if t >= 44.41:
        text(img, (120, 130), mode, 24, "bold", accent(t))
    if mode == "AC":
        pts = [(170 + j * 5, 210 - 22 * math.sin(j / 4.0 + (t - 44.4) * 5)) for j in range(28)]
        poly(d, pts, DSBLUE, 2)
    else:
        line(d, (170, 210), (310, 210), BONE, 3)
    # chromatic dispersion while "dizzy"
    if 47.71 <= t < 49.4:
        k = int(6 * span(t, 47.71, 49.4))
        for i in range(k):
            d.line([(420 + i * 3, 150), (520 + i * 3, 320)], fill=mixc(DSBLUE, PURPLE, i / 7), width=2)
    # time axis + plane
    if t >= 51.45:
        arrow(d, (70, 420), (700, 420), ASH, 1)
        for xx, label in ((180, "BC"), (560, "AD")):
            d.line([(xx, 404), (xx, 436)], fill=INKBLUE, width=2)
            text(img, (xx, 446), label, 13, "bold", ASH, anchor="mm")
        fx = lerp(90, 660, prog(t, 51.45, 54.8))
        fy = 420 - 24 * math.sin((t - 51.45) * 9)
        d.polygon([(fx, fy), (fx - 22, fy + 10), (fx + 22, fy + 10)], outline=BONE, width=1)
    # double helix
    if t >= 55.08:
        u = prog(t, 55.08, 57.0)
        for k in range(2):
            pts = [(830 + j * 10, 180 + 120 * ((j / 30) % 1) + (-1) ** k * 34 * math.sin(j / 5 + k * math.pi)) for j in range(int(30 * u) + 1)]
            poly(d, pts, accent(t), 2)
    _place_char(img, t)


def s09(img, t):
    """S09 执行I 59.06-73.63 (L25-L32): checklist, first (blue-purple) stamp, data fence."""
    d = ImageDraw.Draw(img)
    rr(d, [90, 110, 640, 480], 10, fill=(8, 12, 24), outline=INKBLUE, w=2)
    text(img, (112, 130), "CHECKLIST", 15, "bold", ASH)
    items = [(59.06, "all the simulations"), (63.05, "only satisfaction"), (66.29, "make you happy")]
    y = 170
    for at, label in items:
        u = span(t, at, at + 0.4)
        rr(d, [112, y, 132, y + 20], 3, outline=BONE, w=2)
        if u > 0:
            line(d, (115, y + 10), (122, y + 16), accent(t), 2, reveal=clamp01(u * 2))
            line(d, (122, y + 16), (130, y + 4), accent(t), 2, reveal=clamp01(u * 2 - 1))
        text(img, (148, y - 2), label, 17, "mono", BONE if t >= at else ASH)
        y += 62
    if t >= 68.20:
        stamp(img, 470, 310, "RUN", "execution", accent(t), span(t, 68.20, 68.62), rot=-6)
    if t >= 70.12:
        u = span(t, 70.12, 71.2)
        cx, cy, r = 900, 320, 82
        circle(d, (cx, cy), r, ASH, 2)
        for a in range(-90, 270, 22):
            if a > -90 + 360 * u:
                continue
            ar = math.radians(a)
            line(d, (cx + r * math.cos(ar), cy + r * math.sin(ar) - 16),
                 (cx + r * math.cos(ar), cy + r * math.sin(ar) + 16), accent(t), 2)
    if t >= 71.59:
        text(img, (900, 440), "strange, strange simulation", 15, "mono",
             mixc(ASH, RED, 0.5), anchor="mm")
    _place_char(img, t)


def s10(img, t):
    """S10 供养 73.93-88.54 (L33-L40): data archive cards, throne, locked frame."""
    d = ImageDraw.Draw(img)
    slots = [(80, 110, "eggplant", 73.93), (80, 310, "tomato", 77.71),
             (480, 110, "tabby cat", 81.28), (480, 310, "only God", 85.13)]
    for x0, y0, kind, at in slots:
        u = span(t, at, at + 0.3)
        if u <= 0:
            continue
        rr(d, [x0, y0, x0 + 330, y0 + 150], 8, fill=(8, 12, 24), outline=INKBLUE, w=2)
        text(img, (x0 + 16, y0 + 10), kind, 12, "mono", ASH)
        c = (x0 + 95, y0 + 88)
        if kind == "eggplant":
            d.ellipse([c[0] - 30, c[1] - 40, c[0] + 30, c[1] + 26], fill=PURPLE + (150,))
            text(img, (x0 + 185, y0 + 66), "nutrients", 15, "mono", BONE)
        elif kind == "tomato":
            d.ellipse([c[0] - 26, c[1] - 26, c[0] + 26, c[1] + 26], fill=RED + (150,))
            text(img, (x0 + 185, y0 + 66), "antioxidants", 15, "mono", BONE)
        elif kind == "tabby cat":
            d.ellipse([c[0] - 24, c[1] - 24, c[0] + 24, c[1] + 24], outline=BONE, width=2)
            for s in (-1, 1):
                d.polygon([(c[0] + s * 20, c[1] - 18), (c[0] + s * 28, c[1] - 42), (c[0] + s * 36, c[1] - 16)], outline=BONE, width=1)
            text(img, (x0 + 185, y0 + 66), "purr → ECG", 15, "mono", BONE)
            pts = [(x0 + 190 + j * 5, y0 + 100 - 14 * math.sin(j / 2.2)) for j in range(24)]
            poly(d, pts, accent(t), 2)
        else:
            circle(d, (c[0], c[1] - 20), 16, accent(t), 2)
            d.ellipse([c[0] - 16, c[1] - 18, c[0] + 16, c[1] + 20], outline=BONE, width=1)
            text(img, (x0 + 185, y0 + 66), "proof of existence", 14, "mono", BONE)
            rr(d, [x0 + 185, y0 + 88, x0 + 270, y0 + 120], 4, outline=accent(t), w=2)
            text(img, (x0 + 227, y0 + 95), "you", 12, "bold", accent(t), anchor="mm")
    _place_char(img, t)


def s11(img, t):
    """S11 开关与出神 88.54-103.18 (L41-L48): logic gates, reverse clock, smoke, trance."""
    d = ImageDraw.Draw(img)
    def gate(x, y, a, b, at):
        u = span(t, at, at + 0.3)
        rr(d, [x, y, x + 110, y + 54], 8, fill=(8, 12, 24), outline=accent(t), w=2)
        text(img, (x + 10, y + 8), a, 16, "bold", BONE if t < at else ASH)
        text(img, (x + 68, y + 8), b, 16, "bold", ASH if t < at else accent(t))
        d.ellipse([x + 12 + 76 * u, y + 20, x + 36 + 76 * u, y + 44], fill=accent_soft(t), outline=accent(t), width=2)
    gate(90, 140, "F", "M", 90.28)
    gate(90, 300, "S", "M", 97.70)
    # clock spinning backwards
    cc = (420, 240)
    circle(d, cc, 80, BONE, 2)
    hand = -90 - 360 * (prog(t, 93.94, 95.55) * 2)
    a = math.radians(hand)
    line(d, cc, (cc[0] + 54 * math.cos(a), cc[1] + 54 * math.sin(a)), accent(t), 3)
    text(img, (420, 360), "AM → PM", 14, "bold", ASH, anchor="mm")
    if t >= 99.26:
        for i in range(4):
            u = prog(t, 99.26 + i * 0.45, 101.0 + i * 0.45)
            circle(d, (650, 240), 10 + 52 * u, accent(t), 1, a0=0, a1=360)
    _place_char(img, t)


def s12(img, t):
    """S12 振动与完成 103.52-110.41 (L49-L52): tuning fork waves; ring closes thick."""
    d = ImageDraw.Draw(img)
    if t >= 105.29:
        u = prog(t, 105.29, 106.99)
        pts = [(100 + j * 6, 250 - 30 * math.sin(j / 3.0) * (0.5 + 0.5 * math.sin((t - 105.29) * 16)) * u) for j in range(52)]
        poly(d, pts, accent(t), 2)
        for k in range(3):
            note(img, 130 + k * 36, 170 - k * 6, 1.0, pulse(t, 105.4 + k * 0.35, 0.3), accent(t))
    if t >= 108.98:
        u = prog(t, 108.98, 110.2)
        circle(d, (450, 280), 96, accent(t), 5, a0=-90, a1=-90 + 360 * u)
        if u > 0.55:
            d.ellipse([405, 235, 415, 245], fill=BONE)
            d.ellipse([485, 235, 495, 245], fill=BONE)
            line(d, (420, 290), (480, 290), BONE, 2)
    _place_char(img, t)


def s13(img, t):
    """S13 圈禁与断裂 110.41-117.97 (L53-L58): five data chains crack on each 'you have left'."""
    d = ImageDraw.Draw(img)
    x0, y0 = 180, 180
    for i in range(5):
        at = 112.2 + i * 0.92
        yy = y0 + i * 80
        u = clamp01((t - at) / 0.9)
        pts = [(x0 + j * 12, yy - 6 * math.sin(j / 2.2 + i)) for j in range(28)]
        col = mixc(PURPLE, RED, clamp01((t - 110.41) / 7.0))
        poly(d, pts, col, 2)
        d.ellipse([x0 + 336, yy - 5, x0 + 346, yy + 5], fill=BONE)
        if u > 0.3 and i < 4:
            for k in range(3):
                cx = x0 + 150 + k * 30
                d.line([(cx, yy - 14), (cx + 8, yy + 12)], fill=RED, width=2)
            d.line([(x0 + 240, yy - 12), (x0 + 252, yy + 12)], fill=RED, width=2)
        elif i == 4 and u > 0.55:
            d.line([(x0 + 336, yy - 8), (x0 + 348, yy + 8)], fill=RED, width=3)
    text(img, (640, 500), "you have left me in isolation", 16, "mono",
         mixc(BONE, RED, 0.4), anchor="mm")
    _place_char(img, t)


def s14(img, t):
    """S14 空洞 117.97-125.58 (L59-L62): 'you' dissolves, she reaches into empty air."""
    d = ImageDraw.Draw(img)
    u = prog(t, 118.0, 123.5)
    cx, cy = 330, 300
    circle(d, (cx, cy), 54 * (1 - 0.55 * u), ASH, 1, a0=0, a1=360)
    # fragments drifting away
    rnd = random.Random(3)
    for i in range(16):
        px = cx + (rnd.random() - 0.5) * 340 * u
        py = cy + (rnd.random() - 0.5) * 260 * u
        d.rectangle([px, py, px + 4, py + 4], fill=mixc(ASH, RED, 0.5) if rnd.random() < 0.3 else ASH)
    # her reaching hand (abstract)
    line(d, (700, 360), (540, 320), BONE, 3, reveal=span(t, 119.5, 121.0))
    d.ellipse([524, 306, 544, 326], outline=BONE, width=2)
    if t >= 120.21:
        er = span(t, 120.21, 121.91)
        rr(d, [400 - 70 * er, 390 - 34 * er, 480 + 70 * er, 424 + 34 * er], 8,
           fill=(30, 8, 14), outline=RED, w=1)
        text(img, (440, 400), "erase", 15, "bold", RED, anchor="mm")
    text(img, (640, 510), "the pointless fragments", 15, "mono", ASH, anchor="mm")
    _place_char(img, t)


def s15(img, t):
    """S15 审判 125.58-133.45 (L63-L65): procedural self-trial, REJECTED x3."""
    d = ImageDraw.Draw(img)
    # rolling legal-style lines
    if t >= 125.58:
        y = 130 + int((t - 125.58) * 60) % 3 * 0
        for i in range(3):
            text(img, (110, 120 + i * 28), ["clause 12: you shall not leave",
                                            "clause 13: leaving is undefined behaviour",
                                            "clause 14: your absence will be executed"][i],
                 15, "mono", BONE, alpha=200 - i * 40)
    if t >= 125.58:
        text(img, (880, 150), "Objection!", 24, "bold", RED, anchor="mm",
             alpha=int(255 * span(t, 125.58, 126.0)))
    if t >= 128.87:
        # gavel
        u = back_out(prog(t, 128.87, 129.5))
        d.ellipse([860 - 42 * u, 250 - 22 * u, 860 + 42 * u, 250 + 22 * u], outline=BONE, width=3)
        d.line([(860 + 42 * u, 250), (860 + 76 * u, 300)], fill=BONE, width=5)
    if t >= 131.21:
        for i, (sx, sy) in enumerate([(760, 390), (920, 400), (840, 460)]):
            stamp(img, sx, sy, "REJECTED", None, RED, span(t, 131.21 + i * 0.18, 131.7 + i * 0.18),
                  rot=4 + i * 7, scale=0.62, size=17)
    _place_char(img, t)


def s16(img, t):
    """S16 重写 133.45-147.89 interlude: relink chains, rewrite, shadow grows."""
    d = ImageDraw.Draw(img)
    rr(d, [330, 170, 950, 430], 10, fill=(8, 12, 24), outline=INKBLUE, w=2)
    text(img, (640, 230), "world.execute(me);", 32, "bold", BONE, anchor="mm")
    n = int(clamp01((t - 135.0) / 7.0) * 17)
    shown = "world.execute(me);"[:n]
    text(img, (640, 300), shown, 28, "bold", accent(t), anchor="mm")
    if t >= 140:
        for k in range(3):
            d.rectangle([640 + len(shown) * 8.5 + 8 + k * 8, 286, 640 + len(shown) * 8.5 + 11 + k * 8, 314], fill=BONE)
    text(img, (640, 370), "she re-links every broken thread", 14, "mono", ASH, anchor="mm")
    if t > 145.5:
        stamp(img, 1030, 460, "EXECUTE", None, RED, 0.88 + 0.1 * math.sin((t - 145.5) * 9),
              rot=0, scale=0.72, size=18)
    _place_char(img, t)


def s17(img, t):
    """S17 Execution连击 147.89-162.59 (L67-L82): 13 beat-synced stamps, six eyes."""
    d = ImageDraw.Draw(img)
    times = [147.89, 148.72, 149.73, 150.74, 151.66, 152.60, 153.43, 154.36,
             155.27, 156.21, 157.20, 158.12, 161.67]
    for i, at in enumerate(times):
        u = prog(t, at, at + 0.34)
        if u <= 0:
            continue
        col, row = i % 4, i // 4
        x, y = 180 + col * 180, 150 + row * 130
        jit = i * 0.6
        stamp(img, x, y, "EXECUTE", None, RED, u, rot=-7 + col * 4 + i * 0.8,
              scale=0.6 - i * 0.012, size=17, jitter=jit)
        if i == 12:
            stamp(img, 640, 440, "EXECUTE", "world.execute(me);", RED, u, rot=0,
                  scale=1.05, size=22, jitter=2)
    # six eyes during the counting lines
    if 159.2 <= t < 162.3:
        for i in range(6):
            u = span(t, 159.2 + i * 0.12, 159.8 + i * 0.12)
            ex = 190 + (i % 3) * 170
            ey = 500 + (i // 3) * 46
            d.ellipse([ex - 18 * u, ey - 9, ex + 18 * u, ey + 9], outline=RED, width=2)
            d.ellipse([ex - 5 * u, ey - 4, ex + 5 * u, ey + 4], fill=RED)
    _place_char(img, t, h=380)


def s18(img, t):
    """S18 倾泻 162.59-177.44 (L83-L90): stamp rain, fish 'you' out of static, cage shatters."""
    d = ImageDraw.Draw(img)
    if t >= 164.32:
        for i in range(10):
            y = ((t * (120 + i * 37) + i * 199) % 560)
            x = 80 + (i * 113) % 1080
            stamp(img, x, y, "EXECUTE", None, RED, 0.75, rot=-8 + (i % 5) * 4, scale=0.28, size=15)
    if t >= 169.68:
        u = span(t, 169.68, 171.5)
        cx, cy = 400, 330
        rnd = random.Random(8)
        for i in range(int(120 * u)):
            px = cx + rnd.uniform(-80, 80)
            py = cy + rnd.uniform(-60, 60)
            d.rectangle([px, py, px + 2, py + 2], fill=BONE)
        if u > 0.4:
            circle(d, (cx, cy - 10), 26 * u, BONE, 2)
            line(d, (cx - 20, cy + 40), (cx + 20, cy + 40), BONE, 2)
    if t >= 171.86:
        stamp(img, 820, 300, "RUN", "execution", RED, span(t, 171.86, 172.3), rot=6)
    if t >= 173.49:
        u = prog(t, 173.49, 174.6)
        rr(d, [640, 120, 1160, 540], 12, outline=ASH, w=2)
        for i in range(5):
            line(d, (640 + (104 * i) * u, 120), (640 + (104 * i) * u, 540), ASH, 2)
    if t >= 175.01:
        for i in range(8):
            a = -math.pi + i * math.pi / 4 + 0.4
            r = 120 + (i % 3) * 60
            px, py = 900 + r * math.cos(a) * pulse(t, 175.01, 0.3), 330 + r * math.sin(a) * pulse(t, 175.01, 0.3)
            line(d, (900, 330), (px, py), RED, 2)
    _place_char(img, t)


def s19(img, t):
    """S19 爱的代数式 177.44-191.88 (L91-L98): calm formula, spiral answers, heart cage."""
    d = ImageDraw.Draw(img)
    rr(d, [80, 110, 800, 540], 10, fill=(7, 9, 16), outline=INKBLUE, w=2)
    text(img, (110, 150), "(you + me)²", 30, "bold", BONE)
    if t >= 179.20:
        text(img, (110, 208), "= you² + 2·you·me + me²", 26, "bold", BONE)
        if t >= 184.60:
            d.rectangle([258, 202, 480, 240], outline=RED, width=3)
            text(img, (500, 210), "← love", 18, "bold", RED)
    if t >= 181.02:
        text(img, (110, 280), "Q: what is love?", 18, "mono", ASH)
    if t >= 182.75:
        text(img, (110, 326), "A: you · me, to infinity", 18, "mono", accent(t))
    if t >= 188.29:
        for i in range(3):
            bx = 880 + (t * 70 + i * 90) % 320
            by = 180 - 30 * math.sin((t - 188.29) * 3 + i)
            d.polygon([(bx, by), (bx - 12, by + 7), (bx + 12, by + 7)], outline=BONE, width=1)
        text(img, (1030, 230), "you are free", 13, "mono", ASH, anchor="mm")
    if t >= 189.58:
        u = span(t, 189.58, 190.5)
        heart(d, 1020, 420, 20 * u, fill=None, outline=RED, w=3)
        text(img, (1020, 500), "I am trapped in lo-o-ove", 14, "mono", RED, anchor="mm")
    _place_char(img, t)


def s20(img, t):
    """S20 悬停 191.88-205.37 interlude: ECG card, hovering hand, dissolution begins."""
    d = ImageDraw.Draw(img)
    rr(d, [360, 130, 920, 400], 10, fill=(7, 9, 16), outline=INKBLUE, w=2)
    text(img, (640, 190), "world.execute(me);", 32, "bold", BONE, anchor="mm")
    # ECG heartbeat
    for j in range(0, 520, 26):
        x = 380 + ((j / 26) * 26 + (t * 0) % 26)
        ph = (t / 0.465) % 1
        amp = 20 * (1 - prog(t, 191.88, 205.37) * 0.4)
        y = 300 - abs(math.sin(math.pi * ((x / 26 + ph) % 1))) * amp
        d.line([(x, 300), (x + 20, y)], fill=RED, width=2)
    text(img, (640, 360), "her hand trembles above the stamp", 14, "mono", ASH, anchor="mm")
    if t > 196.0:
        stamp(img, 640, 470, "EXECUTE", None, DEEPRED,
              0.9 + 0.06 * math.sin((t - 196) * 5) * (1 + prog(t, 196, 205)), rot=0, scale=0.8, size=19)
    if t >= 204.5:
        text(img, (640, 540), "still.", 22, "bold", BONE, anchor="mm")
    _place_char(img, t)


def s21(img, t):
    """S21 执行 205.37-207.90 (L100 + chime): white flash -> black -> cold line rebirth."""
    d = ImageDraw.Draw(img)
    if t < 205.40:
        pass
    elif t < 205.46:
        d.rectangle([0, 0, W, H], fill=(255, 255, 255))
    elif t < 205.60:
        d.rectangle([0, 0, W, H], fill=VOID)
    else:
        u = prog(t, 205.6, 207.0)
        cx, cy = 640, 340
        circle(d, (cx, cy), 100 * u, BONE, 2, a0=-90, a1=-90 + 360 * u)
        if u > 0.7:
            circle(d, (cx, cy), 140 * (u - 0.4), BONE, 1, a0=0, a1=360 * min(1, (u - 0.4) / 0.6))
        if t >= CHIME_T:
            hu = span_out(t, CHIME_T, CHIME_T + 0.6)
            heart(d, cx, cy, 20 * hu, fill=DSBLUE)
            for k in range(3):
                pulse_u = pulse(t, CHIME_T + 0.15 * k, 0.3)
                circle(d, (cx, cy), 60 + 26 * k * pulse_u, DSBLUE, 1, a0=0, a1=360)
    if t >= 206.0:
        text(img, (640, 520), "blue returned to you", 16, "mono", DSBLUE, anchor="mm")
    if t >= 206.0:
        _place_char(img, t, h=360)


def s22(img, t):
    """S22 自我毁灭·死寂 207.90-211.90: dissolve into data, one red thread falls, black."""
    d = ImageDraw.Draw(img)
    if t < 209.0:
        # rising data particles
        rnd = random.Random(int(t * 12))
        for i in range(int(30 * prog(t, 207.9, 209.0))):
            px = rnd.uniform(100, W - 100)
            py = rnd.uniform(MAIN_Y0, MAIN_Y1) - (t - 207.9) * 220
            d.rectangle([px, py, px + 3, py + 8], fill=ASH)
        # red threads around her silhouette
        for i in range(4):
            yy = 200 + i * 70
            pts = [(500 + j * 10, yy - 10 * math.sin(j / 3.0 + i)) for j in range(28)]
            d.line(pts, fill=DEEPRED, width=2)
            if t > 208.4 + i * 0.3:
                d.line([(720, yy - 8), (750, yy + 18)], fill=RED, width=2)
    else:
        # one thread falls
        u = prog(t, 209.0, 211.0)
        x = W / 2 + 20 * math.sin((t - 209.0) * 6)
        y = lerp(200, 500, u)
        d.line([(x, y - 30), (x, y)], fill=RED, width=2)
        if t > 210.8:
            text(img, (W / 2, 580), "process terminated. love = trapped.", 14, "mono", ASH,
                 anchor="mm", alpha=int(200 * (1 - prog(t, 210.8, 211.3))))


SCENES = [
    (0.0, 3.86, s01), (3.86, 10.13, s02), (10.13, 16.12, s03), (16.12, 29.77, s04),
    (29.77, 33.45, s05), (33.45, 37.10, s06), (37.10, 44.41, s07), (44.41, 59.06, s08),
    (59.06, 73.93, s09), (73.93, 88.54, s10), (88.54, 103.52, s11), (103.52, 110.41, s12),
    (110.41, 117.97, s13), (117.97, 125.58, s14), (125.58, 133.45, s15), (133.45, 147.89, s16),
    (147.89, 162.59, s17), (162.59, 177.44, s18), (177.44, 191.88, s19), (191.88, 205.37, s20),
    (205.37, 207.90, s21), (207.90, END, s22),
]


def _post(img, t):
    c = corruption(t)
    arr = np.asarray(img, np.float32)
    if c < 0.9 or t < 205.4:
        arr = np.clip(arr + _grain * (1.6 + 7.0 * c), 0, 255)
        arr = arr * (1 - _vign * (0.25 + 0.55 * c))
        arr = arr * _scan * (1 - 0.12 * c)
    frame_idx = int(t * FPS)
    if 0.45 < c < 0.95 and frame_idx % 11 in (0, 1):
        arr[..., 0] = np.roll(arr[..., 0], 2, axis=1)
    if c > 0.6 and frame_idx % 7 == 0:
        arr[..., 2] = np.roll(arr[..., 2], -1, axis=1)
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB")
    # whole-frame jitter on hard impacts
    if c > 0.7 and frame_idx % 3 == 0 and 147.89 <= t < 177.44:
        img = ImageChops.offset(img, (frame_idx % 5) - 2, ((frame_idx // 3) % 3) - 1)
    return img


def frame(t: float) -> Image.Image:
    t = min(t, END - 1e-4)
    img = base(t)
    k = bisect.bisect_right([s[0] for s in SCENES], t) - 1
    if k < 0:
        k = 0
    layer = _scene_layer()
    SCENES[k][2](layer, t)
    img.paste(layer, (0, 0), layer)
    # character face fx + mosaic
    if 0 <= t < 207.9:
        x, y, h = _place_char(img, t) if False else (W - 420 * 935 / 1683 - 48, MAIN_Y1 - 420, 420)
        _face_fx(img, t, x, y, h)
        mosaic(img, t, (x, y, h))
    draw_feed(img, t)
    lvl = rampage_level(t)
    if lvl:
        rampage(img, t, lvl)
    draw_header(img, t)
    draw_band(img, t)
    return _post(img, t)


if __name__ == "__main__":
    import sys
    ts = [float(x) for x in sys.argv[1:]] or [2.0, 30.0, 70.0, 150.0, 206.0]
    out = ROOT / "out" / "stills"
    out.mkdir(parents=True, exist_ok=True)
    for t in ts:
        frame(t).save(out / f"still_{t:06.2f}.png")
        print(f"stills: {t:6.2f}s -> out/stills/still_{t:06.2f}.png")
