#!/usr/bin/env python

import sys
sys.path.insert(0, "../")
import pymongo
import simplejson as json
import copy
import re
import datetime
import os.path
import uuid
import urlparse
from django.conf import settings
import getopt
import urllib
import logging
from django.core.cache import get_cache
from django.core.urlresolvers import reverse
from browsing_history_cache import BrowsingHistoryCache

from common.utils import smart_split

from apps.apis.search import es_search_functions
from elasticutils import S, F

from common.mongo_client import getMongoClient
from common.mongo_client import SimpleRecommendationResultFilter
from common.mongo_client import SameGroupRecommendationResultFilter

from tasks import process_item_update_queue
from tasks import write_log

from common.recommender_cache import RecommenderCache


#logging.basicConfig(format="%(asctime)s|%(levelname)s|%(name)s|%(message)s",
#                    level=logging.WARNING,
#                    datefmt="%Y-%m-%d %I:%M:%S")


mongo_client = getMongoClient()

mongo_client.reloadApiKey2SiteID()

class HotViewListCache:
    EXPIRY_TIME = 3600

    def __init__(self, mongo_client):
        self.mongo_client = mongo_client

    def getHotViewList(self, site_id, hot_index_type, category_id=None, brand=None):
        cache_key = "hot-view-list-%s-%s-%s-%s" % (site_id, hot_index_type, category_id, brand)
        django_cache = get_cache("default")
        cache_entry = django_cache.get(cache_key)
        if cache_entry:
            return cache_entry
        else:
            cache_entry = self.mongo_client.getHotViewList(site_id, hot_index_type, category_id, brand)
            if cache_entry is None:
                cache_entry = []
            django_cache.set(cache_key, cache_entry, self.EXPIRY_TIME)
        return cache_entry
hot_view_list_cache = HotViewListCache(mongo_client)

browsing_history_cache = BrowsingHistoryCache(mongo_client)


# jquery serialize()  http://api.jquery.com/serialize/
# http://stackoverflow.com/questions/5784400/un-jquery-param-in-server-side-python-gae
# http://www.tsangpo.net/2010/04/24/unserialize-param-in-python.html

# TODO: referer;
# TODO: when to reload site ids.


class LogWriter:
    def writeLineToLocalLog(self, site_id, line):
        pass

    def writeEntry(self, site_id, content):
        content["created_on"] = datetime.datetime.now()
        #if settings.PRINT_RAW_LOG:
        #    print "RAW LOG: site_id: %s, %s" % (site_id, content)
        write_log.delay(site_id, content)


def extractArguments(request):
    result = {}
    for key in request.arguments.keys():
        result[key] = request.arguments[key][0]
    return result


class BaseArgumentProcessor:
    # TODO, avoid hacky code
    # if user_id and 0 or null
    def _convertArg(self, argument_name, args):
        '''
        Sometimes, site code will misuse 0 and null, to be consistent forcely convert to null
        '''
        arg = args[argument_name]
        if argument_name == "user_id":
            return arg == "0" and "null" or arg
        return arg

    def processArgs(self, args):
        raise NotImplemented


class ArgumentProcessor(BaseArgumentProcessor):
    def __init__(self, definitions, accept_extra_fields=False):
        self.definitions = definitions
        self.accept_extra_fields = accept_extra_fields

    def processArgs(self, args):
        err_msg = None
        result = {}

        if self.accept_extra_fields:
            for argument_name, is_required in self.definitions:
                if not args.has_key(argument_name) and is_required:
                    err_msg = "%s is required." % argument_name
                    break
            if err_msg is None:
                for argument_name in args.keys():
                    result[argument_name] = self._convertArg(argument_name, args)
        else:
            for argument_name, is_required in self.definitions:
                if argument_name not in args:
                    if is_required:
                        err_msg = "%s is required." % argument_name
                        break
                    else:
                        result[argument_name] = None
                else:
                    result[argument_name] = self._convertArg(argument_name, args)

        return err_msg, result


class CustomEventArgumentProcessor(BaseArgumentProcessor):
    def processArgs(self, args):
        result = {}
        err_msg = None
        if not args.has_key("user_id"):
            err_msg = "user_id is required."
        for argument_name in args.keys():
            result[argument_name] = self._convertArg(argument_name, args)
        return err_msg, result

class ArgumentError(Exception):
    pass


#class PtmIdEnabledHandlerMixin:
#    def prepare(self):
#        tornado.web.RequestHandler.prepare(self)
#        self.ptm_id = self.get_cookie("__ptmid")
#        if not self.ptm_id:
#            self.ptm_id = str(uuid.uuid4())
#            self.set_cookie("__ptmid", self.ptm_id, expires_days=109500)


#class SingleRequestHandler(PtmIdEnabledHandlerMixin, APIHandler):
#    processor_class = None

#    def process(self, site_id, args):
#        not_log_action = "not_log_action" in args
#        processor = self.processor_class(not_log_action)
#        err_msg, args = processor.processArgs(args)
#        if err_msg:
#            return {"code": 1, "err_msg": err_msg}
#        else:
#            args["ptm_id"] = self.ptm_id
#            referer = self.request.headers.get('Referer')
#            args["referer"] = referer
#            return processor.process(site_id, args)


