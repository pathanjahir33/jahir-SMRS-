/**
 * Smart Meters Registry & Real-Time Telemetry Inspector
 */

let meterHistoryChart = null;
let currentInspectedMeterId = null;

document.addEventListener('DOMContentLoaded', function () {
  loadMeters();
  loadConsumersForSelect();

  // Search and Filter Listeners
  const searchInput = document.getElementById('meterSearchInput');
  const statusFilter = document.getElementById('meterStatusFilter');
  const feederFilter = document.getElementById('meterFeederFilter');

  if (searchInput) searchInput.addEventListener('input', debounce(loadMeters, 300));
  if (statusFilter) statusFilter.addEventListener('change', loadMeters);
  if (feederFilter) feederFilter.addEventListener('change', loadMeters);

  // Add Meter Form
  const addMeterForm = document.getElementById('addMeterForm');
  if (addMeterForm) {
    addMeterForm.addEventListener('submit', handleAddMeter);
  }

  // Update Status Button in Modal
  const btnUpdateStatus = document.getElementById('btn-update-meter-status');
  if (btnUpdateStatus) {
    btnUpdateStatus.addEventListener('click', handleUpdateMeterStatus);
  }
});

// Debounce helper for search input
function debounce(func, wait) {
  let timeout;
  return function (...args) {
    clearTimeout(timeout);
    timeout = setTimeout(() => func.apply(this, args), wait);
  };
}

async function loadMeters() {
  const search = document.getElementById('meterSearchInput')?.value || '';
  const status = document.getElementById('meterStatusFilter')?.value || 'ALL';
  const feeder = document.getElementById('meterFeederFilter')?.value || 'ALL';

  const params = new URLSearchParams();
  if (search) params.append('search', search);
  if (status !== 'ALL') params.append('status', status);
  if (feeder !== 'ALL') params.append('feeder_id', feeder);

  try {
    const res = await fetch(`/api/meters?${params.toString()}`);
    const data = await res.json();
    if (!data.success) return;

    const tbody = document.getElementById('metersTableBody');
    const badge = document.getElementById('meterCountBadge');
    if (badge) badge.innerText = `${data.count} Meters`;

    if (!data.meters || data.meters.length === 0) {
      tbody.innerHTML = '<tr><td colspan="7" class="text-center py-4 text-secondary">No smart meters found matching your filter criteria.</td></tr>';
      return;
    }

    tbody.innerHTML = data.meters.map(m => {
      let statusBadge = '<span class="badge-status badge-active">Active</span>';
      if (m.status === 'Tampered') statusBadge = '<span class="badge-status badge-tampered">Tampered</span>';
      else if (m.status === 'Faulty') statusBadge = '<span class="badge-status badge-faulty">Faulty</span>';
      else if (m.status === 'Suspended') statusBadge = '<span class="badge bg-secondary">Suspended</span>';

      return `
        <tr>
          <td>
            <strong class="text-white">${m.meter_id}</strong>
            <small class="text-secondary d-block">${m.serial_number}</small>
          </td>
          <td>
            <div class="text-white">${m.consumer_name || 'Unassigned'}</div>
            <small class="text-secondary">${m.consumer_category || 'Residential'}</small>
          </td>
          <td>
            <span class="text-white">${m.feeder_id}</span>
            <small class="text-secondary d-block">${m.substation_name || ''}</small>
          </td>
          <td>
            <small class="text-cyan">${m.tariff_name || m.tariff_id}</small>
          </td>
          <td>
            <span class="fw-bold text-white">${m.current_cumulative_kwh || 0.0}</span>
            <small class="text-secondary"> kWh</small>
          </td>
          <td>${statusBadge}</td>
          <td class="text-end">
            <button class="btn btn-outline-custom btn-sm" onclick="inspectMeter('${m.meter_id}')" title="Inspect live telemetry & electrical logs">
              <i class="bi bi-activity text-cyan me-1"></i>Telemetry
            </button>
          </td>
        </tr>
      `;
    }).join('');
  } catch (err) {
    console.error('Error loading meters:', err);
  }
}

async function loadConsumersForSelect() {
  try {
    const res = await fetch('/api/consumers');
    const data = await res.json();
    if (!data.success) return;

    const select = document.getElementById('new_consumer_id');
    if (select) {
      select.innerHTML = '<option value="">Select registered consumer...</option>' +
        data.consumers.map(c => `<option value="${c.consumer_id}">${c.full_name} (${c.consumer_id} - ${c.category})</option>`).join('');
    }
  } catch (err) {
    console.error('Error loading consumers:', err);
  }
}

