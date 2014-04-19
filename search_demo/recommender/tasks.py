#from __future__ import absolute_import

from celery import shared_task
import es_client

@shared_task
def es_index_item(site_id, item):
    es_client.es_index_item(site_id, item)
