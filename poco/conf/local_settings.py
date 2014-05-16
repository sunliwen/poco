from __future__ import absolute_import

MONGODB_HOST = "localhost"
API_SERVER_PREFIX = "http://localhost:2222"
API_PATH_PREFIX = "/api/v1.6/"
PRINT_RAW_LOG = True
#recommendation_deduplicate_item_names_required_set = set([])
DEBUG = True
DEBUG_PROPAGATE_EXCEPTIONS=True

BROKER_URL = "django://"


API_PREFIX_FOR_SEARCH_DEMO = "http://0.0.0.0:2222/api/v1.6/"
API_KEY_FOR_SEARCH_DEMO = "668ab90b"


from datetime import timedelta
from celery.schedules import crontab

CELERYBEAT_SCHEDULE = {
    'run-terms-cache-rebuilding': {
        'task': 'api_app.tasks.rebuild_suggestion_cache',
        'schedule': crontab(hour=18, minute=01),
        'args': ("haoyaoshi", )
    },
}

CELERY_TIMEZONE = 'Asia/Shanghai'

REDIS_CONFIGURATION = {"host": "localhost", "port": 6379, "db": 0}

# These are configuration copied from old dashboard configuration
COMPRESS_ENABLED=not DEBUG

