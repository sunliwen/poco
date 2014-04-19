#encoding=utf8
import sys
import logging
import uuid

from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response

from action_processors import mongo_client
import action_processors

"""
PUT /1.6/items/<item_id>/
GET /1.6/items/<item_id>/
PUT /1.6/categories/

POST /1.6/events/view_item/
POST /1.6/events/add_favorite/
POST /1.6/events/remove_favorite/
POST /1.6/events/unlike/ (??)
POST /1.6/events/rate_item/
POST /1.6/events/add_order_item/
POST /1.6/events/remove_order_item/
POST /1.6/events/place_order/

GET /1.6/items/recommend/alsoViewed
GET /1.6/items/recommend/byBrowsingHistory
GET /1.6/items/recommend/AlsoBought
...
GET /1.6/redirect/

"""

# TODO: config 
#logging.basicConfig(format="%(asctime)s|%(levelname)s|%(name)s|%(message)s",
#                    level=logging.WARNING,
#                    datefmt="%Y-%m-%d %I:%M:%S")


class APIRootView(APIView):
    def get(self, request, format=None):
        return Response({
            'view-item': reverse('recommender-events', request=request, format=format),
        })


class ItemsAPIView(APIView):
    def get(self, request, format=None):
        pass

    def put(self, request, format=None):
        pass


class ItemsAPIView(APIView):
    def post(self, request, format=None):
        pass


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


class SingleRequestAPIView(BaseAPIView):
    MAX_AGE = 109500 * 3600 * 24
    
    def getActionProcessor(self, args):
        raise NotImplemented

    def get_ptm_id(self, request, response):
        ptm_id = request.COOKIES.get("__ptmid", None)
        if not ptm_id:
            ptm_id = str(uuid.uuid4())
            response.set_cookie("__ptmid", value=ptm_id, max_age=self.MAX_AGE)
        return ptm_id

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
                args["ptm_id"] = self.get_ptm_id(request, response)
                referer = request.META.get("HTTP_REFERER", "")
                args["referer"] = referer
                return action_processor.process(site_id, args)


class ItemsAPIView(BaseAPIView):
    def getActionProcessor(self, args):
        return True, action_processors.UpdateItemProcessor

    def process_post(self, request, response, site_id, args):
        _, processor_class = self.getActionProcessor(args)
        action_processor = processor_class()

        return action_processor.process(site_id, args)


class RecommenderAPIView(SingleRequestAPIView):
    def getDebugResponse(self, args, result):
        # for byEach... do 
        amount = int(args["amount"])
        if args.get("include_item_info", "yes") != "no":
            return {
                "topn": [
                    {"item_name": "星月--动物音乐敲击琴",
                     "price": "79.00",
                     "market_price": "118.00", 
                     "image_link": "http://image.example.com/blah.jpg", #TODO
                     "score": 1.0, 
                     "item_link": "http://example.com/products/3852023/", 
                     "item_id": "3852023"
                     }
                ] * amount,
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
                "code": 0,
                "req_id": result["req_id"]
            }

    def process(self, request, response, site_id, args):
        debug = args.get("debug", None) is not None
        result = super(RecommenderAPIView, self).process(request, response, site_id, args)
        if result["code"] == 0 and debug:
            return self.getDebugResponse(args, result)
        else:
            return result

    def getActionProcessor(self, args):
        type = args.get("type", None)
        action_processor = action_processors.RECOMMEND_TYPE2ACTION_PROCESSOR.get(type, None)
        if action_processor is None:
            return False, {"code": 2, "err_msg": "no or invalid type"}
        else:
            return True, action_processor


class EventsAPIView(SingleRequestAPIView):

    def getActionProcessor(self, args):
        event_type = args.get("event_type", None)
        action_processor = action_processors.EVENT_TYPE2ACTION_PROCESSOR.get(event_type, None)
        if action_processor is None:
            return False, {"code": 2, "err_msg": "no or invalid event_type"}
        else:
            return True, action_processor




