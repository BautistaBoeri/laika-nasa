/* Laika: mapa de análogos de Marte.
   Lee data/sites.json y data/textos.json (formato en docs/contratos.md). */
'use strict';

// Todos los textos de la interfaz, en un solo lugar (traducir acá).
const T = {
  locale: 'es-AR',
  tagline: 'Análogos de Marte en la Tierra, encontrados por datos',
  marsSite: 'Sitio de Marte',
  mapLabel: 'Mapa de lugares de la Tierra parecidos al sitio de Marte',
  layer: 'Capa de similitud',
  layerShort: 'Capa',
  layerMissing: 'La capa de similitud de este sitio todavía no está disponible',
  siteEyebrow: 'El sitio de Marte',
  how: 'Cómo funciona',
  limits: 'Límites',
  peek: 'Cómo funciona y límites',
  hint: 'Tocá un punto para ver por qué se parece',
  hintSub: '{n} lugares de la Tierra, ordenados por similitud con {target}',
  legendTitle: 'Similitud con {target}',
  legendKnown: 'Análogo ya estudiado',
  panelLabel: 'Detalle del sitio',
  close: 'Cerrar detalle',
  rank: 'Puesto {n} de {total}',
  rankKnown: 'Supera al {p} % del planeta',
  knownBadge: 'Análogo ya estudiado',
  validation: 'Este lugar ya se usa como análogo de Marte. El método no lo sabía, y le dio más puntaje que al {p} % de la superficie analizada.',
  validationNoPct: 'Este lugar ya se usa como análogo de Marte. El método no lo sabía: su puntaje sirve para validar los resultados.',
  informative: 'Informativa: no entra en el puntaje',
  provisional: ' · Resultados provisorios: el análisis sigue en curso.',
  sample: ' · Prototipo con datos de ejemplo: los valores son de relleno.',
  scoreLabel: 'similitud total con {target}',
  imageLabel: 'Sentinel-2 · Copernicus/ESA',
  imageAlt: 'Imagen satelital',
  locator: 'Ubicación',
  varsTitle: 'Variable por variable',
  varsCount: '{n} variables',
  onEarth: 'en la Tierra',
  onMars: 'en Marte',
  why: 'Por qué se parece',
  breaks: 'Dónde se rompe la analogía',
  use: 'Para qué serviría',
  bestVar: 'Donde más se parece',
  worstVar: 'Donde más se aleja',
  noText: 'Sitio encontrado por el método, todavía sin descripción. Lo que se ve arriba es todo lo que dicen los datos.',
  unnamed: 'Sin nombre registrado',
  pointAria: '{name}, similitud {pct} %',
  knownAria: 'análogo ya estudiado',
  globeAria: 'Ubicación de {target} en Marte',
  loadError: 'No se pudieron cargar los datos del mapa. Si abriste el archivo directo, servilo con un servidor local (ver web/README.md).',
  north: 'N', south: 'S', east: 'E', west: 'O'
};

// Cortes de la escala de similitud; los colores salen de --sim-1..5 en styles.css.
const STEPS = [
  { min: 0.00, label: '<40' },
  { min: 0.40, label: '40' },
  { min: 0.55, label: '55' },
  { min: 0.65, label: '65' },
  { min: 0.75, label: '75+' }
];
const css = getComputedStyle(document.documentElement);
STEPS.forEach((s, i) => { s.color = css.getPropertyValue(`--sim-${i + 1}`).trim(); });
const KNOWN_COLOR = css.getPropertyValue('--known').trim();
const LAYER_BOUNDS = [[-85, -180], [85, 180]]; // la capa PNG viene en Web Mercator con estos límites
const WORLD = [[-58, -170], [78, 180]];
const mobile = window.matchMedia('(max-width: 759px)');

