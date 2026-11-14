/* Página estática: lee data/sites.json y, si existe, data/textos.json.
   Los formatos están en docs/contratos.md. No hay paso de compilación. */

'use strict';

// Escala de color de la similitud: un solo tono, de oscuro a claro.
// Tiene que coincidir con RAMP, SCALE_MIN y SCALE_MAX de earth/layer.py,
// porque la capa PNG ya viene pintada con esos colores.
const RAMP = ['#3b0e00', '#5d1c00', '#822a00', '#a83900', '#cb4e19', '#e96a3a', '#ff8c63', '#ffb9a0', '#ffe0d6'];
const SCALE_MIN = 0.5;
const SCALE_MAX = 1.0;

const KNOWN_COLOR = '#3987e5';
const SURFACE = '#0d0d0d';
const LAYER_BOUNDS = [[-85, -180], [85, 180]]; // la capa viene en Web Mercator con estos límites
const LAYER_OPACITY = 0.85;

// ---------------------------------------------------------------- utilidades

/** Crea un elemento. El texto siempre entra por textContent: los nombres vienen de archivos JSON. */
function el(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (value === null || value === undefined || value === false) continue;
    if (key === 'class') node.className = value;
    else if (key === 'text') node.textContent = value;
    else if (key.startsWith('on')) node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value === true ? '' : value);
  }
  node.append(...children.filter((c) => c !== null && c !== undefined && c !== false));
  return node;
}

const nf = (value, options) => new Intl.NumberFormat('es-AR', options).format(value);

/** Puntaje de 0 a 1 como porcentaje. Cerca del 100 % muestra un decimal para que se vean las diferencias. */
function pct(score) {
  const p = score * 100;
  return nf(p, { maximumFractionDigits: p >= 99 && p < 99.95 ? 1 : 0 }) + ' %';
}

function fmtValue(value, unit) {
  if (typeof value !== 'number' || !Number.isFinite(value)) return 'sin dato';
  const text = nf(value, { maximumSignificantDigits: 3 });
  if (!unit) return text;
  return unit === '°' ? text + '°' : text + ' ' + unit;
}

function fmtCoords(lat, lon) {
  const d = (v) => nf(Math.abs(v), { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return `${d(lat)}° ${lat >= 0 ? 'N' : 'S'}, ${d(lon)}° ${lon >= 0 ? 'E' : 'O'}`;
}

function hexToRgb(hex) {
  return [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));
}

/** Color de la rampa para un puntaje. */
function rampColor(score) {
  const t = Math.min(1, Math.max(0, (score - SCALE_MIN) / (SCALE_MAX - SCALE_MIN)));
  const x = t * (RAMP.length - 1);
  const i = Math.min(RAMP.length - 2, Math.floor(x));
  const a = hexToRgb(RAMP[i]);
  const b = hexToRgb(RAMP[i + 1]);
  const mix = a.map((v, k) => Math.round(v + (b[k] - v) * (x - i)));
  return `rgb(${mix[0]}, ${mix[1]}, ${mix[2]})`;
}

/** Tinta para escribir dentro de un relleno: casi negro sobre claros, blanco sobre oscuros. */
function inkOn(color) {
  const [r, g, b] = color.startsWith('#') ? hexToRgb(color) : color.match(/\d+/g).map(Number);
  const lin = (v) => { const c = v / 255; return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; };
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b) > 0.3 ? '#0b0b0b' : '#ffffff';
}

/** SVG del marcador. Solo recibe números y colores calculados acá, nunca texto de los datos. */
function markSvg(site, size = 30) {
  const head = `<svg width="${size}" height="${size}" viewBox="-15 -15 30 30" aria-hidden="true">`;
  if (site.known) {
    return head +
      '<rect class="halo" x="-10" y="-10" width="20" height="20" transform="rotate(45)"/>' +
      `<rect x="-8" y="-8" width="16" height="16" transform="rotate(45)" fill="${SURFACE}"/>` +
      `<rect x="-6" y="-6" width="12" height="12" transform="rotate(45)" fill="${KNOWN_COLOR}"/></svg>`;
  }
  const fill = rampColor(site.score);
  return head +
    '<circle class="halo" r="14"/>' +
    `<circle r="12" fill="${SURFACE}"/><circle r="10" fill="${fill}"/>` +
    `<text fill="${inkOn(fill)}">${site.rank}</text></svg>`;
}

