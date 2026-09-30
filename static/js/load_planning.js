/**
 * Grid Load Planning & Substation Forecasting
 */

let planningChart = null;
let feederBarChart = null;

document.addEventListener('DOMContentLoaded', function () {
  initLoadPlanning();

  const feederSelect = document.getElementById('planningFeederSelect');
  if (feederSelect) {
    feederSelect.addEventListener('change', () => loadPlanningCurve(feederSelect.value));
  }
});

async function initLoadPlanning() {
  await Promise.all([
    loadPlanningCurve('ALL'),
    loadFeederMatrix()
  ]);
}

async function loadPlanningCurve(feederId = 'ALL') {
  try {
    const url = `/api/analytics/load-curve${feederId && feederId !== 'ALL' ? '?feeder_id=' + feederId : ''}`;
    const res = await fetch(url);
    const data = await res.json();
    if (!data.success) return;

    const c = data.curve;

    // Fill KPI Metrics
    document.getElementById('plan-max-demand').innerText = `${c.max_demand_kw} kW`;
    document.getElementById('plan-avg-demand').innerText = `${c.avg_demand_kw} kW`;
    document.getElementById('plan-load-factor').innerText = `${c.load_factor_pct}%`;
    document.getElementById('plan-peak-window').innerText = c.peak_window;

    const ctx = document.getElementById('planningLoadCurveChart').getContext('2d');

    const grad = ctx.createLinearGradient(0, 0, 0, 300);
    grad.addColorStop(0, 'rgba(6, 182, 212, 0.45)');
    grad.addColorStop(1, 'rgba(6, 182, 212, 0.02)');

    if (planningChart) {
      planningChart.data.labels = c.labels;
      planningChart.data.datasets[0].data = c.total_load_kw;
      planningChart.data.datasets[1].data = c.peak_load_kw;
      planningChart.update();
    } else {
      planningChart = new Chart(ctx, {
        type: 'line',
        data: {
          labels: c.labels,
          datasets: [
            {
              label: 'Hourly Grid Demand (kW)',
              data: c.total_load_kw,
              borderColor: '#06b6d4',
              backgroundColor: grad,
              fill: true,
              tension: 0.35,
              borderWidth: 2.5,
              pointBackgroundColor: '#06b6d4',
              pointBorderColor: '#fff',
              pointRadius: 3
            },
            {
              label: 'Peak Hour Spike Limit (kW)',
              data: c.peak_load_kw,
              borderColor: '#f59e0b',
              borderDash: [6, 4],
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
          plugins: {
            legend: { labels: { color: '#9ca3af', font: { size: 12 } } },
            tooltip: {
              backgroundColor: '#111827',
              borderColor: 'rgba(255,255,255,0.1)',
              borderWidth: 1,
              padding: 10
            }
          },
          scales: {
            x: {
              grid: { color: 'rgba(255,255,255,0.05)' },
              ticks: { color: '#9ca3af', font: { size: 10 } }
            },
            y: {
              grid: { color: 'rgba(255,255,255,0.05)' },
              ticks: { color: '#9ca3af', callback: v => v + ' kW' }
            }
          }
        }
      });
    }
  } catch (err) {
    console.error('Error loading planning curve:', err);
  }
}

async function loadFeederMatrix() {
  try {
    const res = await fetch('/api/analytics/feeder-capacities');
    const data = await res.json();
    if (!data.success) return;

    const feeders = data.feeders;
    const container = document.getElementById('feederCardsGrid');
    document.getElementById('plan-total-feeders').innerText = `${feeders.length} Units`;

    // Render Feeder Cards
    container.innerHTML = feeders.map(f => {
      let badgeClass = 'badge-active';
      if (f.status === 'WARNING') badgeClass = 'badge-faulty';
      else if (f.status === 'CRITICAL') badgeClass = 'badge-tampered';

      const barBg = f.status === 'CRITICAL' ? 'bg-danger' : (f.status === 'WARNING' ? 'bg-warning' : 'bg-info');

      return `
        <div class="col-md-6">
          <div class="p-3 rounded bg-dark border border-secondary border-opacity-25 h-100">
            <div class="d-flex justify-content-between align-items-start mb-2">
              <div>
                <h6 class="text-white fw-bold mb-0">${f.feeder_id}</h6>
                <small class="text-secondary">${f.substation_name}</small>
              </div>
              <span class="badge-status ${badgeClass}">${f.status}</span>
            </div>

            <div class="d-flex justify-content-between align-items-center mb-1 small">
              <span class="text-secondary">Current Load: <strong class="text-white">${f.current_load_kw} kW</strong></span>
              <span class="text-secondary">Rated: <strong class="text-white">${f.rated_capacity_kw} kW</strong></span>
            </div>

            <div class="progress mb-2" style="height: 8px; background-color: rgba(255,255,255,0.08);">
              <div class="progress-bar ${barBg}" role="progressbar" style="width: ${f.utilization_pct}%;"></div>
            </div>

            <div class="d-flex justify-content-between align-items-center small text-secondary">
              <span>Utilization: <strong class="text-cyan">${f.utilization_pct}%</strong></span>
              <span>Reserve Margin: <strong class="text-emerald">${f.reserve_margin_kw} kW</strong></span>
            </div>
          </div>
        </div>
      `;
    }).join('');

    // Render Feeder Bar Chart (Current vs Rated)
    renderFeederBarChart(feeders);
  } catch (err) {
    console.error('Error loading feeder matrix:', err);
  }
}

function renderFeederBarChart(feeders) {
  const ctx = document.getElementById('feederBarChart').getContext('2d');
  const labels = feeders.map(f => f.feeder_id.replace('FDR-', ''));
  const currentLoads = feeders.map(f => f.current_load_kw);
  const ratedCaps = feeders.map(f => f.rated_capacity_kw);

  if (feederBarChart) {
    feederBarChart.data.labels = labels;
    feederBarChart.data.datasets[0].data = currentLoads;
    feederBarChart.data.datasets[1].data = ratedCaps;
    feederBarChart.update();
  } else {
    feederBarChart = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [
          {
            label: 'Current Demand (kW)',
            data: currentLoads,
            backgroundColor: '#06b6d4',
            borderRadius: 6
          },
          {
            label: 'Rated Limit (kW)',
            data: ratedCaps,
            backgroundColor: 'rgba(255, 255, 255, 0.1)',
            borderRadius: 6
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { labels: { color: '#9ca3af', font: { size: 11 } } },
          tooltip: {
            backgroundColor: '#111827',
            borderColor: 'rgba(255,255,255,0.1)',
            borderWidth: 1
          }
        },
        scales: {
          x: {
            grid: { color: 'rgba(255,255,255,0.05)' },
            ticks: { color: '#9ca3af' }
          },
          y: {
            grid: { color: 'rgba(255,255,255,0.05)' },
            ticks: { color: '#9ca3af', callback: v => v + ' kW' }
          }
        }
      }
    });
  }
}
