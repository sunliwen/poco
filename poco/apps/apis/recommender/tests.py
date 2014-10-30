# encoding=utf8
import cgi
import urlparse
import copy
import json
from django.test import TestCase
from django.test.utils import override_settings
from django.core.urlresolvers import reverse
from django.core.cache import get_cache
from django.conf import settings
from django.http import HttpResponseRedirect, HttpResponseBadRequest
from common.test_utils import BaseAPITest
from common import site_manage_utils
from common import test_data1
from apps.apis.search import es_search_functions
from apps.apis.search.keyword_list import keyword_list

import tasks


class BaseRecommenderTest(BaseAPITest):

    def get_ptm_id(self, response):
        ptm_id_morsel = response.client.cookies.get("__ptmid", None)
        if ptm_id_morsel:
            ptm_id = ptm_id_morsel.value
            return ptm_id

    def get_item(self, item_id):
        c_items = self.mongo_client.getSiteDBCollection(self.TEST_SITE_ID, "items")
        return c_items.find_one({"item_id": item_id})

    def get_browsing_history_cache(self):
        from browsing_history_cache import BrowsingHistoryCache
        return BrowsingHistoryCache(self.mongo_client)

    def _viewItem(self, user_id, item_id, times=1):
        for i in range(times):
            response = self.api_get(reverse("recommender-events"),
                    data={"api_key": self.api_key,
                          "event_type": "ViewItem",
                          "user_id": user_id,
                          "item_id": item_id
                          })
        return response

    def _recommender(self, user_id, expected_status_code=200, **args):
        data = {"api_key": self.api_key,
                "user_id": user_id}
        data.update(args)
        response = self.api_get(reverse("recommender-recommender"),
                    data=data, expected_status_code=200)
        return response

    def _placeOrder(self, user_id, order_content):
        self.api_get(reverse("recommender-events"),
                data={"api_key": self.api_key,
                      "event_type": "PlaceOrder",
                      "user_id": user_id,
                      "order_content": order_content
                      })

    def get_last_n_raw_logs(self, n=1):
        c_raw_logs = self.mongo_client.getSiteDBCollection(self.TEST_SITE_ID, "raw_logs")
        rset = c_raw_logs.find().sort([("$natural", -1)])
        if n is not None:
            rset = rset.limit(n)
        raw_logs = [raw_log for raw_log in rset]
        return raw_logs

    def insert_viewed_ultimately_buys(self, item_id, total_views, viewedUltimatelyBuys):
        c_viewed_ultimately_buys = self.mongo_client.getSiteDBCollection(
                    self.TEST_SITE_ID, "viewed_ultimately_buys")
        for entry in viewedUltimatelyBuys:
            entry["percentage"] = entry["count"] / float(total_views)
        record = {"item_id": item_id, "total_views": total_views,
                  "viewedUltimatelyBuys": viewedUltimatelyBuys}
        c_viewed_ultimately_buys.insert(record)

    def insert_item_similarities(self, similarity_type, item_id, mostSimilarItems):
        c_item_similarities =  self.mongo_client.getSiteDBCollection(
                    self.TEST_SITE_ID, "item_similarities_%s" % similarity_type)
        record = {"item_id": item_id,
                  "mostSimilarItems": mostSimilarItems}
        c_item_similarities.insert(record)


#@override_settings(CELERY_EAGER_PROPAGATES_EXCEPTIONS=True,
#                   CELERY_ALWAYS_EAGER=True,
#                   BROKER_BACKEND='memory')
#class BenchmarkUpdateHotViewListTest(BaseRecommenderTest):
#    def test_hot_index_calculation_with_5000_items(self):
#        for i in range(5000):
#            self._viewItem("U1", "ID%s" % i)
#        import time
#        start_time = time.time()
#        tasks.update_hotview_list.delay(self.TEST_SITE_ID)
#        print time.time() - start_time





@override_settings(CELERY_EAGER_PROPAGATES_EXCEPTIONS=True,
                   CELERY_ALWAYS_EAGER=True,
                   BROKER_BACKEND='memory')