async function handleAddMeter(e) {
  e.preventDefault();
  const payload = {
    meter_id: document.getElementById('new_meter_id').value.trim(),
    serial_number: document.getElementById('new_serial_number').value.trim(),
    consumer_id: document.getElementById('new_consumer_id').value,
    feeder_id: document.getElementById('new_feeder_id').value,
    tariff_id: document.getElementById('new_tariff_id').value,
    model: document.getElementById('new_model').value.trim()
  };

  try {
    const res = await fetch('/api/meters', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (data.success) {
      window.showToast(`Meter ${payload.meter_id} registered successfully!`, true);
      const modalEl = document.getElementById('addMeterModal');
      const modal = bootstrap.Modal.getInstance(modalEl);
      if (modal) modal.hide();
      document.getElementById('addMeterForm').reset();
      loadMeters();
    } else {
      window.showToast(data.error || 'Failed to add meter', false);
    }
  } catch (err) {
    window.showToast('Error registering meter: ' + err.message, false);
  }
}

window.inspectMeter = async function (meterId) {
  currentInspectedMeterId = meterId;
  try {
    const res = await fetch(`/api/meters/${meterId}`);
    const data = await res.json();
    if (!data.success) {
      window.showToast('Could not load telemetry for ' + meterId, false);
      return;
    }

    const m = data.meter;
    const history = data.telemetry_history || [];

    document.getElementById('telemetryModalTitle').innerText = `Telemetry: ${m.meter_id} (${m.model})`;
    document.getElementById('telemetryModalSubtitle').innerText = `Serial: ${m.serial_number} | Feeder: ${m.feeder_id}`;

    // Fill metadata
    document.getElementById('info-consumer-name').innerText = m.consumer_name || 'N/A';
    document.getElementById('info-consumer-address').innerText = m.consumer_address || 'N/A';
    document.getElementById('info-tariff-name').innerText = m.tariff_name || m.tariff_id;
    document.getElementById('info-cumulative-kwh').innerText = `${m.current_cumulative_kwh || 0.0} kWh`;
    document.getElementById('modalChangeStatusSelect').value = m.status;

    // Fill instant metrics from latest reading if available
    const latest = history[history.length - 1];
    if (latest) {
      document.getElementById('param-active-power').innerText = `${latest.active_power_kw} kW`;
      document.getElementById('param-voltage').innerText = `${latest.voltage_v} V`;
      document.getElementById('param-current').innerText = `${latest.current_a} A`;
      document.getElementById('param-pf').innerText = latest.power_factor;
    } else {
      document.getElementById('param-active-power').innerText = '0.00 kW';
      document.getElementById('param-voltage').innerText = '230.0 V';
      document.getElementById('param-current').innerText = '0.00 A';
      document.getElementById('param-pf').innerText = '0.95';
    }

    // Render Telemetry Chart
    renderMeterChart(history);

    // Show Modal
    const modal = new bootstrap.Modal(document.getElementById('meterTelemetryModal'));
    modal.show();
  } catch (err) {
    console.error('Error inspecting meter:', err);
    window.showToast('Error opening telemetry modal', false);
  }
};

function renderMeterChart(history) {
  const ctx = document.getElementById('meterHistoryChart').getContext('2d');
  const labels = history.map(h => (h.timestamp || '').split(' ')[1] || h.timestamp);
  const powerData = history.map(h => h.active_power_kw);
  const voltageData = history.map(h => h.voltage_v);

  if (meterHistoryChart) {
    meterHistoryChart.destroy();
  }

  meterHistoryChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: labels.length ? labels : ['00:00', '04:00', '08:00', '12:00', '16:00', '20:00'],
      datasets: [
        {
          label: 'Active Power (kW)',
          data: powerData.length ? powerData : [0, 0, 0, 0, 0, 0],
          borderColor: '#06b6d4',
          backgroundColor: 'rgba(6, 182, 212, 0.1)',
          fill: true,
          tension: 0.3,
          yAxisID: 'y'
        },
        {
          label: 'Line Voltage (V)',
          data: voltageData.length ? voltageData : [230, 230, 230, 230, 230, 230],
          borderColor: 'rgba(255, 255, 255, 0.5)',
          borderDash: [4, 4],
          fill: false,
          tension: 0.2,
          yAxisID: 'y1'
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: '#9ca3af', font: { size: 11 } } }
      },
      scales: {
        x: {
          grid: { color: 'rgba(255,255,255,0.05)' },
          ticks: { color: '#9ca3af', font: { size: 9 }, maxTicksLimit: 8 }
        },
        y: {
          type: 'linear',
          display: true,
          position: 'left',
          grid: { color: 'rgba(255,255,255,0.05)' },
          ticks: { color: '#06b6d4' }
        },
        y1: {
          type: 'linear',
          display: true,
          position: 'right',
          grid: { drawOnChartArea: false },
          ticks: { color: '#9ca3af' },
          min: 190,
          max: 260
        }
      }
    }
  });
}

async function handleUpdateMeterStatus() {
  if (!currentInspectedMeterId) return;
  const newStatus = document.getElementById('modalChangeStatusSelect').value;

  try {
    const res = await fetch(`/api/meters/${currentInspectedMeterId}/status`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: newStatus })
    });
    const data = await res.json();
    if (data.success) {
      window.showToast(`Meter status updated to ${newStatus}`, true);
      loadMeters();
    } else {
      window.showToast(data.error || 'Failed to update status', false);
    }
  } catch (err) {
    window.showToast('Error updating status: ' + err.message, false);
  }
}
