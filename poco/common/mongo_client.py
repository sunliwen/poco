import hashlib
import random
import time
import datetime
import copy
import pymongo
from django.conf import settings
from django.core.cache import get_cache
from pymongo.read_preferences import ReadPreference
from common.utils import getSiteDBName, getSiteDB, getSiteDBCollection
from common.utils import sign

import logging

#logging.basicConfig(format="%(asctime)s|%(levelname)s|%(name)s|%(message)s",
#                    level=logging.WARNING,
#                    datefmt="%Y-%m-%d %I:%M:%S")


class UpdateSiteError(Exception):
    pass


class BaseRecommendationResultFilter(object):
    def is_allowed(self, item_dict):
        return item_dict["available"] and item_dict.get("stock", 0) > 0


class SimpleRecommendationResultFilter(BaseRecommendationResultFilter):
    pass


HOT_INDEX_ALL_ITEMS = 0


# Now we intepret items which do not belong to any group in a default group.
class SameGroupRecommendationResultFilter(BaseRecommendationResultFilter):
    def getCatId(self, category):
        if isinstance(category, basestring):
            cat_id = category
        else:
            cat_id = category["id"]
        return cat_id

    def __init__(self, mongo_client, site_id, item_id):
        self.mongo_client = mongo_client
        self.site_id = site_id
        self.item_id = item_id

        category_groups = mongo_client.getCategoryGroups(site_id)
        allowed_category_groups = []
        item = mongo_client.getItem(site_id, item_id)
        if item is not None:
            for category in item["categories"]:
                category_group = category_groups.get(self.getCatId(category), None)
                allowed_category_groups.append(category_group)
            self.allowed_categories = set([self.getCatId(category) for category in item["categories"]])
            self.allowed_category_groups = set(allowed_category_groups)
        else:
            self.allowed_categories = set([])
            self.allowed_category_groups = set([])

    def is_allowed(self, item_dict):
        if not super(SameGroupRecommendationResultFilter, self).is_allowed(item_dict):
            return False
        category_groups = self.mongo_client.getCategoryGroups(self.site_id)
        if len(item_dict["categories"]) == 0:
            return True
        else:
            for category in item_dict["categories"]:
                if category_groups is not None:
                    item_category_group = category_groups.get(self.getCatId(category), None)
                    if item_category_group in self.allowed_category_groups:
                        return True
                elif self.getCatId(category) in self.allowed_categories:
                    return True
            return False


class ApiKeyAndSiteIDCache:
    EXPIRY_TIME = 3600 #1h

    CACHE_KEY_API_KEY_TO_SITE_ID = "api-key-to-site-id-dict"
    CACHE_KEY_SITE_ID_TO_API_KEY = "site-id-to-api-key-dict"

    def __init__(self, mongo_client):
        self.mongo_client = mongo_client

    def reload(self):
        api_key2site_id, site_id2api_key = self.mongo_client.fetchApiKeyAndSiteIDMapping()
        django_cache = get_cache("default")
        django_cache.set(self.CACHE_KEY_API_KEY_TO_SITE_ID, api_key2site_id, self.EXPIRY_TIME)
        django_cache.set(self.CACHE_KEY_SITE_ID_TO_API_KEY, site_id2api_key, self.EXPIRY_TIME)
        return api_key2site_id, site_id2api_key

    def getApiKey2SiteID(self):
        api_key2site_id = get_cache("default").get(self.CACHE_KEY_API_KEY_TO_SITE_ID)
        if api_key2site_id is None:
            api_key2site_id, site_id2api_key = self.reload()
        return api_key2site_id

    def getSiteID2ApiKey(self):
        site_id2api_key = get_cache("default").get(self.CACHE_KEY_SITE_ID_TO_API_KEY)
        if site_id2api_key is None:
            api_key2site_id, site_id2api_key = self.reload()
        return site_id2api_key