class EventsAPITest(BaseRecommenderTest):
    def _test_event(self, data, expected, referer="http://example.com/fake_page/"):
        initial_raw_log_num = len(self.get_last_n_raw_logs(n=None))
        data["api_key"] = self.api_key
        response = self.api_get(reverse("recommender-events"),
                    data=data,
                    **{"HTTP_REFERER": referer})
        raw_logs = self.get_last_n_raw_logs(n=None)
        self.assertEqual(response.data["code"], 0, "Invalid response: %s" % response.data)
        self.assertEqual(len(raw_logs), initial_raw_log_num + 1)
        #print raw_logs[0]
        self.assertSeveralKeys(raw_logs[0],
                expected)
        self.assertEquals(raw_logs[0]["ptm_id"], self.get_ptm_id(response))
        self.assertEquals(raw_logs[0].has_key("created_on"), True)
        self.assertEquals(raw_logs[0]["referer"], referer)

    def _test_invalid_event0(self, data):
        initial_raw_log_num = len(self.get_last_n_raw_logs(n=None))
        data["api_key"] = self.api_key
        response = self.api_get(reverse("recommender-events"),
                    data=data)
        raw_logs = self.get_last_n_raw_logs(n=None)
        self.assertEqual(response.data["code"], 1)
        self.assertEqual(len(raw_logs), initial_raw_log_num)

    def _test_invalid_event(self, data, missing_keys=[], invalid_keys=[]):
        for missing_key in missing_keys:
            self._test_invalid_event0(self._remove_key(data, missing_key))

        for invalid_key, invalid_value in invalid_keys:
            self._test_invalid_event0(self._change_key(data, invalid_key, invalid_value))

    def _remove_key(self, dict, key):
        new_dict = copy.deepcopy(dict)
        del new_dict[key]
        return new_dict

    def _change_key(self, dict, key, value):
        new_dict = copy.deepcopy(dict)
        new_dict[key] = value
        return new_dict

    def _test_ViewItem(self):
        data = {
              "event_type": "ViewItem",
              "user_id": "U1",
              "item_id": "I1"
              }
        expected = {
                    "behavior": "V",
                    "user_id": "U1",
                    "item_id": "I1",
                    "event_type": "ViewItem",
                    "is_reserved": True
                }
        self._test_event(data, expected)
        self._test_invalid_event(data, missing_keys=["user_id", "item_id"])

    def _test_AddFavorite(self):
        data = {"event_type": "AddFavorite",
                  "user_id": "U1",
                  "item_id": "I1"
                }
        expected = {
                    "behavior": "AF",
                    "user_id": "U1",
                    "item_id": "I1",
                    "event_type": "AddFavorite",
                    "is_reserved": True
                }
        self._test_event(data, expected)
        self._test_invalid_event(data, missing_keys=["user_id", "item_id"])

    def _test_RemoveFavorite(self):
        data = {"event_type": "RemoveFavorite",
                  "user_id": "U1",
                  "item_id": "I1"
                }
        expected = {
                    "behavior": "RF",
                    "user_id": "U1",
                    "item_id": "I1",
                    "event_type": "RemoveFavorite",
                    "is_reserved": True
                }
        self._test_event(data, expected)
        self._test_invalid_event(data, missing_keys=["user_id", "item_id"])

    def _test_Unlike(self):
        data = {"event_type": "Unlike",
                  "user_id": "U1",
                  "item_id": "I1"
                }
        expected = {
                    "behavior": "UNLIKE",
                    "user_id": "U1",
                    "item_id": "I1",
                  "event_type": "Unlike",
                  "is_reserved": True
                }
        self._test_event(data, expected)
        self._test_invalid_event(data, missing_keys=["user_id", "item_id"])

    def _test_RateItem(self):
        data = {"event_type": "RateItem",
                  "user_id": "U1",
                  "item_id": "I1",
                  "score": 3
                }
        expected = {
                    "behavior": "RI",
                    "user_id": "U1",
                    "item_id": "I1",
                    "score": '3',
                  "event_type": "RateItem",
                  "is_reserved": True
                }
        self._test_event(data, expected)
        self._test_invalid_event(data, missing_keys=["user_id", "item_id", "score"])

    def _test_AddOrderItem(self):
        data = {"event_type": "AddOrderItem",
                  "user_id": "U1",
                  "item_id": "I1",
                }
        expected = {
                    "behavior": "ASC",
                    "user_id": "U1",
                    "item_id": "I1",
                    "event_type": "AddOrderItem",
                    "is_reserved": True
                }
        self._test_event(data, expected)
        self._test_invalid_event(data, missing_keys=["user_id", "item_id"])

    def _test_RemoveOrderItem(self):
        data = {"event_type": "RemoveOrderItem",
                  "user_id": "U1",
                  "item_id": "I1",
                }
        expected = {
                    "behavior": "RSC",
                    "user_id": "U1",
                    "item_id": "I1",
                  "event_type": "RemoveOrderItem",
                  "is_reserved": True
                }
        self._test_event(data, expected)
        self._test_invalid_event(data, missing_keys=["user_id", "item_id"])

    def _test_ClickLink_SearchResult(self):
        data = {"event_type": "ClickLink",
                  "user_id": "U1",
                  "link_type": "SearchResult",
                  "url": "http://example.com/blahblah/",
                  "q": "haha",
                  "categories": "1,2,3",
                  "page": "1",
                  "item_id": "I255"
                }
        expected = {
                    "behavior": "Event",
                    "user_id": "U1",
                    "event_type": "ClickLink",
                    "link_type": "SearchResult",
                    "url": "http://example.com/blahblah/",
                    "is_reserved": True,
                    "q": "haha",
                    "categories": "1,2,3",
                    "page": "1",
                    "item_id": "I255"
                }
        self._test_event(data, expected)
        self._test_event(self._change_key(data, "item_id", "I5"),
                         self._change_key(expected, "item_id", "I5"))
        self._test_event(self._change_key(data, "custom_field2", "abc"),
                         self._change_key(expected, "custom_field2", "abc"))
        self._test_invalid_event(data,
                         missing_keys=["user_id", "link_type", "url", "q", "page", "item_id", "categories"])

    def _test_ClickLink_RecommendationResult(self):
        data = {"event_type": "ClickLink",
                  "user_id": "U1",
                  "link_type": "RecommendationResult",
                  "url": "http://example.com/blahblah/",
                  "req_id": "blah-blah",
                  "item_id": "I255"
                }
        expected = {
                    "behavior": "Event",
                    "user_id": "U1",
                    "event_type": "ClickLink",
                    "link_type": "RecommendationResult",
                    "url": "http://example.com/blahblah/",
                    "is_reserved": True,
                    "req_id": "blah-blah",
                    "item_id": "I255"
                }
        self._test_event(data, expected)
        self._test_event(self._change_key(data, "item_id", "I5"),
                         self._change_key(expected, "item_id", "I5"))
        self._test_event(self._change_key(data, "custom_field2", "abc"),
                         self._change_key(expected, "custom_field2", "abc"))
        self._test_invalid_event(data,
                         missing_keys=["user_id", "link_type", "url", "req_id", "item_id"])

    def _test_ClickLink_HotKeyword(self):
        data = {"event_type": "ClickLink",
                  "user_id": "U1",
                  "link_type": "HotKeyword",
                  "url": "http://example.com/blahblah/",
                  "keyword": "ganmao"
                }
        expected = {
                    "behavior": "Event",
                    "user_id": "U1",
                    "event_type": "ClickLink",
                    "link_type": "HotKeyword",
                    "url": "http://example.com/blahblah/",
                    "is_reserved": True,
                    "keyword": "ganmao"
                }
        self._test_event(data, expected)
        self._test_event(self._change_key(data, "item_id", "I5"),
                         self._change_key(expected, "item_id", "I5"))
        self._test_event(self._change_key(data, "custom_field2", "abc"),
                         self._change_key(expected, "custom_field2", "abc"))
        self._test_invalid_event(data,
                         missing_keys=["user_id", "link_type", "url", "keyword"])

    def _test_Search(self):
        data = {"event_type": "Search",
                  "user_id": "U1",
                  "categories": "1,2,3",
                  "q": "haha"
                }
        expected = {
                    "behavior": "Event",
                    "user_id": "U1",
                    "event_type": "Search",
                    "categories": "1,2,3",
                    "q": "haha",
                    "is_reserved": True
                }
        self._test_event(data, expected)
        self._test_invalid_event(data, missing_keys=["user_id", "q"])

    def _test_ViewCategory(self):
        data = {"event_type": "ViewCategory",
                  "user_id": "U1",
                  "categories": "1,2,3"
                }
        expected = {
                    "behavior": "Event",
                    "user_id": "U1",
                    "event_type": "ViewCategory",
                    "categories": "1,2,3",
                    "is_reserved": True
                }
        self._test_event(data, expected)
        self._test_invalid_event(data, missing_keys=["user_id", "categories"])

    def _test_PlaceOrder(self):
        data = {"event_type": "PlaceOrder",
                  "user_id": "U1",
                  "order_content": "I1,3.5,2|I2,5.5,1",
                  "order_id": "357755"
                }
        expected = {
                    "behavior": "PLO",
                    "user_id": "U1",
                    "order_id": "357755",
                    "order_content": [{u'item_id': u'I1', u'price': u'3.5', u'amount': u'2'},
                                    {u'item_id': u'I2', u'price': u'5.5', u'amount': u'1'}],
                  "event_type": "PlaceOrder",
                  "is_reserved": True
                }
        self._test_event(data, expected)
        self._test_invalid_event(data, missing_keys=["user_id", "order_content"])

    def test_events(self):
        self._test_ViewItem()
        self._test_AddFavorite()
        self._test_RemoveFavorite()
        self._test_Unlike()
        self._test_RateItem()
        self._test_AddOrderItem()
        self._test_RemoveOrderItem()
        self._test_ClickLink_SearchResult()
        self._test_ClickLink_RecommendationResult()
        self._test_ClickLink_HotKeyword()
        self._test_Search()
        self._test_ViewCategory()
        self._test_PlaceOrder()

    def test_custom_events(self):
        # TODO user_id is expected.
        data = {"event_type": "ItemTaste",
                  "user_id": "U5",
                  "item_id": "I255",
                  "taste_good": "yes",
                  "comment": "That's fantastic!"
                }
        expected = {
                    "behavior": "Event",
                    "user_id": "U5",
                    "item_id": "I255",
                    "taste_good": "yes",
                    "comment": "That's fantastic!",
                  "event_type": "ItemTaste",
                  "is_reserved": False
                }
        self._test_event(data, expected)

        self._test_invalid_event(data, missing_keys=["user_id"])


@override_settings(CELERY_EAGER_PROPAGATES_EXCEPTIONS=True,
                   CELERY_ALWAYS_EAGER=True,
                   BROKER_BACKEND='memory')
class RecommenderRedirectTest(BaseRecommenderTest):
    def test_recommender_redirect(self):
        c_raw_logs = self.mongo_client.getSiteDBCollection(self.TEST_SITE_ID, "raw_logs")
        redirect_path = reverse("recommender-redirect")
        self.assertEqual(c_raw_logs.count(), 0)
        # Test invalid requests
        invalid_request_data_list = [
            {"url": "http://example.com/blah",
                  "api_key": "INVALID_API_KEY",
                  "req_id": "REQ1100",
                  "item_id": "I123"},
            {"api_key": self.api_key,
                  "req_id": "REQ1100",
                  "item_id": "I123"},
        ]
        for invalid_request_data in invalid_request_data_list:
            response = self.client.get(redirect_path,
                            data=invalid_request_data)
            self.assertIsInstance(response, HttpResponseBadRequest)
            self.assertEqual(c_raw_logs.count(), 0)

        # valid request
        response = self.client.get(
                  redirect_path,
                  data={"url": "http://example.com/blah",
                  "api_key": self.api_key,
                  "req_id": "REQ1100",
                  "item_id": "I123"})

        self.assertIsInstance(response, HttpResponseRedirect)
        self.assertEqual(c_raw_logs.count(), 1)
        self.assertSeveralKeys(c_raw_logs.find_one(),
                               {"behavior": "ClickRec",
                                "url": "http://example.com/blah",
                                "req_id": "REQ1100",
                                "item_id": "I123",
                                "site_id": self.TEST_SITE_ID,
                                "ptm_id": self.get_ptm_id(response)})


