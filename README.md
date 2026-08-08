# Nikolaus Correll

Personal / lab website for **Nikolaus Correll**, Viola D. Hank Professor of Aerospace and
Mechanical Engineering at the **University of Notre Dame** — robotic manipulation, robotic
materials, and full-stack humanoids.

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

Two scripts keep the content current; both run in CI (see below) and can be run locally:

```bash
python3 scripts/pull_pubs.py         # publications from OpenAlex, grouped by year
python3 scripts/pull_pub_images.py   # per-paper thumbnails (needs playwright + pillow)
```

- **`pull_pubs.py`** fetches all of Correll's OpenAlex author identities, de-dupes by title,
  and writes `data/publications.json` (159 papers, grouped by year).
- **`pull_pub_images.py`** renders the source lab site's AJAX "All papers" view with a headless
  browser, grabs the thumbnail in front of each paper, downloads the token-free original,
  resizes it into `assets/pubs/`, and writes `data/pub_images.json` mapping each paper's
  (normalized, fuzzy-matched) title to its local image. Pages show the thumbnail where one
  exists and a subtle placeholder otherwise.

## Automation

- **`.github/workflows/deploy.yml`** — publishes the repo to GitHub Pages on every push to `main`.
- **`.github/workflows/refresh.yml`** — scheduled weekly (Mondays); re-runs both data scripts,
  installs Playwright + Chromium, and commits any updated publications/thumbnails back to `main`
  (which in turn triggers a redeploy). Can also be run on demand from the Actions tab.

In **Settings → Pages**, the source is **GitHub Actions**.