const $ = (id) => document.getElementById(id);
const tpl = (s, v) => s.replace(/\{(\w+)\}/g, (_, k) => v[k] ?? '');
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const fmt = (n, d) => Number(n).toLocaleString(T.locale, { minimumFractionDigits: d, maximumFractionDigits: d });
const pct = (x) => Math.round(x * 100);
const step = (x) => STEPS.reduce((acc, s) => (x >= s.min ? s : acc), STEPS[0]);
const coords = (lat, lon) =>
  `${fmt(Math.abs(lat), 2)}° ${lat >= 0 ? T.north : T.south} · ${fmt(Math.abs(lon), 2)}° ${lon >= 0 ? T.east : T.west}`;
const DECIMALS = { slope: 1, roughness: 0 };
const value = (v, x) => {
  if (x === undefined || x === null) return '—';
  const s = fmt(x, DECIMALS[v.id] ?? 2);
  return !v.unit ? s : v.unit === '°' ? s + '°' : `${s} ${v.unit}`;
};

const state = { data: null, textos: {}, target: null, selected: null, layerOn: false };
let map, locator, locatorDot, layerOverlay, landGeo, landStyle, markers = new Map();

// ---------- Textos estáticos ----------
document.querySelectorAll('[data-t]').forEach((el) => { el.textContent = T[el.dataset.t]; });
document.querySelectorAll('[data-t-aria]').forEach((el) => el.setAttribute('aria-label', T[el.dataset.tAria]));
$('target-select').setAttribute('aria-label', T.marsSite); // en celular la etiqueta visible se oculta

// ---------- Carga ----------
async function getJSON(url, optional) {
  const r = await fetch(url);
  if (!r.ok) { if (optional) return null; throw new Error(`${url}: ${r.status}`); }
  return r.json();
}

async function init() {
  initMap();
  try {
    const [data, textos, land] = await Promise.all([
      getJSON('data/sites.json'),
      getJSON('data/textos.json', true).catch(() => null),
      getJSON('data/land-50m.json', true).catch(() => null)
    ]);
    if (!data?.targets?.length) throw new Error('sites.json sin sitios objetivo');
    state.data = data;
    state.textos = textos || {};
    if (land) drawLand(land);
    $('sample-note').textContent = data.sample ? T.sample : data.provisional ? T.provisional : '';
    $('sample-note').hidden = !(data.sample || data.provisional);
    buildChips();
    const fromHash = new URLSearchParams(location.hash.slice(1));
    setTarget(data.targets.find((t) => t.id === fromHash.get('sitio'))?.id || data.targets[0].id, true);
    if (fromHash.get('punto')) select(fromHash.get('punto'));
  } catch (err) {
    console.error(err);
    $('status').textContent = T.loadError;
    $('status').hidden = false;
    $('hint').hidden = $('dock').hidden = true;
  }
}

// ---------- Mapa ----------
function initMap() {
  map = L.map('map', {
    zoomSnap: 0.25, zoomDelta: 0.5, maxZoom: 8,
    wheelPxPerZoomLevel: 150, // media unidad de zoom por muesca de rueda; el valor por defecto salta más de una
    worldCopyJump: false, maxBoundsViscosity: 1
  });
  fitLimits();
  map.on('resize', fitLimits);
  map.attributionControl.setPrefix('<a href="https://leafletjs.com">Leaflet</a>');
  map.attributionControl.addAttribution('Continentes: <a href="https://www.naturalearthdata.com">Natural Earth</a>');
  map.createPane('land').style.zIndex = 250;
  map.createPane('similarity').style.zIndex = 300;
  map.fitBounds(WORLD);
  map.on('click', () => select(null));
}

// Límites del mapa: no se aleja más que "el mundo ocupa todo el ancho" ni se arrastra fuera del mundo.
// Con el panel abierto se deja correr hacia el este el ancho del panel, para que no tape el punto elegido.
function fitLimits() {
  const z = Math.ceil(Math.log2(map.getSize().x / 256) * 4) / 4; // múltiplo de zoomSnap
  const extra = state.selected && !mobile.matches ? ($('panel').offsetWidth + 48) * 360 / (256 * 2 ** z) : 0;
  map.setMinZoom(z);
  map.setMaxBounds([[-85, -180], [85, 180 + extra]]);
}

