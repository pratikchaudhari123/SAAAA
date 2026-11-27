import os
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.environ['DJANGO_SECRET_KEY']
DEBUG = False
ALLOWED_HOSTS = ['localhost', '127.0.0.1', 'testserver']
INSTALLED_APPS = ['django.contrib.auth','django.contrib.contenttypes','django.contrib.sessions','rest_framework','campus']
MIDDLEWARE = ['django.middleware.security.SecurityMiddleware','django.contrib.sessions.middleware.SessionMiddleware','django.middleware.common.CommonMiddleware','django.middleware.csrf.CsrfViewMiddleware','django.contrib.auth.middleware.AuthenticationMiddleware']
ROOT_URLCONF = 'config.urls'
DATABASES = {'default': {'ENGINE':'django.db.backends.postgresql','NAME':os.environ.get('POSTGRES_DB','saaaa'),'USER':os.environ.get('POSTGRES_USER','saaaa'),'PASSWORD':os.environ['POSTGRES_PASSWORD'],'HOST':os.environ.get('POSTGRES_HOST','127.0.0.1'),'PORT':os.environ.get('POSTGRES_PORT','55440')}}
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
USE_TZ = True
TIME_ZONE = 'Asia/Kolkata'
REST_FRAMEWORK = {'DEFAULT_AUTHENTICATION_CLASSES':['rest_framework.authentication.SessionAuthentication'],'DEFAULT_PERMISSION_CLASSES':['rest_framework.permissions.IsAuthenticated'],'DEFAULT_RENDERER_CLASSES':['rest_framework.renderers.JSONRenderer']}
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'
