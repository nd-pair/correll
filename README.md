# Correll Laboratory

Website for the **Correll Laboratory** of **Nikolaus Correll**, Viola D. Hank Professor of
Aerospace and Mechanical Engineering at the **University of Notre Dame** — robotic manipulation,
robotic materials, and full-stack humanoids.

Live at **[nd-pair.github.io/correll](https://nd-pair.github.io/correll)**.

## Structure

Static site, no build step. Shared chrome (nav + footer) is injected by `site.js`; each page
loads its content from JSON in `data/`. Layout mirrors the PAIR site; palette is its own
(Notre Dame navy with electric-indigo and gold accents).

| Page | Data |
| --- | --- |
| `index.html` — home + last four publications | `data/publications.json`, `data/pub_images.json` |
| `publications.html` — searchable, grouped by year, with a thumbnail per paper | `data/publications.json`, `data/pub_images.json` |
| `people.html` — team + collapsible alumni | `data/people.json` |
| `teaching.html` — courses + textbook | `data/teaching.json` |
| `art.html` — art & music projects (with embedded videos) | `data/art.json` |

## Data pipeline

Three scripts keep the content current; all run in CI (see below) and can be run locally:

```bash
python3 scripts/pull_pubs.py         # publications from OpenAlex, grouped by year
python3 scripts/pull_pub_images.py   # curated per-paper thumbnails (needs playwright + pillow)
python3 scripts/pull_pub_figures.py  # auto figure per paper from its OA PDF (needs pymupdf + pillow)
```

- **`pull_pubs.py`** fetches all of Correll's OpenAlex author identities, de-dupes by title,
  captures each paper's open-access PDF url, and writes `data/publications.json` (159 papers,
  grouped by year).
- **`pull_pub_images.py`** renders the source lab site's AJAX "All papers" view with a headless
  browser, grabs the hand-curated thumbnail in front of each recent paper, downloads the
  token-free original, resizes it into `assets/pubs/`, and writes `data/pub_images.json`
  (normalized, fuzzy-matched title → image).
- **`pull_pub_figures.py`** fills the gaps automatically: for every paper without a curated
  thumbnail, it downloads the open-access PDF (arXiv links resolved to the direct PDF) and gathers
  the candidate teaser figures from the first pages. If a Claude API key is available, a vision
  model picks the most representative one; otherwise a "top-right, earliest page" heuristic is used.
  The chosen figure is rendered (so soft-masks/transparency show on white), resized into
  `assets/pubs/auto/`, and recorded in `data/pub_figures.json`. Paywalled or HTML-only papers are
  skipped. The site merges the two maps with the **curated image winning** over the auto figure,
  and shows a subtle placeholder when neither exists.
- **`pull_pub_teasers.py`** writes a one-line teaser for each paper from its OpenAlex abstract
  (`data/abstracts.json`) using the Claude API, cached in `data/pub_teasers.json`. Incremental —
  only papers without a cached teaser are sent — and best-effort: with no API key it no-ops.

### LLM enrichment (optional)

The figure-selection and teaser steps call **Claude via the Anthropic API** (`scripts/llm.py`,
default model `claude-opus-5`, override with `CORRELL_LLM_MODEL`). They activate only when an
`ANTHROPIC_API_KEY` is present — add it as a repo secret (**Settings → Secrets and variables →
Actions**) to turn them on. Without the key the site still works: figures fall back to the
heuristic and no teasers are shown. (An earlier version used GitHub Models, which GitHub is
retiring; the pipeline now uses the Anthropic API directly.)

## Automation

- **`.github/workflows/deploy.yml`** — publishes the repo to GitHub Pages on every push to `main`.
- **`.github/workflows/refresh.yml`** — scheduled weekly (Mondays); installs Playwright +
  Chromium + PyMuPDF, re-runs all three data scripts, commits any updated
  publications/thumbnails/figures, and then deploys Pages itself (a push made with the default
  `GITHUB_TOKEN` does not trigger `deploy.yml`, so this workflow must publish its own result).
  Can also be run on demand from the Actions tab.

In **Settings → Pages**, the source is **GitHub Actions**.