class ActionProcessor(object):
    action_name = None

    def __init__(self, not_log_action=False):
        self.not_log_action = not_log_action

    def logAction(self, site_id, args, action_content, tjb_id_required=True):
        if not self.not_log_action:
            assert self.action_name != None
            if tjb_id_required:
                assert "ptm_id" in args
                action_content["ptm_id"] = args["ptm_id"]
            action_content["referer"] = args.get("referer", None)
            action_content["behavior"] = self.action_name
            logWriter.writeEntry(site_id, action_content)

    def processArgs(self, args):
        return self.ap.processArgs(args)

    def _process(self, site_id, args):
        raise NotImplemented

    def process(self, site_id, args):
        try:
            logWriter.writeLineToLocalLog(site_id, "BEGIN_REQUEST")
            try:
                return self._process(site_id, args)
            except ArgumentError:
                raise
            except:
                logging.critical("An Error occurred while processing action: site_id=%s, args=%s" % (site_id, args), exc_info=True)
                logWriter.writeLineToLocalLog(site_id, "UNKNOWN_ERROR:action_name=%s:args=%s" % (self.action_name, json.dumps(args)))
                return {"code": 99}
        finally:
            logWriter.writeLineToLocalLog(site_id, "END_REQUEST")


class BaseEventProcessor(ActionProcessor):
    def logAction(self, site_id, args, action_content, tjb_id_required=True):
        action_content["event_type"] = args["event_type"]
        action_content["is_reserved"] = EVENT_TYPE2ACTION_PROCESSOR.has_key(args["event_type"])
        return super(BaseEventProcessor, self).logAction(site_id, args, action_content, tjb_id_required=True)


class CustomEventProcessor(BaseEventProcessor):
    action_name = "Event"
    ap = CustomEventArgumentProcessor()

    def _process(self, site_id, args):
        self.logAction(site_id, args, args)
        return {"code": 0}


class SearchProcessor(BaseEventProcessor):
    action_name = "Event"
    ap = ArgumentProcessor(
            (("event_type", True),
             ("user_id", True),
             ("categories", False),
             ("q", True))
    )

    def _process(self, site_id, args):
        self.logAction(site_id, args, args)
        return {"code": 0}


class ViewCategoryProcessor(BaseEventProcessor):
    action_name = "Event"
    ap = ArgumentProcessor(
            (("event_type", True),
             ("user_id", True),
             ("categories", True))
    )

    def _process(self, site_id, args):
        self.logAction(site_id, args, args)
        return {"code": 0}


class ClickLinkProcessor(BaseEventProcessor):
    action_name = "Event"
    ap = ArgumentProcessor(
            (("event_type", True),
             ("user_id", True),
             ("link_type", True),
             ("url", True)),
            accept_extra_fields=True
    )

    def _process(self, site_id, args):
        link_type = args["link_type"]
        if link_type == "SearchResult" and not (args.has_key("q") and args.has_key("page") and args.has_key("item_id") and args.has_key("categories")):
            return {"code": 1, "err_msg": "q, page, item_id and categories are required."}
        elif link_type == "RecommendationResult" and not (args.has_key("req_id") and args.has_key("item_id")):
            return {"code": 1, "err_msg": "req_id and item_id are required."}
        elif link_type == "HotKeyword" and not (args.has_key("keyword")):
            return {"code": 1, "err_msg": "keyword is required."}
        self.logAction(site_id, args, args)
        return {"code": 0}


class ViewItemProcessor(BaseEventProcessor):
    action_name = "V"
    ap = ArgumentProcessor(
         (("event_type", True),
         ("item_id", True),
         ("user_id", True)  # if no user_id, pass in "null"
        )
    )

    def _validateInput(self, site_id, args):
        if re.match("[0-9a-zA-Z_-]+$", args["item_id"]) is None \
            or re.match("[0-9a-zA-Z_-]+$", args["user_id"]) is None:
            logWriter.writeEntry(site_id,
                {"behavior": "ERROR",
                 "content": {"behavior": "V",
                  "user_id": args["user_id"],
                  "ptm_id": args["ptm_id"],
                  "item_id": args["item_id"],
                  "referer": args.get("referer", None)}
                })
            raise ArgumentError("invalid item_id or user_id")

    def _process(self, site_id, args):
        self._validateInput(site_id, args)
        self.logAction(site_id, args,
                {"user_id": args["user_id"],
                 "item_id": args["item_id"]})
        return {"code": 0}


class UnlikeProcessor(BaseEventProcessor):
    action_name = "UNLIKE"
    ap = ArgumentProcessor(
        (
         ("event_type", True),
         ("item_id", True),
         ("user_id", True),
        )
    )

    def _process(self, site_id, args):
        self.logAction(site_id, args,
                        {"user_id": args["user_id"],
                         "item_id": args["item_id"]})
        return {"code": 0}


class AddFavoriteProcessor(BaseEventProcessor):
    action_name = "AF"
    ap = ArgumentProcessor(
        (
         ("event_type", True),
         ("item_id", True),
         ("user_id", True),
        )
    )

    def _process(self, site_id, args):
        self.logAction(site_id, args,
                        {"user_id": args["user_id"],
                         "item_id": args["item_id"]})
        return {"code": 0}


class RemoveFavoriteProcessor(BaseEventProcessor):
    action_name = "RF"
    ap = ArgumentProcessor(
         (("event_type", True),
         ("item_id", True),
         ("user_id", True),
        )
    )

    def _process(self, site_id, args):
        self.logAction(site_id, args,
                        {"user_id": args["user_id"],
                         "item_id": args["item_id"]})
        return {"code": 0}


