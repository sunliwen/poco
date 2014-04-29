import cgi
import urlparse
from django.test import TestCase
from django.test.utils import override_settings
from django.core.urlresolvers import reverse
from django.core.cache import get_cache
from django.conf import settings
from django.http import HttpResponseRedirect, HttpResponseBadRequest
from common.test_utils import BaseAPITest
from common import site_manage_utils
from common import test_data1
from recommender import tasks


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

    def _recommender(self, user_id, **args):
        data = {"api_key": self.api_key,
                "user_id": user_id}
        data.update(args)
        response = self.api_get(reverse("recommender-recommender"),
                    data=data)
        return response

    def _placeOrder(self, user_id, order_content):
        self.api_get(reverse("recommender-events"),
                data={"api_key": self.api_key,
                      "event_type": "PlaceOrder",
                      "user_id": user_id,
                      "order_content": order_content
                      })


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
                                  **{"Authorization": "Token WRONG_TOKEN"})
        self.assertEqual(c_items.count(), 0)

        # If we post with a correct site_token but wrong api_key
        sample_item["api_key"] = other_site_record["api_key"]
        response = self.api_post(reverse("recommender-items"), data=sample_item,
                                  expected_status_code=403,
                                  **{"Authorization": "Token %s" % self.site_token})
        self.assertEqual(c_items.count(), 0)

        # Then with correct site_token
        sample_item["api_key"] = self.api_key
        response = self.api_post(reverse("recommender-items"), data=sample_item,
                                  expected_status_code=200,
                                  **{"Authorization": "Token %s" % self.site_token}
                                  )
        self.assertEqual(c_items.count(), 1)


@override_settings(CELERY_EAGER_PROPAGATES_EXCEPTIONS=True,
                   CELERY_ALWAYS_EAGER=True,
                   BROKER_BACKEND='memory')
class GetByBrowsingHistoryTest(BaseRecommenderTest):
    def setUp(self):
        super(GetByBrowsingHistoryTest, self).setUp()
        self.postItems(test_data1, None)

    def get_last_n_raw_logs(self, n=1):
        c_raw_logs = self.mongo_client.getSiteDBCollection(self.TEST_SITE_ID, "raw_logs")
        raw_logs = [raw_log for raw_log in c_raw_logs.find().sort([("$natural", -1)]).limit(n)]
        return raw_logs

    def insert_item_similarities(self, similarity_type, item_id, mostSimilarItems):
        c_item_similarities =  self.mongo_client.getSiteDBCollection(
                    self.TEST_SITE_ID, "item_similarities_%s" % similarity_type)
        record = {"item_id": item_id,
                  "mostSimilarItems": mostSimilarItems}
        c_item_similarities.insert(record)


    def test_by_browsing_history_return_topn(self):
        # We have no browsing history and no hot index
        #browsing_history_cache = self.get_browsing_history_cache()
        #browsing_history = browsing_history_cache.get_from_cache(self.TEST_SITE_ID, ptm_id, 
        #                    no_result_as_none=True)
        #self.assertEqual(browsing_history, [])
        # So we don't have recommendation from ByBrowsingHistory
        response = self._recommender("U1", type="ByBrowsingHistory", amount=5)
        self.assertEqual([item["item_id"] for item in response.data["topn"]], 
                        [])
        # But ... If there is some by_viewed hot index
        # let's view some items
        self._viewItem("U1", "I123", 3)
        self._viewItem("U2", "I124", 2)
        self._viewItem("U3", "I125", 1)
        self._viewItem("U5", "I126", 5)

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
                         ["I126", "I123", "I124", "I125"])

        # And the ByBrowsingHistory should return same result
        response = self._recommender("U1", type="ByBrowsingHistory", amount=5)
        self.assertEqual([item["item_id"] for item in response.data["topn"]], 
                        ["I126", "I123", "I124", "I125"])

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

        response = self._recommender("U1", type="ByBrowsingHistory", amount=5)
        self.assertEqual([item["item_id"] for item in response.data["topn"]], 
                        [])

        self._viewItem("U1", "I123")
        self._viewItem("U1", "I124")
        browsing_history = browsing_history_cache.get_from_cache(self.TEST_SITE_ID, ptm_id, 
                            no_result_as_none=True)
        self.assertEqual(browsing_history, ["K300", "K301", "I123", "I124"])
        
        response = self._recommender("U1", type="ByBrowsingHistory", amount=5)
        self.assertEqual([item["item_id"] for item in response.data["topn"]], 
                        ["I125", "I126"])

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
