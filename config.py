import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Flask settings
    SECRET_KEY = os.environ.get('SECRET_KEY', 'smrs-super-secret-key-2026-secure')
    DEBUG = os.environ.get('FLASK_DEBUG', 'True').lower() in ('true', '1', 't')
    PORT = int(os.environ.get('PORT', 5000))
    HOST = os.environ.get('HOST', '127.0.0.1')

    # Database Backend Preference ('mysql' or 'sqlite' or 'auto')
    # In 'auto' mode, it attempts to connect to MySQL first; if unavailable, falls back gracefully to SQLite
    DB_ENGINE = os.environ.get('DB_ENGINE', 'auto')

    # MySQL Database Configuration
    MYSQL_HOST = os.environ.get('MYSQL_HOST', 'localhost')
    MYSQL_PORT = int(os.environ.get('MYSQL_PORT', 3306))
    MYSQL_USER = os.environ.get('MYSQL_USER', 'root')
    MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', '')
    MYSQL_DB = os.environ.get('MYSQL_DB', 'smart_meter_db')

    # SQLite Database Configuration (Fallback or Standalone)
    SQLITE_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'smart_meter.db')

    # Time-of-Use (ToU) Peak Hour definition (18:00 to 22:00 = 6 PM to 10 PM)
    PEAK_HOURS_START = int(os.environ.get('PEAK_HOURS_START', 18))
    PEAK_HOURS_END = int(os.environ.get('PEAK_HOURS_END', 22))

    # Grid Alert Thresholds
    VOLTAGE_LOW_LIMIT = 207.0    # 230V - 10%
    VOLTAGE_HIGH_LIMIT = 253.0   # 230V + 10%
    LOW_POWER_FACTOR_LIMIT = 0.85