class RateItemProcessor(BaseEventProcessor):
    action_name = "RI"
    ap = ArgumentProcessor(
         (("event_type", True),
         ("item_id", True),
         ("score", True),
         ("user_id", True),
        )
    )

    def _process(self, site_id, args):
        self.logAction(site_id, args,
                        {"user_id": args["user_id"],
                         "item_id": args["item_id"],
                         "score": args["score"]})
        return {"code": 0}


# FIXME: check user_id, the user_id can't be null.


class AddOrderItemProcessor(BaseEventProcessor):
    action_name = "ASC"
    ap = ArgumentProcessor(
        (("event_type", True),
         ("user_id", True),
         ("item_id", True),
         ('ptm_id', False)
        )
    )

    def _process(self, site_id, args):
        self.logAction(site_id, args,
                        {"user_id": args["user_id"],
                         "item_id": args["item_id"]})
        return {"code": 0}


class RemoveOrderItemProcessor(BaseEventProcessor):
    action_name = "RSC"
    ap = ArgumentProcessor(
        (("event_type", True),
         ("user_id", True),
         ("item_id", True),
        )
    )

    def _process(self, site_id, args):
        self.logAction(site_id, args,
                        {"user_id": args["user_id"],
                         "item_id": args["item_id"]})
        return {"code": 0}


class PlaceOrderProcessor(BaseEventProcessor):
    action_name = "PLO"
    ap = ArgumentProcessor(
        (("event_type", True),
         ("user_id", True),
         # order_content Format: item_id,price,amount|item_id,price,amount
         ("order_content", True),
         ("order_id", False)
        )
    )

    def _convertOrderContent(self, order_content):
        result = []
        for row in order_content.split("|"):
            item_id, price, amount = row.split(",")
            price = price.strip()
            result.append({"item_id": item_id, "price": price,
                           "amount": amount})
        return result

    def _process(self, site_id, args):
        uniq_order_id = str(uuid.uuid4())
        self.logAction(site_id, args,
                       {"user_id":  args["user_id"],
                        "order_id": args["order_id"],
                        "uniq_order_id": uniq_order_id,
                        "order_content": self._convertOrderContent(args["order_content"])})
        return {"code": 0}


class UpdateItemProcessor(ActionProcessor):
    action_name = "UItem"
    ap = ArgumentProcessor(
         (
            ("type", True),
            ("available", False),
            ("item_id", True),
            ("item_link", True),
            ("item_name", True),

            ("description", False),
            ("image_link", False),
            ("price", False),
            ("market_price", False),
            ("categories", False),
            ("item_group", False),
            # New attributes for haoyaoshi
            ("brand", False),
            ("item_level", False),
            ("item_spec", False),
            ("item_comment_num", False),
            ("origin_place", False),
            ("tags", False),
            ("prescription_type", False),
            ("sku", False),
            ("stock", False),
            ("factory", False)
        )
    )

    def __init__(self, not_log_action=False):
        super(UpdateItemProcessor, self).__init__(not_log_action)
        self.item_update_queue = []

    def _validateCategories(self, args):
        if not isinstance(args["categories"], list):
            return {"code": 1, "err_msg": "categories should be of type 'list'"}
        null_parent_id_found = False
        for category in args["categories"]:
            if not isinstance(category, dict):
                return {"code": 1, "err_msg": "categories content should be dicts. "}
            if category.get("type", None) != "category":
                return {"code": 1, "err_msg": "categories content should has type 'category'"}
            for expected_key in ("id", "name", "parent_id"):
                if not category.has_key(expected_key):
                    return {"code": 1, "err_msg": "categories content should contains key: '%s'" % expected_key}
                if (not isinstance(category[expected_key], basestring)) or (len(category[expected_key].strip()) == 0):
                    return {"code": 1, "err_msg": "'%s' of category should be a non empty string." % expected_key}
            for expected_key in ("id", "parent_id"):
                if re.match(r"[A-Za-z0-9]+", category[expected_key]) is None:
                    return {"code": 1, "err_msg": "category ids can only contains digits and letters."}
            null_parent_id_found = null_parent_id_found or category["parent_id"] == "null"
        if args["categories"] != [] and not null_parent_id_found:
            return {"code": 1, "err_msg": "At least one category should be at the top level"}
        return None

    def _validateBrand(self, args):
        args_brand = args.get("brand", None)
        if args_brand is not None:
            if not isinstance(args_brand, dict):
                return {"code": 1, "err_msg": "brand should be of type 'dict'"}
            if args_brand.get("type", None) != "brand":
                return {"code": 1, "err_msg": "brand should has type 'brand'"}
            for expected_key in ("id", "name"):
                if not args_brand.has_key(expected_key):
                    return {"code": 1, "err_msg": "brand content should contains key: '%s'" % expected_key}
        return None

    def _queueItem(self, site_id, args):
        self.item_update_queue.append((site_id, args))

    def sendQueueProcessingTask(self):
        process_item_update_queue.delay(self.item_update_queue)

    def _process(self, site_id, args):
        err_msg, args = self.ap.processArgs(args)
        if err_msg:
            return {"code": 1, "err_msg": err_msg}
        else:
            if args["type"] != "product":
                return {"code": 1, "err_msg": "The type of the item is expected to be 'product'"}
            if not isinstance(args["item_id"], basestring):
                return {"code": 1, "err_msg": "The type of item_id should be string."}
            if args["available"] is None:
                args["available"] = True
            if args["description"] is None:
                del args["description"]
            if args["image_link"] is None:
                del args["image_link"]
            if args["price"] is None:
                del args["price"]
            if args["market_price"] is None:
                del args["market_price"]
            if args["categories"] is None:
                args["categories"] = []
            if args["stock"] is None:
                args["stock"] = 0
            if not isinstance(args["stock"], int):
                return {"code": 1, "err_msg": "The type of stock should be integer."}
            err_response = self._validateCategories(args)
            if err_response:
                return err_response
            err_response = self._validateBrand(args)
            if err_response:
                return err_response
            if args["item_group"] is None:
                del args["item_group"]
            if args["tags"] is None:
                args["tags"] = []
            else:
                if not isinstance(args["tags"], list):
                    return {"code": 1, "err_msg": "'tags' should be a list of strings."}
                for tag in args["tags"]:
                    if not isinstance(tag, basestring):
                        return {"code": 1, "err_msg": "'tags' should be a list of strings."}

            for key in ("item_level", "item_comment_num", "origin_place"):
                if args.get(key, None) is not None:
                    try:
                        args[key] = int(args[key])
                    except (ValueError, TypeError):
                        return {"code": 1, "err_msg": "%s should be an integer." % key}

            #self._updateItem(site_id, args)
            self._queueItem(site_id, args)

            return {"code": 0}


