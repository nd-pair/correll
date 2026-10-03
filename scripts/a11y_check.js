#!/usr/bin/env node
/**
 * Accessibility and design-compliance gate for the Notre Dame Web Theme sites.
 *
 * Runs against the BUILT site (a directory of .html plus its assets), serving it
 * over http so the pages load the real theme from conductor.nd.edu — which is what
 * the University actually measures, fonts and all.
 *
 * What it checks, and why each one is here:
 *
 *   axe-core, WCAG 2.0/2.1/2.2 A + AA, every page x light/dark x desktop/mobile,
 *     with every <details> forced open. Dark mode is not optional: the theme
 *     declares `color-scheme: light dark`, and four findings in the Creative
 *     review were site CSS that used a fixed palette variable instead of
 *     light-dark().
 *
 *   Pixel contrast behind text that sits over a photograph. axe reports these as
 *     "incomplete" and moves on, so nothing automated catches them. This samples
 *     the real painted pixels inside the rectangles the glyphs occupy.
 *
 *   Duplicate element ids — the sticky navigation repeats the primary nav, so this
 *     is a live risk every time the header changes.
 *
 *   Image hygiene: every <img> needs an alt attribute (empty is allowed and
 *     sometimes correct, missing never is) and intrinsic width/height for CLS.
 *
 *   Behaviour: the video dialog opens over the page and closes, the sticky bar
 *     appears on scroll and leaves the accessibility tree at the top, and the
 *     publication filter keeps its counts honest.
 *
 * Usage:
 *   node scripts/a11y_check.js [--root _site] [--warn-only] [--widths 1440,390]
 *
 * Exit code 1 on any failure, or 0 with ::warning:: annotations under --warn-only.
 */
'use strict';

const fs = require('fs');
const http = require('http');
const path = require('path');
const { chromium } = require('playwright');

const AXE = require.resolve('axe-core/axe.min.js');

// ---------------------------------------------------------------- arguments --
const argv = process.argv.slice(2);
const arg = (name, fallback) => {
  const i = argv.indexOf('--' + name);
  return i === -1 ? fallback : argv[i + 1];
};
const ROOT = path.resolve(arg('root', '_site'));
const WARN_ONLY = argv.includes('--warn-only');
const WIDTHS = arg('widths', '1440,390').split(',').map(Number);
const SCHEMES = arg('schemes', 'light,dark').split(',');

// Large text clears AA at 3:1 instead of 4.5:1 (>=24px, or >=18.66px bold).
const needFor = (px, weight) => (px >= 24 || (px >= 18.66 && weight >= 700)) ? 3 : 4.5;

const problems = [];
const fail = (where, msg, detail) => problems.push({ where, msg, detail });

// ------------------------------------------------------------- static server --
const MIME = {
  '.html': 'text/html; charset=utf-8', '.css': 'text/css', '.js': 'text/javascript',
  '.json': 'application/json', '.svg': 'image/svg+xml', '.webp': 'image/webp',
  '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.gif': 'image/gif',
  '.xml': 'application/xml', '.txt': 'text/plain', '.ico': 'image/x-icon',
  '.woff': 'font/woff', '.woff2': 'font/woff2',
};

function serve(root) {
  return new Promise((resolve) => {
    const server = http.createServer((req, res) => {
      let rel = decodeURIComponent(req.url.split('?')[0]);
      if (rel.endsWith('/')) rel += 'index.html';
      const file = path.join(root, path.normalize(rel).replace(/^(\.\.[/\\])+/, ''));
      if (!file.startsWith(root) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) {
        res.writeHead(404).end('not found');
        return;
      }
      res.writeHead(200, { 'Content-Type': MIME[path.extname(file)] || 'application/octet-stream' });
      fs.createReadStream(file).pipe(res);
    });
    server.listen(0, '127.0.0.1', () => resolve({ server, port: server.address().port }));
  });
}

