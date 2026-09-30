import sqlite3
import re
from datetime import datetime
from config import Config

# Check if mysql.connector is available
MYSQL_AVAILABLE = False
try:
    import mysql.connector
    from mysql.connector import Error as MySQLError
    MYSQL_AVAILABLE = True
except ImportError:
    MYSQL_AVAILABLE = False

_active_engine = None

def get_active_engine():
    global _active_engine
    if _active_engine is not None:
        return _active_engine

    if Config.DB_ENGINE == 'sqlite':
        _active_engine = 'sqlite'
        return _active_engine

    if MYSQL_AVAILABLE and Config.DB_ENGINE in ('mysql', 'auto'):
        try:
            conn = mysql.connector.connect(
                host=Config.MYSQL_HOST,
                port=Config.MYSQL_PORT,
                user=Config.MYSQL_USER,
                password=Config.MYSQL_PASSWORD,
                database=Config.MYSQL_DB,
                connect_timeout=2
            )
            if conn.is_connected():
                conn.close()
                _active_engine = 'mysql'
                return _active_engine
        except Exception:
            pass

    _active_engine = 'sqlite'
    return _active_engine

def get_connection():
    engine = get_active_engine()
    if engine == 'mysql':
        return mysql.connector.connect(
            host=Config.MYSQL_HOST,
            port=Config.MYSQL_PORT,
            user=Config.MYSQL_USER,
            password=Config.MYSQL_PASSWORD,
            database=Config.MYSQL_DB,
            autocommit=True
        )
    else:
        conn = sqlite3.connect(Config.SQLITE_DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

def query_db(query, args=(), one=False, commit=False):
    """
    Unified database query executor supporting both MySQL and SQLite.
    Automatically translates '%s' placeholders to '?' when using SQLite.
    """
    engine = get_active_engine()
    conn = get_connection()
    cursor = None
    try:
        if engine == 'mysql':
            cursor = conn.cursor(dictionary=True)
            cursor.execute(query, args)
            if commit:
                conn.commit()
                last_id = cursor.lastrowid
                row_count = cursor.rowcount
                cursor.close()
                conn.close()
                return {'lastrowid': last_id, 'rowcount': row_count}
            
            rv = cursor.fetchall()
            cursor.close()
            conn.close()
            return (rv[0] if rv else None) if one else rv
        else:
            # SQLite mode: convert %s placeholders to ?
            # Ensure literal percent signs (like LIKE '%foo%') are preserved
            sqlite_query = re.sub(r'(?<!%)%s', '?', query)
            cursor = conn.cursor()
            cursor.execute(sqlite_query, args)
            if commit:
                conn.commit()
                last_id = cursor.lastrowid
                row_count = cursor.rowcount
                cursor.close()
                conn.close()
                return {'lastrowid': last_id, 'rowcount': row_count}
            
            rv = cursor.fetchall()
            # Convert sqlite3.Row to dict
            dict_rv = [dict(row) for row in rv]
            cursor.close()
            conn.close()
            return (dict_rv[0] if dict_rv else None) if one else dict_rv
    except Exception as e:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
        raise e

def init_db():
    """Initializes tables for SQLite if running SQLite, or ensures MySQL schema exists."""
    engine = get_active_engine()
    if engine == 'sqlite':
        init_sqlite_schema()
    print(f"[SMRS Database] Initialized successfully using: {engine.upper()}")

def init_sqlite_schema():
    conn = sqlite3.connect(Config.SQLITE_DB_PATH)
    cur = conn.cursor()

    # Create tables compatible with SQLite
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS tariffs (
        tariff_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        customer_type TEXT NOT NULL,
        slab1_limit REAL NOT NULL DEFAULT 100.0,
        slab1_rate REAL NOT NULL DEFAULT 0.10,
        slab2_limit REAL NOT NULL DEFAULT 300.0,
        slab2_rate REAL NOT NULL DEFAULT 0.16,
        slab3_rate REAL NOT NULL DEFAULT 0.24,
        peak_surcharge_rate REAL NOT NULL DEFAULT 0.06,
        fixed_charge REAL NOT NULL DEFAULT 12.00,
        tax_percent REAL NOT NULL DEFAULT 5.0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS feeders (
        feeder_id TEXT PRIMARY KEY,
        substation_name TEXT NOT NULL,
        location TEXT NOT NULL,
        rated_capacity_kw REAL NOT NULL,
        warning_threshold_pct REAL NOT NULL DEFAULT 80.0,
        critical_threshold_pct REAL NOT NULL DEFAULT 95.0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS consumers (
        consumer_id TEXT PRIMARY KEY,
        full_name TEXT NOT NULL,
        email TEXT,
        phone TEXT,
        address TEXT,
        feeder_id TEXT,
        category TEXT NOT NULL DEFAULT 'Residential',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (feeder_id) REFERENCES feeders(feeder_id)
    );

    CREATE TABLE IF NOT EXISTS meters (
        meter_id TEXT PRIMARY KEY,
        serial_number TEXT NOT NULL UNIQUE,
        consumer_id TEXT,
        tariff_id TEXT NOT NULL,
        feeder_id TEXT NOT NULL,
        model TEXT NOT NULL DEFAULT 'SmartGrid IoT-X3',
        installation_date DATE,
        status TEXT NOT NULL DEFAULT 'Active',
        current_cumulative_kwh REAL NOT NULL DEFAULT 0.0,
        last_reading_time TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (consumer_id) REFERENCES consumers(consumer_id),
        FOREIGN KEY (tariff_id) REFERENCES tariffs(tariff_id),
        FOREIGN KEY (feeder_id) REFERENCES feeders(feeder_id)
    );

    CREATE TABLE IF NOT EXISTS meter_readings (
        reading_id INTEGER PRIMARY KEY AUTOINCREMENT,
        meter_id TEXT NOT NULL,
        timestamp TIMESTAMP NOT NULL,
        cumulative_kwh REAL NOT NULL,
        active_power_kw REAL NOT NULL,
        reactive_power_kvar REAL NOT NULL DEFAULT 0.0,
        voltage_v REAL NOT NULL DEFAULT 230.0,
        current_a REAL NOT NULL DEFAULT 0.0,
        power_factor REAL NOT NULL DEFAULT 0.95,
        frequency_hz REAL NOT NULL DEFAULT 50.0,
        is_peak_hour INTEGER NOT NULL DEFAULT 0,
        tamper_alert INTEGER NOT NULL DEFAULT 0,
        ingestion_mode TEXT NOT NULL DEFAULT 'REST_API',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (meter_id) REFERENCES meters(meter_id)
    );

    CREATE INDEX IF NOT EXISTS idx_meter_timestamp ON meter_readings(meter_id, timestamp);
    CREATE INDEX IF NOT EXISTS idx_timestamp ON meter_readings(timestamp);

    CREATE TABLE IF NOT EXISTS billing_records (
        bill_id TEXT PRIMARY KEY,
        meter_id TEXT NOT NULL,
        consumer_id TEXT NOT NULL,
        billing_month TEXT NOT NULL,
        start_date DATE NOT NULL,
        end_date DATE NOT NULL,
        start_reading_kwh REAL NOT NULL,
        end_reading_kwh REAL NOT NULL,
        total_units_kwh REAL NOT NULL,
        peak_units_kwh REAL NOT NULL DEFAULT 0.0,
        base_energy_charge REAL NOT NULL,
        peak_surcharge REAL NOT NULL DEFAULT 0.0,
        fixed_charge REAL NOT NULL,
        tax_amount REAL NOT NULL,
        total_payable REAL NOT NULL,
        due_date DATE NOT NULL,
        payment_status TEXT NOT NULL DEFAULT 'Unpaid',
        paid_at TIMESTAMP NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (meter_id) REFERENCES meters(meter_id),
        FOREIGN KEY (consumer_id) REFERENCES consumers(consumer_id)
    );

    CREATE TABLE IF NOT EXISTS system_alerts (
        alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
        meter_id TEXT NULL,
        feeder_id TEXT NULL,
        alert_type TEXT NOT NULL,
        severity TEXT NOT NULL DEFAULT 'WARNING',
        message TEXT NOT NULL,
        is_resolved INTEGER NOT NULL DEFAULT 0,
        created_at TIMESTAMP NOT NULL,
        FOREIGN KEY (meter_id) REFERENCES meters(meter_id),
        FOREIGN KEY (feeder_id) REFERENCES feeders(feeder_id)
    );
    """)

    # Seed baseline tariffs and feeders if not present
    cur.execute("SELECT COUNT(*) FROM tariffs")
    if cur.fetchone()[0] == 0:
        cur.executemany("""
        INSERT INTO tariffs (tariff_id, name, customer_type, slab1_limit, slab1_rate, slab2_limit, slab2_rate, slab3_rate, peak_surcharge_rate, fixed_charge, tax_percent)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            ('TAR-RES-01', 'Standard Residential Tiered', 'Residential', 100.0, 0.09, 300.0, 0.14, 0.22, 0.05, 8.50, 5.0),
            ('TAR-COM-01', 'Commercial General Tariff', 'Commercial', 300.0, 0.15, 800.0, 0.22, 0.30, 0.08, 25.00, 7.5),
            ('TAR-IND-01', 'Industrial High-Tension (HT)', 'Industrial', 1000.0, 0.18, 3000.0, 0.25, 0.34, 0.10, 75.00, 10.0)
        ])

    cur.execute("SELECT COUNT(*) FROM feeders")
    if cur.fetchone()[0] == 0:
        cur.executemany("""
        INSERT INTO feeders (feeder_id, substation_name, location, rated_capacity_kw, warning_threshold_pct, critical_threshold_pct)
        VALUES (?, ?, ?, ?, ?, ?)
        """, [
            ('FDR-NORTH-01', 'North City Substation', 'Sector 4, North Zone', 450.0, 80.0, 95.0),
            ('FDR-SOUTH-02', 'South City Substation', 'District 9, South Bay', 600.0, 80.0, 95.0),
            ('FDR-EAST-03',  'Eastside Industrial Park', 'Industrial Area, East', 1200.0, 80.0, 95.0),
            ('FDR-WEST-04',  'West End Commercial Hub', 'Downtown Avenue, West', 800.0, 80.0, 95.0)
        ])

    conn.commit()
    conn.close()