@override_settings(CELERY_EAGER_PROPAGATES_EXCEPTIONS=True,
                   CELERY_ALWAYS_EAGER=True,
                   BROKER_BACKEND='memory')
class ItemsAPITest(BaseRecommenderTest):
    #def test_items_with_tags(self):
    #    raise NotImplemented

    #def test_no_categories_provided(self):
    #    raise NotImplemented

    def _assertKWList(self, list_type, expected):
        self.assertEqual(set([(keyword_record["keyword"], keyword_record["count"])
                for keyword_record in self.mongo_client.getSuggestKeywordList(self.TEST_SITE_ID, list_type)]), expected)

    def test_updating_of_suggest_keyword_list(self):
        c_items = self.mongo_client.getSiteDBCollection(self.TEST_SITE_ID, "items")
        self.assertEqual(c_items.count(), 0)
        self.assertEqual(self.mongo_client.getSuggestKeywordList(self.TEST_SITE_ID).count(), 0)
        item = {
            "api_key": self.api_key,
            "type": "product",
            "available": True,
            "item_id": "I888",
            "item_name": u"能恩奶粉",
            "item_link": "http://example.com/"
        }
        response = self.postItem(item)
        self.assertEqual(response.data["code"], 0, "Unexpected response: %s" % response.data)

        item = {
            "api_key": self.api_key,
            "type": "product",
            "available": True,
            "item_id": "I889",
            "item_name": u"能恩超级",
            "item_link": "http://example.com/"
        }
        response = self.postItem(item)
        self.assertEqual(response.data["code"], 0, "Unexpected response: %s" % response.data)

        self.assertEqual(es_search_functions.getItemById(self.TEST_SITE_ID, "I888")["_source"]["keywords"], [u"能恩", u"奶粉"])

        self._assertKWList(keyword_list.WHITE_LIST, set())
        self._assertKWList(keyword_list.BLACK_LIST, set())
        self._assertKWList(keyword_list.UNIDENTIFIED_LIST, set([(u"能恩", 2), (u"奶粉", 1), (u"超级", 1)]))

        # let's move 能恩 as white list
        keyword_list.markKeywordsAsWhiteListed(self.TEST_SITE_ID, ["能恩"])
        self._assertKWList(keyword_list.WHITE_LIST, set([(u"能恩", 2)]))
        self._assertKWList(keyword_list.BLACK_LIST, set())
        self._assertKWList(keyword_list.UNIDENTIFIED_LIST, set([(u"奶粉", 1), (u"超级", 1)]))
        self.assertEqual(es_search_functions.getItemById(self.TEST_SITE_ID, "I888")["_source"]["keywords"], [u"能恩", u"奶粉"])
        # move 奶粉 into black list
        keyword_list.markKeywordsAsBlackListed(self.TEST_SITE_ID, ["奶粉"])
        self._assertKWList(keyword_list.WHITE_LIST, set([(u"能恩", 2)]))
        self._assertKWList(keyword_list.BLACK_LIST, set([(u"奶粉", 1)]))
        self._assertKWList(keyword_list.UNIDENTIFIED_LIST, set([(u"超级", 1)]))
        self.assertEqual(es_search_functions.getItemById(self.TEST_SITE_ID, "I888")["_source"]["keywords"], [u"能恩", u"奶粉"])
        self.assertEqual(es_search_functions.getItemById(self.TEST_SITE_ID, "I889")["_source"]["keywords"], [u"能恩", u"超级"])

    def test_invalid_properties_format_in_posted_items(self):
        # TODO full test of properties type
        c_items = self.mongo_client.getSiteDBCollection(self.TEST_SITE_ID, "items")
        self.assertEqual(c_items.count(), 0)
        # an item with wrong category format
        item_wrong_brand = {
            "type": "product",
            "available": True,
            "item_id": "I200",
            "item_name": "Milk",
            "item_link": "http://example.com/I123/",
            "categories": [
                {"type": "category",
                 "id": "2",
                 "name": "cat1",
                 "parent_id": "3"
                }
            ]
        }
        item_wrong_brand["api_key"] = self.api_key
        response = self.api_post(reverse("recommender-items"), data=item_wrong_brand,
                                  expected_status_code=200,
                                  **{"HTTP_AUTHORIZATION": "Token %s" % self.site_token})
        self.assertEqual(response.data["code"], 1)
        self.assertEqual(c_items.count(), 0)

    def test_authentication_and_permission(self):
        # let's create another site
        other_site_record = self.initSite("site_for_other_purpose")

        c_items = self.mongo_client.getSiteDBCollection(self.TEST_SITE_ID, "items")
        self.assertEqual(c_items.count(), 0)
        # Let's post an item with wrong site_token
        sample_item = test_data1.getItems(None)[0]
        sample_item["api_key"] = self.api_key
        response = self.api_post(reverse("recommender-items"), data=sample_item,
                                  expected_status_code=403,
                                  **{"HTTP_AUTHORIZATION": "Token WRONG_TOKEN"})
        self.assertEqual(c_items.count(), 0)

        # If we post with a correct site_token but wrong api_key
        sample_item["api_key"] = other_site_record["api_key"]
        response = self.api_post(reverse("recommender-items"), data=sample_item,
                                  expected_status_code=403,
                                  **{"HTTP_AUTHORIZATION": "Token %s" % self.site_token})
        self.assertEqual(c_items.count(), 0)

        # The correct posting of items
        sample_item["api_key"] = self.api_key
        response = self.api_post(reverse("recommender-items"), data=sample_item,
                                  expected_status_code=200,
                                  **{"HTTP_AUTHORIZATION": "Token %s" % self.site_token}
                                  )
        self.assertEqual(c_items.count(), 1)


    def _test_multiple_products_posting_invalid_items(self, c_items, items_to_post):
        # Invalid items should be rejected wholely
        invalid_items1 = copy.deepcopy(items_to_post)
        del invalid_items1[0]["item_name"]
        invalid_items1[1]["brand"] = "blah"
        data = {"type": "multiple_products",
                "api_key": self.api_key,
                "items": invalid_items1}
        response = self.api_post(reverse("recommender-items"), data=data,
                                  expected_status_code=200,
                                  **{"HTTP_AUTHORIZATION": "Token %s" % self.site_token}
                                  )
        self.assertEqual(response.data["code"], 4)
        self.assertEqual(len(response.data["errors"]), 2)
        self.assertEqual(c_items.count(), 0)

    def _test_multiple_products_posting_valid_items(self, c_items, items_to_post):
        # Valid Items
        data = {"type": "multiple_products",
                "api_key": self.api_key,
                "items": items_to_post}

        response = self.api_post(reverse("recommender-items"), data=data,
                                  expected_status_code=200,
                                  **{"HTTP_AUTHORIZATION": "Token %s" % self.site_token}
                                  )
        self.assertEqual(response.data["code"], 0)
        self.assertEqual(c_items.count(), len(items_to_post))

    def test_multiple_products_posting(self):
        c_items = self.mongo_client.getSiteDBCollection(self.TEST_SITE_ID, "items")
        self.assertEqual(c_items.count(), 0)

        items_to_post = test_data1.getItems(None)
        self.assertGreater(len(items_to_post), 1)

        self._test_multiple_products_posting_invalid_items(c_items, items_to_post)
        self._test_multiple_products_posting_valid_items(c_items, items_to_post)

    def test_stock(self):
        c_items = self.mongo_client.getSiteDBCollection(self.TEST_SITE_ID, "items")
        self.assertEqual(c_items.count(), 0)
        item_to_post = test_data1.getItems(["I123"])[0]
        item_to_post["api_key"] = self.api_key

        stock1 = 5
        item_to_post["stock"] = stock1
        response = self.api_post(reverse("recommender-items"), data=item_to_post,
                                  expected_status_code=200,
                                  **{"HTTP_AUTHORIZATION": "Token %s" % self.site_token}
                                  )
        self.assertEqual(response.data["code"], 0)
        items = [item for item in c_items.find({})]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["stock"], stock1)

        stock2 = "0"
        item_to_post["stock"] = stock2
        response = self.api_post(reverse("recommender-items"), data=item_to_post,
                                  expected_status_code=200,
                                  **{"HTTP_AUTHORIZATION": "Token %s" % self.site_token}
                                  )
        self.assertEqual(response.data["code"], 1)
        items = [item for item in c_items.find({})]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["stock"], stock1)

        del item_to_post["stock"]
        response = self.api_post(reverse("recommender-items"), data=item_to_post,
                                  expected_status_code=200,
                                  **{"HTTP_AUTHORIZATION": "Token %s" % self.site_token}
                                  )
        self.assertEqual(response.data["code"], 0)
        items = [item for item in c_items.find({})]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["stock"], 0)

    def test_prescription_type(self):
        c_items = self.mongo_client.getSiteDBCollection(self.TEST_SITE_ID, "items")
        self.assertEqual(c_items.count(), 0)
        item_to_post = test_data1.getItems(["I123"])[0]
        item_to_post["api_key"] = self.api_key

        prescription_type = 8627
        item_to_post["prescription_type"] = prescription_type
        response = self.api_post(reverse("recommender-items"), data=item_to_post,
                                  expected_status_code=200,
                                  **{"HTTP_AUTHORIZATION": "Token %s" % self.site_token}
                                  )
        self.assertEqual(response.data["code"], 0)
        items = [item for item in c_items.find({})]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["prescription_type"], prescription_type)

        self.refreshSiteItemIndex(self.TEST_SITE_ID)
        self.clearCaches()
        # also search it
        res = self.client.post(reverse("products-search"),
                         content_type="application/json",
                         data=json.dumps({"q": "",
                                          "filters": {"prescription_type": [prescription_type]},
                                          "api_key": self.api_key}))
        self.assertEqual(res.data["errors"], [])
        self.assertEqual(res.data["records"][0]["item_id"], "I123")
        self.assertEqual(res.data["records"][0]["prescription_type"], prescription_type)


