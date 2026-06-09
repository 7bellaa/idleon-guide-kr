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
# matches a block plus the single leading newline it owns — byte-stable across
# re-runs (does NOT swallow the following line's indentation)
MARK_BLOCK_RE = re.compile(
    r"\n?" + re.escape(MARK_START) + r".*?" + re.escape(MARK_END), re.S)

# small game-asset icons injected inside table cells
ICO_START = "<!--glf-ico-->"
ICO_END = "<!--/glf-ico-->"
ICO_BLOCK_RE = re.compile(
    re.escape(ICO_START) + r".*?" + re.escape(ICO_END), re.S)

TABLE_RE = re.compile(r"<table\b.*?</table>", re.S | re.I)
ROW_RE = re.compile(r"<tr\b.*?</tr>", re.S | re.I)
CELL_RE = re.compile(r"<(t[dh])\b[^>]*>(.*?)</\1>", re.S | re.I)


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
def wrap_block(inner):
    """Wrap inner HTML in markers with exactly one owned leading newline."""
    return f"\n{MARK_START}\n{inner}\n{MARK_END}"


def figure_inner(slug, fname, alt):
    alt_attr = html.escape(alt, quote=True)
    return (f'<figure class="guide-img">'
            f'<img src="../assets/images/{slug}/{fname}" '
            f'alt="{alt_attr}" loading="lazy"></figure>')


def gallery_html(slug, items):
    figs = "\n".join(figure_inner(slug, it["fname"], it["alt"]) for it in items)
    return wrap_block(
        f'<section class="guide-gallery"><h2>이미지</h2>\n{figs}\n</section>')


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

    # collect (offset, order_within_section, figure) so we can apply later
    inserts = []
    for sec, items in by_section.items():
        if sec == 0:
            # intro images: just before the first heading (after intro text)
            base = headings[0].start() if headings else len(doc)
            for i, it in enumerate(items):
                inserts.append((base, i, figure_inner(slug, it["fname"], it["alt"])))
            continue
        start = headings[sec - 1].end()
        end = headings[sec].start() if sec < len(headings) else content_end
        cands = section_anchors(doc, start, end)
        for i, it in enumerate(items):
            off = min(cands, key=lambda c: abs(c[1] - it["frac"]))[0]
            inserts.append((off, i, figure_inner(slug, it["fname"], it["alt"])))

    # group figures landing on the same offset into one marker block (ordered)
    grouped = {}
    for off, order, fig in inserts:
        grouped.setdefault(off, []).append((order, fig))
    merged = [(off, wrap_block("\n".join(f for _, f in sorted(items))))
              for off, items in grouped.items()]

    # apply high->low so earlier offsets stay valid
    for off, block in sorted(merged, key=lambda x: x[0], reverse=True):
        doc = doc[:off] + block + doc[off:]
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
# small game-asset icons -> injected into the matching translated table cells
# --------------------------------------------------------------------------- #
def cell_icon_urls(inner):
    """Ordered, de-duplicated small-icon URLs inside one table cell.

    The source emits each lazy icon twice (placeholder + <noscript> copy), so
    de-dupe by resolved URL while preserving first-seen order.
    """
    seen = set()
    urls = []
    for m in IMG_TAG_RE.finditer(inner):
        a = attrs_of(m.group(0))
        u = real_url(a)
        if not u or not SMALL_NAME_RE.search(u.split("?")[0]):
            continue
        if u in seen:
            continue
        seen.add(u)
        urls.append(u)
    return urls


def table_shape(table_html):
    """[cells-per-row, ...] — a structural fingerprint for alignment."""
    return [len(CELL_RE.findall(r)) for r in ROW_RE.findall(table_html)]


def original_cell_icons(content):
    """
    For the original article, return a list (per table) of
    {(row, col): [icon_url, ...]} plus each table's shape.
    """
    tables = []
    for t in TABLE_RE.findall(content):
        cells = {}
        for r, row in enumerate(ROW_RE.findall(t)):
            for c, cm in enumerate(CELL_RE.finditer(row)):
                urls = cell_icon_urls(cm.group(2))
                if urls:
                    cells[(r, c)] = urls
        tables.append((cells, table_shape(t)))
    return tables


def ico_html(slug, fnames):
    imgs = "".join(
        f'<img class="ico" src="../assets/images/{slug}/{f}" alt="" '
        f'loading="lazy">' for f in fnames)
    return f"{ICO_START}{imgs}{ICO_END}"