class RemoveItemProcessor(ActionProcessor):
    action_name = "RItem"
    ap = ArgumentProcessor(
         [("item_id", True)]
        )

    def _process(self, site_id, args):
        err_msg, args = self.ap.processArgs(args)
        if err_msg:
            return {"code": 1, "err_msg": err_msg}
        else:
            mongo_client.removeItem(site_id, args["item_id"])
            return {"code": 0}


class BaseRecommendationProcessor(ActionProcessor):
    def generateReqId(self):
        return str(uuid.uuid4())

    def _extractRecommendedItems(self, topn):
        return [topn_row["item_id"] for topn_row in topn]

    def getRedirectUrlFor(self, url, site_id, item_id, req_id, ref):
        if ref:
            url = url + "?" + ref  # TODO, any better way to append a parameter
        api_key = mongo_client.getSiteID2ApiKey()[site_id]
        param_str = urllib.urlencode({"url": url,
                                  "api_key": api_key,
                                  "item_id": item_id,
                                   "req_id": req_id})
        REDIRECT_PATH = reverse("recommender-redirect")
        full_url = urlparse.urljoin(settings.API_SERVER_PREFIX, REDIRECT_PATH) + "?" + param_str
        return full_url

    def getRecommendationResultFilter(self, site_id, args):
        raise NotImplemented

    def getRecommendationResultSorter(self, site_id, args):
        raise NotImplemented

    def getExcludedRecommendationItems(self):
        return getattr(self, "excluded_recommendation_items", set([]))

    def isDeduplicateItemNamesRequired(self, site_id):
        #return site_id in settings.recommendation_deduplicate_item_names_required_set
        return False

    def getExcludedRecommendationItemNames(self, site_id):
        if self.isDeduplicateItemNamesRequired(site_id):
            return getattr(self, "excluded_recommendation_item_names", set([]))
        else:
            return set([])


class BaseByEachItemProcessor(BaseRecommendationProcessor):
    # args should have "user_id", "ptm_id"
    def getRecommendationLog(self, args, req_id, recommended_items):
        return {"req_id": req_id,
                "user_id": args["user_id"],
                "ptm_id": args["ptm_id"],
                "is_empty_result": len(recommended_items) == 0,
                "amount_for_each_item": self.getAmountForEachItem(args)
                }

    def getRecommendationsForEachItem(site_id, args):
        raise NotImplemented

    def getRecommendationResultFilter(self, site_id, args):
        raise NotImplemented

    def getRecRowMaxAmount(self, args):
        try:
            rec_row_max_amount = int(args["rec_row_max_amount"])
        except ValueError:
            raise ArgumentError("rec_row_max_amount should be an integer.")
        return rec_row_max_amount

    def getAmountForEachItem(self, args):
        try:
            amount_for_each_item = int(args["amount_for_each_item"])
        except ValueError:
            raise ArgumentError("amount_for_each_item should be an integer.")
        return amount_for_each_item

    def _process(self, site_id, args):
        self.recommended_items = None
        self.recommended_item_names = None
        include_item_info = args["include_item_info"] == "yes" or args["include_item_info"] is None
        req_id = self.generateReqId()
        ref = self._getRef(args)
        result_filter = self.getRecommendationResultFilter(site_id, args)

        amount_for_each_item = self.getAmountForEachItem(args)
        recommended_items = []
        recommended_item_names = set([])
        recommendations_for_each_item = []
        for recommendation_for_item in self.getRecommendationsForEachItem(site_id, args):
            if include_item_info:
                by_item = mongo_client.getItem(site_id, recommendation_for_item["item_id"])
                del by_item["_id"]
                del by_item["available"]
                del by_item["categories"]
                del by_item["created_on"]
                if "updated_on" in by_item:
                    del by_item["updated_on"]
                if "removed_on" in by_item:
                    del by_item["removed_on"]
                del recommendation_for_item["item_id"]
                recommendation_for_item["by_item"] = by_item
            else:
                recommendation_for_item["by_item"] = {"item_id": recommendation_for_item["item_id"]}
                del recommendation_for_item["item_id"]
            topn = recommendation_for_item["topn"]
            excluded_recommendation_items = self.getExcludedRecommendationItems() | set(recommended_items)
            excluded_recommendation_item_names = self.getExcludedRecommendationItemNames(site_id) | recommended_item_names
            topn, rin = mongo_client.convertTopNFormat(site_id, req_id, ref, result_filter, topn,
                            amount_for_each_item, include_item_info,
                            url_converter=self.getRedirectUrlFor,
                            deduplicate_item_names_required=self.isDeduplicateItemNamesRequired(site_id),
                            excluded_recommendation_item_names=excluded_recommendation_item_names,
                            excluded_recommendation_items=excluded_recommendation_items
                        )
            if len(topn) > 0:
                recommendation_for_item["topn"] = topn
                recommended_items += self._extractRecommendedItems(topn)
                recommended_item_names |= rin
                recommendations_for_each_item.append(recommendation_for_item)
            if len(recommendations_for_each_item) >= self.getRecRowMaxAmount(args):
                break

        self.logAction(site_id, args, self.getRecommendationLog(args, req_id, recommended_items))
        self.recommended_items = recommended_items
        self.recommended_item_names = recommended_item_names
        return {"code": 0, "result": recommendations_for_each_item, "req_id": req_id}