// Los contornos que cruzan los 180° (Rusia, Fiji) saltan de +180 a -180, y Leaflet une esos
// puntos con una recta que atraviesa todo el mapa. Se vuelven continuos sumando ±360.
// Un salto impar es la Antártida, que da toda la vuelta: se deja como está.
function unwrapRing(ring) {
  let jumps = 0;
  for (let k = 1; k < ring.length; k++) if (Math.abs(ring[k][0] - ring[k - 1][0]) > 180) jumps++;
  if (!jumps || jumps % 2) return;
  let off = 0;
  for (let k = 1; k < ring.length; k++) {
    let x = ring[k][0] + off;
    const d = x - ring[k - 1][0];
    if (d > 180) { off -= 360; x -= 360; } else if (d < -180) { off += 360; x += 360; }
    ring[k][0] = x;
  }
  // el anillo puede empezar del lado "equivocado" (Afro-Eurasia arranca en Chukotka):
  // se lo corre entero para que su centro quede entre -180 y 180
  let min = Infinity, max = -Infinity;
  ring.forEach(([x]) => { min = Math.min(min, x); max = Math.max(max, x); });
  const shift = -360 * Math.round((min + max) / 2 / 360);
  if (shift) ring.forEach((c) => { c[0] += shift; });
}

function drawLand(topo) {
  const geo = topojson.feature(topo, topo.objects.land);
  geo.features.forEach((f) => {
    const polys = f.geometry.type === 'Polygon' ? [f.geometry.coordinates] : f.geometry.coordinates;
    polys.forEach((p) => p.forEach(unwrapRing));
  });
  landStyle = { fillColor: css.getPropertyValue('--land').trim(), fillOpacity: 1, color: css.getPropertyValue('--line').trim(), weight: 0.6 };
  landGeo = geo;
  L.geoJSON(geo, { pane: 'land', interactive: false, style: landStyle, renderer: L.canvas({ pane: 'land' }) }).addTo(map);
}

// ---------- Datos derivados ----------
const target = () => state.data.targets.find((t) => t.id === state.target);
const meta = (t, s) => {
  const m = state.textos[`${t.id}:${s.id}`] || state.textos[s.id];
  return m || s.name ? { name: s.name, ...m } : null;
};
const ranked = (t) => t.sites.slice().sort((a, b) => b.score - a.score);

// ---------- Selector de sitio de Marte ----------
function buildChips() {
  const sel = $('target-select');
  state.data.targets.forEach((t) => sel.add(new Option(t.name, t.id)));
  sel.addEventListener('change', () => setTarget(sel.value));
}

let fadeTimer;
function setTarget(id, first) {
  if (id === state.target) return;
  const apply = () => {
    state.target = id;
    state.selected = null;
    if (!first) history.replaceState(null, '', `#sitio=${id}`);
    renderTarget();
    renderMarkers();
    renderLayer();
    renderPanel();
    fitLimits();
    $('map').classList.remove('fading');
    if (mobile.matches) {
      const pts = target().sites.map((s) => [s.lat, s.lon]);
      // que no queden puntos debajo del aviso de arriba ni de la tarjeta de abajo
      if (pts.length) map.fitBounds(pts, { paddingTopLeft: [16, 72], paddingBottomRight: [16, $('dock').offsetHeight + 16], maxZoom: 3, animate: false });
    }
  };
  if (first) return apply();
  $('map').classList.add('fading');
  clearTimeout(fadeTimer);
  fadeTimer = setTimeout(apply, 140);
}