class MongoClient:
    def __init__(self, connection):
        self.connection = connection
        self.api_key_n_site_id_cache = ApiKeyAndSiteIDCache(self)

    def dropSiteDB(self, site_id):
        self.connection.drop_database(getSiteDBName(site_id))

    def getSiteDB(self, site_id):
        return getSiteDB(self.connection, site_id)

    def getSiteDBCollection(self, site_id, coll_name):
        return getSiteDBCollection(self.connection, site_id, coll_name)

    def toggle_black_list(self, site_id, item_id1, item_id2, is_on):
        c_rec_black_lists = getSiteDBCollection(self.connection, site_id, "rec_black_lists")
        rec_black_list = c_rec_black_lists.find_one({"item_id": item_id1})
        if rec_black_list is None:
            c_rec_black_lists.insert({"item_id": item_id1, "black_list": []})
        if is_on:
            c_rec_black_lists.update({"item_id": item_id1}, {"$addToSet": {"black_list": item_id2}})
        else:
            c_rec_black_lists.update({"item_id": item_id1}, {"$pull":  {"black_list": item_id2}})

    def get_black_list(self, site_id, item_id):
        c_rec_black_lists = getSiteDBCollection(self.connection, site_id, "rec_black_lists")
        row = c_rec_black_lists.find_one({"item_id": item_id})
        if row is None:
            return []
        else:
            return row["black_list"]

    def apply_black_list2topn(self, site_id, item_id, topn):
        ''' Remove items in black list '''
        black_list_set = set(self.get_black_list(site_id, item_id))
        return [topn_item for topn_item in topn if topn_item[0] not in black_list_set]

    def getPurchasingHistory(self, site_id, user_id):
        c_purchasing_history = getSiteDBCollection(self.connection, site_id, "purchasing_history")
        ph_in_db = c_purchasing_history.find_one({"user_id": user_id}, read_preference=ReadPreference.SECONDARY_PREFERRED)
        if ph_in_db is None:
            ph_in_db = {"user_id": user_id, "purchasing_history": []}
        return ph_in_db

    MAX_PURCHASING_HISTORY_AMOUNT = 100

    # ASSUME use will not purchase so quickly that the order of two purchasing will be reversed.
    # ASSUMING purchasing speed is far slower than page view.
    # there is a small chance that the "purchasing_history" will not
    # 100% correctly reflect the raw_log
    def updateUserPurchasingHistory(self, site_id, user_id):
        # TODO: time consuming, defer to offline computing
        logging.critical("TODO: move offline updateUserPurchasingHistory - user_id: %s" % user_id)
        pass
        ph_in_db = self.getPurchasingHistory(site_id, user_id)
        c_raw_logs = getSiteDBCollection(self.connection, site_id, "raw_logs")
        cursor = c_raw_logs.find({"user_id": user_id, "behavior": "PLO"}).\
                sort("created_on", -1).limit(self.MAX_PURCHASING_HISTORY_AMOUNT)
        is_items_enough = False
        purchasing_history = []
        ph_map = {}
        for record_PLO in cursor:
            for order_item in record_PLO["order_content"]:
                item_id = order_item["item_id"]
                if item_id not in ph_map:
                    purchasing_history.append(item_id)
                    ph_map[item_id] = 1
                if len(purchasing_history) > self.MAX_PURCHASING_HISTORY_AMOUNT:
                    is_items_enough = True
                    break
            if is_items_enough:
                break
        ph_in_db["purchasing_history"] = purchasing_history
        c_purchasing_history = getSiteDBCollection(self.connection, site_id, "purchasing_history")
        c_purchasing_history.save(ph_in_db)

    def recommend_based_on_purchasing_history(self, site_id, user_id):
        purchasing_history = self.getPurchasingHistory(site_id, user_id)["purchasing_history"]
        topn = self.calc_weighted_top_list_method1(site_id, "PLO", purchasing_history)
        return topn

    def getSimilaritiesForViewedUltimatelyBuy(self, site_id, item_id):
        viewed_ultimately_buys = getSiteDBCollection(self.connection, site_id, "viewed_ultimately_buys")
        result = viewed_ultimately_buys.find_one({"item_id": item_id}, read_preference=ReadPreference.SECONDARY_PREFERRED)
        if result is not None:
            vubs = result["viewedUltimatelyBuys"]
        else:
            vubs = []
        topn = [(vubs_item["item_id"], vubs_item["percentage"]) for vubs_item in vubs]
        topn = self.apply_black_list2topn(site_id, item_id, topn)
        return topn

    def getSimilaritiesForItem(self, site_id, similarity_type, item_id):
        item_similarities = getSiteDBCollection(self.connection, site_id, "item_similarities_%s" % similarity_type)
        result = item_similarities.find_one({"item_id": item_id}, read_preference=ReadPreference.SECONDARY_PREFERRED)
        if result is not None:
            topn = result["mostSimilarItems"]
        else:
            topn = []
        topn = self.apply_black_list2topn(site_id, item_id, topn)
        return topn

    def getSimilaritiesForItems(self, site_id, similarity_type, item_ids):
        c_item_similarities = getSiteDBCollection(self.connection, site_id, "item_similarities_%s" % similarity_type)
        result = []
        for row in c_item_similarities.find({"item_id": {"$in": item_ids}}):
            row["mostSimilarItems"] = self.apply_black_list2topn(site_id, row["item_id"],
                                        row["mostSimilarItems"])
            result.append(row)
        return result

    #API_KEY2SITE_ID = None
    #SITE_ID2API_KEY = None

    def fetchApiKeyAndSiteIDMapping(self):
        api_key2site_id = {}
        site_id2api_key = {}
        c_sites = self.connection["tjb-db"]["sites"]
        for site in c_sites.find():
            api_key2site_id[site["api_key"]] = site["site_id"]
            site_id2api_key[site["site_id"]] = site["api_key"]
        return api_key2site_id, site_id2api_key

    def reloadApiKey2SiteID(self):
        self.api_key_n_site_id_cache.reload()

    def getSiteID2ApiKey(self):
        return self.api_key_n_site_id_cache.getSiteID2ApiKey()

    def getApiKey2SiteID(self):
        return self.api_key_n_site_id_cache.getApiKey2SiteID()

    def siteExists(self, site_id, use_cache=True):
        if not use_cache:
            self.reloadApiKey2SiteID()
        return self.getSiteID2ApiKey().has_key(site_id)

    def loadSites(self):
        c_sites = self.connection["tjb-db"]["sites"]
        return [site for site in c_sites.find().sort('site_id')]

    # FIXME: should also make the api_key field unique.
    # FIXME: should fetch site info from cache
    def generateApiKey(self, site_id, site_name, api_prefix="test-"):
        c_sites = self.connection["tjb-db"]["sites"]
        api_key = api_prefix + hashlib.md5("%s:%s:%s" % (site_id, site_name, random.random())).hexdigest()[3:11]
        while c_sites.find_one({"api_key": api_key}) is not None:
            api_key = hashlib.md5("%s:%s:%s" % (site_id, site_name, random.random())).hexdigest()[3:11]
        return api_key

    def getTjbDb(self):
        return self.connection["tjb-db"]

    def dropSiteRecord(self, site_id):
        c_sites = self.getTjbDb()["sites"]
        c_sites.remove({"site_id": site_id})

    def getSite(self, site_id):
        c_sites = self.getTjbDb()["sites"]
        site = c_sites.find_one({"site_id": site_id})
        return site

    def getSiteFromToken(self, site_token):
        c_sites = self.getTjbDb()["sites"]
        site = c_sites.find_one({"site_token": site_token})
        return site

    def updateSite(self, site_id, site_name, calc_interval, algorithm_type="llh", api_prefix="test-"):
        c_sites = self.getTjbDb()["sites"]
        site = c_sites.find_one({"site_id": site_id})
        if site is None:
            if site_name is None:
                raise UpdateSiteError("site_name is required for new site creation.")
            site = {"site_id": site_id}
        site.setdefault("last_update_ts", None)
        site.setdefault("disabledFlows", [])
        site.setdefault("api_key", self.generateApiKey(site_id, site_name, api_prefix="test-"))
        if site_name is not None:
            site["site_name"] = site_name
        site["calc_interval"] = calc_interval
        site["algorithm_type"] = algorithm_type
        c_sites.save(site)
        return site

    def updateCategory(self, site_id, category):
        c_categories = getSiteDBCollection(self.connection, site_id, "categories")
        cat_in_db = c_categories.find_one({"category_id": category["category_id"]})
        if cat_in_db is None:
            cat_in_db = {}
        else:
            cat_in_db = {"_id": cat_in_db["_id"]}
        cat_in_db.update(category)
        c_categories.save(cat_in_db)

    def updateProperty(self, site_id, property):
        c_properties = getSiteDBCollection(self.connection, site_id, "properties")
        prop_in_db = c_properties.find_one({"id": property["id"]})
        if prop_in_db is None:
            prop_in_db = {}
        else:
            prop_in_db = {"_id": prop_in_db["_id"]}
        prop_in_db.update(property)
        c_properties.save(prop_in_db)

    def getProperty(self, site_id, property_type, property_id):
        c_properties = getSiteDBCollection(self.connection, site_id, "properties")
        result = c_properties.find_one({"type": property_type, "id": property_id},
                                        read_preference=ReadPreference.SECONDARY_PREFERRED)
        return result

    def getPropertyName(self, site_id, property_type, property_id):
        prop = self.getProperty(site_id, property_type, property_id)
        if prop:
            return prop.get("name", "")
        else:
            return ""

    def updateItem(self, site_id, item):
        c_items = getSiteDBCollection(self.connection, site_id, "items")
        item_in_db = c_items.find_one({"item_id": item["item_id"]})

        if item_in_db is None:
            item_in_db = {"created_on": datetime.datetime.now()}
        else:

            item_in_db.setdefault("created_on", datetime.datetime.now())
            item_in_db.update({"updated_on": datetime.datetime.now()})  # might be useful to have the updated_on

        item_in_db.update(item)
        c_items.save(item_in_db)
        self.updateTrafficMetricsFromItem(site_id, item_in_db)
        return item_in_db

    def removeItem(self, site_id, item_id):
        c_items = getSiteDBCollection(self.connection, site_id, "items")
        item_in_db = c_items.find_one({"item_id": item_id})
        if item_in_db is not None:
            item_in_db["available"] = False
            item_in_db["removed_on"] = datetime.datetime.now()
            c_items.save(item_in_db)

    def getItem(self, site_id, item_id):
        c_items = getSiteDBCollection(self.connection, site_id, "items")
        return c_items.find_one({"item_id": item_id}, read_preference=ReadPreference.SECONDARY_PREFERRED)

    def cleanupItems(self, site_id):
        c_items = getSiteDBCollection(self.connection, site_id, "items")
        c_items.remove({})

    def reloadCategoryGroups(self, site_id):
        now = time.time()
        c_sites = self.connection["tjb-db"]["sites"]
        site = c_sites.find_one({"site_id": site_id})
        self.SITE_ID2CATEGORY_GROUPS[site_id] = (site.get("category_groups", {}), now)

    SITE_ID2CATEGORY_GROUPS = {}

    def getCategoryGroups(self, site_id):
        # TODO: use callLater to update allowed_cross_category
        allowed_cross_category, last_update_ts = self.SITE_ID2CATEGORY_GROUPS.get(site_id, (None, None))
        now = time.time()
        if site_id not in self.SITE_ID2CATEGORY_GROUPS \
            or self.SITE_ID2CATEGORY_GROUPS[site_id][1] - now > 10:
            self.reloadCategoryGroups(site_id)
        return self.SITE_ID2CATEGORY_GROUPS[site_id][0]

    def convertTopNFormat(self, site_id, req_id, ref, result_filter, topn, amount, include_item_info=True,
            url_converter=None, excluded_recommendation_items=None,
            deduplicate_item_names_required=False,
            excluded_recommendation_item_names=None):
        if excluded_recommendation_items is None:
            excluded_recommendation_items = set([])
        if excluded_recommendation_item_names is None:
            excluded_recommendation_item_names = set([])
        if url_converter is None:
            url_converter = self.getRedirectUrlFor

        #c_items_collection = getSiteDBCollection(self.connection, site_id, "items")

        result = []
        recommended_item_names = []
        item_group = {}  # if item_group is available, aggregate item_group to any one available
        for topn_row in topn:
            item_in_db = self.getItem(site_id, topn_row[0])  # get only needed fields

            # excluded filtering
            if item_in_db is None or not result_filter.is_allowed(item_in_db) \
                or item_in_db["item_id"] in excluded_recommendation_items \
                or (deduplicate_item_names_required and item_in_db["item_name"] in excluded_recommendation_item_names):
                    continue

            # logging.critical("item_name %r " % item_in_db)
            # GOTCHA:
            # In case the item_name is not available, just skip it. The update api should accept new name right?
            recommended_item_names.append(item_in_db["item_name"])
            if deduplicate_item_names_required:
                excluded_recommendation_item_names |= set([item_in_db["item_name"]])

            # prepare info for response
            if include_item_info:
                # TODO, refactor - prepare a to delete list
                # TODO, list needed info only
                del item_in_db["_id"]
                del item_in_db["available"]
                del item_in_db["categories"]
                del item_in_db["created_on"]
                if "description" in item_in_db:
                    del item_in_db["description"]
                if "updated_on" in item_in_db:
                    del item_in_db["updated_on"]
                if "removed_on" in item_in_db:
                    del item_in_db["removed_on"]

                item_in_db["score"] = topn_row[1]
                item_in_db["item_link"] = url_converter(item_in_db["item_link"], site_id,
                                                item_in_db["item_id"], req_id, ref)
                result.append(item_in_db)
            else:
                result.append({"item_id": topn_row[0], "score": topn_row[1]})
            if len(result) == amount:
                break
        return result, set(recommended_item_names)

    def calc_weighted_top_list_method1(self, site_id, similarity_type,
            items_list, extra_excludes_list=[]):
        if len(items_list) > 15:
            recent_history = items_list[:15]
        else:
            recent_history = items_list

        excludes_set = set(items_list + extra_excludes_list)

        # calculate weighted top list from recent browsing history
        rec_map = {}
        for row in self.getSimilaritiesForItems(site_id, similarity_type, recent_history):
            recommended_items = row["mostSimilarItems"]
            for rec_item, score in recommended_items:
                if rec_item not in excludes_set:
                    rec_map.setdefault(rec_item, [0, 0])
                    rec_map[rec_item][0] += float(score)
                    rec_map[rec_item][1] += 1
        rec_tuples = []
        for key in rec_map.keys():
            score_total, count = rec_map[key][0], rec_map[key][1]
            rec_tuples.append((key, score_total / count))
        rec_tuples.sort(lambda a, b: sign(b[1] - a[1]))
        topn = [rec_tuple for rec_tuple in rec_tuples]
        return topn

    def recommend_by_each_purchased_item(self, site_id, user_id):
        purchasing_history = self.getPurchasingHistory(site_id, user_id)["purchasing_history"]
        return self.recommend_by_each_item(site_id, "PLO", purchasing_history)

    def recommend_by_each_item(self, site_id, similarity_type, items_list):
        result = []
        items_set = set(items_list)
        for row in self.getSimilaritiesForItems(site_id, similarity_type, items_list):
            topn = [topn_item for topn_item in row["mostSimilarItems"] if topn_item[0] not in items_set]
            result.append({"item_id": row["item_id"], "topn": topn})

        return result

    def recommend_based_on_some_items(self, site_id, similarity_type, items_list):
        topn = self.calc_weighted_top_list_method1(site_id, similarity_type, items_list)
        return topn

    def recommend_based_on_shopping_cart(self, site_id, user_id, shopping_cart):
        if user_id == "null":
            purchasing_history = []
        else:
            purchasing_history = self.getPurchasingHistory(site_id, user_id)["purchasing_history"]
        topn1 = self.calc_weighted_top_list_method1(site_id, "BuyTogether", shopping_cart,
                    extra_excludes_list=purchasing_history)
        topn2 = self.calc_weighted_top_list_method1(site_id, "PLO", shopping_cart,
                    extra_excludes_list=purchasing_history)
        topn1_item_set = set([topn1_item[0] for topn1_item in topn1])

        return topn1 + [topn2_item for topn2_item in topn2 if topn2_item[0] not in topn1_item_set]

    def recommend_for_edm(self, site_id, user_id, max_amount=5):
        c_user_orders = getSiteDBCollection(self.connection, site_id, "user_orders")
        c_raw_logs = getSiteDBCollection(self.connection, site_id, "raw_logs")
        latest_user_order = [user_order for user_order in c_user_orders.find({"user_id": user_id}).sort("order_datetime", -1).limit(1)][0]
        raw_log = c_raw_logs.find_one({"_id": latest_user_order["raw_log_id"]})
        items_list = [order_item["item_id"] for order_item in raw_log["order_content"]]
        purchasing_history = self.getPurchasingHistory(site_id, user_id)["purchasing_history"]
        topn = self.calc_weighted_top_list_method1(site_id, "PLO", items_list, extra_excludes_list=purchasing_history)
        ref = "ref=edm" # to trace source in edm
        result = self.convertTopNFormat(site_id, req_id=None, result_filter=SimpleRecommendationResultFilter(),
                        topn=topn, amount=max_amount, include_item_info=True, deduplicate_item_names_required=True,
                        url_converter=lambda item_link, site_id, item_id, req_id, ref: item_link)
        return result

    # Logging Part
    def writeLogToMongo(self, site_id, content):
        c_raw_logs = getSiteDBCollection(self.connection, site_id, "raw_logs")
        c_raw_logs.insert(content)

    # TODO: should use pub/sub to handle this
    def updateVisitorsFromLog(self, site_id, raw_log):
        c_visitors = getSiteDBCollection(self.connection, site_id, "visitors")
        behavior = raw_log.get("behavior", None)
        if behavior == "V":
            # refs: http://docs.mongodb.org/manual/reference/operator/update/slice/
            ptm_id = raw_log["ptm_id"]
            c_visitors.update({"ptm_id": ptm_id},
                           {"$set": {"updated_on": datetime.datetime.now()},
                            "$push" :{
                                "browsing_history": {
                                    "$each": [raw_log["item_id"]],
                                    "$slice": -settings.VISITOR_BROWSING_HISTORY_LENGTH
                                }
                            }
                            },
                           upsert=True)

    def getBrowsingHistory(self, site_id, ptm_id):
        c_visitors = getSiteDBCollection(self.connection, site_id, "visitors")
        visitor = c_visitors.find_one({"ptm_id": ptm_id})
        if visitor:
            return visitor["browsing_history"]
        else:
            return []

    def updateTrafficMetricsFromItem(self, site_id, item):
        c_traffic_metrics = getSiteDBCollection(self.connection, site_id, "traffic_metrics")
        categories = [category["id"] for category in item["categories"]]
        brand = item.get("brand", None)
        if brand is None:
            brand = None
        else:
            brand = brand.get("id", None)
        c_traffic_metrics.update({"item_id": item["item_id"]},
                                 {"item_id": item["item_id"],
                                  "categories": categories,
                                  "brand": brand},
                                  upsert=True
                                 )

    def _constructMetricsUpdatingDictForTimeStamp(self, prefix, timestamp):
        year, month, day, hour = timestamp.year, timestamp.month, timestamp.day, timestamp.hour
        updating_dict = {
            "$inc": {
                "%s.%d.%s" % (prefix, year, prefix): 1,
                "%s.%d.%d.%s" % (prefix, year, month, prefix): 1,
                "%s.%d.%d.%d.%s" % (prefix, year, month, day, prefix): 1,
                "%s.%d.%d.%d.%d.%s" % (prefix, year, month, day, hour, prefix): 1
            }
        }
        return updating_dict

    def updateKeywordMetricsFromLog(self, site_id, raw_log):
        c_keyword_metrics = getSiteDBCollection(self.connection, site_id, "keyword_metrics")
        created_on = raw_log["created_on"]
        keywords = [keyword.strip() for keyword in raw_log.get("q", "").split(" ")]
        category_id = raw_log.get("category_id", "null")
        if raw_log["behavior"] == "Event" and raw_log["event_type"] == "Search":
            for keyword in keywords:
                c_keyword_metrics.update(
                        {"keyword": keyword, "category_id": category_id},
                        self._constructMetricsUpdatingDictForTimeStamp("k", created_on),
                        upsert=True
                    )

    def calculateKeywordHotViewList(self, site_id, today=None):
        if today is None:
            today = datetime.date.today()
        last_7_days_attr_names = self.getLast7DaysAttributeNames("k", today)
        c_keyword_metrics = getSiteDBCollection(self.connection, site_id, "keyword_metrics")
        res = c_keyword_metrics.aggregate(
            [
            {"$project": {
                "keyword": 1,
                "count": {"$add": last_7_days_attr_names}
            }
            },
            {"$group": {
                "_id": "$keyword",
                "count": {"$sum": "$count"}
                }
            },
            {"$match": {"count": {"$gt": 0}}},
            {"$sort": {"count": -1}},
            {"$limit": 50}
            ]
        )
        result = res.get("result", [])
        print "RES:", result
        topn = [record["_id"] for record in result if record["count"] >= settings.MINIMAL_KEYWORD_HOT_VIEW_COUNT]
        if len(topn) >= settings.MINIMAL_KEYWORD_HOT_VIEW_LENGTH:
            return {"null": topn}
        else:
            return {"null": []}

    def getFromCachedResults(self, site_id, cache_key):
        c_cached_results = self.getSiteDBCollection(site_id, "cached_results")
        cached_result = c_cached_results.find_one({"cache_key": cache_key})
        if cached_result:
            result = cached_result["result"]
        else:
            result = None
        return result

    def updateCachedResults(self, site_id, cache_key, result):
        c_cached_results = self.getSiteDBCollection(site_id, "cached_results")
        c_cached_results.update({"cache_key": cache_key},
                                {"cache_key": cache_key, "result": result},
                                upsert=True)

    # TODO: should use pub/sub to handle this
    def updateTrafficMetricsFromLog(self, site_id, raw_log):
        c_traffic_metrics = getSiteDBCollection(self.connection, site_id, "traffic_metrics")
        behavior = raw_log.get("behavior", None)
        created_on = raw_log["created_on"]
        year, month, day, hour = created_on.year, created_on.month, created_on.day, created_on.hour
        if behavior == "V":
            item_id = raw_log["item_id"]
            c_traffic_metrics.update({"item_id": item_id},
                    {"$inc": {
                        "v.%d.v" % year: 1,
                        "v.%d.%d.v" % (year, month): 1,
                        "v.%d.%d.%d.v" % (year, month, day): 1,
                        "v.%d.%d.%d.%d.v" % (year, month, day, hour): 1,
                    }
                    },
                    upsert=True)
        elif behavior == "PLO":
            for order_row in raw_log["order_content"]:
                item_id = order_row["item_id"]
                try:
                    amount = int(order_row["amount"])
                except ValueError:
                    continue

                c_traffic_metrics.update({"item_id": item_id},
                    {"$inc": {
                        ("po.%d.po" % year): 1,
                        ("po.%d.%d.po" % (year, month)): 1,
                        ("po.%d.%d.%d.po" % (year, month, day)): 1,
                         "po.%d.%d.%d.%d.po" % (year, month, day, hour): 1,
                    }
                    },
                    upsert=True)

                c_traffic_metrics.update({"item_id": item_id},
                    {"$inc": {
                        ("pq.%d.pq" % year): amount,
                        ("pq.%d.%d.pq" % (year, month)): amount,
                        ("pq.%d.%d.%d.pq" % (year, month, day)): amount,
                         "pq.%d.%d.%d.%d.pq" % (year, month, day, hour): amount,
                    }
                    },
                    upsert=True)

    def getLastNDays(self, n, today):
        dt = today
        result = []
        for i in range(n):
            result.append(dt)
            dt -= datetime.timedelta(days=1)
        return result

    def getLast7DaysAttributeNames(self, prefix, today):
        last_7_days = self.getLastNDays(7, today)
        attr_names = [{"$ifNull": ["$%s.%d.%d.%d.%s" % (prefix, dt.year, dt.month, dt.day, prefix), 0]}
                    for dt in last_7_days]
        return attr_names

    def getHotViewList(self, site_id, hot_index_type, category_id=None, brand=None):
        c_cached_hot_view = getSiteDBCollection(self.connection, site_id, "cached_hot_view")
        cached = c_cached_hot_view.find_one({"hot_index_type": hot_index_type, "category_id": category_id, "brand": brand})
        if cached:
            return cached["result"]
        else:
            return []

    #EVENT_TYPE2HOT_INDEX_PREFIX = {"ViewItem": "v", "PlaceOrder": "p"}
    HOT_INDEX_TYPE2INDEX_PREFIX = {"by_viewed": "v", "by_order": "po", "by_quantity": "pq"}
    def updateHotViewList(self, site_id, hot_index_type, today=None):
        if today is None:
            today = datetime.date.today()
        prefix = self.HOT_INDEX_TYPE2INDEX_PREFIX[hot_index_type]
        last_7_days_attr_names = self.getLast7DaysAttributeNames(prefix, today)
        c_traffic_metrics = getSiteDBCollection(self.connection, site_id, "traffic_metrics")
        res = c_traffic_metrics.aggregate(
            [
            {"$project": {
                "item_id": 1,
                "categories": 1,
                "brand": 1,
                "total_views": {"$add": last_7_days_attr_names}
            }
            },
            {"$match": {"total_views": {"$gt": 0}}},
            {"$sort": {"total_views": -1}},
            #{"$limit": 10}
            ]
        )
        result = res.get("result", [])

        if result:
            highest_views = max(1.0, float(result[0]["total_views"]))
        else:
            highest_views = 1.0

        topn_by_categories = {}
        topn_by_brands = {}
        topn_overall = []
        for record in result:
            topn_entry = (record["item_id"], record["total_views"]/ highest_views)
            if len(topn_overall) < 10:
                topn_overall.append(topn_entry)
            for category_id in record.get("categories", []):
                topn_of_category = topn_by_categories.setdefault(category_id, [])
                if len(topn_of_category) < 10:
                    topn_of_category.append(topn_entry)
            if record.has_key("brand"):
                topn_of_brand = topn_by_brands.setdefault(record["brand"], [])
                if len(topn_of_brand) < 10:
                    topn_of_brand.append(topn_entry)

        c_cached_hot_view = getSiteDBCollection(self.connection, site_id, "cached_hot_view")

        c_cached_hot_view.update({"hot_index_type": hot_index_type, "category_id": None, "brand": None},
                                 {"hot_index_type": hot_index_type, "category_id": None, "brand": None, "result": topn_overall},
                                 upsert=True)
        for category_id, topn in topn_by_categories.items():
            c_cached_hot_view.update({"hot_index_type": hot_index_type, "category_id": category_id, "brand": None},
                                     {"hot_index_type": hot_index_type, "category_id": category_id, "brand": None, "result": topn},
                                     upsert=True)
        for brand, topn in topn_by_brands.items():
            c_cached_hot_view.update({"hot_index_type": hot_index_type, "category_id": None, "brand": brand},
                                     {"hot_index_type": hot_index_type, "category_id": None, "brand": brand, "result": topn},
                                     upsert=True)
        
    def updateSearchTermsCache(self, site_id, cache_entry):
        c_search_terms_cache = getSiteDBCollection(self.connection, site_id, "search_terms_cache")
        terms_key = "|".join(cache_entry["terms"])
        cache_entry["terms_key"] = terms_key
        c_search_terms_cache.update({"terms_key": terms_key},
                                    cache_entry,
                                    upsert=True)

    def fetchSearchTermsCacheEntry(self, site_id, terms):
        c_search_terms_cache = getSiteDBCollection(self.connection, site_id, "search_terms_cache")
        terms = copy.copy(terms)
        terms.sort()
        terms_key = "|".join(terms)
        cache_entry = c_search_terms_cache.find_one({"terms_key": terms_key})
        return terms_key, cache_entry

    def updateSuggestKeywordList(self, site_id, list_type, keywords, increase_count=False):
        c_suggest_keyword_list = self.getSiteDBCollection(site_id, "suggest_keyword_list")
        for keyword in keywords:
            update_doc = {"$setOnInsert": {"keyword": keyword},
                          "$set": {"type": list_type}}
            if increase_count:
                update_doc["$inc"] = {"count": 1}
            c_suggest_keyword_list.update({"keyword": keyword},
                                          update_doc,
                                          upsert=True)

    def getSuggestKeywordStatus(self, site_id, keyword):
        c_suggest_keyword_list = self.getSiteDBCollection(site_id, "suggest_keyword_list")
        record = c_suggest_keyword_list.find_one({"keyword": keyword})
        if record is None:
            return None
        else:
            return record["type"]

    def getSuggestKeywordList(self, site_id, list_type=None):
        c_suggest_keyword_list = self.getSiteDBCollection(site_id, "suggest_keyword_list")
        if list_type is None:
            return c_suggest_keyword_list.find().sort("count", -1)
        else:
            return c_suggest_keyword_list.find({"type": list_type}).sort("count", -1)

def getConnection():
    if(settings.REPLICA_SET):
        #return pymongo.MongoReplicaSetClient(settings.MONGODB_HOST, replicaSet=settings.REPLICA_SET, read_preference=ReadPreference.SECONDARY)
        return pymongo.MongoClient(settings.MONGODB_HOST, replicaSet=settings.REPLICA_SET, read_preference=ReadPreference.SECONDARY)
    else:
        return pymongo.MongoClient(settings.MONGODB_HOST)


mongo_client = MongoClient(getConnection())


def getMongoClient():
    return mongo_client
