# Correll Lab

Personal / lab website for **Nikolaus Correll**, Professor of Computer Science at the
University of Colorado Boulder — robotic manipulation, robotic materials, and full-stack humanoids.

Live at **[nd-pair.github.io/correll](https://nd-pair.github.io/correll)**.

## Structure

Static site, no build step. Shared chrome (nav + footer) is injected by `site.js`; each page
loads its content from JSON in `data/`.

| Page | Data |
| --- | --- |
| `index.html` — home / research overview | — |
| `publications.html` — searchable, grouped by year | `data/publications.json` |
| `people.html` — team + collapsible alumni | `data/people.json` |
| `teaching.html` — courses + textbook | `data/teaching.json` |
| `art.html` — art & music projects | `data/art.json` |

## Regenerating publications

`data/publications.json` is built from [OpenAlex](https://openalex.org) (all of Correll's author
identities, de-duplicated by title, grouped by year):

```bash
python3 scripts/pull_pubs.py
```

## Deploy

Pushing to `main` triggers `.github/workflows/deploy.yml`, which publishes the repo root to
GitHub Pages. In repo **Settings → Pages**, set the source to **GitHub Actions**.
