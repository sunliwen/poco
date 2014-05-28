Periodic Tasks
--------------
reference: http://celery.readthedocs.org/en/latest/userguide/periodic-tasks.html

celery periodic tasks are configured in local_settings.py file. See local_settings.py.EXAMPLE

The celery-beat daemon are managed by supervisord currently. 

WARNING: You have to ensure only one celery beat instance is running.


Celery Worker
-------------
configure under supervisor https://github.com/celery/celery/tree/3.1/extra/supervisord/

We can start multiple works on the same machine:  http://celery.readthedocs.org/en/latest/userguide/workers.html#starting-the-worker
