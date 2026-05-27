web: gunicorn bookmyseat.wsgi --bind 0.0.0.0:$PORT
worker: celery -A bookmyseat worker --pool=solo -l info
beat: celery -A bookmyseat beat -l info