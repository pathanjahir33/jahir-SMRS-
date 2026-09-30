/**
 * Automated Billing Engine & Invoice Generator
 */

let activeBillIdInModal = null;

document.addEventListener('DOMContentLoaded', function () {
  loadBillingLedger();

  const monthInput = document.getElementById('billingMonthInput');
  const statusFilter = document.getElementById('billingStatusFilter');

  if (monthInput) monthInput.addEventListener('change', loadBillingLedger);
  if (statusFilter) statusFilter.addEventListener('change', loadBillingLedger);

  const btnReload = document.getElementById('btn-reload-bills');
  if (btnReload) btnReload.addEventListener('click', loadBillingLedger);

  const btnGenerate = document.getElementById('btn-generate-all-bills');
  if (btnGenerate) btnGenerate.addEventListener('click', handleGenerateAllBills);

  const btnPay = document.getElementById('btn-pay-invoice');
  if (btnPay) btnPay.addEventListener('click', handleSimulatePayment);
});

async function loadBillingLedger() {
  const month = document.getElementById('billingMonthInput')?.value || '';
  const status = document.getElementById('billingStatusFilter')?.value || 'ALL';

  const params = new URLSearchParams();
  if (month) params.append('month', month);
  if (status !== 'ALL') params.append('status', status);

  try {
    const res = await fetch(`/api/billing?${params.toString()}`);
    const data = await res.json();
    if (!data.success) return;

    const tbody = document.getElementById('billingTableBody');
    const badge = document.getElementById('billsCountBadge');
    if (badge) badge.innerText = `${data.count} Invoices`;

    if (!data.bills || data.bills.length === 0) {
      tbody.innerHTML = '<tr><td colspan="9" class="text-center py-4 text-secondary">No invoices found for this period. Click "Run Automated Invoicing" to generate them.</td></tr>';
      return;
    }

    tbody.innerHTML = data.bills.map(b => {
      let statusBadge = '<span class="badge-status badge-unpaid">Unpaid</span>';
      if (b.payment_status === 'Paid') statusBadge = '<span class="badge-status badge-paid">Paid</span>';
      else if (b.payment_status === 'Overdue') statusBadge = '<span class="badge-status badge-tampered">Overdue</span>';

      return `
        <tr>
          <td><strong class="text-white">${b.bill_id}</strong></td>
          <td>
            <div class="text-white">${b.consumer_name}</div>
            <small class="text-secondary">${b.category}</small>
          </td>
          <td>
            <span class="text-cyan">${b.meter_id}</span>
            <small class="text-secondary d-block">${b.feeder_id}</small>
          </td>
          <td><span class="text-white">${b.billing_month}</span></td>
          <td><span class="text-white fw-bold">${b.total_units_kwh}</span> <small class="text-secondary">kWh</small></td>
          <td><span class="text-warning">${b.peak_units_kwh || 0.0}</span> <small class="text-secondary">kWh</small></td>
          <td><span class="text-cyan fw-bold fs-6">$${parseFloat(b.total_payable).toFixed(2)}</span></td>
          <td>${statusBadge}</td>
          <td class="text-end">
            <button class="btn btn-outline-custom btn-sm" onclick="viewInvoice('${b.bill_id}')">
              <i class="bi bi-file-earmark-text text-cyan me-1"></i>Invoice
            </button>
          </td>
        </tr>
      `;
    }).join('');
  } catch (err) {
    console.error('Error loading bills:', err);
  }
}

async function handleGenerateAllBills() {
  const month = document.getElementById('billingMonthInput')?.value;
  if (!month) {
    window.showToast('Please select a billing cycle month', false);
    return;
  }

  const btn = document.getElementById('btn-generate-all-bills');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Calculating Slabs...';

  try {
    const res = await fetch('/api/billing/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ billing_month: month })
    });
    const data = await res.json();
    if (data.success) {
      window.showToast(`Calculated & generated ${data.count} utility bills for cycle ${month}!`, true);
      loadBillingLedger();
    } else {
      window.showToast(data.error || 'Failed to generate bills', false);
    }
  } catch (err) {
    window.showToast('Error during billing calculation: ' + err.message, false);
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<i class="bi bi-gear-wide-connected me-1"></i>Run Automated Invoicing';
  }
}

