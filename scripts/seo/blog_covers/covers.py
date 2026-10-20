#!/usr/bin/env python3
"""Render the xerj.org blog covers: one "engineering field-log poster" per post.

Each post gets three files, all drawn from code (HTML + SVG, rasterised by
headless Chromium through Playwright), never from an image model:

    landing/og/blog-<slug>.png           1200x630  og:image / twitter:image
    landing/blog/covers/<slug>-hero.webp 1600x640  the cover at the top of the post
    landing/blog/covers/<slug>-thumb.webp 640x336  the card thumbnail on /blog/

Layout, type and colour are fixed for the series; only the halftone motif
(scripts/seo/blog_covers/motifs.py) and the words change per post. The words
live in POSTS below. Every number a cover shows must appear in its post.

    python3 scripts/seo/blog_covers/covers.py                 # all posts
    python3 scripts/seo/blog_covers/covers.py --only the-corpus-hub
    python3 scripts/seo/blog_covers/covers.py --contact /tmp/contact.png

Needs: pip install playwright pillow, plus a Chromium (`playwright install
chromium`, or point CHROME at an installed Chrome/Chromium binary). This is an
offline authoring tool, like the og-blog render note in ../assets/: CI does
not run it, the PNG/WebP outputs are committed. See README.md.
"""

from __future__ import annotations

import argparse
import html
import io
import os
import pathlib
import random
import shutil
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent.parent.parent
LANDING = REPO / "landing"
sys.path.insert(0, str(HERE))
from motifs import MOTIFS, disc  # noqa: E402

# ── brand tokens: literal values of landing/style.css :root (night theme) ────
TOKENS = {
    "bg": "#0b0b0d",      # --z-bg
    "ink": "#f4f2ec",     # --z-ink
    "mute": "#8a8680",    # --z-mute
    "faint": "#2b2a28",   # --z-faint
    "line": "#3a3836",    # --z-line
    "accent": "#ffc400",  # --z-accent
    "cmp": "#7f93aa",     # --z-cmp
}

# ── the series: one entry per post ───────────────────────────────────────────
# title     display face, set uppercase; keep it to the post's own title
# subtitle  yellow line under the title; a phrase lifted from the post
# date      the post's published date (pagedata.py `published`)
# motif     key into motifs.MOTIFS; the motif's docstring names its sources
# alt       alt text for the hero/thumb and og:image:alt: what the card shows
POSTS: list[dict[str, str]] = [
    dict(slug="does-xerj-beat-jev", date="2026-09-21", motif="jevbars",
         title="Does XERJ beat JEV?",
         subtitle="On the bill, outright. On FiQA, no.",
         alt="Cover: dot-bars of nDCG@10 for XERJ and BM25+Jev on SciFact (0.6993 vs 0.7410), NFCorpus (0.3448 vs 0.3312) and FiQA (0.2382 vs 0.3638), and the FiQA rerank bill, $0.6375 against $0 local"),
    dict(slug="jev-vs-a-bm25-vote", date="2026-09-22", motif="vote",
         title="A BM25 vote ties Jev on spam and beats it on intent",
         subtitle="Count your labels before you pay for a model.",
         alt="Cover: two grids of 500 Banking77 decisions, filled dots for correct answers: BM25 vote 0.9140, Jev 0.8240; SMS spam is a tie, 0.9840 vs 0.9880"),
    dict(slug="cutting-the-index-28-percent", date="2026-09-27", motif="index28",
         title="Cutting the index 28%",
         subtitle="Dissect first, write Rust second.",
         alt="Cover: a block of dots for the 5.52 MB index with the 3.99 MB index drawn inside it to scale, minus 28%, and bars for the .seg (minus 73.1%) and .meta (minus 93.1%) formats"),
    dict(slug="one-vulnerability-three-names", date="2026-09-27", motif="names",
         title="One vulnerability, three names",
         subtitle="Checksums prove integrity. They do not prove origin.",
         alt="Cover: the labels RUSTSEC-2021-0003, GHSA-43w2-9j62-hq99 and CVE-2021-25900 converging on one signed record; 4,107 filings to 1,950 records"),
    dict(slug="the-rc80-gates", date="2026-09-30", motif="gates",
         title="The rc.80 gates",
         subtitle="Measured in public, losses left in.",
         alt="Cover: a row of ten gates, one per feature: three pass, three fail, one split, one reported, two not measured"),
    dict(slug="the-corpus-hub", date="2026-10-01", motif="tiles",
         title="The Corpus Hub",
         subtitle="Pinned, licenced, signed, contributed by pull request.",
         alt="Cover: a wall of 100 pack tiles with the four launch corpora in yellow and a seal ring on the signed pack"),
    dict(slug="eval-scars-from-agent-memory", date="2026-10-07", motif="scars",
         title="Six eval scars from production agent memory",
         subtitle="If every query scores zero hits, suspect your mask.",
         alt="Cover: six scratch marks, one per eval pattern, tagged with the post's figures: recall@1, +2.75pt, group by qid, 0.87 vs 0.78, 4x unpaired, mask to zero hits"),
    dict(slug="the-exploit-hub", date="2026-10-08", motif="network",
         title="The exploit hub, tested on three fresh CVEs",
         subtitle="One query, exact attribution, wrong patch.",
         alt="Cover: a network of proof-of-concept documents; CVE-2026-23744 links to 36 PoCs, CVE-2026-105844 to one neighbouring exploit, CVE-2026-97332 to none"),
    dict(slug="corpus-hub-v2", date="2026-10-19", motif="route",
         title="Corpus Hub v2",
         subtitle="Ask the question, get the one pack that answers it.",
         alt="Cover: a wall of 245 faint pack tiles behind the 14 corpora of the signed catalogue; a question routes to the lz4 tile, whose 4.4 MB pack goes to a local node on port 9300; 1.72 to 2.27 s cold, 37 to 57 ms warm"),
]