/**
 * Offline escape hatch. CI runs on a runner that can reach conductor.nd.edu, which
 * is what we want to test against — the real theme, the real fonts. Set
 * A11Y_THEME_DIR to a checkout of ndwebgroup/ndt4-storybook to work somewhere that
 * cannot, serving css/ndt.snapshot.css and public/js/global.js in their place.
 */
async function themeFromDisk(page) {
  const dir = process.env.A11Y_THEME_DIR;
  if (!dir) return;
  const css = path.join(dir, 'css', 'ndt.snapshot.css');
  const js = path.join(dir, 'public', 'js', 'global.js');
  if (!fs.existsSync(css) || !fs.existsSync(js)) {
    console.log(`::warning::A11Y_THEME_DIR=${dir} does not look like ndt4-storybook; ignoring it.`);
    return;
  }
  await page.route('**://conductor.nd.edu/**', route => {
    const isCss = route.request().url().endsWith('.css');
    route.fulfill({
      body: fs.readFileSync(isCss ? css : js),
      contentType: isCss ? 'text/css' : 'text/javascript',
    });
  });
  // static.nd.edu serves the brand fonts and favicons; stub them so the run does
  // not hang. Spacing-sensitive results are therefore not trustworthy offline.
  await page.route('**://static.nd.edu/**', route => route.fulfill({ status: 200, body: '' }));
}

// ------------------------------------------------------------------- helpers --
const CONTRAST_HELPERS = `
  window.__lum = function (r, g, b) {
    const f = c => { c /= 255; return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
  };
  window.__ratio = function (a, b) {
    const hi = Math.max(a, b), lo = Math.min(a, b);
    return (hi + 0.05) / (lo + 0.05);
  };
`;

/** The rectangles the glyphs actually occupy, taken from the text nodes.
 *  The padded element box is the wrong thing to sample: it is mostly whitespace
 *  and it contains the element's own underline, which is not its background. */
const GLYPH_RECTS = `
  window.__glyphRects = function (selectorList) {
    const out = [];
    for (const selector of selectorList.split(',').map(s => s.trim())) {
    for (const el of document.querySelectorAll(selector)) {
      const cs = getComputedStyle(el);
      if (cs.visibility === 'hidden' || cs.display === 'none') continue;
      const walk = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
      let node;
      while ((node = walk.nextNode())) {
        if (!node.textContent.trim()) continue;
        const range = document.createRange();
        range.selectNodeContents(node);
        for (const r of range.getClientRects()) {
          if (r.width < 2 || r.height < 2) continue;
          if (r.bottom < 0 || r.top > innerHeight) continue;
          out.push({
            selector, color: cs.color,
            fontSize: parseFloat(cs.fontSize), fontWeight: parseInt(cs.fontWeight, 10) || 400,
            text: node.textContent.trim().slice(0, 30),
            x: Math.floor(r.x), y: Math.floor(r.y),
            w: Math.ceil(r.width), h: Math.ceil(r.height),
          });
        }
      }
    }
    }
    return out;
  };
`;

async function runAxe(page) {
  await page.addScriptTag({ path: AXE });
  return page.evaluate(async () => {
    const res = await window.axe.run(document, {
      runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'] },
    });
    return res.violations.map(v => ({
      id: v.id, impact: v.impact, help: v.help, count: v.nodes.length,
      sample: v.nodes.slice(0, 3).map(n => n.html.slice(0, 160)),
    }));
  });
}

// ------------------------------------------------------- text over photographs --
/**
 * Measure what is really painted behind the hero text.
 *
 * Screenshot the page with the text's own colour and decorations turned
 * transparent — keeping layout identical — then sample every pixel inside the
 * glyph rectangles recorded beforehand. Repeat for each photograph the hero
 * rotates through, because the crop, and therefore the backdrop, changes with it.
 */
const OVER_IMAGE = '.page-header .nav-primary a, .page-header .page-title, ' +
                   '.page-header .page-lede, .site-title a, .site-tagline, ' +
                   '.header-nav .nav-primary a, .header-nav-toggle button';

