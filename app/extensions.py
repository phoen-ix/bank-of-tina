from __future__ import annotations

from flask_babel import Babel
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from flask_migrate import Migrate
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from apscheduler.schedulers.background import BackgroundScheduler

babel: Babel = Babel()
db: SQLAlchemy = SQLAlchemy()
csrf: CSRFProtect = CSRFProtect()
migrate: Migrate = Migrate()
limiter: Limiter = Limiter(key_func=get_remote_address, storage_uri="memory://", default_limits=[])
# A job that couldn't start on time (busy worker, restart) still runs within the
# hour, and a backlog of missed runs collapses into one.
scheduler: BackgroundScheduler = BackgroundScheduler(
    daemon=True, job_defaults={'misfire_grace_time': 3600, 'coalesce': True})
