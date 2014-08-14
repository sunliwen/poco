#encoding=utf8
import sys
import logging
import uuid

from django.shortcuts import render, redirect
from django.http import HttpResponse, HttpResponseBadRequest
from rest_framework.views import APIView
from rest_framework.response import Response
from common.poco_token_auth import PocoTokenAuthentication
from common.poco_token_auth import TokenMatchAPIKeyPermission

from action_processors import mongo_client
import action_processors

# TODO: config
#logging.basicConfig(format="%(asctime)s|%(levelname)s|%(name)s|%(message)s",
#                    level=logging.WARNING,
#                    datefmt="%Y-%m-%d %I:%M:%S")
logger = logging.getLogger(__name__)


class BaseAPIView(APIView):
    def process(self, request, response, site_id, args):
        raise NotImplemented

    def _extractArguments(self, request):
        # TODO: make it more secure
        return dict(kv for kv in request.GET.items())

    def get(self, request, format=None):
        args = self._extractArguments(request)
        api_key = args.get("api_key", None)
        api_key2site_id = mongo_client.getApiKey2SiteID()
        if api_key not in api_key2site_id:
            return Response({'code': 2, 'err_msg': 'no such api_key'})
        else:
            site_id = api_key2site_id[api_key]
            del args["api_key"]
            try:
                response = Response()
                response_data = self.process(request, response, site_id, args)
                response.data = response_data
                return response
            except action_processors.ArgumentError as e:
                return Response({"code": 1, "err_msg": e.message})

    def post(self, request, format=None):
        args = request.DATA
        api_key = args.get("api_key", None)
        api_key2site_id = mongo_client.getApiKey2SiteID()
        if api_key not in api_key2site_id:
            return Response({'code': 2, 'err_msg': 'no such api_key'})
        else:
            site_id = api_key2site_id[api_key]
            del args["api_key"]
            try:
                response = Response()
                response_data = self.process_post(request, response, site_id, args)
                response.data = response_data
                return response
            except action_processors.ArgumentError as e:
                return Response({"code": 1, "err_msg": e.message})


MAX_AGE = 109500 * 3600 * 24
def get_ptm_id(request, response):
    ptm_id = request.COOKIES.get("__ptmid", None)
    if not ptm_id:
        ptm_id = str(uuid.uuid4())  # TODO: how to store more useful information?
        response.set_cookie("__ptmid", value=ptm_id, max_age=MAX_AGE)
    return ptm_id


class SingleRequestAPIView(BaseAPIView):
    def getActionProcessor(self, args):
        raise NotImplemented

    def process(self, request, response, site_id, args):
        not_log_action = "not_log_action" in args
        processor_found, processor_class = self.getActionProcessor(args)
        if not processor_found:
            response = processor_class
            return response
        else:
            action_processor = processor_class(not_log_action)
            err_msg, args = action_processor.processArgs(args)
            if err_msg:
                return {"code": 1, "err_msg": err_msg}
            else:
                args["ptm_id"] = get_ptm_id(request, response)
                referer = request.META.get("HTTP_REFERER", "")
                args["referer"] = referer
                return action_processor.process(site_id, args)


class ItemsAPIView(BaseAPIView):
    authentication_classes = (PocoTokenAuthentication, )
    permission_classes = (TokenMatchAPIKeyPermission,)

    def getActionProcessor(self, args):
        return True, action_processors.UpdateItemProcessor

    def process_post(self, request, response, site_id, args):
        _, processor_class = self.getActionProcessor(args)
        action_processor = processor_class()

        type = args.get("type", None)
        if not (type in ("product", "multiple_products")):
            return {"code": 1, "err_msg": "'type' can only be 'product' or 'multiple_products'."}

        if type == "product":
            result = action_processor.process(site_id, args)
            action_processor.sendQueueProcessingTask()
            return result
        elif type == "multiple_products":
            items = args.get("items", [])
            if isinstance(items, list) and len(items) > 0:
                errors = []
                for item in items:
                    result = action_processor.process(site_id, item)
                    if result["code"] != 0:
                        result["item_id"] = item.get("item_id", None)
                        errors.append(result)
                if errors:
                    return {"code": 4, "errors": errors}
                else:
                    action_processor.sendQueueProcessingTask()
                    return {"code": 0}
            else:
                return {"code": 1, "err_msg": "'items' is expected to be a non empty list."}