async function heroContrast(page, url, width, label) {
  const hero = await page.$('.page-image img');
  if (!hero) return;

  const shots = await page.evaluate(() => {
    const fig = document.querySelector('.page-image');
    const img = fig.querySelector('img');
    const list = [{ src: img.getAttribute('src'), srcset: img.getAttribute('srcset') || '' }];
    try {
      const extra = JSON.parse(fig.getAttribute('data-hero-rotate') || '[]');
      if (Array.isArray(extra)) list.push(...extra);
    } catch (e) { /* no rotation configured */ }
    return list;
  });

  for (const shot of shots) {
    await page.evaluate(async (shot) => {
      const img = document.querySelector('.page-image img');
      img.removeAttribute('srcset');
      img.removeAttribute('sizes');
      img.src = shot.src;
      try { await img.decode(); } catch (e) { /* keep going on a decode hiccup */ }
      await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
    }, shot);

    const boxes = await page.evaluate(sel => window.__glyphRects(sel), OVER_IMAGE);
    if (!boxes.length) continue;

    const hide = await page.addStyleTag({
      content: OVER_IMAGE.split(',').map(s => s.trim())
        .flatMap(s => [s, s + '::before', s + '::after']).join(',') +
        '{color:transparent !important;text-decoration-color:transparent !important;' +
        'border-color:transparent !important;box-shadow:none !important;' +
        'background-image:none !important;}',
    });
    await page.waitForTimeout(120);
    const png = await page.screenshot({ clip: { x: 0, y: 0, width, height: 900 } });
    await page.evaluate(el => el.remove(), hide);

    const sampled = await page.evaluate(async ([dataUrl, boxes]) => {
      const img = new Image();
      img.src = dataUrl;
      await img.decode();
      const c = document.createElement('canvas');
      c.width = img.width; c.height = img.height;
      const ctx = c.getContext('2d', { willReadFrequently: true });
      ctx.drawImage(img, 0, 0);
      return boxes.map(b => {
        const x0 = Math.max(0, b.x), y0 = Math.max(0, b.y);
        const x1 = Math.min(c.width, b.x + b.w), y1 = Math.min(c.height, b.y + b.h);
        if (x1 <= x0 || y1 <= y0) return null;
        const d = ctx.getImageData(x0, y0, x1 - x0, y1 - y0).data;
        const fg = b.color.match(/[\d.]+/g).map(Number);
        const lt = window.__lum(fg[0], fg[1], fg[2]);
        let worst = Infinity, at = null;
        for (let i = 0; i < d.length; i += 4) {
          const r = window.__ratio(lt, window.__lum(d[i], d[i + 1], d[i + 2]));
          if (r < worst) { worst = r; at = [d[i], d[i + 1], d[i + 2]]; }
        }
        return { ...b, worst, at };
      }).filter(Boolean);
    }, ['data:image/png;base64,' + png.toString('base64'), boxes]);

    // One line per selector per photograph: every glyph row of the same heading
    // failing the same way is one problem, not eight.
    const worstBySelector = {};
    for (const s of sampled) {
      const need = needFor(s.fontSize, s.fontWeight);
      if (s.worst >= need) continue;
      const cur = worstBySelector[s.selector];
      if (!cur || s.worst < cur.worst) worstBySelector[s.selector] = { ...s, need };
    }
    for (const [selector, s] of Object.entries(worstBySelector)) {
      fail(`${label} @${width}px`,
        `Text over the hero below AA: ${s.worst.toFixed(2)}:1 (needs ${s.need}:1)`,
        `${selector} — "${s.text}" over rgb(${s.at}) with ${shot.src}`);
    }
  }
}

