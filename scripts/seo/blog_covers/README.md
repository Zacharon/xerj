# `scripts/seo/blog_covers/`: the blog cover series

Every post on xerj.org/blog gets a cover from one series, the **engineering
field-log poster**: night-black ground, a large halftone motif drawn from
that post's own numbers, a mono kicker, the title in the display face, a
yellow subtitle and the post URL. All of it comes from code: HTML + SVG
rendered by headless Chromium. No image model is involved, and the same
inputs give the same pixels.

| output | size | used for |
|---|---|---|
| `landing/og/blog-<slug>.png` | 1200×630, 96-colour PNG | `og:image`, `twitter:image`, Article JSON-LD `image` |
| `landing/blog/covers/<slug>-hero.webp` | 1600×640, lossless WebP | the cover at the top of the post |
| `landing/blog/covers/<slug>-thumb.webp` | 640×336, WebP q80 | the card thumbnail on `/blog/` (lazy-loaded) |

## Run it

```sh
python3 -m venv /tmp/covers && /tmp/covers/bin/pip install playwright pillow
/tmp/covers/bin/playwright install chromium     # or: export CHROME=/usr/bin/google-chrome
/tmp/covers/bin/python scripts/seo/blog_covers/covers.py                    # every post
/tmp/covers/bin/python scripts/seo/blog_covers/covers.py --only <slug>      # one post
/tmp/covers/bin/python scripts/seo/blog_covers/covers.py --contact /tmp/sheet.png
```

This is an offline authoring tool. CI does not run it (the `scripts/seo/`
gates stay stdlib-only). The outputs are committed, and `seo_lint.py` checks
that every `og:image` exists and is 1200×630.

The fonts are vendored in `fonts/` (Big Shoulders Display and JetBrains Mono,
both SIL OFL 1.1, licence texts beside them), so a render does not depend on
what is installed on the machine. They are the families `landing/style.css`
names as `--font-display` and `--font-mono`. The colours are the literal
`landing/style.css` tokens (`--z-bg`, `--z-ink`, `--z-mute`, `--z-line`,
`--z-accent`, `--z-cmp`), copied into `TOKENS` in `covers.py`.

## Adding a post

1. Add an entry to `POSTS` in `covers.py`: `slug`, `date` (the post's
   published date), `title`, `subtitle` (a phrase lifted from the post),
   `motif`, and `alt` (describe only what the card draws).
2. Pick a motif in `motifs.py` or write one: `motif(w, h, rng) -> svg`.
   Every number it draws must appear in the post. Name the source in the
   motif's docstring. `rng` is seeded with the slug and may only decide
   placement (jitter, scatter), never a value.
3. Render, then wire it:
   - `scripts/seo/pagedata.py`: `og_image="og/blog-<slug>.png"` and
     `og_image_alt=` the same text as `alt`, then
     `python3 scripts/seo/fix_heads.py --write`;
   - the post: `<figure class="blog-cover"><img src="/blog/covers/<slug>-hero.webp"
     width="1600" height="640" alt="…" fetchpriority="high" decoding="async"></figure>`
     right after the `blog-crumb` line;
   - `landing/blog/index.html`: `<img class="bl-thumb" src="/blog/covers/<slug>-thumb.webp"
     width="640" height="336" alt="…" loading="lazy" decoding="async">` as the
     first child of the post's `bl-card`.
4. Look at the contact sheet before you commit. If a label collides with
   the motif, fix the motif. Do not shrink the type.

## The motifs

| motif | post | what it draws |
|---|---|---|
| `jevbars` | does-xerj-beat-jev | nDCG@10 dot-bars per dataset, one denominator; the FiQA bill |
| `vote` | jev-vs-a-bm25-vote | 500 Banking77 decisions per arm, filled = correct |
| `index28` | cutting-the-index-28-percent | 5.52 MB and 3.99 MB blocks to scale; .seg/.meta bars |
| `names` | one-vulnerability-three-names | three advisory ids converging on one signed record |
| `gates` | the-rc80-gates | ten features as gates: pass / fail / split / unmeasured |
| `tiles` | the-corpus-hub | a wall of 100 pack tiles, the launch four in yellow |
| `scars` | eval-scars-from-agent-memory | six scratch marks, one per pattern |
| `network` | the-exploit-hub | PoC documents linked to the three CVEs of the eval |
| `route` | corpus-hub-v2 | 245 packs, the 14 catalogue corpora, a question routed to lz4 |

Inks: yellow (`--z-accent`) for XERJ or the result the post is about,
grey-blue (`--z-cmp`) for the comparison series and never for XERJ,
paper (`--z-ink`) for structure, and mute/line for annotation and empty cells.
