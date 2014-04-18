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
from django.conf import settings
import getopt
import urllib
import logging

from common.utils import smart_split

from mongo_client import MongoClient
from mongo_client import SimpleRecommendationResultFilter
from mongo_client import SameGroupRecommendationResultFilter

from es_client import es_index_item


#logging.basicConfig(format="%(asctime)s|%(levelname)s|%(name)s|%(message)s",
#                    level=logging.WARNING,
#                    datefmt="%Y-%m-%d %I:%M:%S")


def getConnection():
    if(settings.REPLICA_SET):
        return pymongo.MongoReplicaSetClient(settings.MONGODB_HOST, replicaSet=settings.REPLICA_SET)
    else:
        return pymongo.Connection(settings.MONGODB_HOST)


mongo_client = MongoClient(getConnection())

mongo_client.reloadApiKey2SiteID()

class HotViewListCache:
    def __init__(self, mongo_client):
        self.mongo_client = mongo_client

    def getHotViewList(self, site_id):
        # NOTE: disabled memcached cache currently
        return self.mongo_client.getHotViewList(site_id)
hot_view_list_cache = HotViewListCache(mongo_client)


# jquery serialize()  http://api.jquery.com/serialize/
# http://stackoverflow.com/questions/5784400/un-jquery-param-in-server-side-python-gae
# http://www.tsangpo.net/2010/04/24/unserialize-param-in-python.html

# TODO: referer;
# TODO: when to reload site ids.


class LogWriter:
    #def __init__(self):
    #    self.local_file = open(settings.local_raw_log_file, "a")

    #def closeLocalLog(self):
    #    self.local_file.close()

    def writeLineToLocalLog(self, site_id, line):
        #full_line = "%s:%s\n" % (site_id, line)
        #self.local_file.write(full_line)
        #self.local_file.flush()
        pass

    #def writeToLocalLog(self, site_id, content):
    #    local_content = copy.copy(content)
    #    local_content["created_on"] = repr(local_content["created_on"])
    #    line = json.dumps(local_content)
    #    self.writeLineToLocalLog(site_id, line)

    def writeEntry(self, site_id, content):
        content["created_on"] = datetime.datetime.now()
        if settings.PRINT_RAW_LOG:
            print "RAW LOG: site_id: %s, %s" % (site_id, content)
        #self.writeToLocalLog(site_id, content)
        mongo_client.writeLogToMongo(site_id, content)


def extractArguments(request):
    result = {}
    for key in request.arguments.keys():
        result[key] = request.arguments[key][0]
    return result


class ArgumentProcessor:
    def __init__(self, definitions):
        self.definitions = definitions

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
        err_msg = None
        result = {}
        for argument_name, is_required in self.definitions:
            if argument_name not in args:
                if is_required:
                    err_msg = "%s is required." % argument_name
                else:
                    result[argument_name] = None
            else:
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


class ActionProcessor:
    action_name = None

    def __init__(self, not_log_action=False):
        self.not_log_action = not_log_action

    def logAction(self, site_id, args, action_content, tjb_id_required=True):
        if not self.not_log_action:
            assert self.action_name != None
            if tjb_id_required:
                assert "ptm_id" in args
                action_content["tjbid"] = args["ptm_id"]
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


