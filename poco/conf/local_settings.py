DEBUG = False

MONGODB_HOST = "localhost"
API_SERVER_PREFIX = "http://localhost:2222"
PRINT_RAW_LOG = True
#recommendation_deduplicate_item_names_required_set = set([])

API_PATH_PREFIX = "/api/v1.6/"

# For Development
BROKER_URL = "django://"
# For Production, use rabbitmq as broker
# BROKER_URL = 'amqp://guest:guest@localhost:5672//'

API_PREFIX_FOR_SEARCH_DEMO = "http://localhost:2222/api/v1.6/"
API_KEY_FOR_SEARCH_DEMO = "fb86b045"  # This is the api key of search demo which uses leyou's data, and the site id is testsite001

# For Production you need to configure CACHES settings
# refs: https://docs.djangoproject.com/en/dev/topics/cache/
# we use memcached in production.
# For development, the default local-memory caching is enough.
#CACHES = {
#    'default': {
#        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
#        'LOCATION': 'unique-snowflake'
#    }
#}


REDIS_CONFIGURATION = {"host": "localhost", "port": 6379, "db": 0}

# Redis cache is used for both production and development
CACHES = {
    'default': {
        'BACKEND': 'redis_cache.cache.RedisCache',
        'LOCATION': '%(host)s:%(port)s:%(db)s' % REDIS_CONFIGURATION,
        'OPTIONS': {
            'CLIENT_CLASS': 'redis_cache.client.DefaultClient',
            #'PASSWORD': 'secretpassword',  # Optional
        }
    }
}

CELERY_TIMEZONE = 'Asia/Shanghai'


# currently, these tasks only support one site
CRON_SITE_ID = "haoyaoshitest"


# CELERYBEAT_SCHEDULE = {
#     'rebuild_suggestion_cache': {
#         'task': 'apps.apis.search.tasks.rebuild_suggestion_cache',
#         'schedule': crontab(hour=23, minute=59), # midnight
#         'args': (CRON_SITE_ID, )
#     },
#     'update_hotview_list': {
#         'task': 'recommender.tasks.update_hotview_list',
#         'schedule': crontab(minute=01), # every hour
#         'args': (CRON_SITE_ID, )
#     },
#     'update_keyword_hot_view_list': {
#         'task': 'recommender.tasks.update_keyword_hot_view_list',
#         'schedule': crontab(minute=01), # every hour
#         'args': (CRON_SITE_ID, )
#     }
# }


# These are configuration copied from old dashboard configuration
COMPRESS_ENABLED=not DEBUG

# Following configure is for GMail SMTP
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = '<your user>'
EMAIL_HOST_PASSWORD = '<your password>'  # Hint: you may use 2-step authentication without put your main password here.

# EDM sender email
EDM_SENDER_EMAIL = '<the sender appear on edm emails>'
