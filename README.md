# Correll Laboratory

Website for the **Correll Laboratory** of **Nikolaus Correll**, Viola D. Hank Professor of
Aerospace and Mechanical Engineering at the **University of Notre Dame** — robotic manipulation,
robotic materials, and full-stack humanoids.

Live at **[nd-pair.github.io/correll](https://nd-pair.github.io/correll)**.

## Built on the Notre Dame Web Theme

The site uses **NDT4**, the University's official web theme, as required for any site on an
`nd.edu` subdomain ([web brand standards](https://onmessage.nd.edu/university-branding/website-requirements/)).
Every page loads the theme's shared assets and uses its components — site header, primary
navigation, page header, cards, buttons, accordion, site footer, global menu:

```html
<link rel="stylesheet" href="https://conductor.nd.edu/stylesheets/themes/ndt/4.0/ndt.css">
...
<script>window.NDTConductorHost='https://conductor.nd.edu';</script>
<script src="https://conductor.nd.edu/javascripts/themes/ndt/4.0/ndt.js"></script>
```

Component documentation lives at [webtheme.nd.edu](https://webtheme.nd.edu) and is also available
to AI coding assistants over MCP at `https://webtheme.nd.edu/mcp` — use it to check the real
markup for a component before hand-writing it.

`styles.css` holds only the handful of site-specific patterns the theme has no component for
(the dense publication list, the alumni roster, art credits); it builds them from theme custom
properties so light/dark mode and the brand palette stay intact. **Do not** re-style theme
components: colours, type, spacing, buttons and cards must stay exactly as the design kit
defines them.

## How the site is built

Pages are assembled at build time and committed to the repository root, which is what GitHub
Pages publishes. Nothing is fetched from JSON in the browser — the content ships in the HTML,
so pages are fast, work without JavaScript, and read correctly to screen readers and crawlers.

```
partials/      shared chrome: head, skip links, header, footer, global menu, icon sprite
pages/         one file per page: JSON front matter + the page's <main> content
scripts/
  build_site.py   stitches partials + pages -> *.html at the repo root, writes sitemap.xml
  render.py       renders publications, people, teaching, art and videos into HTML
```

After editing anything in `partials/` or `pages/`, or any file in `data/`, run:

```bash
python3 scripts/build_site.py
```

CI runs the same command before publishing, so the deployed pages always match the sources.
`app.js` adds only two progressive enhancements: scoping the global-menu search to this site,
and filtering the publication list as you type.

| Page | Source | Data |
| --- | --- | --- |
| Home | `pages/index.html` | `data/publications.json`, `data/videos.json` |
| Publications | `pages/publications.html` | `data/publications.json`, `data/pub_images.json`, `data/pub_figures.json`, `data/pub_teasers.json` |
| People | `pages/people.html` | `data/people.json` |
| Teaching | `pages/teaching.html` | `data/teaching.json` |
| Art | `pages/art.html` | `data/art.json` |
| 404 | `pages/404.html` | — |

## Data pipeline

Four scripts keep the content current; all run in CI (see below) and can be run locally:

```bash
python3 scripts/pull_pubs.py         # publications from OpenAlex, grouped by year
python3 scripts/pull_pub_images.py   # curated per-paper thumbnails (needs playwright + pillow)
python3 scripts/pull_pub_figures.py  # auto figure per paper from its OA PDF (needs pymupdf + pillow)
python3 scripts/pull_pub_teasers.py  # one-line teaser per paper from its abstract
```

- **`pull_pubs.py`** fetches all of Correll's OpenAlex author identities, de-dupes by title,
  captures each paper's open-access PDF url, and writes `data/publications.json`, grouped by year.
- **`pull_pub_images.py`** renders the source lab site's AJAX "All papers" view with a headless
  browser, grabs the hand-curated thumbnail in front of each recent paper, downloads the
  token-free original, saves it as a resized WebP in `assets/pubs/`, and writes
  `data/pub_images.json` (normalized, fuzzy-matched title → image).
- **`pull_pub_figures.py`** fills the gaps automatically: for every paper without a curated
  thumbnail, it downloads the open-access PDF (arXiv links resolved to the direct PDF) and gathers
  the candidate teaser figures from the first pages. If a Claude API key is available, a vision
  model picks the most representative one; otherwise a "top-right, earliest page" heuristic is used.
  The chosen figure is rendered onto white, resized into `assets/pubs/auto/` as WebP, and recorded
  in `data/pub_figures.json`. Paywalled or HTML-only papers are skipped. The build merges the two
  maps with the **curated image winning** over the auto figure, and falls back to a neutral tile
  when neither exists.
- **`pull_pub_teasers.py`** writes a one-line teaser for each paper from its OpenAlex abstract
  (`data/abstracts.json`) using the Claude API, cached in `data/pub_teasers.json`. Incremental —
  only papers without a cached teaser are sent — and best-effort: with no API key it no-ops.

All images on the site are WebP; the scripts above emit WebP directly.

### LLM enrichment (optional)

The figure-selection and teaser steps call **Claude via the Anthropic API** (`scripts/llm.py`,
default model `claude-opus-5`, override with `CORRELL_LLM_MODEL`). They activate only when an
`ANTHROPIC_API_KEY` is present — add it as a repo secret (**Settings → Secrets and variables →
Actions**) to turn them on. Without the key the site still works: figures fall back to the
heuristic and no teasers are shown.

## Automation

- **`.github/workflows/deploy.yml`** — on every push to `main`: runs `build_site.py`, stages the
  publishable files into `_site/` and publishes them to GitHub Pages. Source directories
  (`pages/`, `partials/`, `scripts/`, `data/`) are not published.
- **`.github/workflows/refresh.yml`** — scheduled weekly (Mondays); re-runs the data scripts,
  rebuilds the pages, commits any changes, and deploys Pages itself (a push made with the default
  `GITHUB_TOKEN` does not trigger `deploy.yml`). Can also be run on demand from the Actions tab.

In **Settings → Pages**, the source is **GitHub Actions**.

## Quality bar

The University enforces these thresholds for `nd.edu` sites, measured with Lighthouse:
performance ≥ 80 mobile and ≥ 90 desktop, accessibility 100, SEO 100, best practices ≥ 80, and
WCAG 2.2 AA conformance. Re-check after any change — most regressions come from unsized images,
non-theme colours, or skipped heading levels.