// ---------------------------------------------------------------- estado

const state = {
  data: null,
  textos: {},
  target: null,
  sites: [],
  selected: null,
  markers: new Map(),
  overlay: null,
  layerOk: false,
};

const $ = (id) => document.getElementById(id);
const panel = $('panel');
const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

// ---------------------------------------------------------------- mapa

const map = L.map('map', {
  worldCopyJump: true,
  minZoom: 2,
  maxZoom: 9,
  zoomSnap: 0.25,
  maxBounds: [[-89, -360], [89, 360]],
  maxBoundsViscosity: 0.8,
});
map.attributionControl.setPrefix(false);

// la capa de similitud va entre el fondo y los nombres, para que los países se sigan leyendo
map.createPane('similarity').style.zIndex = 300;
map.createPane('labels').style.zIndex = 450;
map.getPane('labels').style.pointerEvents = 'none';

// Todo el mapa base sale de NASA GIBS, que es abierto y no pide clave.
const GIBS = 'https://gibs.earthdata.nasa.gov/wmts/epsg3857/best';
const GIBS_CREDIT = 'Mapa: <a href="https://earthdata.nasa.gov/gibs">NASA GIBS</a> / ESDIS';
const OSM_CREDIT = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>';
const gibs = (layer, level, ext, options) =>
  L.tileLayer(`${GIBS}/${layer}/default/GoogleMapsCompatible_Level${level}/{z}/{y}/{x}.${ext}`, { maxNativeZoom: level, maxZoom: 9, ...options });

const bases = {
  // tierra y agua en grises; style.css lo invierte y lo oscurece (.base-dark)
  dark: gibs('OSM_Land_Water_Map', 9, 'png', { className: 'base-dark', attribution: GIBS_CREDIT }),
  sat: gibs('BlueMarble_NextGeneration', 8, 'jpeg', { attribution: `${GIBS_CREDIT}, Blue Marble` }),
};
// fronteras y nombres van arriba de la capa de similitud
const labels = L.layerGroup([
  gibs('Reference_Features', 9, 'png', { pane: 'labels', attribution: OSM_CREDIT }),
  gibs('Reference_Labels', 9, 'png', { pane: 'labels' }),
]);
const markerLayer = L.layerGroup().addTo(map);

bases.dark.addTo(map);
labels.addTo(map);
map.fitBounds([[-56, -168], [76, 178]]);

document.querySelectorAll('.segmented button').forEach((button) => {
  button.addEventListener('click', () => {
    const chosen = button.dataset.base;
    Object.entries(bases).forEach(([name, layer]) => (name === chosen ? layer.addTo(map) : layer.remove()));
    document.querySelectorAll('.segmented button').forEach((b) => b.setAttribute('aria-pressed', String(b === button)));
  });
});

$('layer-toggle').addEventListener('change', syncOverlay);

function syncOverlay() {
  if (!state.overlay) return;
  if ($('layer-toggle').checked && state.layerOk) state.overlay.addTo(map);
  else state.overlay.remove();
}

/** Carga la capa del sitio objetivo. Si el PNG no existe, la página sigue andando sin capa. */
function loadOverlay(target) {
  if (state.overlay) state.overlay.remove();
  state.overlay = null;
  state.layerOk = false;
  const toggle = $('layer-toggle');
  const legend = $('legend');
  toggle.disabled = true;
  legend.classList.add('no-layer');
  if (!target.layer) return;

  const overlay = L.imageOverlay(target.layer, LAYER_BOUNDS, { opacity: LAYER_OPACITY, pane: 'similarity', interactive: false });
  overlay.once('load', () => {
    if (state.overlay !== overlay) return;
    state.layerOk = true;
    toggle.disabled = false;
    legend.classList.remove('no-layer');
  });
  overlay.once('error', () => {
    if (state.overlay === overlay) overlay.remove();
  });
  state.overlay = overlay;
  // hay que agregarla para que empiece a cargar; si falla, el evento de error la saca
  if (toggle.checked) overlay.addTo(map);
  else { const probe = new Image(); probe.onload = () => overlay.fire('load'); probe.src = target.layer; }
}

