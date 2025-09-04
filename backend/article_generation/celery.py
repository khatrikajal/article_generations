import os
from celery import Celery
from django.conf import settings

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'article_generation.settings')

app = Celery('article_generation')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

# Optional configuration
app.conf.update(
    task_track_started=True,
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
    result_backend_transport_options={
        'retry_on_timeout': True,
    },
    broker_transport_options={
        'retry_on_timeout': True,
    },
)

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')