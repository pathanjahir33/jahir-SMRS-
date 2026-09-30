from flask import Blueprint, render_template
from database import get_active_engine
from models import FeederModel, TariffModel

views_bp = Blueprint('views', __name__)

@views_bp.route('/')
def dashboard_view():
    feeders = FeederModel.get_all()
    engine = get_active_engine()
    return render_template('index.html', feeders=feeders, db_engine=engine)

@views_bp.route('/meters')
def meters_view():
    feeders = FeederModel.get_all()
    tariffs = TariffModel.get_all()
    engine = get_active_engine()
    return render_template('meters.html', feeders=feeders, tariffs=tariffs, db_engine=engine)

@views_bp.route('/readings')
def readings_view():
    engine = get_active_engine()
    return render_template('readings.html', db_engine=engine)

@views_bp.route('/load-planning')
def load_planning_view():
    feeders = FeederModel.get_all()
    engine = get_active_engine()
    return render_template('load_planning.html', feeders=feeders, db_engine=engine)

@views_bp.route('/billing')
def billing_view():
    engine = get_active_engine()
    return render_template('billing.html', db_engine=engine)

@views_bp.route('/docs')
def docs_view():
    engine = get_active_engine()
    return render_template('docs.html', db_engine=engine)
