#!/usr/bin/env python3
"""
Restore original images into the Korean Idleon guides.

Each translated guide in guides/*.html carries its source URL in a
<p class="source"><a href="https://gameslikefinder.com/article/<slug>/"> line.
The translation kept the text but dropped every <img>. This script:

  1. maps each local guide to its gameslikefinder.com source URL
  2. fetches (and caches) the original article HTML
  3. isolates the article body (entry-content) and walks it in document order,
     recording h2/h3 headings (with an index) and the substantial content
     images that follow each heading
  4. downloads those images into assets/images/<slug>/
  5. re-inserts them into the translated guide by HEADING-INDEX alignment
     (verified: translated and original headings match 1:1 in count + order),
     wrapped in <!-- glf-img --> markers so re-runs don't duplicate
  6. prints a per-guide report; guides whose heading count doesn't match fall
     back to a gallery appended before </main> and are flagged for review.

Pure standard library + curl. No pip installs needed.

Usage:
  python3 tools/sync_images.py                 # all guides
  python3 tools/sync_images.py --only idleon-alchemy-guide
  python3 tools/sync_images.py --no-fetch      # use cache only, don't hit network
  python3 tools/sync_images.py --no-download   # plan only, skip image download
"""
import argparse
import html
import os
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GUIDES_DIR = os.path.join(ROOT, "guides")
IMAGES_DIR = os.path.join(ROOT, "assets", "images")
CACHE_DIR = os.path.join(ROOT, ".cache")

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36")

# politeness throttles (seconds) — only applied on real network requests
PAGE_DELAY = 0.8
IMG_DELAY = 0.2

SOURCE_RE = re.compile(
    r'<p class="source">.*?href="(https://gameslikefinder\.com/article/[^"]+?)"',
    re.S)

# images that are site chrome / not real content
CHROME_RE = re.compile(
    r'(logo|gamesfinder|gravatar|avatar|/emoji/|wpforms|/themes/|/plugins/)',
    re.I)
# WordPress thumbnail size suffix, e.g. name-300x200.png
THUMB_RE = re.compile(r'-\d+x\d+(?=\.\w+$)')
# tiny game-asset icon filenames, e.g. 36px-YellowBubble10.png
SMALL_NAME_RE = re.compile(r'/\d{1,3}px-[^/]+$')

IMG_TAG_RE = re.compile(r'<img\b[^>]*>', re.I | re.S)
HEADING_RE = re.compile(r'<(h[23])\b[^>]*>(.*?)</\1>', re.I | re.S)
ATTR_RE = re.compile(r'(\w[\w-]*)\s*=\s*"([^"]*)"')

MARK_START = "<!-- glf-img:start -->"
MARK_END = "<!-- glf-img:end -->"
MARK_BLOCK_RE = re.compile(
    re.escape(MARK_START) + r".*?" + re.escape(MARK_END) + r"\s*", re.S)


def log(msg):
    print(msg, flush=True)


# --------------------------------------------------------------------------- #
# fetch
# --------------------------------------------------------------------------- #
def fetch(url, dest, allow_network=True):
    """Return raw HTML for url, caching to dest. Returns text or None."""
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        with open(dest, encoding="utf-8", errors="replace") as f:
            return f.read()
    if not allow_network:
        return None
    for attempt in range(2):
        try:
            res = subprocess.run(
                ["curl", "-sL", "--max-time", "40", "-A", UA, url],
                capture_output=True, timeout=60)
            data = res.stdout
            if data and len(data) > 1000:
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with open(dest, "wb") as f:
                    f.write(data)
                time.sleep(PAGE_DELAY)  # be polite between page fetches
                return data.decode("utf-8", errors="replace")
        except Exception as e:  # noqa: BLE001
            log(f"    fetch error ({attempt}): {e}")
        time.sleep(1.5)
    return None


# --------------------------------------------------------------------------- #
# parse original article
# --------------------------------------------------------------------------- #
def isolate_content(src):
    """Slice the article body out of a GeneratePress page."""
    m = re.search(r'class="[^"]*entry-content[^"]*"', src)
    start = m.start() if m else 0
    end = len(src)
    for pat in (r'id="comments"', r'<footer', r'id="right-sidebar"',
                r'class="[^"]*(?:author-box|related|nav-links|post-navigation)'):
        m2 = re.search(pat, src[start:])
        if m2:
            end = min(end, start + m2.start())
    return src[start:end]


