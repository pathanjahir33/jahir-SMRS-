from database import query_db
from datetime import datetime, timedelta

class BillingService:
    @staticmethod
    def calculate_bill_for_meter(meter_id, billing_month):
        """
        Calculates itemized bill for a smart meter for a given month (YYYY-MM).
        Retrieves starting reading, ending reading, peak units, and computes tiered tariff charges.
        """
        # Fetch meter and tariff details
        meter_sql = """
            SELECT m.*, t.slab1_limit, t.slab1_rate, t.slab2_limit, t.slab2_rate,
                   t.slab3_rate, t.peak_surcharge_rate, t.fixed_charge, t.tax_percent
            FROM meters m
            JOIN tariffs t ON m.tariff_id = t.tariff_id
            WHERE m.meter_id = %s
        """
        meter = query_db(meter_sql, (meter_id,), one=True)
        if not meter:
            return {'error': f"Meter {meter_id} not found."}

        consumer_id = meter['consumer_id']
        year, month = map(int, billing_month.split('-'))
        start_date = f"{year:04d}-{month:02d}-01 00:00:00"
        
        # Calculate next month start for upper boundary
        if month == 12:
            end_date = f"{year+1:04d}-01-01 00:00:00"
            due_date = f"{year+1:04d}-01-20"
        else:
            end_date = f"{year:04d}-{month+1:02d}-01 00:00:00"
            due_date = f"{year:04d}-{month+1:02d}-20"

        # Fetch first and last reading in the cycle
        first_reading_sql = """
            SELECT cumulative_kwh, timestamp FROM meter_readings
            WHERE meter_id = %s AND timestamp >= %s AND timestamp < %s
            ORDER BY timestamp ASC LIMIT 1
        """
        last_reading_sql = """
            SELECT cumulative_kwh, timestamp FROM meter_readings
            WHERE meter_id = %s AND timestamp >= %s AND timestamp < %s
            ORDER BY timestamp DESC LIMIT 1
        """
        r_first = query_db(first_reading_sql, (meter_id, start_date, end_date), one=True)
        r_last = query_db(last_reading_sql, (meter_id, start_date, end_date), one=True)

        if not r_first or not r_last:
            # If no readings in specific date range, check latest available reading
            r_last = query_db("SELECT cumulative_kwh FROM meter_readings WHERE meter_id = %s ORDER BY timestamp DESC LIMIT 1", (meter_id,), one=True)
            if not r_last:
                return {'error': f"No telemetry readings found for meter {meter_id}."}
            start_kwh = max(0.0, r_last['cumulative_kwh'] - 120.0) # Estimated baseline
            end_kwh = r_last['cumulative_kwh']
        else:
            start_kwh = r_first['cumulative_kwh']
            end_kwh = r_last['cumulative_kwh']

        total_units = max(0.0, round(end_kwh - start_kwh, 2))

        # Peak units calculation (readings during peak hours)
        peak_sql = """
            SELECT COUNT(*) as peak_count, AVG(active_power_kw) as avg_peak_kw
            FROM meter_readings
            WHERE meter_id = %s AND timestamp >= %s AND timestamp < %s AND is_peak_hour = 1
        """
        peak_stats = query_db(peak_sql, (meter_id, start_date, end_date), one=True)
        # Approximate peak units (assuming ~1 reading/hr or ratio of peak load)
        if total_units > 0 and peak_stats and peak_stats['peak_count'] and peak_stats['peak_count'] > 0:
            peak_units = round(total_units * 0.28, 2) # approx 28% peak window usage
        else:
            peak_units = round(total_units * 0.25, 2)

        # Tiered Slab Calculation
        slab1_limit = meter['slab1_limit']
        slab1_rate = meter['slab1_rate']
        slab2_limit = meter['slab2_limit']
        slab2_rate = meter['slab2_rate']
        slab3_rate = meter['slab3_rate']

        energy_charge = 0.0
        remaining_units = total_units

        # Tier 1
        u1 = min(remaining_units, slab1_limit)
        energy_charge += u1 * slab1_rate
        remaining_units -= u1

        # Tier 2
        if remaining_units > 0:
            slab2_capacity = slab2_limit - slab1_limit
            u2 = min(remaining_units, slab2_capacity)
            energy_charge += u2 * slab2_rate
            remaining_units -= u2

        # Tier 3 (High consumption)
        if remaining_units > 0:
            energy_charge += remaining_units * slab3_rate

        # Peak surcharge
        peak_surcharge = round(peak_units * meter['peak_surcharge_rate'], 2)
        fixed_charge = round(meter['fixed_charge'], 2)
        subtotal = round(energy_charge + peak_surcharge + fixed_charge, 2)
        tax_amount = round(subtotal * (meter['tax_percent'] / 100.0), 2)
        total_payable = round(subtotal + tax_amount, 2)

        # Unique Bill ID
        bill_id = f"BILL-{billing_month.replace('-', '')}-{meter_id}"

        # Insert or update bill
        upsert_bill_sql = """
            INSERT INTO billing_records
            (bill_id, meter_id, consumer_id, billing_month, start_date, end_date,
             start_reading_kwh, end_reading_kwh, total_units_kwh, peak_units_kwh,
             base_energy_charge, peak_surcharge, fixed_charge, tax_amount, total_payable,
             due_date, payment_status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'Unpaid')
            ON DUPLICATE KEY UPDATE
             end_reading_kwh = VALUES(end_reading_kwh),
             total_units_kwh = VALUES(total_units_kwh),
             base_energy_charge = VALUES(base_energy_charge),
             peak_surcharge = VALUES(peak_surcharge),
             total_payable = VALUES(total_payable)
        """
        # Execute query (compatible with both MySQL and SQLite)
        try:
            query_db(upsert_bill_sql, (
                bill_id, meter_id, consumer_id, billing_month,
                start_date.split(' ')[0], end_date.split(' ')[0],
                start_kwh, end_kwh, total_units, peak_units,
                round(energy_charge, 2), peak_surcharge, fixed_charge, tax_amount, total_payable,
                due_date
            ), commit=True)
        except Exception:
            # Fallback for SQLite upsert
            query_db("DELETE FROM billing_records WHERE bill_id = %s", (bill_id,), commit=True)
            insert_sql = """
                INSERT INTO billing_records
                (bill_id, meter_id, consumer_id, billing_month, start_date, end_date,
                 start_reading_kwh, end_reading_kwh, total_units_kwh, peak_units_kwh,
                 base_energy_charge, peak_surcharge, fixed_charge, tax_amount, total_payable,
                 due_date, payment_status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'Unpaid')
            """
            query_db(insert_sql, (
                bill_id, meter_id, consumer_id, billing_month,
                start_date.split(' ')[0], end_date.split(' ')[0],
                start_kwh, end_kwh, total_units, peak_units,
                round(energy_charge, 2), peak_surcharge, fixed_charge, tax_amount, total_payable,
                due_date
            ), commit=True)

        return {
            'bill_id': bill_id,
            'meter_id': meter_id,
            'consumer_id': consumer_id,
            'billing_month': billing_month,
            'total_units_kwh': total_units,
            'peak_units_kwh': peak_units,
            'base_energy_charge': round(energy_charge, 2),
            'peak_surcharge': peak_surcharge,
            'fixed_charge': fixed_charge,
            'tax_amount': tax_amount,
            'total_payable': total_payable,
            'due_date': due_date
        }

    @staticmethod
    def generate_all_bills(billing_month):
        """Generates billing statements for all active smart meters."""
        meters = query_db("SELECT meter_id FROM meters WHERE status = 'Active'")
        results = []
        for m in meters:
            res = BillingService.calculate_bill_for_meter(m['meter_id'], billing_month)
            results.append(res)
        return results