@override_settings(CELERY_EAGER_PROPAGATES_EXCEPTIONS=True,
                   CELERY_ALWAYS_EAGER=True,
                   BROKER_BACKEND='memory')
class RecommenderTest(BaseRecommenderTest):
    def setUp(self):
        super(RecommenderTest, self).setUp()
        self.postItems(test_data1, None)

    def _test_recommenders_with_one_item_id_as_input(self, action_name, recommend_type):
        self.insert_item_similarities(action_name, "I123",
                    [["I124", 0.9725],
                     ["I125", 0.8023]])
        self.insert_item_similarities(action_name, "I124",
                    [["I125", 0.9725],
                     ["I126", 0.7050]])

        # Missing item_id
        response = self._recommender("U1", type=recommend_type, amount=5)
        self.assertEqual(response.data["code"], 1)
        # items without similarities
        response = self._recommender("U1", type=recommend_type, item_id="I5000", amount=5)
        self.assertEqual([item["item_id"] for item in response.data["topn"]], [])
        response = self._recommender("U1", type=recommend_type, item_id="I123", amount=5)
        self.assertEqual([item["item_id"] for item in response.data["topn"]], ["I124", "I125"])
        for item in response.data["topn"]:
            self.assertEqual(item.has_key("stock"), True)

        # if we change the recommender order, the result will be reordered
        self.mongo_client.updateRecommendStickLists(self.TEST_SITE_ID,
                                                    recommend_type,
                                                    ['I126', 'I125'])
        response = self._recommender("U1", type=recommend_type, item_id="I123", amount=5)
        self.assertEqual([item["item_id"] for item in response.data["topn"]],
                         ["I126", "I125", "I124"])
        for item in response.data["topn"]:
            self.assertEqual(item.has_key("stock"), True)
        # if we make I124 stock to 0
        item = test_data1.getItems(item_ids=["I124"])[0]
        item["stock"] = 0
        response = self.postItem(item)
        self.assertEqual(response.data["code"], 0, "Unexpected response: %s" % response.data)
        response = self._recommender("U1", type=recommend_type, item_id="I123", amount=5)
        self.assertEqual([item["item_id"] for item in response.data["topn"]],
                         ["I126", "I125"])
        # turn stock back
        ## let's turn stock back
        item = test_data1.getItems(item_ids=["I124"])[0]
        item["stock"] = 8
        response = self.postItem(item)
        self.assertEqual(response.data["code"], 0, "Unexpected response: %s" % response.data)
        self.assertEqual(self.get_item("I124")["stock"], 8)

        # if we make I124 not available
        item = test_data1.getItems(item_ids=["I124"])[0]
        item["available"] = False
        response = self.postItem(item)
        self.assertEqual(response.data["code"], 0, "Unexpected response: %s" % response.data)
        response = self._recommender("U1", type=recommend_type, item_id="I123", amount=5)
        self.assertEqual([item["item_id"] for item in response.data["topn"]],
                         ["I126", "I125"])
        # turn stock back
        ## let's turn stock back
        item = test_data1.getItems(item_ids=["I124"])[0]
        item["available"] = True
        response = self.postItem(item)
        self.assertEqual(response.data["code"], 0, "Unexpected response: %s" % response.data)
        self.assertEqual(self.get_item("I124")["available"], True)

    def test_also_viewed(self):
        self._test_recommenders_with_one_item_id_as_input("V", "AlsoViewed")

    def test_also_bought(self):
        self._test_recommenders_with_one_item_id_as_input("PLO", "AlsoBought")

    def test_bought_together(self):
        self._test_recommenders_with_one_item_id_as_input("BuyTogether", "BoughtTogether")

    def test_ultimately_bought(self):
        self.insert_viewed_ultimately_buys("I123", 100,
                    [{"item_id": "I126", "count": 5},
                     {"item_id": "I125", "count": 3}])
        self.insert_viewed_ultimately_buys("I124", 150,
                    [{"item_id": "I125", "count": 8},
                     {"item_id": "I124", "count": 3}])

        # Missing item_id
        response = self._recommender("U1", type="UltimatelyBought", amount=5)
        self.assertEqual(response.data["code"], 1)
        # items without similarities
        response = self._recommender("U1", type="UltimatelyBought", item_id="I5000", amount=5)
        self.assertEqual([item["item_id"] for item in response.data["topn"]], [])
        # item I123
        response = self._recommender("U1", type="UltimatelyBought", item_id="I123", amount=5)
        self.assertEqual([item["item_id"] for item in response.data["topn"]], ["I126", "I125"])

    def test_by_purchasing_history(self):
        self.insert_item_similarities("PLO", "I123",
                    [["I124", 0.9725],
                     ["I125", 0.8023]])
        self.insert_item_similarities("PLO", "I124",
                    [["I125", 0.9720],
                     ["I126", 0.7050]])

        # No purchasing history, should return []
        response = self._recommender("U1", type="ByPurchasingHistory", amount=5)
        self.assertEqual([item["item_id"] for item in response.data["topn"]], [])

        # Buy something
        self._placeOrder("U1", "I123,3.50,2")
        self._placeOrder("U1", "I124,15.50,1")

        # should recommend something
        response = self._recommender("U1", type="ByPurchasingHistory", amount=5)
        self.assertEqual([item["item_id"] for item in response.data["topn"]], ["I125", "I126"])

    def test_by_shopping_cart(self):
        response = self._recommender("U1", type="ByShoppingCart", shopping_cart="I123,I124", amount=5)
        self.assertEqual(response.data["topn"], [])

        self.insert_item_similarities("BuyTogether", "I123",
                    [["I124", 0.9725],
                     ["I125", 0.8023]])
        self.insert_item_similarities("BuyTogether", "I124",
                    [["I125", 0.9720]])

        self.insert_item_similarities("PLO", "I123",
                    [["I124", 0.8725],
                     ["I126", 0.7023]])

        response = self._recommender("U1", type="ByShoppingCart", amount=5)
        self.assertEqual(response.data["topn"], [])

        response = self._recommender("U1", type="ByShoppingCart", shopping_cart="I123,I124", amount=5)
        self.assertEqual([item["item_id"] for item in response.data["topn"]], ["I125", "I126"])


@override_settings(CELERY_EAGER_PROPAGATES_EXCEPTIONS=True,
                   CELERY_ALWAYS_EAGER=True,
                   BROKER_BACKEND='memory')