// ---------------------------------------------------------------- page audits --
async function staticAudits(page, label) {
  const report = await page.evaluate(() => {
    const dupes = {};
    const seen = new Set();
    document.querySelectorAll('[id]').forEach(el => {
      if (seen.has(el.id)) dupes[el.id] = (dupes[el.id] || 1) + 1;
      seen.add(el.id);
    });
    const imgs = [...document.querySelectorAll('img')];
    return {
      duplicateIds: Object.keys(dupes),
      // Count the headings a screen reader would actually reach. A single-page app
      // can legitimately carry two <h1> in the DOM — a gate and the application
      // behind it — as long as only one is ever exposed.
      h1Count: [...document.querySelectorAll('h1')].filter(h => {
        if (h.closest('[hidden]') || h.closest('[aria-hidden="true"]')) return false;
        for (let el = h; el; el = el.parentElement) {
          const cs = getComputedStyle(el);
          if (cs.display === 'none' || cs.visibility === 'hidden') return false;
        }
        return true;
      }).length,
      lang: document.documentElement.lang || null,
      // An empty alt is a legitimate choice for an image whose meaning is already
      // carried by adjacent text; a missing one never is.
      missingAlt: imgs.filter(i => i.getAttribute('alt') === null)
        .map(i => (i.getAttribute('src') || '').slice(-60)),
      unsized: imgs.filter(i => !i.getAttribute('width') || !i.getAttribute('height'))
        .map(i => (i.getAttribute('src') || '').slice(-60)),
      themeCss: !!document.querySelector('link[href*="themes/ndt/4.0/ndt.css"]'),
      themeJs: !!document.querySelector('script[src*="themes/ndt/4.0/ndt.js"]'),
      canonical: !!document.querySelector('link[rel="canonical"]'),
      title: document.title,
    };
  });

  if (report.duplicateIds.length) fail(label, 'Duplicate element id(s)', report.duplicateIds.join(', '));
  if (report.h1Count !== 1) fail(label, `Page has ${report.h1Count} <h1> elements, expected exactly 1`);
  if (!report.lang) fail(label, 'No lang attribute on <html>');
  if (report.missingAlt.length) fail(label, `${report.missingAlt.length} image(s) with no alt attribute`, report.missingAlt.slice(0, 5).join(', '));
  if (report.unsized.length) fail(label, `${report.unsized.length} image(s) without width/height`, report.unsized.slice(0, 5).join(', '));
  if (!report.themeCss) fail(label, 'Page does not load the NDT4 stylesheet from conductor.nd.edu');
  if (!report.themeJs) fail(label, 'Page does not load the NDT4 script from conductor.nd.edu');
  if (!report.canonical) fail(label, 'No canonical link');
  if (!report.title) fail(label, 'No <title>');
}

// ------------------------------------------------------------------ behaviour --
async function behaviour(page, label) {
  // Video dialog: opens over the page, and the iframe stays unloaded until then.
  if (await page.$('.dialog-item .dialog-link')) {
    const before = await page.evaluate(() => {
      const d = document.querySelector('.dialog-item dialog');
      return { open: d.open, display: getComputedStyle(d).display };
    });
    if (before.open || before.display !== 'none') {
      fail(label, 'Video dialog is not closed on load');
    }
    await page.evaluate(() => document.querySelector('.dialog-item .dialog-link').click());
    await page.waitForTimeout(400);
    const after = await page.evaluate(() => {
      const d = document.querySelector('.dialog-item dialog');
      return { open: d.open, stillOnPage: !!document.querySelector('.site-content') };
    });
    if (!after.open) fail(label, 'Clicking a video did not open its dialog (ndt.js did not bind it?)');
    if (!after.stillOnPage) fail(label, 'Clicking a video navigated away instead of opening a dialog');
    await page.evaluate(() => {
      const b = document.querySelector('.dialog-item .dialog-close button');
      if (b) b.click();
      const d = document.querySelector('.dialog-item dialog');
      if (d && d.open) d.close();
    });
    await page.waitForTimeout(200);
  }

  // Sticky navigation: hidden at the top, revealed once the header scrolls away.
  if (await page.$('#nav-fixed')) {
    const atTop = await page.evaluate(() => document.getElementById('nav-fixed').hidden);
    if (!atTop) fail(label, 'Sticky nav is not hidden at the top of the page (it would sit in the accessibility tree)');
    await page.evaluate(() => window.scrollTo(0, 2000));
    await page.waitForTimeout(600);
    const scrolled = await page.evaluate(() => {
      const n = document.getElementById('nav-fixed');
      return { hidden: n.hidden, links: n.querySelectorAll('a').length };
    });
    if (scrolled.hidden) fail(label, 'Sticky nav never appeared when scrolling');
    if (!scrolled.hidden && scrolled.links === 0) fail(label, 'Sticky nav appeared with no links in it');
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.waitForTimeout(600);
  }

  // Publication filter: the per-year counts have to follow the filter.
  if (await page.$('#pub-q')) {
    const result = await page.evaluate(async () => {
      const q = document.getElementById('pub-q');
      const before = [...document.querySelectorAll('.pub-count')].map(e => e.textContent.trim());
      q.value = 'zzzznotarealterm';
      q.dispatchEvent(new Event('input', { bubbles: true }));
      await new Promise(r => setTimeout(r, 300));
      const visible = document.querySelectorAll('.pub-list > li:not([hidden])').length;
      const shownYears = [...document.querySelectorAll('.pub-year:not([hidden])')].length;
      q.value = '';
      q.dispatchEvent(new Event('input', { bubbles: true }));
      await new Promise(r => setTimeout(r, 300));
      const after = [...document.querySelectorAll('.pub-count')].map(e => e.textContent.trim());
      return { before, after, visible, shownYears, hasUnit: before.every(t => /publication/.test(t)) };
    });
    if (!result.hasUnit) fail(label, 'A year heading shows a bare number with no unit', result.before.slice(0, 3).join(' | '));
    if (result.visible !== 0 || result.shownYears !== 0) {
      fail(label, 'Publication filter did not hide everything for a term that matches nothing');
    }
    if (JSON.stringify(result.before) !== JSON.stringify(result.after)) {
      fail(label, 'Publication counts did not return to their totals after clearing the filter');
    }
  }
}

