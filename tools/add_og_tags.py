#!/usr/bin/env python3
"""
Inject Open Graph + Twitter Card meta tags into index.html and every guide so
shared links show a rich preview (KakaoTalk, Discord, Twitter, Facebook, ...).

Each guide uses its own first (card-friendly) screenshot as the preview image
with accurate width/height; guides without a usable screenshot — and the index
hub — fall back to the branded banner assets/og-image.png (1200x630).
Idempotent: the block is wrapped in markers and regenerated on each run.

Usage: python3 tools/add_og_tags.py
"""
import glob
import html
import os
import re
import struct

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = "https://7bellaa.github.io/idleon-guide-kr"
BANNER = f"{BASE}/assets/og-image.png"
BANNER_DIMS = (1200, 630)
SITE = "Idleon 빌드 가이드 (한글)"

START, END = "<!-- og:start -->", "<!-- og:end -->"
BLOCK_RE = re.compile(r"\s*" + re.escape(START) + r".*?" + re.escape(END), re.S)
TITLE_RE = re.compile(r"<title>(.*?)</title>", re.S | re.I)
DESC_RE = re.compile(r'<meta\s+name="description"\s+content="([^"]*)"', re.I)
FIRST_P_RE = re.compile(r"<p[^>]*>(.*?)</p>", re.S | re.I)
FIGURE_RE = re.compile(
    r'<figure class="guide-img"><img\b[^>]*?\bsrc="\.\./(assets/images/[^"]+)"',
    re.I)


# --- helpers --------------------------------------------------------------- #
def text(s):
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def attr(s):
    return html.escape(s, quote=True)


def image_size(path):
    """(width, height) for png/gif/jpeg/webp, or None."""
    try:
        with open(path, "rb") as f:
            head = f.read(32)
            if head[:8] == b"\x89PNG\r\n\x1a\n":
                return struct.unpack(">II", head[16:24])
            if head[:6] in (b"GIF87a", b"GIF89a"):
                return struct.unpack("<HH", head[6:10])
            if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
                fmt = head[12:16]
                if fmt == b"VP8 ":
                    return (struct.unpack("<H", head[26:28])[0] & 0x3FFF,
                            struct.unpack("<H", head[28:30])[0] & 0x3FFF)
                if fmt == b"VP8L":
                    b = head[21:25]
                    w = ((b[1] & 0x3F) << 8 | b[0]) + 1
                    h = ((b[3] & 0xF) << 10 | b[2] << 2 | (b[1] & 0xC0) >> 6) + 1
                    return w, h
                if fmt == b"VP8X":
                    w = 1 + (head[24] | head[25] << 8 | head[26] << 16)
                    h = 1 + (head[27] | head[28] << 8 | head[29] << 16)
                    return w, h
            if head[:2] == b"\xff\xd8":
                f.seek(2)
                while True:
                    b = f.read(1)
                    while b and b != b"\xff":
                        b = f.read(1)
                    m = f.read(1)
                    while m == b"\xff":
                        m = f.read(1)
                    if m in (b"\xc0", b"\xc1", b"\xc2", b"\xc3", b"\xc5",
                             b"\xc6", b"\xc7", b"\xc9", b"\xca", b"\xcb",
                             b"\xcd", b"\xce", b"\xcf"):
                        f.read(3)
                        h, w = struct.unpack(">HH", f.read(4))
                        return w, h
                    ln = struct.unpack(">H", f.read(2))[0]
                    f.seek(ln - 2, 1)
    except Exception:  # noqa: BLE001
        pass
    return None


def pick_image(doc):
    """First card-friendly guide screenshot -> (abs_url, dims) or banner."""
    sized = []
    for rel in FIGURE_RE.findall(doc):
        sized.append((rel, image_size(os.path.join(ROOT, rel))))
    # prefer the first screenshot that reads well as a share card
    for rel, d in sized:
        if d and d[0] >= 300 and d[1] >= 150 and 0.4 <= d[0] / d[1] <= 4.0:
            return f"{BASE}/{rel}", d
    for rel, d in sized:          # else first one with a known size
        if d:
            return f"{BASE}/{rel}", d
    if sized:                     # else first one, dims unknown
        return f"{BASE}/{sized[0][0]}", None
    return BANNER, BANNER_DIMS    # no screenshots -> banner


def description(htmltext, fallback):
    m = DESC_RE.search(htmltext)
    if m:
        return text(m.group(1))
    for m in FIRST_P_RE.finditer(htmltext):
        t = text(m.group(1))
        if len(t) > 30:
            return (t[:147] + "…") if len(t) > 150 else t
    return fallback


def og_block(title, desc, url, og_type, image, dims):
    t, d = attr(title), attr(desc)
    dim_tags = ""
    if dims:
        dim_tags = (f'<meta property="og:image:width" content="{dims[0]}">\n'
                    f'<meta property="og:image:height" content="{dims[1]}">\n')
    return (
        f"{START}\n"
        f'<meta property="og:type" content="{og_type}">\n'
        f'<meta property="og:site_name" content="{attr(SITE)}">\n'
        f'<meta property="og:locale" content="ko_KR">\n'
        f'<meta property="og:title" content="{t}">\n'
        f'<meta property="og:description" content="{d}">\n'
        f'<meta property="og:url" content="{url}">\n'
        f'<meta property="og:image" content="{image}">\n'
        f"{dim_tags}"
        f'<meta name="twitter:card" content="summary_large_image">\n'
        f'<meta name="twitter:title" content="{t}">\n'
        f'<meta name="twitter:description" content="{d}">\n'
        f'<meta name="twitter:image" content="{image}">\n'
        f"{END}")


def process(path, url, og_type, fallback_desc, use_banner=False):
    with open(path, encoding="utf-8") as f:
        doc = f.read()
    doc = BLOCK_RE.sub("", doc)
    tm = TITLE_RE.search(doc)
    title = text(tm.group(1)) if tm else SITE
    desc = description(doc, fallback_desc)
    image, dims = (BANNER, BANNER_DIMS) if use_banner else pick_image(doc)
    block = "\n" + og_block(title, desc, url, og_type, image, dims) + "\n"
    doc = re.sub(r"\s*</head>", block + "</head>", doc, count=1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(doc)
    return image


def main():
    fb = "Legends of Idleon 클래스·스킬·월드 공략 한글 번역본 (이미지 포함)."
    process(os.path.join(ROOT, "index.html"), BASE + "/", "website", fb,
            use_banner=True)
    own = banner = 0
    for g in sorted(glob.glob(os.path.join(ROOT, "guides", "*.html"))):
        slug = os.path.basename(g)
        img = process(g, f"{BASE}/guides/{slug}", "article", fb)
        if img == BANNER:
            banner += 1
        else:
            own += 1
    print(f"OG tags injected: index + {own + banner} guides")
    print(f"  guides using own screenshot: {own}")
    print(f"  guides falling back to banner: {banner}")


if __name__ == "__main__":
    main()