class GetByBrowsingHistoryTest(BaseRecommenderTest):
    def setUp(self):
        super(GetByBrowsingHistoryTest, self).setUp()
        self.postItems(test_data1, None)

    def test_by_browsing_history_not_returning_topn(self):
        # We have no browsing history and no hot index
        # So we don't have recommendation from ByBrowsingHistory
        response = self._recommender("U1", type="ByBrowsingHistory", amount=5)
        self.assertEqual([item["item_id"] for item in response.data["topn"]],
                        [])
        # If there is some by_viewed hot index
        # let's view some items
        self._viewItem("U2", "I123", 3)
        self._viewItem("U2", "I124", 2)
        self._viewItem("U3", "I125", 1)
        self._viewItem("U5", "I126", 5)

        tasks.update_hotview_list.delay(self.TEST_SITE_ID)
        get_cache("default").clear()

        # now we have topns from ByHotIndex
        response = self.api_get(reverse("recommender-recommender"),
            data={"api_key": self.api_key,
                  "type": "ByHotIndex",
                  "hot_index_type": "by_viewed",
                  "user_id": "U1",
                  "amount": 5
                  })

        self.assertEqual(response.data["code"], 0)
        self.assertEqual([item["item_id"] for item in response.data["topn"]],
                         ["I126", "I123", "I124", "I125"])

        # But the ByBrowsingHistory still should return no result
        response = self._recommender("U1", type="ByBrowsingHistory", amount=5)
        self.assertEqual([item["item_id"] for item in response.data["topn"]],
                        [])

    def test_GetByBrowsingHistory(self):
        self.insert_item_similarities("V", "I123",
                    [["I124", 0.9725],
                     ["I125", 0.8023]])
        self.insert_item_similarities("V", "I124",
                    [["I125", 0.9725],
                     ["I126", 0.7050]])

        browsing_history_cache = self.get_browsing_history_cache()

        response = self._viewItem("U1", "K300")
        ptm_id = self.get_ptm_id(response)
        response = self._viewItem("U1", "K301")
        browsing_history = browsing_history_cache.get_from_cache(self.TEST_SITE_ID, ptm_id,
                            no_result_as_none=True)
        self.assertEqual(browsing_history, ["K300", "K301"])

        print "1========"
        response = self._recommender("U1", type="ByBrowsingHistory", amount=5)
        self.assertEqual([item["item_id"] for item in response.data["topn"]],
                        [])

        self._viewItem("U1", "I123")
        self._viewItem("U1", "I124")
        browsing_history = browsing_history_cache.get_from_cache(self.TEST_SITE_ID, ptm_id,
                            no_result_as_none=True)
        self.assertEqual(browsing_history, ["K300", "K301", "I123", "I124"])

        print "2========="
        response = self._recommender("U1", type="ByBrowsingHistory", amount=5)
        self.assertEqual([item["item_id"] for item in response.data["topn"]],
                        ["I125", "I126"], "Unexpected Response: %s" % response.data)

        last_raw_log = self.get_last_n_raw_logs(1)[0]
        self.assertEqual(last_raw_log["behavior"], "RecBOBH")
        self.assertEqual(last_raw_log["browsing_history"], ["K300", "K301", "I123", "I124"])


    def test_view_item_affects_browsing_history(self):
        browsing_history_cache = self.get_browsing_history_cache()
        response = self._viewItem("U1", "I123")
        ptm_id = self.get_ptm_id(response)
        browsing_history = browsing_history_cache.get_from_cache(self.TEST_SITE_ID, ptm_id,
                            no_result_as_none=True)
        self.assertEqual(browsing_history, ["I123"])

        response = self._viewItem("U1", "I124")
        browsing_history = browsing_history_cache.get_from_cache(self.TEST_SITE_ID, ptm_id,
                            no_result_as_none=True)
        self.assertEqual(browsing_history, ["I123", "I124"])

        for i in range(3):
            response = self._viewItem("U1", "I126")
        browsing_history = browsing_history_cache.get_from_cache(self.TEST_SITE_ID, ptm_id,
                            no_result_as_none=True)
        self.assertEqual(browsing_history, ["I123", "I124", "I126", "I126", "I126"])

        item_ids = ["K%s" % i for i in range(settings.VISITOR_BROWSING_HISTORY_LENGTH)]
        for item_id in item_ids:
            response = self._viewItem("U1", item_id)
        browsing_history = browsing_history_cache.get_from_cache(self.TEST_SITE_ID, ptm_id,
                            no_result_as_none=True)
        self.assertEqual(browsing_history, item_ids)

        # Then we clear the cache.
        browsing_history_cache.clear()

        browsing_history = browsing_history_cache.get_from_cache(self.TEST_SITE_ID, ptm_id,
                            no_result_as_none=True)
        self.assertEqual(browsing_history, None)

        browsing_history = browsing_history_cache.get(self.TEST_SITE_ID, ptm_id)
        #print "SOOO:", browsing_history, "\n", item_ids
        self.assertEqual(browsing_history, item_ids)

        # TODO: test with same ids ["I125"] * 15


@override_settings(CELERY_EAGER_PROPAGATES_EXCEPTIONS=True,
                   CELERY_ALWAYS_EAGER=True,
                   BROKER_BACKEND='memory')