SIZES = {"og": (1200, 630), "hero": (1600, 640)}
THUMB = (640, 336)


def font_url(name: str) -> str:
    return (HERE / "fonts" / name).as_uri()


CSS = """
@font-face { font-family: 'Big Shoulders Display'; font-weight: 100 900;
             src: url('%(display)s') format('truetype'); }
@font-face { font-family: 'JetBrains Mono'; font-weight: 100 800;
             src: url('%(mono)s') format('truetype'); }
* { box-sizing: border-box; margin: 0; padding: 0; }
html, body { background: %(bg)s; }
.card { position: relative; overflow: hidden; background: %(bg)s; color: %(ink)s;
        width: %(W)spx; height: %(H)spx; }
.bgsvg { position: absolute; inset: 0; }
.kicker { position: absolute; left: %(P)spx; top: %(P)spx; right: %(P)spx;
          font: 600 %(kfs)spx/1 'JetBrains Mono', monospace; letter-spacing: .14em;
          color: %(ink)s; display: flex; gap: 14px; align-items: center; }
.kicker .sq { width: 12px; height: 12px; background: %(accent)s; flex: none; }
.kicker .no { margin-left: auto; color: %(mute)s; }
.textcol { position: absolute; left: %(P)spx; top: %(ttop)spx; width: %(tw)spx;
           height: %(th)spx; display: flex; flex-direction: column; justify-content: center; }
h1 { font-family: 'Big Shoulders Display', sans-serif; font-weight: 900;
     text-transform: uppercase; line-height: .9; letter-spacing: .005em;
     color: %(ink)s; font-size: %(tfs)spx; }
.sub { margin-top: 22px; font-family: 'Big Shoulders Display', sans-serif; font-weight: 700;
       text-transform: uppercase; letter-spacing: .02em; line-height: 1.02;
       color: %(accent)s; font-size: %(sfs)spx; max-width: %(tw)spx; }
.rule { width: 72px; height: 3px; background: %(accent)s; margin: 0 0 22px; }
.motif { position: absolute; left: %(mx)spx; top: %(my)spx; }
.foot { position: absolute; left: %(P)spx; right: %(P)spx; bottom: %(fb)spx;
        border-top: 1px solid %(line)s; padding-top: 14px; display: flex;
        font: 500 %(ffs)spx/1 'JetBrains Mono', monospace; letter-spacing: .08em; color: %(mute)s; }
.foot b { color: %(ink)s; font-weight: 600; }
.foot .r { margin-left: auto; }
svg text { font-family: 'JetBrains Mono', monospace; }
.y { fill: %(accent)s; } .w { fill: %(ink)s; } .b { fill: %(cmp)s; }
.m { fill: %(mute)s; } .f { fill: %(line)s; }
.y-s { stroke: %(accent)s; } .w-s { stroke: %(ink)s; } .b-s { stroke: %(cmp)s; }
.m-s { stroke: %(mute)s; } .f-s { stroke: %(line)s; }
.bgfill { fill: %(bg)s; } .fa { fill: %(faint)s; }
svg text { paint-order: stroke; stroke: %(bg)s; stroke-width: 5px; stroke-linejoin: round; }
.lab { font-size: %(lfs)spx; font-weight: 600; letter-spacing: .1em; fill: %(mute)s; }
.lab.y { fill: %(accent)s; } .lab.w { fill: %(ink)s; } .lab.b { fill: %(cmp)s; }
.num { font-size: %(nfs)spx; font-weight: 600; letter-spacing: .02em; }
.num.y { fill: %(accent)s; } .num.b { fill: %(cmp)s; } .num.w { fill: %(ink)s; } .num.m { fill: %(mute)s; }
.tag { font-size: %(gfs)spx; font-weight: 700; letter-spacing: .06em; }
.tag.y { fill: %(accent)s; } .tag.w { fill: %(ink)s; } .tag.m { fill: %(mute)s; }
.big { font-family: 'Big Shoulders Display', sans-serif; font-weight: 900; font-size: %(bfs)spx; }
.ink { mix-blend-mode: screen; }
"""

