#from __future__ import absolute_import

from celery import shared_task
from common.mongo_client import getMongoClient
from common.cached_result import cached_result
from django.conf import settings
import es_client
from browsing_history_cache import BrowsingHistoryCache

from common.recommender_cache import RecommenderCache


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

@shared_task
def update_keyword_hot_view_list(site_id):
    mongo_client = getMongoClient()
    results = mongo_client.calculateKeywordHotViewList(site_id)
    for category_id, topn in results.items():
        if len(topn) > 0:
            cached_result.set("KeywordHotView", site_id, (category_id, ), topn)

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


mongo_client = getMongoClient()


def _write_log(site_id, content, is_update_visitor_cache=True):
    #mongo_client = getMongoClient()
    mongo_client.writeLogToMongo(site_id, content)
    mongo_client.updateTrafficMetricsFromLog(site_id, content)
    mongo_client.updateKeywordMetricsFromLog(site_id, content)
    # check & update visitor cache
    if is_update_visitor_cache:
        update_visitor_cache(mongo_client, site_id, content)
    # check & update user purchasing history
    if content["behavior"] == "PLO":
        mongo_client.updateUserPurchasingHistory(site_id=site_id, user_id=content["user_id"])
    # delete the shopping cart recommender cache
    # apps/apis/recommender/action_processor.py class GetByShoppingCartProcessor
    elif content['behavior'] == 'ASC':
        RecommenderCache.delRecommenderCacheResult(site_id, ('RecSC', content['user_id'], content['ptm_id']))
        

@shared_task
def write_log(site_id, content):
    _write_log(site_id, content)