function renderTarget() {
  const t = target();
  const m = state.textos[t.id] || {};
  $('target-select').value = t.id;
  $('target-name').textContent = t.name;
  $('target-coords').textContent = coords(t.lat, t.lon);
  $('target-blurb').textContent = m.blurb || '';
  $('target-blurb').hidden = !m.blurb;
  $('target-mission').textContent = m.mission || '';
  $('target-mission').hidden = !m.mission;
  const y = (36 - 30 * Math.sin(t.lat * Math.PI / 180)).toFixed(1);
  $('globe-ring').setAttribute('cy', y);
  $('globe-dot').setAttribute('cy', y);
  $('globe').setAttribute('aria-label', tpl(T.globeAria, { target: t.name }));
  $('legend-title').textContent = tpl(T.legendTitle, { target: t.name });
  $('legend-steps').innerHTML = STEPS.map((s) =>
    `<div class="legend-step"><span class="legend-swatch" style="background:${s.color}"></span><span>${s.label}</span></div>`).join('');
  $('hint-sub').textContent = tpl(T.hintSub, { n: t.sites.length, target: t.name });
  renderSection(m.section);
  const toggle = $('layer-toggle');
  toggle.disabled = !t.layer;
  toggle.title = t.layer ? '' : T.layerMissing;
}

// Sección larga del sitio de Marte elegido (textos.json → <sitio>.section)
function renderSection(sec) {
  $('sitio').hidden = $('nav-site').hidden = !sec;
  if (!sec) return;
  $('site-title').textContent = sec.title || '';
  $('site-text').innerHTML = (sec.paragraphs || []).map((p) => `<p class="lead">${esc(p)}</p>`).join('');
  const im = sec.image, img = $('site-img');
  img.closest('figure').hidden = !im;
  if (im) {
    img.src = im.src;
    img.alt = im.alt || '';
    if (im.width && im.height) { img.width = im.width; img.height = im.height; }
    $('site-caption').textContent = im.caption || '';
  }
  $('site-facts').innerHTML = (sec.facts || []).map((f) =>
    `<div class="tile"><span class="tile-label">${esc(f.label)}</span><span class="big-num">${esc(f.value)}</span><span class="tile-text">${esc(f.text)}</span></div>`).join('');
}

// ---------- Puntos ----------
function renderMarkers() {
  markers.forEach((mk) => mk.remove());
  markers.clear();
  const t = target();
  ranked(t).forEach((s) => {
    const m = meta(t, s);
    const name = m?.name || coords(s.lat, s.lon);
    const color = s.known ? KNOWN_COLOR : step(s.score).color;
    const mk = L.marker([s.lat, s.lon], {
      icon: L.divIcon({
        className: `pt${s.known ? ' known' : ''}`,
        html: `<span class="pt-hit" style="--c:${color}"><span class="pt-dot"></span></span>`,
        iconSize: [44, 44]
      }),
      keyboard: true,
      zIndexOffset: s.known ? 0 : Math.round(s.score * 500)
    });
    mk.bindTooltip(
      `<span class="tip-name${m?.name ? '' : ' coords'}">${esc(name)}</span><span class="tip-pct"><i class="sw" style="background:${color}"></i>${pct(s.score)} %</span>`,
      { direction: 'top', offset: [0, -16], className: 'tip' }
    );
    mk.on('click', (e) => { L.DomEvent.stopPropagation(e); select(s.id === state.selected ? null : s.id); });
    mk.addTo(map);
    const el = mk.getElement();
    el.setAttribute('aria-label', tpl(T.pointAria, { name, pct: pct(s.score) }) + (s.known ? `, ${T.knownAria}` : ''));
    el.setAttribute('aria-pressed', 'false');
    el.removeAttribute('title');
    markers.set(s.id, mk);
  });
}

// ---------- Capa de similitud ----------
function renderLayer() {
  const t = target();
  const on = state.layerOn && !!t.layer;
  $('layer-toggle').setAttribute('aria-pressed', String(on));
  if (layerOverlay) { layerOverlay.remove(); layerOverlay = null; }
  if (on) layerOverlay = L.imageOverlay(t.layer, LAYER_BOUNDS, { pane: 'similarity', opacity: 0.85 }).addTo(map);
}
$('layer-toggle').addEventListener('click', () => { state.layerOn = !state.layerOn; renderLayer(); });

