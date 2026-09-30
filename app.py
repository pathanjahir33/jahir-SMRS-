import os
from flask import Flask, render_template, jsonify
from config import Config
from database import init_db, get_active_engine
from routes.api_routes import api_bp
from routes.view_routes import views_bp
from seed_data import seed_database

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Register Blueprints
    app.register_blueprint(api_bp)
    app.register_blueprint(views_bp)

    # Error Handlers
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('base.html', not_found=True), 404

    @app.errorhandler(500)
    def internal_error(e):
        return jsonify({'success': False, 'error': 'Internal server error', 'details': str(e)}), 500

    # Initialize DB & Seed baseline data if needed
    with app.app_context():
        try:
            seed_database()
        except Exception as e:
            print(f"[Startup Warning] Could not seed database: {e}")

    return app

app = create_app()

if __name__ == '__main__':
    print("=" * 60)
    print("  SMART METER READING SYSTEM (SMRS)")
    print(f"  Active Storage Backend: {get_active_engine().upper()}")
    print("  Server URL: http://127.0.0.1:5000")
    print("=" * 60)
    app.run(host=Config.HOST, port=Config.PORT, debug=Config.DEBUG)
