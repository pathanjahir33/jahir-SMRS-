from database import query_db
from datetime import datetime

class MeterModel:
    @staticmethod
    def get_all(search=None, status=None, feeder_id=None):
        sql = """
            SELECT m.*, c.full_name as consumer_name, c.category as consumer_category,
                   f.substation_name, t.name as tariff_name
            FROM meters m
            LEFT JOIN consumers c ON m.consumer_id = c.consumer_id
            LEFT JOIN feeders f ON m.feeder_id = f.feeder_id
            LEFT JOIN tariffs t ON m.tariff_id = t.tariff_id
            WHERE 1=1
        """
        params = []
        if search:
            sql += " AND (m.meter_id LIKE %s OR m.serial_number LIKE %s OR c.full_name LIKE %s)"
            pattern = f"%{search}%"
            params.extend([pattern, pattern, pattern])
        if status and status != 'ALL':
            sql += " AND m.status = %s"
            params.append(status)
        if feeder_id and feeder_id != 'ALL':
            sql += " AND m.feeder_id = %s"
            params.append(feeder_id)
        sql += " ORDER BY m.meter_id ASC"
        return query_db(sql, tuple(params))

    @staticmethod
    def get_by_id(meter_id):
        sql = """
            SELECT m.*, c.full_name as consumer_name, c.email as consumer_email,
                   c.phone as consumer_phone, c.address as consumer_address,
                   c.category as consumer_category, f.substation_name, f.rated_capacity_kw,
                   t.name as tariff_name, t.slab1_limit, t.slab1_rate, t.slab2_limit,
                   t.slab2_rate, t.slab3_rate, t.peak_surcharge_rate, t.fixed_charge, t.tax_percent
            FROM meters m
            LEFT JOIN consumers c ON m.consumer_id = c.consumer_id
            LEFT JOIN feeders f ON m.feeder_id = f.feeder_id
            LEFT JOIN tariffs t ON m.tariff_id = t.tariff_id
            WHERE m.meter_id = %s
        """
        return query_db(sql, (meter_id,), one=True)

    @staticmethod
    def create(meter_id, serial_number, consumer_id, tariff_id, feeder_id, model='SmartGrid IoT-X3'):
        sql = """
            INSERT INTO meters (meter_id, serial_number, consumer_id, tariff_id, feeder_id, model, installation_date, status, current_cumulative_kwh)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'Active', 0.0)
        """
        today = datetime.now().strftime('%Y-%m-%d')
        return query_db(sql, (meter_id, serial_number, consumer_id, tariff_id, feeder_id, model, today), commit=True)

    @staticmethod
    def update_status(meter_id, status):
        sql = "UPDATE meters SET status = %s WHERE meter_id = %s"
        return query_db(sql, (status, meter_id), commit=True)

    @staticmethod
    def count_summary():
        sql = """
            SELECT 
                COUNT(*) as total_meters,
                SUM(CASE WHEN status = 'Active' THEN 1 ELSE 0 END) as active_meters,
                SUM(CASE WHEN status = 'Faulty' THEN 1 ELSE 0 END) as faulty_meters,
                SUM(CASE WHEN status = 'Tampered' THEN 1 ELSE 0 END) as tampered_meters,
                SUM(CASE WHEN status = 'Suspended' THEN 1 ELSE 0 END) as suspended_meters
            FROM meters
        """
        return query_db(sql, one=True)


