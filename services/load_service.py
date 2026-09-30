from database import query_db
from datetime import datetime, timedelta

class LoadPlanningService:
    @staticmethod
    def get_system_load_curve(feeder_id=None, date_str=None):
        """
        Calculates the 24-hour load curve (active power kW per hour)
        for load planning and peak analysis.
        """
        if not date_str:
            date_str = datetime.now().strftime('%Y-%m-%d')

        start_time = f"{date_str} 00:00:00"
        end_time = f"{date_str} 23:59:59"

        # Check if we have readings for date_str; if not, query the latest available date in database
        check_sql = "SELECT timestamp FROM meter_readings ORDER BY timestamp DESC LIMIT 1"
        latest = query_db(check_sql, one=True)
        if latest and latest.get('timestamp'):
            # Convert timestamp to date
            ts_str = str(latest['timestamp'])
            db_date = ts_str.split(' ')[0]
            if date_str > db_date:
                # Use latest date with available data for a rich view
                date_str = db_date
                start_time = f"{date_str} 00:00:00"
                end_time = f"{date_str} 23:59:59"

        sql = """
            SELECT 
                SUBSTR(r.timestamp, 12, 2) as hour_of_day,
                AVG(r.active_power_kw) as avg_power_kw,
                SUM(r.active_power_kw) as total_load_kw,
                MAX(r.active_power_kw) as peak_load_kw,
                COUNT(r.reading_id) as sample_count
            FROM meter_readings r
            JOIN meters m ON r.meter_id = m.meter_id
            WHERE r.timestamp >= %s AND r.timestamp <= %s
        """
        params = [start_time, end_time]
        if feeder_id and feeder_id != 'ALL':
            sql += " AND m.feeder_id = %s"
            params.append(feeder_id)

        sql += " GROUP BY SUBSTR(r.timestamp, 12, 2) ORDER BY hour_of_day ASC"
        rows = query_db(sql, tuple(params))

        # Fill 24 hours structure (00:00 to 23:00)
        hour_map = {f"{h:02d}": 0.0 for h in range(24)}
        peak_map = {f"{h:02d}": 0.0 for h in range(24)}

        for r in rows:
            hr = str(r['hour_of_day']).zfill(2)
            if hr in hour_map:
                hour_map[hr] = round(float(r['total_load_kw'] or 0.0), 2)
                peak_map[hr] = round(float(r['peak_load_kw'] or 0.0), 2)

        labels = [f"{h:02d}:00" for h in range(24)]
        loads = [hour_map[f"{h:02d}"] for h in range(24)]
        peaks = [peak_map[f"{h:02d}"] for h in range(24)]

        # Calculate metrics
        max_load = max(loads) if loads and max(loads) > 0 else 1.0
        avg_load = sum(loads) / len(loads) if loads else 0.0
        load_factor = round((avg_load / max_load) * 100.0, 2) if max_load > 0 else 0.0

        peak_hour_idx = loads.index(max(loads)) if loads else 0
        peak_hour_str = f"{peak_hour_idx:02d}:00 - {(peak_hour_idx+1)%24:02d}:00"

        return {
            'target_date': date_str,
            'labels': labels,
            'total_load_kw': loads,
            'peak_load_kw': peaks,
            'max_demand_kw': round(max(loads), 2),
            'avg_demand_kw': round(avg_load, 2),
            'load_factor_pct': load_factor,
            'peak_window': peak_hour_str
        }

    @staticmethod
    def get_feeder_capacities():
        """
        Calculates transformer load utilization per Feeder for grid planning.
        Identifies capacity bottleneck and alert status.
        """
        feeders = query_db("SELECT * FROM feeders ORDER BY feeder_id ASC")
        result = []

        for f in feeders:
            feeder_id = f['feeder_id']
            # Get current aggregated load from recent readings
            load_sql = """
                SELECT SUM(r.active_power_kw) as current_load_kw,
                       COUNT(DISTINCT r.meter_id) as reporting_meters
                FROM meter_readings r
                JOIN meters m ON r.meter_id = m.meter_id
                WHERE m.feeder_id = %s
                  AND r.timestamp >= datetime('now', '-2 hour')
            """
            # Use general compatible query
            try:
                load_data = query_db(load_sql, (feeder_id,), one=True)
            except Exception:
                # MySQL equivalent
                mysql_load_sql = """
                    SELECT SUM(r.active_power_kw) as current_load_kw,
                           COUNT(DISTINCT r.meter_id) as reporting_meters
                    FROM meter_readings r
                    JOIN meters m ON r.meter_id = m.meter_id
                    WHERE m.feeder_id = %s
                      AND r.timestamp >= DATE_SUB(NOW(), INTERVAL 2 HOUR)
                """
                load_data = query_db(mysql_load_sql, (feeder_id,), one=True)

            current_load = float(load_data['current_load_kw'] or 0.0) if load_data else 0.0
            # If no recent readings, grab average of latest available hour
            if current_load <= 0.0:
                fallback_sql = """
                    SELECT SUM(r.active_power_kw) as current_load_kw,
                           COUNT(DISTINCT r.meter_id) as reporting_meters
                    FROM meter_readings r
                    JOIN meters m ON r.meter_id = m.meter_id
                    WHERE m.feeder_id = %s
                    GROUP BY r.timestamp
                    ORDER BY r.timestamp DESC LIMIT 1
                """
                fallback_data = query_db(fallback_sql, (feeder_id,), one=True)
                if fallback_data:
                    current_load = float(fallback_data['current_load_kw'] or 0.0)

            rated_cap = float(f['rated_capacity_kw'])
            utilization_pct = round((current_load / rated_cap) * 100.0, 1) if rated_cap > 0 else 0.0

            if utilization_pct >= f['critical_threshold_pct']:
                status = 'CRITICAL'
                status_color = 'danger'
            elif utilization_pct >= f['warning_threshold_pct']:
                status = 'WARNING'
                status_color = 'warning'
            else:
                status = 'OPTIMAL'
                status_color = 'success'

            result.append({
                'feeder_id': feeder_id,
                'substation_name': f['substation_name'],
                'location': f['location'],
                'rated_capacity_kw': rated_cap,
                'current_load_kw': round(current_load, 2),
                'utilization_pct': min(100.0, utilization_pct),
                'status': status,
                'status_color': status_color,
                'reserve_margin_kw': round(max(0.0, rated_cap - current_load), 2)
            })

        return result

    @staticmethod
    def get_category_distribution():
        """Aggregates energy consumption by customer type (Residential vs Commercial vs Industrial)"""
        sql = """
            SELECT c.category, SUM(m.current_cumulative_kwh) as total_kwh, COUNT(m.meter_id) as meter_count
            FROM meters m
            JOIN consumers c ON m.consumer_id = c.consumer_id
            GROUP BY c.category
        """
        rows = query_db(sql)
        categories = []
        kwh_values = []
        meter_counts = []
        for r in rows:
            categories.append(r['category'])
            kwh_values.append(round(float(r['total_kwh'] or 0.0), 2))
            meter_counts.append(r['meter_count'])
        return {
            'labels': categories,
            'kwh': kwh_values,
            'counts': meter_counts
        }
