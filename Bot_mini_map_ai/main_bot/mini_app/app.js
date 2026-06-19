/* global L */
'use strict';

const tg = window.Telegram.WebApp;
tg.expand();
tg.ready();

// ─── Tab switcher ──────────────────────────────────────────────────────
const tabs    = document.querySelectorAll('.tab');
const panels  = document.querySelectorAll('.tab-content');

tabs.forEach(tab => {
  tab.addEventListener('click', () => {
    tabs.forEach(t  => { t.classList.remove('active'); t.setAttribute('aria-selected', 'false'); });
    panels.forEach(p => p.classList.remove('active'));

    tab.classList.add('active');
    tab.setAttribute('aria-selected', 'true');
    document.getElementById(tab.dataset.tab).classList.add('active');

    if (tab.dataset.tab === 'map-tab' && map) {
      // Leaflet needs layout to settle before recalculating size
      requestAnimationFrame(() => setTimeout(() => map.invalidateSize(), 80));
    }
  });
});

// ─── Predict form ──────────────────────────────────────────────────────
const predictForm = document.getElementById('predictForm');
const calcBtn     = document.getElementById('calcBtn');
const resultBox   = document.getElementById('result');
const resultPrice = document.getElementById('resultPrice');

predictForm.addEventListener('submit', async e => {
  e.preventDefault();

  const raw = Object.fromEntries(new FormData(e.target).entries());
  const payload = {
    area:         parseFloat(raw.area),
    floor:        parseInt(raw.floor),
    time_to_metro: parseInt(raw.time_to_metro),
    renovation:   parseInt(raw.renovation),
    house_type:   parseInt(raw.house_type),
  };

  // Loading state
  calcBtn.classList.add('loading');
  calcBtn.disabled = true;

  try {
    const resp = await fetch('/api/predict', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

    const { price } = await resp.json();
    resultPrice.textContent = `₽\u00a0${price.toLocaleString('ru-RU', { maximumFractionDigits: 0 })}`;
    resultBox.classList.remove('hidden');
  } catch {
    resultPrice.textContent = 'Ошибка — проверьте соединение';
    resultBox.classList.remove('hidden');
  } finally {
    calcBtn.classList.remove('loading');
    calcBtn.disabled = false;
  }
});

// ─── Map ───────────────────────────────────────────────────────────────
let map;
let dealsLayers = [];

const COLORS = {
  good:    '#4ade80',  // profit-hi
  neutral: '#fbbf24',  // profit-mid
  bad:     '#f87171',  // profit-lo
  user:    '#60a5fa',  // user-pin
};

function initMap() {
  const params    = new URLSearchParams(window.location.search);
  const paramLat  = params.get('lat');
  const paramLng  = params.get('lng');
  const hasUser   = paramLat && paramLng;

  const centerLat = hasUser ? parseFloat(paramLat) : 55.7539;
  const centerLng = hasUser ? parseFloat(paramLng) : 37.6208;
  const zoom      = hasUser ? 14 : 11;

  map = L.map('map', { zoomControl: true, attributionControl: false })
         .setView([centerLat, centerLng], zoom);

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
  }).addTo(map);

  // Attribution tucked into bottom-right, minimal
  L.control.attribution({ prefix: false })
   .addAttribution('© <a href="https://osm.org/copyright">OSM</a>')
   .addTo(map);

  if (hasUser) {
    L.circleMarker([centerLat, centerLng], {
      color:       COLORS.user,
      fillColor:   COLORS.user,
      fillOpacity: 0.9,
      radius:      9,
      weight:      2,
    })
    .addTo(map)
    .bindPopup('<strong>Ваша позиция</strong>')
    .openPopup();

    // Auto-switch to map tab when coordinates are present
    document.getElementById('tab-map')?.click();
  }

  loadDeals();
}