class BaseSimpleResultRecommendationProcessor(BaseRecommendationProcessor):
    # args should have "user_id", "ptm_id"
    def getRecommendationLog(self, args, req_id, recommended_items):
        return {"req_id": req_id,
                "user_id": args["user_id"],
                "ptm_id": args["ptm_id"],
                "recommended_items": recommended_items,
                "is_empty_result": len(recommended_items) == 0,
                "amount": args["amount"]}

    def postprocessTopN(self, topn):
        return

    # return the cache key fields.
    # If this returns None, then we will not lookup in cache
    def getCacheKeyTuple(self, args):
        if self.action_name is None:
            return []
        cache_key_fields = self.getCacheKeyFields()
        cache_key_tuple = []
        if cache_key_fields is not None:
            cache_key_tuple.append(self.__class__.action_name)
            for cache_key_field in cache_key_fields:
                cache_key = args.get(cache_key_field, None)
                if cache_key is None:
                    cache_key_tuple[:] = []
                    break
                cache_key_tuple.append(cache_key)
        return cache_key_tuple

    def getCacheKeyFields(self):
        return None

    def getTopNWithCache(self, site_id, args):
        # look up cache first
        cache_key_tuple = self.getCacheKeyTuple(args)
        if cache_key_tuple:
            topn = RecommenderCache.getRecommenderCacheResult(site_id, cache_key_tuple)
            if topn is not None:
                return topn
        topn = self.getTopN(site_id, args)
        self.reOrderTopN(site_id, topn)
        # add topn to cache if possible
        if cache_key_tuple:
            RecommenderCache.setRecommenderCacheResult(site_id,
                                                       cache_key_tuple,
                                                       topn)
        return topn
        

    def getTopN(self, site_id, args):
        raise NotImplemented

    def _getRef(self, args):
        if "ref" in args and args["ref"]:
            return "ref=" + str.strip(args["ref"])
        else:
            return None

    def reOrderTopN(self, site_id, topn):
        manual_list = mongo_client.getRecommendStickLists(
            site_id,
            self.recommender_type)
        if not (manual_list and manual_list.get('content', [])):
            return
        item_order_list = manual_list['content'] + [item[0] for item in topn]
        topn.sort(lambda item_i, item_j: item_order_list.index(item_i[0]) - item_order_list.index(item_j[0]))

        
    def _process(self, site_id, args):
        self.recommended_items = None
        self.recommended_item_names = None
        include_item_info = args["include_item_info"] == "yes" or args["include_item_info"] is None

        try:
            amount = int(args["amount"])
        except ValueError:
            raise ArgumentError("amount should be an integer.")
        req_id = self.generateReqId()
        # append ref parameters
        ref = self._getRef(args)
        topn = self.getTopNWithCache(site_id, args)

        # apply filter
        result_filter = self.getRecommendationResultFilter(site_id, args)
        excluded_recommendation_item_names = self.getExcludedRecommendationItemNames(site_id)
        topn, recommended_item_names = mongo_client.convertTopNFormat(site_id, req_id, ref, result_filter, topn,
                    amount, include_item_info, url_converter=self.getRedirectUrlFor,
                    excluded_recommendation_items=self.getExcludedRecommendationItems(),
                    deduplicate_item_names_required=self.isDeduplicateItemNamesRequired(site_id),
                    excluded_recommendation_item_names=excluded_recommendation_item_names)

        self.postprocessTopN(topn)
        recommended_items = self._extractRecommendedItems(topn)
        self.logAction(site_id, args, self.getRecommendationLog(args, req_id, recommended_items))
        self.recommended_items = recommended_items
        self.recommended_item_names = recommended_item_names
        return {"code": 0, "topn": topn, "req_id": req_id}


class BaseSimilarityProcessor(BaseSimpleResultRecommendationProcessor):
    similarity_type = None

    ap = ArgumentProcessor(
         (
            ("user_id", True),
            ("item_id", True),
            ("include_item_info", False),  # no, not include; yes, include
            ("amount", True),
            ("ref", False),  # appendix to item_link
        )
    )

    def getRecommendationLog(self, args, req_id, recommended_items):
        log = BaseSimpleResultRecommendationProcessor.getRecommendationLog(self, args, req_id, recommended_items)
        log["item_id"] = args["item_id"]
        return log

    def getCacheKeyTuple(self, args):
        return (self.similarity_type, args['item_id'])

    def getTopN(self, site_id, args):
        return mongo_client.getSimilaritiesForItem(site_id, self.similarity_type, args["item_id"])


