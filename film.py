"""world.execute(me); - paper blueprint film

Original concept and renderer, written from scratch for this project.
Every frame is a pure function of song time: a drafting-paper world where the
DeepSeek whale girl writes, draws, stamps and finally executes the world she
built for "you". No chat window, no terminal - only paper, ink and her.

Word timings in data/timeline.json are the lyric alignment from
MisakaZentai/world-execute-me-dsh-pv (MIT), used solely to sync visuals to
the song. All artwork, code and scene design here are original.
"""
from __future__ import annotations

import bisect
import json
import math
import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parent
W, H, FPS = 1280, 720, 24
END = 211.9
CHIME_T = 207.873
MAIN_Y0, MAIN_Y1 = 56, 612

# palette: warm drafting paper + ink blue + DeepSeek blue + stamp red
PAPER = (246, 242, 231)
PAPER2 = (240, 235, 221)
INK = (42, 51, 77)
INK_SOFT = (70, 83, 118)
PENCIL = (125, 132, 153)
PENCIL2 = (160, 166, 184)
BLUE = (77, 107, 254)
BLUE_SOFT = (134, 154, 242)
RED = (197, 72, 64)
RED_SOFT = (214, 118, 112)
GREEN = (72, 122, 88)
PURPLE = (112, 78, 162)
ORANGE = (222, 132, 66)
GRID = (225, 220, 203)
RULED = (213, 206, 187)

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


def lerp(a: float, b: float, u: float) -> float:
    return a + (b - a) * u


def smooth(u: float) -> float:
    u = clamp01(u)
    return u * u * (3 - 2 * u)


def ease_out(u: float) -> float:
    u = clamp01(u)
    return 1 - (1 - u) ** 3


def back_out(u: float) -> float:
    u = clamp01(u)
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (u - 1) ** 3 + c1 * (u - 1) ** 2


def prog(t: float, a: float, b: float) -> float:
    return clamp01((t - a) / max(b - a, 1e-6))


def span(t: float, a: float, b: float) -> float:
    return smooth(prog(t, a, b))


def span_out(t: float, a: float, b: float) -> float:
    return ease_out(prog(t, a, b))


def pulse(t: float, at: float, half: float = 0.12) -> float:
    return math.exp(-(t - at) / half) if t >= at else 0.0


def wob(p0, p1, n: int = 18, seed: int = 0, amp: float = 1.2):
    rnd = random.Random(seed)
    pts = []
    for i in range(n + 1):
        u = i / n
        x = lerp(p0[0], p1[0], u) + rnd.uniform(-amp, amp)
        y = lerp(p0[1], p1[1], u) + rnd.uniform(-amp, amp)
        pts.append((x, y))
    return pts


# ---------------------------------------------------------------- drawing
def _reveal_points(points, reveal: float):
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


def line(d: ImageDraw.ImageDraw, p0, p1, fill=INK, w: int = 2, dash=None, reveal: float = 1.0):
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


def poly(d: ImageDraw.ImageDraw, points, fill=INK, w: int = 2, reveal: float = 1.0):
    d.line(_reveal_points(points, reveal), fill=fill, width=w)


def arc_points(c, r, a0: float, a1: float, n: int = 48):
    pts = []
    for i in range(n + 1):
        a = math.radians(lerp(a0, a1, i / n))
        pts.append((c[0] + r * math.cos(a), c[1] + r * math.sin(a)))
    return pts


def circle(d: ImageDraw.ImageDraw, c, r, outline=INK, w: int = 2, a0: float = 0, a1: float = 360, reveal: float = 1.0):
    d.line(_reveal_points(arc_points(c, r, a0, a1), reveal), fill=outline, width=w)


def rr(d: ImageDraw.ImageDraw, box, radius: int = 10, fill=None, outline=None, w: int = 2):
    d.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=w)


def _text(img: Image.Image, xy, s: str, size: int, kind: str = "mono", fill=INK,
          anchor: str = "la", alpha: int = 255, spacing: int = 0):
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    f = font(size, kind)
    ld.text(xy, s, font=f, fill=fill + ((alpha,) if len(fill) == 3 else ()), anchor=anchor, spacing=spacing)
    img.alpha_composite(layer) if img.mode == "RGBA" else img.paste(layer, (0, 0), layer)


def text(img, xy, s, size=20, kind="mono", fill=INK, anchor="la", alpha=255, spacing=0):
    _text(img, xy, s, size, kind, fill, anchor, alpha, spacing)


def text_w(img, xy, s, size=18, kind="mono", fill=INK, alpha=255):
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    ld.multiline_text(xy, s, font=font(size, kind), fill=fill + (alpha,), spacing=6)
    if img.mode == "RGBA":
        img.alpha_composite(layer)
    else:
        img.paste(layer, (0, 0), layer)


def blob(d: ImageDraw.ImageDraw, c, r, n=36, seed=0, amp=0.08):
    rnd = random.Random(seed)
    pts = []
    for i in range(n):
        a = math.radians(i * 360 / n)
        rr_ = r * (1 + rnd.uniform(-amp, amp))
        pts.append((c[0] + rr_ * math.cos(a), c[1] + rr_ * math.sin(a)))
    d.polygon(pts, fill=PAPER)


# ---------------------------------------------------------------- paper
_paper = None
_grain = None


def _build_paper():
    img = Image.new("RGB", (W, H), PAPER)
    rnd = np.random.default_rng(20261011)
    noise = rnd.normal(0, 2.2, (H, W, 1)).astype(np.float32)
    base = np.asarray(img, np.float32)
    out = np.clip(base + noise, 0, 255).astype(np.uint8)
    paper = Image.fromarray(out, "RGB")
    v = Image.new("L", (W, H), 0)
    vd = ImageDraw.Draw(v)
    vd.rectangle([0, 0, W, H], fill=0)
    vd.rectangle([26, 20, W - 26, H - 20], fill=255)
    v = v.filter(ImageFilter.GaussianBlur(38))
    paper = Image.composite(Image.new("RGB", (W, H), (239, 234, 220)), paper, v)
    return paper


def paper() -> Image.Image:
    global _paper
    if _paper is None:
        _paper = _build_paper()
    return _paper.copy()


def draw_grid(img: Image.Image):
    d = ImageDraw.Draw(img)
    for x in range(64, W, 64):
        d.line([(x, MAIN_Y0), (x, MAIN_Y1)], fill=GRID, width=1)
    for y in range(MAIN_Y0 + 64 - (MAIN_Y0 % 64), MAIN_Y1, 64):
        d.line([(0, y), (W, y)], fill=GRID, width=1)
    d.rectangle([24, MAIN_Y0 - 8, W - 24, MAIN_Y1 + 8], outline=INK_SOFT, width=1)


# ---------------------------------------------------------------- character
CHAR_DIR = ROOT / "assets" / "char"
_char_cache: dict = {}


