#from __future__ import absolute_import

from celery import shared_task
from common.mongo_client import getMongoClient
import es_client

@shared_task
def es_index_item(site_id, item):
    es_client.es_index_item(site_id, item)


@shared_task
def update_hotview_list(site_id):
    mongo_client = getMongoClient()
    for event_type, prefix in mongo_client.EVENT_TYPE2HOT_INDEX_PREFIX.items():
        mongo_client.updateHotViewList(site_id, event_type)
