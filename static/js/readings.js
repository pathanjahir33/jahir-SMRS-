/**
 * Structured Ingestion Portal & REST API Tester
 */

document.addEventListener('DOMContentLoaded', function () {
  loadMetersDropdown();
  loadReadingsTable();

  // Form Submission
  const form = document.getElementById('ingestForm');
  if (form) form.addEventListener('submit', handleIngestSubmit);

  // Pre-fill button
  const btnSample = document.getElementById('btn-prefill-json');
  if (btnSample) btnSample.addEventListener('click', prefillSampleData);

  // Seed History button
  const btnSeed = document.getElementById('btn-seed-history');
  if (btnSeed) btnSeed.addEventListener('click', handleSeedHistory);

  // Filter dropdown & refresh button
  const filterMeter = document.getElementById('filterReadingMeter');
  if (filterMeter) filterMeter.addEventListener('change', () => loadReadingsTable(filterMeter.value));

  const btnRefresh = document.getElementById('btn-refresh-readings');
  if (btnRefresh) btnRefresh.addEventListener('click', () => loadReadingsTable(filterMeter?.value));
});

window.refreshReadingsTable = function () {
  const filterMeter = document.getElementById('filterReadingMeter');
  loadReadingsTable(filterMeter ? filterMeter.value : '');
};

async function loadMetersDropdown() {
  try {
    const res = await fetch('/api/meters');
    const data = await res.json();
    if (!data.success) return;

    const selectIngest = document.getElementById('ingest_meter_id');
    const selectFilter = document.getElementById('filterReadingMeter');

    const optionsHtml = data.meters.map(m =>
      `<option value="${m.meter_id}">${m.meter_id} (${m.consumer_name || 'Unassigned'})</option>`
    ).join('');

    if (selectIngest) selectIngest.innerHTML = '<option value="">Select target meter...</option>' + optionsHtml;
    if (selectFilter) selectFilter.innerHTML = '<option value="">All Meters</option>' + optionsHtml;
  } catch (err) {
    console.error('Error loading meter dropdowns:', err);
  }
}

async function loadReadingsTable(meterId = '') {
  try {
    const url = `/api/readings/recent?limit=40${meterId ? '&meter_id=' + meterId : ''}`;
    const res = await fetch(url);
    const data = await res.json();
    if (!data.success) return;

    const tbody = document.getElementById('readingsLogTableBody');
    if (!data.readings || data.readings.length === 0) {
      tbody.innerHTML = '<tr><td colspan="10" class="text-center py-4 text-secondary">No telemetry records found.</td></tr>';
      return;
    }

    tbody.innerHTML = data.readings.map(r => {
      const isPeak = r.is_peak_hour ? '<span class="badge bg-warning text-dark">Peak</span>' : '<span class="badge bg-secondary">Off-Peak</span>';
      return `
        <tr>
          <td><code class="text-secondary">#${r.reading_id}</code></td>
          <td><strong class="text-white">${r.meter_id}</strong></td>
          <td><small class="text-secondary">${r.timestamp}</small></td>
          <td><span class="text-white fw-bold">${r.cumulative_kwh}</span></td>
          <td><span class="text-cyan fw-bold">${r.active_power_kw}</span></td>
          <td><span class="text-secondary">${r.voltage_v}</span></td>
          <td><span class="text-secondary">${r.current_a}</span></td>
          <td><span class="text-emerald">${r.power_factor}</span></td>
          <td>${isPeak}</td>
          <td><span class="badge bg-dark border border-secondary text-secondary">${r.ingestion_mode}</span></td>
        </tr>
      `;
    }).join('');
  } catch (err) {
    console.error('Error loading readings table:', err);
  }
}

function prefillSampleData() {
  const select = document.getElementById('ingest_meter_id');
  if (select && select.options.length > 1) {
    select.selectedIndex = 1; // Pick first available meter
  }
  document.getElementById('ingest_active_kw').value = (Math.random() * 4 + 1.2).toFixed(2);
  document.getElementById('ingest_kwh').value = (Math.random() * 300 + 400).toFixed(2);
  document.getElementById('ingest_voltage').value = (228 + Math.random() * 6).toFixed(1);
  document.getElementById('ingest_pf').value = (0.93 + Math.random() * 0.05).toFixed(2);
  window.showToast('Pre-filled sample smart meter telemetry payload');
}

async function handleIngestSubmit(e) {
  e.preventDefault();
  const btn = document.getElementById('btn-submit-reading');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Ingesting...';

  const payload = {
    meter_id: document.getElementById('ingest_meter_id').value,
    active_power_kw: parseFloat(document.getElementById('ingest_active_kw').value),
    cumulative_kwh: parseFloat(document.getElementById('ingest_kwh').value),
    voltage_v: parseFloat(document.getElementById('ingest_voltage').value),
    power_factor: parseFloat(document.getElementById('ingest_pf').value),
    tamper_alert: document.getElementById('ingest_tamper').value === '1'
  };

  const responseViewer = document.getElementById('apiResponseViewer');
  const badge = document.getElementById('responseStatusBadge');

  try {
    const res = await fetch('/api/readings/ingest', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();

    badge.innerText = `HTTP ${res.status} ${res.ok ? 'OK' : 'ERROR'}`;
    badge.className = `badge ${res.ok ? 'bg-success' : 'bg-danger'}`;
    responseViewer.innerText = JSON.stringify(data, null, 2);

    if (data.success) {
      window.showToast(`Reading ingested into structured storage for ${payload.meter_id}!`, true);
      loadReadingsTable();
    } else {
      window.showToast(data.error || 'Ingestion failed', false);
    }
  } catch (err) {
    badge.innerText = 'HTTP ERROR';
    badge.className = 'badge bg-danger';
    responseViewer.innerText = JSON.stringify({ error: err.message }, null, 2);
    window.showToast('Network error during ingestion: ' + err.message, false);
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<i class="bi bi-send me-1"></i>Post Reading via REST API';
  }
}

async function handleSeedHistory() {
  const btn = document.getElementById('btn-seed-history');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Seeding...';

  try {
    const res = await fetch('/api/simulator/seed', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ days: 5 })
    });
    const data = await res.json();
    if (data.success) {
      window.showToast(data.message, true);
      loadReadingsTable();
    } else {
      window.showToast('Seed failed: ' + data.error, false);
    }
  } catch (err) {
    window.showToast('Error seeding: ' + err.message, false);
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<i class="bi bi-clock-history me-1"></i>Seed 5-Day Data';
  }
}
