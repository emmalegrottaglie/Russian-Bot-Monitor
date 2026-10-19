// Bot Traffic Monitor front end. Vanilla JS, no build step; markup uses the
// terminal kit classes from /design/terminal.css (see DESIGN_GUIDE.md).

const $ = (id) => document.getElementById(id);
const view = $('view');
const REFRESH_MS = 60_000;
const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;

const TAG_SHORT = {
  'political-right': 'RIGHT-WING', narratives: 'NARRATIVES', 'anti-trans': 'ANTI-TRANS', political: 'POLITICS', regional: 'REGIONAL',
  'south-america': 'SOUTH AMERICA', russia: 'RUSSIA', control: 'NON-POLITICAL',
};
// One line per group for the "who is in each group" panels. The tags themselves
// are editorial labels set in config/sources.toml.
const TAG_ABOUT = {
  'political-right': 'Communities organised around right-wing or conservative politics.',
  narratives: 'Bluesky and X searches for talking points documented in Russian influence operations (Ukraine aid, Zelensky, "woke", "trans youth", Habeck). They count everyone using the words, critics included: they measure the topic, not the operation. Sources in docs/NARRATIVES.md.',
  'anti-trans': 'X searches for anti-trans rhetoric: the slur "troon" and the claim that there is "no such thing as trans" (kids, people). X only; on Bluesky they are rare. They count everyone using the words, including people quoting them to object. Sources in docs/NARRATIVES.md.',
  political: 'General news and politics communities, across the spectrum.',
  regional: 'Local communities for US states and European countries.',
  'south-america': 'Country communities across South America. Nobody has reported an effect there; this group checks.',
  russia: 'Communities about Russia and Russian-language communities: everyday (r/Pikabu), questions to Russians (r/AskARussian) and émigré-leaning news (r/tjournal_refugees).',
  control: 'Hobby and lifestyle communities. They are the control group: a drop that shows up here too is not about politics.',
};

// Explanatory notes as a short list, one point per line, in sentence case.
const notes = (items, attrs = '') => `<ul class="notes"${attrs}>${items.filter(Boolean).map((i) => `<li>${i}</li>`).join('')}</ul>`;

function groupsPanel() {
  const byTag = new Map();
  for (const s of snap.series) {
    if (s.kind !== 'community' || !s.primary) continue;
    for (const t of s.tags) (byTag.get(t) || byTag.set(t, []).get(t)).push(s.label);
  }
  const order = Object.keys(TAG_SHORT).filter((t) => byTag.has(t));
  return `<details class="explain-groups"><summary>Who is in each group?</summary>
    <dl>${order.map((t) => `<dt>${esc(TAG_SHORT[t])}</dt>
      <dd>${esc(TAG_ABOUT[t] || '')} <span class="members">${byTag.get(t).map(esc).join(' · ')}</span></dd>`).join('')}</dl>
    <p class="notes-tail">Groups are editorial labels, open to challenge in <code>config/sources.toml</code>.</p></details>`;
}
const PLATFORM_SHORT = { ioda: 'IODA', cloudflare: 'CLOUDFLARE', reddit: 'REDDIT', bluesky: 'BLUESKY', x: 'X' };

let snap = null;
const state = { tag: 'all', allMetrics: false, a: null, b: null, days: 30, compare: 'ref',
  corrTags: new Set(['political-right', 'control']), diffTag: 'political-right', alignedTag: 'political-right' };
// Line style per group on the correlation chart; Yandex itself is always a1.
const TAG_LINE = { 'political-right': 'l-a3', narratives: 'l-a3 l-dash', 'anti-trans': 'l-a1', political: 'l-a2', regional: 'l-a2 l-dash', 'south-america': 'l-a1 l-dash', russia: 'l-ink', control: 'l-muted' };

// ── Formatting: one time format per screen (MM-DD HH:MM UTC) ────────────────
const pad = (n) => String(n).padStart(2, '0');
const utc = (ts) => new Date(ts * 1000);
const hhmm = (ts) => `${pad(utc(ts).getUTCHours())}:${pad(utc(ts).getUTCMinutes())}`;
const mmdd = (ts) => `${pad(utc(ts).getUTCMonth() + 1)}-${pad(utc(ts).getUTCDate())}`;
const stamp = (ts) => (ts ? `${mmdd(ts)} ${hhmm(ts)} UTC` : '—');
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);

function num(v) {
  if (v == null || Number.isNaN(v)) return '—';
  const a = Math.abs(v);
  if (a >= 10000) return `${(v / 1000).toFixed(1)}K`;
  if (a >= 100) return Math.round(v).toLocaleString('en-US');
  if (a >= 10) return v.toFixed(1);
  return v.toFixed(2);
}
function pct(x) {
  if (x == null) return '—';
  const s = Math.round(x * 100);
  return `${s > 0 ? '+' : s < 0 ? '−' : '±'}${Math.abs(s)}%`;
}
const dirClass = (x) => (x == null ? '' : x < 0 ? 't-down' : 't-up');
// Table header with a short visible label and a full name for screen readers.
const th = (short, long, cls = '') =>
  `<th scope="col"${cls ? ` class="${cls}"` : ''}><span aria-hidden="true">${short}</span><span class="sr-only">${long}</span></th>`;
// Decorative glyphs (▼ ● ▤) are hidden from screen readers.
const glyph = (g) => `<span aria-hidden="true">${g}</span>`;
function setState(text) {
  const el = $('state');
  if (el.dataset.v === text) return;
  el.dataset.v = text;
  el.innerHTML = `${glyph('●')} ${esc(text)}`;
}

// Fixes applied to whatever a view renders, including parts filled in later:
// a lone "—" is read as "no data" (screen readers often skip the dash), and a
// table that scrolls becomes a focusable, named region so keyboards can scroll it.
function enhance(root) {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  const dashes = [];
  for (let n = walker.nextNode(); n; n = walker.nextNode()) {
    if (n.nodeValue.trim() === '—' && !n.parentElement.closest('[aria-hidden="true"], svg, option')) dashes.push(n);
  }
  for (const n of dashes) {
    const span = document.createElement('span');
    span.innerHTML = '<span aria-hidden="true">—</span><span class="sr-only">no data</span>';
    n.replaceWith(span);
  }
  for (const wrap of root.querySelectorAll('.table-wrap')) {
    const scrolls = wrap.scrollWidth > wrap.clientWidth + 1 || wrap.scrollHeight > wrap.clientHeight + 1;
    if (scrolls) {
      wrap.tabIndex = 0;
      wrap.setAttribute('role', 'region');
      wrap.setAttribute('aria-label', `${wrap.querySelector('table')?.getAttribute('aria-label') || 'Table'}, scrollable`);
    } else if (wrap.getAttribute('role') === 'region') {
      wrap.removeAttribute('tabindex'); wrap.removeAttribute('role'); wrap.removeAttribute('aria-label');
    }
  }
}

// ── API ─────────────────────────────────────────────────────────────────────
// Static mode: the site was exported by `python -m tracker publish` and is served
// as plain files (e.g. GitHub Pages), so API paths map onto pre-built JSON files.
const STATIC = document.querySelector('meta[name="data-mode"]')?.content === 'static';

function staticFile(path) {
  const url = new URL(path, 'http://local');
  const q = url.searchParams;
  const series = url.pathname.match(/^\/api\/series\/([^/]+)\/(points|event-study|strike-hours)$/);
  if (series && series[2] === 'points') {
    const bucket = q.get('bucket') === 'day' ? 'day' : 'hour';
    const since = (snap?.now ?? Date.now() / 1000) - Number(q.get('days') || 30) * 86400;
    return [`api/series/${series[1]}/${bucket}.json`, (d) => ({ ...d, points: d.points.filter((p) => p[0] >= since) })];
  }
  if (series && series[2] === 'strike-hours') return [`api/series/${series[1]}/strike-hours-${Number(q.get('event') || 0)}.json`, (d) => d];
  if (series) return [`api/series/${series[1]}/event-study.json`, (d) => d];
  if (url.pathname === '/api/alerts') return ['api/alerts.json', (d) => d.slice(0, Number(q.get('limit') || 100))];
  if (url.pathname === '/api/health') return ['api/snapshot.json', () => ({ ok: true })];
  if (url.pathname === '/api/reports/latest') return ['api/reports/latest.json', (d) => d];
  return [`${url.pathname.slice(1)}.json`, (d) => d];
}

async function api(path) {
  // Relative URLs, so the site also works from a sub-path such as user.github.io/repo/.
  const [file, shape] = STATIC ? staticFile(path) : [path.slice(1), (d) => d];
  const r = await fetch(file, { headers: { Accept: 'application/json' } });
  if (!r.ok) throw new Error(`${r.status} ${path}`);
  return shape(await r.json());
}

// ── Boot sequence: lines appear as real steps complete ──────────────────────
const boot = {
  steps: 0, total: 2,
  line(text) { $('boot-lines').insertAdjacentHTML('beforeend', `<div class="boot-line">${esc(text)}</div>`); },
  ok() {
    $('boot-lines').lastElementChild?.insertAdjacentHTML('beforeend', ' <span class="ok">[ OK ]</span>');
    this.steps++;
    const p = Math.round((this.steps / this.total) * 100);
    $('boot-fill').style.setProperty('--pct', `${p}%`);
    $('boot-pct').textContent = `${p}% — ${p === 100 ? 'READY' : 'LOADING'}`;
  },
  done() { $('boot').hidden = true; view.hidden = false; },
};

function toast(message, kind = 'err') {
  $('toast-slot').insertAdjacentHTML('beforeend',
    `<div class="toast ${kind}"><span class="led${kind === 'err' ? ' three' : ''}"></span>${esc(message)}</div>`);
}

// ── Components ──────────────────────────────────────────────────────────────
function bars(items) {
  // items: [{value, label, text}] — value scaled across the series' own range, 12% floor.
  const vals = items.map((i) => i.value).filter((v) => v != null);
  if (!vals.length) return '<p class="note">NO DATA YET — NEEDS A BASELINE PERIOD</p>';
  const lo = Math.min(...vals), hi = Math.max(...vals), span = hi - lo || 1;
  const peak = items.findIndex((i) => i.value === hi);
  // Screen readers get one "label: value" item per bar (items may pass `sr`).
  return `<div class="bars" role="list">${items.map((it, i) => {
    const h = it.value == null ? 0 : 12 + ((it.value - lo) / span) * 88;
    const sr = it.sr || `${it.label}: ${it.value == null ? 'no data' : it.text}`;
    return `<div class="bar${i === peak ? ' peak' : ''}" role="listitem"><span class="sr-only">${esc(sr)}</span>
      <div class="bar-value" aria-hidden="true">${esc(it.text)}</div>
      <div class="bar-track" aria-hidden="true"><div class="bar-fill" style="--pct:${h}%"></div></div>
      <div class="bar-label" aria-hidden="true">${esc(it.label)}</div></div>`;
  }).join('')}</div>`;
}

function niceMax(v) {
  if (v <= 0) return 1;
  const p = 10 ** Math.floor(Math.log10(v));
  return [1, 2, 2.5, 5, 10].map((m) => m * p).find((m) => m >= v);
}

// Round tick step for a value axis: about four intervals, on 1, 2, 2.5 or 5 times a power of ten.
function niceStep(span) { return niceMax(span / 4); }

// Value formats for index charts (100 = pre-strike average) and differences in percentage points.
const indexTick = (v) => `${Math.round(v)}%`;
const indexValue = (v) => `${Math.round(v)}% (${pct(v / 100 - 1)})`;
const ppValue = (v) => { const r = Math.round(v); return `${r > 0 ? '+' : r < 0 ? '−' : ''}${Math.abs(r)} PP`; };
const refDates = (ref) => `${mmdd(ref.start)} TO ${mmdd(ref.end - 1)}`;
const SOURCES = { ioda: 'IODA, GEORGIA TECH', cloudflare: 'CLOUDFLARE RADAR', reddit: 'REDDIT FEEDS · ARCTIC SHIFT ARCHIVE', bluesky: 'BLUESKY SEARCH', x: 'X API POST COUNTS' };

// SVG line chart with labeled axes, event markers, reference band and a hover readout.
// `lines`: [{label, cls, points: [[ts, value], ...], area?}] drawn in order (last on top).
// `band`: {lo, hi, label} shades a horizontal normal range. `share`: {name, title,
// caption, sources?} adds a PNG download that redraws the chart with that context, and
// the caption and sources are shown under the chart.
// The value axis is titled with `axisTitle` (default: the unit). `tick` formats tick
// labels and `value` formats readout values (both default to num).
// `envelope`: {lo, hi, label} with [[x, value], ...] each shades a range that varies
// along the x axis. The x axis is time unless `xTicks(start, end)` and `xStamp(x)` say
// otherwise (and `xTitle` names it in the data table).
//
// The time axis zooms: an overview strip under the chart holds a window that can be
// dragged (pan) or resized from its edges (zoom); the chart itself pans by dragging and
// zooms with Ctrl/⌘ + scroll or a trackpad pinch; buttons and +/−/0 keys do the same.
// The value axis is fixed to the whole period, so zooming never exaggerates a change.
let chartSeq = 0;
const OV_H = 30;
const zoomMemory = new Map();  // chart → zoomed window, kept across the 60 s refresh

function timeTicks(start, end) {
  const span = end - start, out = [];
  if (span > 2.5 * 86400) {
    const days = span / 86400;
    const every = (days <= 8 ? 1 : days <= 16 ? 2 : days <= 35 ? 7 : 14) * 86400;
    for (let t = Math.ceil(start / 86400) * 86400; t <= end; t += every) out.push([t, mmdd(t)]);
  } else {
    const step = (span <= 8 * 3600 ? 1 : span <= 18 * 3600 ? 3 : span <= 36 * 3600 ? 6 : 12) * 3600;
    for (let t = Math.ceil(start / step) * step; t <= end; t += step) out.push([t, t % 86400 === 0 ? mmdd(t) : hhmm(t)]);
  }
  return out;
}