def inject_icons(doc, slug, content, dest_dir, args):
    """
    Inject small icons into translated table cells by table/row/cell position.
    Returns (new_doc, n_icons, n_tables_skipped).

    Safety: only inject when the guide's table count matches the original; for
    each table, only when its row/cell shape matches. Mismatches are skipped
    and counted (never mis-injected into the wrong table).
    """
    otables = original_cell_icons(content)
    if not any(cells for cells, _ in otables):
        return doc, 0, 0

    region = re.search(r"<main\b.*?</main>", doc, re.S)
    lo, hi = (region.start(), region.end()) if region else (0, len(doc))
    ttable_spans = [m for m in TABLE_RE.finditer(doc, lo, hi)]

    # guide-level guard: table counts must match to trust index alignment
    if len(ttable_spans) != len(otables):
        n_icons = sum(len(u) for cells, _ in otables for u in cells.values())
        return doc, 0, len([1 for cells, _ in otables if cells])  # all skipped

    inserts = []          # (offset, html)
    n_icons = 0
    skipped = 0
    for i, (ocells, oshape) in enumerate(otables):
        if not ocells:
            continue
        tspan = ttable_spans[i]
        ttable = doc[tspan.start():tspan.end()]
        if table_shape(ttable) != oshape:
            skipped += 1
            continue
        # walk translated rows/cells, collecting absolute inner-start offsets
        for r, rowm in enumerate(ROW_RE.finditer(doc, tspan.start(), tspan.end())):
            for c, cm in enumerate(CELL_RE.finditer(doc, rowm.start(), rowm.end())):
                urls = ocells.get((r, c))
                if not urls:
                    continue
                fnames = []
                for u in urls:
                    local = download(u, u, dest_dir, allow=not args.no_download)
                    if local:
                        fnames.append(local)
                if not fnames:
                    continue
                inner_start = cm.start(2)   # right after the <td ...> open tag
                inserts.append((inner_start, ico_html(slug, fnames)))
                n_icons += len(fnames)

    for off, block in sorted(inserts, key=lambda x: x[0], reverse=True):
        doc = doc[:off] + block + doc[off:]
    return doc, n_icons, skipped


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def process(path, args):
    fname = os.path.basename(path)
    slug = fname[:-5] if fname.endswith(".html") else fname
    with open(path, encoding="utf-8") as f:
        doc = f.read()

    base = {"slug": slug, "status": "no-source", "imgs": 0, "icons": 0,
            "heads": 0, "tbl_skipped": 0}

    m = SOURCE_RE.search(doc)
    if not m:
        return base
    raw = fetch(m.group(1), os.path.join(CACHE_DIR, slug + ".html"),
                allow_network=not args.no_fetch)
    if not raw:
        return {**base, "status": "fetch-failed"}

    content = isolate_content(raw)
    dest_dir = os.path.join(IMAGES_DIR, slug)
    orig_headings = heading_count(content)

    # idempotent: drop only the blocks the enabled passes will re-create, so a
    # single-pass run (e.g. --no-bigimg) leaves the other pass's blocks intact
    if not args.no_bigimg:
        doc = MARK_BLOCK_RE.sub("", doc)
    if not args.no_icons:
        doc = ICO_BLOCK_RE.sub("", doc)

    # --- big-image pass ---
    status = "no-images"
    n_imgs = 0
    if not args.no_bigimg:
        placed = []
        for im in extract_images(content):
            local = download(im["fullres"], im["url"], dest_dir,
                             allow=not args.no_download)
            if local:
                placed.append({"section": im["section"], "fname": local,
                               "alt": im["alt"], "frac": im["frac"]})
        if placed:
            result = insert_aligned(doc, slug, placed)
            if result is None:
                doc, n_imgs = insert_gallery(doc, slug, placed)
                status = "gallery"
            else:
                doc, n_imgs = result
                status = "aligned"

    # --- small-icon pass ---
    n_icons = tbl_skipped = 0
    if not args.no_icons:
        doc, n_icons, tbl_skipped = inject_icons(doc, slug, content,
                                                 dest_dir, args)

    if not args.dry_run:
        with open(path, "w", encoding="utf-8") as f:
            f.write(doc)
    return {"slug": slug, "status": status, "imgs": n_imgs, "icons": n_icons,
            "heads": orig_headings, "tbl_skipped": tbl_skipped}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="process a single guide slug (no .html)")
    ap.add_argument("--no-fetch", action="store_true",
                    help="use cache only, never hit the network")
    ap.add_argument("--no-download", action="store_true",
                    help="skip image download (plan/positions only)")
    ap.add_argument("--dry-run", action="store_true",
                    help="don't write the guide files")
    ap.add_argument("--no-icons", action="store_true",
                    help="skip the small table-icon pass")
    ap.add_argument("--no-bigimg", action="store_true",
                    help="skip the big-image pass (icons only)")
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

    log(f"{'guide':45} {'status':12} {'imgs':>5} {'icons':>6} {'head':>5}")
    log("-" * 80)
    review = []
    totals = {"aligned": 0, "gallery": 0, "imgs": 0, "icons": 0}
    for p in paths:
        r = process(p, args)
        log(f"{r['slug']:45} {r['status']:12} {r['imgs']:5d} "
            f"{r['icons']:6d} {r['heads']:5d}")
        totals["imgs"] += r["imgs"]
        totals["icons"] += r["icons"]
        if r["status"] in ("aligned", "gallery"):
            totals[r["status"]] += 1
        if r["status"] == "gallery":
            review.append((r["slug"], "big-image gallery fallback"))
        if r["tbl_skipped"]:
            review.append((r["slug"], f"{r['tbl_skipped']} table(s) skipped (shape mismatch)"))

    log("-" * 80)
    log(f"aligned guides: {totals['aligned']}   gallery-fallback: {totals['gallery']}   "
        f"images placed: {totals['imgs']}   icons placed: {totals['icons']}")
    if review:
        log("\nNEEDS MANUAL REVIEW:")
        for slug, note in review:
            log(f"  {slug}: {note}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