class GetByEachPurchasedItemProcessor(BaseByEachItemProcessor):
    action_name = "RecEPI"
    ap = ArgumentProcessor(
        (
            ("user_id", True),
            ("ref", False),
            ("include_item_info", False),  # no, not include; yes, include
            ("rec_row_max_amount", True),
            ("amount_for_each_item", True),
        )
    )

    def getRecommendationResultFilter(self, site_id, args):
        return SimpleRecommendationResultFilter()

    def getRecommendationsForEachItem(self, site_id, args):
        user_id = args["user_id"]
        return mongo_client.recommend_by_each_purchased_item(site_id, user_id)


class GetByEachBrowsedItemProcessor(BaseByEachItemProcessor):
    action_name = "RecEBI"
    ap = ArgumentProcessor(
            (
                ("user_id", True),
                ("ref", False),
                ("browsing_history", False),
                ("include_item_info", False),  # no, not include; yes, include
                ("rec_row_max_amount", True),
                ("amount_for_each_item", True),
            )
        )

    def getRecommendationResultFilter(self, site_id, args):
        return SimpleRecommendationResultFilter()

    def getBrowsingHistory(self, args):
        browsing_history = args["browsing_history"]
        if browsing_history == None:
            browsing_history = []
        else:
            browsing_history = browsing_history.split(",")
        return browsing_history

    def getRecommendationLog(self, args, req_id, recommended_items):
        log = BaseByEachItemProcessor.getRecommendationLog(self, args, req_id, recommended_items)
        log["browsing_history"] = self.getBrowsingHistory(args)
        return log

    def getRecommendationsForEachItem(self, site_id, args):
        browsing_history = self.getBrowsingHistory(args)
        return mongo_client.recommend_by_each_item(site_id, "V", browsing_history)


class GetAlsoViewedProcessor(BaseSimilarityProcessor):
    action_name = "RecVAV"
    similarity_type = "V"

    def getRecommendationResultFilter(self, site_id, args):
        return SameGroupRecommendationResultFilter(mongo_client, site_id, args["item_id"])


class GetAlsoBoughtProcessor(BaseSimilarityProcessor):
    action_name = "RecBAB"
    similarity_type = "PLO"

    def getRecommendationResultFilter(self, site_id, args):
        return SameGroupRecommendationResultFilter(mongo_client, site_id, args["item_id"])


class GetBoughtTogetherProcessor(BaseSimilarityProcessor):
    action_name = "RecBTG"
    similarity_type = "BuyTogether"

    def getRecommendationResultFilter(self, site_id, args):
        return SimpleRecommendationResultFilter()


class GetUltimatelyBoughtProcessor(BaseSimpleResultRecommendationProcessor):
    '''
        TODO:
            * support filter by SKUG - sku group 
    '''
    action_name = "RecVUB"
    ap = ArgumentProcessor(
        (
            ("user_id", True),
            ("ref", False),
            ("item_id", True),
            ("include_item_info", False),  # no, not include; yes, include
            ("amount", True)
        )
    )

    def getRecommendationResultFilter(self, site_id, args):
        return SameGroupRecommendationResultFilter(mongo_client, site_id, args["item_id"])

    def getRecommendationLog(self, args, req_id, recommended_items):
        log = BaseSimpleResultRecommendationProcessor.getRecommendationLog(self, args, req_id, recommended_items)
        log["item_id"] = args["item_id"]
        return log

    def getCacheKeyFields(self):
        return ('item_id', )

    def getTopN(self, site_id, args):
        return mongo_client.getSimilaritiesForViewedUltimatelyBuy(site_id, args["item_id"])

    def postprocessTopN(self, topn):
        for topn_item in topn:
            topn_item["percentage"] = int(round(topn_item["score"] * 100))


class GetByBrowsingHistoryProcessor(BaseSimpleResultRecommendationProcessor):
    action_name = "RecBOBH"
    ap = ArgumentProcessor(
            (
                ("user_id", True),
                ("ref", False),
                #("browsing_history", False),
                ("include_item_info", False),  # no, not include; yes, include
                ("amount", True),
            )
        )

    def getRecommendationResultFilter(self, site_id, args):
        return SimpleRecommendationResultFilter()

    def getRecommendationLog(self, args, req_id, recommended_items):
        log = BaseSimpleResultRecommendationProcessor.getRecommendationLog(self, args, req_id, recommended_items)
        log["browsing_history"] = args.get("browsing_history", [])
        return log

    def getCacheKeyFields(self):
        return ('ptm_id', )

    def getTopN(self, site_id, args):
        ptm_id = args["ptm_id"]
        browsing_history = browsing_history_cache.get(site_id, ptm_id)
        args["browsing_history"] = browsing_history
        topn = mongo_client.recommend_based_on_some_items(site_id, "V", browsing_history)
        return topn


class GetByHotIndexProcessor(BaseSimpleResultRecommendationProcessor):
    action_name = "RecBHI"
    ap = ArgumentProcessor(
            (
                ("user_id", True),
                ("ref", False),
                ("hot_index_type", True), 
                ("category_id", False),
                ("brand", False),
                ("include_item_info", False),  # no, not include; yes, include
                ("amount", True),
            )
        )

    def getRecommendationResultFilter(self, site_id, args):
        return SimpleRecommendationResultFilter()

    def getRecommendationLog(self, args, req_id, recommended_items):
        log = BaseSimpleResultRecommendationProcessor.getRecommendationLog(self, args, req_id, recommended_items)
        log["category_id"] = args["category_id"]
        log["brand"] = args["brand"]
        return log

    def getTopN(self, site_id, args):
        hot_index_type = args.get("hot_index_type", None)
        is_valid_hot_index_type = mongo_client.HOT_INDEX_TYPE2INDEX_PREFIX.has_key(hot_index_type)
        if is_valid_hot_index_type:
            topn = hot_view_list_cache.getHotViewList(site_id, 
                            hot_index_type=hot_index_type,
                            category_id=args.get("category_id", None), 
                            brand=args.get("brand", None))
            return topn
        else:
            raise ArgumentError("hot_index_type should be one of these values: %s" % (",".join(mongo_client.HOT_INDEX_TYPE2INDEX_PREFIX.keys())))


