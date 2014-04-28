from django.test import TestCase
from django.test.utils import override_settings
from django.core.urlresolvers import reverse
from django.core.cache import get_cache
from common.test_utils import BaseAPITest
from common import test_data1
from recommender import tasks


@override_settings(CELERY_EAGER_PROPAGATES_EXCEPTIONS=True,
                   CELERY_ALWAYS_EAGER=True,
                   BROKER_BACKEND='memory')
class HotIndexTest(BaseAPITest):
    def setUp(self):
        super(HotIndexTest, self).setUp()
        self.postItems(test_data1, None)
        
    def _viewItem(self, user_id, item_id, times=1):
        for i in range(times):
            self.api_get(reverse("recommender-events"),
                    data={"api_key": self.api_key,
                          "event_type": "ViewItem",
                          "user_id": user_id,
                          "item_id": item_id
                          })

    def _placeOrder(self, user_id, order_content):
        self.api_get(reverse("recommender-events"),
                data={"api_key": self.api_key,
                      "event_type": "PlaceOrder",
                      "user_id": user_id,
                      "order_content": order_content
                      })

    def test_by_browsing_history_return_topn(self):
        raise NotImplemented

    def test_hotindex_place_order(self):
        for hot_index_type in ("bought", "viewed"):
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
        # 123 - 9; 124 - 5; 125-11; 126-1;
        self._placeOrder("U1", "I123,5.00,1|I124,12.00,1|I125,3.00,1")
        self._placeOrder("U2", "I123,5.00,1|I124,12.00,1|I126,3.00,1")
        self._placeOrder("U1", "I123,5.00,7|I124,12.00,3|I125,3.00,10")

        tasks.update_hotview_list.delay(self.TEST_SITE_ID)
        get_cache("default").clear()

        # viewed should not be affected
        response = self.api_get(reverse("recommender-recommender"),
                    data={"api_key": self.api_key,
                          "type": "ByHotIndex",
                          "hot_index_type": "viewed",
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
                          "hot_index_type": "bought",
                          "user_id": "U1",
                          "amount": 5
                          })

        self.assertEqual(response.data["code"], 0)
        self.assertEqual([item["item_id"] for item in response.data["topn"]],
                         ["I125", "I123", "I124", "I126"])

        # TOPN of a toplevel category
        response = self.api_get(reverse("recommender-recommender"),
                    data={"api_key": self.api_key,
                          "type": "ByHotIndex",
                          "hot_index_type": "bought",
                          "user_id": "U1",
                          "category_id": "12",
                          "amount": 5
                          })

        self.assertEqual(response.data["code"], 0)
        self.assertEqual([item["item_id"] for item in response.data["topn"]],
                         ["I125", "I123", "I124"])

        # TOPN of a second level category
        response = self.api_get(reverse("recommender-recommender"),
                    data={"api_key": self.api_key,
                          "type": "ByHotIndex",
                          "hot_index_type": "bought",
                          "user_id": "U1",
                          "category_id": "1201",
                          "amount": 5
                          })

        self.assertEqual(response.data["code"], 0)
        self.assertEqual([item["item_id"] for item in response.data["topn"]],
                         ["I125", "I124"])

        # TOPN of brands
        response = self.api_get(reverse("recommender-recommender"),
                    data={"api_key": self.api_key,
                          "type": "ByHotIndex",
                          "hot_index_type": "bought",
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
                          "hot_index_type": "bought",
                          "user_id": "U1",
                          "brand": "24",
                          "amount": 5
                          })

        self.assertEqual(response.data["code"], 0)
        self.assertEqual([item["item_id"] for item in response.data["topn"]],
                         ["I126"])

    def test_hotindex_view_item(self):
        response = self.api_get(reverse("recommender-recommender"),
                    data={"api_key": self.api_key,
                          "type": "ByHotIndex",
                          "hot_index_type": "viewed",
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
                          "hot_index_type": "viewed",
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
                          "hot_index_type": "viewed",
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
                          "hot_index_type": "viewed",
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
                          "hot_index_type": "viewed",
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
                          "hot_index_type": "viewed",
                          "user_id": "U1",
                          "brand": "24",
                          "amount": 5
                          })

        self.assertEqual(response.data["code"], 0)
        self.assertEqual([item["item_id"] for item in response.data["topn"]],
                         ["I126"])