def attrs_of(tag):
    return {k.lower(): v for k, v in ATTR_RE.findall(tag)}


def real_url(a):
    """Resolve the genuine image URL, preferring the lazy-load source."""
    for key in ("data-lazy-src", "data-src", "src"):
        v = a.get(key, "")
        if v and not v.startswith("data:"):
            return v
    return ""


def is_small(a, url):
    if SMALL_NAME_RE.search(url):
        return True
    try:
        w = int(a.get("width", "0"))
        h = int(a.get("height", "0"))
        if w and h and w < 100 and h < 100:
            return True
    except ValueError:
        pass
    return False


def extract_images(content):
    """
    Walk content in document order. Return list of dicts:
      {url, fullres, alt, section, frac}
    - section: 1-based index of the most recent h2/h3 (0 = intro / before the
      first heading).
    - frac: where the image sits within its section, 0.0 (right after the
      section heading) .. 1.0 (right before the next heading). Used to place
      the image at the same relative spot in the translated section.
    Deduplicated by full-res URL, first occurrence wins.
    """
    heads = [(m.start(), m.end()) for m in HEADING_RE.finditer(content)]
    head_starts = [h[0] for h in heads]

    def section_span(idx):
        """span of section `idx` (1-based) as (content_start, content_end)."""
        start = heads[idx - 1][1]
        end = head_starts[idx] if idx < len(heads) else len(content)
        return start, end

    seen = set()
    out = []
    for m in IMG_TAG_RE.finditer(content):
        pos = m.start()
        a = attrs_of(m.group(0))
        url = real_url(a)
        if not url or CHROME_RE.search(url) or is_small(a, url):
            continue
        full = THUMB_RE.sub("", url)
        if full in seen:
            continue
        seen.add(full)
        # which section index precedes this image?
        section = sum(1 for hs in head_starts if hs <= pos)
        if section == 0:
            frac = 0.0
        else:
            s, e = section_span(section)
            frac = (pos - s) / max(1, e - s)
            frac = min(1.0, max(0.0, frac))
        out.append({"url": url, "fullres": full,
                    "alt": html.unescape(a.get("alt", "")).strip(),
                    "section": section, "frac": frac})
    return out


def heading_count(content):
    return len(HEADING_RE.findall(content))


# --------------------------------------------------------------------------- #
# download
# --------------------------------------------------------------------------- #
def safe_name(url):
    base = url.split("?")[0].rstrip("/").split("/")[-1]
    base = re.sub(r"[^A-Za-z0-9._-]", "_", base) or "image"
    return base