class GetByShoppingCartProcessor(BaseSimpleResultRecommendationProcessor):
    action_name = "RecSC"
    ap = ArgumentProcessor(
            (
                ("user_id", True),
                ("ref", False),
                ("shopping_cart", False),
                ("include_item_info", False),  # no, not include; yes, include
                ("amount", True),
            )
        )

    def getRecommendationResultFilter(self, site_id, args):
        return SimpleRecommendationResultFilter()

    def getRecommendationLog(self, args, req_id, recommended_items):
        log = BaseSimpleResultRecommendationProcessor.getRecommendationLog(self, args, req_id, recommended_items)
        if args["shopping_cart"] == None:
            log["shopping_cart"] = []
        else:
            log["shopping_cart"] = args["shopping_cart"].split(",")
        return log

    def getCacheKeyFields(self):
        return ('user_id', 'ptm_id')

    def getTopN(self, site_id, args):
        shopping_cart = args["shopping_cart"]
        if shopping_cart == None:
            shopping_cart = []
        else:
            shopping_cart = shopping_cart.split(",")

        return mongo_client.recommend_based_on_shopping_cart(site_id, args["user_id"], shopping_cart)


class GetByPurchasingHistoryProcessor(BaseSimpleResultRecommendationProcessor):
    action_name = "RecPH"
    ap = ArgumentProcessor(
            (
                ("user_id", True),
                ("ref", False),
                ("include_item_info", False),  # no, not include; yes, include
                ("amount", True),
            )
        )

    def getRecommendationResultFilter(self, site_id, args):
        return SimpleRecommendationResultFilter()

    def getCacheKeyTuple(self, args):
        user_id = args["user_id"]
        if user_id == "null":
            return []
        return [self.__class__.action_name, user_id]

    def getTopN(self, site_id, args):
        user_id = args["user_id"]
        if user_id == "null":
            return []
        else:
            return mongo_client.recommend_based_on_purchasing_history(site_id, user_id)

class GetCustomListsRecommend(BaseSimpleResultRecommendationProcessor):
    action_name = "CustomLists"
    similarity_type = "CST"
    ap = ArgumentProcessor(
            (
                ("ref", False),
                ("user_id", True),
                ("include_item_info", False),  # no, not include; yes, include
                ("custom_type", True),
                ("amount", True),
            )
        )

    def getRecommendationResultFilter(self, site_id, args):
        return SimpleRecommendationResultFilter()

    def getCacheKeyFields(self):
        return ('custom_type', )

    def getTopN(self, site_id, args):
        rtype = args.get('custom_type', '')
        amount = int(args.get('amount', 5))
        recommend_data = mongo_client.getRecommendCustomLists(site_id, rtype)
        topn = []
        if recommend_data:
            topn = [[item, 0.5] for item in recommend_data['content']['item_ids']]
        if len(topn) < amount:
            default_topn = mongo_client.getHotViewList(site_id,
                                                       'by_viewed')
            topn_set = set([item[0] for item in topn])
            miss_amount = amount-len(topn)
            default_topn = [item for item in default_topn if item[0] not in topn_set][:miss_amount]
            topn = topn + default_topn
        return topn


logWriter = LogWriter()


EVENT_TYPE2ACTION_PROCESSOR = {
    "ViewItem": ViewItemProcessor,
    "AddFavorite": AddFavoriteProcessor,
    "RemoveFavorite": RemoveFavoriteProcessor,
    "Unlike": UnlikeProcessor,
    "RateItem": RateItemProcessor,
    "AddOrderItem": AddOrderItemProcessor,
    "RemoveOrderItem": RemoveOrderItemProcessor,
    "PlaceOrder": PlaceOrderProcessor,
    "ClickLink": ClickLinkProcessor,
    "Search": SearchProcessor,
    "ViewCategory": ViewCategoryProcessor
}


class RecommenderRegistry:
    def __init__(self):
        self.registry_map = {}

    def register(self, recommender_type, action_processor):
        self.registry_map[recommender_type] = action_processor
        action_processor.recommender_type = recommender_type

    def getRecommenderTypes(self):
        return self.registry_map.keys()

    def getProcessor(self, recommender_type):
        return self.registry_map.get(recommender_type, None)


#def ExcludeItemsProcessor(action_processor_class, items_to_exclude=[]):
#    class ExcludeItemsProcessor(BaseSimpleResultRecommendationProcessor):
#        action_name = "Recommendation"
#
#        def __init__(self, not_log_action=False):
#            BaseSimpleResultRecommendationProcessor.__init__(self, not_log_action)
#            self.not_log_action_for_child = not_log_action
#            self.not_log_action = True
#
#        def getTopN(self, site_id, args):
#            action_processor = self.action_processor_class(self.not_log_action_for_child)
#            topn = action_processor.getTopN(site_id, args)


