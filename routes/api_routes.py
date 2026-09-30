from flask import Blueprint, request, jsonify
from datetime import datetime
from database import query_db, get_active_engine
from models import MeterModel, ReadingModel, ConsumerModel, FeederModel, TariffModel, BillingModel, AlertModel
from services.billing_service import BillingService
from services.load_service import LoadPlanningService
from services.simulator_service import SimulatorService
from config import Config

api_bp = Blueprint('api', __name__, url_prefix='/api')

# -------------------------------------------------------------
# 1. TELEMETRY INGESTION (AMR / AMI REST API)
# -------------------------------------------------------------
@api_bp.route('/readings/ingest', methods=['POST'])
def ingest_reading():
    """
    REST API endpoint for Smart Meters / IoT Gateways to push telemetry.
    Solves the core problem: Unstructured data -> Structured relational storage.
    """
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'Invalid JSON payload'}), 400

    meter_id = data.get('meter_id')
    if not meter_id:
        return jsonify({'success': False, 'error': 'meter_id is required'}), 400

    # Verify meter exists
    meter = MeterModel.get_by_id(meter_id)
    if not meter:
        return jsonify({'success': False, 'error': f"Meter {meter_id} not registered in utility database"}), 404

    timestamp = data.get('timestamp') or datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cumulative_kwh = float(data.get('cumulative_kwh', 0.0))
    active_power_kw = float(data.get('active_power_kw', 0.0))
    reactive_power_kvar = float(data.get('reactive_power_kvar', 0.0))
    voltage_v = float(data.get('voltage_v', 230.0))
    current_a = float(data.get('current_a', 0.0))
    power_factor = float(data.get('power_factor', 0.95))
    frequency_hz = float(data.get('frequency_hz', 50.0))
    tamper_alert = 1 if data.get('tamper_alert') else 0

    # Determine peak hour
    try:
        hour = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S').hour
    except Exception:
        hour = datetime.now().hour
    is_peak = 1 if (Config.PEAK_HOURS_START <= hour <= Config.PEAK_HOURS_END) else 0

    # Ingestion into structured storage
    res = ReadingModel.record_reading(
        meter_id=meter_id,
        timestamp=timestamp,
        cumulative_kwh=cumulative_kwh,
        active_power_kw=active_power_kw,
        reactive_power_kvar=reactive_power_kvar,
        voltage_v=voltage_v,
        current_a=current_a,
        power_factor=power_factor,
        frequency_hz=frequency_hz,
        is_peak_hour=is_peak,
        tamper_alert=tamper_alert,
        ingestion_mode='REST_API'
    )

    # Grid Anomaly Checks
    if voltage_v < Config.VOLTAGE_LOW_LIMIT:
        AlertModel.create(meter_id, meter['feeder_id'], 'VOLTAGE_DROP', 'WARNING',
                          f"Under-voltage reading {voltage_v}V on meter {meter_id}")
    elif voltage_v > Config.VOLTAGE_HIGH_LIMIT:
        AlertModel.create(meter_id, meter['feeder_id'], 'VOLTAGE_SURGE', 'WARNING',
                          f"Over-voltage reading {voltage_v}V on meter {meter_id}")

    if power_factor < Config.LOW_POWER_FACTOR_LIMIT:
        AlertModel.create(meter_id, meter['feeder_id'], 'LOW_PF', 'INFO',
                          f"Low Power Factor {power_factor} detected on meter {meter_id}")

    if tamper_alert:
        AlertModel.create(meter_id, meter['feeder_id'], 'TAMPERING', 'CRITICAL',
                          f"Tamper alarm flag received from Smart Meter {meter_id}")
        MeterModel.update_status(meter_id, 'Tampered')

    return jsonify({
        'success': True,
        'message': f"Telemetry successfully ingested into structured storage for meter {meter_id}",
        'reading_id': res.get('lastrowid') if isinstance(res, dict) else None,
        'meter_id': meter_id,
        'timestamp': timestamp,
        'cumulative_kwh': cumulative_kwh
    }), 201


@api_bp.route('/readings/batch', methods=['POST'])
def ingest_batch_readings():
    """Batch ingestion endpoint for smart meter concentrators."""
    data = request.get_json()
    if not data or not isinstance(data.get('readings'), list):
        return jsonify({'success': False, 'error': 'Expected array of readings'}), 400

    count = 0
    for r in data['readings']:
        mid = r.get('meter_id')
        if not mid:
            continue
        ts = r.get('timestamp') or datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        ReadingModel.record_reading(
            meter_id=mid,
            timestamp=ts,
            cumulative_kwh=float(r.get('cumulative_kwh', 0.0)),
            active_power_kw=float(r.get('active_power_kw', 0.0)),
            voltage_v=float(r.get('voltage_v', 230.0)),
            current_a=float(r.get('current_a', 0.0)),
            power_factor=float(r.get('power_factor', 0.95)),
            ingestion_mode='BATCH_API'
        )
        count += 1

    return jsonify({'success': True, 'ingested_count': count}), 200