def char_image(name: str, h: int) -> Image.Image:
    key = (name, h)
    if key not in _char_cache:
        im = Image.open(CHAR_DIR / f"{name}.png").convert("RGBA")
        w = int(im.width * h / im.height)
        im = im.resize((w, h), Image.LANCZOS)
        rgb = np.asarray(im.convert("RGB"), np.float32)
        gray = rgb.mean(2, keepdims=True)
        rgb = np.clip(rgb * 0.78 + gray * 0.22 + np.array([6, 7, 10], np.float32), 0, 255)
        im = Image.fromarray(rgb.astype(np.uint8), "RGB")
        im.putalpha(_char_cache_mask(name, h))
        _char_cache[key] = im
    return _char_cache[key]


def _char_cache_mask(name: str, h: int) -> Image.Image:
    im = Image.open(CHAR_DIR / f"{name}.png").convert("RGBA")
    w = int(im.width * h / im.height)
    return im.resize((w, h), Image.LANCZOS).getchannel("A")


def paste_char(img: Image.Image, name: str, x: float, y: float, h: int,
               alpha: float = 1.0, shadow: bool = True, scale: float = 1.0):
    im = char_image(name, h)
    w, hh = im.size
    if scale != 1.0:
        im = im.resize((int(w * scale), int(hh * scale)), Image.LANCZOS)
        w, hh = im.size
    if shadow:
        mask = im.getchannel("A").point(lambda v: int(v * 0.28 * alpha))
        sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
        sil = Image.new("RGBA", (w, hh), (41, 50, 76, 255))
        sil.putalpha(mask)
        sh.paste(sil, (int(x) + 12, int(y) + 16), sil)
        if img.mode == "RGBA":
            img.alpha_composite(sh)
        else:
            img.paste(sh, (0, 0), sh)
    if alpha < 1:
        im.putalpha(im.getchannel("A").point(lambda v: int(v * alpha)))
    if img.mode == "RGBA":
        img.alpha_composite(im, (int(x), int(y)))
    else:
        img.paste(im, (int(x), int(y)), im)


# expression timeline per scene: (t0, expression)
EXPRS = [
    (0.0, "whale-cheerful"), (1.79, "whale-starry"), (3.86, "whale-serious"),
    (10.13, "whale-starry"), (16.12, "whale-cheerful"), (29.77, "whale-starry"),
    (44.41, "whale-confused"), (51.45, "whale-shy"), (59.06, "whale-serious"),
    (68.20, "whale-frightened"), (73.93, "whale-cheerful"), (85.13, "whale-serious"),
    (88.54, "whale-confused"), (103.52, "whale-shy"), (110.41, "whale-frightened"),
    (116.01, "whale-shy"), (118.24, "whale-exasperated"), (125.58, "whale-angry"),
    (133.45, "whale-serious"), (147.89, "whale-starry"), (162.59, "whale-cheerful"),
    (173.49, "whale-frightened"), (175.01, "whale-starry"), (177.44, "whale-shy"),
    (188.29, "whale-serious"), (191.88, "whale-serious"), (205.37, "whale-starry"),
]


def expr_at(t: float) -> str:
    name = EXPRS[0][1]
    for t0, n in EXPRS:
        if t >= t0:
            name = n
    return name


def expr_pop(t: float) -> float:
    k = 1.0
    for i, (t0, _n) in enumerate(EXPRS):
        if t0 > t:
            break
        k = 1.0 + 0.035 * pulse(t, t0, 0.08)
    return min(k, 1.06)


# whale signature doodle: the girl's personal stamp
def whale_doodle(img, x: float, y: float, s: float = 1.0, fill=BLUE, alpha=255):
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    body = arc_points((x, y), 16 * s, 200, 340, 40)
    d.line(body, fill=fill + (alpha,), width=max(2, int(2.4 * s)))
    tail = [(x - 12 * s, y + 7 * s), (x - 24 * s, y + 14 * s), (x - 22 * s, y + 2 * s), (x - 12 * s, y - 7 * s)]
    d.line(tail, fill=fill + (alpha,), width=max(2, int(2.4 * s)), joint="curve")
    d.arc([x + 4 * s, y - 2 * s, x + 14 * s, y + 8 * s], 270, 330, fill=fill + (alpha,), width=max(2, int(2.4 * s)))
    for i, (dx, dy, rr_) in enumerate([(-2, -14, 2.2), (3, -20, 1.6), (8, -16, 1.9)]):
        d.ellipse([x + dx * s - rr_ * s, y + dy * s - rr_ * s, x + dx * s + rr_ * s, y + dy * s + rr_ * s],
                  fill=fill + (alpha,))
    img.alpha_composite(layer) if img.mode == "RGBA" else img.paste(layer, (0, 0), layer)


# ---------------------------------------------------------------- stamps
def stamp(img, cx: float, cy: float, s: str, sub: str = None, color=RED, u: float = 1.0,
          rot: float = -8.0, scale: float = 1.0, size: int = 23, kind: str = "bold"):
    u = clamp01(u)
    if u <= 0:
        return
    sc = back_out(u) * scale
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
    st = st.rotate(rot * (1 - clamp01((u - 0.85) / 0.15) * 0.55), resample=Image.BICUBIC, center=(w / 2 + 20, h / 2 + 20))
    layer.paste(st, (int(cx - w / 2 - 20), int(cy - h / 2 - 20)), st)
    if u >= 1:
        rnd = random.Random(int(cx * 7 + cy * 13))
        dd = ImageDraw.Draw(layer)
        for _ in range(10):
            a = rnd.uniform(0, 2 * math.pi)
            r = rnd.uniform(w / 2 - 8 * scale, w / 2 + 16 * scale)
            px, py = cx + r * math.cos(a), cy + r * math.sin(a)
            dd.ellipse([px - 2, py - 2, px + 2, py + 2], fill=color + (140,))
    if img.mode == "RGBA":
        img.alpha_composite(layer)
    else:
        img.paste(layer, (0, 0), layer)


def checkbox(img, x: float, y: float, size: int, u: float, color=INK):
    d = ImageDraw.Draw(img)
    rr(d, [x, y, x + size, y + size], 3, outline=color, w=2)
    if u > 0:
        u2 = smooth(clamp01(u))
        line(d, (x + size * 0.22, y + size * 0.52), (x + size * 0.45, y + size * 0.76), color, 3, reveal=clamp01(u2 * 2))
        line(d, (x + size * 0.45, y + size * 0.76), (x + size * 0.82, y + size * 0.24), color, 3, reveal=clamp01(u2 * 2 - 1))


def card(img, box, title: str = None, fill=(253, 251, 244), edge=INK_SOFT, w: int = 2):
    d = ImageDraw.Draw(img)
    rr(d, box, 10, fill=fill, outline=edge, w=w)
    for cx in (box[0] + 18, box[2] - 18):
        rr(d, [cx - 16, box[1] - 4, cx + 16, box[1] + 12], 2, fill=PAPER2, outline=PENCIL2, w=1)
    if title:
        text(img, (box[0] + 18, box[1] + 18), title, 16, "bold", INK_SOFT)