class ViewItemProcessor(ActionProcessor):
    action_name = "V"
    ap = ArgumentProcessor(
         (("item_id", True),
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
                  "tjbid": args["ptm_id"],
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


class UnlikeProcessor(ActionProcessor):
    action_name = "UNLIKE"
    ap = ArgumentProcessor(
        (
         ("item_id", True),
         ("user_id", False),
        )
    )

    def _process(self, site_id, args):
        self.logAction(site_id, args,
                        {"user_id": args["user_id"],
                         "item_id": args["item_id"]})
        return {"code": 0}


class AddFavoriteProcessor(ActionProcessor):
    action_name = "AF"
    ap = ArgumentProcessor(
        (
         ("item_id", True),
         ("user_id", False),
        )
    )

    def _process(self, site_id, args):
        self.logAction(site_id, args,
                        {"user_id": args["user_id"],
                         "item_id": args["item_id"]})
        return {"code": 0}


class RemoveFavoriteProcessor(ActionProcessor):
    action_name = "RF"
    ap = ArgumentProcessor(
         (("item_id", True),
         ("user_id", True),
        )
    )

    def _process(self, site_id, args):
        self.logAction(site_id, args,
                        {"user_id": args["user_id"],
                         "item_id": args["item_id"]})
        return {"code": 0}


class RateItemProcessor(ActionProcessor):
    action_name = "RI"
    ap = ArgumentProcessor(
         (("item_id", True),
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


class AddOrderItemProcessor(ActionProcessor):
    action_name = "ASC"
    ap = ArgumentProcessor(
        (
         ("user_id", True),
         ("item_id", True),
        )
    )

    def _process(self, site_id, args):
        self.logAction(site_id, args,
                        {"user_id": args["user_id"],
                         "item_id": args["item_id"]})
        return {"code": 0}


class RemoveOrderItemProcessor(ActionProcessor):
    action_name = "RSC"
    ap = ArgumentProcessor(
        (
         ("user_id", True),
         ("item_id", True),
        )
    )

    def _process(self, site_id, args):
        self.logAction(site_id, args,
                        {"user_id": args["user_id"],
                         "item_id": args["item_id"]})
        return {"code": 0}


class PlaceOrderProcessor(ActionProcessor):
    action_name = "PLO"
    ap = ArgumentProcessor(
        (
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
        mongo_client.updateUserPurchasingHistory(site_id=site_id, user_id=args["user_id"])
        return {"code": 0}


class UpdateCategoryProcessor(ActionProcessor):
    action_name = "UCat"
    ap = ArgumentProcessor(
         (("category_id", True),
         ("category_link", False),
         ("category_name", True),
         ("parent_categories", False)
        )
    )

    def _process(self, site_id, args):
        err_msg, args = self.ap.processArgs(args)
        if err_msg:
            return {"code": 1, "err_msg": err_msg}
        else:
            if args["parent_categories"] is None:
                args["parent_categories"] = []
            else:
                args["parent_categories"] = smart_split(args["parent_categories"], ",")
        mongo_client.updateCategory(site_id, args)
        return {"code": 0}


class UpdateItemProcessor(ActionProcessor):
    action_name = "UItem"
    ap = ArgumentProcessor(
         (
            ("item_id", True),
            ("item_link", True),
            ("item_name", True),

            ("description", False),
            ("image_link", False),
            ("price", False),
            ("market_price", False),
            ("categories", False),
            ("item_group", False)
        )
    )

    def _process(self, site_id, args):
        err_msg, args = self.ap.processArgs(args)
        if err_msg:
            return {"code": 1, "err_msg": err_msg}
        else:
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
            else:
                args["categories"] = smart_split(args["categories"], ",")
            if args["item_group"] is None:
                del args["item_group"]
            item = mongo_client.updateItem(site_id, args)
            es_index_item(item)
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
        full_url = settings.API_SERVER_PREFIX + "/1.6/redirect?" + param_str
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
                "tjbid": args["ptm_id"],
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
                "tjbid": args["ptm_id"],
                "recommended_items": recommended_items,
                "is_empty_result": len(recommended_items) == 0,
                "amount": args["amount"]}

    def postprocessTopN(self, topn):
        return

    def getTopN(self, site_id, args):
        raise NotImplemented

    def _getRef(self, args):
        if "ref" in args and args["ref"]:
            return "ref=" + str.strip(args["ref"])
        else:
            return None

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
        topn = self.getTopN(site_id, args)  # return TopN list

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
                ("browsing_history", False),
                ("include_item_info", False),  # no, not include; yes, include
                ("amount", True),
            )
        )

    def getRecommendationResultFilter(self, site_id, args):
        return SimpleRecommendationResultFilter()

    def getRecommendationLog(self, args, req_id, recommended_items):
        log = BaseSimpleResultRecommendationProcessor.getRecommendationLog(self, args, req_id, recommended_items)
        browsing_history = args["browsing_history"]
        if browsing_history == None:
            browsing_history = []
        else:
            browsing_history = browsing_history.split(",")
        log["browsing_history"] = browsing_history
        return log

    def getTopN(self, site_id, args):
        browsing_history = args["browsing_history"]
        if browsing_history == None:
            browsing_history = []
        else:
            browsing_history = browsing_history.split(",")
        topn = mongo_client.recommend_based_on_some_items(site_id, "V", browsing_history)
        if len(topn) == 0:
            topn = hot_view_list_cache.getHotViewList(site_id)
        return topn


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

    def getTopN(self, site_id, args):
        user_id = args["user_id"]
        if user_id == "null":
            return []
        else:
            return mongo_client.recommend_based_on_purchasing_history(site_id, user_id)


logWriter = LogWriter()


EVENT_TYPE2ACTION_PROCESSOR = {
    "view_item": ViewItemProcessor,
    "add_favorite": AddFavoriteProcessor,
    "remove_favorite": RemoveFavoriteProcessor,
    "unlike": UnlikeProcessor,
    "rate_item": RateItemProcessor
}


RECOMMEND_TYPE2ACTION_PROCESSOR = {
    "AlsoViewed": GetAlsoViewedProcessor,
    "ByBrowsingHistory": GetByBrowsingHistoryProcessor,
    "AlsoBought": GetAlsoBoughtProcessor,
    "BoughtTogether": GetBoughtTogetherProcessor,
    "UltimatelyBought": GetUltimatelyBoughtProcessor,
    "ByPurchasingHistory": GetByPurchasingHistoryProcessor,
    "ByShoppingCart": GetByShoppingCartProcessor,
    "ByEachBrowsedItem": GetByEachBrowsedItemProcessor,
    "ByEachPurchasedItem": GetByEachPurchasedItemProcessor
}

