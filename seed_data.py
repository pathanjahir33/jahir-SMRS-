from database import init_db, query_db, get_active_engine
from services.simulator_service import SimulatorService
from services.billing_service import BillingService
from datetime import datetime

def seed_database():
    print(f"[Seed] Checking database tables on engine: {get_active_engine().upper()}...")
    init_db()

    # 1. Seed Consumers if empty
    consumers_count = query_db("SELECT COUNT(*) as cnt FROM consumers", one=True)
    if consumers_count and consumers_count['cnt'] == 0:
        print("[Seed] Populating consumers...")
        consumers = [
            ('CONS-1001', 'Alexander Wright', 'alex.wright@email.com', '+1-555-0101', '742 Evergreen Terrace, Sector 4', 'FDR-NORTH-01', 'Residential'),
            ('CONS-1002', 'Elena Rostova', 'elena.r@email.com', '+1-555-0102', '124 Conch Street, Sector 4', 'FDR-NORTH-01', 'Residential'),
            ('CONS-1003', 'Marcus Aurelius Chen', 'marcus.chen@techcorp.io', '+1-555-0103', '404 Silicon Boulevard, Downtown', 'FDR-WEST-04', 'Commercial'),
            ('CONS-1004', 'Sarah Jenkins', 'sarah.j@email.com', '+1-555-0104', '88 Maple Drive, South Bay', 'FDR-SOUTH-02', 'Residential'),
            ('CONS-1005', 'Horizon Cold Storage Ltd', 'facility@horizoncold.com', '+1-555-0105', 'Plot 12, Eastside Industrial Park', 'FDR-EAST-03', 'Industrial'),
            ('CONS-1006', 'Apex Precision Tooling', 'ops@apexprecision.com', '+1-555-0106', 'Plot 45, Eastside Industrial Park', 'FDR-EAST-03', 'Industrial'),
            ('CONS-1007', 'Metro Supermarket #14', 'store14@metrosuper.com', '+1-555-0107', '210 Main Commercial Hub, West', 'FDR-WEST-04', 'Commercial'),
            ('CONS-1008', 'David K. Miller', 'dmiller@home.org', '+1-555-0108', '512 Willow Creek Way, South Bay', 'FDR-SOUTH-02', 'Residential'),
            ('CONS-1009', 'Priya Sharma', 'priya.s@cloudmail.net', '+1-555-0109', '19 Oak Ridge Lane, Sector 4', 'FDR-NORTH-01', 'Residential'),
            ('CONS-1010', 'Grand Central Cinema', 'admin@grandcinema.com', '+1-555-0110', '700 West Promenade, West', 'FDR-WEST-04', 'Commercial'),
        ]
        for c in consumers:
            query_db("""
                INSERT INTO consumers (consumer_id, full_name, email, phone, address, feeder_id, category)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, c, commit=True)

    # 2. Seed Meters if empty
    meters_count = query_db("SELECT COUNT(*) as cnt FROM meters", one=True)
    if meters_count and meters_count['cnt'] == 0:
        print("[Seed] Populating smart meters...")
        meters = [
            ('SM-N-101', 'SN-2024-N001', 'CONS-1001', 'TAR-RES-01', 'FDR-NORTH-01', 'SmartGrid IoT-X3', '2024-01-15', 'Active'),
            ('SM-N-102', 'SN-2024-N002', 'CONS-1002', 'TAR-RES-01', 'FDR-NORTH-01', 'SmartGrid IoT-X3', '2024-01-20', 'Active'),
            ('SM-W-201', 'SN-2024-W001', 'CONS-1003', 'TAR-COM-01', 'FDR-WEST-04', 'Schneider ION7400', '2023-11-10', 'Active'),
            ('SM-S-301', 'SN-2024-S001', 'CONS-1004', 'TAR-RES-01', 'FDR-SOUTH-02', 'SmartGrid IoT-X3', '2024-02-01', 'Active'),
            ('SM-E-401', 'SN-2024-E001', 'CONS-1005', 'TAR-IND-01', 'FDR-EAST-03', 'ABB A44 High-Tension', '2023-08-15', 'Active'),
            ('SM-E-402', 'SN-2024-E002', 'CONS-1006', 'TAR-IND-01', 'FDR-EAST-03', 'ABB A44 High-Tension', '2023-09-01', 'Active'),
            ('SM-W-202', 'SN-2024-W002', 'CONS-1007', 'TAR-COM-01', 'FDR-WEST-04', 'Schneider ION7400', '2023-12-05', 'Active'),
            ('SM-S-302', 'SN-2024-S002', 'CONS-1008', 'TAR-RES-01', 'FDR-SOUTH-02', 'SmartGrid IoT-X3', '2024-03-12', 'Faulty'),
            ('SM-N-103', 'SN-2024-N003', 'CONS-1009', 'TAR-RES-01', 'FDR-NORTH-01', 'SmartGrid IoT-X3', '2024-03-25', 'Tampered'),
            ('SM-W-203', 'SN-2024-W003', 'CONS-1010', 'TAR-COM-01', 'FDR-WEST-04', 'Schneider ION7400', '2024-04-02', 'Active'),
        ]
        for m in meters:
            query_db("""
                INSERT INTO meters (meter_id, serial_number, consumer_id, tariff_id, feeder_id, model, installation_date, status, current_cumulative_kwh)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 0.0)
            """, m, commit=True)

    # 3. Seed historical readings
    readings_count = query_db("SELECT COUNT(*) as cnt FROM meter_readings", one=True)
    if not readings_count or readings_count['cnt'] < 50:
        print("[Seed] Populating 5 days of telemetry readings...")
        SimulatorService.seed_historical_telemetry(days=5)

    # 4. Seed system alerts
    alerts_count = query_db("SELECT COUNT(*) as cnt FROM system_alerts", one=True)
    if alerts_count and alerts_count['cnt'] == 0:
        print("[Seed] Populating initial system alerts...")
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        alerts = [
            ('SM-N-103', 'FDR-NORTH-01', 'TAMPERING', 'CRITICAL', 'Terminal cover breach detected. Reverse energy flow logged.', 0, now),
            ('SM-S-302', 'FDR-SOUTH-02', 'FAULTY', 'WARNING', 'Zero consumption reported for 48 consecutive hours. Potential CT failure.', 0, now),
            (None, 'FDR-EAST-03', 'OVERLOAD', 'WARNING', 'Peak feeder demand reached 88.5% of rated capacity (1062 kW / 1200 kW).', 0, now),
        ]
        for a in alerts:
            query_db("""
                INSERT INTO system_alerts (meter_id, feeder_id, alert_type, severity, message, is_resolved, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, a, commit=True)

    # 5. Seed sample billing records for previous month
    bills_count = query_db("SELECT COUNT(*) as cnt FROM billing_records", one=True)
    if bills_count and bills_count['cnt'] == 0:
        print("[Seed] Generating baseline billing records for current cycle...")
        current_month = datetime.now().strftime('%Y-%m')
        BillingService.generate_all_bills(current_month)

    print("[Seed] Database seeding completed successfully!")

if __name__ == '__main__':
    seed_database()
