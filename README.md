# Smart Meter Reading System (SMRS)

> **Enterprise Utility Operations, Structured Telemetry Storage, Automated Invoicing & Grid Load Planning**

---

## 📌 Problem Statement Addressed

> **"A utility company has no structured storage for meter readings, complicating billing and load planning."**

### Traditional Utility Challenges:
1. **Unstructured & Disparate Data:** Meter readings scattered in CSV spreadsheets or unindexed text logs with no relational integrity.
2. **Billing Delays & Disputes:** Estimated bills, delayed calculation of tiered tariffs, and inability to bill for Time-of-Use (ToU) peak hours.
3. **Blackout Risks & Blind Load Planning:** Substation engineers have no aggregated visibility into 24-hour demand curves, causing transformer overloads during peak hours.

### The SMRS Solution:
1. **Structured Relational Storage (MySQL):** A unified relational time-series database schema (`schema.sql`) indexing meter parameters: `active_power_kw`, `cumulative_kwh`, `voltage_v`, `current_a`, `power_factor`, `is_peak_hour`, and tamper alarm flags.
2. **Automated Tiered & ToU Billing Engine:** Instantly calculates monthly utility invoices using multi-tiered rate slabs, peak demand surcharges, fixed infrastructure fees, and tax duties with one-click payment settlement.
3. **Grid Load Planning Analytics (Chart.js):** Generates 24-hour system load curves, identifies peak demand windows (e.g., 18:00 - 22:00), computes Grid Load Factor (%), and monitors substation feeder capacities to prevent transformer outages.

---

## 🛠️ Technical Stack

| Component | Technology | Role in System |
|---|---|---|
| **Backend & Routing** | **Flask (Python 3.x)** | RESTful API server, business logic services, database abstraction |
| **Relational Database** | **MySQL** | Production structured storage with dual-mode fallback to **SQLite** |
| **Frontend Framework** | **Bootstrap 5 & Vanilla CSS** | Cyber-grid dark theme, responsive cards, modals, toast alerts |
| **Data Visualizations** | **Chart.js 4.x** | Interactive 24-hour load curves, category doughnuts, feeder bars |
| **Client Scripting** | **JavaScript (ES6+)** | Asynchronous `fetch` calls, live telemetry stream, real-time UI updates |
| **API Protocol** | **REST API (JSON)** | Endpoints for smart meter concentrators, IoT telemetry, billing, and planning |

---

## 📁 Project Architecture

```
jahir(SMRS)/
├── app.py                   # Flask server entry point & startup runner
├── config.py                # Database and grid threshold configuration
├── database.py              # Universal DB abstraction (MySQL with SQLite fallback)
├── schema.sql               # Production MySQL schema and baseline seeds
├── models.py                # Database models for Meters, Readings, Billing, etc.
├── seed_data.py             # Script to pre-populate consumers, meters & historical data
├── requirements.txt         # Python package dependencies
├── services/
│   ├── billing_service.py   # Multi-tier tariff & peak surcharge calculator
│   ├── load_service.py      # 24-hr demand curves, load factor & feeder forecasting
│   └── simulator_service.py # Realistic IoT AMI smart meter telemetry generator
├── routes/
│   ├── api_routes.py        # REST API endpoints (/api/readings, /api/meters, etc.)
│   └── view_routes.py       # HTML template views (/meters, /billing, /load-planning)
├── static/
│   ├── css/
│   │   └── style.css        # Custom utility operations center styling
│   └── js/
│       ├── dashboard.js     # Real-time KPIs, 24-hr load curve, feeder status
│       ├── meters.js        # Meter management & telemetry inspection modal
│       ├── readings.js      # Structured ingestion table & REST API tester
│       ├── load_planning.js # Substation transformer bars & peak planning
│       └── billing.js       # Billing engine, invoice modal & payment
└── templates/
    ├── base.html            # Master layout with sidebar & live telemetry switch
    ├── index.html           # Utility operations dashboard
    ├── meters.html          # Smart meters registry & telemetry inspector
    ├── readings.html        # Structured time-series ingestion portal
    ├── load_planning.html   # Substation load planning & forecasting hub
    ├── billing.html         # Automated invoicing engine & printable invoices
    └── docs.html            # Problem statement walkthrough & API guide
```

---

## 🚀 Quick Start Guide

### 1. Install Dependencies
Open your terminal in the project directory:
```bash
pip install -r requirements.txt
```

### 2. Configure Database (MySQL or SQLite)
The application comes pre-configured with **Dual-Mode Automatic Detection**:
- **Automatic / SQLite (Instant Run):** If you run without MySQL installed, the app automatically initializes `smart_meter.db` (SQLite) and seeds baseline consumers, meters, and telemetry with **zero setup needed**.
- **MySQL (Production):**
  1. Ensure MySQL server is running (e.g. via XAMPP, WAMP, or standalone MySQL).
  2. Import the schema:
     ```bash
     mysql -u root -p < schema.sql
     ```
  3. (Optional) Set your MySQL credentials in `.env` or `config.py`:
     ```env
     MYSQL_HOST=localhost
     MYSQL_PORT=3306
     MYSQL_USER=root
     MYSQL_PASSWORD=your_password
     MYSQL_DB=smart_meter_db
     DB_ENGINE=mysql
     ```

### 3. Run the Application
```bash
python app.py
```
Open your browser and navigate to:
```
http://127.0.0.1:5000
```

---

## 📡 Key REST API Endpoints

### 1. Telemetry Ingestion
- `POST /api/readings/ingest`: Push reading from smart meter / AMI concentrator.
  ```json
  {
    "meter_id": "SM-N-101",
    "cumulative_kwh": 712.40,
    "active_power_kw": 3.45,
    "voltage_v": 231.2,
    "current_a": 15.6,
    "power_factor": 0.96,
    "tamper_alert": false
  }
  ```
- `GET /api/readings/recent?limit=50`: Retrieve recent structured readings.

### 2. Asset & Grid Analytics
- `GET /api/analytics/kpis`: Real-time KPI summary (Active meters, today's energy kWh, billing collection %).
- `GET /api/analytics/load-curve`: 24-hour demand profile, peak hour, and Grid Load Factor.
- `GET /api/analytics/feeder-capacities`: Substation transformer load percentages vs rated capacity.

### 3. Automated Invoicing
- `POST /api/billing/generate`: Generate tiered and ToU invoices for all active meters for a given month (`YYYY-MM`).
- `GET /api/billing/<bill_id>`: Fetch itemized charges (base slabs, peak surcharge, tax, net payable).
- `POST /api/billing/<bill_id>/pay`: Settle bill payment.

---

## ⚡ Live Telemetry Simulation
The system includes a built-in **IoT Smart Meter Simulator**:
- **Simulate Pulse:** Click the `Simulate Pulse` button in the top navigation bar to broadcast an instant telemetry reading across all grid meters.
- **Live Stream Switch:** Toggle the `Live Telemetry Stream` switch in the top bar to stream readings every 5 seconds, causing real-time visual updates to load curves, voltage meters, and ingestion tables.