FIT_JS = """
() => {
  const h1 = document.querySelector('h1'), col = document.querySelector('.textcol');
  let fs = parseFloat(getComputedStyle(h1).fontSize);
  while (col.scrollHeight > col.clientHeight + 1 && fs > 30) { fs -= 2; h1.style.fontSize = fs + 'px'; }
  return fs;
}
"""


def layout(kind: str) -> dict:
    W, H = SIZES[kind]
    if kind == "og":
        return dict(W=W, H=H, P=56, kfs=15, ttop=104, tw=500, th=410, tfs=92, sfs=30,
                    mx=610, my=112, mw=536, mh=400, fb=40, ffs=15, lfs=12, nfs=13, gfs=11, bfs=54)
    return dict(W=W, H=H, P=64, kfs=16, ttop=110, tw=640, th=410, tfs=104, sfs=32,
                mx=790, my=112, mw=746, mh=410, fb=40, ffs=15, lfs=13, nfs=14, gfs=12, bfs=64)


def background(W: int, H: int, seed: int) -> str:
    """Grid paper, crop marks and a fixed-seed risograph grain."""
    marks = []
    for (x, y) in [(22, 22), (W - 22, 22), (22, H - 22), (W - 22, H - 22)]:
        marks.append(f'<line x1="{x-9}" y1="{y}" x2="{x+9}" y2="{y}" stroke="{TOKENS["line"]}"/>'
                     f'<line x1="{x}" y1="{y-9}" x2="{x}" y2="{y+9}" stroke="{TOKENS["line"]}"/>'
                     f'<circle cx="{x}" cy="{y}" r="5" fill="none" stroke="{TOKENS["line"]}"/>')
    return f"""<svg class="bgsvg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg">
<defs>
 <pattern id="grid" width="16" height="16" patternUnits="userSpaceOnUse">
  <circle cx="8" cy="8" r="1" fill="#1d1c1b"/></pattern>
 <filter id="grain" x="0" y="0" width="100%" height="100%">
  <feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves="2" seed="{seed}"/>
  <feColorMatrix values="0 0 0 0 0.96  0 0 0 0 0.95  0 0 0 0 0.92  0 0 0 0.9 -0.35"/>
 </filter>
</defs>
<rect width="{W}" height="{H}" fill="url(#grid)"/>
{''.join(marks)}
</svg>"""