function chart(el, readout, lines, opts) {
  const { unit, events = [], ref = null, baseline = null, band = null, envelope = null, share = null } = opts;
  const value = opts.value || num, axisTitle = opts.axisTitle || unit;
  const xTicks = opts.xTicks || timeTicks, xStamp = opts.xStamp || stamp;
  const full = { start: opts.start, end: opts.end };
  const fullSpan = full.end - full.start;
  const W = Math.max(el.clientWidth, 280), H = opts.height || 170, R = 6, T = 18, B = 18;  // T leaves room for the axis title
  lines = lines.filter((l) => l.points.length);
  if (!lines.length) {
    el.innerHTML = '';
    readout.innerHTML = '<span class="muted">NO DATA IN THIS RANGE</span>';
    return;
  }
  const zoomable = !opts.still;
  const id = ++chartSeq;

  // Value axis from the whole period: stable while panning, honest while zoomed.
  const values = lines.flatMap((l) => l.points.map((p) => p[1]));
  if (baseline != null) values.push(baseline);
  if (band) values.push(band.lo, band.hi);
  if (envelope) values.push(...envelope.lo.map((p) => p[1]), ...envelope.hi.map((p) => p[1]));
  const min = Math.min(...values), max = Math.max(...values);
  const step = niceStep(Math.max(max, 0) - Math.min(min, 0) || 1);
  const lo = min < 0 ? Math.floor(min / step) * step : 0, hi = Math.max(step, Math.ceil(max / step) * step);
  const yTicks = [];
  for (let v = lo; v <= hi + step / 2; v += step) yTicks.push(Math.round(v * 1e6) / 1e6);
  // Default tick labels carry as many decimals as the step needs: 0, 25, 50, not 0.00, 25.0.
  const decimals = step >= 1 ? 0 : (String(Number(step.toPrecision(3))).split('.')[1] || '').length;
  const tick = opts.tick || ((v) => (Math.abs(v) >= 10000 ? num(v) : v.toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })));
  const baselineLabel = baseline == null ? '' : opts.baselineLabel ?? (ref ? `${tick(baseline)} = AVERAGE ${refDates(ref)}` : `${tick(baseline)} = PRE-STRIKE`);
  // Left margin fits the widest tick label (about 6 px a character at the axis font size).
  const L = Math.max(40, 10 + 6 * Math.max(...yTicks.map((v) => tick(v).length)));
  const y = (v) => T + (1 - (v - lo) / (hi - lo || 1)) * (H - T - B);

  const stepOf = (pts) => {
    const steps = pts.slice(1).map((p, i) => p[0] - pts[i][0]).sort((m, n) => m - n);
    return steps[Math.floor(steps.length / 2)] || 3600;
  };
  // Break a line where samples are missing for more than `maxGap` steps (default 3, so
  // hourly polling hiccups stay joined; daily charts pass 1 so a missing day shows).
  const segments = (pts) => {
    const step = stepOf(pts), segs = [[]];
    pts.forEach((p, i) => {
      if (i && p[0] - pts[i - 1][0] > step * (opts.maxGap ?? 3)) segs.push([]);
      segs[segs.length - 1].push(p);
    });
    return segs.filter((g) => g.length);
  };
  const minSpan = Math.min(fullSpan, Math.max(6 * stepOf(lines[0].points), 6 * 3600));

  const memKey = `${el.id}|${unit}|${lines.map((l) => l.label).join()}`;
  let view = { ...full };
  const mem = zoomable && zoomMemory.get(memKey);
  if (mem && mem.start >= full.start && mem.end <= full.end && mem.end - mem.start >= minSpan) view = { ...mem };
  const zoomed = () => view.end - view.start < fullSpan - 1;

  el.innerHTML = `${zoomable ? `<div class="chart-zoom">
      <span class="chart-range" aria-live="polite"></span>
      <span class="chart-zoom-btns" role="group" aria-label="Zoom the time axis">
        <button type="button" data-zoom="out" aria-label="Zoom out">−</button>
        <button type="button" data-zoom="in" aria-label="Zoom in">+</button>
        <button type="button" data-zoom="all" aria-label="Show the whole period">ALL</button></span></div>` : ''}
    <div class="chart-main"><svg class="chart-svg" viewBox="0 0 ${W} ${H}" role="img" tabindex="0"${H !== 170 ? ` style="height:${H}px"` : ''}></svg></div>
    ${zoomable ? `<svg class="chart-overview" viewBox="0 0 ${W} ${OV_H}" aria-hidden="true"></svg>` : ''}
    ${share?.caption ? `<p class="note chart-caption">${esc(share.caption)} Source: ${esc(share.sources || 'IODA · CLOUDFLARE RADAR · REDDIT · BLUESKY')}.</p>` : ''}
    <div class="chart-tools"><details class="data-table"><summary>Show data as a table${lines[0].points.length > 120 ? ' · daily means' : ''}</summary><div class="table-wrap"></div></details>
    ${share ? `<button type="button" class="chart-png" aria-label="Download this chart, as currently zoomed, as a PNG image">${glyph('▼')} PNG</button>` : ''}</div>`;

  const svg = el.querySelector('.chart-svg');
  const ov = el.querySelector('.chart-overview');
  const rangeLabel = el.querySelector('.chart-range');
  const near = (pts, t) => pts.reduce((best, p) => (Math.abs(p[0] - t) < Math.abs(best[0] - t) ? p : best), pts[0]);
  const envAt = (t) => {
    const lo = envelope?.lo.find((p) => p[0] === t), hi = envelope?.hi.find((p) => p[0] === t);
    return lo && hi ? ` <span class="muted">· ${esc((envelope.label || 'normal range').toLowerCase())} ${tick(lo[1])} to ${tick(hi[1])}</span>` : '';
  };
  const describe = (t, prefix) => {
    if (lines.length === 1) {
      const p = near(lines[0].points, t);
      return `${prefix}${value(p[1])} <span class="muted">${esc(unit)} · ${xStamp(p[0])}</span>${envAt(p[0])}`;
    }
    const p0 = near(lines[0].points, t);
    return `${prefix}<span class="muted">${xStamp(p0[0])} ·</span> ${lines.map((l) =>
      `${esc(l.label)} ${value(near(l.points, p0[0])[1])}`).join(' · ')} <span class="muted">${esc(unit)}</span>${envAt(p0[0])}`;
  };
  let cursorT = null;  // time under the hover or keyboard cursor
  const idle = () => { readout.innerHTML = describe(view.end, view.end < full.end ? 'END OF VIEW ' : opts.xStamp ? '' : 'LATEST '); };
  let labelTimer = null;
  const describeRange = () => {
    const span = view.end - view.start;
    const fmt = (t) => (span <= 2.5 * 86400 ? `${mmdd(t)} ${hhmm(t)}` : mmdd(t));
    const len = span >= 2 * 86400 ? `${Math.round(span / 86400)}\u00a0DAYS` : `${Math.round(span / 3600)}\u00a0H`;  // keep number and unit together
    return zoomed() ? `${fmt(view.start)} – ${fmt(view.end)} · ${len}` : `ALL ${Math.round(fullSpan / 86400)} DAYS · DRAG THE STRIP OR PRESS + TO ZOOM`;
  };

  const draw = () => {
    const { start, end } = view;
    const x = (t) => L + ((t - start) / (end - start)) * (W - L - R);
    const xy = (p) => `${x(p[0]).toFixed(1)},${y(p[1]).toFixed(1)}`;
    const pad = (end - start) * 0.02;
    const drawn = lines.map((line) => {
      // Only what is near the window is drawn; the clip path trims the edges.
      const segs = segments(line.points).map((g) => g.filter((p) => p[0] >= start - pad - 4 * stepOf(line.points) && p[0] <= end + pad + 4 * stepOf(line.points))).filter((g) => g.length);
      const path = segs.map((g) => `M${g.map(xy).join('L')}`).join('');
      const area = !line.area ? '' : segs.filter((g) => g.length > 1).map((g) =>
        `M${x(g[0][0]).toFixed(1)},${y(lo)}L${g.map(xy).join('L')}L${x(g[g.length - 1][0]).toFixed(1)},${y(lo)}Z`).join('');
      // Isolated samples (no neighbour within the gap limit) get a dot, or they'd be invisible.
      const lone = segs.filter((g) => g.length === 1).map(([p]) =>
        `<circle class="dot ${line.cls || ''}" r="2" cx="${x(p[0]).toFixed(1)}" cy="${y(p[1]).toFixed(1)}"/>`).join('');
      return `${area ? `<path class="area" d="${area}"/>` : ''}<path class="line ${line.cls || ''}" d="${path}"/>${lone}`;
    }).join('');

    const refBand = ref && ref.end > start && ref.start < end
      ? `<rect class="ref-band" x="${x(Math.max(ref.start, start))}" y="${T}" width="${x(Math.min(ref.end, end)) - x(Math.max(ref.start, start))}" height="${H - T - B}"/>`
      : '';
    const base = baseline == null ? '' : `<line class="baseline" x1="${L}" x2="${W - R}" y1="${y(baseline)}" y2="${y(baseline)}"/>
      <text class="axis base-label" x="${L + 4}" y="${y(baseline) - 3}">${esc(baselineLabel)}</text>`;  // left: line names sit at the right end
    const normBand = !band ? '' : `<rect class="norm-band" x="${L}" y="${y(band.hi)}" width="${W - L - R}" height="${Math.max(1, y(band.lo) - y(band.hi))}"/>
      <text class="axis base-label" x="${L + 4}" y="${y(band.hi) - 3}">${esc(band.label || 'NORMAL RANGE')}</text>`;
    // A varying range is drawn as one polygon per run of x values where both edges exist.
    let envShape = '';
    if (envelope) {
      const hiAt = new Map(envelope.hi.map((p) => [p[0], p[1]]));
      const runs = segments(envelope.lo.filter((p) => hiAt.has(p[0])));
      envShape = runs.filter((g) => g.length > 1).map((g) => `<path class="norm-band" d="M${g.map(xy).join('L')}L${
        g.slice().reverse().map((p) => xy([p[0], hiAt.get(p[0])])).join('L')}Z"/>`).join('');
    }
    // Event labels run vertically down their marker. Markers closer than one
    // label's width (narrow or zoomed-out charts) share a single label, joined with " · ".
    const shown = events.filter((e) => e.ts >= start && e.ts <= end);
    const labels = [];
    for (const e of shown) {
      const last = labels[labels.length - 1];
      if (last && x(e.ts) - last.x < 12) last.text += ` · ${e.short}`;
      else labels.push({ x: x(e.ts), text: e.short });
    }
    const ev = shown.map((e) => `<line class="event" x1="${x(e.ts)}" x2="${x(e.ts)}" y1="${T}" y2="${H - B}"/>`).join('')
      + labels.map((l) => `<text class="event-label" transform="translate(${l.x - 3},${T + 2}) rotate(-90)" text-anchor="end">${esc(l.text)}</text>`).join('');

    // Each line is named at its last visible point, so lines are told apart by text, not colour alone.
    const visible = lines.map((l) => ({ ...l, pts: l.points.filter((p) => p[0] >= start && p[0] <= end) }));
    const endLabels = lines.length < 2 ? '' : visible.filter((l) => l.pts.length).map((l) => {
      const p = l.pts[l.pts.length - 1];
      return `<text class="line-label ${l.cls || ''}" x="${(x(p[0]) - 3).toFixed(1)}" y="${(y(p[1]) - 4).toFixed(1)}" text-anchor="end">${esc(l.label)}</text>`;
    }).join('');
    const summary = visible.filter((l) => l.pts.length).map((l) => {
      const vs = l.pts.map((p) => p[1]);
      return `${l.label}: last ${value(vs[vs.length - 1])}, range ${tick(Math.min(...vs))} to ${tick(Math.max(...vs))}`;
    }).join('; ') || 'no data in this window';
    const bandText = band ? ` Shaded band: ${(band.label || 'normal range').toLowerCase()}, ${tick(band.lo)} to ${tick(band.hi)}.` : '';
    const envText = envelope ? ` Shaded area: ${(envelope.label || 'normal range').toLowerCase()}.` : '';
    svg.setAttribute('aria-label', `Chart, ${axisTitle}, ${xStamp(start)} to ${xStamp(end)}. ${summary}.${bandText}${envText} Left and right arrow keys read values, plus and minus zoom; the data table below lists every value.`);

    svg.innerHTML = `<clipPath id="clip-${id}"><rect x="${L}" y="0" width="${W - L - R}" height="${H}"/></clipPath>
      ${yTicks.map((v) => `<line class="grid" x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}"/>
        <text class="axis" x="${L - 5}" y="${y(v) + 3}" text-anchor="end">${esc(tick(v))}</text>`).join('')}
      <text class="axis axis-title" x="4" y="9">${esc(axisTitle)}</text>
      ${xTicks(start, end, W).map(([t, s]) => `<text class="axis" x="${x(t)}" y="${H - 4}" text-anchor="middle">${s}</text>`).join('')}
      <g clip-path="url(#clip-${id})">${refBand}${normBand}${envShape}${drawn}${ev}</g>
      ${base}${endLabels}
      <line class="cursor" y1="${T}" y2="${H - B}" visibility="hidden"/>`;
    svg.classList.toggle('zoomed', zoomed());
    if (cursorT != null && cursorT >= start && cursorT <= end) {
      const cur = svg.querySelector('.cursor');
      cur.setAttribute('visibility', 'visible');
      cur.setAttribute('x1', x(cursorT)); cur.setAttribute('x2', x(cursorT));
    }

    if (zoomable) {
      const ovX = (t) => L + ((t - full.start) / fullSpan) * (W - L - R);
      const a = ovX(start), b = ovX(end);
      ov.querySelector('.ov-shade-l').setAttribute('width', Math.max(0, a - L));
      ov.querySelector('.ov-shade-r').setAttribute('x', b);
      ov.querySelector('.ov-shade-r').setAttribute('width', Math.max(0, W - R - b));
      const win = ov.querySelector('.ov-window');
      win.setAttribute('x', a); win.setAttribute('width', Math.max(1, b - a));
      ov.querySelector('.ov-handle-l').setAttribute('x', a - 2);
      ov.querySelector('.ov-handle-r').setAttribute('x', b - 2);
      el.querySelector('[data-zoom="in"]').disabled = end - start <= minSpan + 1;
      el.querySelector('[data-zoom="out"]').disabled = !zoomed();
      el.querySelector('[data-zoom="all"]').disabled = !zoomed();
      if (zoomed()) zoomMemory.set(memKey, { ...view }); else zoomMemory.delete(memKey);
      clearTimeout(labelTimer);  // announce the range once movement settles, not on every frame
      labelTimer = setTimeout(() => { rangeLabel.textContent = describeRange(); }, 250);
    }
    if (cursorT == null) idle();
  };

  let pending = false;
  const schedule = () => {
    if (pending) return;
    pending = true;
    requestAnimationFrame(() => { pending = false; draw(); });
  };
  const setView = (s, e) => {
    const span = Math.max(minSpan, Math.min(fullSpan, e - s));
    const start = Math.max(full.start, Math.min(s, full.end - span));
    view = { start, end: start + span };
    schedule();
  };
  const zoomAround = (t, factor) => {
    const span = (view.end - view.start) * factor;
    setView(t - (t - view.start) * factor, t - (t - view.start) * factor + span);
  };
  const timeAt = (clientX) => {
    const box = svg.getBoundingClientRect();
    return view.start + ((clientX - box.left) / box.width * W - L) / (W - L - R) * (view.end - view.start);
  };

  if (!zoomable) draw();

  if (share) {
    const btn = el.querySelector('.chart-png');
    btn.addEventListener('click', () => {
      btn.disabled = true;
      exportPng(lines, { ...opts, start: view.start, end: view.end })
        .catch((e) => toast(`PNG FAILED: ${e.message}`)).finally(() => { btn.disabled = false; });
    });
  }

  // Pointer: hover reads values; when zoomed, dragging pans; Ctrl/⌘ + wheel (and trackpad pinch) zooms.
  let drag = null;
  svg.addEventListener('pointermove', (e) => {
    if (drag) {
      const dt = -((e.clientX - drag.x) / drag.w) * (W / (W - L - R)) * (drag.end - drag.start);
      setView(drag.start + dt, drag.end + dt);
      return;
    }
    const p = near(lines[0].points, timeAt(e.clientX));
    cursorT = p[0];
    const cur = svg.querySelector('.cursor');
    const x = L + ((p[0] - view.start) / (view.end - view.start)) * (W - L - R);
    cur.setAttribute('visibility', 'visible');
    cur.setAttribute('x1', x); cur.setAttribute('x2', x);
    readout.innerHTML = describe(p[0], '');
  });
  svg.addEventListener('pointerdown', (e) => {
    if (!zoomable || !zoomed() || e.button !== 0) return;
    drag = { x: e.clientX, w: svg.getBoundingClientRect().width, start: view.start, end: view.end };
    svg.setPointerCapture(e.pointerId);
    svg.classList.add('dragging');
  });
  const endDrag = () => { drag = null; svg.classList.remove('dragging'); };
  svg.addEventListener('pointerup', endDrag);
  svg.addEventListener('pointercancel', endDrag);
  svg.addEventListener('pointerleave', () => {
    if (drag) return;
    cursorT = null;
    svg.querySelector('.cursor').setAttribute('visibility', 'hidden');
    idle();
  });
  if (zoomable) {
    svg.addEventListener('wheel', (e) => {
      if (!e.ctrlKey && !e.metaKey) return;  // plain scrolling still scrolls the page
      e.preventDefault();
      zoomAround(timeAt(e.clientX), Math.min(2, Math.max(0.5, Math.exp(e.deltaY * 0.01))));
    }, { passive: false });
  }

  // Keyboard: arrows step through the first line's points (the view follows), +/− zoom, 0 shows all.
  let idx = lines[0].points.length - 1;
  readout.setAttribute('aria-live', 'polite');
  svg.addEventListener('blur', () => { cursorT = null; svg.querySelector('.cursor').setAttribute('visibility', 'hidden'); idle(); });
  svg.addEventListener('keydown', (e) => {
    const pts = lines[0].points;
    const moves = { ArrowLeft: -1, ArrowRight: 1, PageUp: -24, PageDown: 24, Home: -Infinity, End: Infinity };
    if (zoomable && ['+', '=', '-', '_', '0'].includes(e.key)) {
      e.preventDefault();
      const centre = cursorT ?? (view.start + view.end) / 2;
      if (e.key === '0') setView(full.start, full.end);
      else zoomAround(centre, e.key === '-' || e.key === '_' ? 2 : 0.5);
      return;
    }
    if (!(e.key in moves)) return;
    e.preventDefault();
    idx = Math.max(0, Math.min(pts.length - 1, idx + moves[e.key]));
    const t = pts[idx][0];
    cursorT = t;
    if (t < view.start || t > view.end) {
      const span = view.end - view.start;
      setView(t - span / 2, t + span / 2);
    } else {
      draw();
    }
    readout.innerHTML = describe(t, '');
  });

  if (zoomable) {
    el.querySelector('.chart-zoom-btns').addEventListener('click', (e) => {
      const b = e.target.closest('button'); if (!b) return;
      if (b.dataset.zoom === 'all') setView(full.start, full.end);
      else zoomAround((view.start + view.end) / 2, b.dataset.zoom === 'in' ? 0.5 : 2);
    });

    // Overview strip: the whole period, with the visible window outlined.
    const ovX = (t) => L + ((t - full.start) / fullSpan) * (W - L - R);
    const ovY = (v) => 3 + (1 - (v - lo) / (hi - lo || 1)) * (OV_H - 6);
    ov.innerHTML = `<rect class="ov-bg" x="${L}" y="0" width="${W - L - R}" height="${OV_H}"/>
      ${lines.map((l) => `<path class="line ${l.cls || ''}" d="${segments(l.points).map((g) =>
        `M${g.map((p) => `${ovX(p[0]).toFixed(1)},${ovY(p[1]).toFixed(1)}`).join('L')}`).join('')}"/>`).join('')}
      <rect class="ov-shade ov-shade-l" x="${L}" y="0" height="${OV_H}"/>
      <rect class="ov-shade ov-shade-r" y="0" height="${OV_H}"/>
      <rect class="ov-window" y="0.5" height="${OV_H - 1}"/>
      <rect class="ov-handle ov-handle-l" y="0" width="4" height="${OV_H}"/>
      <rect class="ov-handle ov-handle-r" y="0" width="4" height="${OV_H}"/>`;
    draw();
    rangeLabel.textContent = describeRange();

    const ovT = (clientX) => {
      const box = ov.getBoundingClientRect();
      return full.start + (((clientX - box.left) / box.width) * W - L) / (W - L - R) * fullSpan;
    };
    let ovDrag = null;
    ov.addEventListener('pointerdown', (e) => {
      if (e.button !== 0) return;
      const t = ovT(e.clientX);
      const box = ov.getBoundingClientRect();
      const grab = 10 / ((box.width / W) * (W - L - R)) * fullSpan;  // 10 px either side of an edge
      let mode;
      if (Math.abs(t - view.start) <= grab && zoomed()) mode = 'l';
      else if (Math.abs(t - view.end) <= grab && zoomed()) mode = 'r';
      else if (t > view.start && t < view.end && zoomed()) mode = 'move';
      else if (!zoomed()) mode = t - full.start < fullSpan / 2 ? 'l' : 'r';  // start a zoom from the nearer edge
      else { const span = view.end - view.start; setView(t - span / 2, t + span / 2); mode = 'move'; }
      ovDrag = { mode, t0: t, start: view.start, end: view.end };
      ov.setPointerCapture(e.pointerId);
      ov.classList.add('dragging');
      e.preventDefault();
    });
    ov.addEventListener('pointermove', (e) => {
      if (!ovDrag) return;
      const t = ovT(e.clientX), d = t - ovDrag.t0;
      if (ovDrag.mode === 'move') setView(ovDrag.start + d, ovDrag.end + d);
      else if (ovDrag.mode === 'l') setView(Math.max(full.start, Math.min(t, ovDrag.end - minSpan)), ovDrag.end);
      else setView(ovDrag.start, Math.min(full.end, Math.max(t, ovDrag.start + minSpan)));
    });
    const endOv = () => { ovDrag = null; ov.classList.remove('dragging'); };
    ov.addEventListener('pointerup', endOv);
    ov.addEventListener('pointercancel', endOv);
  }

  // Data table, built when opened. Long hourly series are shown as daily means.
  const details = el.querySelector('details');
  details.addEventListener('toggle', () => {
    if (!details.open || details.dataset.built) return;
    details.dataset.built = '1';
    const daily = lines[0].points.length > 120;
    const rowsBy = new Map();
    lines.forEach((l, li) => {
      const sums = new Map();
      for (const [t, v] of l.points) {
        const k = daily ? t - (t % 86400) : t;
        const a = sums.get(k) || [0, 0]; a[0] += v; a[1] += 1; sums.set(k, a);
      }
      for (const [k, [sum, n]] of sums) {
        if (!rowsBy.has(k)) rowsBy.set(k, new Array(lines.length).fill(null));
        rowsBy.get(k)[li] = sum / n;
      }
    });
    const keys = [...rowsBy.keys()].sort((a, b) => (opts.xStamp ? a - b : b - a));
    const when = (t) => (daily ? mmdd(t) : xStamp(t));
    // The shaded range is data too: its edges get their own columns.
    const edge = (side) => new Map((envelope?.[side] || []).map((p) => [p[0], p[1]]));
    const envLo = edge('lo'), envHi = edge('hi');
    const envCols = envelope && !daily;
    details.querySelector('.table-wrap').innerHTML = `<table class="table" aria-label="${esc(unit)} data">
      <thead><tr><th scope="col">${daily ? 'DATE UTC' : esc(opts.xTitle || 'TIME')}</th>${lines.map((l) => `<th scope="col" class="t-num">${esc(l.label)}</th>`).join('')}${
        envCols ? '<th scope="col" class="t-num">RANGE LOW</th><th scope="col" class="t-num">RANGE HIGH</th>' : ''}</tr></thead>
      <tbody>${keys.map((k) => `<tr><td class="t-key">${when(k)}</td>${rowsBy.get(k).map((v) => `<td class="t-num">${v == null ? '—' : num(v)}</td>`).join('')}${
        envCols ? `<td class="t-num">${envLo.has(k) ? num(envLo.get(k)) : '—'}</td><td class="t-num">${envHi.has(k) ? num(envHi.get(k)) : '—'}</td>` : ''}</tr>`).join('')}</tbody>
    </table>`;
  });
}

// ── Chart images ────────────────────────────────────────────────────────────
// A chart is redrawn off-screen at a fixed size, its computed styles and font are
// inlined so the SVG renders the same as an image, and it is composed on a canvas
// with its title, caption, data date and sources: the context travels with it.
const PNG_W = 1200, PNG_H = 675, PNG_SCALE = 2;
const SVG_PROPS = ['fill', 'fill-opacity', 'stroke', 'stroke-width', 'stroke-dasharray', 'stroke-opacity', 'opacity',
  'font-family', 'font-size', 'font-weight', 'letter-spacing', 'paint-order', 'visibility'];
let fontFaces = null;

function toBase64(buf) {
  const bytes = new Uint8Array(buf);
  let bin = '';
  for (let i = 0; i < bytes.length; i += 0x8000) bin += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return btoa(bin);
}

// The page's web font as data-URI @font-face rules (Latin subset only). An SVG drawn
// as an image cannot load external fonts; without this it falls back to a system font.
async function embeddedFonts() {
  if (fontFaces != null) return fontFaces;
  try {
    const link = [...document.querySelectorAll('link[rel="stylesheet"]')].find((l) => l.href.includes('fonts.googleapis.com'));
    const family = getComputedStyle(document.body).fontFamily.split(',')[0].replace(/["']/g, '').trim();
    const css = await (await fetch(link.href)).text();
    const blocks = css.match(/@font-face\s*{[^}]*}/g) || [];
    const wanted = blocks.filter((b) => b.includes(`'${family}'`) && b.includes('U+0000-00FF'));
    const data = new Map();
    for (const b of wanted) {
      const url = b.match(/url\((https:[^)]+)\)/)[1];
      if (!data.has(url)) data.set(url, `data:font/woff2;base64,${toBase64(await (await fetch(url)).arrayBuffer())}`);
    }
    fontFaces = wanted.map((b) => b.replace(/url\((https:[^)]+)\)/, (_, u) => `url(${data.get(u)})`)).join('\n');
  } catch {
    return '';  // offline or blocked: this export uses a fallback monospace; the next one retries
  }
  return fontFaces;
}

function wrapText(ctx, text, width) {
  const out = [];
  let line = '';
  for (const word of text.split(' ')) {
    const next = line ? `${line} ${word}` : word;
    if (ctx.measureText(next).width > width && line) { out.push(line); line = word; } else line = next;
  }
  if (line) out.push(line);
  return out;
}

async function exportPng(lines, opts) {
  const { share } = opts;
  const host = document.createElement('div');
  host.className = 'chart';
  host.style.cssText = 'position:absolute;left:-10000px;top:0;width:760px;margin:0';
  document.body.append(host);
  try {
    chart(host, document.createElement('div'), lines, { ...opts, share: null, still: true, height: 300 });
    const svg = host.querySelector('.chart-svg');
    const clone = svg.cloneNode(true);
    const src = [...svg.querySelectorAll('*')], dst = [...clone.querySelectorAll('*')];
    src.forEach((node, i) => {
      const cs = getComputedStyle(node);
      dst[i].setAttribute('style', SVG_PROPS.map((p) => `${p}:${cs.getPropertyValue(p)}`).join(';'));
    });
    clone.querySelector('.cursor')?.remove();
    const [, , vw, vh] = clone.getAttribute('viewBox').split(' ').map(Number);
    clone.setAttribute('width', vw); clone.setAttribute('height', vh);
    clone.removeAttribute('style');
    const style = document.createElementNS('http://www.w3.org/2000/svg', 'style');
    style.textContent = await embeddedFonts();
    clone.prepend(style);
    const img = new Image();
    img.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(new XMLSerializer().serializeToString(clone))}`;
    await img.decode();

    const root = getComputedStyle(document.documentElement);
    const token = (n) => root.getPropertyValue(n).trim();
    const family = getComputedStyle(document.body).fontFamily;
    await document.fonts.ready;
    const canvas = document.createElement('canvas');
    canvas.width = PNG_W * PNG_SCALE; canvas.height = PNG_H * PNG_SCALE;
    const ctx = canvas.getContext('2d');
    ctx.scale(PNG_SCALE, PNG_SCALE);
    ctx.fillStyle = getComputedStyle(document.body).backgroundColor;
    ctx.fillRect(0, 0, PNG_W, PNG_H);
    const pad = 48;
    ctx.textBaseline = 'alphabetic';
    ctx.fillStyle = token('--a2'); ctx.font = `800 26px ${family}`;
    if ('letterSpacing' in ctx) ctx.letterSpacing = '3px';
    ctx.fillText(share.title.toUpperCase(), pad, 64);
    ctx.fillStyle = token('--term-muted'); ctx.font = `500 15px ${family}`;
    if ('letterSpacing' in ctx) ctx.letterSpacing = '0.5px';
    wrapText(ctx, share.caption, PNG_W - 2 * pad).slice(0, 3).forEach((t, i) => ctx.fillText(t, pad, 98 + i * 22));
    const chartTop = 176, chartH = 430;
    const chartW = Math.min(PNG_W - 2 * pad + 16, chartH * (vw / vh));
    ctx.drawImage(img, pad - 16, chartTop, chartW, chartW * (vh / vw));
    ctx.strokeStyle = token('--term-line'); ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(pad, PNG_H - 52); ctx.lineTo(PNG_W - pad, PNG_H - 52); ctx.stroke();
    const dataTo = opts.dataTo ?? Math.max(...lines.flatMap((l) => l.points.filter((p) => p[0] <= opts.end).map((p) => p[0])));
    ctx.fillStyle = token('--term-muted'); ctx.font = `500 13px ${family}`;
    ctx.fillText(`DATA TO ${stamp(dataTo)} · ${share.sources || 'IODA · CLOUDFLARE RADAR · REDDIT · BLUESKY'}`, pad, PNG_H - 26);
    ctx.textAlign = 'right'; ctx.fillStyle = token('--a1');
    ctx.fillText(`${location.host}${location.pathname.replace(/\/$/, '')}`, PNG_W - pad, PNG_H - 26);

    const blob = await new Promise((res, rej) => canvas.toBlob((b) => (b ? res(b) : rej(new Error('canvas export'))), 'image/png'));
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `bot-monitor-${share.name}-${new Date(snap.now * 1000).toISOString().slice(0, 10)}.png`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 10_000);
  } finally {
    host.remove();
  }
}

