#encoding=utf8
#import sys
#sys.path.insert(0, ".")
import urllib
import urllib2
import urlparse
import json
from common import api_client

import os

#API_ROOT = "http://0.0.0.0:2222/api/v1.6/"
#api_key = "BB"
#api_key = "api_haoyaoshi"
#site_token = "blahblah"

#api_key = os.getenv('API_KEY', "6fad74ab")
#api_key = os.getenv("API_KEY", "fb86b045") # Default to testsite001 which is leyou data

#API_ROOT = "http://poco.ehaoyao.com/api/v1.6/"
#api_key = "4ad6af048ec"
#api_key = "6fad74ab" # haoyaoshitest
#api_key = "fb86b045"  #testsite001

#api_key = "a4b4dc8a" # poco_internal_test
#site_token = "d70127ab-aea0-473f-8b91-c48a2e5a6be4"


api_access = api_client.APIClient(API_ROOT)


def config(_API_ROOT=None, _api_key=None, _site_token=None):
    global API_ROOT
    global api_key
    global site_token
    if _API_ROOT is not None:
        API_ROOT = _API_ROOT
    if _api_key is not None:
        api_key = _api_key
    if _site_token is not None:
        site_token = _site_token


def test(function, expected_result, amount=50, *args):
    print "Testing:", function.__name__, args
    import time
    t1 = time.time()
    for i in range(amount):
        res = function(*args)
        if isinstance(expected_result, dict):
            assert res == expected_result, "Invalid result: %s, \n Expected: %s " % (res, expected_result)
        else:
            assert expected_result(res), "Invalid result: %s" % res
    t2 = time.time()
    print "%d times: %s" % (amount, t2-t1)
    if amount>1:
        print "avarage time: %s" % ((t2-t1)/amount)
    return res

def post_items():
    import test_products
    for product in test_products.PRODUCTS:
        body = product
        body["api_key"] = api_key
        res = api_access("private/items/", {"api_key": api_key}, body=body, 
                            headers={"Authorization": "Token %s" % site_token})
    return res

def post_items2(item):
    item["api_key"] = api_key
    res = api_access("private/items/", {"api_key": api_key}, body=item, 
                            headers={"Authorization": "Token %s" % site_token})
    return res

def post_search(q="", filters=None):
    body = {
                "api_key": api_key,
                "q": q
            }
    if filters:
        body["filters"] = filters
    res = api_access("public/search/", None,
            body=body)
    return res


def post_search2():
    res = api_access("public/search/", None,
            body={
                "api_key": api_key,
                "q": ""
            })
    return res


def post_search3(body):
    body["api_key"] = api_key
    res = api_access("public/search/", None,
            body=body)
    return res


def post_suggest():
    res = api_access("public/suggest/", None,
            body={
                "api_key": api_key,
                "q": "能"
            })
    return res

def recommend(type, params):
    params["api_key"] = api_key
    params["type"] = type
    res = api_access("public/recommender/", params)
    return res

def events(event_type, params):
    params["api_key"] = api_key
    params["event_type"] = event_type
    res = api_access("public/events/", params)
    return res


if __name__== "__main__":
    #test(post_search2, {}, 1)

    #test(post_items, {"code": 0}, 1)
    test(post_search, lambda x:x["errors"]==[""], 1, "", {"origin_place": ["0"]})
    import sys; sys.exit(0)

    #test(post_items, {"code": 0}, 1)
    #print test(post_search, lambda x:x["errors"]==[], 5)
    print test(post_suggest, lambda x:x["errors"]==[], 5)

    test(recommend, lambda x:x["code"]==0, 1, "AlsoViewed", {"user_id": "U1", "item_id": "I1", "amount": 5})
    test(recommend, lambda x:x["code"]==0, 1, "ByBrowsingHistory", {"user_id": "U1", "amount": 5})
    test(recommend, lambda x:x["code"]==0, 1, "AlsoBought", {"user_id": "U1", "item_id": "I1", "amount": 5})
    test(recommend, lambda x:x["code"]==0, 1, "BoughtTogether", {"user_id": "U1", "item_id": "I1", "amount": 5})
    test(recommend, lambda x:x["code"]==0, 1, "UltimatelyBought", {"user_id": "U1", "item_id": "I1", "amount": 5})
    test(recommend, lambda x:x["code"]==0, 1, "ByPurchasingHistory", {"user_id": "U1", "amount": 5})
    test(recommend, lambda x:x["code"]==0, 1, "ByShoppingCart", {"user_id": "U1", "amount": 5})

    test(events, {"code": 0}, 1, "ViewItem", {"user_id": "U1", "item_id": "I1", "amount": 5})
    test(events, {"code": 0}, 1, "AddFavorite", {"user_id": "U1", "item_id": "I1", "amount": 5})
    test(events, {"code": 0}, 1, "RemoveFavorite", {"user_id": "U1", "item_id": "I1", "amount": 5})
    test(events, {"code": 0}, 1, "RateItem", {"user_id": "U1", "item_id": "I1", "score": 3, "amount": 5})
    test(events, {"code": 0}, 1, "AddOrderItem", {"user_id": "U1", "item_id": "I1", "amount": 5})
    test(events, {"code": 0}, 1, "RemoveOrderItem", {"user_id": "U1", "item_id": "I1", "amount": 5})