def grain_overlay(W: int, H: int, seed: int) -> str:
    """Risograph speckle: sparse, fixed-seed flecks of paper ink. Sparse on
    purpose; per-pixel noise would triple the PNG size for no visible gain."""
    rng = random.Random(seed)
    flecks = "".join(
        f'<rect x="{rng.randrange(W)}" y="{rng.randrange(H)}" width="{rng.choice((1, 1, 2))}" height="1"/>'
        for _ in range(W * H // 900))
    return (f'<svg class="bgsvg" width="{W}" height="{H}" style="opacity:.22;pointer-events:none" '
            f'xmlns="http://www.w3.org/2000/svg"><g fill="{TOKENS["mute"]}">{flecks}</g></svg>')


def page(post: dict, kind: str, number: int, total: int) -> str:
    L = layout(kind)
    seed = sum(post["slug"].encode()) % 997
    rng = random.Random(post["slug"] + ":" + kind)
    motif = MOTIFS[post["motif"]](L["mw"], L["mh"], rng)
    # the poster's ground: one big, faint halftone sun behind every motif
    R = max(L["mw"], L["mh"]) * 0.62
    wash = disc(L["mw"] * 0.62, L["mh"] * 0.50, R, 13, "fa", lambda d: 0.55 * (1 - d) ** 1.4)
    # misregistration: the yellow plate sits 1.5px off the paper plate, as on a riso
    motif_svg = (f'<svg class="motif" width="{L["mw"]}" height="{L["mh"] + 4}" '
                 f'viewBox="0 0 {L["mw"]} {L["mh"] + 4}" overflow="visible" xmlns="http://www.w3.org/2000/svg">'
                 f'<g>{wash}</g><g filter="url(#rough)">{motif}</g>'
                 f'<defs><filter id="rough"><feTurbulence type="fractalNoise" baseFrequency="0.6" seed="{seed}" result="n"/>'
                 f'<feDisplacementMap in="SourceGraphic" in2="n" scale="1.6"/></filter></defs></svg>')
    css = CSS % {**TOKENS, **L, "display": font_url("BigShouldersDisplay-wght.ttf"),
                 "mono": font_url("JetBrainsMono-wght.ttf")}
    e = html.escape
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>{css}</style></head><body>
<div class="card">
{background(L["W"], L["H"], seed)}
<div class="kicker"><span class="sq"></span><span>XERJ · ENGINEERING LOG · {e(post["date"])}</span>
<span class="no">No. {number:02d} / {total:02d}</span></div>
<div class="textcol"><div class="rule"></div><h1>{e(post["title"])}</h1><p class="sub">{e(post["subtitle"])}</p></div>
{motif_svg}
<div class="foot"><span><b>xerj.org/blog/{e(post["slug"])}</b></span><span class="r">FIELD LOG · DRAWN FROM THE POST'S OWN NUMBERS</span></div>
{grain_overlay(L["W"], L["H"], seed)}
</div></body></html>"""


def chrome_path() -> str | None:
    if os.environ.get("CHROME"):
        return os.environ["CHROME"]
    for c in ("google-chrome", "chromium", "chromium-browser"):
        p = shutil.which(c)
        if p:
            return p
    return None


def save_png(img, path: pathlib.Path) -> None:
    from PIL import Image
    q = img.convert("RGB").quantize(colors=96, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    path.parent.mkdir(parents=True, exist_ok=True)
    q.save(path, optimize=True)


def save_webp(img, path: pathlib.Path) -> None:
    """Lossless WebP of the same 96-colour image the PNG gets: flat inks and
    dot screens compress far better losslessly than with lossy WebP, and the
    dots stay crisp."""
    from PIL import Image
    q = img.convert("RGB").quantize(colors=96, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    path.parent.mkdir(parents=True, exist_ok=True)
    q.convert("RGB").save(path, "WEBP", lossless=True, quality=100, method=6)


def render(posts: list[dict], series_total: int, numbers: dict[str, int],
           html_dir: pathlib.Path | None) -> dict[str, dict]:
    from playwright.sync_api import sync_playwright
    from PIL import Image
    out: dict[str, dict] = {}
    with sync_playwright() as p:
        kw = {}
        exe = chrome_path()
        try:
            browser = p.chromium.launch()
        except Exception:
            if not exe:
                raise
            browser = p.chromium.launch(executable_path=exe)
        for post in posts:
            out[post["slug"]] = {}
            for kind, (W, H) in SIZES.items():
                pg = browser.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
                doc = page(post, kind, numbers[post["slug"]], series_total)
                if html_dir:
                    html_dir.mkdir(parents=True, exist_ok=True)
                    (html_dir / f"{post['slug']}-{kind}.html").write_text(doc)
                tmp = HERE / f".render-{kind}.html"
                tmp.write_text(doc)
                pg.goto(tmp.as_uri())
                pg.evaluate("document.fonts.ready")
                pg.wait_for_timeout(150)
                pg.evaluate(FIT_JS)
                png = pg.locator(".card").screenshot(type="png")
                tmp.unlink()
                pg.close()
                out[post["slug"]][kind] = Image.open(io.BytesIO(png)).convert("RGB")
        browser.close()
    return out


def write(images: dict[str, dict]) -> list[pathlib.Path]:
    from PIL import Image
    written = []
    for slug, imgs in images.items():
        og = LANDING / "og" / f"blog-{slug}.png"
        save_png(imgs["og"], og)
        hero = LANDING / "blog" / "covers" / f"{slug}-hero.webp"
        save_webp(imgs["hero"], hero)
        thumb = LANDING / "blog" / "covers" / f"{slug}-thumb.webp"
        # the thumbnail is a downscale, full of in-between tones: lossy wins there
        thumb.parent.mkdir(parents=True, exist_ok=True)
        imgs["og"].resize(THUMB, Image.LANCZOS).save(thumb, "WEBP", quality=80, method=6)
        written += [og, hero, thumb]
    return written


def contact_sheet(images: dict[str, dict], path: pathlib.Path) -> None:
    from PIL import Image
    cols = 3
    cw, ch = 600, 315
    gap = 24
    rows = (len(images) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cw + (cols + 1) * gap, rows * ch + (rows + 1) * gap), (0x1d, 0x1c, 0x1b))
    for n, (slug, imgs) in enumerate(images.items()):
        r, c = divmod(n, cols)
        sheet.paste(imgs["og"].resize((cw, ch), Image.LANCZOS), (gap + c * (cw + gap), gap + r * (ch + gap)))
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(path, optimize=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--only", action="append", help="render only this slug (repeatable)")
    ap.add_argument("--contact", type=pathlib.Path, help="also write a contact sheet PNG of every og card")
    ap.add_argument("--html-dir", type=pathlib.Path, help="keep the intermediate HTML pages here")
    a = ap.parse_args()
    numbers = {p["slug"]: i + 1 for i, p in enumerate(POSTS)}
    todo = [p for p in POSTS if not a.only or p["slug"] in a.only]
    if a.only and len(todo) != len(a.only):
        known = {p["slug"] for p in POSTS}
        print("unknown slug(s): " + ", ".join(s for s in a.only if s not in known), file=sys.stderr)
        return 2
    images = render(todo, len(POSTS), numbers, a.html_dir)
    for f in write(images):
        print(f"wrote {f.relative_to(REPO)} ({f.stat().st_size:,} B)")
    if a.contact:
        contact_sheet(images, a.contact)
        print(f"wrote {a.contact}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