function lineChart(el, readout, points, opts) {
  chart(el, readout, [{ label: opts.unit, points, area: true }], opts);
}

function seriesLabel(s) { return `${s.label} · ${s.unit}`; }
function byKey(key) { return snap?.series.find((s) => s.key === key); }

function renderCorrelation(c) {
  const start = c.days[0], end = snap.now;
  const pts = (vals) => c.days.map((d, i) => [d + 43200, vals[i]]).filter((p) => p[1] != null);  // plot at midday
  const label = (tag) => TAG_SHORT[tag] || tag.toUpperCase();
  const shown = c.groups.filter((g) => state.corrTags.has(g.tag));
  const lines = [
    ...shown.map((g) => ({ label: label(g.tag), cls: TAG_LINE[g.tag] || 'l-ink', points: pts(g.values) })),
    { label: 'YANDEX', cls: 'l-a1', points: pts(c.infra.values) },
  ];
  chart($('corr-chart'), $('corr-readout'), lines,
    { start, end, unit: '% OF PRE-STRIKE AVERAGE', events: c.events, ref: c.reference, baseline: 100, maxGap: 1,
      tick: indexTick, value: indexValue,
      share: { name: 'correlation', title: 'Community activity vs Yandex Cloud', sources: 'IODA · REDDIT FEEDS · ARCTIC SHIFT · BLUESKY',
        caption: `Daily median of each group's communities and Yandex Cloud reachability, as a % of their own average over ${refDates(c.reference).toLowerCase()} (100%). UTC days with at least 20 hours of data. Shaded: that reference period. Dashed: reported strikes. Correlation, not proof of cause.` } });
  renderDiff(c);

  const swatch = (cls) => `<svg class="swatch" viewBox="0 0 22 8" aria-hidden="true"><line class="line ${cls}" x1="1" x2="21" y1="4" y2="4"/></svg>`;
  $('corr-legend').innerHTML = `<span class="legend-item">${swatch('l-a1')}YANDEX CLOUD</span>${c.groups.map((g) =>
    `<button class="legend-item" data-v="${esc(g.tag)}" aria-pressed="${state.corrTags.has(g.tag)}">${swatch(TAG_LINE[g.tag] || 'l-ink')}${esc(label(g.tag))}</button>`).join('')}`;
  $('corr-legend').onclick = (e) => {
    const b = e.target.closest('button'); if (!b) return;
    if (state.corrTags.has(b.dataset.v)) state.corrTags.delete(b.dataset.v); else state.corrTags.add(b.dataset.v);
    renderCorrelation(c);
  };

  // Index of the latest day with a value: only complete UTC days get one, so it is not today.
  const latest = (vals) => { for (let i = vals.length - 1; i >= 0; i--) if (vals[i] != null) return i; return -1; };
  // Strength words follow the usual reading of a correlation coefficient.
  const strength = (r) => {
    if (r == null) return 'NOT ENOUGH DAYS YET';
    if (Math.abs(r) < 0.3) return 'NO CLEAR LINK';
    return `${Math.abs(r) < 0.6 ? 'MODERATE' : 'STRONG'} · ${r > 0 ? 'MOVES WITH' : 'MOVES OPPOSITE TO'} YANDEX`;
  };
  const signed = (r) => (r == null ? '—' : `${r > 0 ? '+' : r < 0 ? '−' : ''}${Math.abs(r).toFixed(2)}`);
  $('corr-tiles').innerHTML = c.groups.map((g) => `<div class="tile" role="listitem">
    <div class="tile-value${g.tag === 'political-right' ? ' hl' : ''}">${signed(g.r)}</div>
    <div class="tile-label">${esc(label(g.tag))}</div>
    <div class="tile-sub">${strength(g.r)}</div>
    <div class="tile-sub">${((i) => (i < 0 ? 'NO COMPLETE DAY YET' : `${mmdd(c.days[i])} UTC: ${Math.round(g.values[i])}% OF NORMAL (${pct(g.values[i] / 100 - 1)})`))(latest(g.values))}</div></div>`).join('');
}

