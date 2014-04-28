from django.test import TestCase
from django.test.utils import override_settings
from django.core.urlresolvers import reverse
from django.core.cache import get_cache
from django.conf import settings
from common.test_utils import BaseAPITest
from common import test_data1
from recommender import tasks


class BaseRecommenderTest(BaseAPITest):
    def setUp(self):
        super(BaseRecommenderTest, self).setUp()
        self.postItems(test_data1, None)
        
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



@override_settings(CELERY_EAGER_PROPAGATES_EXCEPTIONS=True,
                   CELERY_ALWAYS_EAGER=True,
                   BROKER_BACKEND='memory')
class GetByBrowsingHistoryTest(BaseRecommenderTest):
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

    def get_ptm_id(self, response):
        ptm_id_morsel = response.cookies.get("__ptmid", None)
        self.assertNotEqual(ptm_id_morsel, None)
        ptm_id = ptm_id_morsel.value
        return ptm_id

    def get_browsing_history_cache(self):
        from browsing_history_cache import BrowsingHistoryCache
        return BrowsingHistoryCache(self.mongo_client)

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