@api_bp.route('/readings/recent', methods=['GET'])
def get_recent_readings():
    limit = min(int(request.args.get('limit', 50)), 200)
    meter_id = request.args.get('meter_id')
    readings = ReadingModel.get_recent(limit=limit, meter_id=meter_id)
    return jsonify({'success': True, 'count': len(readings), 'readings': readings})


# -------------------------------------------------------------
# 2. METERS API
# -------------------------------------------------------------
@api_bp.route('/meters', methods=['GET'])
def list_meters():
    search = request.args.get('search')
    status = request.args.get('status')
    feeder_id = request.args.get('feeder_id')
    meters = MeterModel.get_all(search=search, status=status, feeder_id=feeder_id)
    return jsonify({'success': True, 'count': len(meters), 'meters': meters})


@api_bp.route('/meters/<meter_id>', methods=['GET'])
def get_meter_details(meter_id):
    meter = MeterModel.get_by_id(meter_id)
    if not meter:
        return jsonify({'success': False, 'error': 'Meter not found'}), 404

    # Fetch last 48 readings for telemetry chart
    history = ReadingModel.get_history_for_meter(meter_id, limit=36)
    return jsonify({
        'success': True,
        'meter': meter,
        'telemetry_history': history
    })


@api_bp.route('/meters', methods=['POST'])
def add_meter():
    data = request.get_json()
    required = ['meter_id', 'serial_number', 'consumer_id', 'tariff_id', 'feeder_id']
    for req in required:
        if not data.get(req):
            return jsonify({'success': False, 'error': f"{req} is required"}), 400

    try:
        MeterModel.create(
            meter_id=data['meter_id'],
            serial_number=data['serial_number'],
            consumer_id=data['consumer_id'],
            tariff_id=data['tariff_id'],
            feeder_id=data['feeder_id'],
            model=data.get('model', 'SmartGrid IoT-X3')
        )
        return jsonify({'success': True, 'message': f"Meter {data['meter_id']} registered successfully"}), 201
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@api_bp.route('/meters/<meter_id>/status', methods=['PATCH'])
def update_meter_status(meter_id):
    data = request.get_json()
    status = data.get('status')
    if status not in ('Active', 'Suspended', 'Faulty', 'Tampered'):
        return jsonify({'success': False, 'error': 'Invalid status'}), 400

    MeterModel.update_status(meter_id, status)
    return jsonify({'success': True, 'message': f"Meter {meter_id} status updated to {status}"})


# -------------------------------------------------------------
# 3. CONSUMERS, FEEDERS, TARIFFS
# -------------------------------------------------------------
@api_bp.route('/consumers', methods=['GET'])
def get_consumers():
    consumers = ConsumerModel.get_all()
    return jsonify({'success': True, 'consumers': consumers})


@api_bp.route('/consumers', methods=['POST'])
def create_consumer():
    data = request.get_json()
    if not data or not data.get('consumer_id') or not data.get('full_name'):
        return jsonify({'success': False, 'error': 'consumer_id and full_name required'}), 400
    try:
        ConsumerModel.create(
            consumer_id=data['consumer_id'],
            full_name=data['full_name'],
            email=data.get('email'),
            phone=data.get('phone'),
            address=data.get('address'),
            feeder_id=data.get('feeder_id', 'FDR-NORTH-01'),
            category=data.get('category', 'Residential')
        )
        return jsonify({'success': True, 'message': 'Consumer created successfully'}), 201
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@api_bp.route('/feeders', methods=['GET'])
def get_feeders():
    feeders = FeederModel.get_all()
    return jsonify({'success': True, 'feeders': feeders})


@api_bp.route('/tariffs', methods=['GET'])
def get_tariffs():
    tariffs = TariffModel.get_all()
    return jsonify({'success': True, 'tariffs': tariffs})


# -------------------------------------------------------------
# 4. BILLING API
# -------------------------------------------------------------
@api_bp.route('/billing', methods=['GET'])
def get_billing_records():
    month = request.args.get('month')
    status = request.args.get('status')
    bills = BillingModel.get_all(month=month, status=status)
    return jsonify({'success': True, 'count': len(bills), 'bills': bills})


@api_bp.route('/billing/<bill_id>', methods=['GET'])
def get_bill_detail(bill_id):
    bill = BillingModel.get_by_id(bill_id)
    if not bill:
        return jsonify({'success': False, 'error': 'Bill not found'}), 404
    return jsonify({'success': True, 'bill': bill})


@api_bp.route('/billing/generate', methods=['POST'])
def generate_bills():
    """Runs automated billing calculation for all meters for a specified month."""
    data = request.get_json() or {}
    billing_month = data.get('billing_month') or datetime.now().strftime('%Y-%m')
    meter_id = data.get('meter_id')

    if meter_id:
        res = BillingService.calculate_bill_for_meter(meter_id, billing_month)
        return jsonify({'success': True, 'result': res})
    else:
        results = BillingService.generate_all_bills(billing_month)
        return jsonify({
            'success': True,
            'message': f"Generated {len(results)} billing statements for {billing_month}",
            'count': len(results),
            'bills': results
        })