// Chart 3 in docs/CHARTS.md: one group's daily index minus the control group's.
// Chart 1: activity around the strikes, every strike lined up at hour 0.
const offsetLabel = (h) => (h === 0 ? '0 H' : `${h > 0 ? '+' : '−'}${Math.abs(h)} H`);
const ALIGNED_X = {
  xTicks: (start, end, width) => {
    // Every 12 h; on phones every 24 h, without the end labels that would run off the edge.
    const step = width < 480 ? 24 : 12, out = [];
    for (let h = Math.ceil(start / (step * 3600)) * step; h * 3600 <= end; h += step) {
      if (width >= 480 || (h * 3600 > start && h * 3600 < end)) out.push([h * 3600, offsetLabel(h)]);
    }
    return out;
  },
  xStamp: (t) => offsetLabel(Math.round(t / 3600)),
  xTitle: 'HOURS FROM STRIKE',
};

function renderAligned(d) {
  const label = (tag) => TAG_SHORT[tag] || tag.toUpperCase();
  const usable = d.groups.filter((g) => g.members >= 2 && g.values.some((v) => v != null));
  const control = usable.find((g) => g.tag === 'control');
  const options = usable.filter((g) => g.tag !== 'control');
  if (!options.length || !d.events.length) {
    $('aligned-switch').innerHTML = '';
    $('aligned-chart').innerHTML = '';
    $('aligned-readout').innerHTML = `<span class="muted">${d.events.length ? 'NO DATA YET' : 'NO STRIKE IS A DAY OLD YET'}</span>`;
    $('aligned-note').innerHTML = '';
    return;
  }
  if (!options.some((g) => g.tag === state.alignedTag)) state.alignedTag = options[0].tag;
  $('aligned-switch').innerHTML = options.map((g) =>
    `<button class="chip" data-v="${esc(g.tag)}" aria-pressed="${g.tag === state.alignedTag}">${esc(label(g.tag))}</button>`).join('');
  $('aligned-switch').onclick = (e) => {
    const b = e.target.closest('button'); if (!b) return;
    state.alignedTag = b.dataset.v; renderAligned(d);
  };
  const g = options.find((o) => o.tag === state.alignedTag);
  const pts = (vs) => d.offsets.map((o, i) => [o * 3600, vs[i]]).filter((p) => p[1] != null);
  const lines = [{ label: label(g.tag), cls: 'l-a3', points: pts(g.values) }];
  if (control) lines.push({ label: 'CONTROL', cls: 'l-muted l-dash', points: pts(control.values) });
  const envelope = g.band && { lo: pts(g.band.lo), hi: pts(g.band.hi), label: 'Normal range' };
  const n = d.events.length, span = d.offsets[d.offsets.length - 1];
  const unknown = d.events.filter((e) => !e.timed).map((e) => e.short.charAt(0) + e.short.slice(1).toLowerCase());
  const caption = `${label(g.tag)} and non-political communities around ${n} reported strikes, all lined up at hour 0, as % of the same weekday and hour 1 to 3 weeks earlier (100 = normal). `
    + (envelope ? `Shaded: range of 90% of ${g.band.draws} random pre-strike windows. ` : '')
    + `${d.smoothing_h}-hour rolling mean.${unknown.length ? ` ${unknown.join(', ')} time unknown, starts at midnight UTC.` : ''}`;
  chart($('aligned-chart'), $('aligned-readout'), lines, {
    ...ALIGNED_X, start: -span * 3600, end: span * 3600, still: true, unit: 'INDEX', axisTitle: 'INDEX · 100 = NORMAL FOR THAT WEEKDAY AND HOUR',
    events: [{ ts: 0, short: 'STRIKE' }], baseline: 100, baselineLabel: '100 = NORMAL', envelope, maxGap: 1,
    tick: (v) => String(Math.round(v)), value: (v) => String(Math.round(v)), dataTo: snap.now,
    share: { name: `${g.tag}-strike-aligned`, title: `${label(g.tag)} around the strikes`, caption, sources: 'REDDIT · ARCTIC SHIFT · BLUESKY · X' } });
  const after = (vs) => vs.filter((v, i) => d.offsets[i] >= 0);
  const outside = envelope ? after(g.values).filter((v, i) => {
    const j = d.offsets.indexOf(0) + i, lo = g.band.lo[j], hi = g.band.hi[j];
    return v != null && lo != null && (v < lo || v > hi);
  }).length : null;
  const hours = after(g.values).filter((v) => v != null).length;
  $('aligned-note').innerHTML = notes([
    `${g.members} ${esc(label(g.tag).toLowerCase())} communities${control ? `, ${control.members} non-political` : ''}. Each line is the median community.`,
    envelope
      ? `After hour 0 the ${esc(label(g.tag).toLowerCase())} line is outside its normal range in ${outside} of ${hours} hours. On ordinary days that happens in about 10% of hours by chance.`
      : 'NOT ENOUGH PRE-STRIKE HISTORY FOR A CHANCE BAND.',
    'The first two strikes are about 24 hours apart, so the hours after one strike include the next.',
    'A line outside the range shows activity was unusual, not why. Compare with the control line: if both move, the cause is probably not political.',
  ]);
}

// Chart 2: every community's daily index, one row each. Bins are symmetric in ratio
// terms (halving reads as far from normal as doubling) and were set from the spread of
// real pre-strike days: the darkest bin on each side holds about 1 in 20 ordinary days.
const HEAT_BINS = [
  { max: 50, cls: 'hm-lo3', label: 'BELOW 50' },
  { max: 67, cls: 'hm-lo2', label: '50–67' },
  { max: 80, cls: 'hm-lo1', label: '67–80' },
  { max: 125, cls: 'hm-mid', label: '80–125 · NORMAL' },
  { max: 150, cls: 'hm-hi1', label: '125–150' },
  { max: 200, cls: 'hm-hi2', label: '150–200' },
  { max: Infinity, cls: 'hm-hi3', label: 'ABOVE 200' },
];
const heatBin = (v) => HEAT_BINS.find((b) => v < b.max);

