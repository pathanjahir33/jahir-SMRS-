/**
 * Dashboard & Operations Analytics
 * Renders Chart.js 24-hr Load Curve, KPIs, Category Distribution & Feeder Gauges
 */

let loadCurveChart = null;
let categoryChart = null;

document.addEventListener('DOMContentLoaded', function () {
  initDashboard();

  const feederSelect = document.getElementById('chartFeederFilter');
  if (feederSelect) {
    feederSelect.addEventListener('change', () => loadSystemCurve(feederSelect.value));
  }

  const btnRefresh = document.getElementById('btn-refresh-curve');
  if (btnRefresh) {
    btnRefresh.addEventListener('click', () => {
      loadSystemCurve(feederSelect ? feederSelect.value : 'ALL');
      loadKPIs();
      loadFeederCapacities();
      loadRecentTelemetry();
    });
  }
});

async function initDashboard() {
  await Promise.all([
    loadKPIs(),
    loadSystemCurve('ALL'),
    loadCategoryDistribution(),
    loadFeederCapacities(),
    loadRecentTelemetry()
  ]);
}

window.refreshDashboardData = async function () {
  const feederSelect = document.getElementById('chartFeederFilter');
  const feederVal = feederSelect ? feederSelect.value : 'ALL';
  await Promise.all([
    loadKPIs(),
    loadSystemCurve(feederVal),
    loadFeederCapacities(),
    loadRecentTelemetry()
  ]);
};

// 1. Load KPI Metrics
async function loadKPIs() {
  try {
    const res = await fetch('/api/analytics/kpis');
    const data = await res.json();
    if (!data.success) return;

    const k = data.kpis;
    document.getElementById('val-active-meters').innerText = k.active_meters;
    document.getElementById('val-total-meters').innerText = k.total_meters;
    document.getElementById('val-today-energy').innerHTML = `${k.today_energy_kwh} <small style="font-size: 1rem; color: #9ca3af;">kWh</small>`;
    document.getElementById('val-collection-rate').innerText = `${k.collection_rate_pct}%`;
    document.getElementById('val-unpaid-bills').innerText = k.unpaid_bills_count;
    document.getElementById('val-active-alerts').innerText = k.active_alerts;

    const tamperText = document.getElementById('val-tamper-text');
    if (k.tampered_meters > 0) {
      tamperText.innerHTML = `<span class="badge bg-danger">${k.tampered_meters} Tampered</span>`;
    } else {
      tamperText.innerText = 'Grid Operating Normal';
      tamperText.className = 'text-emerald';
    }
  } catch (err) {
    console.error('Error loading KPIs:', err);
  }
}