/**
 * An advisory run happens on a schedule, with nobody reading the log. A warning
 * that nobody sees is not a warning, so file it where it will be noticed — and
 * keep it to one open issue, commented on, rather than a new one every fortnight.
 */
async function raiseIssue(lines) {
  const token = process.env.GITHUB_TOKEN;
  const repo = process.env.GITHUB_REPOSITORY;
  if (!token || !repo || !WARN_ONLY || !problems.length) return;

  const api = async (method, url, body) => {
    const res = await fetch(`https://api.github.com/repos/${repo}${url}`, {
      method,
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
      },
      body: body ? JSON.stringify(body) : undefined,
    });
    if (!res.ok) throw new Error(`${method} ${url} -> ${res.status} ${await res.text()}`);
    return res.json();
  };

  const run = process.env.GITHUB_RUN_ID
    ? `\n[Full run](${process.env.GITHUB_SERVER_URL || 'https://github.com'}/${repo}/actions/runs/${process.env.GITHUB_RUN_ID})\n`
    : '';
  const body = `An unattended run found **${problems.length}** problem(s). ` +
    `The site was published anyway — this check is advisory on scheduled runs.\n${run}\n` +
    lines.join('\n');

  try {
    const open = await api('GET', '/issues?state=open&labels=a11y-check');
    if (open.length) {
      await api('POST', `/issues/${open[0].number}/comments`, { body });
      console.log(`a11y_check: commented on issue #${open[0].number}`);
    } else {
      const made = await api('POST', '/issues', {
        title: 'Scheduled run found accessibility or design problems',
        body,
        labels: ['a11y-check'],
      });
      console.log(`a11y_check: opened issue #${made.number}`);
    }
  } catch (err) {
    // Never fail the build over the bookkeeping; the warnings are already in the log.
    console.log(`::warning::a11y_check could not file an issue: ${err.message}`);
  }
}