function drawLegend(target) {
  $('legend-title').textContent = `Similitud con ${target.name}`;
  $('legend-ramp').style.background = `linear-gradient(to right, ${RAMP.join(', ')})`;
  const ticks = $('legend-ticks');
  ticks.replaceChildren();
  const steps = 5;
  for (let i = 0; i <= steps; i++) {
    const value = SCALE_MIN + (SCALE_MAX - SCALE_MIN) * (i / steps);
    const text = (i === 0 && SCALE_MIN > 0 ? '≤ ' : '') + nf(value * 100, { maximumFractionDigits: 0 }) + (i === steps ? ' %' : '');
    ticks.append(el('span', { text, style: `left: ${(100 * i) / steps}%` }));
  }
  $('legend').hidden = false;
}

// ---------------------------------------------------------------- sitios

function siteTitle(site) {
  const texto = state.textos[site.id];
  if (texto && texto.name) return texto.country ? `${texto.name}, ${texto.country}` : texto.name;
  return site.name || fmtCoords(site.lat, site.lon);
}

function hasName(site) {
  return Boolean((state.textos[site.id] && state.textos[site.id].name) || site.name);
}

/** Dónde queda el puntaje entre todas las celdas sin vegetación del planeta. */
function percentileText(percentile) {
  const top = 100 - percentile;
  const of = 'de la tierra sin vegetación analizada';
  if (top < 0.1) return `Está entre el 0,1 % más parecido ${of}.`;
  if (top <= 25) return `Está en el ${nf(top, { maximumSignificantDigits: 2 })} % más parecido ${of}.`;
  return `Supera al ${nf(percentile, { maximumFractionDigits: 0 })} % ${of}.`;
}

function kindText(site) {
  const total = state.sites.filter((s) => !s.known).length;
  return site.known ? 'Análogo ya conocido' : `Sitio nuevo · puesto ${site.rank} de ${total}`;
}

function setTarget(id) {
  const target = state.data.targets.find((t) => t.id === id) || state.data.targets[0];
  state.target = target;
  state.selected = null;

  const all = Array.isArray(target.sites) ? target.sites : [];
  const fresh = all.filter((s) => !s.known).sort((a, b) => b.score - a.score);
  fresh.forEach((site, i) => { site.rank = i + 1; });
  const known = all.filter((s) => s.known).sort((a, b) => b.score - a.score);
  state.sites = [...fresh, ...known];

  markerLayer.clearLayers();
  state.markers.clear();
  // los conocidos primero, así los nuevos quedan arriba; el mejor puesto, arriba de todo
  [...known, ...fresh.slice().reverse()].forEach((site) => {
    const label = `${siteTitle(site)}. ${kindText(site)}. Similitud ${pct(site.score)}.`;
    const marker = L.marker([site.lat, site.lon], {
      icon: L.divIcon({ className: 'site-marker', html: markSvg(site), iconSize: [30, 30], iconAnchor: [15, 15] }),
      alt: label,
      keyboard: true,
      riseOnHover: true,
    });
    marker.bindTooltip(
      el('div', {}, el('strong', { text: pct(site.score) }), el('span', { text: siteTitle(site) }), el('span', { text: kindText(site) })),
      { direction: 'top', offset: [0, -14], className: 'site-tip', opacity: 1 },
    );
    marker.on('click', () => select(site.id, { fly: false }));
    marker.addTo(markerLayer);
    state.markers.set(site.id, marker);
  });

  $('target').value = target.id;
  drawLegend(target);
  loadOverlay(target);
  renderList();
}

