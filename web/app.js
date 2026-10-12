// Bot Traffic Monitor front end. Vanilla JS, no build step; markup uses the
// terminal kit classes from /design/terminal.css (see DESIGN_GUIDE.md).

const $ = (id) => document.getElementById(id);
const view = $('view');
const REFRESH_MS = 60_000;
const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;

const TAG_SHORT = {
  'political-right': 'RIGHT', political: 'POLITICS', regional: 'REGIONAL',
  russia: 'RUSSIA', control: 'CONTROL',
};
const PLATFORM_SHORT = { ioda: 'IODA', cloudflare: 'CLOUDFLARE', reddit: 'REDDIT', bluesky: 'BLUESKY' };

let snap = null;
const state = { tag: 'all', allMetrics: false, a: null, b: null, days: 30, compare: 'ref',
  corrTags: new Set(['political-right', 'control']) };
// Line style per group on the correlation chart; Yandex itself is always a1.
const TAG_LINE = { 'political-right': 'l-a3', political: 'l-a2', regional: 'l-a2 l-dash', russia: 'l-ink', control: 'l-muted' };

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
function setState(text) { $('state').innerHTML = `${glyph('●')} ${esc(text)}`; }

// ── API ─────────────────────────────────────────────────────────────────────
// Static mode: the site was exported by `python -m tracker publish` and is served
// as plain files (e.g. GitHub Pages), so API paths map onto pre-built JSON files.
const STATIC = document.querySelector('meta[name="data-mode"]')?.content === 'static';

function staticFile(path) {
  const url = new URL(path, 'http://local');
  const q = url.searchParams;
  const series = url.pathname.match(/^\/api\/series\/([^/]+)\/(points|event-study)$/);
  if (series && series[2] === 'points') {
    const bucket = q.get('bucket') === 'day' ? 'day' : 'hour';
    const since = (snap?.now ?? Date.now() / 1000) - Number(q.get('days') || 30) * 86400;
    return [`api/series/${series[1]}/${bucket}.json`, (d) => ({ ...d, points: d.points.filter((p) => p[0] >= since) })];
  }
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
    `<div class="toast ${kind}" role="status"><span class="led${kind === 'err' ? ' three' : ''}"></span>${esc(message)}</div>`);
}

// ── Components ──────────────────────────────────────────────────────────────
function bars(items) {
  // items: [{value, label, text}] — value scaled across the series' own range, 12% floor.
  const vals = items.map((i) => i.value).filter((v) => v != null);
  if (!vals.length) return '<p class="note">NO DATA YET — NEEDS A BASELINE PERIOD</p>';
  const lo = Math.min(...vals), hi = Math.max(...vals), span = hi - lo || 1;
  const peak = items.findIndex((i) => i.value === hi);
  return `<div class="bars">${items.map((it, i) => {
    const h = it.value == null ? 0 : 12 + ((it.value - lo) / span) * 88;
    return `<div class="bar${i === peak ? ' peak' : ''}">
      <div class="bar-value">${esc(it.text)}</div>
      <div class="bar-track"><div class="bar-fill" style="--pct:${h}%"></div></div>
      <div class="bar-label">${esc(it.label)}</div></div>`;
  }).join('')}</div>`;
}

function niceMax(v) {
  if (v <= 0) return 1;
  const p = 10 ** Math.floor(Math.log10(v));
  return [1, 2, 2.5, 5, 10].map((m) => m * p).find((m) => m >= v);
}

