from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from flask_migrate import Migrate
from apscheduler.schedulers.background import BackgroundScheduler

db = SQLAlchemy()
csrf = CSRFProtect()
migrate = Migrate()
scheduler = BackgroundScheduler(daemon=True)