function select(siteId, { fly = true } = {}) {
  const site = state.sites.find((s) => s.id === siteId) || null;
  state.selected = site;
  state.markers.forEach((marker, id) => {
    const node = marker.getElement();
    if (node) node.classList.toggle('is-selected', Boolean(site) && id === site.id);
    marker.setZIndexOffset(site && id === site.id ? 1000 : 0);
  });
  if (!site) {
    history.replaceState(null, '', location.pathname + location.search);
    renderList();
    return;
  }
  history.replaceState(null, '', `#${state.target.id}/${site.id}`);
  renderDetail(site);
  if (fly) {
    const zoom = Math.max(map.getZoom(), 4.5);
    if (reducedMotion) map.setView([site.lat, site.lon], zoom);
    else map.flyTo([site.lat, site.lon], zoom, { duration: 0.8 });
  }
  panel.scrollTop = 0;
}

// ---------------------------------------------------------------- panel

function variableList() {
  return Array.isArray(state.data.variables) ? state.data.variables : [];
}

function siteRow(site) {
  const mark = el('span', { class: 'mark' });
  mark.innerHTML = markSvg(site, 24);
  const name = el('span', { class: 'name', text: siteTitle(site) });
  if (hasName(site)) name.append(el('small', { text: fmtCoords(site.lat, site.lon) }));
  return el('li', {},
    el('button', { class: 'site-row', type: 'button', onclick: () => select(site.id) },
      mark, name, el('span', { class: 'score', text: pct(site.score) })));
}

function renderList() {
  const target = state.target;
  const fresh = state.sites.filter((s) => !s.known);
  const known = state.sites.filter((s) => s.known);

  const tiles = el('div', { class: 'tiles' });
  variableList().forEach((v) => {
    const value = target.values ? target.values[v.id] : undefined;
    tiles.append(el('div', { class: 'tile' },
      el('div', { class: 'label', text: v.label || v.id }),
      el('div', { class: 'value', text: fmtValue(value, v.unit) })));
  });

  const nodes = [
    el('div', { class: 'target-card' },
      el('div', { class: 'eyebrow', text: 'Sitio objetivo en Marte' }),
      el('h2', { text: target.name }),
      el('div', { class: 'coords', text: fmtCoords(target.lat, target.lon) }),
      tiles),
  ];

  if (fresh.length) {
    const list = el('ol', { class: 'site-list' });
    fresh.forEach((site) => list.append(siteRow(site)));
    nodes.push(
      el('div', { class: 'list-head' }, el('h3', { text: 'Sitios nuevos' }), el('span', { text: 'similitud' })),
      el('p', { class: 'note', text: 'Las celdas de la Tierra que más se le parecen, fuera de los análogos ya estudiados.' }),
      list);
  }
  if (known.length) {
    const list = el('ul', { class: 'site-list' });
    known.forEach((site) => list.append(siteRow(site)));
    nodes.push(
      el('div', { class: 'list-head' }, el('h3', { text: 'Análogos ya conocidos' }), el('span', { text: 'similitud' })),
      el('p', { class: 'note', text: 'No entran en la búsqueda. Los medimos después para ver si el método los encuentra.' }),
      list);
  }
  if (!fresh.length && !known.length) nodes.push(el('p', { class: 'status', text: 'Este sitio todavía no tiene resultados.' }));
  panel.replaceChildren(...nodes);
}

