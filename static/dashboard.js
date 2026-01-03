(function () {
  const filtersForm = document.getElementById('filters-form');
  const resetBtn = document.getElementById('reset-filters');
  const refreshBtn = document.getElementById('refresh-dashboard');
  const applyBtn = filtersForm?.querySelector('button[type="submit"]');
  const pageSizeSelect = document.getElementById('page-size');
  const collisionsBody = document.getElementById('collisions-body');
  const collisionsPrev = document.getElementById('collisions-prev');
  const collisionsNext = document.getElementById('collisions-next');
  const collisionsHint = document.getElementById('collisions-hint');
  const collisionsDownloadBtn = document.getElementById('collisions-download');
  const sortHeaders = Array.from(document.querySelectorAll('th[data-sort-key]'));
  const detailPanel = document.getElementById('collision-detail');
  const detailContent = document.getElementById('collision-detail-content');
  const flagForm = document.getElementById('flag-form');
  const flagCollisionInput = document.getElementById('flag-collision-id');
  const flagStatus = document.getElementById('flag-status');
  const topIntersectionsBody = document.getElementById('top-intersections-body');
  const topLimitInput = document.getElementById('top-limit');
  const topRefreshBtn = document.getElementById('top-refresh');
  const topDownloadBtn = document.getElementById('top-download');
  const nearForm = document.getElementById('near-form');
  const nearBody = document.getElementById('near-body');
  const alertBox = document.getElementById('dashboard-alert');

  const chartRegistry = {};
  let collisionsState = { next: null, previous: null, current: null };
  let collisionsCache = [];
  let collisionsDisplay = [];
  let collisionsHintText = '';
  let currentSort = { key: null, direction: 'asc' };
  let topIntersectionsCache = [];

  document.addEventListener('DOMContentLoaded', () => {
    restoreFiltersFromQuery();

    filtersForm?.addEventListener('submit', evt => {
      evt.preventDefault();
      applyFiltersAndRefresh();
    });

    resetBtn?.addEventListener('click', () => {
      filtersForm?.reset();
      clearFiltersFromUrl();
      applyFiltersAndRefresh();
    });

    refreshBtn?.addEventListener('click', () => applyFiltersAndRefresh());

    pageSizeSelect?.addEventListener('change', () => {
      loadCollisions().catch(err => setAlert(err.message, true));
    });

    collisionsPrev?.addEventListener('click', () => {
      if (collisionsState.previous) {
        loadCollisions(collisionsState.previous).catch(err => setAlert(err.message, true));
      }
    });

    collisionsNext?.addEventListener('click', () => {
      if (collisionsState.next) {
        loadCollisions(collisionsState.next).catch(err => setAlert(err.message, true));
      }
    });

    collisionsBody?.addEventListener('click', evt => {
      const row = evt.target?.closest('tr[data-collision-id]');
      if (row) {
        loadCollisionDetail(row.dataset.collisionId).catch(err => setAlert(err.message, true));
      }
    });

    sortHeaders.forEach(th => {
      const key = th.dataset.sortKey;
      const button = th.querySelector('button');
      if (!key || !button) return;
      button.addEventListener('click', () => sortCollisions(key));
    });

    collisionsDownloadBtn?.addEventListener('click', () => {
      downloadCsv('collisions-page.csv', collisionsDisplay, [
        { label: 'collision_id', value: row => row.collision_id },
        { label: 'occurred_at', value: row => row.occurred_at },
        { label: 'quadrant', value: row => row.quadrant },
        { label: 'count', value: row => row.count },
        { label: 'location_text', value: row => row.location_text },
        { label: 'station', value: row => row.nearest_station?.name || '' },
      ]);
    });

    topLimitInput?.addEventListener('change', () => {
      loadTopIntersections().catch(err => setAlert(err.message, true));
    });

    topRefreshBtn?.addEventListener('click', () => {
      loadTopIntersections().catch(err => setAlert(err.message, true));
    });

    topDownloadBtn?.addEventListener('click', () => {
      downloadCsv('top-intersections.csv', topIntersectionsCache, [
        { label: 'intersection_key', value: row => row.intersection_key },
        { label: 'location_text', value: row => row.location_text },
        { label: 'total', value: row => row.total },
        { label: 'collisions', value: row => row.collisions },
      ]);
    });

    nearForm?.addEventListener('submit', evt => {
      evt.preventDefault();
      loadNearCollisions().catch(err => setAlert(err.message, true));
    });

    flagForm?.addEventListener('submit', evt => {
      evt.preventDefault();
      submitFlagForm().catch(err => setFlagStatus(err.message, true));
    });

    applyFiltersAndRefresh();
  });

  async function applyFiltersAndRefresh() {
    updateUrlWithFilters();
    await refreshDashboard();
  }

  async function refreshDashboard() {
    if (!filtersForm) return;
    setLoadingState(true);
    setAlert('Loading dashboard...');
    const tasks = [
      loadMonthlyTrend(),
      loadHourly(),
      loadWeekday(),
      loadQuadrantShare(),
      loadWeatherStats(),
      loadTopIntersections(),
      loadCollisions(),
      loadNearCollisions(true),
    ];
    const errors = [];
    await Promise.all(
      tasks.map(p => p.catch(err => {
        errors.push(err);
      })),
    );
    setLoadingState(false);
    if (errors.length) {
      setAlert(`Some data failed to load: ${errors[0].message}`, true);
    } else {
      setAlert('Dashboard updated.');
    }
  }

  async function loadMonthlyTrend() {
    const qs = buildQuery();
    const data = await fetchJSON(`/api/v1/stats/monthly-trend?${qs}`);
    const months = Array.from({ length: 12 }, (_, i) => i + 1);
    const totals = months.map(month => {
      const entry = data.results?.find(row => row.month === month);
      return entry ? entry.total : 0;
    });
    renderChart('monthly', 'monthly-chart', {
      type: 'bar',
      data: {
        labels: months.map(monthLabel),
        datasets: [
          {
            label: 'Collisions',
            data: totals,
            backgroundColor: '#c8102e88',
            borderColor: '#c8102e',
            borderWidth: 1,
          },
        ],
      },
      options: {
        responsive: true,
        plugins: { legend: { display: false } },
        scales: { y: { beginAtZero: true } },
      },
    });
  }

  async function loadHourly() {
    const commute = getCommuteSelection();
    const qs = buildQuery({ commute }, { includeCommute: false });
    const data = await fetchJSON(`/api/v1/stats/by-hour?${qs}`);
    const hours = Array.from({ length: 24 }, (_, i) => i);
    const totals = hours.map(hour => {
      const entry = data.results?.find(row => row.hour === hour);
      return entry ? entry.total : 0;
    });
    renderChart('hourly', 'hourly-chart', {
      type: 'line',
      data: {
        labels: hours.map(h => `${h}:00`),
        datasets: [
          {
            label: 'Collisions',
            data: totals,
            borderColor: '#c8102e',
            backgroundColor: '#c8102e33',
            tension: 0.3,
            fill: true,
          },
        ],
      },
      options: {
        responsive: true,
        plugins: {
          legend: { display: false },
          title: {
            display: Boolean(commute),
            text: commute ? `Commute filter: ${commute.toUpperCase()}` : '',
          },
        },
        scales: { y: { beginAtZero: true } },
      },
    });
  }

  async function loadWeekday() {
    const qs = buildQuery();
    const data = await fetchJSON(`/api/v1/stats/weekday?${qs}`);
    const days = Array.from({ length: 7 }, (_, i) => i);
    const totals = days.map(day => {
      const entry = data.results?.find(row => row.weekday === day);
      return entry ? entry.total : 0;
    });
    renderChart('weekday', 'weekday-chart', {
      type: 'bar',
      data: {
        labels: days.map(dayLabel),
        datasets: [
          {
            label: 'Collisions',
            data: totals,
            backgroundColor: '#0f62fe55',
            borderColor: '#0f62fe',
          },
        ],
      },
      options: {
        responsive: true,
        plugins: { legend: { display: false } },
        scales: { y: { beginAtZero: true } },
      },
    });
  }

  async function loadQuadrantShare() {
    const qs = buildQuery();
    const data = await fetchJSON(`/api/v1/stats/quadrant-share?${qs}`);
    const keys = ['NE', 'NW', 'SE', 'SW', 'UNK'];
    const totals = keys.map(key => {
      const entry = data.results?.find(row => row.quadrant === key);
      return entry ? entry.total : 0;
    });
    renderChart('quadrant', 'quadrant-chart', {
      type: 'doughnut',
      data: {
        labels: keys.map(k => (k === 'UNK' ? 'Unknown' : k)),
        datasets: [
          {
            data: totals,
            backgroundColor: ['#c8102e', '#f5643b', '#ffd166', '#06d6a0', '#adb5bd'],
          },
        ],
      },
      options: {
        responsive: true,
        plugins: { legend: { position: 'bottom' } },
      },
    });
  }

  async function loadWeatherStats() {
    const qs = buildQuery();
    const data = await fetchJSON(`/api/v1/stats/by-weather?${qs}`);
    const order = ['DRY', 'WET', 'SNY'];
    const labels = ['Dry', 'Wet', 'Snowy'];
    const totals = order.map(code => {
      const entry = data.results?.find(row => row.weather_day === code);
      return entry ? entry.total : 0;
    });
    renderChart('weather', 'weather-chart', {
      type: 'bar',
      data: {
        labels,
        datasets: [
          {
            label: 'Collisions',
            data: totals,
            backgroundColor: ['#2b8a3e', '#1c7ed6', '#868e96'],
          },
        ],
      },
      options: {
        responsive: true,
        plugins: { legend: { display: false } },
        scales: { y: { beginAtZero: true } },
      },
    });
  }

  async function loadTopIntersections() {
    const limit = clampNumber(parseInt(topLimitInput?.value ?? '10', 10) || 10, 1, 50);
    if (topLimitInput) {
      topLimitInput.value = String(limit);
    }
    const qs = buildQuery({ limit });
    const data = await fetchJSON(`/api/v1/stats/top-intersections?${qs}`);
    const rows = data.results || [];
    topIntersectionsCache = rows;
    if (!rows.length) {
      topIntersectionsBody.innerHTML = '<tr><td colspan="4">No data for current filters.</td></tr>';
      return;
    }
    topIntersectionsBody.innerHTML = rows
      .map(row => {
        const desc = row.location_text || '—';
        return `<tr><td>${escapeHtml(row.intersection_key)}</td><td>${escapeHtml(desc)}</td><td>${row.total}</td><td>${row.collisions}</td></tr>`;
      })
      .join('');
  }

  async function loadCollisions(url) {
    try {
      const pageSize = pageSizeSelect ? Number(pageSizeSelect.value) : 50;
      const endpoint = url || `/api/v1/collisions/?${buildQuery({ page_size: pageSize })}`;
      collisionsBody.innerHTML = '<tr><td colspan="6">Loading...</td></tr>';
      const data = await fetchJSON(endpoint);
      collisionsState = {
        next: normalizeApiUrl(data.next),
        previous: normalizeApiUrl(data.previous),
        current: endpoint,
      };
      collisionsPrev.disabled = !collisionsState.previous;
      collisionsNext.disabled = !collisionsState.next;
      collisionsCache = data.results || [];
      collisionsHintText = collisionsCache.length
        ? `Showing ${collisionsCache.length} of ${data.count ?? 'unknown'} collisions`
        : 'No collisions to display.';
      if (!collisionsCache.length) {
        collisionsBody.innerHTML = '<tr><td colspan="6">No collisions match the current filters.</td></tr>';
        collisionsHint.textContent = collisionsHintText;
        return;
      }
      currentSort = { key: null, direction: 'asc' };
      updateSortIndicators();
      renderCollisionsTable(collisionsCache);
    } catch (err) {
      collisionsBody.innerHTML = '<tr><td colspan="6">Unable to load collisions.</td></tr>';
      collisionsHintText = 'Error loading collisions.';
      collisionsHint.textContent = collisionsHintText;
      throw err;
    }
  }

  function renderCollisionsTable(rows) {
    collisionsDisplay = rows.slice();
    collisionsBody.innerHTML = rows
      .map(item => {
        const station = item.nearest_station ? item.nearest_station.name : '—';
        const occurred = item.occurred_at ? formatDate(item.occurred_at) : '—';
        return `<tr data-collision-id="${escapeHtml(item.collision_id)}">
            <td>${escapeHtml(item.collision_id)}</td>
            <td>${occurred}</td>
            <td>${item.quadrant || 'UNK'}</td>
            <td>${item.count || 1}</td>
            <td>${escapeHtml(item.location_text || '')}</td>
            <td>${escapeHtml(station)}</td>
          </tr>`;
      })
      .join('');
    collisionsHint.textContent = collisionsHintText;
  }

  async function loadCollisionDetail(collisionId) {
    if (!collisionId) return;
    detailContent.textContent = 'Loading detail...';
    detailPanel.hidden = false;
    flagForm?.setAttribute('hidden', 'hidden');
    try {
      const data = await fetchJSON(`/api/v1/collisions/${encodeURIComponent(collisionId)}/`);
      detailContent.textContent = JSON.stringify(data, null, 2);
      if (flagForm && flagCollisionInput && flagStatus) {
        flagForm.reset();
        flagCollisionInput.value = collisionId;
        flagStatus.textContent = '';
        flagForm.hidden = false;
      }
    } catch (err) {
      detailContent.textContent = 'Unable to load collision detail.';
      throw err;
    }
  }

  async function loadNearCollisions(skipIfUnchanged = false) {
    if (!nearForm) return;
    const formData = new FormData(nearForm);
    const params = {};
    for (const [key, value] of formData.entries()) {
      if (value !== null && String(value).trim() !== '') {
        params[key] = String(value).trim();
      }
    }
    if (!params.lat || !params.lon) {
      if (skipIfUnchanged) {
        return;
      }
      nearBody.innerHTML = '<tr><td colspan="5">Latitude and longitude are required.</td></tr>';
      return;
    }
    const qs = buildQuery(params);
    try {
      nearBody.innerHTML = '<tr><td colspan="5">Loading...</td></tr>';
      const data = await fetchJSON(`/api/v1/collisions/near?${qs}`);
      if (!data.results?.length) {
        nearBody.innerHTML = '<tr><td colspan="5">No nearby collisions for that point.</td></tr>';
        return;
      }
      nearBody.innerHTML = data.results
        .map(item => {
          const occurred = item.occurred_at ? formatDate(item.occurred_at) : '—';
          const distance = typeof item.distance_km === 'number' ? item.distance_km.toFixed(3) : item.distance_km ?? '—';
          return `<tr><td>${escapeHtml(item.collision_id)}</td><td>${distance}</td><td>${occurred}</td><td>${item.quadrant || 'UNK'}</td><td>${escapeHtml(item.location_text || '')}</td></tr>`;
        })
        .join('');
    } catch (err) {
      nearBody.innerHTML = '<tr><td colspan="5">Unable to load near collisions.</td></tr>';
      throw err;
    }
  }

  async function submitFlagForm() {
    if (!flagForm || !flagCollisionInput) return;
    const collisionId = flagCollisionInput.value;
    const note = flagForm.elements.namedItem('note')?.value?.trim();
    if (!collisionId || !note) {
      setFlagStatus('Select a collision and provide a note.', true);
      return;
    }
    setFlagStatus('Saving flag...');
    await fetchJSON('/api/v1/flags/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ collision: collisionId, note }),
    });
    setFlagStatus('Flag created.');
    flagForm.reset();
    flagCollisionInput.value = collisionId;
  }

  function sortCollisions(key) {
    if (!collisionsCache.length) return;
    const direction = currentSort.key === key && currentSort.direction === 'asc' ? 'desc' : 'asc';
    currentSort = { key, direction };
    const sorted = [...collisionsCache].sort((a, b) => compareValues(getCollisionValue(a, key), getCollisionValue(b, key), direction));
    renderCollisionsTable(sorted);
    updateSortIndicators();
  }

  function updateSortIndicators() {
    sortHeaders.forEach(th => {
      if (!th.dataset.sortKey) return;
      const isActive = currentSort.key === th.dataset.sortKey;
      th.setAttribute('aria-sort', isActive ? currentSort.direction : 'none');
    });
  }

  function getCollisionValue(row, key) {
    switch (key) {
      case 'occurred_at':
        return row.occurred_at ? new Date(row.occurred_at).getTime() : 0;
      case 'count':
        return Number(row.count || 0);
      case 'station':
        return row.nearest_station?.name || '';
      default:
        return row[key] ?? '';
    }
  }

  function compareValues(a, b, direction) {
    if (a === b) return 0;
    const factor = direction === 'asc' ? 1 : -1;
    if (typeof a === 'number' && typeof b === 'number') {
      return (a - b) * factor;
    }
    return String(a).localeCompare(String(b)) * factor;
  }

  function getFilters(options = {}) {
    const includeCommute = options.includeCommute ?? false;
    const includeAliases = options.includeAliases ?? true;
    if (!filtersForm) return {};
    const params = {};
    const formData = new FormData(filtersForm);
    for (const [key, value] of formData.entries()) {
      if (value !== null && String(value).trim() !== '') {
        if (key === 'commute' && !includeCommute) {
          continue;
        }
        params[key] = String(value).trim();
        if (includeAliases) {
          if (key === 'from_date') {
            params.from = params[key];
          }
          if (key === 'to_date') {
            params.to = params[key];
          }
        }
      }
    }
    return params;
  }

  function getCommuteSelection() {
    const select = filtersForm?.querySelector('select[name="commute"]');
    return select ? select.value : '';
  }

  function buildQuery(extraParams = {}, options = {}) {
    const filters = getFilters({
      includeCommute: options.includeCommute ?? false,
      includeAliases: options.includeAliases ?? true,
    });
    const params = { ...filters, ...extraParams };
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        searchParams.append(key, value);
      }
    });
    return searchParams.toString();
  }

  function updateUrlWithFilters() {
    const params = getFilters({ includeCommute: true, includeAliases: false });
    const search = new URLSearchParams(params).toString();
    const url = new URL(window.location.href);
    url.search = search ? `?${search}` : '';
    history.replaceState(null, '', url);
  }

  function restoreFiltersFromQuery() {
    if (!filtersForm) return;
    const params = new URLSearchParams(window.location.search);
    params.forEach((value, key) => {
      let target = key;
      if (key === 'from') {
        target = 'from_date';
      } else if (key === 'to') {
        target = 'to_date';
      }
      const field = filtersForm.elements.namedItem(target);
      if (field && 'value' in field) {
        field.value = value;
      }
    });
  }

  function clearFiltersFromUrl() {
    const url = new URL(window.location.href);
    url.search = '';
    history.replaceState(null, '', url);
  }

  function setLoadingState(isLoading) {
    if (refreshBtn) refreshBtn.disabled = isLoading;
    if (applyBtn) applyBtn.disabled = isLoading;
  }

  function setAlert(message = '', isError = false) {
    if (!alertBox) return;
    alertBox.textContent = message;
    alertBox.classList.toggle('error', Boolean(message) && isError);
  }

  function setFlagStatus(message, isError = false) {
    if (!flagStatus) return;
    flagStatus.textContent = message;
    flagStatus.classList.toggle('error', Boolean(message) && isError);
  }

  async function fetchJSON(url, options = {}) {
    const headers = { Accept: 'application/json', ...(options.headers || {}) };
    const response = await fetch(url, { ...options, headers });
    if (!response.ok) {
      const detail = await safeReadText(response);
      throw new Error(detail || `Request failed ${response.status}`);
    }
    const text = await response.text();
    return text ? JSON.parse(text) : {};
  }

  async function safeReadText(response) {
    try {
      return await response.text();
    } catch (err) {
      return '';
    }
  }

  function downloadCsv(filename, rows, columns) {
    if (!rows.length) {
      setAlert('No data to download.', true);
      return;
    }
    const header = columns.map(col => col.label).join(',');
    const body = rows
      .map(row => columns.map(col => formatCsvCell(col.value(row))).join(','))
      .join('\r\n');
    const csv = `${header}\r\n${body}`;
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }

  function formatCsvCell(value) {
    const normalized = value ?? '';
    const str = typeof normalized === 'string' ? normalized : String(normalized);
    if (/[",\n]/.test(str)) {
      return `"${str.replace(/"/g, '""')}"`;
    }
    return str;
  }

  function renderChart(key, canvasId, config) {
    const canvas = document.getElementById(canvasId);
    if (!canvas || typeof Chart === 'undefined') return;
    if (chartRegistry[key]) {
      chartRegistry[key].data = config.data;
      chartRegistry[key].options = config.options ?? {};
      chartRegistry[key].update();
    } else {
      chartRegistry[key] = new Chart(canvas.getContext('2d'), config);
    }
  }

  function monthLabel(month) {
    const date = new Date(2024, month - 1, 1);
    return date.toLocaleString('en-CA', { month: 'short' });
  }

  function dayLabel(day) {
    const reference = new Date(2024, 0, 1 + day);
    return reference.toLocaleString('en-CA', { weekday: 'short' });
  }

  function formatDate(value) {
    try {
      return new Date(value).toLocaleString('en-CA', { timeZone: 'America/Edmonton' });
    } catch (err) {
      return value;
    }
  }

  function normalizeApiUrl(url) {
    if (!url) return null;
    try {
      const parsed = new URL(url, window.location.origin);
      return `${parsed.pathname}${parsed.search}`;
    } catch (err) {
      return url;
    }
  }

  function clampNumber(value, min, max) {
    return Math.min(Math.max(value, min), max);
  }

  function escapeHtml(value) {
    return String(value ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }
})();