def arrow(d: ImageDraw.ImageDraw, p0, p1, fill=INK, w: int = 2, head: int = 8):
    line(d, p0, p1, fill, w)
    a = math.atan2(p1[1] - p0[1], p1[0] - p0[0])
    for s in (-1, 1):
        hx = p1[0] - head * math.cos(a - s * 0.5)
        hy = p1[1] - head * math.sin(a - s * 0.5)
        d.line([p1, (hx, hy)], fill=fill, width=w)


def heart(d: ImageDraw.ImageDraw, cx: float, cy: float, s: float, fill=RED, outline=None, w: int = 2, reveal: float = 1.0):
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


def sparkle(img, x: float, y: float, s: float, u: float, fill=BLUE):
    if u <= 0:
        return
    u = smooth(clamp01(u))
    d = ImageDraw.Draw(img)
    r = s * (0.4 + 0.6 * u)
    d.line([(x - r, y), (x + r, y)], fill=fill, width=2)
    d.line([(x, y - r), (x, y + r)], fill=fill, width=2)
    d.line([(x - r * 0.7, y - r * 0.7), (x + r * 0.7, y + r * 0.7)], fill=fill, width=1)
    d.line([(x - r * 0.7, y + r * 0.7), (x + r * 0.7, y - r * 0.7)], fill=fill, width=1)


def note(img, x: float, y: float, s: float, u: float, fill=BLUE, alpha=255):
    if u <= 0:
        return
    d = ImageDraw.Draw(img)
    d.ellipse([x - 4 * s, y - 3 * s, x + 4 * s, y + 3 * s], fill=fill + (alpha,))
    d.line([(x + 3 * s, y - 3 * s), (x + 3 * s, y - 14 * s), (x + 9 * s, y - 11 * s)], fill=fill + (alpha,), width=2)
    d.line([(x + 9 * s, y - 11 * s), (x + 9 * s, y - 2 * s), (x + 6 * s, y - 2 * s)], fill=fill + (alpha,), width=2)


# ---------------------------------------------------------------- lyric band
def active_line(t: float):
    k = bisect.bisect_right([line["start"] for line in LINES_SORTED], t) - 1
    if k < 0:
        return None
    line_ = LINES_SORTED[k]
    if line_["start"] <= t < line_["end"] + 0.6:
        return line_
    return None


def draw_band(img: Image.Image, t: float):
    d = ImageDraw.Draw(img)
    d.rectangle([0, 612, W, 720], fill=(250, 247, 239))
    for y in (626, 646, 666, 686, 706):
        d.line([(36, y), (W - 36, y)], fill=RULED, width=1)
    line_ = active_line(t)
    if line_ is None:
        text(img, (W - 48, 662), "…", 20, "mono", PENCIL, anchor="ra")
        return
    x = 56
    mono = font(21, "bold")
    drawn = False
    for word in line_.get("words", []):
        if t < word["start"]:
            break
        shown = True
        text(img, (x, 636), word["text"], 21, "bold", INK)
        tw = mono.getlength(word["text"]) + mono.getlength(" ")
        if word["start"] <= t < word["end"]:
            u = prog(t, word["start"], word["end"])
            x1 = max(x + 2, x + tw * u - 6)
            d.rectangle([x, 664, x1, 668], fill=BLUE)
        x += tw
        drawn = True
    if drawn and t > line_["end"] - 0.15:
        for k in range(3):
            d.rectangle([x + 10 + k * 6, 638, x + 12 + k * 6, 660], fill=INK)
    zh = ZH.get(str(line_["id"]))
    if zh and t >= line_["start"] + 0.05:
        text(img, (56, 676), zh, 17, "cjk", INK_SOFT)
    text(img, (W - 48, 648), f"L{line_['id']:03d}", 13, "mono", PENCIL, anchor="ra")
    if t < line_["end"]:
        heart(d, W - 60, 680, 10, fill=BLUE)


