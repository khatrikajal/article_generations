import os
from celery import Celery
from django.conf import settings


os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'article_generation.settings')

app = Celery('article_generation')

app.config_from_object('django.conf:settings', namespace='CELERY')


app.autodiscover_tasks()

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