function renderHeatmap(d) {
  const el = $('heat-chart'), readout = $('heat-readout');
  if (!d.rows.length) {
    el.innerHTML = '';
    readout.innerHTML = '<span class="muted">NO DATA YET</span>';
    return;
  }
  const narrow = el.clientWidth < 480;
  const nDays = Math.min(d.days.length, narrow ? 21 : 50);
  const days = d.days.slice(-nDays), first = d.days.length - nDays;
  // Rows in group order, with a heading row before each group.
  const items = [];
  let last;
  for (const r of d.rows) {
    if (r.group !== last) { items.push({ heading: r.group }); last = r.group; }
    items.push({ row: r, values: r.values.slice(first) });
  }
  const rows = items.filter((i) => i.row);
  const W = Math.max(el.clientWidth, 280), L = narrow ? 112 : 150, R = 4, T = 30, CH = 10, HH = 18;
  const cw = (W - L - R) / nDays;
  let yPos = T;
  for (const it of items) { it.y = yPos; yPos += it.heading ? HH : CH; }
  const H = yPos + 4;
  const x = (i) => L + i * cw;
  const label = (tag) => TAG_SHORT[tag] || (tag || 'OTHER').toUpperCase();
  // Long names are cut in the middle so a trailing language code (" en") stays visible.
  const fit = (t) => {
    const max = narrow ? 17 : 23;
    if (t.length <= max) return t;
    const tail = / [a-z]{2}$/.test(t) ? t.slice(-3) : '';
    return `${t.slice(0, max - 1 - tail.length)}…${tail}`;
  };
  const mid = (i) => (x(i) + cw / 2).toFixed(1);
  const strikeCols = d.events.map((e) => ({ e, i: days.findIndex((dd) => e.ts >= dd && e.ts < dd + 86400) })).filter((s) => s.i >= 0);

  const cells = items.map((it) => {
    if (it.heading) return `<text class="hm-group" x="2" y="${it.y + HH - 5}">${esc(label(it.heading))}</text>`;
    const allMissing = it.values.every((v) => v == null);
    return `<text class="axis hm-label" x="${L - 6}" y="${it.y + CH - 2}" text-anchor="end">${esc(fit(it.row.label))}</text>`
      + it.values.map((v, i) => `<rect class="${v == null ? 'hm-none' : heatBin(v).cls}" x="${x(i).toFixed(1)}" y="${it.y}" width="${Math.max(1, cw - 1).toFixed(1)}" height="${CH - 1}"/>`).join('')
      + (allMissing ? `<text class="axis" x="${L + 4}" y="${it.y + CH - 2}">NO DATA YET</text>` : '');
  }).join('');
  const dayTicks = days.map((dd, i) => (i % 7 === 0 ? `<text class="axis" x="${mid(i)}" y="${T - 4}" text-anchor="middle">${mmdd(dd)}</text>` : '')).join('');
  const strikes = strikeCols.map(({ i }) => `<line class="event" x1="${mid(i)}" x2="${mid(i)}" y1="${T - 2}" y2="${H - 4}"/>
    <text class="event-label" x="${mid(i)}" y="9" text-anchor="middle">▼</text>`).join('');

  el.innerHTML = `<div class="chart-main"><svg class="chart-svg hm" viewBox="0 0 ${W} ${H}" style="height:${H}px" role="grid" tabindex="0"
      aria-label="Heatmap: ${rows.length} communities by day, ${mmdd(days[0])} to ${mmdd(days[days.length - 1])}. Arrow keys move between cells, Home and End jump to the row ends; the data table below lists every value.">
      <defs><pattern id="hm-hatch" width="4" height="4" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
        <line class="hm-hatch" x1="0" y1="0" x2="0" y2="4"/></pattern></defs>
      ${dayTicks}${cells}${strikes}<rect class="hm-cursor" visibility="hidden" width="${Math.max(1, cw - 1).toFixed(1)}" height="${CH - 1}"/></svg></div>
    <div class="hm-legend" role="list" aria-label="Colour key">${HEAT_BINS.map((b) =>
      `<span role="listitem"><i class="${b.cls}"></i>${b.label}</span>`).join('')}<span role="listitem"><i class="hm-none"></i>NO DATA</span></div>
    <p class="note chart-caption">Each cell is a community's activity that UTC day as % of its pre-strike average (${refDates(snap.reference)}). ▼ and dashed lines: reported strikes. Hatched: no data. Last ${nDays} days. Source: REDDIT · ARCTIC SHIFT · BLUESKY · X.</p>
    <div class="chart-tools"><details class="data-table"><summary>Show data as a table</summary><div class="table-wrap"></div></details></div>`;

  const svg = el.querySelector('svg'), cursor = svg.querySelector('.hm-cursor');
  const describe = (ri, ci) => {
    const r = rows[ri], v = r.values[ci];
    return `${esc(r.row.label)} · ${mmdd(days[ci])} · ${v == null ? 'no data' : `index ${Math.round(v)} (${pct(v / 100 - 1)} vs pre-strike)`}`;
  };
  const idle = () => { readout.innerHTML = '<span class="muted">HOVER OR FOCUS A CELL TO READ IT</span>'; };
  const show = (ri, ci) => {
    cursor.setAttribute('x', x(ci).toFixed(1)); cursor.setAttribute('y', rows[ri].y);
    cursor.setAttribute('visibility', 'visible');
    readout.innerHTML = describe(ri, ci);
  };
  svg.addEventListener('pointermove', (e) => {
    const b = svg.getBoundingClientRect(), px = (e.clientX - b.left) / b.width * W, py = (e.clientY - b.top) / b.height * H;
    const ci = Math.floor((px - L) / cw), ri = rows.findIndex((r) => py >= r.y && py < r.y + CH);
    if (ci >= 0 && ci < nDays && ri >= 0) show(ri, ci);
  });
  svg.addEventListener('pointerleave', () => { cursor.setAttribute('visibility', 'hidden'); idle(); });
  let pos = [0, nDays - 1];
  readout.setAttribute('aria-live', 'polite');
  svg.addEventListener('focus', () => show(...pos));
  svg.addEventListener('blur', () => { cursor.setAttribute('visibility', 'hidden'); idle(); });
  svg.addEventListener('keydown', (e) => {
    const [ri, ci] = pos;
    const next = { ArrowUp: [ri - 1, ci], ArrowDown: [ri + 1, ci], ArrowLeft: [ri, ci - 1], ArrowRight: [ri, ci + 1], Home: [ri, 0], End: [ri, nDays - 1] }[e.key];
    if (!next) return;
    e.preventDefault();
    pos = [Math.max(0, Math.min(rows.length - 1, next[0])), Math.max(0, Math.min(nDays - 1, next[1]))];
    show(...pos);
  });
  idle();

  const details = el.querySelector('details');
  details.addEventListener('toggle', () => {
    if (!details.open || details.dataset.built) return;
    details.dataset.built = '1';
    details.querySelector('.table-wrap').innerHTML = `<table class="table" aria-label="Daily index by community">
      <thead><tr><th scope="col">COMMUNITY</th><th scope="col">GROUP</th>${days.map((dd) => `<th scope="col" class="t-num">${mmdd(dd)}</th>`).join('')}</tr></thead>
      <tbody>${rows.map((r) => `<tr><td class="t-value">${esc(r.row.label)}</td><td class="t-key">${esc(label(r.row.group))}</td>${
        r.values.map((v) => `<td class="t-num">${v == null ? '—' : Math.round(v)}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
  });
}

const DIFF_CAPTION = (g) => `${g} communities minus the non-political control group, in percentage points of their pre-strike level. Shaded: range of 90% of pre-strike days. Dashed: reported strikes.`;

function renderDiff(c) {
  const label = (tag) => TAG_SHORT[tag] || tag.toUpperCase();
  const control = c.groups.find((g) => g.tag === 'control');
  const options = c.groups.filter((g) => g.tag !== 'control');
  if (!options.some((g) => g.tag === state.diffTag) && options.length) state.diffTag = options[0].tag;
  $('diff-switch').innerHTML = options.map((g) =>
    `<button class="chip" data-v="${esc(g.tag)}" aria-pressed="${g.tag === state.diffTag}">${esc(label(g.tag))}</button>`).join('');
  $('diff-switch').onclick = (e) => {
    const b = e.target.closest('button'); if (!b) return;
    state.diffTag = b.dataset.v; renderDiff(c);
  };
  const g = options.find((o) => o.tag === state.diffTag);
  if (!g || !control) {
    $('diff-chart').innerHTML = '';
    $('diff-readout').innerHTML = '<span class="muted">NO DATA YET — NEEDS BOTH A GROUP AND THE CONTROL GROUP</span>';
    $('diff-note').innerHTML = '';
    return;
  }
  // A day where either index is missing is missing, never zero.
  const diffs = c.days.map((d, i) => (g.values[i] != null && control.values[i] != null ? g.values[i] - control.values[i] : null));
  const mid = (d) => d + 43200;
  const ref = c.days.map((d, i) => [mid(d), diffs[i]])
    .filter(([t, v]) => v != null && t >= c.reference.start && t <= c.reference.end).map(([, v]) => v).sort((a, b) => a - b);
  const q = (p) => { const pos = p * (ref.length - 1), i = Math.floor(pos); return ref[i] + (ref[Math.min(i + 1, ref.length - 1)] - ref[i]) * (pos - i); };
  const band = ref.length >= 10 ? { lo: q(0.05), hi: q(0.95), label: '90% OF PRE-STRIKE DAYS FELL HERE' } : null;
  const caption = DIFF_CAPTION(label(g.tag));
  chart($('diff-chart'), $('diff-readout'),
    [{ label: `${label(g.tag)} − CONTROL`, cls: 'l-a3', points: c.days.map((d, i) => [mid(d), diffs[i]]).filter((p) => p[1] != null) }],
    { start: c.days[0], end: snap.now, unit: 'VS CONTROL', axisTitle: 'PERCENTAGE POINTS · GROUP MINUS CONTROL',
      events: c.events, baseline: 0, baselineLabel: '0 = NO DIFFERENCE', band, maxGap: 1, tick: ppValue, value: ppValue,
      share: { name: `${g.tag}-minus-control`, title: `${label(g.tag)} minus control`, caption, sources: 'REDDIT FEEDS · ARCTIC SHIFT · BLUESKY' } });
  $('diff-note').innerHTML = notes([
    `The line is ${esc(label(g.tag).toLowerCase())} activity minus non-political activity, both as a % of their usual pre-strike level.`,
    'Above 0: the group is busier than usual compared with non-political communities. Below 0: quieter.',
    band ? 'The shaded band is the normal range: 90% of pre-strike days fell inside it.' : 'No normal range yet: fewer than 10 pre-strike days have data for both groups.',
  ]);
}

// ── Views ───────────────────────────────────────────────────────────────────
const views = {
  live() {
    $('prompt').textContent = 'monitor --live --interval 15m';
    const ref = byKey(snap.correlation_ref) || snap.series.find((s) => s.kind === 'infrastructure');
    const infra = snap.series.filter((s) => s.kind === 'infrastructure');
    const groups = snap.groups;

    let hero = '<div class="hero"><div class="hero-value">—</div><div class="hero-status">NO INFRASTRUCTURE DATA</div></div>';
    if (ref) {
      const share = ref.change_ref == null ? null : (1 + ref.change_ref) * 100;
      // Without a recent point there is nothing to compare, which is not a missing baseline.
      const status = share == null ? (ref.fresh ? 'NO PRE-STRIKE BASELINE' : 'NO RECENT DATA') : share >= 90 ? 'NOMINAL' : share >= 50 ? 'DEGRADED' : 'SEVERE OUTAGE';
      hero = `<div class="hero">
        <div class="hero-value">${share == null ? num(ref.latest) : Math.round(share)}<span class="hero-unit">${share == null ? '' : '%'}</span></div>
        <div class="hero-status">${esc(status)}</div>
        <div class="hero-meta">${esc(ref.label)} · ${share == null ? '' : 'OF PRE-STRIKE LEVEL · '}${num(ref.latest)} ${esc(ref.unit)} · ${stamp(ref.latest_ts)}</div>
      </div>`;
    }

    const chips = snap.runs.map((r) => {
      const off = (r.error || '').startsWith('not configured');
      const cls = off ? 'ghost' : r.ok ? '' : 'three';
      return `<span class="chip ${cls}" role="listitem" title="${esc(r.error || '')}">${esc(PLATFORM_SHORT[r.platform] || r.platform)} ${off ? 'OFF' : r.ok ? 'OK' : 'ERR'}</span>`;
    }).join('');

    const tiles = infra.map((s) => `<div class="tile" role="listitem">
      <div class="tile-value${s.key === ref?.key ? ' hl' : ''}">${num(s.latest)}</div>
      <div class="tile-label">${esc(s.unit)} · ${esc(s.label)}</div>
      <div class="tile-sub">REF <span>${pct(s.change_ref)}</span> · 7D <span>${pct(s.change_7d)}</span></div></div>`).join('');

    const MODES = {
      ref: { field: 'change_ref', n: 'n_ref', note: `Each bar: the last 24 hours compared with the average from ${mmdd(snap.reference.start)} to ${mmdd(snap.reference.end)}, before the strikes.` },
      '7d': { field: 'change_7d', n: 'n_7d', note: 'Each bar: the last 3 hours compared with the same hours of day over the previous 7 days.' },
      event: { field: 'event_effect', n: 'n_event',
        note: `Each bar: the ${snap.event_window} hours after each strike compared with the same weekday and hour 1 to 3 weeks earlier, averaged over the strikes.` },
    };
    const mode = MODES[state.compare];
    const groupBars = bars(groups.map((g) => ({
      value: g[mode.field], label: TAG_SHORT[g.tag] || g.tag.toUpperCase(),
      text: g[mode.field] == null ? '—' : `${pct(g[mode.field])} n${g[mode.n]}`,
      sr: `${TAG_SHORT[g.tag] || g.tag}: ${g[mode.field] == null ? 'no data' : `${pct(g[mode.field])}, ${g[mode.n]} communities`}`,
    })));
    const sigTable = state.compare !== 'event' ? '' : `<div class="table-wrap"><table class="table" aria-label="Change after strikes by group">
      <thead><tr><th scope="col">GROUP</th>${th('MEDIAN Δ', 'Median change after strikes', 't-num')}${th('P &lt; 0.05', 'Share with placebo p below 0.05', 't-num')}${th('N', 'Communities', 't-num')}</tr></thead>
      <tbody>${groups.map((g) => `<tr><td class="t-value">${esc(TAG_SHORT[g.tag] || g.tag)}</td>
        <td class="t-num ${dirClass(g.event_effect)}">${pct(g.event_effect)}</td>
        <td class="t-num">${g.share_sig == null ? '—' : Math.round(g.share_sig * 100) + '%'}</td>
        <td class="t-num">${g.n_event}</td></tr>`).join('')}</tbody></table></div>
      ${notes([
        'P &lt; 0.05: the share of the group\'s communities whose drop after the strikes was bigger than on 95% of ordinary days before them.',
        'About 5% would pass by chance alone, so compare with the non-political group.',
      ])}`;

    const cov = snap.coverage;
    const ticks = cov == null ? '········' : '|'.repeat(Math.round(cov * 8)).padEnd(8, '·');
    const stale = snap.series.filter((s) => !s.fresh && !snap.runs.find((r) => r.platform === s.platform && (r.error || '').startsWith('not configured')));

    view.innerHTML = `${hero}
      <h2 class="sect">Around the strikes · index · 100 = normal</h2>
      <div class="switch" id="aligned-switch" role="group" aria-label="Group shown around the strikes"></div>
      <div class="readout" id="aligned-readout"></div>
      <div class="chart" id="aligned-chart"><p class="note">LOADING…</p></div>
      <div id="aligned-note"></div>
      <h2 class="sect">Correlation · activity vs Yandex Cloud · % of pre-strike</h2>
      <div class="legend" id="corr-legend" role="group" aria-label="Lines shown on the correlation chart"></div>
      ${groupsPanel()}
      <div class="readout" id="corr-readout"></div>
      <div class="chart" id="corr-chart"><p class="note">LOADING…</p></div>
      <h3 class="tiles-title">How closely each group follows Yandex Cloud</h3>
      <div class="tiles" role="list" id="corr-tiles"></div>
      ${notes([
        'Each line is a group\'s daily activity as a % of its usual level before the strikes: 100 means normal.',
        'The Yandex Cloud line is the share of its network still answering, against the same pre-strike level.',
        'The number on each tile is a correlation from −1 to +1, over the days both lines have data (up to 45). Near +1: the group rises and falls with Yandex. Near 0: no link. Near −1: it moves the opposite way.',
        'A drop in the non-political group as well means the cause is probably not political.',
        'Correlation is not proof of cause. Methods are on the About tab.',
      ])}
      <h2 class="sect">Difference · group minus non-political · percentage points</h2>
      <div class="switch" id="diff-switch" role="group" aria-label="Group compared with the control group"></div>
      <div class="readout" id="diff-readout"></div>
      <div class="chart" id="diff-chart"><p class="note">LOADING…</p></div>
      <div id="diff-note"></div>
      <div class="chips" style="margin-top:14px" role="list" aria-label="Source status">${chips}</div>
      <h2 class="sect">Infrastructure · latest value</h2>
      <div class="tiles" role="list">${tiles}</div>
      <h2 class="sect">Community activity · median change by group</h2>
      <div class="switch" data-compare role="group" aria-label="Compare community activity">
        <button class="chip" data-v="ref" aria-pressed="${state.compare === 'ref'}">VS PRE-STRIKE</button>
        <button class="chip" data-v="7d" aria-pressed="${state.compare === '7d'}">VS LAST 7 DAYS</button>
        <button class="chip" data-v="event" aria-pressed="${state.compare === 'event'}">STRIKE WINDOWS</button>
      </div>
      ${groupBars}
      ${notes([mode.note, 'The value is the median across the group\'s communities; n is how many have enough history to compare.'])}
      ${sigTable}
      <div class="qband"><span class="qband-label">DATA COVERAGE ${cov == null ? '—' : Math.round(cov * 100) + '%'}</span>
        <span class="qband-ticks" aria-hidden="true">${ticks}</span><button class="qband-action" data-why aria-expanded="false" aria-controls="why">WHY?<span aria-hidden="true">&gt;</span></button></div>
      <div class="explain note" hidden id="why">SHARE OF CONFIGURED SERIES UPDATED IN THE LAST 3 H.
        ${stale.length ? 'STALE: ' + stale.slice(0, 12).map((s) => esc(s.key)).join(' · ') + (stale.length > 12 ? ` · +${stale.length - 12} MORE` : '') : 'ALL SERIES CURRENT.'}</div>
      <h2 class="sect">${esc(ref ? ref.label : 'Infrastructure')} · ${esc(ref ? ref.unit : '')} · 14 days</h2>
      <div class="readout" id="live-readout"></div>
      <div class="chart" id="live-chart"></div>
      ${notes(['Shaded: the pre-strike reference period.', 'Dashed lines: reported strikes (sources on the About tab).'])}
      <h2 class="sect">Latest alerts</h2>
      <div id="live-alerts"><p class="note">LOADING…</p></div>`;

    view.querySelector('[data-compare]').addEventListener('click', (e) => {
      const b = e.target.closest('button'); if (!b) return;
      state.compare = b.dataset.v; views.live();
    });
    const why = view.querySelector('[data-why]');
    const setWhy = (open) => { $('why').hidden = !open; why.setAttribute('aria-expanded', String(open)); };
    why.addEventListener('click', () => setWhy($('why').hidden));
    view.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && !$('why').hidden) { setWhy(false); why.focus(); }
    });

    api('/api/strike-aligned').then(renderAligned).catch(() => {
      $('aligned-chart').innerHTML = '<p class="note">STRIKE DATA UNAVAILABLE</p>';
    });
    api('/api/correlation').then(renderCorrelation).catch(() => {
      $('corr-chart').innerHTML = '<p class="note">CORRELATION DATA UNAVAILABLE</p>';
    });

    if (ref) {
      const end = snap.now, start = end - 14 * 86400;
      api(`/api/series/${encodeURIComponent(ref.key)}/points?days=14&bucket=hour`).then((d) =>
        lineChart($('live-chart'), $('live-readout'), d.points, { start, end, unit: ref.unit, events: snap.events, ref: snap.reference,
          share: { name: ref.key, title: `${ref.label} · ${ref.unit}`, sources: SOURCES[ref.platform],
            caption: 'Hourly means, UTC, last 14 days. Shaded: pre-strike reference period. Dashed: reported strikes.' } }))
        .catch(() => toast('CHART DATA UNAVAILABLE'));
    }
    api('/api/alerts?limit=3').then((list) => {
      $('live-alerts').innerHTML = list.length
        ? `<div style="display:grid;gap:6px;padding:0 var(--gutter)">${list.map((a) =>
          `<div class="toast info"><span class="led"></span>${esc(stamp(a.ts))} · ${esc(a.details.map((d) => `${d.label} ${pct(d.change)}`).join(' · '))}</div>`).join('')}</div>`
        : '<p class="note">NO ALERTS YET</p>';
    }).catch(() => { $('live-alerts').innerHTML = '<p class="note">ALERTS UNAVAILABLE</p>'; });
  },

  communities() {
    $('prompt').textContent = `communities --tag ${state.tag} --sort change-ref`;
    const tags = ['all', ...snap.groups.map((g) => g.tag)];
    const rows = snap.series
      .filter((s) => s.kind === 'community' && (state.allMetrics || s.primary))
      .filter((s) => state.tag === 'all' || s.tags.includes(state.tag))
      .sort((a, b) => (a.change_ref ?? 9) - (b.change_ref ?? 9));
    const refLabel = byKey(snap.correlation_ref)?.label || snap.correlation_ref;

    view.innerHTML = `<h2 class="sect">Every community · daily % of pre-strike average</h2>
      <div class="readout" id="heat-readout"></div>
      <div class="chart" id="heat-chart"><p class="note">LOADING…</p></div>
      ${notes([
        'One row per community, its main metric only. Columns are UTC days. Dim cells are within the normal day-to-day range (80 to 125).',
        'A drop across many right-wing rows but not the non-political rows would point at something political.',
        'Dark cells happen on ordinary days too: before the strikes, about 1 in 20 days was below 50.',
      ])}
      <h2 class="sect">Filter</h2>
      ${groupsPanel()}
      <div class="switch" data-tags role="group" aria-label="Filter by group">${tags.map((t) =>
        `<button class="chip" data-v="${esc(t)}" aria-pressed="${state.tag === t}">${esc(t === 'all' ? 'ALL' : TAG_SHORT[t] || t)}</button>`).join('')}</div>
      <div class="switch" data-metrics role="group" aria-label="Metrics shown">
        <button class="chip" data-v="primary" aria-pressed="${!state.allMetrics}">MAIN METRIC</button>
        <button class="chip" data-v="all" aria-pressed="${state.allMetrics}">ALL METRICS</button>
      </div>
      <h2 class="sect">Communities · ${rows.length} series</h2>
      <div class="table-wrap"><table class="table" aria-label="Communities">
        <thead><tr><th scope="col">COMMUNITY</th><th scope="col">REGION</th>${th('NOW', 'Latest rate', 't-num')}<th scope="col">UNIT</th>
          ${th('Δ 7D', 'Change vs last 7 days', 't-num')}${th('Δ REF', 'Change vs pre-strike', 't-num')}
          ${th('STRIKE Δ', 'Change after strikes', 't-num')}${th('P', 'Placebo p-value', 't-num')}${th('R', 'Correlation with Yandex Cloud reachability', 't-num')}</tr></thead>
        <tbody>${rows.map((s) => `<tr>
          <td class="t-value"><a class="row-link" href="#history" data-key="${esc(s.key)}">${esc(s.label)}</a></td><td class="t-key">${esc(s.region)}</td>
          <td class="t-num">${num(s.latest)}</td><td class="t-key">${esc(s.unit)}</td>
          <td class="t-num ${dirClass(s.change_7d)}">${pct(s.change_7d)}</td>
          <td class="t-num ${dirClass(s.change_ref)}">${pct(s.change_ref)}</td>
          <td class="t-num ${dirClass(s.event_effect)}">${pct(s.event_effect)}</td>
          <td class="t-num">${s.event_p == null ? '—' : s.event_p.toFixed(2)}</td>
          <td class="t-num">${s.r == null ? '—' : s.r.toFixed(2)}</td></tr>`).join('')}</tbody>
      </table></div>
      ${notes([
        '<b>Now</b>: the latest hourly rate.',
        '<b>Δ 7D</b>: the last 3 hours compared with the same hours over the previous 7 days.',
        '<b>Δ REF</b>: the last 24 hours compared with the average before the strikes.',
        `<b>Strike Δ</b>: the ${snap.event_window} hours after each strike compared with the same weekday and hour 1 to 3 weeks earlier.`,
        `<b>P</b>: how often a drop this big happens on an ordinary day before the strikes. With ${rows.length} series, about ${Math.round(rows.length * 0.05)} will show P &lt; 0.05 by chance.`,
        `<b>R</b>: correlation of daily activity with ${esc(refLabel)} over the last 30 days, from −1 to +1.`,
        '— means not enough data yet. Select a community name to see its history.',
      ])}`;

    view.querySelector('[data-tags]').addEventListener('click', (e) => {
      const b = e.target.closest('button'); if (b) { state.tag = b.dataset.v; views.communities(); }
    });
    view.querySelector('[data-metrics]').addEventListener('click', (e) => {
      const b = e.target.closest('button'); if (b) { state.allMetrics = b.dataset.v === 'all'; views.communities(); }
    });
    view.querySelectorAll('a[data-key]').forEach((a) => a.addEventListener('click', () => { state.b = a.dataset.key; }));
    api('/api/heatmap').then(renderHeatmap).catch(() => { $('heat-chart').innerHTML = '<p class="note">HEATMAP DATA UNAVAILABLE</p>'; });
  },

  history() {
    const infra = snap.series.filter((s) => s.kind === 'infrastructure');
    const comm = snap.series.filter((s) => s.kind === 'community');
    state.a ||= snap.correlation_ref || infra[0]?.key;
    state.b ||= comm.find((s) => s.tags.includes('political-right') && s.primary)?.key || comm[0]?.key;
    $('prompt').textContent = `history --days ${state.days} --compare ${state.a} ${state.b}`;
    const opt = (list, sel) => list.map((s) => `<option value="${esc(s.key)}"${s.key === sel ? ' selected' : ''}>${esc(seriesLabel(s))}</option>`).join('');
    const csv = (key) => (STATIC ? `api/export/series/${encodeURIComponent(key)}.csv`
      : `api/export/series.csv?key=${encodeURIComponent(key)}&days=${state.days}&bucket=hour`);

    view.innerHTML = `<h2 class="sect">Range</h2>
      <div class="switch" data-days role="group" aria-label="Time range">${[7, 14, 30, 90].map((d) =>
        `<button class="chip" data-v="${d}" aria-pressed="${state.days === d}">${d}D</button>`).join('')}</div>
      <label class="field"><span>Infrastructure series</span><select id="sel-a">${opt(infra, state.a)}</select></label>
      <div class="readout" id="ro-a"></div><div class="chart" id="chart-a"></div>
      <label class="field" style="margin-top:14px"><span>Community series</span><select id="sel-b">${opt(comm, state.b)}</select></label>
      <div class="readout" id="ro-b"></div><div class="chart" id="chart-b"></div>
      <h2 class="sect" id="daily-title">Daily mean · last 14 days</h2>
      <div id="daily-bars"></div>
      <h2 class="sect" id="es-title">Event study · robustness</h2>
      <div id="es-grid"><p class="note">LOADING…</p></div>
      <h2 class="sect">Download</h2>
      <div class="links">
        <a class="chip ghost" href="${csv(state.a)}">${glyph('▼')} ${esc(state.a)}.CSV</a>
        <a class="chip ghost" href="${csv(state.b)}">${glyph('▼')} ${esc(state.b)}.CSV</a>
        <a class="chip" href="api/export/daily.csv?days=365">${glyph('▼')} ALL SERIES · DAILY CSV</a>
        ${STATIC ? '' : '<a class="chip two" href="docs">API DOCS</a>'}
      </div>`;

    view.querySelector('[data-days]').addEventListener('click', (e) => {
      const b = e.target.closest('button'); if (b) { state.days = Number(b.dataset.v); views.history(); }
    });
    $('sel-a').addEventListener('change', (e) => { state.a = e.target.value; views.history(); });
    $('sel-b').addEventListener('change', (e) => { state.b = e.target.value; views.history(); });

    const end = snap.now, start = end - state.days * 86400;
    const draw = async (key, chart, ro) => {
      const s = byKey(key);
      const d = await api(`/api/series/${encodeURIComponent(key)}/points?days=${state.days}&bucket=hour`);
      lineChart($(chart), $(ro), d.points, { start, end, unit: s.unit, events: snap.events, ref: snap.reference,
        share: { name: key, title: `${s.label} · ${s.unit}`, sources: SOURCES[s.platform],
          caption: `Hourly means, UTC, last ${state.days} days. Shaded: pre-strike reference period. Dashed: reported strikes.` } });
    };
    draw(state.a, 'chart-a', 'ro-a').catch(() => toast('SERIES A UNAVAILABLE'));
    draw(state.b, 'chart-b', 'ro-b').catch(() => toast('SERIES B UNAVAILABLE'));
    api(`/api/series/${encodeURIComponent(state.b)}/event-study`).then((d) => {
      const s = byKey(state.b);
      $('es-title').textContent = `Event study · ${s.label} · robustness`;
      if (!d.grid.length) { $('es-grid').innerHTML = '<p class="note">NO EVENTS OLD ENOUGH YET</p>'; return; }
      const cell = (c) => (c.effect == null ? '—' : `${pct(c.effect)} p${c.p == null ? ' —' : c.p.toFixed(2)}`);
      const at = (w, o) => d.grid.find((c) => c.window === w && c.offset_h === o);
      const main = at(12, 0);
      $('es-grid').innerHTML = `<div class="table-wrap"><table class="table" aria-label="Event study robustness grid">
        <thead><tr><th scope="col">WINDOW</th><th scope="col">START −3 H</th><th scope="col">AT EVENT</th><th scope="col">START +3 H</th></tr></thead>
        <tbody>${[6, 12, 24].map((w) => `<tr><td class="t-key">${w} H</td>${[-3, 0, 3].map((o) => {
          const c = at(w, o);
          return `<td class="${c.p != null && c.p < 0.05 ? 't-delta' : 't-value'}">${cell(c)}</td>`;
        }).join('')}</tr>`).join('')}</tbody></table></div>
        <div class="tiles" role="list">${d.events.map((e, i) => `<div class="tile" role="listitem">
          <div class="tile-value">${pct(main.per_event[i])}</div>
          <div class="tile-label">${esc(e.short)} · ${stamp(e.ts)}</div>
          <div class="tile-sub">${e.timed ? 'MEASURED TIME' : 'MIDNIGHT UTC · TIME UNKNOWN'}</div></div>`).join('')}</div>
        ${notes([
          'Each cell: total activity after the strikes compared with the same weekday and hour 1 to 3 weeks earlier, averaged over the strikes.',
          main.placebo_n >= 50
            ? `p: the share of 500 draws from ${main.placebo_n} random pre-strike windows with a drop at least this large. ○ marks p &lt; 0.05.`
            : 'p needs 4 or more weeks of history before the first strike; it appears once the backfill has loaded it.',
          'Tiles: each strike on its own, 12-hour window.',
          'A real effect should hold across the grid, not in one cell.',
        ])}`;
    }).catch(() => { $('es-grid').innerHTML = '<p class="note">UNAVAILABLE</p>'; });
    api(`/api/series/${encodeURIComponent(state.b)}/points?days=14&bucket=day`).then((d) => {
      const s = byKey(state.b);
      $('daily-title').textContent = `${s.label} · ${s.unit} · daily mean, 14 days`;
      $('daily-bars').innerHTML = bars(d.points.map(([t, v]) => ({ value: v, label: mmdd(t).slice(3), text: num(v), sr: `${mmdd(t)}: ${num(v)}` })));
    }).catch(() => { $('daily-bars').innerHTML = '<p class="note">UNAVAILABLE</p>'; });
  },

  async alerts() {
    $('prompt').textContent = 'alerts --list --limit 100';
    view.innerHTML = '<h2 class="sect">Alert log</h2><p class="note">LOADING…</p>';
    const list = await api('/api/alerts?limit=100');
    view.innerHTML = `<h2 class="sect">Alert log · ${list.length}</h2>
      <div class="table-wrap"><table class="table" aria-label="Alert log">
        <thead><tr><th scope="col">TIME UTC</th><th scope="col">ALERT</th><th scope="col">POSTED</th></tr></thead>
        <tbody>${list.map((a) => `<tr><td class="t-key">${esc(stamp(a.ts))}</td><td class="wrap">${esc(a.message)}</td>
          <td class="${a.posted ? 't-data' : 't-delta'}">${a.posted ? 'X' : esc(a.error ? 'FAILED' : 'LOG ONLY')}</td></tr>`).join('')
          || '<tr><td colspan="3" class="t-key">NO ALERTS YET</td></tr>'}</tbody>
      </table></div>
      ${notes([
        'An alert fires when an infrastructure signal moves 25% or more, or a group\'s median moves 30% or more, against the same hours over the previous 7 days.',
        'Each signal then waits 12 hours before it can alert again.',
      ])}`;
  },

  async report() {
    $('prompt').textContent = 'report --latest --format csv,json,zip';
    view.innerHTML = '<h2 class="sect">Report</h2><p class="note">LOADING…</p>';
    const [list, rep] = await Promise.all([
      api('/api/reports'),
      api('/api/reports/latest').catch(() => null),
    ]);
    if (!rep) {
      view.innerHTML = '<h2 class="sect">Report</h2><p class="note">NO REPORT YET — THE FIRST ONE IS BUILT AFTER THE NEXT COLLECTION PASS, OR RUN: python -m tracker report</p>';
      return;
    }
    const base = `reports/${encodeURIComponent(rep.report_date)}`;
    const files = list.find((r) => r.date === rep.report_date)?.files || [];
    const zip = files.find((f) => f.endsWith('.zip'));
    const label = (tag) => TAG_SHORT[tag] || tag.toUpperCase();
    const share = (x) => (x == null ? '—' : `${Math.round(x * 100)}%`);
    const p2 = (x) => (x == null ? '—' : x.toFixed(2));
    const rows = rep.communities.filter((c) => state.allMetrics || c.main_metric === 'yes');

    view.innerHTML = `
      <div class="hero">
        <div class="hero-value" style="font-size:44px;line-height:44px">${esc(rep.report_date)}</div>
        <div class="hero-status">REPORT SNAPSHOT</div>
        <div class="hero-meta">GENERATED ${esc(rep.generated_utc.replace('T', ' ').replace('Z', ' UTC'))} · PRE-STRIKE
          ${esc(rep.reference_period.start_utc.slice(5, 10))} – ${esc(rep.reference_period.end_utc.slice(5, 10))} ·
          ${rep.communities.filter((c) => c.main_metric === 'yes').length} COMMUNITIES · ${rep.events.length} EVENTS</div>
      </div>
      <div class="links">
        ${zip ? `<a class="chip" href="${base}/${encodeURIComponent(zip)}">${glyph('▼')} FULL BUNDLE .ZIP</a>` : ''}
        <a class="chip two" href="${base}/groups.csv">${glyph('▼')} GROUPS.CSV</a>
        <a class="chip two" href="${base}/communities.csv">${glyph('▼')} COMMUNITIES.CSV</a>
        <a class="chip ghost" href="${base}/infrastructure.csv">${glyph('▼')} INFRASTRUCTURE.CSV</a>
        <a class="chip ghost" href="${base}/daily.csv">${glyph('▼')} DAILY.CSV</a>
        <a class="chip ghost" href="${base}/report.json">${glyph('▼')} JSON</a>
        <a class="chip ghost" href="${base}/README.md">METHODS</a>
      </div>

      <h2 class="sect">Groups · headline</h2>
      <div class="table-wrap"><table class="table" aria-label="Groups, headline">
        <thead><tr><th scope="col">GROUP</th>${th('N', 'Communities', 't-num')}${th('Δ PRE-STRIKE', 'Median change vs pre-strike', 't-num')}
          ${th('STRIKE Δ', 'Median change after strikes', 't-num')}${th('P &lt; .05', 'Share with placebo p below 0.05', 't-num')}${th('ROBUST', 'Share robust across timing checks', 't-num')}
          ${th('R', 'Correlation with Yandex Cloud reachability', 't-num')}${th('INDEX NOW', 'Latest index, 100 equals pre-strike', 't-num')}</tr></thead>
        <tbody>${rep.groups.map((g) => `<tr><td class="t-value">${esc(label(g.group))}</td><td class="t-num">${g.communities}</td>
          <td class="t-num ${dirClass(g.median_change_vs_pre_strike)}">${pct(g.median_change_vs_pre_strike)}</td>
          <td class="t-num ${dirClass(g.median_strike_window_change)}">${pct(g.median_strike_window_change)}</td>
          <td class="t-num">${share(g.share_p_below_0_05)}</td><td class="t-num">${share(g.share_robust)}</td>
          <td class="t-num">${p2(g.r_vs_infrastructure)}</td>
          <td class="t-num">${g.latest_index == null ? '—' : Math.round(g.latest_index)}</td></tr>`).join('')}</tbody>
      </table></div>
      ${notes([
        'Values are medians across each group\'s communities.',
        'P &lt; .05: the share with a placebo p below 0.05; about 5% would pass by chance.',
        'Robust: the share with a drop of 5% or more at p &lt; .05 in at least 5 of 9 timing checks.',
        'R: correlation with Yandex Cloud reachability. Index 100 = the pre-strike level.',
      ])}

      <h2 class="sect">Infrastructure</h2>
      <div class="table-wrap"><table class="table" aria-label="Infrastructure">
        <thead><tr><th scope="col">SIGNAL</th><th scope="col">UNIT</th><th scope="col" class="t-num">LATEST</th>
          ${th('PRE-STRIKE', 'Pre-strike mean', 't-num')}${th('Δ PRE-STRIKE', 'Change vs pre-strike', 't-num')}${th('STRIKE Δ', 'Change after strikes', 't-num')}</tr></thead>
        <tbody>${rep.infrastructure.map((r) => `<tr><td class="t-value">${esc(r.signal)}</td><td class="t-key">${esc(r.unit)}</td>
          <td class="t-num">${num(r.latest)}</td><td class="t-num">${num(r.pre_strike_mean)}</td>
          <td class="t-num ${dirClass(r.change_vs_pre_strike)}">${pct(r.change_vs_pre_strike)}</td>
          <td class="t-num ${dirClass(r.strike_window_change)}">${pct(r.strike_window_change)}</td></tr>`).join('')}</tbody>
      </table></div>

      <h2 class="sect">Communities · ${rows.length}</h2>
      <div class="switch" data-metrics role="group" aria-label="Metrics shown">
        <button class="chip" data-v="primary" aria-pressed="${!state.allMetrics}">MAIN METRIC</button>
        <button class="chip" data-v="all" aria-pressed="${state.allMetrics}">ALL METRICS</button>
      </div>
      <div class="table-wrap"><table class="table" aria-label="Communities">
        <thead><tr><th scope="col">COMMUNITY</th><th scope="col">GROUP</th><th scope="col">UNIT</th>
          ${th('PRE-STRIKE', 'Pre-strike mean', 't-num')}${th('LAST 7D', 'Last 7 days mean', 't-num')}${th('Δ PRE', 'Change vs pre-strike', 't-num')}
          ${th('STRIKE Δ', 'Change after strikes', 't-num')}${th('P', 'Placebo p-value', 't-num')}${th('ROBUST', 'Timing checks passed, of 9', 't-num')}
          ${th('R', 'Correlation with Yandex Cloud reachability', 't-num')}</tr></thead>
        <tbody>${rows.map((c) => `<tr><td class="t-value">${esc(c.community)}</td>
          <td class="t-key">${esc(c.groups.split('|').map(label).join(' '))}</td><td class="t-key">${esc(c.unit)}</td>
          <td class="t-num">${num(c.pre_strike_mean)}</td><td class="t-num">${num(c.last_7d_mean)}</td>
          <td class="t-num ${dirClass(c.change_vs_pre_strike)}">${pct(c.change_vs_pre_strike)}</td>
          <td class="t-num ${dirClass(c.strike_window_change)}">${pct(c.strike_window_change)}</td>
          <td class="t-num">${p2(c.strike_window_p)}</td>
          <td class="t-num">${c.robust_cells == null ? '—' : `${c.robust_cells}/9`}</td>
          <td class="t-num">${p2(c.r_vs_infrastructure)}</td></tr>`).join('')}</tbody>
      </table></div>
      ${notes([
        'Rates are per hour.',
        'Strike Δ: the 12 hours after each strike compared with the same weekday and hour 1 to 3 weeks earlier. P: the placebo test.',
        'Robust: timing checks, of 9, with a drop of 5% or more at p &lt; .05.',
        'Full column definitions are in the bundle\'s README.',
      ])}

      <button class="action" id="print">${glyph('▤')} PRINT / SAVE AS PDF</button>

      <h2 class="sect">Archive · ${list.length} report${list.length === 1 ? '' : 's'}</h2>
      <div class="table-wrap"><table class="table" aria-label="Report archive">
        <thead><tr><th scope="col">DATE</th><th scope="col">DOWNLOAD</th></tr></thead>
        <tbody>${list.map((r) => {
          const z = r.files.find((f) => f.endsWith('.zip'));
          const b = `reports/${encodeURIComponent(r.date)}`;
          return `<tr><td class="t-key">${esc(r.date)}</td><td>${z ? `<a href="${b}/${encodeURIComponent(z)}">ZIP</a> · ` : ''}<a href="${b}/groups.csv">GROUPS</a> ·
            <a href="${b}/communities.csv">COMMUNITIES</a> · <a href="${b}/README.md">README</a></td></tr>`;
        }).join('')}</tbody>
      </table></div>
      <p class="note">A NEW REPORT IS SAVED EVERY DAY AND NEVER CHANGED AFTERWARDS · CITE AS: BOT TRAFFIC MONITOR, REPORT OF ${esc(rep.report_date)}</p>`;

    view.querySelector('[data-metrics]').addEventListener('click', (e) => {
      const b = e.target.closest('button'); if (b) { state.allMetrics = b.dataset.v === 'all'; views.report(); }
    });
    $('print').addEventListener('click', () => window.print());
  },

  about() {
    $('prompt').textContent = 'man monitor';
    const ev = snap.events.map((e) => `<li><b>${mmdd(e.ts)}</b> — ${esc(e.label)} <span class="muted">(${esc(e.status)}; ${esc(e.source)})</span></li>`).join('');
    const pal = document.documentElement.dataset.palette;
    const crt = document.documentElement.dataset.crt;
    view.innerHTML = `<h2 class="sect">What this is</h2>
      <div class="prose">
        <p>An open monitor for one question: when Yandex data centres go dark, does activity in online political communities change, and does it change more than in non-political ones?</p>
        <p>It records two kinds of signal side by side. <b>Infrastructure</b>: how much of Yandex's network is reachable (IODA active probing and BGP routing) and, when configured, the share of HTTP requests from Yandex's network that Cloudflare classifies as bots. <b>Communities</b>: comments and posts per hour in selected subreddits, and posts per hour matching keywords on Bluesky and on X (original posts, reposts and replies, from X's post counts, updated once a day). Only timestamps are counted; no usernames or content are stored.</p>
      </div>
      <h2 class="sect">Read this before citing a number</h2>
      <div class="prose"><ul>
        <li>Correlation is not attribution. A drop in a community after an outage is consistent with bot or troll accounts going offline, but also with news cycles, weekends, moderation changes, Reddit's own systems, or real users in Russia losing service.</li>
        <li>Compare against the <b>control</b> group. A drop that also appears in non-political communities is not evidence of anything political.</li>
        <li>Cloudflare's "bot" share for AS13238 is dominated by Yandex's own search crawlers. It measures automated traffic from that network, not influence operations.</li>
        <li>Group tags (right-wing, narratives, anti-trans, politics, regional, South America, Russia, non-political) are editorial labels set in <code>config/sources.toml</code>. They are open to challenge; propose changes there.</li>
        <li>Reddit history before this site started collecting comes from the Arctic Shift archive and is backfilled hourly; days missing from the archive are left as gaps, never filled.</li>
      </ul></div>
      <h2 class="sect">Definitions</h2>
      <div class="prose"><ul>
        <li><b>Δ 7D</b>: the last 3 hours vs the median of the same hours of day over the previous 7 days. Drives alerts.</li>
        <li><b>Δ REF</b>: the last 24 hours (3 for infrastructure) vs the mean of the pre-strike reference period, ${mmdd(snap.reference.start)} to ${mmdd(snap.reference.end)}.</li>
        <li><b>R</b>: Pearson correlation of daily means with <code>${esc(snap.correlation_ref)}</code> over the last 30 days; shown when at least 7 days overlap.</li>
        <li><b>Strike Δ</b>: total activity in the ${snap.event_window} hours after each strike vs the same weekday and hour 1, 2 and 3 weeks earlier, averaged over strikes with equal weight. Strike times come from <code>config/events.toml</code>; where IODA shows the outage, its time is used.</li>
        <li><b>P</b>: a placebo test. The same statistic is computed for random start times before the first strike (500 draws); P is the share of those that drop at least as much. It answers "how often does a dip this size happen with no strike?". Placebo windows overlap, so treat P as a rough guide, and with many communities about 5% will pass P &lt; 0.05 by chance. Check the robustness grid on the History tab: an effect that appears for only one window length or start time is not robust. Baselines come from the weeks before each strike, so a lasting drop from an earlier strike also shows up in the windows of later ones; the per-strike tiles make that visible.</li>
        <li><b>Rates</b>: each poll reads the newest 100 items; if they span more than an hour the last hour is counted exactly, otherwise the rate is extrapolated from the span covered.</li>
      </ul></div>
      <h2 class="sect">Prior work</h2>
      <div class="prose"><p>The event-study design follows a community analysis posted to r/theydidthemath,
        <a href="https://www.reddit.com/r/theydidthemath/comments/1x3q43a/" rel="noopener">"Comparing Reddit activity around three reported Yandex attacks"</a>.
        It used hourly Syften counts for 968 subreddits and found 90 that declined after all three strikes, none of which held across every timing check.
        Commenters asked for random-date comparisons and controls; the placebo test, the control group and the robustness grid here answer that.</p></div>
      <h2 class="sect">Anti-trans and anti-LGBTQ rhetoric</h2>
      <div class="prose">
        <p>Influence operations have used anti-trans topics: a fake LGBTQ+ outlet run by the Russian operation Doppelganger filed stories under "Trans youth" and "Woke Wars" (<a href="https://dfrlab.org/2024/09/18/doppelganger-us-election/" rel="noopener">DFRLab, 2024</a>). Most anti-trans rhetoric online is domestic, and others have measured it where it mostly lives, on X:</p>
        <ul>
          <li><a href="https://counterhate.com/research/digital-hate-lgbtq/" rel="noopener">CCDH and the Human Rights Campaign (2022)</a>: 989,547 tweets in January to July 2022 used slurs such as "groomer" about LGBTQ+ people; "grooming" talk rose 406% in the month after Florida's "Don't Say Gay or Trans" law.</li>
          <li><a href="https://counterhate.com/blog/the-musk-bump-quantifying-the-rise-in-hate-speech-under-elon-musk/" rel="noopener">CCDH (2022)</a>: tweets using one transphobic slur rose 62%, from 3,159 to 5,117 a day, after Twitter changed owner.</li>
          <li><a href="https://www.isdglobal.org/digital-dispatch/offline-events-online-threats-analyzing-online-extremist-targeting-of-lgbtq-communities/" rel="noopener">ISD (2025)</a>: over 97,000 anti-LGBTQ+ posts from more than 1,000 violent extremist channels between August 2024 and January 2025; targeted hate doubled around the US election, and anti-trans content rose to 46% of it.</li>
          <li><a href="https://bethylamine.github.io/" rel="noopener">Beth's Anti-Transphobia Library</a> catalogues the talking points, their code words and how they recycle older homophobic ones, and summarises 52,401 Twitter accounts reported as transphobic.</li>
        </ul>
        <p>On Bluesky this rhetoric is rare, and in a hand check in October 2026 almost none of the matching posts used it: of about 50 recent posts each, "groomer" was mostly pet grooming, "women's sports" and "protect women" were mostly fans and people criticising the framing, and "TRAs" matched the Spanish word "tras". Counting them would measure the pushback, not the rhetoric, so Bluesky is not charted.</p>
        <p>On X, from October 2026, the <b>anti-trans</b> group counts two searches: the slur "troon" (listed as a slur in Beth's glossary), about 3,300 original posts a day, and the phrase "no such thing as (a) trans", about 160 a day (<a href="https://www.the74million.org/article/in-private-texts-ny-ed-council-reps-congressional-candidate-demean-lgbtq-kids/" rel="noopener">The 74, 2023</a>, documents the claim). Counts include people quoting the words to object; how many has not been checked on X. See <code>docs/NARRATIVES.md</code>.</p>
      </div>
      <h2 class="sect">Annotated events</h2>
      <div class="prose"><ul>${ev || '<li>None.</li>'}</ul></div>
      <h2 class="sect">Sources</h2>
      <div class="prose"><ul>
        <li>IODA, Georgia Tech Internet Intelligence Lab — outage signals.</li>
        <li>Cloudflare Radar — CC BY-NC 4.0.</li>
        <li>Reddit Data API / public feeds; Arctic Shift archive for history.</li>
        <li>Bluesky public AppView search.</li>
        <li>X API post counts (pay-per-use; counts only, no posts read).</li>
        <li>All data: <a href="api/export/daily.csv?days=365">daily CSV</a>${STATIC ? '' : ' · <a href="docs">API</a>'} · <a href="#report">dated reports</a>.</li>
      </ul></div>
      <h2 class="sect">Display</h2>
      <div class="switch" data-palette role="group" aria-label="Colour palette">${[['term-phosphor', 'PHOSPHOR'], ['term-amber', 'AMBER'], ['term-navy', 'BROADCAST 8S']]
        .map(([v, l]) => `<button class="chip" data-v="${v}" aria-pressed="${pal === v}">${l}</button>`).join('')}</div>
      <div class="switch" data-mode role="group" aria-label="Light or dark">${[['dark', 'DARK'], ['light', 'LIGHT']]
        .map(([v, l]) => `<button class="chip" data-v="${v}" aria-pressed="${document.documentElement.dataset.mode === v}">${l}</button>`).join('')}</div>
      <p class="note">EVERY PALETTE HAS A DARK AND A LIGHT VERSION. WITHOUT A CHOICE HERE, THE SITE FOLLOWS YOUR SYSTEM SETTING.</p>
      <p class="note" id="crt-note">CRT SCANLINES · OFF BY DEFAULT: THE EFFECT LOWERS TEXT CONTRAST</p>
      <div class="switch" data-crt role="group" aria-label="CRT scanlines" aria-describedby="crt-note">
        <button class="chip" data-v="on" aria-pressed="${crt === 'on'}">ON</button>
        <button class="chip" data-v="off" aria-pressed="${crt !== 'on'}">OFF</button>
      </div>`;
    view.querySelector('[data-palette]').addEventListener('click', (e) => {
      const b = e.target.closest('button'); if (!b) return;
      document.documentElement.dataset.palette = b.dataset.v;
      try { localStorage.setItem('palette', b.dataset.v); } catch { /* storage unavailable: setting lasts this visit */ }
      views.about();
    });
    view.querySelector('[data-mode]').addEventListener('click', (e) => {
      const b = e.target.closest('button'); if (!b) return;
      setMode(b.dataset.v, true);
      views.about();
    });
    view.querySelector('[data-crt]').addEventListener('click', (e) => {
      const b = e.target.closest('button'); if (!b) return;
      document.documentElement.dataset.crt = b.dataset.v;
      try { localStorage.setItem('crt', b.dataset.v); } catch { /* storage unavailable: setting lasts this visit */ }
      views.about();
    });
  },
};

// ── Routing, refresh, clock ─────────────────────────────────────────────────
const TITLES = { live: 'BOT MONITOR', communities: 'GROUPS', history: 'HISTORY', report: 'REPORT', alerts: 'ALERTS', about: 'ABOUT' };
const PAGE_TITLES = { live: 'Live', communities: 'Groups', history: 'History', report: 'Report', alerts: 'Alerts', about: 'About' };
let paused = false;

// moveFocus: true when the visitor switched tabs, so focus lands on the new
// view's heading instead of staying on the nav link while content swaps silently.
function route(moveFocus = false) {
  const name = (location.hash.slice(1) || 'live').split('?')[0];
  const key = views[name] ? name : 'live';
  document.querySelectorAll('.nav a').forEach((a) => {
    if (a.getAttribute('href') === `#${key}`) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current');
  });
  $('title').innerHTML = `${glyph('// ')}${TITLES[key]}`;
  document.title = key === 'live' ? 'Bot Traffic Monitor' : `${PAGE_TITLES[key]} · Bot Traffic Monitor`;
  if (!snap) return;
  Promise.resolve(views[key]())
    .then(() => { if (moveFocus) $('title').focus(); })
    .catch((e) => toast(`VIEW FAILED: ${e.message}`));
}

async function refresh() {
  try {
    snap = await api('/api/snapshot');
    setState(STATIC ? 'SNAPSHOT' : paused ? 'PAUSED' : 'LIVE');
    $('updated').textContent = `UPDATED ${hhmm(snap.now)} UTC`;
    // Never redraw under someone: not while paused, and not while focus is inside the view.
    if (paused || view.contains(document.activeElement)) return;
    const name = (location.hash.slice(1) || 'live');
    if (name === 'live' || name === 'communities') route();
  } catch {
    setState('OFFLINE');
  }
}

function tickClock() {
  const n = Math.floor(Date.now() / 1000);
  $('clock').textContent = hhmm(n);
}

// Light or dark. The page head sets it before the first paint; `save` is false when it
// only follows the system setting, so a later system change is still followed.
function setMode(mode, save) {
  document.documentElement.dataset.mode = mode;
  const btn = $('mode');
  btn.setAttribute('aria-pressed', String(mode === 'light'));
  if (save) {
    try { localStorage.setItem('mode', mode); } catch { /* storage unavailable: setting lasts this visit */ }
  }
}

async function start() {
  setMode(document.documentElement.dataset.mode || 'dark', false);
  $('mode').addEventListener('click', () => setMode(document.documentElement.dataset.mode === 'light' ? 'dark' : 'light', true));
  const system = window.matchMedia?.('(prefers-color-scheme: light)');
  system?.addEventListener('change', (e) => {
    let saved = null;
    try { saved = localStorage.getItem('mode'); } catch { /* storage unavailable */ }
    if (!saved) setMode(e.matches ? 'light' : 'dark', false);
  });
  try {
    const crt = localStorage.getItem('crt');  // CRT overlay is opt-in: it lowers contrast
    if (crt) document.documentElement.dataset.crt = crt;
  } catch { /* storage unavailable */ }
  tickClock();
  setInterval(tickClock, 30_000);
  const asn = $('asn');
  const setAsn = (open) => { $('asn-info').hidden = !open; asn.setAttribute('aria-expanded', String(open)); };
  asn.addEventListener('click', () => setAsn($('asn-info').hidden));
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && !$('asn-info').hidden) { setAsn(false); asn.focus(); }
  });
  $('pause').addEventListener('click', () => {
    paused = !paused;
    $('pause').setAttribute('aria-pressed', String(paused));
    setState(STATIC ? 'SNAPSHOT' : paused ? 'PAUSED' : 'LIVE');
    if (!paused) refresh();
  });

  boot.line('fetch /api/health');
  try {
    await api('/api/health'); boot.ok();
    boot.line('fetch /api/snapshot · compute baselines');
    snap = await api('/api/snapshot'); boot.ok();
  } catch (e) {
    setState('OFFLINE');
    $('boot-pct').textContent = 'API UNREACHABLE';
    toast(`API UNREACHABLE — ${e.message}`);
    return;
  }
  setState(STATIC ? 'SNAPSHOT' : 'LIVE');
  $('updated').textContent = `UPDATED ${hhmm(snap.now)} UTC`;
  setTimeout(() => { boot.done(); route(); }, reduced ? 0 : 360);
  setInterval(refresh, REFRESH_MS);
}

window.addEventListener('hashchange', () => route(true));
let enhancePending = false;
new MutationObserver(() => {
  if (enhancePending) return;
  enhancePending = true;
  requestAnimationFrame(() => { enhancePending = false; enhance(view); });
}).observe(view, { childList: true, subtree: true });
let resizeTimer;
window.addEventListener('resize', () => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(() => { if (!view.contains(document.activeElement)) route(); }, 250);
});
route();
start();