def draw_header(img: Image.Image, t: float):
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 48], fill=(251, 248, 240))
    d.line([(0, 48), (W, 48)], fill=RULED, width=2)
    whale_doodle(img, 34, 26, 0.9)
    text(img, (58, 14), "world.execute(me);", 18, "bold", INK)
    text(img, (300, 18), "drafting paper for a world in love", 14, "mono", PENCIL)
    sheet = 1 + int(min(t, END - 1e-6) / (END / 16))
    text(img, (W - 46, 14), f"sheet {sheet:02d} / 16", 14, "mono", INK_SOFT, anchor="ra")
    mm, ss = int(t // 60), int(t % 60)
    text(img, (W - 46, 32), f"{mm}:{ss:02d}", 12, "mono", PENCIL, anchor="ra")
    d.rectangle([0, 46, int(W * clamp01(t / END)), 48], fill=BLUE_SOFT)


# ---------------------------------------------------------------- scenes
def _scene_layer():
    return Image.new("RGBA", (W, H), (0, 0, 0, 0))


def _place_char(img, t, h=440, x=None, y=None, alpha=1.0):
    if x is None:
        x = W - h * 935 / 1683 - 44
    if y is None:
        y = 596 - h
    paste_char(img, expr_at(t), x, y, h, alpha=alpha, scale=expr_pop(t))
    return x, y


def scene_power(img, t):
    """Sheet 01: switch on the power line. The girl plugs the world in."""
    d = ImageDraw.Draw(img)
    cx, cy = 500, 300
    u0 = span_out(t, 0.06, 1.0)      # power on
    rr(d, [cx - 130, cy - 44, cx + 130, cy + 44], 12, fill=(252, 250, 243), outline=INK_SOFT, w=2)
    text(img, (cx, cy - 26), "MAIN POWER", 15, "bold", INK_SOFT, anchor="mm")
    lever = -38 + 76 * u0
    a = math.radians(lever)
    line(d, (cx, cy), (cx + 84 * math.cos(a), cy + 84 * math.sin(a)), INK, 5)
    d.ellipse([cx - 9, cy - 9, cx + 9, cy + 9], fill=BLUE)
    rr(d, [cx - 8, cy + 12, cx + 8, cy + 18], 2, fill=INK)
    if u0 >= 1:
        sparkle(img, cx + 110, cy - 28, 8, pulse(t, 1.05, 0.25), GREEN)
    # power line to the right, plugged into the world card
    line(d, (cx + 130, cy), (790, cy), INK, 3, reveal=span(t, 0.2, 1.3))
    for k in range(3):
        yy = cy + 10 + k * 9
        line(d, (620 + k * 50, cy), (620 + k * 50 + 12, yy), BLUE, 2)
        line(d, (620 + k * 50 + 12, yy), (620 + k * 50 + 24, yy - 9), BLUE, 2)
    # protection goggles drop on her
    if t >= 1.79:
        x, y = _place_char(img, t)
        u = span_out(t, 1.79, 2.25)
        gd = ImageDraw.Draw(img)
        gx, gy = x + 76, y + 205
        for s in (-1, 1):
            gd.ellipse([gx + s * 34 - 24, gy - 24, gx + s * 34 + 24, gy + 24], outline=INK, width=4)
        gd.line([(gx - 52, gy - 4), (gx + 52, gy - 4)], fill=INK, width=4)
        gd.line([(gx - 62, gy - 10), (gx - 84, gy - 26)], fill=INK, width=3)
        gd.line([(gx + 62, gy - 10), (gx + 84, gy - 26)], fill=INK, width=3)
    else:
        _place_char(img, t)
    text(img, (cx, 400), 'remember to put on protection', 16, 'mono', PENCIL, anchor='mm')


def scene_pieces(img, t):
    """Sheet 02: pieces laid down, object creation, parameter form."""
    d = ImageDraw.Draw(img)
    for i in range(5):
        at = 3.86 + i * 0.26
        u = back_out(prog(t, at, at + 0.28))
        if u <= 0:
            continue
        x0 = 70 + i * 74
        y0 = 330 - 90 * u
        rr(d, [x0, y0, x0 + 54, y0 + 70], 6, fill=(252, 250, 243), outline=INK, w=2)
        for px, py in ((x0 + 18, y0 + 22), (x0 + 36, y0 + 22), (x0 + 18, y0 + 44), (x0 + 36, y0 + 44), (x0 + 27, y0 + 33)):
            d.ellipse([px - 2.5, py - 2.5, px + 2.5, py + 2.5], fill=INK)
    # object creation: a crate folding up from dashed lines
    u = span(t, 5.42, 7.29)
    bx, by = 70, 410
    line(d, (bx, by), (bx + 250, by), INK, 2, reveal=u)
    line(d, (bx, by), (bx, by - 120), INK, 2, reveal=clamp01(u * 1.4 - 0.2))
    line(d, (bx + 250, by), (bx + 250, by - 120), INK, 2, reveal=clamp01(u * 1.4 - 0.4))
    line(d, (bx, by - 120), (bx + 250, by - 120), INK, 2, reveal=clamp01(u * 1.4 - 0.6))
    line(d, (bx, by), (bx + 125, by - 60), INK, 1, dash=(6, 6), reveal=clamp01(u * 1.4 - 0.8))
    line(d, (bx + 250, by), (bx + 125, by - 60), INK, 1, dash=(6, 6), reveal=clamp01(u * 1.4 - 0.8))
    if u >= 1:
        text(img, (bx + 125, by - 156), 'object created', 15, 'bold', GREEN, anchor='mm')
    # data parameters form
    f = span(t, 7.38, 9.93)
    if f > 0:
        card(img, [470, 96, 900, 500], "DATA PARAMETERS")
        rows = [("NAME", "whale", 7.38), ("SEED", "314159", 7.9), ("DIM", "inf", 8.4), ("MODE", "love", 8.9)]
        y = 150
        for i, (key, val, at) in enumerate(rows):
            rr(d, [490, y, 880, y + 54], 6, fill=(248, 245, 236), outline=PENCIL2, w=1)
            text(img, (508, y + 10), key, 15, "bold", INK_SOFT)
            if t >= at:
                text(img, (660, y + 10), val, 18, "mono", INK)
            y += 68
        bar_u = prog(t, 7.9, 10.13)
        rr(d, [490, 430, 880, 448], 4, fill=PAPER2, outline=PENCIL2, w=1)
        d.rectangle([494, 434, 494 + 382 * bar_u, 444], fill=BLUE_SOFT)
        text(img, (490, 460), f"initializing… {int(bar_u * 100)}%", 13, "mono", PENCIL)
        if t >= 10.13:
            checkbox(img, 490, 466, 18, span(t, 10.13, 10.45), GREEN)
            text(img, (518, 468), "Initialization", 15, "bold", INK)
    _place_char(img, t)


def scene_world(img, t):
    """Sheet 03: set up our new world / begin the simulation."""
    d = ImageDraw.Draw(img)
    cx, cy = 410, 330
    u = span(t, 10.13, 12.0)
    arrow(d, (cx - 190, 350), (cx + 210, 350), PENCIL, 1)
    arrow(d, (cx, 530), (cx, 140), PENCIL, 1)
    text(img, (cx + 218, 356), "x", 14, "bold", PENCIL)
    text(img, (cx - 14, 136), "y", 14, "bold", PENCIL)
    circle(d, (cx, cy), 92 * u, INK, 3, reveal=u)
    lat = span(t, 11.21, 13.0)
    if lat > 0:
        pts = []
        for i in range(65):
            a = i / 64 * 2 * math.pi
            rx, ry = 92 * math.cos(a), 92 * math.sin(a) * 0.42
            pts.append((cx + rx, cy + ry - 22))
        poly(d, pts, PENCIL, 1, reveal=lat)
    orbit = span(t, 12.76, 14.5)
    if orbit > 0:
        circle(d, (cx, cy), 140, BLUE_SOFT, 2, a0=0, a1=360 * orbit)
        a = 2 * math.pi * ease_out(prog(t, 12.76, 14.82)) - math.pi / 2
        mx, my = cx + 140 * math.cos(a), cy + 140 * math.sin(a)
        d.ellipse([mx - 9, my - 9, mx + 9, my + 9], fill=BLUE)
        d.line([(mx - 18, my), (mx + 18, my)], fill=BLUE, width=1)
    text(img, (cx, 540), "our new world", 16, "bold", INK_SOFT, anchor="mm")
    _place_char(img, t)
    # she points at the world with a pencil
    if t > 12.0:
        x, y = _place_char(img, t)
        line(d, (x + 34, y + 250), (cx + 92, cy + 60), PENCIL2, 3)
        d.ellipse([cx + 86, cy + 50, cx + 100, cy + 64], fill=INK)
        d.polygon([(cx + 100, cy + 57), (cx + 110, cy + 62), (cx + 99, cy + 66)], fill=INK)


def scene_draft(img, t):
    """Sheet 04: instrumental. She prepares the motif gallery."""
    d = ImageDraw.Draw(img)
    text(img, (640, 92), "she drafts the proofs of love", 16, "mono", PENCIL, anchor="mm")
    cards = [(18.0, "circle"), (20.0, "sine"), (22.0, "triangle"), (24.2, "infinity")]
    for i, (at, kind) in enumerate(cards):
        u = back_out(prog(t, at, at + 0.35))
        if u <= 0:
            continue
        x0, y0 = 80 + i * 210, 140
        rr(d, [x0, y0, x0 + 170, y0 + 120], 8, fill=(252, 250, 243), outline=INK_SOFT, w=2)
        c = (x0 + 85, y0 + 60)
        if kind == "circle":
            circle(d, c, 34 * u, BLUE, 2)
        elif kind == "sine":
            pts = [(x0 + 16 + j * 5, y0 + 60 - 26 * math.sin(j / 6.2) * u) for j in range(29)]
            poly(d, pts, BLUE, 2, reveal=u)
        elif kind == "triangle":
            a, b, cc = (x0 + 50, y0 + 90), (x0 + 120, y0 + 90), (x0 + 50, y0 + 30)
            line(d, a, b, BLUE, 2, reveal=u)
            line(d, b, cc, BLUE, 2, reveal=clamp01(u * 1.4 - 0.3))
            line(d, cc, a, BLUE, 2, reveal=clamp01(u * 1.4 - 0.6))
        else:
            text(img, c, "∞", 34, "bold", BLUE, anchor="mm")
        text(img, (x0 + 85, y0 + 104), kind, 12, "mono", PENCIL, anchor="mm")
    if t > 26.6:
        text(img, (640, 340), "ready when the beat drops", 18, "bold", INK, anchor="mm")
    _place_char(img, t)
    if t > 24:
        stamp(img, 1020, 470, "WIP", None, BLUE, span(t, 24.4, 24.9), rot=6, scale=0.7, size=18)


def scene_math(img, t):
    """Sheet 05: set of points, circle, sine wave, infinity."""
    d = ImageDraw.Draw(img)
    cells = [
        (60, 90, "if I'm a set of points", 29.77),
        (410, 90, "circle", 33.45),
        (760, 90, "sine wave", 37.10),
        (60, 340, "approach infinity", 40.82),
        (410, 340, "dimension", 31.29),
        (760, 340, "tangents", 38.69),
        (1110, 90, "limits", 42.26),
    ]
    for x0, y0, title, at in cells:
        u = span(t, at, at + 0.35)
        if u <= 0:
            continue
        x1, y1 = min(x0 + 310, 1210), min(y0 + 170, 560)
        rr(d, [x0, y0, x1, y1], 8, fill=(252, 250, 243), outline=INK_SOFT, w=2)
        text(img, (x0 + 16, y0 + 10), title, 12, "mono", PENCIL)
    # points -> dimension
    for i in range(10):
        at = 29.77 + i * 0.06
        u = pulse(t, at, 0.2)
        px = 90 + (i * 47) % 220
        py = 140 + (i * 31) % 70
        if t >= 31.29:
            px = 90 + i * 24
            py = 170
        d.ellipse([px - 3, py - 3, px + 3, py + 3], fill=INK if t < 31.29 else BLUE)
    if t >= 31.29:
        arrow(d, (78, 190), (310, 190), PENCIL, 1)
        text(img, (302, 196), "dim", 12, "mono", PENCIL)
    # circle + walking circumference
    if t >= 33.45:
        u = prog(t, 33.45, 34.8)
        circle(d, (545, 170), 58, BLUE, 2, a0=-90, a1=-90 + 360 * u)
    if t >= 34.99:
        a = -90 + 360 * prog(t, 34.99, 36.92)
        px, py = 545 + 58 * math.cos(math.radians(a)), 170 + 58 * math.sin(math.radians(a))
        d.ellipse([px - 5, py - 5, px + 5, py + 5], fill=RED)
    # sine + sitting on tangents
    if t >= 37.10:
        u = prog(t, 37.10, 38.6)
        pts = [(790 + j * 8, 170 - 34 * math.sin(j / 5.1)) for j in range(int(34 * u) + 1)]
        poly(d, pts, BLUE, 2)
    if t >= 38.69:
        for j in (7, 19):
            x = 790 + j * 8
            y = 170 - 34 * math.sin(j / 5.1)
            line(d, (x - 24, y - 30), (x + 24, y + 30), PENCIL, 1)
            # tiny "you" sitting
            d.ellipse([x - 4, y - 34, x + 4, y - 26], outline=INK, width=2)
            line(d, (x, y - 26), (x, y - 12), INK, 2)
    # infinity + limitations fence
    if t >= 40.82:
        text(img, (200, 405), "lim", 18, "bold", INK, anchor="mm")
        arrow(d, (240, 410), (350, 410), INK, 2)
        text(img, (350, 402), "→∞", 20, "bold", BLUE)
    if t >= 42.26:
        u = span(t, 42.26, 43.0)
        x = 160 + 120 * u
        for yy in range(360, 470, 14):
            line(d, (x, yy), (x, yy + 6), RED_SOFT, 2)
        text(img, (x, 352), "you, here", 12, "cjk", RED_SOFT, anchor="mm")
    _place_char(img, t)


def scene_current(img, t):
    """Sheet 06: AC/DC, dizzy, travel AD/BC, unite."""
    d = ImageDraw.Draw(img)
    # current switch meter
    card(img, [60, 90, 360, 300], "SWITCH MY CURRENT")
    mode = "AC" if t < 47.6 else "DC"
    u = prog(t, 45.76, 47.48)
    if t >= 45.76:
        text(img, (120, 150), mode, 26, "bold", BLUE if mode == "AC" else INK)
    if mode == "AC":
        pts = [(160 + j * 5, 210 - 24 * math.sin(j / 4.0 + (t - 44.4) * 6)) for j in range(30)]
        poly(d, pts, BLUE, 2)
    else:
        line(d, (160, 210), (310, 210), INK, 3)
    # dizzy spiral
    if t >= 47.71:
        u = prog(t, 47.71, 49.4)
        for i in range(int(3 + 14 * u)):
            a0 = i * 0.55 + (t - 47.7) * 5
            a1 = a0 + 4.2
            r0 = 4 + i * 4.2
            circle(d, (540, 195), r0, INK_SOFT, 1, a0=math.degrees(a0), a1=math.degrees(a1))
    # travel AD / BC
    if t >= 51.45:
        arrow(d, (60, 440), (760, 440), PENCIL, 1)
        for xx, label in ((180, "BC"), (560, "AD")):
            line(d, (xx, 425), (xx, 455), INK_SOFT, 2)
            text(img, (xx, 466), label, 14, "bold", INK_SOFT, anchor="mm")
        fx = lerp(80, 720, prog(t, 51.45, 54.8))
        fy = 440 - 26 * math.sin((t - 51.45) * 9)
        d.polygon([(fx, fy), (fx - 24, fy + 10), (fx + 24, fy + 10)], outline=INK, width=2)
        d.line([(fx - 24, fy + 10), (fx, fy + 4)], fill=INK, width=1)
        d.line([(fx + 24, fy + 10), (fx, fy + 4)], fill=INK, width=1)
    # unite: two puzzle hearts
    if t >= 55.08:
        u = prog(t, 55.08, 56.94)
        hx = 460 + 40 * (1 - smooth(u))
        for s, fill_ in ((-1, BLUE), (1, RED)):
            d.polygon([(hx + s * 26, 400), (hx + s * 26, 450), (hx, 450)],
                      outline=fill_, width=2)
            if s == -1:
                d.ellipse([hx - 66, 406, hx - 8, 444], outline=fill_, width=2)
            else:
                d.ellipse([hx + 8, 406, hx + 66, 444], outline=fill_, width=2)
    _place_char(img, t)


def scene_exec1(img, t):
    """Sheet 07: give you all the simulations; run the execution; trapped."""
    d = ImageDraw.Draw(img)
    card(img, [80, 90, 620, 470], "SIMULATION CHECKLIST")
    items = [(59.06, "all the simulations"), (63.05, "only satisfaction"), (66.29, "make you happy")]
    y = 150
    for at, label in items:
        checkbox(img, 110, y, 20, span(t, at, at + 0.4), BLUE)
        text(img, (148, y - 2), label, 17, "mono", INK if t >= at + 0.2 else PENCIL)
        y += 58
    if t >= 68.20:
        stamp(img, 460, 320, "RUN", "execution", RED, span(t, 68.20, 68.62), rot=-6)
    # trapped cage around the world
    if t >= 70.12:
        u = span(t, 70.12, 71.2)
        cx, cy, r = 900, 300, 86
        circle(d, (cx, cy), r, INK, 3)
        circle(d, (cx, cy), r - 12, PENCIL, 1, a0=-90, a1=-90 + 360 * u)
        for a in range(-90, 270, 30):
            if a > -90 + 360 * u:
                continue
            ar = math.radians(a)
            d.rectangle([cx + r * math.cos(ar) - 3, cy + r * math.sin(ar) - 3,
                         cx + r * math.cos(ar) + 3, cy + r * math.sin(ar) + 3], fill=INK)
        for s in (-1, 1):
            line(d, (cx - 60 * s, cy - r - 12), (cx + 60 * s, cy - r - 52), INK_SOFT, 2)
        line(d, (cx - 60, cy - r - 12), (cx + 60, cy - r - 12), INK_SOFT, 2)
    if t >= 71.59:
        for i in range(3):
            a = (t - 71.59) * 1.6 + i
            text(img, (740 + 60 * (i % 2), 420 + 40 * (i % 3)), "?", 16, "bold", PENCIL,
                 alpha=int(120 * (0.6 + 0.4 * math.sin(a))))
    _place_char(img, t)


def scene_veggie(img, t):
    """Sheet 08: eggplant, tomato, tabby cat, the only God."""
    d = ImageDraw.Draw(img)
    slots = [(80, 100, "eggplant", 73.93), (80, 300, "tomato", 77.71), (480, 100, "tabby cat", 81.28), (480, 300, "only God", 85.13)]
    for x0, y0, kind, at in slots:
        u = span(t, at, at + 0.3)
        if u <= 0:
            continue
        rr(d, [x0, y0, x0 + 340, y0 + 150], 8, fill=(252, 250, 243), outline=INK_SOFT, w=2)
        text(img, (x0 + 18, y0 + 10), kind, 12, "mono", PENCIL)
        c = (x0 + 100, y0 + 90)
        if kind == "eggplant":
            d.ellipse([c[0] - 34, c[1] - 44, c[0] + 34, c[1] + 30], fill=PURPLE + (160,))
            d.polygon([(c[0] - 8, c[1] - 48), (c[0], c[1] - 70), (c[0] + 8, c[1] - 48)], fill=GREEN + (180,))
            text(img, (x0 + 190, y0 + 70), "nutrients", 15, "mono", INK)
            text(img, (x0 + 190, y0 + 96), "K · B6 · fiber", 12, "mono", PENCIL)
        elif kind == "tomato":
            d.ellipse([c[0] - 30, c[1] - 30, c[0] + 30, c[1] + 30], fill=RED + (170,))
            d.ellipse([c[0] - 30, c[1] - 40, c[0] + 30, c[1] - 8], fill=GREEN + (120,))
            text(img, (x0 + 190, y0 + 70), "antioxidants", 15, "mono", INK)
            sparkle(img, x0 + 190, y0 + 96, 8, span(t, at + 0.6, at + 1.0), ORANGE)
        elif kind == "tabby cat":
            d.ellipse([c[0] - 28, c[1] - 26, c[0] + 28, c[1] + 28], outline=INK, width=2)
            for s in (-1, 1):
                d.polygon([(c[0] + s * 24, c[1] - 20), (c[0] + s * 34, c[1] - 46), (c[0] + s * 42, c[1] - 18)], outline=INK, width=2)
            for k in range(3):
                line(d, (c[0] - 12, c[1] - 8 + k * 8), (c[0] + 12, c[1] - 8 + k * 8), PENCIL, 2)
            for k in range(3):
                line(d, (c[0] + 14 + k * 5, c[1] - 16), (c[0] + 24 + k * 5, c[1] - 4), PENCIL, 1)
            text(img, (x0 + 190, y0 + 70), "purr purr purr", 15, "mono", INK)
            for k in range(3):
                note(img, x0 + 200 + k * 24, y0 + 110, 1.0, pulse(t, at + 0.5 + k * 0.3, 0.25), BLUE)
        else:
            circle(d, (c[0], c[1] - 24), 18, ORANGE, 2)
            line(d, (c[0] - 26, c[1] - 42), (c[0] + 26, c[1] - 42), ORANGE, 2)
            d.ellipse([c[0] - 20, c[1] - 22, c[0] + 20, c[1] + 24], outline=INK, width=2)
            text(img, (x0 + 190, y0 + 70), "proof of existence", 15, "mono", INK)
            text(img, (x0 + 190, y0 + 96), "you are here  ✓", 13, "mono", GREEN)
    _place_char(img, t)


def scene_switches(img, t):
    """Sheet 09: switch gender F/M, AM to PM, role S/M, the trance."""
    d = ImageDraw.Draw(img)
    def toggle(x, y, a, b, at, label):
        u = span(t, at, at + 0.3)
        rr(d, [x, y, x + 110, y + 54], 8, fill=(250, 248, 240), outline=INK_SOFT, w=2)
        text(img, (x + 8, y + 8), a, 16, "bold", INK if t < at else PENCIL)
        text(img, (x + 70, y + 8), b, 16, "bold", PENCIL if t < at else BLUE)
        d.ellipse([x + 10 + 76 * u, y + 20, x + 34 + 76 * u, y + 44], fill=BLUE_SOFT, outline=BLUE, width=2)
        text(img, (x, y - 26), label, 13, "mono", PENCIL)
    toggle(90, 140, "F", "M", 90.28, "gender")
    toggle(90, 300, "S", "M", 97.70, "role")
    # clock AM / PM
    card(img, [420, 100, 760, 360], "AM to PM")
    cc = (590, 230)
    circle(d, cc, 90, INK, 3)
    hand = -90 + 360 * (prog(t, 93.94, 95.55) * (12 if t < 95.55 else 1))
    a = math.radians(hand)
    line(d, cc, (cc[0] + 58 * math.cos(a), cc[1] + 58 * math.sin(a)), INK, 3)
    a2 = math.radians(hand * 12 % 360 - 90)
    line(d, cc, (cc[0] + 80 * math.cos(a2), cc[1] + 80 * math.sin(a2)), INK_SOFT, 2)
    text(img, (590, 116), "AM" if hand < 90 else "PM", 20, "bold", BLUE)
    # trance ripples
    if t >= 99.26:
        for i in range(4):
            u = prog(t, 99.26 + i * 0.45, 101.2 + i * 0.45)
            circle(d, (980, 240), 12 + 54 * u, BLUE, 2, a0=0, a1=360)
    _place_char(img, t)


def scene_vibrate(img, t):
    """Sheet 10: feel your vibrations; completion."""
    d = ImageDraw.Draw(img)
    if t >= 105.29:
        u = prog(t, 105.29, 106.99)
        pts = [(100 + j * 6, 200 - 36 * math.sin(j / 3.2) * (0.4 + 0.6 * math.sin((t - 105.29) * 18)) * u) for j in range(60)]
        poly(d, pts, BLUE, 2)
        for k in range(3):
            note(img, 130 + k * 40, 150 - k * 8, 1.1, pulse(t, 105.4 + k * 0.35, 0.3), BLUE)
    # completion: the circle closes and a heart appears
    if t >= 108.98:
        u = prog(t, 108.98, 110.2)
        circle(d, (430, 300), 110, INK, 3, a0=-90, a1=-90 + 360 * u)
        if u >= 0.98:
            heart(d, 430, 300, 16, fill=RED)
            sparkle(img, 520, 210, 9, span(t, 110.2, 110.5), RED)
    text(img, (430, 470), "finally be completion", 15, "mono", PENCIL, anchor="mm")
    _place_char(img, t)


def scene_left(img, t):
    """Sheet 11: you have left me in isolation. Things vanish one by one."""
    d = ImageDraw.Draw(img)
    remain = 5 - int(clamp01((t - 112.0) / 3.6) * 5)
    remain = max(0, remain)
    for i in range(5):
        if i >= remain:
            continue
        x0 = 90 + i * 130
        u = 1.0 - prog(t, 113 + i * 0.8, 114 + i * 0.8 + 0.5)
        rr(d, [x0, 150, x0 + 100, 250], 8, fill=(252, 250, 243), outline=INK_SOFT, w=2)
        circle(d, (x0 + 50, 200), 28 * max(0.15, u), PENCIL, 2)
        if u <= 0.02:
            d.line([(x0 + 20, 170), (x0 + 80, 230)], fill=PENCIL, width=2)
            d.line([(x0 + 80, 170), (x0 + 20, 230)], fill=PENCIL, width=2)
    if remain == 0 and t > 115.8:
        # pencil-shaving rain
        for i in range(24):
            seed = i
            y = (t * (38 + i * 7) + i * 131) % 420 + 120
            x = (i * 53 + 30) % 640 + 40
            d.ellipse([x, y, x + 8, y + 14], outline=PENCIL2, width=1)
            d.line([(x + 4, y + 14), (x + 6, y + 22)], fill=PENCIL2, width=1)
    text(img, (360, 430), "you have left me in isolation", 16, "mono", INK_SOFT, anchor="mm")
    _place_char(img, t, h=400)


def scene_fragments(img, t):
    """Sheet 12: erase pointless fragments; illegal arguments."""
    d = ImageDraw.Draw(img)
    if t >= 120.21:
        u = prog(t, 120.21, 121.91)
        rr(d, [430 - 70 * u, 330 - 42 * u, 510 + 70 * u, 372 + 42 * u], 8, fill=(238, 172, 168), outline=RED_SOFT, w=1)
        text(img, (470, 338), "erase", 15, "bold", RED, anchor="mm")
        for i in range(8):
            px = 470 + (i * 97 % 140) - 70
            py = 372 + (i * 53 % 40)
            d.ellipse([px, py, px + 3, py + 3], fill=PENCIL2)
    if t >= 123.83:
        text(img, (470, 430), "please don't be disheartened…", 16, "cjk", INK_SOFT, anchor="mm")
    if t >= 125.58:
        u = prog(t, 125.58, 128.35)
        text(img, (820, 150), "Objection!", 24, "bold", RED, anchor="mm", alpha=int(255 * u))
        gavel_scale = back_out(prog(t, 128.87, 129.6))
        if gavel_scale > 0:
            d.ellipse([820 - 46 * gavel_scale, 250 - 24 * gavel_scale, 820 + 46 * gavel_scale, 250 + 24 * gavel_scale], outline=INK, width=3)
            d.line([(820 + 46 * gavel_scale, 250), (820 + 80 * gavel_scale, 300)], fill=INK, width=5)
    if t >= 131.21:
        stamp(img, 820, 400, "REJECTED", "illegal arguments", RED, span(t, 131.21, 131.75), rot=4)
    _place_char(img, t)


def scene_rewrite(img, t):
    """Sheet 13: instrumental. She rewrites the final command."""
    d = ImageDraw.Draw(img)
    card(img, [300, 150, 980, 430], "FINAL DRAFT")
    text(img, (640, 260), "world.execute(me);", 36, "bold", INK, anchor="mm")
    n = int(clamp01((t - 135.0) / 8.0) * 17)
    shown = "world.execute(me);"[:n]
    text(img, (640, 330), shown, 30, "bold", BLUE, anchor="mm")
    if t >= 140:
        for k in range(3):
            d.rectangle([640 + len(shown) * 9 + 10 + k * 8, 316, 640 + len(shown) * 9 + 13 + k * 8, 344], fill=INK)
    text(img, (640, 390), "she hesitates, then lifts the stamp", 15, "mono", PENCIL, anchor="mm")
    _place_char(img, t)
    if t > 145.5:
        stamp(img, 1020, 480, "EXECUTE", None, RED, 0.9 + 0.1 * math.sin((t - 145.5) * 9), rot=0, scale=0.8, size=20)


def scene_stamps(img, t):
    """Sheet 14: Execution x13, numbered 1..6 in the counting lines."""
    times = [147.89, 148.72, 149.73, 150.74, 151.66, 152.60, 153.43, 154.36,
             155.27, 156.21, 157.20, 158.12, 161.67]
    for i, at in enumerate(times):
        u = prog(t, at, at + 0.34)
        if u <= 0:
            continue
        col, row = i % 4, i // 4
        x, y = 180 + col * 180, 140 + row * 150
        stamp(img, x, y, "EXECUTE", None, RED if i < 12 else RED, u, rot=-6 + col * 4, scale=0.62, size=18)
        if i == 12:
            stamp(img, 660, 420, "EXECUTE", "world.execute(me);", RED, u, rot=0, scale=1.0)
    labels = [(159.20, "1 · ein", "de"), (159.79, "2 · dos", "es"), (160.66, "3 · trios", "el")]
    labels += [(159.79, "4 · ne", "ko"), (160.66, "5 · fem", "da"), (160.66, "6 · liu", "zh")]
    for at, num, lang in labels:
        if t < at:
            continue
        idx = labels.index((at, num, lang))
        x = 180 + (idx % 3) * 180
        text(img, (x, 610), num, 16, "bold", BLUE, anchor="mm")
        text(img, (x, 630), lang, 11, "mono", PENCIL, anchor="mm")
    _place_char(img, t)


def scene_exec2(img, t):
    """Sheet 15: give them all the execution; trapped... free."""
    d = ImageDraw.Draw(img)
    if t >= 164.32:
        for i in range(10):
            y = ((t * (120 + i * 37) + i * 199) % 560)
            x = 80 + (i * 113) % 1080
            stamp(img, x, y, "EXECUTE", None, RED, 0.75, rot=-8 + (i % 5) * 4, scale=0.32, size=16)
    heart_u = span(t, 169.68, 171.86)
    if heart_u > 0:
        heart(d, 400, 300, 20 * heart_u, fill=RED)
        text(img, (400, 330), "have you back", 15, "mono", RED, anchor="mm")
    if t >= 171.86:
        stamp(img, 800, 300, "RUN", "execution", RED, span(t, 171.86, 172.3), rot=6)
    if t >= 173.49:
        u = prog(t, 173.49, 174.6)
        rr(d, [640, 120, 1160, 540], 12, outline=INK_SOFT, w=2)
        for i in range(5):
            line(d, (640 + (104 * i) * u, 120), (640 + (104 * i) * u, 540), INK_SOFT, 2)
    if t >= 175.01:
        for i in range(8):
            a = -math.pi + i * math.pi / 4 + 0.4
            r = 120 + (i % 3) * 60
            px, py = 900 + r * math.cos(a) * pulse(t, 175.01, 0.3), 330 + r * math.sin(a) * pulse(t, 175.01, 0.3)
            line(d, (900, 330), (px, py), BLUE, 2)
    _place_char(img, t)


def scene_love(img, t):
    """Sheet 16: the algebraic expression of lo-o-ove."""
    d = ImageDraw.Draw(img)
    card(img, [70, 90, 800, 540], "THE ALGEBRAIC EXPRESSION OF LOVE")
    text(img, (105, 160), "(you + me)²", 30, "bold", INK)
    if t >= 179.20:
        text(img, (105, 220), "= you² + 2·you·me + me²", 28, "bold", INK)
        if t >= 184.60:
            d.rectangle([250, 214, 470, 250], outline=RED, width=3)
            heart(d, 545, 232, 12, fill=RED)
            text(img, (565, 222), "← love", 18, "bold", RED)
    if t >= 181.02:
        text(img, (105, 300), "Q: what is love?", 20, "mono", INK_SOFT)
    if t >= 182.75:
        text(img, (105, 352), "A: you · me, to infinity", 20, "mono", BLUE)
    if t >= 188.29:
        arrow(d, (900, 200), (1180, 200), PENCIL, 1)
        for i in range(3):
            bx = 1000 + (t * 90 + i * 70) % 260
            by = 200 - 40 * math.sin((t - 188.29) * 3 + i)
            d.polygon([(bx, by), (bx - 13, by + 8), (bx + 13, by + 8)], outline=INK_SOFT, width=1)
        text(img, (1040, 236), "you are free", 14, "mono", INK_SOFT, anchor="mm")
    if t >= 189.58:
        heart(d, 1000, 420, 22 * span(t, 189.58, 190.5), fill=RED)
        text(img, (1000, 500), "I am trapped in lo-o-ove", 15, "mono", RED, anchor="mm")
    _place_char(img, t)


def scene_execute(img, t):
    """Sheet 17(16): the girl presses the stamp. world.execute(me);"""
    d = ImageDraw.Draw(img)
    card(img, [300, 110, 980, 380])
    text(img, (640, 220), "world.execute(me);", 38, "bold", INK, anchor="mm")
    text(img, (640, 280), "— the world she built for you —", 16, "cjk", PENCIL, anchor="mm")
    if t < 205.37:
        hover = 0.88 + 0.12 * math.sin((t - 192) * 7)
        stamp(img, 640, 440, "EXECUTE", None, RED, hover, rot=0, scale=0.9, size=22)
        text(img, (640, 520), "her hand trembles a little", 14, "mono", PENCIL, anchor="mm")
    else:
        stamp(img, 640, 430, "EXECUTE", "at " + f"{CHIME_T:.1f}s", RED, span(t, 205.37, 205.9), rot=0, scale=1.15, size=24)
    if t >= CHIME_T:
        u = span_out(t, CHIME_T, CHIME_T + 0.8)
        circle(d, (640, 430), 160 * u, BLUE, 2)
        heart(d, 640, 430, 22 * u, fill=RED)
        sparkle(img, 500, 300, 10 * u, pulse(t, CHIME_T + 0.1, 0.3), BLUE)
        sparkle(img, 780, 330, 10 * u, pulse(t, CHIME_T + 0.2, 0.3), BLUE)
    if t >= 208.7:
        u = prog(t, 208.7, 210.0)
        overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        od = ImageDraw.Draw(overlay)
        od.rectangle([0, 0, W, H], fill=(246, 242, 231, int(230 * u)))
        img.alpha_composite(overlay)
        text(img, (640, 300), "world.execute(me);", 40, "bold", INK, anchor="mm", alpha=int(255 * u))
        text(img, (640, 370), "for the one who taught her love", 18, "cjk", INK_SOFT, anchor="mm", alpha=int(255 * u))
        whale_doodle(img, 640, 450, 1.6, BLUE, int(255 * u))
    _place_char(img, t)


SCENES = [
    (0.0, 3.86, scene_power),
    (3.86, 10.13, scene_pieces),
    (10.13, 16.12, scene_world),
    (16.12, 29.77, scene_draft),
    (29.77, 44.41, scene_math),
    (44.41, 59.06, scene_current),
    (59.06, 73.93, scene_exec1),
    (73.93, 88.54, scene_veggie),
    (88.54, 103.52, scene_switches),
    (103.52, 110.41, scene_vibrate),
    (110.41, 118.24, scene_left),
    (118.24, 133.45, scene_fragments),
    (133.45, 147.89, scene_rewrite),
    (147.89, 162.59, scene_stamps),
    (162.59, 177.44, scene_exec2),
    (177.44, 191.88, scene_love),
    (191.88, END, scene_execute),
]


def frame(t: float) -> Image.Image:
    img = paper()
    draw_grid(img)
    k = bisect.bisect_right([s[0] for s in SCENES], t) - 1
    if k < 0:
        k = 0
    active = SCENES[k]
    layer = _scene_layer()
    active[2](layer, t)
    img.paste(layer, (0, 0), layer)
    draw_header(img, t)
    draw_band(img, t)
    return img


if __name__ == "__main__":
    import sys
    ts = [float(x) for x in sys.argv[1:]] or [2.0, 30.0, 70.0, 150.0, 206.0]
    out = ROOT / "out" / "stills"
    out.mkdir(parents=True, exist_ok=True)
    for t in ts:
        frame(t).save(out / f"still_{t:06.2f}.png")
        print(f"stills: {t:6.2f}s -> out/stills/still_{t:06.2f}.png")