// 2. Load 24-Hour System Load Curve (Chart.js)
async function loadSystemCurve(feederId = 'ALL') {
  try {
    const url = `/api/analytics/load-curve${feederId && feederId !== 'ALL' ? '?feeder_id=' + feederId : ''}`;
    const res = await fetch(url);
    const data = await res.json();
    if (!data.success) return;

    const c = data.curve;
    document.getElementById('stat-peak-demand').innerText = `${c.max_demand_kw} kW`;
    document.getElementById('stat-load-factor').innerText = `${c.load_factor_pct}%`;
    document.getElementById('stat-peak-window').innerText = c.peak_window;

    const ctx = document.getElementById('systemLoadChart').getContext('2d');

    // Create cyan gradient
    const gradient = ctx.createLinearGradient(0, 0, 0, 300);
    gradient.addColorStop(0, 'rgba(6, 182, 212, 0.4)');
    gradient.addColorStop(1, 'rgba(6, 182, 212, 0.0)');

    if (loadCurveChart) {
      loadCurveChart.data.labels = c.labels;
      loadCurveChart.data.datasets[0].data = c.total_load_kw;
      loadCurveChart.data.datasets[1].data = c.peak_load_kw;
      loadCurveChart.update();
    } else {
      loadCurveChart = new Chart(ctx, {
        type: 'line',
        data: {
          labels: c.labels,
          datasets: [
            {
              label: 'Hourly Active Load (kW)',
              data: c.total_load_kw,
              borderColor: '#06b6d4',
              backgroundColor: gradient,
              fill: true,
              tension: 0.35,
              pointBackgroundColor: '#06b6d4',
              pointBorderColor: '#fff',
              pointRadius: 3,
              pointHoverRadius: 6,
              borderWidth: 2
            },
            {
              label: 'Peak Hour Envelope (kW)',
              data: c.peak_load_kw,
              borderColor: 'rgba(245, 158, 11, 0.7)',
              borderDash: [5, 5],
              fill: false,
              tension: 0.3,
              pointRadius: 0,
              borderWidth: 1.5
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          interaction: { mode: 'index', intersect: false },
          plugins: {
            legend: {
              labels: { color: '#9ca3af', font: { family: 'Plus Jakarta Sans', size: 12 } }
            },
            tooltip: {
              backgroundColor: '#111827',
              borderColor: 'rgba(255,255,255,0.1)',
              borderWidth: 1,
              titleColor: '#fff',
              bodyColor: '#06b6d4',
              padding: 10
            }
          },
          scales: {
            x: {
              grid: { color: 'rgba(255, 255, 255, 0.05)' },
              ticks: { color: '#9ca3af', font: { size: 10 } }
            },
            y: {
              grid: { color: 'rgba(255, 255, 255, 0.05)' },
              ticks: {
                color: '#9ca3af',
                callback: function (val) { return val + ' kW'; }
              }
            }
          }
        }
      });
    }
  } catch (err) {
    console.error('Error rendering system load curve:', err);
  }
}

// 3. Category Consumption Distribution (Chart.js Doughnut)
async function loadCategoryDistribution() {
  try {
    const res = await fetch('/api/analytics/category-distribution');
    const data = await res.json();
    if (!data.success) return;

    const d = data.distribution;
    const ctx = document.getElementById('categoryPieChart').getContext('2d');

    if (categoryChart) {
      categoryChart.data.labels = d.labels;
      categoryChart.data.datasets[0].data = d.kwh;
      categoryChart.update();
    } else {
      categoryChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
          labels: d.labels,
          datasets: [{
            data: d.kwh,
            backgroundColor: [
              '#06b6d4', // Residential (Cyan)
              '#3b82f6', // Commercial (Blue)
              '#10b981'  // Industrial (Emerald)
            ],
            borderColor: '#111827',
            borderWidth: 3,
            hoverOffset: 6
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          cutout: '70%',
          plugins: {
            legend: { display: false }
          }
        }
      });
    }

    // Render legend with percentages
    const total = d.kwh.reduce((a, b) => a + b, 0) || 1;
    const legendEl = document.getElementById('categoryBreakdownLegend');
    const colors = ['#06b6d4', '#3b82f6', '#10b981'];
    legendEl.innerHTML = d.labels.map((lbl, idx) => {
      const pct = ((d.kwh[idx] / total) * 100).toFixed(1);
      return `
        <div class="d-flex justify-content-between align-items-center mb-1 small">
          <div class="d-flex align-items-center gap-2">
            <span style="width: 10px; height: 10px; border-radius: 50%; background: ${colors[idx % colors.length]}; display: inline-block;"></span>
            <span class="text-white">${lbl}</span>
          </div>
          <div>
            <strong class="text-white">${d.kwh[idx]} kWh</strong>
            <span class="text-secondary ms-1">(${pct}%)</span>
          </div>
        </div>
      `;
    }).join('');
  } catch (err) {
    console.error('Error rendering category distribution:', err);
  }
}

// 4. Feeder Capacities
async function loadFeederCapacities() {
  try {
    const res = await fetch('/api/analytics/feeder-capacities');
    const data = await res.json();
    if (!data.success) return;

    const container = document.getElementById('feederCapacityContainer');
    container.innerHTML = data.feeders.map(f => {
      const barColor = f.status === 'CRITICAL' ? 'bg-danger' : (f.status === 'WARNING' ? 'bg-warning' : 'bg-cyan');
      return `
        <div class="mb-3">
          <div class="d-flex justify-content-between align-items-center mb-1 small">
            <div>
              <strong class="text-white">${f.feeder_id}</strong>
              <span class="text-secondary ms-2">${f.substation_name}</span>
            </div>
            <div>
              <span class="fw-bold text-white">${f.current_load_kw} kW</span>
              <span class="text-secondary">/ ${f.rated_capacity_kw} kW</span>
              <span class="badge bg-${f.status_color} ms-2" style="font-size: 0.65rem;">${f.utilization_pct}%</span>
            </div>
          </div>
          <div class="progress" style="height: 7px; background-color: rgba(255,255,255,0.08);">
            <div class="progress-bar ${barColor}" role="progressbar" style="width: ${f.utilization_pct}%" aria-valuenow="${f.utilization_pct}" aria-valuemin="0" aria-valuemax="100"></div>
          </div>
        </div>
      `;
    }).join('');
  } catch (err) {
    console.error('Error loading feeder capacities:', err);
  }
}

// 5. Recent Telemetry Logs for Dashboard Table
async function loadRecentTelemetry() {
  try {
    const res = await fetch('/api/readings/recent?limit=8');
    const data = await res.json();
    if (!data.success) return;

    const tbody = document.getElementById('liveIngestionTableBody');
    if (!data.readings || data.readings.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6" class="text-center py-3 text-secondary">No telemetry records found.</td></tr>';
      return;
    }

    tbody.innerHTML = data.readings.map(r => {
      const timeStr = (r.timestamp || '').split(' ')[1] || r.timestamp;
      const tamperBadge = r.tamper_alert ? '<span class="badge-status badge-tampered ms-1">TAMPER</span>' : '';
      return `
        <tr>
          <td><small class="text-secondary">${timeStr}</small></td>
          <td><strong class="text-white">${r.meter_id}</strong></td>
          <td><span class="text-cyan fw-bold">${r.active_power_kw}</span></td>
          <td><span class="text-white">${r.cumulative_kwh}</span></td>
          <td><span class="text-secondary">${r.voltage_v}V</span></td>
          <td>
            <span class="badge-status badge-active">OK</span>
            ${tamperBadge}
          </td>
        </tr>
      `;
    }).join('');
  } catch (err) {
    console.error('Error loading recent telemetry:', err);
  }
}
