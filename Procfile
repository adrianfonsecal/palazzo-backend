web: python manage.py collectstatic && gunicorn restapi.wsgi
worker: celery -A restapi worker -l INFO