class RecommenderAPIView(SingleRequestAPIView):
    def getDebugResponse(self, args, result):
        amount = int(args["amount"])
        if args.get("include_item_info", "yes") != "no":
            return {
                "topn": [
                    {"item_name": "星月--动物音乐敲击琴",
                     "price": "79.00",
                     "market_price": "118.00",
                     "image_link": "http://poco.tuijianbao.net/static/images/160x90.gif", #TODO
                     "score": 1.0,
                     "item_link": "http://example.com/products/3852023/",
                     "item_id": "3852023"
                     }
                ] * amount,
                "type": args["type"],
                "code": 0,
                "req_id": result["req_id"]
            }
        else:
            return {
                "topn": [
                    {
                     "score": 1.0,
                     "item_id": "3852023"
                     }
                ] * amount,
                "type": args["type"],
                "code": 0,
                "req_id": result["req_id"]
            }

    def process(self, request, response, site_id, args):
        debug = args.get("debug", "false") == "true"
        result = super(RecommenderAPIView, self).process(request, response, site_id, args)
        if result["code"] == 0:
            result["type"] = args["type"]
        if result["code"] == 0 and debug:
            return self.getDebugResponse(args, result)
        else:
            return result

    def getActionProcessor(self, args):
        type = args.get("type", None)
        action_processor = action_processors.recommender_registry.getProcessor(type)
        if action_processor is None:
            return False, {"code": 2, "err_msg": "no or invalid type"}
        else:
            return True, action_processor


class EventsAPIView(BaseAPIView):
    # these fields are not supposed to appear in the params
    DISALLOWED_PARAMS = set(["is_reserved", "behavior"])
    # these fields would not be recorded
    # NOT_RECORDED_PARAMS = set(["not_log_action"])
    # reserved event types. event types starts with "$" should be in this list
    # and event types not starts with "$" should not be in this list
    #RESERVED_EVENT_TYPES = set(action_processors.EVENT_TYPE2ACTION_PROCESSOR.keys() + ["$ClickLink"])

    def getActionProcessor(self, args):
        event_type = args.get("event_type", "")
        action_processor = action_processors.EVENT_TYPE2ACTION_PROCESSOR.get(event_type, None)
        if action_processor is None:
            action_processor = action_processors.CustomEventProcessor
        return True, action_processor

    def call_action_processor(self, request, response, site_id, args, not_log_action):
        processor_found, processor_class = self.getActionProcessor(args)
        if not processor_found:
            response = processor_class
            return response
        else:
            action_processor = processor_class(not_log_action)
            err_msg, args = action_processor.processArgs(args)
            if err_msg:
                return {"code": 1, "err_msg": err_msg}
            else:
                args["ptm_id"] = get_ptm_id(request, response)
                referer = request.META.get("HTTP_REFERER", "")
                args["referer"] = referer
                return action_processor.process(site_id, args)

    def process(self, request, response, site_id, args):
        not_log_action = "not_log_action" in args
        if not_log_action:
            del args["not_log_action"]
        event_type = args.get("event_type", "")
        
        for param in args.keys():
            if param in self.DISALLOWED_PARAMS:
                return {"code": 1, "err_msg": "param %s is not allowed. " % param}

        #if event_type.startswith("$") and not action_processors.EVENT_TYPE2ACTION_PROCESSOR.has_key(event_type):
        #    return {"code": 1, "err_msg": "Event types which start with '$' should be reserved event types. Please check the doc for a list of them."}
        #if not event_type.startswith("$") and action_processors.EVENT_TYPE2ACTION_PROCESSOR.has_key("$" + event_type):
        #    return {"code": 1, "err_msg": "Custom event types should not have same name of reserved ones. Please check the doc for a list of reserved event types."}

        return self.call_action_processor(request, response, site_id, args, not_log_action)

def recommended_item_redirect(request):
    if request.method == "GET":
        url = request.GET.get("url", None)
        api_key = request.GET.get("api_key", None)
        req_id = request.GET.get("req_id", None)
        item_id = request.GET.get("item_id", None)

        api_key2site_id = mongo_client.getApiKey2SiteID()
        if url is None or api_key not in api_key2site_id:
            # TODO, looks different from other error message, any way to make them consistent?
            response = HttpResponseBadRequest("wrong url")
        else:
            response = redirect(url)
            ptm_id = get_ptm_id(request, response)
            site_id = api_key2site_id[api_key]
            log_content = {
                "behavior": "ClickRec",
                "url": url,
                "req_id": req_id,
                "item_id": item_id,
                "site_id": site_id,
                "ptm_id": ptm_id
                }
            action_processors.logWriter.writeEntry(site_id, log_content)
        return response
