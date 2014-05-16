"""
Django settings for poco project.

For more information on this file, see
https://docs.djangoproject.com/en/1.6/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/1.6/ref/settings/
"""

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
import os
BASE_DIR = os.path.dirname(os.path.dirname(__file__))


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/1.6/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = '=bc0@z=9h)2r6h8h-us*p_c!r6d4&nzew*jzrkh0#y-mhjg#p2'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

#DEBUG = False

TEMPLATE_DEBUG = True

ALLOWED_HOSTS = []


# Application definition

INSTALLED_APPS = (
    #'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'bootstrap_pagination',
    'django_extensions',
    'rest_framework',
    'compressor',
    #'kombu.transport.django', # disable this in production

    # poco apis
    'apps.apis.search',
    'apps.apis.recommender',

    # poco web apps
    'apps.web.dashboard',
    'apps.web.adminboard',

    # poco search example
    'examples.search',

    'gunicorn'
)

MIDDLEWARE_CLASSES = (
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
)

ROOT_URLCONF = 'conf.urls'

WSGI_APPLICATION = 'conf.wsgi.application'


# Database
# https://docs.djangoproject.com/en/1.6/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
    }
}

# Internationalization
# https://docs.djangoproject.com/en/1.6/topics/i18n/

#LANGUAGE_CODE = 'en-us'
LANGUAGE_CODE = 'zh-cn'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.6/howto/static-files/

STATIC_URL = '/static/'
STATIC_ROOT = 'static'

from django.conf import global_settings
TEMPLATE_CONTEXT_PROCESSORS = global_settings.TEMPLATE_CONTEXT_PROCESSORS + ("django.core.context_processors.request",)


LOGGING = {
    'version': 1,
    'disable_existing_loggers': True,
}

REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': (
        'rest_framework.renderers.UnicodeJSONRenderer',
        'rest_framework.renderers.JSONPRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    )
}


# django_compressor
COMPRESS_ENABLED = not DEBUG
COMPRESS_ROOT = STATIC_ROOT
COMPRESS_OUTPUT_DIR = 'min'


# recommender app settings
VISITOR_BROWSING_HISTORY_LENGTH = 15
MONGODB_HOST = None
REPLICA_SET = None
PRINT_RAW_LOG = False
API_SERVER_PREFIX = None
API_PATH_PREFIX = None
#MEMCACHED_HOSTS = None
BROKER_URL = None
# this should be a dictionary. set([site_id])
#recommendation_deduplicate_item_names_required_set = None


# celery
CELERY_ACCEPT_CONTENT = ['pickle', 'json', 'msgpack', 'yaml']

from local_settings import *


assert MONGODB_HOST is not None
assert API_SERVER_PREFIX is not None
assert API_PATH_PREFIX is not None
#assert recommendation_deduplicate_item_names_required_set is not None
#assert MEMCACHED_HOSTS is not None
assert BROKER_URL is not None
assert VISITOR_BROWSING_HISTORY_LENGTH > 0