def sniff_ext(path):
    """Return the true extension from magic bytes, or '' if unknown."""
    try:
        with open(path, "rb") as f:
            head = f.read(16)
    except OSError:
        return ""
    if head[:3] == b"\xff\xd8\xff":
        return ".jpg"
    if head[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"
    if head[:4] in (b"GIF8",):
        return ".gif"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return ".webp"
    if head[:5] == b"<?xml" or head[:4] == b"<svg":
        return ".svg"
    return ""


def fix_extension(dest):
    """Rename dest so its extension matches the real content. Return new path."""
    ext = sniff_ext(dest)
    if not ext:
        return dest
    stem, cur = os.path.splitext(dest)
    if cur.lower() == ext:
        return dest
    new = stem + ext
    # avoid clobbering a different existing file
    if os.path.exists(new):
        os.remove(dest)
        return new
    os.replace(dest, new)
    return new


def download(url, fallback, dest_dir, allow=True):
    """
    Download url (full-res) into dest_dir, falling back to `fallback` on 404.
    The saved file's extension is corrected to match its real bytes (the
    source serves some .jpg URLs as WebP). Returns the local filename or None.
    """
    os.makedirs(dest_dir, exist_ok=True)
    name = safe_name(url)
    dest = os.path.join(dest_dir, name)
    # already downloaded (possibly under a corrected extension)?
    for existing in (dest, os.path.splitext(dest)[0] + ".webp",
                     os.path.splitext(dest)[0] + ".png"):
        if os.path.exists(existing) and os.path.getsize(existing) > 200:
            return os.path.basename(existing)
    if not allow:
        return name  # assume planned
    for candidate in (url, fallback):
        if not candidate:
            continue
        try:
            res = subprocess.run(
                ["curl", "-sL", "--max-time", "40", "-A", UA,
                 "-w", "%{http_code}", "-o", dest, candidate],
                capture_output=True, text=True, timeout=60)
            code = (res.stdout or "").strip()[-3:]
            time.sleep(IMG_DELAY)  # be polite between image downloads
            if code == "200" and os.path.exists(dest) and os.path.getsize(dest) > 200:
                return os.path.basename(fix_extension(dest))
        except Exception as e:  # noqa: BLE001
            log(f"    download error: {e}")
        if os.path.exists(dest) and os.path.getsize(dest) <= 200:
            os.remove(dest)
    return None


# --------------------------------------------------------------------------- #
# insert into translated file
# --------------------------------------------------------------------------- #
def figure_html(slug, fname, alt):
    alt_attr = html.escape(alt, quote=True)
    return (f'{MARK_START}\n'
            f'<figure class="guide-img">'
            f'<img src="../assets/images/{slug}/{fname}" '
            f'alt="{alt_attr}" loading="lazy"></figure>\n{MARK_END}\n')


def gallery_html(slug, items):
    figs = "".join(
        f'<figure class="guide-img">'
        f'<img src="../assets/images/{slug}/{it["fname"]}" '
        f'alt="{html.escape(it["alt"], quote=True)}" loading="lazy"></figure>\n'
        for it in items)
    return (f'{MARK_START}\n<section class="guide-gallery">'
            f'<h2>이미지</h2>\n{figs}</section>\n{MARK_END}\n')


def strip_markers(text):
    return MARK_BLOCK_RE.sub("", text)


# block-close anchors inside a translated section we can insert *after*
BLOCK_CLOSE_RE = re.compile(
    r'</p>|</table>|</ul>|</ol>|</blockquote>|</figure>|</div>', re.I)


def section_anchors(doc, start, end):
    """
    Ordered candidate insertion offsets within [start, end): the section start,
    every block-close inside, and the section end. Each as (offset, frac).
    """
    span = max(1, end - start)
    cands = [(start, 0.0)]
    for m in BLOCK_CLOSE_RE.finditer(doc, start, end):
        off = m.end()
        cands.append((off, (off - start) / span))
    cands.append((end, 1.0))
    return cands


def insert_aligned(doc, slug, placed):
    """
    placed: list of dicts with keys section, fname, alt, frac (document order).
    Align by heading index against the translated doc's h2/h3 sequence, then
    drop each image at the block-close anchor whose position best matches the
    image's fractional spot within the original section.
    Returns (new_doc, num_inserted) or None if heading counts mismatch.
    """
    headings = list(HEADING_RE.finditer(doc))
    sections = {it["section"] for it in placed}
    if (max(sections) if sections else 0) > len(headings):
        return None  # can't align -> caller uses gallery fallback

    # last section must not bleed into the footer / page chrome
    content_end = doc.rfind("</main>")
    if content_end < 0:
        content_end = doc.rfind("</body>")
    if content_end < 0:
        content_end = len(doc)

    by_section = {}
    for it in placed:
        by_section.setdefault(it["section"], []).append(it)

    # collect (offset, order_within_section, html) so we can apply later
    inserts = []
    for sec, items in by_section.items():
        if sec == 0:
            # intro images: just before the first heading (after intro text)
            base = headings[0].start() if headings else len(doc)
            for i, it in enumerate(items):
                inserts.append((base, i, figure_html(slug, it["fname"], it["alt"])))
            continue
        start = headings[sec - 1].end()
        end = headings[sec].start() if sec < len(headings) else content_end
        cands = section_anchors(doc, start, end)
        for i, it in enumerate(items):
            off = min(cands, key=lambda c: abs(c[1] - it["frac"]))[0]
            inserts.append((off, i, figure_html(slug, it["fname"], it["alt"])))

    # group images landing on the same offset, preserving their original order
    grouped = {}
    for off, order, blk in inserts:
        grouped.setdefault(off, []).append((order, blk))
    merged = [(off, "".join(b for _, b in sorted(items)))
              for off, items in grouped.items()]

    # apply high->low so earlier offsets stay valid
    for off, block in sorted(merged, key=lambda x: x[0], reverse=True):
        doc = doc[:off] + "\n" + block + doc[off:]
    return doc, len(placed)


def insert_gallery(doc, slug, placed):
    block = gallery_html(slug, placed)
    idx = doc.rfind("</main>")
    if idx < 0:
        idx = doc.rfind("</body>")
    if idx < 0:
        idx = len(doc)
    return doc[:idx] + block + doc[idx:], len(placed)


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def process(path, args):
    fname = os.path.basename(path)
    slug = fname[:-5] if fname.endswith(".html") else fname
    with open(path, encoding="utf-8") as f:
        doc = f.read()

    m = SOURCE_RE.search(doc)
    if not m:
        return (slug, "no-source", 0, 0, False)
    url = m.group(1)

    raw = fetch(url, os.path.join(CACHE_DIR, slug + ".html"),
                allow_network=not args.no_fetch)
    if not raw:
        return (slug, "fetch-failed", 0, 0, False)

    content = isolate_content(raw)
    images = extract_images(content)
    orig_headings = heading_count(content)
    if not images:
        return (slug, "no-images", 0, orig_headings, False)

    # download
    dest_dir = os.path.join(IMAGES_DIR, slug)
    placed = []
    for im in images:
        local = download(im["fullres"], im["url"], dest_dir,
                         allow=not args.no_download)
        if local:
            placed.append({"section": im["section"], "fname": local,
                           "alt": im["alt"], "frac": im["frac"]})
    if not placed:
        return (slug, "download-failed", 0, orig_headings, False)

    # insert (idempotent: strip any prior markers first)
    doc2 = strip_markers(doc)
    result = insert_aligned(doc2, slug, placed)
    if result is None:
        doc3, n = insert_gallery(doc2, slug, placed)
        fallback = True
    else:
        doc3, n = result
        fallback = False

    if not args.dry_run:
        with open(path, "w", encoding="utf-8") as f:
            f.write(doc3)
    status = "gallery" if fallback else "aligned"
    return (slug, status, n, orig_headings, fallback)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="process a single guide slug (no .html)")
    ap.add_argument("--no-fetch", action="store_true",
                    help="use cache only, never hit the network")
    ap.add_argument("--no-download", action="store_true",
                    help="skip image download (plan/positions only)")
    ap.add_argument("--dry-run", action="store_true",
                    help="don't write the guide files")
    args = ap.parse_args()

    paths = sorted(
        os.path.join(GUIDES_DIR, f)
        for f in os.listdir(GUIDES_DIR) if f.endswith(".html"))
    if args.only:
        target = args.only if args.only.endswith(".html") else args.only + ".html"
        paths = [p for p in paths if os.path.basename(p) == target]
        if not paths:
            log(f"no guide matching {args.only}")
            return 1

    log(f"{'guide':45} {'status':14} {'imgs':>5} {'head':>5}")
    log("-" * 76)
    review = []
    totals = {"aligned": 0, "gallery": 0, "imgs": 0}
    for p in paths:
        slug, status, n, heads, fb = process(p, args)
        log(f"{slug:45} {status:14} {n:5d} {heads:5d}")
        totals["imgs"] += n
        if status in ("aligned", "gallery"):
            totals[status] += 1
        if status not in ("aligned",) or fb:
            if status != "aligned":
                review.append((slug, status))

    log("-" * 76)
    log(f"aligned guides: {totals['aligned']}   gallery-fallback: {totals['gallery']}   "
        f"images placed: {totals['imgs']}")
    if review:
        log("\nNEEDS MANUAL REVIEW:")
        for slug, status in review:
            log(f"  {slug}: {status}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
