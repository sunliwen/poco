#encoding=utf8
import urllib
import urllib2
import urlparse
import json

import os

API_ROOT = "http://0.0.0.0:2222/api/v1.6/"
api_key = os.getenv('API_KEY', "api_haoyaoshi")


def api_access(path, params, body=None):
    full_url = urlparse.urljoin(API_ROOT, path)
    if params:
        params_str = "?" + urllib.urlencode(params)
    else:
        params_str = ""
    full_url += params_str
    if body:
        req = urllib2.Request(full_url, data=json.dumps(body), 
                              headers={'Content-type': 'application/json'})
    else:
        req = urllib2.Request(full_url,
                              headers={'Content-type': 'application/json'})

    content = urllib2.urlopen(req).read()
    result = json.loads(content)
    return result


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
    print t2-t1

def post_items():
    import test_products
    for product in test_products.PRODUCTS:
        body = product
        body["api_key"] = api_key
        res = api_access("private/items/", {"api_key": api_key}, body=body)
    return res

def post_search():
    res = api_access("public/search/", None,
            body={
                "api_key": api_key,
                "q": "",
                "filters": {"categories": ["123"]}
            })
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


test(post_items, {"code": 0}, 1)
test(post_search, lambda x:x["errors"]=={}, 5)
test(post_suggest, lambda x:x["errors"]=={}, 5)

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