// ----------------------------------------------------------------------- main --
(async () => {
  if (!fs.existsSync(ROOT)) {
    console.error(`::error::a11y_check: no such directory: ${ROOT}`);
    process.exit(1);
  }
  const pages = fs.readdirSync(ROOT).filter(f => f.endsWith('.html')).sort();
  if (!pages.length) {
    console.error(`::error::a11y_check: no .html files in ${ROOT}`);
    process.exit(1);
  }

  const { server, port } = await serve(ROOT);
  // CI installs its own browser; locally, honour an existing one if Playwright's
  // bundled build is a different revision from what is on disk.
  const browser = await chromium.launch(
    process.env.A11Y_CHROMIUM ? { executablePath: process.env.A11Y_CHROMIUM } : {});
  let checked = 0;

  try {
    for (const scheme of SCHEMES) {
      for (const width of WIDTHS) {
        const ctx = await browser.newContext({
          colorScheme: scheme,
          viewport: { width, height: 900 },
          // Freeze the hero rotation so every measurement is of a known image.
          reducedMotion: 'reduce',
        });
        const page = await ctx.newPage();
        await page.addInitScript(CONTRAST_HELPERS + GLYPH_RECTS);
        await themeFromDisk(page);

        for (const file of pages) {
          const label = `${file} | ${scheme} | ${width}px`;
          const url = `http://127.0.0.1:${port}/${file}`;
          const response = await page.goto(url, { waitUntil: 'load', timeout: 45000 });
          if (!response || !response.ok()) {
            fail(label, `Page did not load (HTTP ${response ? response.status() : 'no response'})`);
            continue;
          }
          // Theme CSS and fonts come off the network; give them a moment.
          await page.waitForTimeout(700);
          // Accordion contents are part of the page and have to be tested too.
          await page.evaluate(() => document.querySelectorAll('details').forEach(d => { d.open = true; }));
          await page.waitForTimeout(200);

          const violations = await runAxe(page);
          for (const v of violations) {
            fail(label, `axe ${v.id} (${v.impact}) x${v.count}: ${v.help}`, v.sample.join(' // '));
          }

          // These do not vary by scheme or width, so only do them once.
          if (scheme === SCHEMES[0] && width === WIDTHS[0]) {
            await staticAudits(page, file);
            await behaviour(page, file);
          }

          // Contrast over photographs is light-mode-and-geometry dependent; run it
          // at every width, since the crop changes with the viewport.
          if (scheme === 'light') await heroContrast(page, url, width, file);

          checked++;
        }
        await ctx.close();
      }
    }
  } finally {
    await browser.close();
    server.close();
  }

  // --------------------------------------------------------------- reporting --
  const level = WARN_ONLY ? 'warning' : 'error';
  const lines = [];
  lines.push(`# Accessibility and design check`);
  lines.push('');
  lines.push(`${checked} page renders checked — ${pages.length} page(s) x ` +
             `${SCHEMES.join('/')} x ${WIDTHS.join('/')}px.`);
  lines.push('');

  if (!problems.length) {
    lines.push('No problems found.');
    console.log('a11y_check: clean across ' + checked + ' page renders.');
  } else {
    lines.push(`**${problems.length} problem(s).**`);
    lines.push('');
    lines.push('| Where | Problem | Detail |');
    lines.push('| --- | --- | --- |');
    for (const p of problems) {
      const esc = s => String(s || '').replace(/\|/g, '\\|').replace(/\n/g, ' ').slice(0, 200);
      lines.push(`| ${esc(p.where)} | ${esc(p.msg)} | ${esc(p.detail)} |`);
      console.log(`::${level}::a11y_check [${p.where}] ${p.msg}${p.detail ? ' — ' + p.detail : ''}`);
    }
  }

  if (process.env.GITHUB_STEP_SUMMARY) {
    fs.appendFileSync(process.env.GITHUB_STEP_SUMMARY, lines.join('\n') + '\n');
  }
  // So an advisory run can decide whether to raise an issue about what it found.
  if (process.env.GITHUB_OUTPUT) {
    fs.appendFileSync(process.env.GITHUB_OUTPUT,
      `problems=${problems.length}\n` +
      `report<<A11Y_EOF\n${lines.join('\n')}\nA11Y_EOF\n`);
  }

  await raiseIssue(lines);

  if (problems.length && !WARN_ONLY) process.exit(1);
  process.exit(0);
})().catch(err => {
  console.error('::error::a11y_check crashed: ' + (err && err.stack ? err.stack : err));
  process.exit(1);
});
