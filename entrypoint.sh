#!/bin/sh
set -e
python manage.py migrate --noinput
exec gunicorn django_survey.wsgi:application \
     --bind 0.0.0.0:8000 \
     --workers 2
