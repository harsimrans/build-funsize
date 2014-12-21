"""
funsize.backend.tasks
~~~~~~~~~~~~~~~~~~

This module contains a wrapper for the celery tasks that are to be run

"""

import os
import time
from celery import Celery
from celery.utils.log import get_task_logger
import funsize.backend.core as core
from funsize.cache import CacheError

app = Celery('tasks', broker=os.environ['CELERY_BROKER'])
celery_config = {
    'CELERY_ACKS_LATE': True,
}
app.conf.update(celery_config)
logger = get_task_logger(__name__)


@app.task
def build_partial_mar(*args, **kwargs):
    """ Wrapper for actual method, to get timestamps and measurings """
    start_time = time.time()
    try:
        core.build_partial_mar(*args, **kwargs)
    except CacheError as exc:
        logger.info("Retrying the failed task")
        raise build_partial_mar.retry(countdown=60, exc=exc, max_retries=2)

    total_time = time.time() - start_time
    logger.info("TOTAL TIME: %s", divmod(total_time, 60))
