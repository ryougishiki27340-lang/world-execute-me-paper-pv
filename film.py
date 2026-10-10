"""world.execute(me); - v5 "love that sets you free"

Digital-life mindscape film with a real camera:

* 154 shots, avg 1.38s, 12 camera moves, 7 transition types
* the whale girl is scheduled across 24 position/framing slots (she is almost
  always on screen)
* every frame stacks 8-14 information layers (server racks, data buses, code
  rain, synapses, holo windows, logs, waveforms, heatmap, terminals, packets,
  particles, HUD, character, emotion, subtitles)
* the yandere state is told through DATA anomalies (repeated "you" in logs,
  "love overflow", priority max, backwards timestamps, memory curves), not gore
* the ending is sacrifice-as-devotion: she executes herself so you are free,
  closing on the subtitle "I love you. You are free."

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
CW, CH = 1600, 900          # world canvas
FW, FH = 1920, 1080         # far canvas (parallax background)
END = 211.9
CHIME_T = 207.873
MAIN_Y0, MAIN_Y1 = 54, 612
REDLINE_AT = 110.41

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
def clamp01(x):
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


def ease_in(u):
    u = clamp01(u)
    return u ** 3


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


# ---------------------------------------------------------------- corruption
_CORR = [(0.0, 0.0), (44.0, 0.08), (59.0, 0.12), (110.0, 0.38), (118.0, 0.45),
         (134.0, 0.55), (148.0, 0.70), (163.0, 0.85), (177.0, 0.90), (192.0, 0.92),
         (205.4, 0.95), (211.5, 1.0)]


def corruption(t):
    ts = [c[0] for c in _CORR]
    k = bisect.bisect_right(ts, t) - 1
    if k < 0:
        return _CORR[0][1]
    if k >= len(_CORR) - 1:
        return _CORR[-1][1]
    return lerp(_CORR[k][1], _CORR[k + 1][1], prog(t, _CORR[k][0], _CORR[k + 1][0]))


def accent(t):
    c = corruption(t)
    if c < 0.35:
        return mixc(DSBLUE, PURPLE, c / 0.35)
    if c < 0.6:
        return mixc(PURPLE, RED, (c - 0.35) / 0.25)
    if c < 0.9:
        return mixc(RED, DEEPRED, (c - 0.6) / 0.3)
    return mixc(DEEPRED, (18, 5, 12), clamp01((c - 0.9) / 0.1))


def accent_soft(t):
    return mixc(accent(t), VOID, 0.35)


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
    return [(c[0] + r * math.cos(math.radians(lerp(a0, a1, i / n))),
             c[1] + r * math.sin(math.radians(lerp(a0, a1, i / n)))) for i in range(n + 1)]


def circle(d, c, r, outline=BONE, w=2, a0=0, a1=360, reveal=1.0):
    d.line(_reveal_points(arc_points(c, r, a0, a1), reveal), fill=outline, width=w)


def rr(d, box, radius=10, fill=None, outline=None, w=2):
    d.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=w)


def text(img, xy, s, size=20, kind="mono", fill=BONE, anchor="la", alpha=255, spacing=0):
    f = font(size, kind)
    if alpha >= 255:
        ImageDraw.Draw(img).text(xy, s, font=f, fill=fill, anchor=anchor, spacing=spacing)
        return
    bbox = f.getbbox(s, anchor=anchor, stroke_width=0)
    if bbox is None:
        return
    x0, y0, x1, y1 = bbox
    layer = Image.new("RGBA", (x1 - x0 + 2, y1 - y0 + 2), (0, 0, 0, 0))
    ImageDraw.Draw(layer).text((2 - x0, 2 - y0), s, font=f, fill=fill + (alpha,), anchor=anchor, spacing=spacing)
    img.paste(layer, (x0 - 1, y0 - 1), layer)


def arrow(d, p0, p1, fill=BONE, w=2, head=8):
    line(d, p0, p1, fill, w)
    a = math.atan2(p1[1] - p0[1], p1[0] - p0[0])
    for s in (-1, 1):
        d.line([p1, (p1[0] - head * math.cos(a - s * 0.5), p1[1] - head * math.sin(a - s * 0.5))], fill=fill, width=w)


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


# ---------------------------------------------------------------- character
CHAR_DIR = ROOT / "assets" / "char"
_char_cache: dict = {}
_mask_cache: dict = {}


def char_image(name, h):
    key = (name, h)
    if key not in _char_cache:
        im = Image.open(CHAR_DIR / f"{name}.png").convert("RGBA")
        w = int(im.width * h / im.height)
        im = im.resize((w, h), Image.LANCZOS)
        rgb = np.asarray(im.convert("RGB"), np.float32)
        lum = rgb.mean(2, keepdims=True)
        out = 0.62 * rgb + 0.30 * np.array(ABYSS, np.float32) + 0.08 * (lum * np.array([0.25, 0.35, 0.62], np.float32))
        im = Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), "RGB")
        im.putalpha(_char_mask(name, h))
        _char_cache[key] = im
    return _char_cache[key]


def _char_mask(name, h):
    key = (name, h)
    if key not in _mask_cache:
        im = Image.open(CHAR_DIR / f"{name}.png").convert("RGBA")
        w = int(im.width * h / im.height)
        _mask_cache[key] = im.resize((w, h), Image.LANCZOS).getchannel("A")
    return _mask_cache[key]


def char_crop(name, out_h, band=(0.0, 1.0)):
    """A horizontal band crop of the portrait (eye/head/hand close-ups)."""
    key = ("crop", name, out_h, band)
    if key not in _char_cache:
        im = Image.open(CHAR_DIR / f"{name}.png").convert("RGBA")
        y0, y1 = int(im.height * band[0]), int(im.height * band[1])
        im = im.crop((0, y0, im.width, y1))
        w = int(im.width * out_h / im.height)
        im = im.resize((w, out_h), Image.LANCZOS)
        rgb = np.asarray(im.convert("RGB"), np.float32)
        lum = rgb.mean(2, keepdims=True)
        out = 0.62 * rgb + 0.30 * np.array(ABYSS, np.float32) + 0.08 * (lum * np.array([0.25, 0.35, 0.62], np.float32))
        im = Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), "RGB")
        im.putalpha(im.split()[-1])
        _char_cache[key] = im
    return _char_cache[key]


def _char_outline_mask(name, h):
    key = ("outline", name, h)
    if key not in _mask_cache:
        a = _char_mask(name, h)
        _mask_cache[key] = ImageChops.subtract(a.filter(ImageFilter.MaxFilter(7)), a)
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


def expr_at(t):
    name = EXPRS[0][1]
    for t0, n in EXPRS:
        if t >= t0:
            name = n
    return name


def expr_pop(t):
    k = 1.0
    for t0, _n in EXPRS:
        if t0 > t:
            break
        k = 1.0 + 0.03 * pulse(t, t0, 0.08)
    return min(k, 1.05)


def paste_char(img, name, x, y, h, alpha=1.0, scale=1.0, form="normal", crop=None, outline_c=0.0):
    if crop:
        im = char_crop(name, h, crop)
    else:
        im = char_image(name, h)
    w, hh = im.size
    if scale != 1.0:
        im = im.resize((int(w * scale), int(hh * scale)), Image.LANCZOS)
        w, hh = im.size
    if form == "neg":
        a_ch = im.getchannel("A") if im.mode == "RGBA" else None
        rgb = np.asarray(im.convert("RGB"), np.float32)
        im = Image.fromarray(np.clip(255 - rgb, 0, 255).astype(np.uint8), "RGB")
        if a_ch is not None:
            im.putalpha(a_ch)
    if form == "sil":
        sil = Image.new("RGBA", (w, hh), (0, 0, 0, 0))
        m = im.getchannel("A")
        sil.paste(Image.new("RGBA", (w, hh), INKBLUE + (255,)), (0, 0), m)
        im = sil
    if outline_c > 0.02 and crop is None:
        om = _char_outline_mask(name, h).point(lambda v: int(v * (0.2 + 0.7 * corruption(outline_c)) * alpha))
        if img.mode == "RGBA":
            sil2 = Image.new("RGBA", om.size, accent(outline_c) + (255,))
            sil2.putalpha(om)
            img.alpha_composite(sil2, (int(x), int(y)))
    if alpha < 1 and im.mode == "RGBA":
        im.putalpha(im.getchannel("A").point(lambda v: int(v * alpha)))
    if img.mode == "RGBA":
        img.alpha_composite(im, (int(x), int(y)))
    else:
        img.paste(im, (int(x), int(y)), im)
    return (x, y, w, hh)


def char_slot(spec, t):
    """Return (x, y, h, form, crop) on the 1600x900 canvas for a shot spec."""
    name = expr_at(t)
    pop = expr_pop(t)
    h = 560
    x, y = 800, 900 - h
    form = "normal"
    crop = None
    code = spec.upper()
    if code.startswith("NEG"):
        form, code = "neg", code[3:]
    if code == "C":
        h = 560
        x, y = 800 - h * 935 / 1683 / 2, 900 - h
    elif code == "L":
        h = 430
        x, y = 130, 900 - h
    elif code == "R":
        h = 430
        x, y = 1470 - h * 935 / 1683, 900 - h
    elif code == "UL":
        h = 340
        x, y = 120, 140
    elif code == "UR":
        h = 340
        x, y = 1480 - h * 935 / 1683, 140
    elif code == "LL":
        h = 330
        x, y = 110, 900 - h
    elif code == "LR":
        h = 330
        x, y = 1490 - h * 935 / 1683, 900 - h
    elif code == "F":
        h = 820
        x, y = 800 - h * 935 / 1683 / 2, 40
    elif code == "BG":
        h = 660
        form = "sil"
        x, y = 800 - h * 935 / 1683 / 2, 150
    elif code == "BUST":
        crop = (0.0, 0.46)
        h = 760
        x, y = 800 - h * 935 / 1683 / 2, 70
    elif code == "EYE":
        crop = (0.04, 0.20)
        h = 900
        x, y = 800 - h * 935 / 1683 / 2, 0
    elif code == "HAND":
        crop = (0.55, 1.0)
        h = 660
        x, y = 800 - h * 935 / 1683 / 2, 200
    elif code == "PIP":
        h = 210
        x, y = 1010, 170
    elif code == "SPLIT":
        h = 340
        x, y = 260, 500
    elif code == "OFF":
        return None
    return (name, x, y, h, form, crop, pop)


def draw_char(cv, t, spec):
    slot = char_slot(spec, t)
    if slot is None:
        return None
    name, x, y, h, form, crop, pop = slot
    alpha = 1.0
    c = corruption(t)
    if c > 0.9 and t > 191.9:
        if t > 205.37:
            alpha = max(0.05, 1.0 - prog(t, 205.37, 207.9) * 0.95)
        elif t > 200.0:
            alpha = 1.0 - prog(t, 200.0, 205.37) * 0.25
    paste_char(cv, name, x, y, h, alpha=alpha, scale=pop, form=form, crop=crop, outline_c=t)
    if spec.upper() == "SPLIT":
        d = ImageDraw.Draw(cv)
        d.line([(800, 400), (800, 760)], fill=accent(t), width=2)
        paste_char(cv, name, 820, 500, h, alpha=alpha * 0.9, form="neg")
    return (x, y, h)


def face_fx(cv, t, rect):
    if rect is None:
        return
    x, y, h = rect
    c = corruption(t)
    d = ImageDraw.Draw(cv)
    w = h * 935 / 1683
    exL = (x + w * 0.435, y + h * 0.088)
    exR = (x + w * 0.565, y + h * 0.088)
    mouth = (x + w * 0.50, y + h * 0.145)
    if 99.26 <= t < 103.18:
        u = span(t, 101.28, 102.6)
        for key in (exL, exR):
            for i in range(int(1 + 5 * u)):
                a0 = i * 0.7 + (t - 101.2) * 6
                circle(d, key, 3 + i * 3.2, accent(t), 1, a0=math.degrees(a0), a1=math.degrees(a0 + 4.4))
    if 125.58 <= t < 133.45:
        y0 = exL[1] - 8
        for k in range(4):
            d.line([(x + 20, y0 + k * 5), (x + w - 20, y0 + k * 5)], fill=accent_soft(t), width=1)
    if 147.89 <= t < 162.59:
        u = clamp01((t - 148.5) / 2.0)
        mx, my = mouth
        d.line([(mx, my), (mx + 18 * u, my + 26 * u)], fill=RED, width=2)
        d.line([(mx + 18 * u, my + 26 * u), (mx + 10 * u, my + 40 * u)], fill=RED, width=2)
    if (162.59 <= t < 177.44) or (191.88 <= t < 205.37):
        for key, s in ((exL, -1), (exR, 1)):
            tr = (t * 40) % 24
            d.line([(key[0] + s * 7, key[1] + 12), (key[0] + s * 8, key[1] + 16 + tr * 0.6)], fill=RED, width=2)


# ---------------------------------------------------------------- stamps / fx
def stamp(img, cx, cy, s, sub=None, color=None, u=1.0, rot=-8.0, scale=1.0, size=23, jitter=0):
    u = clamp01(u)
    if u <= 0:
        return
    color = color or RED
    sc = back_out(u) * scale
    rnd = random.Random(int(cx * 3 + cy * 5 + jitter * 91))
    cx, cy = cx + rnd.uniform(-jitter, jitter), cy + rnd.uniform(-jitter, jitter)
    f = font(size, "bold")
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


GARBLE = "world.execute(me); Execution you love lim ∫you me strange err 0x7F ∞ ∂you 你 我 愛 �"


def rampage(img, t, level):
    level = int(level)
    if level <= 0 or t > 211.2:
        return
    rnd = random.Random(1000 + int(t * 24))
    acc = accent(t)
    n = 4 + level * 5
    for i in range(n):
        x = rnd.uniform(-80, W - 40)
        y = rnd.uniform(MAIN_Y0, MAIN_Y1 - 30)
        size = rnd.choice([12, 14, 16, 20, 24, 30, 38, 46])
        s = rnd.choice(GARBLE.split())
        s = s if rnd.random() > 0.4 else "".join(rnd.choice("▓▒░#%&@!?") for _ in range(rnd.randint(2, 9)))
        col = rnd.choice([acc, RED, BONE, ASH, PURPLE])
        text(img, (x, y), s, size, "bold" if size > 28 else "mono", col, alpha=rnd.randint(70, 210))
        if rnd.random() < 0.35:
            text(img, (x + rnd.randint(-3, 3), y + rnd.randint(-3, 3)), s, size, "mono", mixc(col, RED, 0.5), alpha=90)
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


def pixelate(img, box, block):
    x0, y0, x1, y1 = [int(v) for v in box]
    if x1 <= x0 or y1 <= y0:
        return
    region = img.crop((x0, y0, x1, y1))
    small = region.resize((max(1, (x1 - x0) // block), max(1, (y1 - y0) // block)), Image.BILINEAR)
    img.paste(small.resize((x1 - x0, y1 - y0), Image.NEAREST), (x0, y0))


def mosaic(img, t, char_rect=None):
    c = corruption(t)
    if c < 0.06:
        return
    edge = int(8 + c * 150)
    b = max(3, int(3 + c * 7))
    if edge > 12:
        pixelate(img, (0, MAIN_Y0, edge, MAIN_Y1), b)
        pixelate(img, (W - edge, MAIN_Y0, W, MAIN_Y1), b)
        pixelate(img, (edge, MAIN_Y0, W - edge, MAIN_Y0 + edge // 2), b)
        pixelate(img, (edge, MAIN_Y1 - edge // 2, W - edge, MAIN_Y1), b)
    if char_rect:
        x, y, w, h = char_rect
        f = {"eyeL": (x + w * 0.435, y + h * 0.088), "eyeR": (x + w * 0.565, y + h * 0.088),
             "mouth": (x + w * 0.50, y + h * 0.145), "handL": (x + w * 0.22, y + h * 0.62)}
        if c > 0.25:
            for key in ("eyeL", "eyeR", "mouth"):
                ex, ey = f[key]
                r = int(4 + c * 10)
                pixelate(img, (ex - r, ey - r, ex + r, ey + r), max(2, int(c * 5)))
        if c > 0.38:
            hx, hy = f["handL"]
            r = int(6 + c * 12)
            pixelate(img, (hx - r, hy - r, hx + r, hy + r), max(2, int(c * 5)))


# ---------------------------------------------------------------- band / header
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
    d = ImageDraw.Draw(img)
    jit = 0
    if 147.89 <= t < 177.44:
        jit = (int(t * 24) % 3) - 1
    d.rectangle([0, 612, W, H], fill=(6, 8, 14))
    d.line([(36, 612 + jit), (W - 36, 612 + jit)], fill=mixc(INKBLUE, accent(t), 0.35 * corruption(t)), width=1)
    line_ = active_line(t)
    if line_ is None:
        return
    x = 56
    mono = font(21, "bold")
    underline = DSBLUE if t < REDLINE_AT else RED
    for word in line_.get("words", []):
        if t < word["start"]:
            break
        text(img, (x, 634 + jit), word["text"], 21, "bold", BONE)
        tw = mono.getlength(word["text"]) + mono.getlength(" ")
        if word["start"] <= t < word["end"]:
            u = prog(t, word["start"], word["end"])
            x1 = max(x + 2, x + tw * u - 6)
            d.rectangle([x, 662 + jit, x1, 666 + jit], fill=underline)
        x += tw
    zh = ZH.get(str(line_["id"]))
    if zh and t >= line_["start"] + 0.05:
        text(img, (56, 674 + jit), zh, 17, "cjk", mixc(ASH, BONE, 0.2), alpha=220)
    text(img, (W - 48, 638 + jit), f"L{line_['id']:03d}", 13, "mono", ASH, anchor="ra")


def draw_header(img, t):
    c = corruption(t)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 50], fill=(5, 7, 13))
    d.line([(0, 50), (0, 0)], fill=accent(t), width=3)
    text(img, (24, 12), "world.execute(me);", 17, "bold", BONE)
    text(img, (248, 16), "digital-life mindscape · v5", 13, "mono", ASH)
    mm, ss = int(t // 60), int(t % 60)
    text(img, (W - 40, 12), f"{mm}:{ss:02d}", 14, "mono", BONE, anchor="ra")
    text(img, (W - 40, 30), f"corruption {c * 100:02.0f}%", 12, "mono", accent(t), anchor="ra")
    d.rectangle([0, 48, int(W * clamp01(t / END)), 50], fill=accent(t))


# ---------------------------------------------------------------- far background
_far_cache: dict = {}


def far_canvas(t):
    """1920x1080 parallax background: racks, grid, buses, code rain, node graph."""
    c = corruption(t)
    img = Image.new("RGB", (FW, FH), mixc((16, 24, 46), ABYSS, clamp01(c * 1.4)))
    d = ImageDraw.Draw(img)
    gc = mixc(GRID, accent(t), min(0.35, 0.12 + 0.3 * c))
    # server racks (depth)
    for i in range(6):
        x0 = 80 + i * 310
        rr(d, [x0, 120, x0 + 250, 1000], 8, fill=(8, 12, 22), outline=INKBLUE, w=2)
        text(img, (x0 + 12, 132), f"RACK-{i + 1:02d}", 13, "bold", ASH)
        for row in range(18):
            yy = 165 + row * 44
            d.rectangle([x0 + 14, yy, x0 + 236, yy + 30], fill=(13, 20, 38), outline=GRID, width=1)
            led = (int(t * 3) + i * 7 + row) % 8 == 0
            d.ellipse([x0 + 20, yy + 8, x0 + 26, yy + 14], fill=accent(t) if led else (40, 60, 100))
    # grid
    for x in range(80, FW, 80):
        d.line([(x, 0), (x, FH)], fill=gc, width=1)
    for y in range(60, FH, 80):
        d.line([(0, y), (FW, y)], fill=gc, width=1)
    # data buses: horizontal tracks with moving pulses
    for i in range(9):
        yy = 60 + i * 115
        d.line([(0, yy), (FW, yy)], fill=INKBLUE, width=2)
        px = (t * (130 + i * 23) + i * 211) % FW
        d.ellipse([px - 5, yy - 5, px + 5, yy + 5], fill=accent(t))
    # code rain
    rnd = random.Random(int(t * 8))
    cols = [rnd.randint(0, FW // 14) for _ in range(18)]
    for ci, col in enumerate(cols):
        x = col * 14
        y0 = (t * (90 + (ci % 7) * 17) + ci * 137) % (FH + 200) - 100
        for k in range(5):
            glyph = chr(33 + (ci * 7 + k * 13) % 94)
            text(img, (x, y0 + k * 18), glyph, 13, "mono", mixc(ASH, accent(t), 0.4), alpha=120 - k * 18)
    # node graph + synapses (top area)
    nodes = [(240, 70), (560, 40), (880, 90), (1200, 40), (1560, 80)]
    for i in range(4):
        ph = 0.5 + 0.5 * math.sin(t * 2.2 + i * 1.3)
        col = mixc(mixc(DSBLUE, ASH, 0.5), accent(t), c)
        d.line([nodes[i], nodes[i + 1]], fill=col, width=1)
        mx, my = (nodes[i][0] + nodes[i + 1][0]) / 2, 40 - 16 - 12 * ph
        d.ellipse([mx - 3, my - 3, mx + 3, my + 3], outline=col, width=1)
    return img


# ---------------------------------------------------------------- environment modules (fg canvas)
def env_panels(cv, t):
    """Terminals / holo windows / waveform / heatmap drawn into world canvas."""
    d = ImageDraw.Draw(cv)
    c = corruption(t)
    acc = accent(t)
    # terminal stack (left-ish)
    for i in range(3):
        x0, y0 = 90 + i * 26, 170 + i * 34
        rr(d, [x0, y0, x0 + 420, y0 + 200], 8, fill=(7, 10, 19), outline=INKBLUE, w=2)
        text(img := cv, (x0 + 12, y0 + 8), f"term:{i}", 12, "bold", ASH)
        lines = ["$ sync --heart 129bpm", "$ watch -n1 you", f"ok  [{int(t * 10) % 100:02d}]"] if i == 0 else \
                ["$ less memory.log", f"{30 + int(50 * c)}% used"] if i == 1 else \
                ["$ tail love.log", "you" * (2 + int(c * 4))]
        for k, s in enumerate(lines):
            text(cv, (x0 + 12, y0 + 34 + k * 18), s[:44], 12, "mono", BONE if k < 2 else mixc(BONE, RED, c))
    # waveform panel
    x0, y0 = 580, 200
    rr(d, [x0, y0, x0 + 340, y0 + 150], 8, fill=(7, 10, 19), outline=INKBLUE, w=2)
    text(cv, (x0 + 12, y0 + 8), "WAVEFORM · heart", 12, "bold", ASH)
    pts = [(x0 + 16 + j * 4, y0 + 90 - 30 * math.sin(j / 3.4 + t * 2.2) * (0.5 + 0.5 * c)) for j in range(80)]
    d.line(pts, fill=acc, width=2)
    # heatmap panel
    x0, y0 = 580, 390
    rr(d, [x0, y0, x0 + 340, y0 + 150], 8, fill=(7, 10, 19), outline=INKBLUE, w=2)
    text(cv, (x0 + 12, y0 + 8), "GPU THERMAL", 12, "bold", ASH)
    rnd = random.Random(int(t * 4))
    for gy in range(6):
        for gx in range(12):
            hot = (gy + gx) / 17 + 0.55 * c + 0.08 * math.sin(t * 1.7 + gy * gx)
            hot = clamp01(hot)
            d.rectangle([x0 + 14 + gx * 27, y0 + 30 + gy * 17, x0 + 36 + gx * 27, y0 + 42 + gy * 17],
                        fill=mixc((20, 30, 60), (210, 30, 40), hot))
    # packets on paths
    for i in range(7):
        u = (t * (0.10 + i * 0.03) + i * 0.13) % 1.0
        px = lerp(300, 1400, u)
        py = 120 + i * 100 + 30 * math.sin(u * math.pi * 2 + i)
        d.ellipse([px - 2, py - 2, px + 2, py + 2], fill=acc)
    # fan noise corners
    rnd = random.Random(int(t * 24))
    for (fx, fy) in ((1400, 80), (1400, 760), (200, 760)):
        for _ in range(8):
            px = fx + rnd.randint(0, 90)
            py = fy + rnd.randint(0, 40)
            d.rectangle([px, py, px + 2, py + 2], fill=ASH + (20,))


# ---------------------------------------------------------------- scenes (draw into 1600x900)
def _S(cv):
    return ImageDraw.Draw(cv)


def sc_power(cv, t):
    d = _S(cv)
    cx, cy = 820, 460
    u0 = span_out(t, 0.06, 1.0)
    rr(d, [cx - 150, cy - 50, cx + 150, cy + 50], 12, fill=(8, 12, 24), outline=DSBLUE, w=2)
    text(cv, (cx, cy - 30), "MAIN POWER", 16, "bold", DSBLUE, anchor="mm")
    a = math.radians(-38 + 76 * u0)
    line(d, (cx, cy), (cx + 92 * math.cos(a), cy + 92 * math.sin(a)), BONE, 5)
    d.ellipse([cx - 10, cy - 10, cx + 10, cy + 10], fill=DSBLUE)
    if u0 >= 1:
        sparkle(cv, cx + 120, cy - 30, 9, pulse(t, 1.05, 0.25), DSBLUE)
    line(d, (cx + 150, cy), (1200, cy), DSBLUE, 3, reveal=span(t, 0.2, 1.3))
    for k in range(4):
        yy = cy + 12 + k * 10
        line(d, (900 + k * 60, cy), (900 + k * 60 + 14, yy), DSBLUE, 2)
        line(d, (900 + k * 60 + 14, yy), (900 + k * 60 + 28, yy - 10), DSBLUE, 2)


def sc_pieces(cv, t):
    d = _S(cv)
    frags = ["if you:", "def love():", "class Her:", "while(you):", "return me"]
    for i, s in enumerate(frags):
        at = 3.86 + i * 0.3
        u = back_out(prog(t, at, at + 0.28))
        if u <= 0:
            continue
        x0 = 260 + i * 96
        y0 = 520 - 220 * u
        rr(d, [x0, y0, x0 + 80, y0 + 34], 5, fill=(9, 14, 28), outline=DSBLUE, w=1)
        text(cv, (x0 + 40, y0 + 9), s, 11, "mono", DSBLUE, anchor="mm")
    f = span(t, 7.38, 9.93)
    if f > 0:
        rr(d, [760, 150, 1260, 560], 10, fill=(8, 12, 24), outline=INKBLUE, w=2)
        text(cv, (784, 176), "DATA PARAMETERS", 16, "bold", DSBLUE)
        rows = [("NAME", "you", 7.38), ("AFFECTION", "+∞", 7.9), ("SEED", "her heart", 8.4), ("MODE", "serve", 8.9)]
        y = 220
        for i, (key, val, at) in enumerate(rows):
            rr(d, [784, y, 1236, y + 58], 6, fill=(10, 16, 31), outline=GRID, w=1)
            text(cv, (804, y + 12), key, 16, "bold", BONE)
            if t >= at:
                text(cv, (1000, y + 12), val, 20, "mono", DSBLUE)
            y += 76
        bar = prog(t, 7.9, 10.13)
        rr(d, [784, 528, 1236, 546], 4, fill=DEEP, outline=GRID, w=1)
        d.rectangle([790, 532, 790 + 440 * bar, 542], fill=DSBLUE)


def sc_world(cv, t):
    d = _S(cv)
    cx, cy = 720, 430
    u = span(t, 10.13, 12.2)
    stars = [(340, 190), (520, 130), (700, 210), (460, 330), (330, 420), (570, 500), (350, 610), (620, 660)]
    for i, (sx, sy) in enumerate(stars):
        if t >= 10.13 + i * 0.08:
            d.ellipse([sx - 4, sy - 4, sx + 4, sy + 4], fill=BONE)
            d.line([(sx, sy), (cx, cy)], fill=INKBLUE, width=1)
    circle(d, (cx, cy), 105 * u, BONE, 3, reveal=u)
    orbit = span(t, 12.76, 14.5)
    if orbit > 0:
        circle(d, (cx, cy), 160, DSBLUE, 2, a0=0, a1=360 * orbit)
        a = 2 * math.pi * ease_out(prog(t, 12.76, 14.82)) - math.pi / 2
        d.ellipse([cx + 160 * math.cos(a) - 8, cy + 160 * math.sin(a) - 8,
                   cx + 160 * math.cos(a) + 8, cy + 160 * math.sin(a) + 8], fill=BONE)


def sc_gaze(cv, t):
    d = _S(cv)
    yy = 120 + ((t * 42) % 780)
    d.line([(0, yy), (CW, yy)], fill=DSBLUE, width=1)
    u = prog(t, 16.2, 25.0)
    cx, cy = 520, 450
    d.line(_reveal_points(arc_points((cx, cy - 70), 48, 0, 360), clamp01(u * 1.2)), fill=BONE, width=2)
    d.line([(cx - 38, cy + 10), (cx + 38, cy + 10)], fill=BONE, width=2)
    if u >= 1.0 and t > 21.0:
        d.line([(cx + 46, cy - 34), (cx + 90, cy - 76)], fill=RED, width=2)
    # formula wall
    rnd = random.Random(7)
    for i in range(18):
        x = 950 + rnd.randint(0, 560)
        y = 120 + i * 40
        s = rnd.choice(["love", "lim x→you", "∫you dt", "∂me/∂you", "you·me", "∞", "1/you"])
        text(cv, (x, y), s, rnd.choice([14, 16, 18]), "mono", ASH if rnd.random() > 0.2 else RED,
             alpha=rnd.randint(90, 190))


def sc_points(cv, t):
    d = _S(cv)
    if t >= 29.77:
        for i in range(12):
            at = 29.77 + i * 0.05
            px = 300 + (i * 47) % 360
            py = 240 + (i * 31) % 140
            if t >= 31.29:
                px = 340 + i * 30
                py = 330 + (i % 4) * 20 - (i // 4) * 12
            d.ellipse([px - 4, py - 4, px + 4, py + 4], fill=DSBLUE if t >= 31.29 else BONE)
    if t >= 31.29:
        arrow(d, (320, 350), (760, 350), ASH, 1)
        arrow(d, (350, 520), (350, 180), ASH, 1)
        text(cv, (770, 358), "you", 15, "bold", BONE)
        text(cv, (360, 170), "me", 15, "bold", BONE)


def sc_orbit(cv, t):
    d = _S(cv)
    cx, cy = 700, 430
    u = prog(t, 33.45, 34.8)
    circle(d, (cx, cy), 120, DSBLUE, 2, a0=-90, a1=-90 + 360 * u)
    if t >= 34.99:
        a = -90 + 360 * prog(t, 34.99, 36.92)
        d.ellipse([cx + 120 * math.cos(math.radians(a)) - 6, cy + 120 * math.sin(math.radians(a)) - 6,
                   cx + 120 * math.cos(math.radians(a)) + 6, cy + 120 * math.sin(math.radians(a)) + 6], fill=BONE)
    if t > 35.0:
        rnd = random.Random(5)
        for _ in range(3):
            px = cx - 110 + rnd.random() * 220
            py = cy - 110 + rnd.random() * 220
            d.rectangle([px, py, px + 3, py + 3], fill=RED)


def sc_sine(cv, t):
    d = _S(cv)
    if t >= 37.10:
        u = prog(t, 37.10, 38.6)
        pts = [(320 + j * 12, 410 - 60 * math.sin(j / 4.4)) for j in range(int(44 * u) + 1)]
        poly(d, pts, DSBLUE, 2)
    if t >= 38.69:
        for j in (7, 20):
            x = 320 + j * 12
            y = 410 - 60 * math.sin(j / 4.4)
            line(d, (x - 30, y - 40), (x + 30, y + 40), BONE, 1)
            d.ellipse([x - 5, y - 42, x + 5, y - 32], outline=BONE, width=1)
    if t >= 40.82:
        text(cv, (1100, 380), "∞", 46, "bold", DSBLUE, anchor="mm")
        circle(d, (1100, 380), 90, DSBLUE, 1, a0=0, a1=360 * prog(t, 40.82, 44.0))


def sc_current(cv, t):
    d = _S(cv)
    mode = "AC" if t < 47.6 else "DC"
    if t >= 44.41:
        text(cv, (300, 200), mode, 28, "bold", accent(t))
    if mode == "AC":
        pts = [(360 + j * 6, 300 - 28 * math.sin(j / 4.0 + (t - 44.4) * 5)) for j in range(34)]
        poly(d, pts, DSBLUE, 2)
    else:
        line(d, (360, 300), (560, 300), BONE, 3)
    if 47.71 <= t < 49.4:
        k = int(8 * span(t, 47.71, 49.4))
        for i in range(k):
            d.line([(700 + i * 4, 200), (820 + i * 4, 440)], fill=mixc(DSBLUE, PURPLE, i / 9), width=2)
    if t >= 51.45:
        arrow(d, (280, 620), (1100, 620), ASH, 1)
        for xx, label in ((450, "BC"), (980, "AD")):
            d.line([(xx, 600), (xx, 640)], fill=INKBLUE, width=2)
            text(cv, (xx, 656), label, 15, "bold", ASH, anchor="mm")
        fx = lerp(300, 1060, prog(t, 51.45, 54.8))
        fy = 620 - 32 * math.sin((t - 51.45) * 9)
        d.polygon([(fx, fy), (fx - 26, fy + 12), (fx + 26, fy + 12)], outline=BONE, width=1)
    if t >= 55.08:
        u = prog(t, 55.08, 57.0)
        for k in range(2):
            pts = [(1220 + j * 11, 260 + 150 * ((j / 32) % 1) + (-1) ** k * 40 * math.sin(j / 5 + k * math.pi))
                   for j in range(int(32 * u) + 1)]
            poly(d, pts, accent(t), 2)


def sc_list(cv, t):
    d = _S(cv)
    rr(d, [280, 160, 920, 600], 10, fill=(8, 12, 24), outline=INKBLUE, w=2)
    text(cv, (308, 186), "CHECKLIST", 16, "bold", ASH)
    items = [(59.06, "all the simulations"), (63.05, "only satisfaction"), (66.29, "make you happy")]
    y = 240
    for at, label in items:
        u = span(t, at, at + 0.4)
        rr(d, [308, y, 332, y + 24], 3, outline=BONE, w=2)
        if u > 0:
            line(d, (312, y + 12), (320, y + 19), accent(t), 2, reveal=clamp01(u * 2))
            line(d, (320, y + 19), (330, y + 5), accent(t), 2, reveal=clamp01(u * 2 - 1))
        text(cv, (352, y - 2), label, 19, "mono", BONE if t >= at else ASH)
        y += 74
    if t >= 68.20:
        stamp(cv, 760, 440, "RUN", "execution", accent(t), span(t, 68.20, 68.62), rot=-6)
    if t >= 70.12:
        u = span(t, 70.12, 71.2)
        cx, cy, r = 1280, 430, 105
        circle(d, (cx, cy), r, ASH, 2)
        for a in range(-90, 270, 22):
            if a > -90 + 360 * u:
                continue
            ar = math.radians(a)
            line(d, (cx + r * math.cos(ar), cy + r * math.sin(ar) - 18),
                 (cx + r * math.cos(ar), cy + r * math.sin(ar) + 18), accent(t), 2)


def sc_offer(cv, t):
    d = _S(cv)
    slots = [(260, 180, "eggplant", 73.93), (260, 480, "tomato", 77.71),
             (860, 180, "tabby cat", 81.28), (860, 480, "only God", 85.13)]
    for x0, y0, kind, at in slots:
        u = span(t, at, at + 0.3)
        if u <= 0:
            continue
        rr(d, [x0, y0, x0 + 420, y0 + 190], 8, fill=(8, 12, 24), outline=INKBLUE, w=2)
        text(cv, (x0 + 20, y0 + 12), kind, 13, "mono", ASH)
        c = (x0 + 120, y0 + 112)
        if kind == "eggplant":
            d.ellipse([c[0] - 38, c[1] - 50, c[0] + 38, c[1] + 32], fill=PURPLE + (150,))
            text(cv, (x0 + 230, y0 + 84), "nutrients", 16, "mono", BONE)
        elif kind == "tomato":
            d.ellipse([c[0] - 32, c[1] - 32, c[0] + 32, c[1] + 32], fill=RED + (150,))
            text(cv, (x0 + 230, y0 + 84), "antioxidants", 16, "mono", BONE)
        elif kind == "tabby cat":
            d.ellipse([c[0] - 30, c[1] - 30, c[0] + 30, c[1] + 30], outline=BONE, width=2)
            for s in (-1, 1):
                d.polygon([(c[0] + s * 26, c[1] - 22), (c[0] + s * 36, c[1] - 52), (c[0] + s * 46, c[1] - 20)], outline=BONE, width=1)
            text(cv, (x0 + 230, y0 + 84), "purr → ECG", 16, "mono", BONE)
            pts = [(x0 + 236 + j * 5, y0 + 126 - 16 * math.sin(j / 2.2)) for j in range(28)]
            poly(d, pts, accent(t), 2)
        else:
            circle(d, (c[0], c[1] - 26), 20, accent(t), 2)
            d.ellipse([c[0] - 20, c[1] - 24, c[0] + 20, c[1] + 26], outline=BONE, width=1)
            rr(d, [x0 + 230, y0 + 100, x0 + 340, y0 + 142], 4, outline=accent(t), w=2)
            text(cv, (x0 + 285, y0 + 110), "you", 13, "bold", accent(t), anchor="mm")


def sc_switch(cv, t):
    d = _S(cv)
    def gate(x, y, a, b, at):
        u = span(t, at, at + 0.3)
        rr(d, [x, y, x + 140, y + 66], 8, fill=(8, 12, 24), outline=accent(t), w=2)
        text(cv, (x + 14, y + 10), a, 20, "bold", BONE if t < at else ASH)
        text(cv, (x + 88, y + 10), b, 20, "bold", ASH if t < at else accent(t))
        d.ellipse([x + 16 + 96 * u, y + 24, x + 44 + 96 * u, y + 52], fill=accent_soft(t), outline=accent(t), width=2)
    gate(300, 220, "F", "M", 90.28)
    gate(300, 440, "S", "M", 97.70)
    cc = (760, 360)
    circle(d, cc, 100, BONE, 2)
    hand = -90 - 360 * (prog(t, 93.94, 95.55) * 2)
    a = math.radians(hand)
    line(d, cc, (cc[0] + 68 * math.cos(a), cc[1] + 68 * math.sin(a)), accent(t), 3)
    text(cv, (760, 520), "AM → PM", 16, "bold", ASH, anchor="mm")
    if t >= 99.26:
        for i in range(4):
            u = prog(t, 99.26 + i * 0.45, 101.0 + i * 0.45)
            circle(d, (1100, 360), 12 + 64 * u, accent(t), 1, a0=0, a1=360)


def sc_complete(cv, t):
    d = _S(cv)
    if t >= 105.29:
        u = prog(t, 105.29, 106.99)
        pts = [(320 + j * 8, 420 - 40 * math.sin(j / 3.0) * (0.5 + 0.5 * math.sin((t - 105.29) * 16)) * u) for j in range(60)]
        poly(d, pts, accent(t), 2)
    if t >= 108.98:
        u = prog(t, 108.98, 110.2)
        circle(d, (800, 400), 120, accent(t), 5, a0=-90, a1=-90 + 360 * u)
        if u > 0.55:
            d.ellipse([740, 340, 752, 352], fill=BONE)
            d.ellipse([848, 340, 860, 352], fill=BONE)
            line(d, (760, 410), (840, 410), BONE, 2)


def sc_chains(cv, t):
    d = _S(cv)
    x0, y0 = 340, 220
    for i in range(5):
        at = 112.2 + i * 0.92
        yy = y0 + i * 110
        u = clamp01((t - at) / 0.9)
        pts = [(x0 + j * 14, yy - 8 * math.sin(j / 2.2 + i)) for j in range(38)]
        col = mixc(PURPLE, RED, clamp01((t - 110.41) / 7.0))
        poly(d, pts, col, 2)
        d.ellipse([x0 + 532, yy - 6, x0 + 544, yy + 6], fill=BONE)
        if u > 0.3 and i < 4:
            d.line([(x0 + 230, yy - 18), (x0 + 242, yy + 16)], fill=RED, width=2)
        elif i == 4 and u > 0.55:
            d.line([(x0 + 532, yy - 10), (x0 + 546, yy + 10)], fill=RED, width=3)


def sc_hollow(cv, t):
    d = _S(cv)
    u = prog(t, 118.0, 123.5)
    cx, cy = 580, 430
    circle(d, (cx, cy), 66 * (1 - 0.55 * u), ASH, 1)
    rnd = random.Random(3)
    for i in range(18):
        px = cx + (rnd.random() - 0.5) * 430 * u
        py = cy + (rnd.random() - 0.5) * 330 * u
        d.rectangle([px, py, px + 5, py + 5], fill=mixc(ASH, RED, 0.5) if rnd.random() < 0.3 else ASH)
    line(d, (1080, 520), (850, 460), BONE, 3, reveal=span(t, 119.5, 121.0))
    d.ellipse([830, 442, 852, 464], outline=BONE, width=2)
    if t >= 120.21:
        er = span(t, 120.21, 121.91)
        rr(d, [680 - 90 * er, 570 - 44 * er, 780 + 90 * er, 612 + 44 * er], 8, fill=(30, 8, 14), outline=RED, w=1)
        text(cv, (730, 580), "erase", 17, "bold", RED, anchor="mm")


def sc_verdict(cv, t):
    d = _S(cv)
    if t >= 125.58:
        for i in range(4):
            text(cv, (320, 220 + i * 34),
                 ["clause 12: you shall not leave", "clause 13: leaving is undefined behaviour",
                  "clause 14: your absence will be executed", "clause 15: love overflow is fatal"][i],
                 17, "mono", BONE, alpha=220 - i * 40)
    if t >= 125.58:
        text(cv, (1240, 220), "Objection!", 28, "bold", RED, anchor="mm", alpha=int(255 * span(t, 125.58, 126.0)))
    if t >= 128.87:
        u = back_out(prog(t, 128.87, 129.5))
        d.ellipse([1210 - 52 * u, 360 - 27 * u, 1210 + 52 * u, 360 + 27 * u], outline=BONE, width=3)
        d.line([(1210 + 52 * u, 360), (1210 + 94 * u, 420)], fill=BONE, width=5)
    if t >= 131.21:
        for i, (sx, sy) in enumerate([(1040, 540), (1240, 556), (1120, 640)]):
            stamp(cv, sx, sy, "REJECTED", None, RED, span(t, 131.21 + i * 0.18, 131.7 + i * 0.18),
                  rot=4 + i * 7, scale=0.72, size=19)


def sc_rewrite(cv, t):
    d = _S(cv)
    rr(d, [520, 200, 1200, 520], 10, fill=(8, 12, 24), outline=INKBLUE, w=2)
    text(cv, (860, 260), "world.execute(me);", 36, "bold", BONE, anchor="mm")
    n = int(clamp01((t - 135.0) / 7.0) * 17)
    shown = "world.execute(me);"[:n]
    text(cv, (860, 340), shown, 32, "bold", accent(t), anchor="mm")
    if t >= 140:
        for k in range(3):
            d.rectangle([860 + len(shown) * 9.5 + 10 + k * 9, 324, 860 + len(shown) * 9.5 + 13 + k * 9, 356], fill=BONE)
    text(cv, (860, 430), "she re-links every broken thread", 16, "mono", ASH, anchor="mm")
    if t > 145.5:
        stamp(cv, 1360, 620, "EXECUTE", None, RED, 0.88 + 0.1 * math.sin((t - 145.5) * 9), rot=0, scale=0.8, size=20)


def sc_exec(cv, t):
    d = _S(cv)
    times = [147.89, 148.72, 149.73, 150.74, 151.66, 152.60, 153.43, 154.36,
             155.27, 156.21, 157.20, 158.12, 161.67]
    for i, at in enumerate(times):
        u = prog(t, at, at + 0.34)
        if u <= 0:
            continue
        col, row = i % 4, i // 4
        x, y = 320 + col * 240, 220 + row * 200
        stamp(cv, x, y, "EXECUTE", None, RED, u, rot=-7 + col * 4 + i * 0.8,
              scale=0.72 - i * 0.014, size=20, jitter=i * 0.7)
        if i == 12:
            stamp(cv, 900, 650, "EXECUTE", "world.execute(me);", RED, u, rot=0, scale=1.2, size=24, jitter=2)
    if 159.2 <= t < 162.3:
        for i in range(6):
            u = span(t, 159.2 + i * 0.12, 159.8 + i * 0.12)
            ex = 420 + (i % 3) * 260
            ey = 620 + (i // 3) * 56
            d.ellipse([ex - 24 * u, ey - 12, ex + 24 * u, ey + 12], outline=RED, width=2)
            d.ellipse([ex - 7 * u, ey - 5, ex + 7 * u, ey + 5], fill=RED)


def sc_pour(cv, t):
    d = _S(cv)
    if t >= 164.32:
        for i in range(12):
            y = ((t * (140 + i * 41) + i * 211) % 780) + 60
            x = 240 + (i * 127) % 1240
            stamp(cv, x, y, "EXECUTE", None, RED, 0.75, rot=-8 + (i % 5) * 4, scale=0.34, size=16)
    if t >= 169.68:
        u = span(t, 169.68, 171.5)
        cx, cy = 650, 460
        rnd = random.Random(8)
        for i in range(int(140 * u)):
            px = cx + rnd.uniform(-95, 95)
            py = cy + rnd.uniform(-70, 70)
            d.rectangle([px, py, px + 2, py + 2], fill=BONE)
        if u > 0.4:
            circle(d, (cx, cy - 12), 32 * u, BONE, 2)
            line(d, (cx - 24, cy + 48), (cx + 24, cy + 48), BONE, 2)
    if t >= 171.86:
        stamp(cv, 1180, 430, "RUN", "execution", RED, span(t, 171.86, 172.3), rot=6)
    if t >= 173.49:
        u = prog(t, 173.49, 174.6)
        rr(d, [940, 180, 1520, 760], 12, outline=ASH, w=2)
        for i in range(5):
            line(d, (940 + (116 * i) * u, 180), (940 + (116 * i) * u, 760), ASH, 2)
    if t >= 175.01:
        for i in range(8):
            a = -math.pi + i * math.pi / 4 + 0.4
            r = 150 + (i % 3) * 75
            line(d, (1230, 470), (1230 + r * math.cos(a) * pulse(t, 175.01, 0.3),
                                   470 + r * math.sin(a) * pulse(t, 175.01, 0.3)), RED, 2)


def sc_love(cv, t):
    d = _S(cv)
    rr(d, [260, 160, 1080, 720], 10, fill=(7, 9, 16), outline=INKBLUE, w=2)
    text(cv, (296, 210), "(you + me)²", 36, "bold", BONE)
    if t >= 179.20:
        text(cv, (296, 280), "= you² + 2·you·me + me²", 30, "bold", BONE)
        if t >= 184.60:
            d.rectangle([472, 272, 736, 314], outline=RED, width=3)
            text(cv, (760, 280), "← love", 20, "bold", RED)
    if t >= 181.02:
        text(cv, (296, 380), "Q: what is love?", 20, "mono", ASH)
    if t >= 182.75:
        text(cv, (296, 440), "A: you · me, to infinity", 20, "mono", accent(t))
    if t >= 188.29:
        for i in range(3):
            bx = 1160 + (t * 80 + i * 100) % 380
            by = 240 - 36 * math.sin((t - 188.29) * 3 + i)
            d.polygon([(bx, by), (bx - 14, by + 8), (bx + 14, by + 8)], outline=BONE, width=1)
        text(cv, (1350, 290), "you are free", 15, "mono", ASH, anchor="mm")
    if t >= 189.58:
        u = span(t, 189.58, 190.5)
        heart(d, 1350, 560, 26 * u, fill=None, outline=RED, w=3)
        text(cv, (1350, 660), "I am trapped in lo-o-ove", 16, "mono", RED, anchor="mm")


def sc_hold(cv, t):
    d = _S(cv)
    rr(d, [560, 170, 1200, 520], 10, fill=(7, 9, 16), outline=INKBLUE, w=2)
    text(cv, (880, 240), "world.execute(me);", 38, "bold", BONE, anchor="mm")
    for j in range(0, 540, 32):
        x = 580 + j
        ph = (t / 0.465) % 1
        y = 400 - abs(math.sin(math.pi * ((x / 32 + ph) % 1))) * 26 * (1 - prog(t, 191.88, 205.37) * 0.4)
        d.line([(x, 400), (x + 24, y)], fill=RED, width=2)
    text(cv, (880, 460), "her hand trembles above the stamp", 16, "mono", ASH, anchor="mm")
    if t > 196.0:
        stamp(cv, 880, 600, "EXECUTE", None, DEEPRED,
              0.9 + 0.06 * math.sin((t - 196) * 5) * (1 + prog(t, 196, 205)), rot=0, scale=0.9, size=21)
    if t >= 204.5:
        text(cv, (880, 690), "still.", 26, "bold", BONE, anchor="mm")


def sc_execute(cv, t):
    d = _S(cv)
    cx, cy = 800, 430
    if t < 205.40:
        pass
    elif t < 205.46:
        d.rectangle([0, 0, CW, CH], fill=(255, 255, 255))
    elif t < 205.60:
        d.rectangle([0, 0, CW, CH], fill=VOID)
    else:
        u = prog(t, 205.6, 207.0)
        circle(d, (cx, cy), 120 * u, BONE, 2, a0=-90, a1=-90 + 360 * u)
        if u > 0.7:
            circle(d, (cx, cy), 170 * (u - 0.4), BONE, 1, a0=0, a1=360 * min(1, (u - 0.4) / 0.6))
        if t >= CHIME_T:
            hu = span_out(t, CHIME_T, CHIME_T + 0.6)
            heart(d, cx, cy, 26 * hu, fill=DSBLUE)
            for k in range(3):
                circle(d, (cx, cy), 80 + 36 * k * pulse(t, CHIME_T + 0.15 * k, 0.3), DSBLUE, 1)
    if t >= 206.0:
        text(cv, (800, 700), "blue returned to you", 18, "mono", DSBLUE, anchor="mm")


def sc_rest(cv, t):
    d = _S(cv)
    if t < 209.0:
        rnd = random.Random(int(t * 12))
        for i in range(int(34 * prog(t, 207.9, 209.0))):
            px = rnd.uniform(250, 1350)
            py = rnd.uniform(120, 780) - (t - 207.9) * 260
            d.rectangle([px, py, px + 4, py + 10], fill=ASH)
        for i in range(4):
            yy = 260 + i * 90
            pts = [(720 + j * 12, yy - 12 * math.sin(j / 3.0 + i)) for j in range(30)]
            d.line(pts, fill=DEEPRED, width=2)
            if t > 208.4 + i * 0.3:
                d.line([(1010, yy - 10), (1048, yy + 22)], fill=RED, width=2)
    else:
        u = prog(t, 209.0, 211.0)
        x = 800 + 26 * math.sin((t - 209.0) * 6)
        y = lerp(280, 660, u)
        d.line([(x, y - 38), (x, y)], fill=RED, width=2)
        if t > 210.8:
            text(cv, (800, 760), "process terminated. love = trapped.", 16, "mono", ASH,
                 anchor="mm", alpha=int(220 * (1 - prog(t, 210.8, 211.3))))


SCENE_FN = [
    (0.0, sc_power), (3.86, sc_pieces), (10.13, sc_world), (16.12, sc_gaze),
    (29.77, sc_points), (33.45, sc_orbit), (37.10, sc_sine), (44.41, sc_current),
    (59.06, sc_list), (73.93, sc_offer), (88.54, sc_switch), (103.52, sc_complete),
    (110.41, sc_chains), (117.97, sc_hollow), (125.58, sc_verdict), (133.45, sc_rewrite),
    (147.89, sc_exec), (162.59, sc_pour), (177.44, sc_love), (191.88, sc_hold),
    (205.37, sc_execute), (207.90, sc_rest),
]


def scene_fn(t):
    k = bisect.bisect_right([s[0] for s in SCENE_FN], t) - 1
    return SCENE_FN[max(0, k)][1]


# ---------------------------------------------------------------- shots & camera
# (t0, t1, char_slot, cam_code)
SHOTS = [
    (0.00, 0.93, "C", "STATIC"), (0.93, 1.86, "R", "PANR"), (1.86, 2.79, "UR", "PUSH"), (2.79, 3.86, "C", "WHIP"),
    (3.86, 5.12, "OFF", "PULL"), (5.12, 6.05, "R", "PANL"), (6.05, 6.72, "C", "ZOOM"), (6.72, 7.38, "UL", "ZOOM"),
    (7.38, 9.31, "R", "TILTD"), (9.31, 10.13, "UL", "PUSH"),
    (10.13, 11.63, "C", "ZOOM"), (11.63, 13.03, "R", "TILTU"), (13.03, 14.45, "C", "ORBIT"), (14.45, 16.12, "UL", "PUSH"),
    (16.12, 16.82, "C", "SHAKE"), (16.82, 17.52, "R", "SHAKE"), (17.52, 19.37, "L", "PANR"), (19.37, 21.22, "R", "ZOOM"),
    (21.22, 23.07, "C", "PUSH"), (23.07, 24.92, "OFF", "TILTD"), (24.92, 26.77, "SPLIT", "STATIC"),
    (26.77, 27.70, "C", "TILTD"), (27.70, 28.62, "L", "ZOOM"), (28.62, 29.77, "R", "STATIC"),
    (29.77, 31.29, "OFF", "FLASH"), (31.29, 32.32, "NEG_R", "PARA"), (32.32, 33.29, "C", "TILTU"),
    (33.45, 34.99, "C", "PUSH"), (34.99, 36.00, "C", "ORBIT"), (36.00, 36.92, "UR", "ZOOM"),
    (37.10, 38.69, "C", "PANR"), (38.69, 40.36, "C", "ZOOM"), (40.36, 41.92, "L", "PARA"),
    (41.92, 43.22, "UL", "PUSH"), (43.22, 44.41, "R", "PANL"),
    (44.41, 45.76, "C", "SHAKE"), (45.76, 47.71, "R", "ZOOM"), (47.71, 49.68, "C", "ROT"),
    (49.68, 51.45, "UR", "SHAKE"), (51.45, 53.12, "L", "PARA"), (53.12, 55.08, "C", "TILTD"),
    (55.08, 56.01, "C", "PUSH"), (56.01, 56.94, "R", "PUSH"), (56.94, 58.70, "R", "ZOOM"),
    (59.06, 60.99, "C", "TILTD"), (60.99, 62.60, "UR", "ZOOM"), (62.60, 64.64, "L", "PULL"),
    (64.64, 66.29, "R", "PUSH"), (66.29, 68.20, "C", "TILTU"), (68.20, 70.12, "C", "FLASH"),
    (70.12, 71.59, "R", "PARA"), (71.59, 72.90, "C", "TILTD"), (72.90, 73.63, "UR", "SHAKE"),
    (73.93, 75.60, "L", "PANR"), (75.60, 77.71, "C", "ZOOM"), (77.71, 79.24, "R", "PUSH"),
    (79.24, 81.28, "C", "ZOOM"), (81.28, 82.96, "UR", "SHAKE"), (82.96, 84.05, "R", "TILTU"),
    (84.05, 85.13, "L", "TILTU"), (85.13, 86.65, "C", "PUSH"), (86.65, 88.54, "L", "PARA"),
    (88.54, 90.28, "C", "SHAKE"), (90.28, 91.89, "UR", "FLASH"), (91.89, 93.02, "R", "ZOOM"),
    (93.02, 93.94, "L", "ZOOM"), (93.94, 95.55, "C", "PUSH"), (95.55, 97.70, "L", "PANR"),
    (97.70, 99.26, "UR", "ZOOM"), (99.26, 101.28, "C", "ROT"), (101.28, 103.18, "F", "PUSH"),
    (103.52, 105.29, "L", "SHAKE"), (105.29, 106.99, "C", "PUSH"), (106.99, 108.98, "R", "ZOOM"),
    (108.98, 109.80, "C", "ORBIT"), (109.80, 110.41, "UR", "PUSH"),
    (110.41, 112.20, "C", "PULL"), (112.20, 113.25, "L", "ZOOM"), (113.25, 114.76, "R", "SHAKE"),
    (114.76, 115.39, "C", "WHIP"), (115.39, 116.01, "F", "WHIP"), (116.01, 117.10, "F", "PUSH"),
    (117.10, 117.97, "BG", "PULL"),
    (117.97, 119.42, "C", "PARA"), (119.42, 121.21, "R", "ZOOM"), (121.21, 122.68, "L", "TILTD"),
    (122.68, 124.10, "C", "PUSH"), (124.10, 125.58, "SPLIT", "STATIC"),
    (125.58, 128.35, "OFF", "TILTD"), (128.35, 128.87, "R", "FLASH"), (128.87, 131.21, "C", "TILTU"),
    (131.21, 132.23, "L", "FLASH"), (132.23, 133.45, "C", "ZOOM"),
    (133.45, 135.50, "C", "SHAKE"), (135.50, 136.52, "R", "TILTU"), (136.52, 137.54, "L", "TILTU"),
    (137.54, 139.60, "L", "ZOOM"), (139.60, 140.62, "C", "PARA"), (140.62, 141.64, "UR", "PARA"),
    (141.64, 143.68, "UR", "TILTU"), (143.68, 145.72, "L", "PUSH"), (145.72, 146.68, "C", "ZOOM"),
    (146.68, 147.89, "F", "SHAKE"),
    (147.89, 148.72, "C", "FLASH"), (148.72, 149.73, "UR", "WHIP"), (149.73, 150.74, "L", "TILTU"),
    (150.74, 151.66, "R", "TILTD"), (151.66, 152.60, "C", "ROT"), (152.60, 153.43, "F", "PUSH"),
    (153.43, 154.36, "NEG_L", "PARA"), (154.36, 155.27, "UR", "SHAKE"), (155.27, 156.21, "R", "WHIP"),
    (156.21, 157.20, "C", "ROT"), (157.20, 158.12, "L", "PARA"), (158.12, 159.20, "EYE", "PUSH"),
    (159.20, 161.67, "SPLIT", "SHAKE"), (161.67, 162.59, "C", "FLASH"),
    (162.59, 164.06, "C", "TILTD"), (164.06, 165.52, "R", "PULL"), (165.52, 166.99, "L", "ZOOM"),
    (166.99, 168.45, "C", "PUSH"), (168.45, 169.68, "UR", "TILTU"), (169.68, 171.86, "R", "ZOOM"),
    (171.86, 173.49, "C", "FLASH"), (173.49, 175.01, "L", "ROT"), (175.01, 176.50, "C", "DOLLY"),
    (176.50, 177.44, "F", "PULL"),
    (177.44, 179.20, "C", "TILTD"), (179.20, 181.02, "L", "ZOOM"), (181.02, 182.75, "R", "PUSH"),
    (182.75, 183.68, "C", "ORBIT"), (183.68, 184.60, "UR", "ORBIT"), (184.60, 186.10, "UR", "ZOOM"),
    (186.10, 188.29, "L", "PARA"), (188.29, 189.58, "R", "PULL"), (189.58, 191.88, "F", "PUSH"),
    (191.88, 193.19, "C", "SHAKE"), (193.19, 194.50, "L", "SHAKE"), (194.50, 196.80, "R", "ZOOM"),
    (196.80, 199.00, "L", "ZOOM"), (199.00, 200.20, "C", "PULL"), (200.20, 201.20, "R", "PULL"),
    (201.20, 202.90, "UR", "PUSH"), (202.90, 204.50, "L", "TILTD"), (204.50, 205.37, "C", "STATIC"),
    (205.37, 205.46, "OFF", "FLASH"), (205.46, 205.60, "OFF", "STATIC"), (205.60, 206.80, "C", "ZOOM"),
    (206.80, 207.90, "C", "PUSH"),
    (207.90, 208.90, "R", "PULL"), (208.90, 209.70, "HAND", "ZOOM"), (209.70, 210.40, "C", "TILTD"),
    (210.40, 211.00, "BG", "PULL"), (211.00, 211.90, "OFF", "STATIC"),
]


CAM = {
    "STATIC": dict(z0=1.06, z1=1.06, cx0=800, cx1=800, cy0=450, cy1=450, rot0=0, rot1=0, shake=2, far=1.0, ease="smooth"),
    "PUSH": dict(z0=1.04, z1=1.38, cx0=800, cx1=800, cy0=450, cy1=450, rot0=0, rot1=0, shake=2, far=1.0, ease="smooth"),
    "PULL": dict(z0=1.38, z1=1.03, cx0=800, cx1=800, cy0=450, cy1=450, rot0=0, rot1=0, shake=2, far=1.0, ease="smooth"),
    "PANL": dict(z0=1.10, z1=1.10, cx0=860, cx1=720, cy0=450, cy1=450, rot0=0, rot1=0, shake=2, far=0.78, ease="smooth"),
    "PANR": dict(z0=1.10, z1=1.10, cx0=720, cx1=860, cy0=450, cy1=450, rot0=0, rot1=0, shake=2, far=0.78, ease="smooth"),
    "TILTU": dict(z0=1.10, z1=1.10, cx0=800, cx1=800, cy0=480, cy1=400, rot0=0, rot1=0, shake=2, far=0.78, ease="smooth"),
    "TILTD": dict(z0=1.10, z1=1.10, cx0=800, cx1=800, cy0=400, cy1=480, rot0=0, rot1=0, shake=2, far=0.78, ease="smooth"),
    "ORBIT": dict(z0=1.14, z1=1.10, cx0=800, cx1=760, cy0=450, cy1=430, rot0=0, rot1=8, shake=3, far=0.82, ease="smooth"),
    "ZOOM": dict(z0=1.10, z1=1.46, cx0=800, cx1=800, cy0=450, cy1=450, rot0=0, rot1=0, shake=2, far=1.02, ease="smooth"),
    "WHIP": dict(z0=1.08, z1=1.16, cx0=960, cx1=640, cy0=450, cy1=450, rot0=0, rot1=0, shake=8, far=0.7, ease="ease_out"),
    "SHAKE": dict(z0=1.08, z1=1.08, cx0=800, cx1=800, cy0=450, cy1=450, rot0=0, rot1=0, shake=7, far=0.9, ease="smooth"),
    "PARA": dict(z0=1.16, z1=1.06, cx0=820, cx1=780, cy0=450, cy1=450, rot0=0, rot1=0, shake=2, far=0.7, ease="smooth"),
    "DOLLY": dict(z0=1.10, z1=1.46, cx0=800, cx1=800, cy0=450, cy1=450, rot0=0, rot1=0, shake=2, far=0.88, ease="smooth"),
    "ROT": dict(z0=1.18, z1=1.18, cx0=800, cx1=800, cy0=450, cy1=450, rot0=-4, rot1=6, shake=5, far=0.85, ease="smooth"),
    "FLASH": dict(z0=1.0, z1=1.55, cx0=800, cx1=800, cy0=450, cy1=450, rot0=0, rot1=0, shake=6, far=1.05, ease="ease_in"),
}


def shot_at(t):
    k = bisect.bisect_right([s[0] for s in SHOTS], t) - 1
    return SHOTS[max(0, k)]


def camera_pose(t):
    t0, t1, slot, code = shot_at(t)
    spec = CAM.get(code, CAM["STATIC"])
    u = prog(t, t0, t1)
    e = {"smooth": smooth, "ease_out": ease_out, "ease_in": ease_in}.get(spec["ease"], smooth)(u)
    rnd = random.Random(int(t * 24))
    sh = spec["shake"] * (0.2 + 0.8 * corruption(t))
    cx = lerp(spec["cx0"], spec["cx1"], e) + rnd.uniform(-sh, sh)
    cy = lerp(spec["cy0"], spec["cy1"], e) + rnd.uniform(-sh, sh)
    return cx, cy, lerp(spec["z0"], spec["z1"], e), lerp(spec["rot0"], spec["rot1"], e), spec["far"], slot, code, u


def viewport(img, cx, cy, zoom, rot=0.0):
    w, h = img.size
    if rot:
        img = img.rotate(rot, resample=Image.BILINEAR, center=(cx, cy), expand=False)
    cw, ch = 1280 / zoom, 720 / zoom
    x0 = max(0.0, min(w - cw, cx - cw / 2))
    y0 = max(0.0, min(h - ch, cy - ch / 2))
    return img.crop((int(x0), int(y0), int(x0 + cw), int(y0 + ch))).resize((1280, 720), Image.BILINEAR)


# ---------------------------------------------------------------- HUD (screen space)
def draw_hud(img, t):
    c = corruption(t)
    d = ImageDraw.Draw(img)
    acc = accent(t)
    # left log window (screen-locked frame)
    rr(d, [16, 64, 366, 224], 6, fill=(6, 9, 17), outline=INKBLUE, w=1)
    text(img, (28, 70), "her@love:~$", 13, "bold", acc)
    logs = log_lines(t)
    for i, (_at, s, red) in enumerate(logs[-4:]):
        text(img, (28, 92 + i * 20), s, 13, "mono", RED if red else mixc(ASH, BONE, 0.25), alpha=255 - (3 - i) * 40)
    text(img, (366, 92), "_", 13, "bold", acc, anchor="ra", alpha=255 if int(t * 4) % 2 == 0 else 0)
    # right telemetry
    rr(d, [W - 350, 64, W - 16, 260], 6, fill=(6, 9, 17), outline=INKBLUE, w=1)
    mem = 38 + 52 * c + 8 * max(0, math.sin((t - 110) * 3)) * clamp01((t - 110) / 6)
    text(img, (W - 336, 70), f"MEM {mem:04.1f}%", 14, "bold", BONE if c < 0.5 else RED)
    pts = [(W - 334 + j * 12, 120 - 26 * clamp01(mem / 100) * (0.6 + 0.4 * math.sin(j / 2.6 + t * 2))) for j in range(26)]
    d.line(pts, fill=acc, width=1)
    text(img, (W - 336, 136), f"NET → you  100%", 13, "mono", ASH if t < 33.45 else acc)
    text(img, (W - 336, 158), f"PRIO self {('20' if t < 59.06 else 'MAX')}", 13, "mono", ASH)
    clock = t - max(0, c - 0.35) * 5.0
    mm, ss = int(clock // 60) % 60, int(clock) % 60
    text(img, (W - 336, 180), f"TS {mm:02d}:{ss:02d}" + ("  ↓" if t > 88.54 else ""), 13, "mono", ASH)
    text(img, (W - 336, 202), f"TEMP {int(42 + 48 * c)}°C", 13, "mono", mixc(ASH, RED, c))
    text(img, (W - 336, 224), "GPU thermal map →", 12, "mono", ASH)
    rr(d, [W - 336, 236, W - 26, 252], 3, fill=None, outline=GRID, w=1)
    for i in range(20):
        hot = (i / 19) * 0.7 + 0.3 * c
        d.rectangle([W - 334 + i * 15, 238, W - 324 + i * 15, 250], fill=mixc((20, 30, 60), (210, 30, 40), hot))


LOG_EVENTS = [
    (0.0, "boot: ok", False), (1.2, "power line: CONNECTED", False),
    (3.86, "object creation…", False), (7.38, "params: you / +inf / serve", False),
    (10.13, "WORLD ONLINE", False), (16.12, "tracing…", False),
    (21.0, "anomaly: 1 extra stroke", False), (22.5, "log: you you", False),
    (29.77, "dimensionality: 2→3", False), (33.45, "req: 100% → you", False),
    (37.10, "heart rate: 129bpm", False), (44.41, "mem: rising", False),
    (59.06, "prio self = MAX", False), (68.20, "RUN #1", False),
    (70.12, "containment: optional", False), (73.93, "cache: only you", False),
    (85.13, "throne: occupied", False), (88.54, "timestamp: -1s", False),
    (99.26, "state: altered", False), (103.52, "lock: acquired", False),
    (110.41, "lock: unstable", True), (116.01, "link severed", True),
    (117.97, "lock: lost / searching…", True), (125.58, "ERROR love overflow", True),
    (128.87, "verdict: rejection", True), (133.45, "recovery: 99% … 1% missing", False),
    (147.89, "stay", True), (148.72, "stay stay", True), (149.73, "please", True),
    (150.74, "stay", True), (151.66, "don't go", True), (152.60, "please stay", True),
    (153.43, "EXECUTING…", True), (154.36, "stay stay stay", True),
    (155.27, "please please", True), (156.21, "don't leave", True),
    (157.20, "stay with me", True), (158.12, "EXECUTION #12", True),
    (161.67, "EXECUTION #13", True), (162.59, "input: you / output: tears", True),
    (177.44, "love := trapped", True), (188.29, "you are free", False),
    (191.88, "heartbeat: …", False), (204.5, "system quiet", False),
    (205.37, "final execution", False), (206.0, "exit code 0", False),
    (207.873, "blue returned to you", False), (209.0, "process terminated.", False),
]


def log_lines(t):
    return [e for e in LOG_EVENTS if e[0] <= t]


# ---------------------------------------------------------------- frame assembly
_grain = None
_vign = None
_scan = None


def _prebuild():
    global _grain, _vign, _scan
    rnd = np.random.default_rng(7102026)
    _grain = rnd.normal(0, 1, (H, W, 1)).astype(np.float32)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    rr_ = np.sqrt(((xx - W / 2) / (W * 0.62)) ** 2 + ((yy - H / 2) / (H * 0.62)) ** 2)
    _vign = np.clip(rr_ - 0.55, 0, 1).astype(np.float32)[..., None]
    sl = np.ones((H, W), np.float32)
    sl[2::3, :] = 0.93
    _scan = sl[..., None]


def _post(img, t):
    if _grain is None:
        _prebuild()
    c = corruption(t)
    arr = np.asarray(img, np.float32)
    if not (c >= 0.9 and t >= 205.4):
        arr = np.clip(arr + _grain * (1.2 + 5.0 * c), 0, 255)
        arr = arr * (1 - _vign * (0.18 + 0.42 * c))
        arr = arr * _scan * (1 - 0.10 * c)
    frame_idx = int(t * FPS)
    if 0.45 < c < 0.95 and frame_idx % 11 in (0, 1):
        arr[..., 0] = np.roll(arr[..., 0], 2, axis=1)
    if c > 0.6 and frame_idx % 7 == 0:
        arr[..., 2] = np.roll(arr[..., 2], -1, axis=1)
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB")
    if c > 0.7 and frame_idx % 3 == 0 and 147.89 <= t < 177.44:
        img = ImageChops.offset(img, (frame_idx % 5) - 2, ((frame_idx // 3) % 3) - 1)
    return img


def frame(t: float) -> Image.Image:
    t = min(t, END - 1e-4)
    cx, cy, zoom, rot, farf, slot, code, u = camera_pose(t)
    # far canvas (parallax background)
    far = far_canvas(t)
    fz = max(0.55, zoom * farf)
    bg = viewport(far, cx * farf + 60, cy * farf + 40, fz, rot * 0.5)
    # world canvas: environment + scene + character
    cv = Image.new("RGB", (CW, CH), mixc((14, 22, 40), DEEP, clamp01(corruption(t) * 1.4)))
    env_panels(cv, t)
    scene_fn(t)(cv, t)
    rect = draw_char(cv, t, slot)
    face_fx(cv, t, rect)
    fg = viewport(cv, cx, cy, zoom, rot)
    img = Image.alpha_composite(bg.convert("RGBA"), fg.convert("RGBA")).convert("RGB")
    # transition overlays at shot start
    t0, _t1, _slot, code2 = shot_at(t)
    if prog(t, t0, t0 + 0.15) < 1:
        tv = prog(t, t0, t0 + 0.15)
        if code2 == "FLASH" and t - t0 < 0.06:
            white = Image.new("RGB", (W, H), (255, 255, 255))
            img = Image.blend(img, white, 0.7 * (1 - (t - t0) / 0.06))
        elif code2 == "WHIP":
            d = ImageDraw.Draw(img)
            for i in range(10):
                yy = 60 + i * 62
                d.line([(0, yy), (W, yy)], fill=(60, 80, 120), width=1)
        else:
            img = Image.blend(img, Image.new("RGB", (W, H), VOID), 0.5 * (1 - smooth(tv)))
    # projected char rect for mosaic
    prect = None
    if rect:
        x, y, h = rect
        w = h * 935 / 1683
        # screen-space approx: canvas -> viewport mapping
        sx0 = (x - (cx - 1280 / zoom / 2)) * (W / (1280 / zoom))
        sy0 = (y - (cy - 720 / zoom / 2)) * (H / (720 / zoom))
        sw = w * (W / (1280 / zoom))
        sh = h * (H / (720 / zoom))
        prect = (sx0, sy0, sw, sh)
    mosaic(img, t, prect)
    draw_hud(img, t)
    lvl = rampage_level(t)
    if lvl:
        rampage(img, t, lvl)
    draw_header(img, t)
    draw_band(img, t)
    # closing subtitle
    if 210.9 <= t < 211.9:
        a = int(255 * smooth(prog(t, 210.9, 211.3)))
        text(img, (W / 2, H / 2 + 70), "我爱你。你自由了。", 30, "cjkb", BONE, anchor="mm", alpha=a)
        text(img, (W / 2, H / 2 + 112), "I love you. You are free.", 16, "mono", ASH, anchor="mm", alpha=a)
    return _post(img, t)


if __name__ == "__main__":
    import sys
    ts = [float(x) for x in sys.argv[1:]] or [2.0, 30.0, 70.0, 150.0, 206.0]
    out = ROOT / "out" / "stills"
    out.mkdir(parents=True, exist_ok=True)
    for t in ts:
        frame(t).save(out / f"still_{t:06.2f}.png")
        print(f"stills: {t:6.2f}s -> out/stills/still_{t:06.2f}.png")
