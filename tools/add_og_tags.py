#!/usr/bin/env python3
"""
Inject Open Graph + Twitter Card meta tags into index.html and every guide so
shared links show a rich preview (KakaoTalk, Discord, Twitter, Facebook, ...).

All pages share one branded preview image (assets/og-image.png, 1200x630);
each page gets its own title / description / canonical url. Idempotent: the
block is wrapped in markers and regenerated on each run.

Usage: python3 tools/add_og_tags.py
"""
import glob
import html
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = "https://7bellaa.github.io/idleon-guide-kr"
OG_IMAGE = f"{BASE}/assets/og-image.png"
SITE = "Idleon 빌드 가이드 (한글)"

START, END = "<!-- og:start -->", "<!-- og:end -->"
BLOCK_RE = re.compile(r"\s*" + re.escape(START) + r".*?" + re.escape(END), re.S)
TITLE_RE = re.compile(r"<title>(.*?)</title>", re.S | re.I)
DESC_RE = re.compile(r'<meta\s+name="description"\s+content="([^"]*)"', re.I)
FIRST_P_RE = re.compile(r"<p[^>]*>(.*?)</p>", re.S | re.I)


def text(s):
    """Strip tags, unescape entities, collapse whitespace."""
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def attr(s):
    return html.escape(s, quote=True)


def description(htmltext, fallback):
    m = DESC_RE.search(htmltext)
    if m:
        return text(m.group(1))
    for m in FIRST_P_RE.finditer(htmltext):
        t = text(m.group(1))
        if len(t) > 30:                       # skip tiny/notice fragments
            return (t[:147] + "…") if len(t) > 150 else t
    return fallback


def og_block(title, desc, url, og_type):
    t, d = attr(title), attr(desc)
    return (
        f"{START}\n"
        f'<meta property="og:type" content="{og_type}">\n'
        f'<meta property="og:site_name" content="{attr(SITE)}">\n'
        f'<meta property="og:locale" content="ko_KR">\n'
        f'<meta property="og:title" content="{t}">\n'
        f'<meta property="og:description" content="{d}">\n'
        f'<meta property="og:url" content="{url}">\n'
        f'<meta property="og:image" content="{OG_IMAGE}">\n'
        f'<meta property="og:image:width" content="1200">\n'
        f'<meta property="og:image:height" content="630">\n'
        f'<meta name="twitter:card" content="summary_large_image">\n'
        f'<meta name="twitter:title" content="{t}">\n'
        f'<meta name="twitter:description" content="{d}">\n'
        f'<meta name="twitter:image" content="{OG_IMAGE}">\n'
        f"{END}")


def process(path, url, og_type, fallback_desc):
    with open(path, encoding="utf-8") as f:
        doc = f.read()
    doc = BLOCK_RE.sub("", doc)                # idempotent: drop prior block
    tm = TITLE_RE.search(doc)
    title = text(tm.group(1)) if tm else SITE
    desc = description(doc, fallback_desc)
    block = "\n" + og_block(title, desc, url, og_type) + "\n"
    doc = re.sub(r"\s*</head>", block + "</head>", doc, count=1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(doc)
    return title


def main():
    fb = "Legends of Idleon 클래스·스킬·월드 공략 한글 번역본 (이미지 포함)."
    process(os.path.join(ROOT, "index.html"), BASE + "/", "website", fb)
    n = 1
    for g in sorted(glob.glob(os.path.join(ROOT, "guides", "*.html"))):
        slug = os.path.basename(g)
        process(g, f"{BASE}/guides/{slug}", "article", fb)
        n += 1
    print(f"OG/Twitter tags injected into {n} pages (index + {n-1} guides)")
    print(f"preview image: {OG_IMAGE}")


if __name__ == "__main__":
    main()