class MatchAnyKeywordProcessor:
    def __init__(self, not_log_action=True):
        pass

    def getRecommendationResultFilter(self, site_id, args):
        return SimpleRecommendationResultFilter()

    def getTopNWithCache(self, site_id, args):
        keywords = args.get("keywords")
        try:
            amount = int(args.get("amount", "5"))
        except ValueError:
            raise ArgumentError("amount should be an integer.")
        s = S().indexes(es_search_functions.getESItemIndexName(site_id)).doctypes("item")
        query = es_search_functions.construct_or_query(keywords, delimiter=",")
        s = s.query_raw(query)
        s = s.filter(available=True)
        topn = [(item["item_id"], 1) for item in s[:amount]]
        return topn

def IfEmptyTryNextProcessor(argument_processor, action_processor_chain, post_process_filters=[], extra_args_to_log=[]):
    # TODO: action_processors should be of BaseSimpleResultRecommendationProcessor
    # TODO: should check the argument list against those action processors
    class IfEmptyTryNextProcessor(BaseSimpleResultRecommendationProcessor):
        action_name = "Recommendation"

        def getRecommendationLog(self, args, req_id, recommended_items):
            log = BaseSimpleResultRecommendationProcessor.getRecommendationLog(self, args, req_id, recommended_items)
            # FIXME fix the setting of recommender_type
            log["recommender_type"] = self.recommender_type
            for extra_arg in extra_args_to_log:
                log[extra_arg] = args[extra_arg]
            return log

        # TODO
        def getRecommendationResultFilter(self, site_id, args):
            return SimpleRecommendationResultFilter()

        def getTopNWithCache(self, site_id, args):
            topn = []
            for action_processor_class, extra_args_pipe in self.action_processor_chain:
                action_processor = action_processor_class(not_log_action=True)
                action_processor.recommender_type = self.recommender_type
                args = copy.deepcopy(args)
                for extra_args_filler in extra_args_pipe:
                    if isinstance(extra_args_filler, dict):
                        args.update(extra_args_filler)
                    else:
                        extra_args_filler(site_id, args)
                topn = action_processor.getTopNWithCache(site_id, args)
                if len(topn) > 0:
                    break
            for filter in post_process_filters:
                topn = filter(site_id, args, topn)
            return topn

    IfEmptyTryNextProcessor.ap = argument_processor
    IfEmptyTryNextProcessor.action_processor_chain = action_processor_chain
    return IfEmptyTryNextProcessor


def fill_category_id_by_item_id(site_id, args):
    item_id = args["item_id"]
    item = mongo_client.getItem(site_id, item_id)
    if item is not None:
        root_categories = [category for category in item["categories"] if category["parent_id"] == "null"]
        if len(root_categories) > 0:
            category_id = root_categories[0]["id"]
        else:
            category_id = None
    else:
        category_id = None
    args["category_id"] = category_id


def exclude_item_id_in_args(site_id, args, topn):
    item_id = args["item_id"]
    return [item for item in topn if item_id != item[0]]


recommender_registry = RecommenderRegistry()

recommender_registry.register("AlsoViewed",GetAlsoViewedProcessor)
recommender_registry.register("ByBrowsingHistory", GetByBrowsingHistoryProcessor)
recommender_registry.register("AlsoBought", GetAlsoBoughtProcessor)
recommender_registry.register("BoughtTogether", GetBoughtTogetherProcessor)
recommender_registry.register("UltimatelyBought", GetUltimatelyBoughtProcessor)
recommender_registry.register("ByPurchasingHistory", GetByPurchasingHistoryProcessor)
recommender_registry.register("ByShoppingCart", GetByShoppingCartProcessor)
recommender_registry.register("ByHotIndex", GetByHotIndexProcessor)
recommender_registry.register("CustomLists", GetCustomListsRecommend)
recommender_registry.register("/unit/home",
                              IfEmptyTryNextProcessor(
                                 ArgumentProcessor(
                                    (("user_id", True),
                                    ("ref", False),
                                    ("include_item_info", False),
                                    ("amount", True)
                                    )
                                  ),
                                  [
                                      (GetByBrowsingHistoryProcessor, {}),
                                      (GetByHotIndexProcessor, [{"hot_index_type": "by_viewed"}])
                                  ]
                              ))

recommender_registry.register("/unit/by_keywords",
                              IfEmptyTryNextProcessor(
                                 ArgumentProcessor(
                                    (("user_id", True),
                                    ("ref", False),
                                    ("include_item_info", False),
                                    ("amount", True),
                                    ("keywords", True),
                                    )
                                  ),
                                  [
                                      (MatchAnyKeywordProcessor, {}),
                                      (GetByBrowsingHistoryProcessor, {}),
                                      (GetByHotIndexProcessor, [{"hot_index_type": "by_viewed"}])
                                  ],
                              extra_args_to_log=["keywords"]
                              ))

recommender_registry.register("/unit/item",
                              IfEmptyTryNextProcessor(
                                 ArgumentProcessor(
                                    (("user_id", True),
                                     ("item_id", True),
                                    ("ref", False),
                                    ("include_item_info", False),
                                    ("amount", True)
                                    )
                                  ),
                                  [
                                      (GetAlsoViewedProcessor, {}),
                                      (GetByHotIndexProcessor, 
                                         [{"hot_index_type": "by_viewed"},
                                          fill_category_id_by_item_id]),
                                      (GetByHotIndexProcessor,
                                       {"hot_index_type": "by_viewed"}) # This is the backup plan in case the hot index of specific categories is also empty
                                  ],
                                  post_process_filters=[exclude_item_id_in_args]
                              ))

