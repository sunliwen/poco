#from __future__ import absolute_import

from celery import shared_task
from common.mongo_client import getMongoClient
from django.conf import settings
import es_client
from browsing_history_cache import BrowsingHistoryCache

@shared_task
def es_index_item(site_id, item):
    es_client.es_index_item(site_id, item)


@shared_task
def process_item_update_queue(item_update_queue):
    mongo_client = getMongoClient()
    for site_id, item in item_update_queue:
        for category in item["categories"]:
            mongo_client.updateProperty(site_id, category)
        if item.get("brand", None):
            mongo_client.updateProperty(site_id, item["brand"])
        item = mongo_client.updateItem(site_id, item)
        es_client.es_index_item(site_id, item)


@shared_task
def update_hotview_list(site_id):
    mongo_client = getMongoClient()
    for hot_index_type, prefix in mongo_client.HOT_INDEX_TYPE2INDEX_PREFIX.items():
        mongo_client.updateHotViewList(site_id, hot_index_type)


def update_visitor_cache(mongo_client, site_id, content):
    if content["behavior"] == "V":
        ptm_id = content["ptm_id"]
        browsing_history_cache = BrowsingHistoryCache(mongo_client)
        browsing_history = browsing_history_cache.get_from_cache(site_id, ptm_id,
                                no_result_as_none=True)
        if browsing_history is None:
            browsing_history = mongo_client.getBrowsingHistory(site_id, ptm_id)
        mongo_client.updateVisitorsFromLog(site_id, content)
        browsing_history.append(content["item_id"])
        browsing_history = browsing_history[-settings.VISITOR_BROWSING_HISTORY_LENGTH:]
        browsing_history_cache.update_cache(site_id, ptm_id, browsing_history)


@shared_task
def write_log(site_id, content):
    mongo_client = getMongoClient()
    mongo_client.writeLogToMongo(site_id, content)
    # check & update visitor cache
    update_visitor_cache(mongo_client, site_id, content)
