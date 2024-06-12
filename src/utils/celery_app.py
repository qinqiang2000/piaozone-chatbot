from celery import Celery
from config.settings import CELERY_CONFIG
celery_app = Celery("tasks", broker=CELERY_CONFIG['broker_url'], backend=CELERY_CONFIG['backend_url'])

celery_app.conf.update(
    timezone='Asia/Shanghai',
    worker_concurrency= 4,
    task_acks_late=True,
    accept_content=['pickle', 'json'],
    task_serializer='pickle',  # 使用pickle作为任务序列化器
    result_serializer='pickle',
    worker_force_execv=True,
    worker_max_tasks_per_child=500,
    broker_heartbeat=0,
    broker_connection_retry_on_startup=True
)

def start_celery():
    celery_app.control.purge()
    celery_app.worker_main(['worker', '--loglevel=info'])