// ---------- Selección y panel ----------
function select(id) {
  const t = target();
  if (!t) return;
  if (id && !t.sites.some((s) => s.id === id)) id = null;
  const prev = state.selected;
  state.selected = id;
  if (prev) markers.get(prev)?.getElement()?.classList.remove('selected');
  if (prev) markers.get(prev)?.getElement()?.setAttribute('aria-pressed', 'false');
  if (id) {
    const el = markers.get(id).getElement();
    el.classList.add('selected');
    el.setAttribute('aria-pressed', 'true');
    markers.get(id).closeTooltip();
  }
  history.replaceState(null, '', `#sitio=${t.id}${id ? `&punto=${id}` : ''}`);
  renderPanel();
  fitLimits();
  if (id) {
    const s = t.sites.find((x) => x.id === id);
    // que el punto no quede tapado por el panel
    if (mobile.matches) {
      // con el mapa tan alejado no hay margen para desplazarlo: se acerca y se centra el punto
      // en la franja visible arriba del panel
      const z = Math.max(map.getZoom(), 3);
      const c = map.project([s.lat, s.lon], z).add([0, $('panel').offsetHeight / 2]);
      map.setView(map.unproject(c, z), z);
    } else {
      map.panInside([s.lat, s.lon], { paddingTopLeft: [24, 24], paddingBottomRight: [$('panel').offsetWidth + 48, 24] });
    }
    $('p-title').focus({ preventScroll: true });
  }
}