class AdUnitTest(BaseRecommenderTest):
    def setUp(self):
        super(AdUnitTest, self).setUp()
        self.postItems(test_data1, None)

    def test_invalid_args(self):
        response = self._recommender("U1", type="/unit/home")
        self.assertEqual(response.data["code"], 1)

    def testUnitByKeywords(self):
        # We have no browsing history and no hot index
        # So we don't have recommendation from ByBrowsingHistory
        response = self._recommender("U1", type="ByBrowsingHistory", amount=5)
        self.assertEqual([item["item_id"] for item in response.data["topn"]],
                        [])
        # Also not hot index
        response = self._recommender("U1", type="ByHotIndex", amount=5, hot_index_type="by_viewed")
        self.assertEqual([item["item_id"] for item in response.data["topn"]],
                        [])
        # But we can match items /unit/by_keywords
        response = self._recommender("U1", type="/unit/by_keywords", amount=5, keywords="雀巢,能恩")
        print response.data
        self.assertEqual(set([item["item_id"] for item in response.data["topn"]]),
                        set(["I123", "I124", "I125"]))
        # by if valid keywords, no result
        response = self._recommender("U1", type="/unit/by_keywords", amount=5, keywords="不存在的关键词1,不存在2")
        self.assertEqual(set([item["item_id"] for item in response.data["topn"]]),
                        set([]))

        # But ... If there is some by_viewed hot index
        # let's view some items with other users
        self._viewItem("U2", "I123", 7)
        self._viewItem("U2", "I124", 5)
        self._viewItem("U3", "I125", 3)
        self._viewItem("U5", "I126", 1)

        tasks.update_hotview_list.delay(self.TEST_SITE_ID)
        get_cache("default").clear()

        # now we have topn
        response = self.api_get(reverse("recommender-recommender"),
            data={"api_key": self.api_key,
                  "type": "ByHotIndex",
                  "hot_index_type": "by_viewed",
                  "user_id": "U1",
                  "amount": 5
                  })

        self.assertEqual(response.data["code"], 0)
        self.assertEqual([item["item_id"] for item in response.data["topn"]],
                         ["I123", "I124", "I125", "I126"])

        # And the /unit/by_keywords with invalid keywords should return blank result on customer request
        response = self._recommender("U1", type="/unit/by_keywords", amount=5, keywords="不存在1,不存在2")
        self.assertEqual([item["item_id"] for item in response.data["topn"]], [])

        # And let's let the user U1 browse some items
        self._viewItem("U1", "I123", 10)
        response = self._viewItem("U1", "I124", 10)

        # And add similarities for ViewItem
        self.insert_item_similarities("V", "I123",
                    [["I124", 0.9725],
                     ["I125", 0.8023]])
        self.insert_item_similarities("V", "I124",
                    [["I125", 0.9721],
                     ["I126", 0.7050]])

        browsing_history_cache = self.get_browsing_history_cache()
        browsing_history = browsing_history_cache.get_from_cache(self.TEST_SITE_ID, self.get_ptm_id(response),
                            no_result_as_none=True)
        self.assertEqual(set(browsing_history), set(["I123", "I124"]))

        # And the ByBrowsingHistory should return a different result than HotIndex
        response = self._recommender("U1", type="ByBrowsingHistory", amount=5)
        self.assertEqual([item["item_id"] for item in response.data["topn"]],
                        ["I125", "I126"])

        raw_log_count = len(self.get_last_n_raw_logs(None))

        # And now the /unit/by_keywords should return blank result
        response = self._recommender("U1", type="/unit/by_keywords", amount=5, keywords="不存在1,不存在2")
        self.assertEqual([item["item_id"] for item in response.data["topn"]], [])
        self.assertEqual(len(self.get_last_n_raw_logs(None)) - raw_log_count, 1)

        # also check the raw log
        raw_log = self.get_last_n_raw_logs(1)[0]
        self.assertSeveralKeys(raw_log,
                    {"user_id": "U1",
                     "behavior": "Recommendation",
                     "recommender_type": "/unit/by_keywords",
                     "recommended_items": [],
                     "amount": '5',
                     "keywords": u"不存在1,不存在2"
                     })
        response = self._recommender("U1", type="/unit/by_keywords", amount=5, keywords="")
        self.assertEqual([item["item_id"] for item in response.data["topn"]], [])


    def testUnitItem(self):
        # And add similarities for ViewItem
        self.insert_item_similarities("V", "I123",
                    [["I124", 0.9725],
                     ["I125", 0.8023]])
        self.insert_item_similarities("V", "I124",
                    [["I125", 0.9721],
                     ["I126", 0.7050]])

        self._viewItem("U2", "I123", 7)
        self._viewItem("U2", "I124", 5)
        self._viewItem("U3", "I125", 3)
        self._viewItem("U5", "I126", 1)

        tasks.update_hotview_list.delay(self.TEST_SITE_ID)

        # For item_id=INULL, there is no AlsoViewed recommendation
        response = self._recommender("U1", type="AlsoViewed", item_id="INULL", amount=5)
        self.assertEqual([item["item_id"] for item in response.data["topn"]],
                        [])
        # For item_id=I123
        response = self._recommender("U1", type="AlsoViewed", item_id="I123", amount=5)
        self.assertEqual([item["item_id"] for item in response.data["topn"]],
                        ["I124", "I125"])
        # there is recommendation for ByHotIndex, category_id=12
        response = self._recommender("U1", type="ByHotIndex", category_id="12", hot_index_type="by_viewed", amount=5)
        self.assertEqual(response.data["code"], 0, "Invalid response: %s" % response.data)
        self.assertEqual([item["item_id"] for item in response.data["topn"]],
                        ["I123", "I124", "I125"])

        # ByHotIndex of full site
        response = self._recommender("U1", type="ByHotIndex", hot_index_type="by_viewed", amount=5)
        self.assertEqual(response.data["code"], 0, "Invalid response: %s" % response.data)
        self.assertEqual([item["item_id"] for item in response.data["topn"]],
                        ["I123", "I124", "I125", "I126"])

        # For /unit/item, if item_id=INULL, the ByHotIndex of full site should be used.
        response = self._recommender("U1", type="/unit/item", item_id="INULL", amount=5)
        self.assertEqual([item["item_id"] for item in response.data["topn"]],
                        ["I123", "I124", "I125", "I126"])

        # For /unit/item, if item_id=I125, the hot index of category 12 would be used. And I125 should be filtered out.
        response = self._recommender("U1", type="/unit/item", item_id="I125", amount=5)
        self.assertEqual([item["item_id"] for item in response.data["topn"]],
                        ["I123", "I124"])

        # For /unit/item, if item_id=I123, the AlsoViewed recommendation should be used
        response = self._recommender("U1", type="/unit/item", item_id="I123", amount=5)
        self.assertEqual([item["item_id"] for item in response.data["topn"]],
                        ["I124", "I125"])

    def testUnitHome(self):
        # We have no browsing history and no hot index
        # So we don't have recommendation from ByBrowsingHistory
        response = self._recommender("U1", type="ByBrowsingHistory", amount=5)
        self.assertEqual([item["item_id"] for item in response.data["topn"]],
                        [])
        # Also not hot index
        response = self._recommender("U1", type="ByHotIndex", amount=5, hot_index_type="by_viewed")
        self.assertEqual([item["item_id"] for item in response.data["topn"]],
                        [])
        # Also not /unit/home
        response = self._recommender("U1", type="/unit/home", amount=5)
        print "RP:", response.data
        self.assertEqual([item["item_id"] for item in response.data["topn"]],
                        [])

        # But ... If there is some by_viewed hot index
        # let's view some items with other users
        self._viewItem("U2", "I123", 7)
        self._viewItem("U2", "I124", 5)
        self._viewItem("U3", "I125", 3)
        self._viewItem("U5", "I126", 1)

        tasks.update_hotview_list.delay(self.TEST_SITE_ID)
        get_cache("default").clear()

        # now we have topn
        response = self.api_get(reverse("recommender-recommender"),
            data={"api_key": self.api_key,
                  "type": "ByHotIndex",
                  "hot_index_type": "by_viewed",
                  "user_id": "U1",
                  "amount": 5
                  })

        self.assertEqual(response.data["code"], 0)
        self.assertEqual([item["item_id"] for item in response.data["topn"]],
                         ["I123", "I124", "I125", "I126"])

        # And the /unit/home should return same result, because the user has no browsing history
        response = self._recommender("U1", type="/unit/home", amount=5)
        self.assertEqual([item["item_id"] for item in response.data["topn"]],
                        ["I123", "I124", "I125", "I126"])

        # And let's let the user U1 browse some items
        self._viewItem("U1", "I123", 10)
        response = self._viewItem("U1", "I124", 10)

        # And add similarities for ViewItem
        self.insert_item_similarities("V", "I123",
                    [["I124", 0.9725],
                     ["I125", 0.8023]])
        self.insert_item_similarities("V", "I124",
                    [["I125", 0.9721],
                     ["I126", 0.7050]])

        browsing_history_cache = self.get_browsing_history_cache()
        browsing_history = browsing_history_cache.get_from_cache(self.TEST_SITE_ID, self.get_ptm_id(response),
                            no_result_as_none=True)
        self.assertEqual(set(browsing_history), set(["I123", "I124"]))

        # And the ByBrowsingHistory should return a different result than HotIndex
        response = self._recommender("U1", type="ByBrowsingHistory", amount=5)
        self.assertEqual([item["item_id"] for item in response.data["topn"]],
                        ["I125", "I126"])

        raw_log_count = len(self.get_last_n_raw_logs(None))

        # And now the /unit/home should return the same result as ByBrowsingHistory
        # because ByBrowsingHistory takes priority in the logic of /unit/home
        response = self._recommender("U1", type="/unit/home", amount=5)
        self.assertEqual([item["item_id"] for item in response.data["topn"]],
                        ["I125", "I126"])
        self.assertEqual(len(self.get_last_n_raw_logs(None)) - raw_log_count, 1)

        # also check the raw log
        raw_log = self.get_last_n_raw_logs(1)[0]
        self.assertSeveralKeys(raw_log,
                    {"user_id": "U1",
                     "behavior": "Recommendation",
                     "recommender_type": "/unit/home",
                     "recommended_items": [u"I125", u"I126"],
                     "amount": '5'
                     })


@override_settings(CELERY_EAGER_PROPAGATES_EXCEPTIONS=True,
                   CELERY_ALWAYS_EAGER=True,
                   BROKER_BACKEND='memory')
