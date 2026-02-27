from __future__ import annotations

from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from flask_migrate import Migrate
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from apscheduler.schedulers.background import BackgroundScheduler

db: SQLAlchemy = SQLAlchemy()
csrf: CSRFProtect = CSRFProtect()
migrate: Migrate = Migrate()
limiter: Limiter = Limiter(key_func=get_remote_address, storage_uri="memory://", default_limits=[])
scheduler: BackgroundScheduler = BackgroundScheduler(daemon=True)