class ReadingModel:
    @staticmethod
    def record_reading(meter_id, timestamp, cumulative_kwh, active_power_kw, reactive_power_kvar=0.0,
                       voltage_v=230.0, current_a=0.0, power_factor=0.95, frequency_hz=50.0,
                       is_peak_hour=0, tamper_alert=0, ingestion_mode='REST_API'):
        sql = """
            INSERT INTO meter_readings 
            (meter_id, timestamp, cumulative_kwh, active_power_kw, reactive_power_kvar,
             voltage_v, current_a, power_factor, frequency_hz, is_peak_hour, tamper_alert, ingestion_mode)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        res = query_db(sql, (
            meter_id, timestamp, cumulative_kwh, active_power_kw, reactive_power_kvar,
            voltage_v, current_a, power_factor, frequency_hz, is_peak_hour, tamper_alert, ingestion_mode
        ), commit=True)

        # Update current cumulative kWh on meter record
        update_meter_sql = """
            UPDATE meters 
            SET current_cumulative_kwh = %s, last_reading_time = %s 
            WHERE meter_id = %s
        """
        query_db(update_meter_sql, (cumulative_kwh, timestamp, meter_id), commit=True)
        return res

    @staticmethod
    def get_recent(limit=50, meter_id=None):
        sql = """
            SELECT r.*, m.serial_number, c.full_name as consumer_name, m.feeder_id
            FROM meter_readings r
            JOIN meters m ON r.meter_id = m.meter_id
            LEFT JOIN consumers c ON m.consumer_id = c.consumer_id
            WHERE 1=1
        """
        params = []
        if meter_id:
            sql += " AND r.meter_id = %s"
            params.append(meter_id)
        sql += " ORDER BY r.timestamp DESC, r.reading_id DESC LIMIT %s"
        params.append(limit)
        return query_db(sql, tuple(params))

    @staticmethod
    def get_history_for_meter(meter_id, limit=48):
        sql = """
            SELECT * FROM meter_readings
            WHERE meter_id = %s
            ORDER BY timestamp DESC
            LIMIT %s
        """
        rows = query_db(sql, (meter_id, limit))
        # Return in ascending order for chart plotting
        return list(reversed(rows)) if rows else []


class ConsumerModel:
    @staticmethod
    def get_all():
        sql = """
            SELECT c.*, f.substation_name, COUNT(m.meter_id) as meter_count
            FROM consumers c
            LEFT JOIN feeders f ON c.feeder_id = f.feeder_id
            LEFT JOIN meters m ON c.consumer_id = m.consumer_id
            GROUP BY c.consumer_id
            ORDER BY c.consumer_id ASC
        """
        return query_db(sql)

    @staticmethod
    def create(consumer_id, full_name, email, phone, address, feeder_id, category):
        sql = """
            INSERT INTO consumers (consumer_id, full_name, email, phone, address, feeder_id, category)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        return query_db(sql, (consumer_id, full_name, email, phone, address, feeder_id, category), commit=True)


class FeederModel:
    @staticmethod
    def get_all():
        sql = "SELECT * FROM feeders ORDER BY feeder_id ASC"
        return query_db(sql)


class TariffModel:
    @staticmethod
    def get_all():
        sql = "SELECT * FROM tariffs ORDER BY tariff_id ASC"
        return query_db(sql)


class BillingModel:
    @staticmethod
    def get_all(month=None, status=None):
        sql = """
            SELECT b.*, c.full_name as consumer_name, c.category, m.feeder_id
            FROM billing_records b
            JOIN consumers c ON b.consumer_id = c.consumer_id
            JOIN meters m ON b.meter_id = m.meter_id
            WHERE 1=1
        """
        params = []
        if month:
            sql += " AND b.billing_month = %s"
            params.append(month)
        if status and status != 'ALL':
            sql += " AND b.payment_status = %s"
            params.append(status)
        sql += " ORDER BY b.created_at DESC"
        return query_db(sql, tuple(params))

    @staticmethod
    def get_by_id(bill_id):
        sql = """
            SELECT b.*, c.full_name as consumer_name, c.email as consumer_email,
                   c.phone as consumer_phone, c.address as consumer_address,
                   c.category as consumer_category, m.serial_number, m.feeder_id,
                   t.name as tariff_name, t.slab1_limit, t.slab1_rate, t.slab2_limit,
                   t.slab2_rate, t.slab3_rate, t.peak_surcharge_rate, t.tax_percent
            FROM billing_records b
            JOIN consumers c ON b.consumer_id = c.consumer_id
            JOIN meters m ON b.meter_id = m.meter_id
            JOIN tariffs t ON m.tariff_id = t.tariff_id
            WHERE b.bill_id = %s
        """
        return query_db(sql, (bill_id,), one=True)

    @staticmethod
    def mark_paid(bill_id):
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        sql = "UPDATE billing_records SET payment_status = 'Paid', paid_at = %s WHERE bill_id = %s"
        return query_db(sql, (now, bill_id), commit=True)


class AlertModel:
    @staticmethod
    def get_recent(limit=10, unresolved_only=True):
        sql = "SELECT * FROM system_alerts WHERE 1=1"
        params = []
        if unresolved_only:
            sql += " AND is_resolved = 0"
        sql += " ORDER BY created_at DESC LIMIT %s"
        params.append(limit)
        return query_db(sql, tuple(params))

    @staticmethod
    def create(meter_id, feeder_id, alert_type, severity, message):
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        sql = """
            INSERT INTO system_alerts (meter_id, feeder_id, alert_type, severity, message, is_resolved, created_at)
            VALUES (%s, %s, %s, %s, %s, 0, %s)
        """
        return query_db(sql, (meter_id, feeder_id, alert_type, severity, message, now), commit=True)

    @staticmethod
    def resolve(alert_id):
        sql = "UPDATE system_alerts SET is_resolved = 1 WHERE alert_id = %s"
        return query_db(sql, (alert_id,), commit=True)