// SVG line chart with labeled axes, event markers, reference band and a hover readout.
// `lines`: [{label, cls, points: [[ts, value], ...], area?}] drawn in order (last on top).
function chart(el, readout, lines, { start, end, unit, events = [], ref = null, baseline = null }) {
  const W = Math.max(el.clientWidth, 280), H = 170, L = 40, R = 6, T = 6, B = 18;
  lines = lines.filter((l) => l.points.length);
  if (!lines.length) {
    el.innerHTML = '';
    readout.innerHTML = '<span class="muted">NO DATA IN THIS RANGE</span>';
    return;
  }
  const values = lines.flatMap((l) => l.points.map((p) => p[1]));
  if (baseline != null) values.push(baseline);
  const lo = Math.min(0, ...values), hi = niceMax(Math.max(...values));
  const x = (t) => L + ((t - start) / (end - start)) * (W - L - R);
  const y = (v) => T + (1 - (v - lo) / (hi - lo || 1)) * (H - T - B);
  const xy = (p) => `${x(p[0]).toFixed(1)},${y(p[1]).toFixed(1)}`;

  const drawn = lines.map((line) => {
    // Break the line where samples are missing for more than 3 steps.
    const pts = line.points;
    const steps = pts.slice(1).map((p, i) => p[0] - pts[i][0]).sort((m, n) => m - n);
    const step = steps[Math.floor(steps.length / 2)] || 3600;
    const segs = [[]];
    pts.forEach((p, i) => {
      if (i && p[0] - pts[i - 1][0] > step * 3) segs.push([]);
      segs[segs.length - 1].push(p);
    });
    const path = segs.filter((g) => g.length).map((g) => `M${g.map(xy).join('L')}`).join('');
    const area = !line.area ? '' : segs.filter((g) => g.length > 1).map((g) =>
      `M${x(g[0][0]).toFixed(1)},${y(lo)}L${g.map(xy).join('L')}L${x(g[g.length - 1][0]).toFixed(1)},${y(lo)}Z`).join('');
    // Isolated samples (no neighbour within 3 steps) get a dot, or they'd be invisible.
    const lone = segs.filter((g) => g.length === 1).map(([p]) =>
      `<circle class="dot ${line.cls || ''}" r="2" cx="${x(p[0]).toFixed(1)}" cy="${y(p[1]).toFixed(1)}"/>`).join('');
    return `${area ? `<path class="area" d="${area}"/>` : ''}<path class="line ${line.cls || ''}" d="${path}"/>${lone}`;
  }).join('');

  const yTicks = [lo, (lo + hi) / 2, hi];
  const days = (end - start) / 86400;
  const every = days <= 8 ? 1 : days <= 16 ? 2 : days <= 35 ? 7 : 14;
  const xTicks = [];
  for (let t = Math.ceil(start / 86400) * 86400; t <= end; t += every * 86400) xTicks.push(t);

  const refBand = ref && ref.end > start && ref.start < end
    ? `<rect class="ref-band" x="${x(Math.max(ref.start, start))}" y="${T}" width="${x(Math.min(ref.end, end)) - x(Math.max(ref.start, start))}" height="${H - T - B}"/>`
    : '';
  const base = baseline == null ? '' : `<line class="baseline" x1="${L}" x2="${W - R}" y1="${y(baseline)}" y2="${y(baseline)}"/>
    <text class="axis" x="${W - R}" y="${y(baseline) - 3}" text-anchor="end">${num(baseline)} = PRE-STRIKE</text>`;
  // Event labels run vertically down their marker, so close events never collide.
  const ev = events.filter((e) => e.ts >= start && e.ts <= end).map((e) => {
    const ex = x(e.ts);
    return `<line class="event" x1="${ex}" x2="${ex}" y1="${T}" y2="${H - B}"/>
     <text class="event-label" transform="translate(${ex - 3},${T + 2}) rotate(-90)" text-anchor="end">${esc(e.short)}</text>`;
  }).join('');

  // Each line is named at its last point, so lines are told apart by text, not colour alone.
  const endLabels = lines.length < 2 ? '' : lines.map((l) => {
    const p = l.points[l.points.length - 1];
    return `<text class="line-label ${l.cls || ''}" x="${(x(p[0]) - 3).toFixed(1)}" y="${(y(p[1]) - 4).toFixed(1)}" text-anchor="end">${esc(l.label)}</text>`;
  }).join('');
  const summary = lines.map((l) => {
    const vs = l.points.map((p) => p[1]);
    return `${l.label}: latest ${num(vs[vs.length - 1])}, range ${num(Math.min(...vs))} to ${num(Math.max(...vs))}`;
  }).join('; ');

  el.innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" tabindex="0"
    aria-label="Chart, ${esc(unit)}, ${mmdd(start)} to ${mmdd(end)}. ${esc(summary)}. Left and right arrow keys read values; the data table below lists them.">
    ${refBand}
    ${yTicks.map((v) => `<line class="grid" x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}"/>
      <text class="axis" x="${L - 5}" y="${y(v) + 3}" text-anchor="end">${num(v)}</text>`).join('')}
    ${xTicks.map((t) => `<text class="axis" x="${x(t)}" y="${H - 4}" text-anchor="middle">${mmdd(t)}</text>`).join('')}
    ${base}${drawn}${endLabels}${ev}
    <line class="cursor" y1="${T}" y2="${H - B}" visibility="hidden"/>
  </svg>
  <details class="data-table"><summary>Data table${lines[0].points.length > 120 ? ' · daily means' : ''}</summary><div class="table-wrap"></div></details>`;

  const svg = el.querySelector('svg'), cur = svg.querySelector('.cursor');
  const near = (pts, t) => pts.reduce((best, p) => (Math.abs(p[0] - t) < Math.abs(best[0] - t) ? p : best), pts[0]);
  const describe = (t, prefix) => {
    if (lines.length === 1) {
      const p = near(lines[0].points, t);
      return `${prefix}${num(p[1])} <span class="muted">${esc(unit)} · ${stamp(p[0])}</span>`;
    }
    const p0 = near(lines[0].points, t);
    return `${prefix}<span class="muted">${stamp(p0[0])} ·</span> ${lines.map((l) =>
      `${esc(l.label)} ${num(near(l.points, p0[0])[1])}`).join(' · ')} <span class="muted">${esc(unit)}</span>`;
  };
  const idle = () => { readout.innerHTML = describe(end, 'LATEST '); };
  idle();
  svg.addEventListener('pointermove', (e) => {
    const box = svg.getBoundingClientRect();
    const t = start + ((e.clientX - box.left) / box.width * W - L) / (W - L - R) * (end - start);
    const p = near(lines[0].points, t);
    cur.setAttribute('visibility', 'visible');
    cur.setAttribute('x1', x(p[0])); cur.setAttribute('x2', x(p[0]));
    readout.innerHTML = describe(t, '');
  });
  svg.addEventListener('pointerleave', () => { cur.setAttribute('visibility', 'hidden'); idle(); });

  // Keyboard: arrows step through the first line's points; the readout is announced.
  let idx = lines[0].points.length - 1;
  const show = () => {
    const p = lines[0].points[idx];
    cur.setAttribute('visibility', 'visible');
    cur.setAttribute('x1', x(p[0])); cur.setAttribute('x2', x(p[0]));
    readout.innerHTML = describe(p[0], '');
  };
  readout.setAttribute('aria-live', 'polite');
  svg.addEventListener('blur', () => { cur.setAttribute('visibility', 'hidden'); idle(); });
  svg.addEventListener('keydown', (e) => {
    const last = lines[0].points.length - 1;
    const moves = { ArrowLeft: -1, ArrowRight: 1, PageUp: -24, PageDown: 24, Home: -Infinity, End: Infinity };
    if (!(e.key in moves)) return;
    e.preventDefault();
    idx = Math.max(0, Math.min(last, idx + moves[e.key]));
    show();
  });

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
    const keys = [...rowsBy.keys()].sort((a, b) => b - a);
    const when = (t) => (daily ? mmdd(t) : stamp(t));
    details.querySelector('.table-wrap').innerHTML = `<table class="table" aria-label="${esc(unit)} data">
      <thead><tr><th scope="col">${daily ? 'DATE UTC' : 'TIME'}</th>${lines.map((l) => `<th scope="col" class="t-num">${esc(l.label)}</th>`).join('')}</tr></thead>
      <tbody>${keys.map((k) => `<tr><td class="t-key">${when(k)}</td>${rowsBy.get(k).map((v) => `<td class="t-num">${num(v)}</td>`).join('')}</tr>`).join('')}</tbody>
    </table>`;
  });
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
    { start, end, unit: '% OF PRE-STRIKE', events: c.events, ref: c.reference, baseline: 100 });

  const swatch = (cls) => `<svg class="swatch" viewBox="0 0 22 8" aria-hidden="true"><line class="line ${cls}" x1="1" x2="21" y1="4" y2="4"/></svg>`;
  $('corr-legend').innerHTML = `<span class="legend-item">${swatch('l-a1')}YANDEX CLOUD</span>${c.groups.map((g) =>
    `<button class="legend-item" data-v="${esc(g.tag)}" aria-pressed="${state.corrTags.has(g.tag)}">${swatch(TAG_LINE[g.tag] || 'l-ink')}${esc(label(g.tag))}
      ${g.r == null ? '' : `<span class="sr-only">correlation</span> R ${g.r.toFixed(2)}`}</button>`).join('')}`;
  $('corr-legend').onclick = (e) => {
    const b = e.target.closest('button'); if (!b) return;
    if (state.corrTags.has(b.dataset.v)) state.corrTags.delete(b.dataset.v); else state.corrTags.add(b.dataset.v);
    renderCorrelation(c);
  };

  const latest = (vals) => { for (let i = vals.length - 1; i >= 0; i--) if (vals[i] != null) return vals[i]; return null; };
  $('corr-tiles').innerHTML = c.groups.map((g) => `<div class="tile">
    <div class="tile-value${g.tag === 'political-right' ? ' hl' : ''}">${g.r == null ? '—' : g.r.toFixed(2)}</div>
    <div class="tile-label">R · ${esc(label(g.tag))} VS YANDEX</div>
    <div class="tile-sub">${latest(g.values) == null ? 'NO DATA' : `NOW ${Math.round(latest(g.values))}% · ${g.r_days} DAYS`}</div></div>`).join('');
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
      const status = share == null ? 'NO PRE-STRIKE BASELINE' : share >= 90 ? 'NOMINAL' : share >= 50 ? 'DEGRADED' : 'SEVERE OUTAGE';
      hero = `<div class="hero">
        <div class="hero-value">${share == null ? num(ref.latest) : Math.round(share)}<span class="hero-unit">${share == null ? '' : '%'}</span></div>
        <div class="hero-status">${esc(status)}</div>
        <div class="hero-meta">${esc(ref.label)} · ${share == null ? '' : 'OF PRE-STRIKE LEVEL · '}${num(ref.latest)} ${esc(ref.unit)} · ${stamp(ref.latest_ts)}</div>
      </div>`;
    }

    const chips = snap.runs.map((r) => {
      const off = (r.error || '').startsWith('not configured');
      const cls = off ? 'ghost' : r.ok ? '' : 'three';
      return `<span class="chip ${cls}" title="${esc(r.error || '')}">${esc(PLATFORM_SHORT[r.platform] || r.platform)} ${off ? 'OFF' : r.ok ? 'OK' : 'ERR'}</span>`;
    }).join('');

    const tiles = infra.map((s) => `<div class="tile">
      <div class="tile-value${s.key === ref?.key ? ' hl' : ''}">${num(s.latest)}</div>
      <div class="tile-label">${esc(s.unit)} · ${esc(s.label)}</div>
      <div class="tile-sub">REF ${pct(s.change_ref)} · 7D ${pct(s.change_7d)}</div></div>`).join('');

    const MODES = {
      ref: { field: 'change_ref', n: 'n_ref', note: `LAST 24 H VS ${mmdd(snap.reference.start)} – ${mmdd(snap.reference.end)} MEAN` },
      '7d': { field: 'change_7d', n: 'n_7d', note: 'LAST 3 H VS SAME HOURS, PREVIOUS 7 DAYS (MEDIAN)' },
      event: { field: 'event_effect', n: 'n_event',
        note: `${snap.event_window} H AFTER EACH STRIKE VS SAME WEEKDAY-HOUR 1–3 WEEKS EARLIER, EQUAL WEIGHT PER STRIKE` },
    };
    const mode = MODES[state.compare];
    const groupBars = bars(groups.map((g) => ({
      value: g[mode.field], label: TAG_SHORT[g.tag] || g.tag.toUpperCase(),
      text: g[mode.field] == null ? '—' : `${pct(g[mode.field])} n${g[mode.n]}`,
    })));
    const sigTable = state.compare !== 'event' ? '' : `<div class="table-wrap"><table class="table" aria-label="Change after strikes by group">
      <thead><tr><th scope="col">GROUP</th>${th('MEDIAN Δ', 'Median change after strikes', 't-num')}${th('P &lt; 0.05', 'Share with placebo p below 0.05', 't-num')}${th('N', 'Communities', 't-num')}</tr></thead>
      <tbody>${groups.map((g) => `<tr><td class="t-value">${esc(TAG_SHORT[g.tag] || g.tag)}</td>
        <td class="t-num ${dirClass(g.event_effect)}">${pct(g.event_effect)}</td>
        <td class="t-num">${g.share_sig == null ? '—' : Math.round(g.share_sig * 100) + '%'}</td>
        <td class="t-num">${g.n_event}</td></tr>`).join('')}</tbody></table></div>
      <p class="note">P &lt; 0.05 = SHARE OF THE GROUP'S COMMUNITIES WHOSE STRIKE-WINDOW DROP IS RARER THAN 5% OF RANDOM PRE-STRIKE WINDOWS.
        ABOUT 5% WOULD PASS BY CHANCE ALONE — COMPARE WITH CONTROL.</p>`;

    const cov = snap.coverage;
    const ticks = cov == null ? '········' : '|'.repeat(Math.round(cov * 8)).padEnd(8, '·');
    const stale = snap.series.filter((s) => !s.fresh && !snap.runs.find((r) => r.platform === s.platform && (r.error || '').startsWith('not configured')));

    view.innerHTML = `${hero}
      <h2 class="sect">Correlation · activity vs Yandex Cloud · % of pre-strike</h2>
      <div class="legend" id="corr-legend" role="group" aria-label="Lines shown on the correlation chart"></div>
      <div class="readout" id="corr-readout"></div>
      <div class="chart" id="corr-chart"><p class="note">LOADING…</p></div>
      <div class="tiles" id="corr-tiles"></div>
      <p class="note">DAILY MEDIAN OF EACH GROUP'S COMMUNITIES · 100 = PRE-STRIKE MEAN · R = PEARSON CORRELATION OF DAILY VALUES
        WITH YANDEX CLOUD REACHABILITY · CONTROL = NON-POLITICAL COMMUNITIES · CORRELATION, NOT PROOF OF CAUSE — METHODS ON ABOUT</p>
      <div class="chips" style="margin-top:14px">${chips}</div>
      <h2 class="sect">Infrastructure · latest value</h2>
      <div class="tiles">${tiles}</div>
      <h2 class="sect">Community activity · median change by group</h2>
      <div class="switch" data-compare role="group" aria-label="Compare community activity">
        <button class="chip" data-v="ref" aria-pressed="${state.compare === 'ref'}">VS PRE-STRIKE</button>
        <button class="chip" data-v="7d" aria-pressed="${state.compare === '7d'}">VS LAST 7 DAYS</button>
        <button class="chip" data-v="event" aria-pressed="${state.compare === 'event'}">STRIKE WINDOWS</button>
      </div>
      ${groupBars}
      <p class="note">${mode.note} · n = COMMUNITIES WITH A BASELINE · CONTROL = NON-POLITICAL</p>
      ${sigTable}
      <div class="qband"><span class="qband-label">DATA COVERAGE ${cov == null ? '—' : Math.round(cov * 100) + '%'}</span>
        <span class="qband-ticks">${ticks}</span><button class="qband-action" data-why aria-expanded="false" aria-controls="why">WHY?&gt;</button></div>
      <div class="explain note" hidden id="why">SHARE OF CONFIGURED SERIES UPDATED IN THE LAST 3 H.
        ${stale.length ? 'STALE: ' + stale.slice(0, 12).map((s) => esc(s.key)).join(' · ') + (stale.length > 12 ? ` · +${stale.length - 12} MORE` : '') : 'ALL SERIES CURRENT.'}</div>
      <h2 class="sect">${esc(ref ? ref.label : 'Infrastructure')} · ${esc(ref ? ref.unit : '')} · 14 days</h2>
      <div class="readout" id="live-readout"></div>
      <div class="chart" id="live-chart"></div>
      <p class="note">SHADED = PRE-STRIKE REFERENCE · DASHED = REPORTED STRIKES (SEE ABOUT)</p>
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

    api('/api/correlation').then(renderCorrelation).catch(() => {
      $('corr-chart').innerHTML = '<p class="note">CORRELATION DATA UNAVAILABLE</p>';
    });

    if (ref) {
      const end = snap.now, start = end - 14 * 86400;
      api(`/api/series/${encodeURIComponent(ref.key)}/points?days=14&bucket=hour`).then((d) =>
        lineChart($('live-chart'), $('live-readout'), d.points, { start, end, unit: ref.unit, events: snap.events, ref: snap.reference }))
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

    view.innerHTML = `<h2 class="sect">Filter</h2>
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
      <p class="note">NOW = LATEST RATE · Δ 7D = LAST 3 H VS SAME HOURS PREVIOUS 7 DAYS · Δ REF = LAST 24 H VS PRE-STRIKE MEAN
        · STRIKE Δ = ${snap.event_window} H AFTER EACH STRIKE VS SAME WEEKDAY-HOUR 1–3 WEEKS EARLIER · P = PLACEBO TEST AGAINST RANDOM PRE-STRIKE WINDOWS
        (WITH ${rows.length} SERIES, ~${Math.round(rows.length * 0.05)} WILL SHOW P &lt; 0.05 BY CHANCE)
        · R = PEARSON CORRELATION OF DAILY MEANS WITH ${esc(refLabel)}, LAST 30 DAYS · — = NOT ENOUGH DATA · SELECT A COMMUNITY NAME FOR ITS HISTORY</p>`;

    view.querySelector('[data-tags]').addEventListener('click', (e) => {
      const b = e.target.closest('button'); if (b) { state.tag = b.dataset.v; views.communities(); }
    });
    view.querySelector('[data-metrics]').addEventListener('click', (e) => {
      const b = e.target.closest('button'); if (b) { state.allMetrics = b.dataset.v === 'all'; views.communities(); }
    });
    view.querySelectorAll('a[data-key]').forEach((a) => a.addEventListener('click', () => { state.b = a.dataset.key; }));
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
      <p class="note">HOURLY MEANS, UTC · SHADED = PRE-STRIKE REFERENCE · DASHED = REPORTED STRIKES</p>
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
      lineChart($(chart), $(ro), d.points, { start, end, unit: s.unit, events: snap.events, ref: snap.reference });
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
        <div class="tiles">${d.events.map((e, i) => `<div class="tile">
          <div class="tile-value">${pct(main.per_event[i])}</div>
          <div class="tile-label">${esc(e.short)} · ${stamp(e.ts)}</div>
          <div class="tile-sub">${e.timed ? 'MEASURED TIME' : 'MIDNIGHT UTC · TIME UNKNOWN'}</div></div>`).join('')}</div>
        <p class="note">EACH CELL: CHANGE IN TOTAL ACTIVITY VS SAME WEEKDAY-HOUR 1–3 WEEKS EARLIER, AVERAGED OVER STRIKES · ${main.placebo_n >= 50
          ? `p = SHARE OF 500 DRAWS FROM ${main.placebo_n} RANDOM PRE-STRIKE WINDOWS WITH A DROP AT LEAST THIS LARGE`
          : 'p NEEDS 4+ WEEKS OF HISTORY BEFORE THE FIRST STRIKE — RUN THE BACKFILL'} · ○ = p &lt; 0.05 ·
          TILES = EACH STRIKE, 12 H WINDOW. A REAL EFFECT SHOULD HOLD ACROSS THE GRID, NOT IN ONE CELL.</p>`;
    }).catch(() => { $('es-grid').innerHTML = '<p class="note">UNAVAILABLE</p>'; });
    api(`/api/series/${encodeURIComponent(state.b)}/points?days=14&bucket=day`).then((d) => {
      const s = byKey(state.b);
      $('daily-title').textContent = `${s.label} · ${s.unit} · daily mean, 14 days`;
      $('daily-bars').innerHTML = bars(d.points.map(([t, v]) => ({ value: v, label: mmdd(t).slice(3), text: num(v) })));
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
      <p class="note">AN ALERT FIRES WHEN AN INFRASTRUCTURE SIGNAL MOVES ≥25% OR A COMMUNITY GROUP MEDIAN MOVES ≥30% VS ITS 7-DAY SAME-HOUR BASELINE · 12 H COOLDOWN PER SIGNAL</p>`;
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
      <p class="note">MEDIANS ACROSS EACH GROUP'S COMMUNITIES · P &lt; .05 = SHARE WITH A PLACEBO P BELOW 0.05 (~5% BY CHANCE) ·
        ROBUST = SHARE WITH A ≥5% DROP AT P &lt; .05 IN 5+ OF 9 TIMING CHECKS · R = CORRELATION WITH YANDEX CLOUD REACHABILITY ·
        INDEX 100 = PRE-STRIKE</p>

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
      <p class="note">RATES PER HOUR · STRIKE Δ = 12 H AFTER EACH STRIKE VS SAME WEEKDAY-HOUR 1–3 WEEKS EARLIER · P = PLACEBO TEST ·
        ROBUST = TIMING CHECKS (OF 9) WITH A ≥5% DROP AT P &lt; .05 · FULL COLUMN DEFINITIONS IN THE BUNDLE README</p>

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
        <p>It records two kinds of signal side by side. <b>Infrastructure</b>: how much of Yandex's network is reachable (IODA active probing and BGP routing) and, when configured, the share of HTTP requests from Yandex's network that Cloudflare classifies as bots. <b>Communities</b>: comments and posts per hour in selected subreddits, and posts per hour matching keywords on Bluesky. Only timestamps are counted; no usernames or content are stored.</p>
      </div>
      <h2 class="sect">Read this before citing a number</h2>
      <div class="prose"><ul>
        <li>Correlation is not attribution. A drop in a community after an outage is consistent with bot or troll accounts going offline, but also with news cycles, weekends, moderation changes, Reddit's own systems, or real users in Russia losing service.</li>
        <li>Compare against the <b>control</b> group. A drop that also appears in non-political communities is not evidence of anything political.</li>
        <li>Cloudflare's "bot" share for AS13238 is dominated by Yandex's own search crawlers. It measures automated traffic from that network, not influence operations.</li>
        <li>Group tags (right, political, regional, russia, control) are editorial labels set in <code>config/sources.toml</code>. They are open to challenge; propose changes there.</li>
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
      <h2 class="sect">Annotated events</h2>
      <div class="prose"><ul>${ev || '<li>None.</li>'}</ul></div>
      <h2 class="sect">Sources</h2>
      <div class="prose"><ul>
        <li>IODA, Georgia Tech Internet Intelligence Lab — outage signals.</li>
        <li>Cloudflare Radar — CC BY-NC 4.0.</li>
        <li>Reddit Data API / public feeds; Arctic Shift archive for history.</li>
        <li>Bluesky public AppView search.</li>
        <li>All data: <a href="api/export/daily.csv?days=365">daily CSV</a>${STATIC ? '' : ' · <a href="docs">API</a>'} · <a href="#report">dated reports</a>.</li>
      </ul></div>
      <h2 class="sect">Display</h2>
      <div class="switch" data-palette role="group" aria-label="Colour palette">${[['term-phosphor', 'PHOSPHOR'], ['term-amber', 'AMBER'], ['term-navy', 'BROADCAST 8S'], ['term-light', 'LIGHT']]
        .map(([v, l]) => `<button class="chip" data-v="${v}" aria-pressed="${pal === v}">${l}</button>`).join('')}</div>
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
    view.querySelector('[data-crt]').addEventListener('click', (e) => {
      const b = e.target.closest('button'); if (!b) return;
      document.documentElement.dataset.crt = b.dataset.v;
      try { localStorage.setItem('crt', b.dataset.v); } catch { /* storage unavailable: setting lasts this visit */ }
      views.about();
    });
  },
};

// ── Routing, refresh, clock ─────────────────────────────────────────────────
const TITLES = { live: 'BOT MONITOR', communities: 'COMMUNITIES', history: 'HISTORY', report: 'REPORT', alerts: 'ALERTS', about: 'ABOUT' };
const PAGE_TITLES = { live: 'Live', communities: 'Communities', history: 'History', report: 'Report', alerts: 'Alerts', about: 'About' };
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

async function start() {
  try {
    const saved = localStorage.getItem('palette');
    if (saved) document.documentElement.dataset.palette = saved;
    const crt = localStorage.getItem('crt');  // CRT overlay is opt-in: it lowers contrast
    if (crt) document.documentElement.dataset.crt = crt;
  } catch { /* storage unavailable */ }
  tickClock();
  setInterval(tickClock, 30_000);
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
let resizeTimer;
window.addEventListener('resize', () => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(() => { if (!view.contains(document.activeElement)) route(); }, 250);
});
route();
start();