@api_bp.route('/billing/<bill_id>/pay', methods=['POST'])
def mark_bill_paid(bill_id):
    BillingModel.mark_paid(bill_id)
    return jsonify({'success': True, 'message': f"Bill {bill_id} marked as Paid"})


# -------------------------------------------------------------
# 5. LOAD PLANNING & ANALYTICS API (FOR CHART.JS)
# -------------------------------------------------------------
@api_bp.route('/analytics/kpis', methods=['GET'])
def get_kpis():
    meter_summary = MeterModel.count_summary()
    active_meters = meter_summary['active_meters'] or 0

    # Today's total kWh
    today = datetime.now().strftime('%Y-%m-%d')
    kwh_sql = "SELECT SUM(active_power_kw) as total_kw_samples FROM meter_readings WHERE timestamp LIKE %s"
    today_data = query_db(kwh_sql, (f"{today}%",), one=True)
    today_total_kwh = round(float(today_data['total_kw_samples'] or 0.0) * 0.5, 2)

    # Billing collection efficiency
    bill_stats_sql = """
        SELECT 
            COUNT(*) as total_bills,
            SUM(CASE WHEN payment_status = 'Paid' THEN 1 ELSE 0 END) as paid_bills,
            SUM(total_payable) as total_billed,
            SUM(CASE WHEN payment_status = 'Paid' THEN total_payable ELSE 0 END) as total_collected
        FROM billing_records
    """
    bill_stats = query_db(bill_stats_sql, one=True)
    total_bills = bill_stats['total_bills'] or 0
    paid_bills = bill_stats['paid_bills'] or 0
    collection_rate = round((paid_bills / total_bills * 100.0), 1) if total_bills > 0 else 0.0

    # System Alerts count
    alerts_sql = "SELECT COUNT(*) as alert_count FROM system_alerts WHERE is_resolved = 0"
    alerts = query_db(alerts_sql, one=True)

    # Database info
    engine = get_active_engine()

    return jsonify({
        'success': True,
        'kpis': {
            'total_meters': meter_summary['total_meters'] or 0,
            'active_meters': active_meters,
            'tampered_meters': meter_summary['tampered_meters'] or 0,
            'faulty_meters': meter_summary['faulty_meters'] or 0,
            'today_energy_kwh': today_total_kwh,
            'collection_rate_pct': collection_rate,
            'unpaid_bills_count': total_bills - paid_bills,
            'active_alerts': alerts['alert_count'] or 0,
            'database_engine': engine.upper()
        }
    })


@api_bp.route('/analytics/load-curve', methods=['GET'])
def get_load_curve():
    feeder_id = request.args.get('feeder_id')
    date_str = request.args.get('date')
    curve_data = LoadPlanningService.get_system_load_curve(feeder_id=feeder_id, date_str=date_str)
    return jsonify({'success': True, 'curve': curve_data})


@api_bp.route('/analytics/feeder-capacities', methods=['GET'])
def get_feeder_capacities():
    feeders = LoadPlanningService.get_feeder_capacities()
    return jsonify({'success': True, 'feeders': feeders})


@api_bp.route('/analytics/category-distribution', methods=['GET'])
def get_category_distribution():
    data = LoadPlanningService.get_category_distribution()
    return jsonify({'success': True, 'distribution': data})


# -------------------------------------------------------------
# 6. SYSTEM ALERTS
# -------------------------------------------------------------
@api_bp.route('/alerts', methods=['GET'])
def get_alerts():
    alerts = AlertModel.get_recent(limit=20, unresolved_only=False)
    return jsonify({'success': True, 'alerts': alerts})


@api_bp.route('/alerts/<int:alert_id>/resolve', methods=['POST'])
def resolve_alert(alert_id):
    AlertModel.resolve(alert_id)
    return jsonify({'success': True, 'message': f"Alert {alert_id} resolved"})


# -------------------------------------------------------------
# 7. TELEMETRY SIMULATOR API
# -------------------------------------------------------------
@api_bp.route('/simulator/tick', methods=['POST'])
def run_simulation_tick():
    data = request.get_json() or {}
    meter_id = data.get('meter_id')
    readings = SimulatorService.simulate_single_tick(meter_id=meter_id)
    return jsonify({
        'success': True,
        'message': f"Generated live readings for {len(readings)} meter(s)",
        'readings': readings
    })


@api_bp.route('/simulator/seed', methods=['POST'])
def seed_simulation_data():
    days = int(request.json.get('days', 5) if request.json else 5)
    count = SimulatorService.seed_historical_telemetry(days=days)
    return jsonify({'success': True, 'message': f"Seeded telemetry data ({count} readings)"})