class HotIndexTest(BaseRecommenderTest):
    def setUp(self):
        super(HotIndexTest, self).setUp()
        self.postItems(test_data1, None)

    def test_hotindex_place_order(self):
        for hot_index_type in ("by_quantity", "by_order", "by_viewed"):
            response = self.api_get(reverse("recommender-recommender"),
                        data={"api_key": self.api_key,
                              "type": "ByHotIndex",
                              "hot_index_type": hot_index_type,
                              "user_id": "U1",
                              "amount": 5
                              })
            self.assertSeveralKeys(response.data,
                        {"code":0,
                         "type": "ByHotIndex",
                         "topn": []})

        # Place orders
        # 123 - 9; 124 - 6; 125-11; 126-1;
        # 123 - 3; 124 - 4; 125-2; 126-1
        self._placeOrder("U1", "I123,5.00,1|I124,12.00,1|I125,3.00,1")
        self._placeOrder("U2", "I123,5.00,1|I124,12.00,1|I126,3.00,1")
        self._placeOrder("U1", "I123,5.00,7|I124,12.00,3|I125,3.00,10")
        self._placeOrder("U5", "I124,8.00,1")

        tasks.update_hotview_list.delay(self.TEST_SITE_ID)
        get_cache("default").clear()

        # viewed should not be affected
        response = self.api_get(reverse("recommender-recommender"),
                    data={"api_key": self.api_key,
                          "type": "ByHotIndex",
                          "hot_index_type": "by_viewed",
                          "user_id": "U1",
                          "amount": 5
                          })

        self.assertEqual(response.data["code"], 0)
        self.assertEqual([item["item_id"] for item in response.data["topn"]],
                         [])

        # TOPN of full site
        response = self.api_get(reverse("recommender-recommender"),
                    data={"api_key": self.api_key,
                          "type": "ByHotIndex",
                          "hot_index_type": "by_quantity",
                          "user_id": "U1",
                          "amount": 5
                          })

        self.assertEqual(response.data["code"], 0)
        self.assertEqual([item["item_id"] for item in response.data["topn"]],
                         ["I125", "I123", "I124", "I126"])

        response = self.api_get(reverse("recommender-recommender"),
                    data={"api_key": self.api_key,
                          "type": "ByHotIndex",
                          "hot_index_type": "by_order",
                          "user_id": "U1",
                          "amount": 5
                          })

        self.assertEqual(response.data["code"], 0)
        self.assertEqual([item["item_id"] for item in response.data["topn"]],
                         [u'I124', u'I123', u'I125', u'I126'])

        # TOPN of a toplevel category
        response = self.api_get(reverse("recommender-recommender"),
                    data={"api_key": self.api_key,
                          "type": "ByHotIndex",
                          "hot_index_type": "by_quantity",
                          "user_id": "U1",
                          "category_id": "12",
                          "amount": 5
                          })

        self.assertEqual(response.data["code"], 0)
        self.assertEqual([item["item_id"] for item in response.data["topn"]],
                         ["I125", "I123", "I124"])

        response = self.api_get(reverse("recommender-recommender"),
                    data={"api_key": self.api_key,
                          "type": "ByHotIndex",
                          "hot_index_type": "by_order",
                          "user_id": "U1",
                          "category_id": "12",
                          "amount": 5
                          })

        self.assertEqual(response.data["code"], 0)
        self.assertEqual([item["item_id"] for item in response.data["topn"]],
                         ["I124", "I123", "I125"])

        # TOPN of a second level category
        response = self.api_get(reverse("recommender-recommender"),
                    data={"api_key": self.api_key,
                          "type": "ByHotIndex",
                          "hot_index_type": "by_quantity",
                          "user_id": "U1",
                          "category_id": "1201",
                          "amount": 5
                          })

        self.assertEqual(response.data["code"], 0)
        self.assertEqual([item["item_id"] for item in response.data["topn"]],
                         ["I125", "I124"])

        response = self.api_get(reverse("recommender-recommender"),
                    data={"api_key": self.api_key,
                          "type": "ByHotIndex",
                          "hot_index_type": "by_order",
                          "user_id": "U1",
                          "category_id": "1201",
                          "amount": 5
                          })

        self.assertEqual(response.data["code"], 0)
        self.assertEqual([item["item_id"] for item in response.data["topn"]],
                         ["I124", "I125"])

        # TOPN of brands 23
        response = self.api_get(reverse("recommender-recommender"),
                    data={"api_key": self.api_key,
                          "type": "ByHotIndex",
                          "hot_index_type": "by_quantity",
                          "user_id": "U1",
                          "brand": "23",
                          "amount": 5
                          })

        self.assertEqual(response.data["code"], 0)
        self.assertEqual([item["item_id"] for item in response.data["topn"]],
                         ["I125", "I124"])

        response = self.api_get(reverse("recommender-recommender"),
                    data={"api_key": self.api_key,
                          "type": "ByHotIndex",
                          "hot_index_type": "by_order",
                          "user_id": "U1",
                          "brand": "23",
                          "amount": 5
                          })

        self.assertEqual(response.data["code"], 0)
        self.assertEqual([item["item_id"] for item in response.data["topn"]],
                         ["I124", "I125"])

        # TopN of brands 24
        response = self.api_get(reverse("recommender-recommender"),
                    data={"api_key": self.api_key,
                          "type": "ByHotIndex",
                          "hot_index_type": "by_quantity",
                          "user_id": "U1",
                          "brand": "24",
                          "amount": 5
                          })

        self.assertEqual(response.data["code"], 0)
        self.assertEqual([item["item_id"] for item in response.data["topn"]],
                         ["I126"])

        response = self.api_get(reverse("recommender-recommender"),
                    data={"api_key": self.api_key,
                          "type": "ByHotIndex",
                          "hot_index_type": "by_order",
                          "user_id": "U1",
                          "brand": "24",
                          "amount": 5
                          })

        self.assertEqual(response.data["code"], 0)
        self.assertEqual([item["item_id"] for item in response.data["topn"]],
                         ["I126"])

    def test_hotindex_view_item(self):
        # test invalid hot_index_type
        response = self.api_get(reverse("recommender-recommender"),
                    data={"api_key": self.api_key,
                          "type": "ByHotIndex",
                          "hot_index_type": "invalid_type",
                          "user_id": "U1",
                          "amount": 5
                          })
        self.assertEqual(response.data["code"], 1)

        # before view items
        response = self.api_get(reverse("recommender-recommender"),
                    data={"api_key": self.api_key,
                          "type": "ByHotIndex",
                          "hot_index_type": "by_viewed",
                          "user_id": "U1",
                          "amount": 5
                          })
        self.assertSeveralKeys(response.data,
                    {"code":0,
                     "type": "ByHotIndex",
                     "topn": []})
        # view items
        self._viewItem("U1", "I123", 3)
        self._viewItem("U2", "I124", 2)
        self._viewItem("U3", "I125", 1)
        self._viewItem("U5", "I126", 5)

        tasks.update_hotview_list.delay(self.TEST_SITE_ID)
        get_cache("default").clear()

        # TOPN of full site
        response = self.api_get(reverse("recommender-recommender"),
                    data={"api_key": self.api_key,
                          "type": "ByHotIndex",
                          "hot_index_type": "by_viewed",
                          "user_id": "U1",
                          "amount": 5
                          })

        self.assertEqual(response.data["code"], 0)
        self.assertEqual([item["item_id"] for item in response.data["topn"]],
                         ["I126", "I123", "I124", "I125"])
        # Check item_link redirect url
        for recommended_item in response.data["topn"]:
            item_link = recommended_item["item_link"]
            parsed_item_link = urlparse.urlparse(item_link)
            original_item_link = self.get_item(recommended_item["item_id"])["item_link"]
            self.assertEqual(parsed_item_link.path, reverse("recommender-redirect"))
            parsed_query = cgi.parse_qs(parsed_item_link.query)
            self.assertEqual(parsed_query.has_key("req_id"), True)
            self.assertSeveralKeys(parsed_query,
                             {"url": [original_item_link],
                              "item_id": [recommended_item["item_id"]],
                              "api_key": [self.api_key]})

        ## If we make an item not available
        item = test_data1.getItems(item_ids=["I123"])[0]
        item["available"] = False
        response = self.postItem(item)
        self.assertEqual(response.data["code"], 0, "Unexpected response: %s" % response.data)
        self.assertEqual(self.get_item("I123")["available"], False)
        ## the unavailable item should not show up in result
        response = self.api_get(reverse("recommender-recommender"),
                    data={"api_key": self.api_key,
                          "type": "ByHotIndex",
                          "hot_index_type": "by_viewed",
                          "user_id": "U1",
                          "amount": 5
          })
        self.assertEqual(response.data["code"], 0)
        self.assertEqual([item["item_id"] for item in response.data["topn"]],
                         ["I126", "I124", "I125"])
        ## let's turn available back
        item = test_data1.getItems(item_ids=["I123"])[0]
        item["available"] = True
        response = self.postItem(item)
        self.assertEqual(response.data["code"], 0, "Unexpected response: %s" % response.data)
        self.assertEqual(self.get_item("I123")["available"], True)

        ## If we make an item stock=0
        item = test_data1.getItems(item_ids=["I124"])[0]
        item["stock"] = 0
        response = self.postItem(item)
        self.assertEqual(response.data["code"], 0, "Unexpected response: %s" % response.data)
        self.assertEqual(self.get_item("I124")["stock"], 0)
        ## the unavailable item should not show up in result
        response = self.api_get(reverse("recommender-recommender"),
                    data={"api_key": self.api_key,
                          "type": "ByHotIndex",
                          "hot_index_type": "by_viewed",
                          "user_id": "U1",
                          "amount": 5
          })
        self.assertEqual(response.data["code"], 0)
        self.assertEqual([item["item_id"] for item in response.data["topn"]],
                         ["I126", "I123", "I125"])
        ## let's turn stock back
        item = test_data1.getItems(item_ids=["I124"])[0]
        item["stock"] = 8
        response = self.postItem(item)
        self.assertEqual(response.data["code"], 0, "Unexpected response: %s" % response.data)
        self.assertEqual(self.get_item("I124")["stock"], 8)

        # TOPN of a certain toplevel category
        response = self.api_get(reverse("recommender-recommender"),
                    data={"api_key": self.api_key,
                          "type": "ByHotIndex",
                          "hot_index_type": "by_viewed",
                          "user_id": "U1",
                          "category_id": "12",
                          "amount": 5
                          })

        self.assertEqual(response.data["code"], 0)
        self.assertEqual([item["item_id"] for item in response.data["topn"]],
                         ["I123", "I124", "I125"])

        # TOPN of a second level category
        response = self.api_get(reverse("recommender-recommender"),
                    data={"api_key": self.api_key,
                          "type": "ByHotIndex",
                          "hot_index_type": "by_viewed",
                          "user_id": "U1",
                          "category_id": "1201",
                          "amount": 5
                          })

        self.assertEqual(response.data["code"], 0)
        self.assertEqual([item["item_id"] for item in response.data["topn"]],
                         ["I124", "I125"])

        # TOPN of brands
        response = self.api_get(reverse("recommender-recommender"),
                    data={"api_key": self.api_key,
                          "type": "ByHotIndex",
                          "hot_index_type": "by_viewed",
                          "user_id": "U1",
                          "brand": "23",
                          "amount": 5
                          })

        self.assertEqual(response.data["code"], 0)
        self.assertEqual([item["item_id"] for item in response.data["topn"]],
                         ["I124", "I125"])

        response = self.api_get(reverse("recommender-recommender"),
                    data={"api_key": self.api_key,
                          "type": "ByHotIndex",
                          "hot_index_type": "by_viewed",
                          "user_id": "U1",
                          "brand": "24",
                          "amount": 5
                          })

        self.assertEqual(response.data["code"], 0)
        self.assertEqual([item["item_id"] for item in response.data["topn"]],
                         ["I126"])

