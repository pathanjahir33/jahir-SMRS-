import random
import math
from datetime import datetime, timedelta
from database import query_db
from models import ReadingModel, MeterModel, AlertModel
from config import Config

class SimulatorService:
    @staticmethod
    def _get_time_of_day_load_factor(hour, category='Residential'):
        """Generates realistic multiplier based on standard utility load curves."""
        if category == 'Residential':
            # Morning peak 7-9am, evening peak 18-22
            if 0 <= hour <= 5:
                return random.uniform(0.15, 0.35)
            elif 6 <= hour <= 9:
                return random.uniform(0.70, 0.95)
            elif 10 <= hour <= 16:
                return random.uniform(0.35, 0.55)
            elif 17 <= hour <= 22:
                return random.uniform(0.85, 1.25) # Peak load
            else:
                return random.uniform(0.40, 0.60)
        elif category == 'Commercial':
            # Business hours 9am to 6pm
            if 9 <= hour <= 18:
                return random.uniform(0.80, 1.20)
            elif 19 <= hour <= 22:
                return random.uniform(0.40, 0.60)
            else:
                return random.uniform(0.15, 0.30)
        else: # Industrial
            # High steady continuous load, slightly lower at night
            if 6 <= hour <= 20:
                return random.uniform(0.85, 1.15)
            else:
                return random.uniform(0.60, 0.85)

    @staticmethod
    def _base_kw_for_category(category):
        if category == 'Residential':
            return random.uniform(2.5, 4.5)  # 2.5 - 4.5 kW max connected load
        elif category == 'Commercial':
            return random.uniform(15.0, 35.0) # 15 - 35 kW
        else: # Industrial
            return random.uniform(80.0, 180.0) # 80 - 180 kW

    @staticmethod
    def simulate_single_tick(meter_id=None):
        """Generates a real-time reading for either a specific meter or all active meters."""
        now = datetime.now()
        timestamp_str = now.strftime('%Y-%m-%d %H:%M:%S')
        is_peak = 1 if (Config.PEAK_HOURS_START <= now.hour <= Config.PEAK_HOURS_END) else 0

        sql = """
            SELECT m.meter_id, m.status, m.current_cumulative_kwh, m.feeder_id, c.category
            FROM meters m
            LEFT JOIN consumers c ON m.consumer_id = c.consumer_id
            WHERE m.status != 'Suspended'
        """
        params = []
        if meter_id:
            sql += " AND m.meter_id = %s"
            params.append(meter_id)

        meters = query_db(sql, tuple(params))
        generated_readings = []

        for m in meters:
            mid = m['meter_id']
            cat = m['category'] or 'Residential'
            base_kw = SimulatorService._base_kw_for_category(cat)
            multiplier = SimulatorService._get_time_of_day_load_factor(now.hour, cat)
            active_kw = round(base_kw * multiplier, 2)

            # Faulty or tampered meters behavior
            tamper_flag = 1 if m['status'] == 'Tampered' else 0
            if m['status'] == 'Faulty':
                active_kw = 0.0
                voltage = random.choice([0.0, 180.0])
                current_a = 0.0
                pf = 0.50
            else:
                # Normal grid conditions: 228V - 238V nominal
                # Rare 2% chance of voltage dip anomaly
                if random.random() < 0.02:
                    voltage = round(random.uniform(195.0, 205.0), 1)
                    AlertModel.create(mid, m['feeder_id'], 'VOLTAGE_DROP', 'WARNING',
                                      f"Voltage drop detected on {mid}: {voltage}V")
                else:
                    voltage = round(random.uniform(227.0, 235.0), 1)

                pf = round(random.uniform(0.92, 0.99), 2)
                # Current (A) = (kW * 1000) / (Voltage * PF)
                current_a = round((active_kw * 1000.0) / max(1.0, (voltage * pf)), 2)
                reactive_kvar = round(active_kw * math.tan(math.acos(min(1.0, pf))), 2)

            # Cumulative increment (approx 1 hour fraction or 0.1 kWh)
            kwh_increment = round(active_kw * 0.25, 3) # for 15-min interval
            new_cumulative = round(float(m['current_cumulative_kwh'] or 0.0) + kwh_increment, 2)

            ReadingModel.record_reading(
                meter_id=mid,
                timestamp=timestamp_str,
                cumulative_kwh=new_cumulative,
                active_power_kw=active_kw,
                reactive_power_kvar=reactive_kvar if m['status'] != 'Faulty' else 0.0,
                voltage_v=voltage,
                current_a=current_a,
                power_factor=pf,
                frequency_hz=round(random.uniform(49.85, 50.15), 2),
                is_peak_hour=is_peak,
                tamper_alert=tamper_flag,
                ingestion_mode='SIMULATED'
            )

            generated_readings.append({
                'meter_id': mid,
                'timestamp': timestamp_str,
                'active_power_kw': active_kw,
                'cumulative_kwh': new_cumulative,
                'voltage_v': voltage,
                'current_a': current_a,
                'power_factor': pf
            })

        return generated_readings

    @staticmethod
    def seed_historical_telemetry(days=7):
        """Populates realistic historical telemetry for the past N days so charts look amazing."""
        meters = query_db("""
            SELECT m.meter_id, m.status, c.category, m.feeder_id
            FROM meters m
            LEFT JOIN consumers c ON m.consumer_id = c.consumer_id
        """)
        if not meters:
            return 0

        # Check if we already have sufficient readings
        count = query_db("SELECT COUNT(*) as cnt FROM meter_readings", one=True)
        if count and count['cnt'] >= 100:
            return count['cnt']

        print(f"[Simulator] Seeding {days} days of historical telemetry...")
        start_time = datetime.now() - timedelta(days=days)
        total_seeded = 0

        # We step in 2-hour increments over past days
        current_time = start_time
        end_time = datetime.now()

        # Cumulative trackers per meter
        cumulative_map = {m['meter_id']: random.uniform(250.0, 1500.0) for m in meters}

        while current_time <= end_time:
            hour = current_time.hour
            is_peak = 1 if (Config.PEAK_HOURS_START <= hour <= Config.PEAK_HOURS_END) else 0
            ts_str = current_time.strftime('%Y-%m-%d %H:%M:%S')

            for m in meters:
                mid = m['meter_id']
                cat = m['category'] or 'Residential'
                base_kw = SimulatorService._base_kw_for_category(cat)
                mult = SimulatorService._get_time_of_day_load_factor(hour, cat)
                active_kw = round(base_kw * mult, 2)
                voltage = round(random.uniform(227.0, 234.0), 1)
                pf = round(random.uniform(0.93, 0.99), 2)
                current_a = round((active_kw * 1000.0) / max(1.0, (voltage * pf)), 2)
                reactive_kvar = round(active_kw * 0.25, 2)

                # Step energy: kW * 2 hours
                kwh_gain = round(active_kw * 2.0, 2)
                cumulative_map[mid] += kwh_gain

                ReadingModel.record_reading(
                    meter_id=mid,
                    timestamp=ts_str,
                    cumulative_kwh=round(cumulative_map[mid], 2),
                    active_power_kw=active_kw,
                    reactive_power_kvar=reactive_kvar,
                    voltage_v=voltage,
                    current_a=current_a,
                    power_factor=pf,
                    frequency_hz=50.0,
                    is_peak_hour=is_peak,
                    tamper_alert=0,
                    ingestion_mode='SIMULATED'
                )
                total_seeded += 1

            current_time += timedelta(hours=2)

        return total_seeded