function renderDetail(site) {
  const target = state.target;
  const texto = state.textos[site.id] || {};
  const nodes = [
    el('button', { class: 'back', type: 'button', text: '← Todos los sitios', onclick: () => select(null) }),
    el('div', { class: `kind${site.known ? ' known' : ''}` }, el('span', { class: 'dot' }), el('span', { text: kindText(site) })),
    el('h2', { text: siteTitle(site) }),
  ];
  if (hasName(site)) nodes.push(el('div', { class: 'coords', text: fmtCoords(site.lat, site.lon) }));

  const hero = el('div', { class: 'hero' },
    el('div', { class: 'label', text: `Similitud con ${target.name}` }),
    el('div', { class: 'value', text: pct(site.score) }));
  if (typeof site.percentile === 'number') hero.append(el('div', { class: 'rank', text: percentileText(site.percentile) }));
  nodes.push(hero);

  if (site.image) {
    const photo = el('img', { class: 'photo', src: site.image, alt: `Imagen satelital de ${siteTitle(site)}`, loading: 'lazy' });
    photo.addEventListener('error', () => photo.remove());
    nodes.push(photo);
  }

  // una barra por cada variable que venga en el sitio, con el nombre y la unidad de la lista general
  const meta = new Map(variableList().map((v) => [v.id, v]));
  const ids = [...variableList().map((v) => v.id).filter((id) => site.variables && id in site.variables),
    ...Object.keys(site.variables || {}).filter((id) => !meta.has(id))];
  const bars = el('div', { class: 'bars' });
  ids.forEach((id) => {
    const v = meta.get(id) || { id, label: id, unit: '' };
    const item = site.variables[id];
    const mars = target.values ? target.values[id] : undefined;
    const width = Math.max(0, Math.min(100, item.score * 100));
    bars.append(el('div', { class: 'bar' },
      el('div', { class: 'bar-head' },
        el('span', { class: 'label', text: v.label || id }),
        el('span', { class: 'pct', text: pct(item.score) })),
      el('div', { class: 'bar-track', role: 'img', 'aria-label': `${v.label || id}: ${pct(item.score)} de similitud` },
        el('div', { class: 'bar-fill', style: `width: ${width}%` })),
      el('div', { class: 'bar-values' },
        el('span', {}, 'Tierra ', el('b', { text: fmtValue(item.earth, v.unit) })),
        el('span', {}, 'Marte ', el('b', { text: fmtValue(mars, v.unit) })))));
  });
  if (ids.length) nodes.push(bars);

  const blocks = [['why', 'Por qué se parece'], ['breaks', 'Dónde se rompe la analogía'], ['use', 'Para qué serviría']]
    .filter(([key]) => texto[key]);
  if (blocks.length) {
    const texts = el('div', { class: 'texts' });
    blocks.forEach(([key, title]) => texts.append(el('div', {}, el('h3', { text: title }), el('p', { text: texto[key] }))));
    nodes.push(texts);
  }

  if (site.known && typeof site.source === 'string' && /^https?:\/\//.test(site.source)) {
    nodes.push(el('p', { class: 'source' },
      el('a', { href: site.source, target: '_blank', rel: 'noopener', text: 'Fuente que lo respalda como análogo' })));
  }

  nodes.push(el('p', { class: 'caveat' },
    'La Tierra no reproduce la gravedad, la presión atmosférica, la composición del aire ni la radiación de Marte. ',
    el('a', { href: '#limites', text: 'Ver límites' }), '.'));
  panel.replaceChildren(...nodes);
}

// ---------------------------------------------------------------- arranque

async function fetchJson(url) {
  const response = await fetch(url, { cache: 'no-cache' });
  if (!response.ok) throw new Error(`${url}: ${response.status}`);
  return response.json();
}

async function start() {
  try {
    state.data = await fetchJson('data/sites.json');
    if (!Array.isArray(state.data.targets) || !state.data.targets.length) throw new Error('sites.json no trae sitios objetivo');
  } catch (error) {
    panel.replaceChildren(el('p', { class: 'status error', text: 'No se pudo leer data/sites.json. Generalo con earth/build_sites.py y abrí la página desde un servidor local.' }));
    console.error(error);
    return;
  }
  // textos.json es opcional: si falta o está mal, la página muestra coordenadas
  state.textos = await fetchJson('data/textos.json').then((t) => (t && typeof t === 'object' ? t : {})).catch(() => ({}));

  const selector = $('target');
  state.data.targets.forEach((t) => selector.append(el('option', { value: t.id, text: t.name })));
  selector.addEventListener('change', () => setTarget(selector.value));

  setTarget(state.data.targets[0].id);
  applyHash();
  window.addEventListener('hashchange', applyHash);
}

/** Abre el sitio de un enlace del tipo #jezero/-24.1_-66.9. Los enlaces a secciones no hacen nada acá. */
function applyHash() {
  const [targetId, siteId] = decodeURIComponent(location.hash.slice(1)).split('/');
  if (!siteId || !state.data.targets.some((t) => t.id === targetId)) return;
  if (state.target.id !== targetId) setTarget(targetId);
  if (state.sites.some((s) => s.id === siteId)) select(siteId);
}

start();