class RecommendStickListsAPITest(BaseRecommenderTest):
    def _assertKWList(self, list_type, expected):
        self.assertEqual(set([(keyword_record["keyword"], keyword_record["count"])
                for keyword_record in self.mongo_client.getSuggestKeywordList(self.TEST_SITE_ID, list_type)]), expected)

    def test_update_stick_recommend_list(self):
        data = {'type': 'wrong-type',
                'item_ids': 'hahah',
                'api_key': self.api_key}
        response = self.api_post(reverse("recommender-stick_lists"),
                                 data=data,
                                 expected_status_code=200,
                                 **{"HTTP_AUTHORIZATION": "Token %s" % self.site_token})
        self.assertEqual(response.data["code"], 1)
        self.assertTrue(response.data["err_msg"].startswith("'type' can only be one of "))

        data['type'] = 'ByHotIndex'
        response = self.api_post(reverse("recommender-stick_lists"),
                                 data=data,
                                 expected_status_code=200,
                                 **{"HTTP_AUTHORIZATION": "Token %s" % self.site_token})
        self.assertEqual(response.data["code"], 1)
        self.assertTrue(response.data["err_msg"].startswith("'item_ids' can only be item_id list"))

        item_ids = ['I%d' % i for i in range(10)]
        data['item_ids'] = item_ids
        response = self.api_post(reverse("recommender-stick_lists"),
                                 data=data,
                                 expected_status_code=200,
                                 **{"HTTP_AUTHORIZATION": "Token %s" % self.site_token})
        self.assertEqual(response.data["code"], 0)

        # check data in mongodb
        recommends =  self.mongo_client.getRecommendStickLists(self.TEST_SITE_ID,
                                                               data['type'])

        self.assertEquals(recommends['content'], item_ids)

@override_settings(CELERY_EAGER_PROPAGATES_EXCEPTIONS=True,
                   CELERY_ALWAYS_EAGER=True,
                   BROKER_BACKEND='memory')
class RecommendCustomListsAPITest(BaseRecommenderTest):
    def setUp(self):
        super(RecommendCustomListsAPITest, self).setUp()
        self.postItems(test_data1, None)

    def test_recommend_custom_lists(self):
        data = {'action': 'wrong-action',
                'type': 'com-type',
                'item_ids': 'hahah',
                'api_key': self.api_key}
        response = self.api_post(reverse("recommender-custom_lists"),
                                 data=data,
                                 expected_status_code=200,
                                 **{"HTTP_AUTHORIZATION": "Token %s" % self.site_token})
        self.assertEqual(response.data["code"], 1)
        self.assertTrue(response.data["err_msg"].startswith("'action' can only be "))

        data['action'] = 'set_recommender_items'
        response = self.api_post(reverse("recommender-custom_lists"),
                                 data=data,
                                 expected_status_code=200,
                                 **{"HTTP_AUTHORIZATION": "Token %s" % self.site_token})
        self.assertEqual(response.data["code"], 1)
        self.assertTrue(response.data["err_msg"].startswith("'item_ids' can only be item_id list"))

        item_ids = ['I12%d' % i for i in range(5)]
        data['item_ids'] = item_ids
        response = self.api_post(reverse("recommender-custom_lists"),
                                 data=data,
                                 expected_status_code=200,
                                 **{"HTTP_AUTHORIZATION": "Token %s" % self.site_token})
        self.assertEqual(response.data["code"], 0)

        data['action'] = 'get_recommender_items'
        response = self.api_post(reverse("recommender-custom_lists"),
                                 data=data,
                                 expected_status_code=200,
                                 **{"HTTP_AUTHORIZATION": "Token %s" % self.site_token})
        self.assertEqual(response.data["code"], 0)
        self.assertEquals(response.data['data']['item_ids'],
                          item_ids)
        data['action'] = 'list_recommender_types'
        response = self.api_post(reverse("recommender-custom_lists"),
                                 data=data,
                                 expected_status_code=200,
                                 **{"HTTP_AUTHORIZATION": "Token %s" % self.site_token})
        self.assertEqual(response.data["code"], 0)
        self.assertEquals(response.data['data'][0]['type'],
                          'com-type')

        #test customlists search
        response = self.api_get(reverse("recommender-recommender"),
                    data={"api_key": self.api_key,
                          "type": "CustomList",
                          "custom_type": "com-type1",
                          "user_id": "U1",
                          "brand": "23",
                          "amount": 10
                          })
        self.assertEqual(response.data["code"], 0)
        self.assertEqual(response.data['topn'], [])

        response = self.api_get(reverse("recommender-recommender"),
                    data={"api_key": self.api_key,
                          "type": "CustomList",
                          "custom_type": "com-type",
                          "user_id": "U1",
                          "brand": "23",
                          "amount": 10
                          })
        self.assertEqual(response.data["code"], 0)
        self.assertEqual([item["item_id"] for item in response.data["topn"]],
                         ['I123', 'I124'])
        # test fill by default value
        # view items
        self._viewItem("U1", "I123", 3)
        self._viewItem("U2", "I124", 2)
        self._viewItem("U3", "I125", 1)
        self._viewItem("U5", "I126", 5)

        tasks.update_hotview_list.delay(self.TEST_SITE_ID)
        get_cache("default").clear()

        response = self.api_get(reverse("recommender-recommender"),
                    data={"api_key": self.api_key,
                          "type": "CustomList",
                          "custom_type": "com-type",
                          "user_id": "U1",
                          "brand": "23",
                          "amount": 10
                          })
        self.assertEqual(response.data["code"], 0)
        self.assertEqual([item["item_id"] for item in response.data["topn"]],
                         ['I123', 'I124', 'I126', 'I125'])