function renderPanel() {
  const t = target();
  const open = !!state.selected;
  const screen = $('top');
  const panel = $('panel');
  screen.classList.toggle('open', open);
  panel.setAttribute('aria-hidden', String(!open));
  panel.inert = !open;
  if (!open) return;

  const list = ranked(t);
  const idx = list.findIndex((s) => s.id === state.selected);
  const s = list[idx];
  const m = meta(t, s);
  const color = step(s.score).color;
  const vars = state.data.variables.filter((v) => s.variables?.[v.id]);

  $('p-badge').hidden = !s.known;
  // los conocidos no compiten por puesto: se muestra a qué porcentaje del planeta superan
  const news = list.filter((x) => !x.known);
  const hasPct = typeof s.percentile === 'number';
  const p = hasPct ? fmt(s.percentile, 1) : '';
  $('p-rank').textContent = s.known
    ? (hasPct ? tpl(T.rankKnown, { p }) : '')
    : tpl(T.rank, { n: s.rank ?? news.indexOf(s) + 1, total: news.length });
  $('p-title').textContent = m?.name || coords(s.lat, s.lon);
  $('p-title').classList.toggle('coords', !m?.name);
  $('p-subtitle').textContent = m?.name ? [m.country, coords(s.lat, s.lon)].filter(Boolean).join(' · ') : T.unnamed;
  $('p-score').innerHTML = `${pct(s.score)}<small>%</small>`;
  $('p-score-sw').style.background = color;
  $('p-score-label').textContent = tpl(T.scoreLabel, { target: t.name });

  // imagen satelital del sitio (earth/imagenes.py la deja en data/img/<id>.jpg);
  // si no existe, un mapa chico de ubicación
  const img = $('p-img');
  const fallback = () => {
    if (state.selected !== s.id) return;
    img.hidden = true;
    $('p-locator').hidden = false;
    $('p-figure-tag').textContent = T.locator;
    showLocator(s, color);
  };
  img.hidden = false;
  $('p-locator').hidden = true;
  $('p-figure-tag').textContent = T.imageLabel;
  img.alt = `${T.imageAlt}: ${m?.name || coords(s.lat, s.lon)}`;
  img.onerror = fallback;
  img.src = s.image || `data/img/${s.id}.jpg`;

  const all = vars.map((v) => ({ v, r: s.variables[v.id] }));
  const rows = all.filter(({ v }) => !v.informative);
  $('p-vars').parentElement.classList.toggle('many', all.length > 4);
  $('p-vars-count').textContent = tpl(T.varsCount, { n: rows.length });
  $('p-vars').innerHTML = all.map(({ v, r }) => `
    <div class="var${v.informative ? ' informative' : ''}">
      ${v.informative ? `
      <div class="var-top"><span class="var-label">${esc(v.label)}</span></div>
      <span class="var-note">${T.informative}</span>` : `
      <div class="var-top"><span class="var-label">${esc(v.label)}</span><span class="var-pct">${pct(r.score)} %</span></div>
      <div class="bar" role="img" aria-label="${esc(v.label)}: ${pct(r.score)} %"><div class="bar-fill" style="width:${pct(r.score)}%;background:${step(r.score).color}"></div></div>`}
      <div class="var-values">
        <span><span class="earth">${esc(value(v, r.earth))}</span> ${T.onEarth}</span>
        <span><span class="marsv">${esc(value(v, t.values?.[v.id]))}</span> ${T.onMars}</span>
      </div>
    </div>`).join('');

  $('p-validation').hidden = !s.known;
  $('p-validation-text').textContent = hasPct ? tpl(T.validation, { p }) : T.validationNoPct;

  const texts = [['why', 'M8 12h8M12 8v8'], ['breaks', 'M8 12h8'], ['use', 'M12 3v2M12 19v2M3 12h2M19 12h2']]
    .filter(([k]) => m?.[k]);
  $('p-texts').hidden = !texts.length;
  $('p-texts').innerHTML = texts.map(([k, path]) => `
    <div class="text-card">
      <h3><span class="text-icon"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#E8EEF7" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9"/>${k === 'use' ? '<circle cx="12" cy="12" r="4"/>' : ''}<path d="${path}"/></svg></span>${T[k]}</h3>
      <p>${esc(m[k])}</p>
    </div>`).join('');

  const sorted = rows.slice().sort((a, b) => b.r.score - a.r.score);
  $('p-numbers').hidden = !!texts.length || !sorted.length;
  if (sorted.length) {
    const best = sorted[0], worst = sorted[sorted.length - 1];
    $('p-best-label').textContent = best.v.label;
    $('p-best-pct').innerHTML = `<i class="sw" style="background:${step(best.r.score).color}"></i>${pct(best.r.score)} %`;
    $('p-worst-label').textContent = worst.v.label;
    $('p-worst-pct').innerHTML = `<i class="sw" style="background:${step(worst.r.score).color}"></i>${pct(worst.r.score)} %`;
  }
  panel.querySelector('.panel-body').scrollTop = 0;
}

function showLocator(s, color) {
  if (!locator) {
    locator = L.map('p-locator', {
      center: [s.lat, s.lon], zoom: 2,
      zoomControl: false, attributionControl: false, dragging: false, scrollWheelZoom: false,
      doubleClickZoom: false, boxZoom: false, keyboard: false, touchZoom: false
    });
    if (landGeo) L.geoJSON(landGeo, { interactive: false, style: landStyle }).addTo(locator);
    locatorDot = L.circleMarker([0, 0], { radius: 5, weight: 2, color: '#FFFFFF', fillOpacity: 1 }).addTo(locator);
  }
  locatorDot.setLatLng([s.lat, s.lon]).setStyle({ fillColor: color });
  // el panel recién se hizo visible: Leaflet necesita medir el contenedor
  // reset: true obliga a reproyectar el contorno; sin eso a veces queda dibujado con el tamaño viejo
  requestAnimationFrame(() => { locator.invalidateSize(); locator.setView([s.lat, s.lon], 2, { reset: true }); });
}

$('p-close').addEventListener('click', () => {
  const prev = state.selected;
  select(null);
  markers.get(prev)?.getElement()?.focus();
});
document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && state.selected) $('p-close').click(); });

init();
