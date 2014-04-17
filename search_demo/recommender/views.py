#encoding=utf8
import sys
#sys.path.insert(0, "/Users/jacobfan/projects/PocoWeb/poco")
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
            'view-item': reverse('recommender-events-view-item', request=request, format=format),
        })


class ItemsAPIView(APIView):
    def get(self, request, format=None):
        pass

    def put(self, request, format=None):
        pass


class CommonActionProcessorWrapperAPIView(APIView):
    def handlePTMID(self):
        # TODO
        self.ptm_id = self.get_cookie("__ptmid")
        if not self.ptm_id:
            self.ptm_id = str(uuid.uuid4())
            self.set_cookie("__ptmid", self.ptm_id, expires_days=109500)




# TODO: note: difference between APIHandler and SingleRequestHandler
class EventsAPIView(APIView):
    MAX_AGE = 109500 * 3600 * 24

    def _extractArguments(self, request):
        # TODO: make it more secure
        return dict(kv for kv in request.GET.items())

    def get_ptm_id(self, request, response):
        ptm_id = request.COOKIES.get("__ptmid", None)
        if not ptm_id:
            ptm_id = str(uuid.uuid4())
            response.set_cookie("__ptmid", value=ptm_id, max_age=self.MAX_AGE)
        return ptm_id

    def process(self, request, response, site_id, args, action_processor):
        not_log_action = "not_log_action" in args

        processor = action_processor(not_log_action)
        err_msg, args = processor.processArgs(args)
        if err_msg:
            return {"code": 1, "err_msg": err_msg}
        else:
            args["ptm_id"] = self.get_ptm_id(request, response)
            referer = request.META.get("HTTP_REFERER", "")
            args["referer"] = referer
            return processor.process(site_id, args)

    def get(self, request, format=None):
        args = self._extractArguments(request)
        api_key = args.get("api_key", None)
        event_type = args.get("event_type", None)
        action_processor = action_processors.EVENT_TYPE2ACTION_PROCESSOR.get(event_type, None)
        if action_processor is None:
            return Response({"code": 2, "err_msg": "no or invalid event_type"})
        api_key2site_id = mongo_client.getApiKey2SiteID()
        if api_key not in api_key2site_id:
            return Response({'code': 2, 'err_msg': 'no such api_key'})
        else:
            site_id = api_key2site_id[api_key]
            del args["api_key"]
            try:
                response = Response()
                response_data = self.process(request, response, site_id, args, action_processor)
                response.data = response_data
                return response
            except action_processors.ArgumentError as e:
                return Response({"code": 1, "err_msg": e.message})
