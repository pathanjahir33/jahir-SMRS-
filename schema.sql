-- ==========================================================
-- SMART METER READING SYSTEM (SMRS)
-- Production MySQL Database Schema
-- Problem Solved: Structured time-series storage for smart
-- meter telemetry to streamline billing and load planning.
-- ==========================================================

CREATE DATABASE IF NOT EXISTS smart_meter_db;
USE smart_meter_db;

-- 1. TARIFF STRUCTURES
CREATE TABLE IF NOT EXISTS tariffs (
    tariff_id VARCHAR(20) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    customer_type ENUM('Residential', 'Commercial', 'Industrial') NOT NULL,
    slab1_limit FLOAT NOT NULL DEFAULT 100.0,
    slab1_rate FLOAT NOT NULL DEFAULT 0.10,
    slab2_limit FLOAT NOT NULL DEFAULT 300.0,
    slab2_rate FLOAT NOT NULL DEFAULT 0.16,
    slab3_rate FLOAT NOT NULL DEFAULT 0.24,
    peak_surcharge_rate FLOAT NOT NULL DEFAULT 0.06,
    fixed_charge FLOAT NOT NULL DEFAULT 12.00,
    tax_percent FLOAT NOT NULL DEFAULT 5.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. FEEDER / SUBSTATION CAPACITIES (FOR LOAD PLANNING)
CREATE TABLE IF NOT EXISTS feeders (
    feeder_id VARCHAR(50) PRIMARY KEY,
    substation_name VARCHAR(100) NOT NULL,
    location VARCHAR(100) NOT NULL,
    rated_capacity_kw FLOAT NOT NULL,
    warning_threshold_pct FLOAT NOT NULL DEFAULT 80.0,
    critical_threshold_pct FLOAT NOT NULL DEFAULT 95.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. CONSUMERS (CUSTOMERS)
CREATE TABLE IF NOT EXISTS consumers (
    consumer_id VARCHAR(50) PRIMARY KEY,
    full_name VARCHAR(150) NOT NULL,
    email VARCHAR(150),
    phone VARCHAR(30),
    address TEXT,
    feeder_id VARCHAR(50),
    category ENUM('Residential', 'Commercial', 'Industrial') NOT NULL DEFAULT 'Residential',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (feeder_id) REFERENCES feeders(feeder_id) ON DELETE SET NULL
);

-- 4. SMART METERS REGISTRY
CREATE TABLE IF NOT EXISTS meters (
    meter_id VARCHAR(50) PRIMARY KEY,
    serial_number VARCHAR(100) NOT NULL UNIQUE,
    consumer_id VARCHAR(50),
    tariff_id VARCHAR(20) NOT NULL,
    feeder_id VARCHAR(50) NOT NULL,
    model VARCHAR(100) NOT NULL DEFAULT 'SmartGrid IoT-X3',
    installation_date DATE,
    status ENUM('Active', 'Suspended', 'Faulty', 'Tampered') NOT NULL DEFAULT 'Active',
    current_cumulative_kwh FLOAT NOT NULL DEFAULT 0.0,
    last_reading_time DATETIME,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (consumer_id) REFERENCES consumers(consumer_id) ON DELETE SET NULL,
    FOREIGN KEY (tariff_id) REFERENCES tariffs(tariff_id) ON DELETE RESTRICT,
    FOREIGN KEY (feeder_id) REFERENCES feeders(feeder_id) ON DELETE RESTRICT
);

-- 5. TIME-SERIES METER READINGS (CORE STRUCTURED STORAGE)
CREATE TABLE IF NOT EXISTS meter_readings (
    reading_id INT AUTO_INCREMENT PRIMARY KEY,
    meter_id VARCHAR(50) NOT NULL,
    timestamp DATETIME NOT NULL,
    cumulative_kwh FLOAT NOT NULL,
    active_power_kw FLOAT NOT NULL,
    reactive_power_kvar FLOAT NOT NULL DEFAULT 0.0,
    voltage_v FLOAT NOT NULL DEFAULT 230.0,
    current_a FLOAT NOT NULL DEFAULT 0.0,
    power_factor FLOAT NOT NULL DEFAULT 0.95,
    frequency_hz FLOAT NOT NULL DEFAULT 50.0,
    is_peak_hour BOOLEAN NOT NULL DEFAULT 0,
    tamper_alert BOOLEAN NOT NULL DEFAULT 0,
    ingestion_mode VARCHAR(30) NOT NULL DEFAULT 'REST_API',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (meter_id) REFERENCES meters(meter_id) ON DELETE CASCADE,
    INDEX idx_meter_timestamp (meter_id, timestamp),
    INDEX idx_timestamp (timestamp)
);

-- 6. BILLING RECORDS (AUTOMATED BILLING ENGINE OUTPUT)
CREATE TABLE IF NOT EXISTS billing_records (
    bill_id VARCHAR(50) PRIMARY KEY,
    meter_id VARCHAR(50) NOT NULL,
    consumer_id VARCHAR(50) NOT NULL,
    billing_month VARCHAR(7) NOT NULL, -- Format: YYYY-MM
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    start_reading_kwh FLOAT NOT NULL,
    end_reading_kwh FLOAT NOT NULL,
    total_units_kwh FLOAT NOT NULL,
    peak_units_kwh FLOAT NOT NULL DEFAULT 0.0,
    base_energy_charge FLOAT NOT NULL,
    peak_surcharge FLOAT NOT NULL DEFAULT 0.0,
    fixed_charge FLOAT NOT NULL,
    tax_amount FLOAT NOT NULL,
    total_payable FLOAT NOT NULL,
    due_date DATE NOT NULL,
    payment_status ENUM('Unpaid', 'Paid', 'Overdue') NOT NULL DEFAULT 'Unpaid',
    paid_at DATETIME NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (meter_id) REFERENCES meters(meter_id) ON DELETE CASCADE,
    FOREIGN KEY (consumer_id) REFERENCES consumers(consumer_id) ON DELETE CASCADE,
    INDEX idx_billing_month (billing_month),
    INDEX idx_bill_meter (meter_id)
);

-- 7. SYSTEM ALERTS & GRID MONITORING
CREATE TABLE IF NOT EXISTS system_alerts (
    alert_id INT AUTO_INCREMENT PRIMARY KEY,
    meter_id VARCHAR(50) NULL,
    feeder_id VARCHAR(50) NULL,
    alert_type VARCHAR(50) NOT NULL, -- 'OVERLOAD', 'VOLTAGE_DROP', 'TAMPERING', 'LOW_PF'
    severity ENUM('INFO', 'WARNING', 'CRITICAL') NOT NULL DEFAULT 'WARNING',
    message TEXT NOT NULL,
    is_resolved BOOLEAN NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL,
    FOREIGN KEY (meter_id) REFERENCES meters(meter_id) ON DELETE SET NULL,
    FOREIGN KEY (feeder_id) REFERENCES feeders(feeder_id) ON DELETE SET NULL
);

-- ==========================================================
-- SEED INITIAL CONFIGURATION
-- ==========================================================

INSERT INTO tariffs (tariff_id, name, customer_type, slab1_limit, slab1_rate, slab2_limit, slab2_rate, slab3_rate, peak_surcharge_rate, fixed_charge, tax_percent)
VALUES 
('TAR-RES-01', 'Standard Residential Tiered', 'Residential', 100.0, 0.09, 300.0, 0.14, 0.22, 0.05, 8.50, 5.0),
('TAR-COM-01', 'Commercial General Tariff', 'Commercial', 300.0, 0.15, 800.0, 0.22, 0.30, 0.08, 25.00, 7.5),
('TAR-IND-01', 'Industrial High-Tension (HT)', 'Industrial', 1000.0, 0.18, 3000.0, 0.25, 0.34, 0.10, 75.00, 10.0)
ON DUPLICATE KEY UPDATE name=VALUES(name);

INSERT INTO feeders (feeder_id, substation_name, location, rated_capacity_kw, warning_threshold_pct, critical_threshold_pct)
VALUES
('FDR-NORTH-01', 'North City Substation', 'Sector 4, North Zone', 450.0, 80.0, 95.0),
('FDR-SOUTH-02', 'South City Substation', 'District 9, South Bay', 600.0, 80.0, 95.0),
('FDR-EAST-03',  'Eastside Industrial Park', 'Industrial Area, East', 1200.0, 80.0, 95.0),
('FDR-WEST-04',  'West End Commercial Hub', 'Downtown Avenue, West', 800.0, 80.0, 95.0)
ON DUPLICATE KEY UPDATE substation_name=VALUES(substation_name);