window.viewInvoice = async function (billId) {
  activeBillIdInModal = billId;
  try {
    const res = await fetch(`/api/billing/${billId}`);
    const data = await res.json();
    if (!data.success) {
      window.showToast('Could not load invoice ' + billId, false);
      return;
    }

    const b = data.bill;

    // Header Details
    document.getElementById('inv-bill-id').innerText = b.bill_id;
    document.getElementById('inv-billing-month').innerText = b.billing_month;
    document.getElementById('inv-due-date').innerText = b.due_date;

    // Consumer Details
    document.getElementById('inv-consumer-name').innerText = b.consumer_name;
    document.getElementById('inv-consumer-address').innerText = b.consumer_address || 'Registered Grid Address';
    document.getElementById('inv-consumer-contact').innerText = `${b.consumer_phone || ''} | ${b.consumer_email || ''}`;
    document.getElementById('inv-consumer-category').innerText = b.consumer_category || 'Residential';

    // Meter Details
    document.getElementById('inv-meter-id').innerText = b.meter_id;
    document.getElementById('inv-meter-serial').innerText = b.serial_number;
    document.getElementById('inv-feeder-id').innerText = b.feeder_id;
    document.getElementById('inv-tariff-name').innerText = b.tariff_name;

    // Reading Summary
    document.getElementById('inv-start-kwh').innerText = `${b.start_reading_kwh} kWh`;
    document.getElementById('inv-end-kwh').innerText = `${b.end_reading_kwh} kWh`;
    document.getElementById('inv-total-units').innerText = `${b.total_units_kwh} kWh`;
    document.getElementById('inv-peak-units').innerText = `${b.peak_units_kwh} kWh`;

    // Tariff breakdown table
    document.getElementById('inv-base-charge').innerText = `$${parseFloat(b.base_energy_charge).toFixed(2)}`;
    document.getElementById('inv-peak-surcharge').innerText = `$${parseFloat(b.peak_surcharge).toFixed(2)}`;
    document.getElementById('inv-fixed-charge').innerText = `$${parseFloat(b.fixed_charge).toFixed(2)}`;
    document.getElementById('inv-tax-rate').innerText = `${b.tax_percent}%`;
    document.getElementById('inv-tax-amount').innerText = `$${parseFloat(b.tax_amount).toFixed(2)}`;
    document.getElementById('inv-total-payable').innerText = `$${parseFloat(b.total_payable).toFixed(2)}`;

    // Payment badge
    const badge = document.getElementById('inv-payment-badge');
    const btnPay = document.getElementById('btn-pay-invoice');
    const paidTimestamp = document.getElementById('inv-paid-timestamp');

    if (b.payment_status === 'Paid') {
      badge.className = 'badge-status badge-paid';
      badge.innerText = 'Paid in Full';
      paidTimestamp.innerText = b.paid_at ? `Payment settled on: ${b.paid_at}` : 'Settled';
      btnPay.disabled = true;
      btnPay.innerText = 'Settled';
    } else {
      badge.className = 'badge-status badge-unpaid';
      badge.innerText = 'Payment Due';
      paidTimestamp.innerText = `Must be settled by ${b.due_date}`;
      btnPay.disabled = false;
      btnPay.innerHTML = '<i class="bi bi-check-circle me-1"></i>Simulate Payment';
    }

    const modal = new bootstrap.Modal(document.getElementById('invoiceModal'));
    modal.show();
  } catch (err) {
    console.error('Error viewing invoice:', err);
    window.showToast('Error opening invoice modal', false);
  }
};

async function handleSimulatePayment() {
  if (!activeBillIdInModal) return;
  const btn = document.getElementById('btn-pay-invoice');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Processing...';

  try {
    const res = await fetch(`/api/billing/${activeBillIdInModal}/pay`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    });
    const data = await res.json();
    if (data.success) {
      window.showToast(`Invoice ${activeBillIdInModal} paid successfully!`, true);
      const badge = document.getElementById('inv-payment-badge');
      badge.className = 'badge-status badge-paid';
      badge.innerText = 'Paid in Full';
      btn.innerText = 'Settled';
      loadBillingLedger();
    } else {
      window.showToast('Payment failed: ' + data.error, false);
      btn.disabled = false;
    }
  } catch (err) {
    window.showToast('Error processing payment: ' + err.message, false);
    btn.disabled = false;
  }
}
