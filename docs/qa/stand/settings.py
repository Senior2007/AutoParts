"""Django settings for the temporary local QA database."""
import os
from pathlib import Path

from config.settings import *  # noqa: F403 - Django settings module configured by overrides below


def runtime_directory():
    raw = os.environ.get('AUTOPARTS_QA_STATE')
    if not raw:
        raise RuntimeError('Запустите стенд командой python -m docs.qa.')
    state = Path(raw).resolve()
    if not state.name.startswith('autoparts-qa-') or not (state / '.autoparts-qa').is_file():
        raise RuntimeError('Ожидается временная папка, созданная командой docs.qa.')
    return state


STATE = runtime_directory()
DATABASES = {
    'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': STATE / 'qa.sqlite3'},
}
DEBUG = False
ALLOWED_HOSTS = ['127.0.0.1', 'localhost', 'testserver']
CSRF_TRUSTED_ORIGINS = []
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {'console': {'class': 'logging.StreamHandler'}},
    'root': {'handlers': ['console'], 'level': 'INFO'},
    'loggers': {'django.server': {'handlers': ['console'], 'level': 'WARNING', 'propagate': False}},
}
