from routes.main import main_bp
from routes.settings import settings_bp
from routes.analytics import analytics_bp


def register_blueprints(app):
    app.register_blueprint(main_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(analytics_bp)