async function loadDeals() {
  let deals = [];
  try {
    const resp = await fetch('/api/deals');
    if (resp.ok) deals = await resp.json();
  } catch { /* silent — map still usable empty */ }

  // Clear old layers
  dealsLayers.forEach(l => map.removeLayer(l));
  dealsLayers = [];

  deals.forEach(deal => {
    if (!deal.lat || !deal.lng) return;

    let color = COLORS.bad;
    let profitLine = 'Нет оценки';

    if (deal.profit != null) {
      if (deal.profit > 1_000_000) {
        color = COLORS.good;
        profitLine = `+${fmt(deal.profit)} ₽ — выгодно`;
      } else if (deal.profit > 0) {
        color = COLORS.neutral;
        profitLine = `+${fmt(deal.profit)} ₽`;
      } else {
        profitLine = `${fmt(deal.profit)} ₽ — переплата`;
      }
    }

    const popup = `
      <div style="font:14px/1.4 -apple-system,sans-serif;min-width:180px">
        <div style="font-weight:700;margin-bottom:6px">${deal.metro || 'Н/Д'}</div>
        <div style="color:#666;font-size:12px;margin-bottom:8px">
          ${deal.area} м² · ${deal.floor} этаж · ${deal.time_to_metro ?? '?'} мин до метро
        </div>
        <div style="font-size:13px;margin-bottom:4px">
          Цена: <strong>${fmt(deal.price)} ₽</strong>
        </div>
        ${deal.predicted_price ? `<div style="font-size:13px;margin-bottom:4px">Оценка ML: <strong>${fmt(deal.predicted_price)} ₽</strong></div>` : ''}
        <div style="font-size:12px;color:${color};font-weight:600;margin-bottom:8px">${profitLine}</div>
        <a href="${deal.url}" target="_blank"
           style="font-size:12px;color:#e07222;font-weight:600;text-decoration:none">
          Открыть на ЦИАН →
        </a>
      </div>`;

    const marker = L.circleMarker([deal.lat, deal.lng], {
      color,
      fillColor:   color,
      fillOpacity: 0.75,
      radius:      8,
      weight:      1.5,
    }).bindPopup(popup, { maxWidth: 240 });

    marker.addTo(map);
    dealsLayers.push(marker);
  });

  updateStats(deals);
}

// ─── Stats ─────────────────────────────────────────────────────────────
function updateStats(deals) {
  const total = deals.length;

  setValue('statTotal',    total || '—');
  setValue('statGood',     total ? deals.filter(d => d.profit > 0).length : '—');

  if (!total) {
    setValue('statAvgPrice', '—');
    setValue('statAvgArea',  '—');
    return;
  }

  const avgPrice = deals.reduce((s, d) => s + d.price, 0) / total;
  const avgArea  = deals.reduce((s, d) => s + (d.area || 0), 0) / total;

  setValue('statAvgPrice', `${fmt(avgPrice)} ₽`);
  setValue('statAvgArea',  `${avgArea.toFixed(0)} м²`);
}

function setValue(id, val) {
  const cell = document.getElementById(id);
  if (!cell) return;
  cell.querySelector('.stat-value').textContent = val;
}

// ─── Parser ────────────────────────────────────────────────────────────
const parseBtn     = document.getElementById('startParse');
const statusBadge  = document.getElementById('parserStatus');

parseBtn.addEventListener('click', async () => {
  parseBtn.classList.add('loading');
  parseBtn.disabled = true;

  try {
    const resp   = await fetch('/api/parse', { method: 'POST' });
    const result = await resp.json();
    setStatus(result.status === 'started' ? 'running' : 'idle');
  } catch {
    setStatus('idle');
  } finally {
    parseBtn.classList.remove('loading');
    parseBtn.disabled = false;
  }
});

function setStatus(state) {
  statusBadge.className = `status-badge ${state}`;
  statusBadge.textContent = state === 'running' ? 'Запущен' : 'Ожидание';
}

// ─── Helpers ───────────────────────────────────────────────────────────
function fmt(n) {
  return Math.round(n).toLocaleString('ru-RU');
}

// ─── Boot ──────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  initMap();

  fetch('/api/parse/status')
    .then(r => r.json())
    .then(({ status }) => setStatus(
      status === 'started' || status === 'pending' ? 'running' : 'idle'
    ))
    .catch(() => {});
});
