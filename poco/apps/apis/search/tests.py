#encoding=utf8

import json
import copy
from django.test.utils import override_settings
from django.core.urlresolvers import reverse
from common import site_manage_utils
from common.mongo_client import getMongoClient
from apps.apis.search import es_search_functions
from common.test_utils import BaseAPITest
from common import test_data1
from apps.apis.recommender.tasks import update_keyword_hot_view_list
from django.conf import settings


@override_settings(CELERY_EAGER_PROPAGATES_EXCEPTIONS=True,
                   CELERY_ALWAYS_EAGER=True,
                   BROKER_BACKEND='memory')
class ItemsSearchViewSortByStockTest(BaseAPITest):
    def test_search2(self):
        # if both items has stock, the one match better should be the first
        items = [{"type": "product",
                  "item_id": "I123",
                  "item_name": "超级tian能恩",
                  "item_link": "abc",
                  "available": True,
                  "stock": 1
                 },
                 {"type": "product",
                                   "item_id": "I124",
                                   "item_name": "能恩",
                                   "item_link": "abc",
                                   "stock": 1,
                                   "available": True
                                  },
                 ]
        class A:
            def getItems(*args):
                return items
        self.postItems(A(), None)

        body = {"api_key": self.api_key,
                "q": "能恩"
                }
        response = self.api_post(reverse("products-search"), data=body)
        self.assertEqual(response.data["info"]["total_result_count"], 2)
        self.assertEqual([rec["item_id"] for rec in response.data["records"]], ["I124", "I123"])

    def test_search(self):
        items = [{
                     "type": "product",
                     "item_id": "I123",
                     "item_name": "超级tian能恩",
                     "item_link": "abc",
                     "available": True,
                     "stock": 1
                 },
                 {
                     "type": "product",
                     "item_id": "I124",
                     "item_name": "能恩",
                     "item_link": "abc",
                     "stock": 0,
                     "available": True
                 },
                 {
                     "type": "product",
                     "item_id": "I125",
                     "item_name": "能恩",
                     "item_link": "abc",
                     "stock": 1,
                     "available": True
                 },
                 ]
        class A:
            def getItems(*args):
                return items
        self.postItems(A(), None)

        body = {"api_key": self.api_key,
                "q": "能恩"
                }

        origin_search_result_order_by_stock = settings.SEARCH_RESULT_ORDER_BY_STOCK

        try:
            self.clearCaches()
            settings.SEARCH_RESULT_ORDER_BY_STOCK = False

            response = self.api_post(reverse("products-search"), data=body)
            self.assertEqual(response.data["info"]["total_result_count"], 3)
            self.assertEqual([rec["item_id"] for rec in response.data["records"]][2], "I123")

            self.clearCaches()
            settings.SEARCH_RESULT_ORDER_BY_STOCK = True

            response = self.api_post(reverse("products-search"), data=body)
            self.assertEqual(response.data["info"]["total_result_count"], 3)
            self.assertEqual([rec["item_id"] for rec in response.data["records"]], ["I125", "I124", "I123"])
        finally:
            settings.SEARCH_RESULT_ORDER_BY_STOCK = origin_search_result_order_by_stock



# refs: http://stackoverflow.com/questions/4055860/unit-testing-with-django-celery
# refs: http://docs.celeryproject.org/en/2.5/django/unit-testing.html
@override_settings(CELERY_EAGER_PROPAGATES_EXCEPTIONS=True,
                   CELERY_ALWAYS_EAGER=True,
                   BROKER_BACKEND='memory')
class ItemsSearchViewTest(BaseAPITest):
    def setUp(self):
        super(ItemsSearchViewTest, self).setUp()
        self.postItems(test_data1, None)

    def _test_by_tags(self):
        # match mode: MATCH_ALL, match all tags; MATCH_MORE_BETTER, match more tags better, but not necessarily all of them
        # MATCH_ALL for one tag
        self._test_template_for_tags("老人", "MATCH_ALL", ["I123", "I125"])

        #MATCH_ALL for two tags
        self._test_template_for_tags("小孩 老人", "MATCH_ALL", ["I125"])

        #MATCH_ALL for impossible combination
        self._test_template_for_tags("老人 小孩 妇女", "MATCH_ALL", [])

        # MATCH_MORE_BETTER for one tag
        self._test_template_for_tags("老人", "MATCH_MORE_BETTER", ["I123", "I125"])
        # MATCH_MORE_BETTER for 2 tags
        self._test_template_for_tags("老人 小孩", "MATCH_MORE_BETTER", ["I125", "I123", "I126", "I124"])
        self._test_template_for_tags("妇女 小孩", "MATCH_MORE_BETTER", ["I124", "I126", "I125"])
        # MATCH_MORE_BETTER for 3 tags
        self._test_template_for_tags("老人 小孩 妇女", "MATCH_MORE_BETTER", ["I124", "I125", "I123", "I126"])

        # Invalid match_mode
        data = {
            "q": "老人",
            "search_config": {"type": "SEARCH_TERMS",
                            "match_mode": "INVALID_MATCH_MODE",
                            "term_field": "tags"
                            },
            "api_key": self.api_key
        }
        response = self.client.post(reverse("products-search"),
                            content_type="application/json",
                            data=json.dumps(data))
        self.assertEqual(len(response.data["errors"]), 1)

        # No term field
        data = {
            "q": "老人",
            "search_config": {"type": "SEARCH_TERMS",
                            "match_mode": "MATCH_ALL",
                            },
            "api_key": self.api_key
        }
        response = self.client.post(reverse("products-search"),
                            content_type="application/json",
                            data=json.dumps(data))
        self.assertEqual(len(response.data["errors"]), 1)

        # Invalid Term field
        data = {
            "q": "老人",
            "search_config": {"type": "SEARCH_TERMS",
                            "match_mode": "MATCH_ALL",
                            "term_field": "invalid_field"
                            },
            "api_key": self.api_key
        }
        response = self.client.post(reverse("products-search"),
                            content_type="application/json",
                            data=json.dumps(data))
        self.assertEqual(len(response.data["errors"]), 1)

        # invalid type
        data = {
            "q": "老人",
            "search_config": {"type": "INVALID_TYPE",
                            "match_mode": "MATCH_ALL",
                            "term_field": "tags"
                            },
            "api_key": self.api_key
        }
        response = self.client.post(reverse("products-search"),
                            content_type="application/json",
                            data=json.dumps(data))
        self.assertEqual(len(response.data["errors"]), 1)

        # SEARCH_TEXT should just behavior like before
        data = {
            "q": "能恩",
            "search_config": {"type": "SEARCH_TEXT"},
            "api_key": self.api_key
        }
        response = self.client.post(reverse("products-search"),
                            content_type="application/json",
                            data=json.dumps(data))
        self.assertEqual(len(response.data["errors"]), 0)
        self.assertEqual([record["item_id"] for record in response.data["records"]],
                         ["I124", "I125"])

    def _test_template_for_tags(self, q, match_mode, expected_item_ids):
        data = {
            "q": q,
            "search_config": {"type": "SEARCH_TERMS",
                            "match_mode": match_mode,
                            "term_field": "tags"
                            },
            "api_key": self.api_key
        }
        response = self.client.post(reverse("products-search"),
                            content_type="application/json",
                            data=json.dumps(data))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["errors"], [])
        self.assertEqual([record["item_id"] for record in response.data["records"]],
                         expected_item_ids)

    def _test_no_such_api_key(self):
        data = {
            "q": "",
            "api_key": ""
            }
        response = self.client.post(reverse("products-search"),
                                    content_type="application/json",
                                    data=json.dumps(data))
        self.assertEqual(response.status_code, 200)
        errors = response.data["errors"]
        self.assertEqual(errors[0]["message"], "no such api_key")

    def _test_search_empty_string(self):
        self.clearCaches()
        body = {"api_key": self.api_key,
                "q": ""
                }
        response = self.api_post(reverse("products-search"), data=body)
        #import pprint; pprint.pprint(response.data)
        self.assertEqual(response.data["info"]["total_result_count"], 4)
        self.assertEqual(self.sortDictList(response.data["info"]["facets"]["brand"], by_key="id"),
                         [{"count": 1, "id": "22", "label": u"雀巢", 'brand_logo': 'http://logo.com/22'},
                         {"count": 2, "id": "23", "label": u"能恩", 'brand_logo': 'http://logo.com/23'},
                         {"count": 1, "id": "24", "label": u"智多星", 'brand_logo': 'http://logo.com/24'},
                        ])
        self.assertEqual(self.sortDictList(response.data["info"]["facets"]["origin_place"], by_key="id"),
                        [{"count": 3, "id": 0, "label": ""},
                         {"count": 1, "id": 1, "label": ""}
                        ])
        self.assertEqual(self.sortDictList(response.data["info"]["facets"]["categories"], by_key="id"),
                        [
                        {"count": 3, "id": "12", "label": u"分类12"},
                         {"count": 2, "id": "1201", "label": u"分类12-01"},
                            {"count": 1, "id": "120101", "label": u"分类12-01-01"},
                            {"count": 1, "id": "120102", "label": u"分类12-01-02"},
                         {"count": 1, "id": "1202", "label": u"分类12-02"},
                         {"count": 1, "id": "15", "label": u"分类15"},
                         {"count": 1, "id": "1501", "label": u"分类15-01"}
                        ])

    def _test_search_facets_under_a_category(self):
        category_id = "12"
        body = {"api_key": self.api_key,
                "q": "",
                "filters": {
                    "categories": [category_id]
                }
            }
        response = self.api_post(reverse("products-search"), data=body)
        self.assertEqual(response.data["info"]["total_result_count"], 3)
        self.assertEqual(self.sortDictList(response.data["info"]["facets"]["brand"], by_key="id"),
                        [{"count": 1, "id": "22", "label": u"雀巢", 'brand_logo': 'http://logo.com/22'},
                         {"count": 2, "id": "23", "label": u"能恩", 'brand_logo': 'http://logo.com/23'},
                        ])
        self.assertEqual(self.sortDictList(response.data["info"]["facets"]["origin_place"], by_key="id"),
                        [{"count": 2, "id": 0, "label": ""},
                         {"count": 1, "id": 1, "label": ""}
                        ])
        self.assertEqual(self.sortDictList(response.data["info"]["facets"]["categories"], by_key="id"),
                        [
                        {"count": 3, "id": "12", "label": u"分类12"},
                         {"count": 2, "id": "1201", "label": u"分类12-01"},
                            {"count": 1, "id": "120101", "label": u"分类12-01-01"},
                            {"count": 1, "id": "120102", "label": u"分类12-01-02"},
                         {"count": 1, "id": "1202", "label": u"分类12-02"},
                        ])

    def _test_search_filters(self):
        body = {"api_key": self.api_key,
            "q": "",
            "filters": {
                "brand": ["23"]
            }
        }
        response = self.api_post(reverse("products-search"), data=body)
        self.assertEqual(response.data["info"]["total_result_count"], 2)

        filters = {}
        body['filters'] = filters
        response = self.api_post(reverse("products-search"), data=body)
        self.assertEqual(response.data["info"]["total_result_count"], 4)


        filters = {'channel': ['1269e', '1269a']}
        body['filters'] = filters
        response = self.api_post(reverse("products-search"), data=body)
        self.assertEqual(response.data["info"]["total_result_count"], 4)


        filters = {'channel': ['1269e']}
        body['filters'] = filters
        response = self.api_post(reverse("products-search"), data=body)
        self.assertEqual(response.data["info"]["total_result_count"], 3)

        filters = {'channel': ['1269a']}
        body['filters'] = filters
        response = self.api_post(reverse("products-search"), data=body)
        self.assertEqual(response.data["info"]["total_result_count"], 1)

        filters = {'channel': ['1269']}
        body['filters'] = filters
        response = self.api_post(reverse("products-search"), data=body)
        self.assertEqual(response.data["info"]["total_result_count"], 0)

    def _test_search_other_fields(self):
        # search the description field
        body = {"api_key": self.api_key,
                "q": "描述A"
                }
        response = self.api_post(reverse("products-search"), data=body)
        self.assertEqual(response.data["info"]["total_result_count"], 1)

        # search the tags field
        body = {"api_key": self.api_key,
                "q": "妇女"
                }
        response = self.api_post(reverse("products-search"), data=body)
        self.assertEqual(response.data["info"]["total_result_count"], 1)

        body = {"api_key": self.api_key,
                "q": "妇"
                }
        response = self.api_post(reverse("products-search"), data=body)
        self.assertEqual(response.data["info"]["total_result_count"], 1)

        # search the brand field
        body = {"api_key": self.api_key,
                "q": "智多星"
                }
        response = self.api_post(reverse("products-search"), data=body)
        self.assertEqual(response.data["info"]["total_result_count"], 1)

        # search the sku field
        body = {"api_key": self.api_key,
                "q": 'SKU10052'}
        response = self.api_post(reverse("products-search"), data=body)
        self.assertEqual(response.data["info"]["total_result_count"], 1)

        # test the sku field by term search
        body = {
            "q": "SKU10052",
            "search_config": {"type": "SEARCH_TERMS",
                            "match_mode": "MATCH_ALL",
                            "term_field": "sku"
                            },
            "api_key": self.api_key
        }
        response = self.api_post(reverse("products-search"), data=body)
        self.assertEqual(response.data["info"]["total_result_count"], 1)

        body['q'] = 'SKU100'
        response = self.api_post(reverse("products-search"), data=body)
        self.assertEqual(response.data["info"]["total_result_count"], 0)


        # search the sku field
        body = {"api_key": self.api_key,
        "q": "SKU10052 奶粉"
        }
        response = self.api_post(reverse("products-search"), data=body)
        self.assertEqual(response.data["info"]["total_result_count"], 0)
        # search the sku field
        body = {"api_key": self.api_key,
        "q": "SKU100"
        }
        response = self.api_post(reverse("products-search"), data=body)
        self.assertEqual(response.data["info"]["total_result_count"], 0)

        items = test_data1.getItems()
        for item_spec, search_strs in (('RH-LH-BO1', ('RHLH', 'RH-LH-BO1', 'HLH', 'LH-BO1')),
                                       ('0.15g*180s', ('0.15g*180s', '0.15g 180s', '0.15g', '180s')),
                                       ('RH-LH-BO1 5支装', ('RH-LH-BO1 5支', 'BO15支', 'RHLHBO1', '支装'))):
            item = items[0]
            item['item_spec'] = item_spec
            self.postItem(item, self.site_token)
            for q in search_strs:
                body = {"api_key": self.api_key,
                        "q": q}
                response = self.api_post(reverse("products-search"), data=body)
                self.assertEqual(response.data["info"]["total_result_count"], 1)

        for item_spec, search_strs in (('88ml', ('288', '882', 'hn88', '88hn',
                                                 '8hn', 'ml8', 'm8')),):
            item = items[0]
            item['item_spec'] = item_spec
            self.postItem(item, self.site_token)
            for q in search_strs:
                body = {"api_key": self.api_key,
                        "q": q}
                response = self.api_post(reverse("products-search"), data=body)
                self.assertEqual(response.data["info"]["total_result_count"], 0)

    #def _test_search_special_characters(self):
    #    # post another item
    #    item = {"type": "product",
    #            "available": True,
    #            "item_id": "ITEM201",
    #            "item_name": "橄榄油(精华)（红色）",
    #            "item_link": "http://example.com/"}
    #    self.postItem(item)
    #    body = {"api_key": self.api_key,
    #            "q": "橄榄油"
    #            }
    #    response = self.api_post(reverse("products-search"), data=body)
    #    self.assertEqual(response.data["info"]["total_result_count"], 1)

    #    body = {"api_key": self.api_key,
    #            "q": "精华"
    #            }
    #    response = self.api_post(reverse("products-search"), data=body)
    #    self.assertEqual(response.data["info"]["total_result_count"], 1)

    #    body = {"api_key": self.api_key,
    #            "q": "（红色）"
    #            }
    #    response = self.api_post(reverse("products-search"), data=body)
    #    self.assertEqual(response.data["info"]["total_result_count"], 1)

    #    body = {"api_key": self.api_key,
    #            "q": "橄榄油(精华)"
    #            }
    #    response = self.api_post(reverse("products-search"), data=body)
    #    self.assertEqual(response.data["info"]["total_result_count"], 1)

    def _test_search1(self):
        body = {"api_key": self.api_key,
                "q": "雀巢"
                }
        response = self.api_post(reverse("products-search"), data=body)
        self.assertEqual(response.data["info"]["total_result_count"], 1)
        # stock field should be included
        self.assertEqual(response.data["records"][0].has_key("stock"), True)
        self.assertEqual(response.data["records"][0]['brand']['id'], '22')
        self.assertEqual(response.data["records"][0]['brand']['name'], u'雀巢')
        self.assertEqual(response.data["records"][0]['brand']['brand_logo'],
                         'http://logo.com/22')

        item_id = response.data['records'][0]['item_id']
        # delete the brand, got nothing
        item = test_data1.getItems(item_ids=[item_id])[0]
        del item['brand']
        response = self.postItem(item)
        self.clearCaches()
        self.refreshSiteItemIndex(self.TEST_SITE_ID)
        response = self.api_post(reverse("products-search"), data=body)
        self.assertEqual(response.data["info"]["total_result_count"], 1)
        # stock field should be included
        self.assertEqual(response.data["records"][0].has_key("stock"), True)
        self.assertEqual(response.data["records"][0].has_key('brand'), False)


    def _test_search2(self):
        body = {"api_key": self.api_key,
                "q": "能恩"
                }
        response = self.api_post(reverse("products-search"), data=body)
        self.assertEqual(response.data["info"]["total_result_count"], 2)


    def _test_search_pagination(self):
        # Invalid per_page
        body = {"api_key": self.api_key,
                    "q": "",
                    "per_page": "1a"
                }
        response = self.api_post(reverse("products-search"), data=body)
        self.assertEqual(response.data["errors"][0]["code"], "INVALID_PARAM")
        self.assertEqual(response.data["errors"][0]["param_name"], "per_page")

        # first page
        body = {"api_key": self.api_key,
                    "q": "",
                    "per_page": "1"
                }
        response = self.api_post(reverse("products-search"), data=body)
        self.assertEqual(response.data["info"]["per_page"], 1)
        self.assertEqual(response.data["info"]["total_result_count"], 4)
        self.assertEqual(response.data["info"]["num_pages"], 4)
        self.assertEqual(response.data["info"]["current_page"], 1)
        self.assertEqual(len(response.data["records"]), 1)
        page1_records = response.data["records"]

        # second page
        body = {"api_key": self.api_key,
                    "q": "",
                    "per_page": "1",
                    "page": 2
                }
        response = self.api_post(reverse("products-search"), data=body)
        self.assertEqual(response.data["info"]["per_page"], 1)
        self.assertEqual(response.data["info"]["total_result_count"], 4)
        self.assertEqual(response.data["info"]["num_pages"], 4)
        self.assertEqual(response.data["info"]["current_page"], 2)
        self.assertEqual(len(response.data["records"]), 1)
        self.assertNotEqual(response.data["records"], page1_records)

        # per_page should be greater than zero
        body = {"api_key": self.api_key,
            "q": "",
            "per_page": "0"
        }
        response = self.api_post(reverse("products-search"), data=body)
        self.assertEqual(len(response.data["errors"]), 1)
        self.assertSeveralKeys(response.data["errors"][0],
                                {"code": "INVALID_PARAM",
                                 "param_name": "per_page"})

        body = {"api_key": self.api_key,
            "q": "",
            "per_page": "-1"
        }
        response = self.api_post(reverse("products-search"), data=body)
        self.assertEqual(len(response.data["errors"]), 1)
        self.assertSeveralKeys(response.data["errors"][0],
                                {"code": "INVALID_PARAM",
                                 "param_name": "per_page"})

    #def _test_result_mode(self):
    #    body = {"api_key": self.api_key,
    #        "q": "",
    #        "per_page": "1",
    #        "result_mode": "without_records"
    #    }
    #    response = self.api_post(reverse("products-search"), data=body)
    #    self.assertEqual(response.data["errors"], [])
    #    self.assertEqual(response.data["records"], [])
    #    self.assertEqual(response.data["info"]["per_page"], 1)
    #    self.assertEqual(response.data["info"]["total_result_count"], 4)
    #    self.assertEqual(response.data["info"]["num_pages"], 0)
    #    self.assertEqual(response.data["info"]["current_page"], 1)

    def _test_search_facets_selection(self):
        body = {"api_key": self.api_key,
            "q": "",
            "facets": {
            }
        }
        response = self.api_post(reverse("products-search"), data=body)
        self.assertEqual(response.data["info"]["facets"], {})

        body = {"api_key": self.api_key,
            "q": "",
            "facets": {
                "brand": {}
            }
        }
        response = self.api_post(reverse("products-search"), data=body)
        self.sortDictList(response.data["info"]["facets"]["brand"], "id")
        self.assertEqual(response.data["info"]["facets"],
                {"brand": [{"count": 1, "id": "22", "label": u"雀巢", 'brand_logo': 'http://logo.com/22'},
                         {"count": 2, "id": "23", "label": u"能恩", 'brand_logo': 'http://logo.com/23'},
                         {"count": 1, "id": "24", "label": u"智多星", 'brand_logo': 'http://logo.com/24'},
                  ]})

        body = {"api_key": self.api_key,
            "q": "",
            "facets": {
                "brand": {},
                "categories": {
                    "mode": "A_INVALID_MODE"
                }
            }
        }
        response = self.api_post(reverse("products-search"), data=body)
        self.assertEqual(response.data["errors"][0]["code"], "INVALID_PARAM")

        body = {"api_key": self.api_key,
            "q": "",
            "facets": {
                "brand": {},
                "categories": {
                    "mode": "DIRECT_CHILDREN"
                }
            }
        }
        response = self.api_post(reverse("products-search"), data=body)
        self.sortDictList(response.data["info"]["facets"]["brand"], "id")
        self.sortDictList(response.data["info"]["facets"]["categories"], "id")
        self.assertEqual(response.data["info"]["facets"],
                {"brand": [{"count": 1, "id": "22", "label": u"雀巢", 'brand_logo': 'http://logo.com/22'},
                         {"count": 2, "id": "23", "label": u"能恩", 'brand_logo': 'http://logo.com/23'},
                         {"count": 1, "id": "24", "label": u"智多星", 'brand_logo': 'http://logo.com/24'},
                  ],
                  "categories":
                        [{"count": 3, "id": "12", "label": u"分类12"},
                         {"count": 1, "id": "15", "label": u"分类15"},
                        ]
                })

        body = {"api_key": self.api_key,
            "q": "",
            "facets": {
                "brand": {},
                "categories": {
                    "mode": "SUB_TREE"
                },
                "origin_place": {
                }
            }
        }
        response = self.api_post(reverse("products-search"), data=body)
        self.sortDictList(response.data["info"]["facets"]["brand"], "id")
        self.sortDictList(response.data["info"]["facets"]["categories"], "id")
        self.sortDictList(response.data["info"]["facets"]["origin_place"], "id")
        self.assertEqual(response.data["info"]["facets"],
                {"brand": [{"count": 1, "id": "22", "label": u"雀巢", 'brand_logo': 'http://logo.com/22'},
                         {"count": 2, "id": "23", "label": u"能恩", 'brand_logo': 'http://logo.com/23'},
                         {"count": 1, "id": "24", "label": u"智多星", 'brand_logo': 'http://logo.com/24'},
                  ],
                  "categories":
                        [{"count": 3, "id": "12", "label": u"分类12"},
                         {"count": 2, "id": "1201", "label": u"分类12-01"},
                            {"count": 1, "id": "120101", "label": u"分类12-01-01"},
                            {"count": 1, "id": "120102", "label": u"分类12-01-02"},
                         {"count": 1, "id": "1202", "label": u"分类12-02"},
                         {"count": 1, "id": "15", "label": u"分类15"},
                         {"count": 1, "id": "1501", "label": u"分类15-01"}
                        ],
                   "origin_place": [{"count": 3, "id": 0, "label": ""},
                         {"count": 1, "id": 1, "label": ""}
                        ]
                })

        # And the default categories facet mode should be "SUB_TREE"
        body = {"api_key": self.api_key,
            "q": "",
            "facets": {
                "brand": {},
                "categories": {},
                "origin_place": {}
            }
        }
        response = self.api_post(reverse("products-search"), data=body)
        self.sortDictList(response.data["info"]["facets"]["brand"], "id")
        self.sortDictList(response.data["info"]["facets"]["categories"], "id")
        self.sortDictList(response.data["info"]["facets"]["origin_place"], "id")
        self.assertEqual(response.data["info"]["facets"],
                {"brand": [{"count": 1, "id": "22", "label": u"雀巢", 'brand_logo': 'http://logo.com/22'},
                         {"count": 2, "id": "23", "label": u"能恩", 'brand_logo': 'http://logo.com/23'},
                         {"count": 1, "id": "24", "label": u"智多星", 'brand_logo': 'http://logo.com/24'},
                  ],
                  "categories":
                        [{"count": 3, "id": "12", "label": u"分类12"},
                         {"count": 2, "id": "1201", "label": u"分类12-01"},
                            {"count": 1, "id": "120101", "label": u"分类12-01-01"},
                            {"count": 1, "id": "120102", "label": u"分类12-01-02"},
                         {"count": 1, "id": "1202", "label": u"分类12-02"},
                         {"count": 1, "id": "15", "label": u"分类15"},
                         {"count": 1, "id": "1501", "label": u"分类15-01"}
                        ],
                   "origin_place": [{"count": 3, "id": 0, "label": ""},
                         {"count": 1, "id": 1, "label": ""}
                        ]
                })

        body = {"api_key": self.api_key,
            "q": "",
            "facets": {
                "categories": {
                    "mode": "SUB_TREE"
                },
            },
            "filters": {
                "categories": ["12"]
            }
        }
        response = self.api_post(reverse("products-search"), data=body)
        self.sortDictList(response.data["info"]["facets"]["categories"], "id")
        self.assertEqual(response.data["info"]["facets"],
                {"categories":
                        [{"count": 3, "id": "12", "label": u"分类12"},
                         {"count": 2, "id": "1201", "label": u"分类12-01"},
                            {"count": 1, "id": "120101", "label": u"分类12-01-01"},
                            {"count": 1, "id": "120102", "label": u"分类12-01-02"},
                         {"count": 1, "id": "1202", "label": u"分类12-02"}
                        ],
                })

        body = {"api_key": self.api_key,
            "q": "",
            "facets": {
                "categories": {
                    "mode": "SUB_TREE"
                },
            },
            "filters": {
                "categories": ["1201"]
            }
        }
        response = self.api_post(reverse("products-search"), data=body)
        self.sortDictList(response.data["info"]["facets"]["categories"], "id")
        self.assertEqual(response.data["info"]["facets"],
                {"categories":
                        [
                         {"count": 2, "id": "12", "label": u"分类12"},
                         {"count": 2, "id": "1201", "label": u"分类12-01"},
                            {"count": 1, "id": "120101", "label": u"分类12-01-01"},
                            {"count": 1, "id": "120102", "label": u"分类12-01-02"},
                        ],
                })


        body = {"api_key": self.api_key,
            "q": "",
            "facets": {
                "categories": {
                    "mode": "SUB_TREE"
                },
            },
            "filters": {
                "categories": ["1201", "15"]
            }
        }
        response = self.api_post(reverse("products-search"), data=body)
        self.sortDictList(response.data["info"]["facets"]["categories"], "id")
        self.assertEqual(response.data["info"]["facets"],
                {"categories":
                        [
                         {"count": 2, "id": "12", "label": u"分类12"},
                         {"count": 2, "id": "1201", "label": u"分类12-01"},
                            {"count": 1, "id": "120101", "label": u"分类12-01-01"},
                            {"count": 1, "id": "120102", "label": u"分类12-01-02"},
                         {"count": 1, "id": "15", "label": u"分类15"},
                         {"count": 1, "id": "1501", "label": u"分类15-01"}
                        ],
                })

    def _test_item_factory_subtitle(self):
        body = {
            "q": "",
            "search_config": {"type": "SEARCH_TEXT"},
            "api_key": self.api_key
        }

        response = self.api_post(reverse("products-search"), data=body)
        self.assertEqual(response.data["info"]["total_result_count"], 4)
        for item in response.data['records']:
            self.assertNotEqual(item['factory'], '')
            self.assertNotEqual(item['item_sub_title'], '')
        items = test_data1.getItems()
        for item in items:
            del item['factory']
            del item['item_sub_title']

        body = {"type": "multiple_products",
                "api_key": self.api_key,
                "items": items}
        response = self.api_post(reverse("recommender-items"), data=body,
                                  expected_status_code=200,
                                  **{"HTTP_AUTHORIZATION": "Token %s" % self.site_token}
                                  )

        body = {
            "q": "",
            "search_config": {"type": "SEARCH_TEXT"},
            "api_key": self.api_key
        }
        self.clearCaches()
        self.refreshSiteItemIndex(self.TEST_SITE_ID)
        response = self.api_post(reverse("products-search"), data=body)
        self.assertEqual(response.data["info"]["total_result_count"], 4)
        for item in response.data['records']:
            self.assertEqual(item.has_key('factory'), False)
            self.assertEqual(item.has_key('item_sub_title'), False)

    def _test_sell_num_sort(self):
        self.clearCaches()
        self.refreshSiteItemIndex(self.TEST_SITE_ID)
        # test blank query string result
        body = {
            "q": "",
            "search_config": {"type": "SEARCH_TEXT"},
            "sort_fields": ['sell_num', ],
            "api_key": self.api_key
        }
        response = self.api_post(reverse("products-search"), data=body)
        items_sell_num_order = ('I124', 'I126', 'I125')
        for item, item_id in zip(response.data['records'], items_sell_num_order):
            self.assertEqual(item['item_id'], item_id)
            self.assertTrue('sell_num' in item)
        items_sell_num_order = ('I125', 'I126', 'I124')
        body['sort_fields'] = ['-sell_num', ]
        response = self.api_post(reverse("products-search"), data=body)
        for item, item_id in zip(response.data['records'], items_sell_num_order):
            self.assertEqual(item['item_id'], item_id)
            self.assertTrue('sell_num' in item)

        body = {
            "q": "",
            "search_config": {"type": "SEARCH_TEXT"},
            "sort_fields": ['_score', 'sell_num'],
            "api_key": self.api_key
        }
        response = self.api_post(reverse("products-search"), data=body)
        # we didn't set the sell_num for I123, so it will always be the last in search resurt
        items_sell_num_order = ('I124', 'I126', 'I125', 'I123')
        for item, item_id in zip(response.data['records'], items_sell_num_order):
            self.assertEqual(item['item_id'], item_id)
        items_sell_num_order = ('I125', 'I126', 'I124', 'I123')
        body['sort_fields'] = ['_score', '-sell_num']
        response = self.api_post(reverse("products-search"), data=body)
        for item, item_id in zip(response.data['records'], items_sell_num_order):
            self.assertEqual(item['item_id'], item_id)
        # test order by sell_num items with same ``_score`` in es response
        # when we query `能` with items in test_data1, we will get two items with same "_score": 0.3942705
        # so we use this query string for cell_num sort test
        body = {
            "q": "能",
            "search_config": {"type": "SEARCH_TEXT"},
            "sort_fields": ['origin_place', ],
            "api_key": self.api_key
        }
        response = self.api_post(reverse("products-search"), data=body)
        # test the sort_fields works with `original_place`
        items_sell_num_order = ('I125', 'I124')
        for item, item_id in zip(response.data['records'], items_sell_num_order):
            self.assertEqual(item['item_id'], item_id)
        items_sell_num_order = ('I124', 'I125')
        body['sort_fields'] = ['-original_place', ]
        response = self.api_post(reverse("products-search"), data=body)
        for item, item_id in zip(response.data['records'], items_sell_num_order):
            self.assertEqual(item['item_id'], item_id)

        # now we test the order by cell_num
        items_sell_num_order = ('I125', 'I124')
        body['sort_fields'] = ['-cell_num', ]
        response = self.api_post(reverse("products-search"), data=body)
        for item, item_id in zip(response.data['records'], items_sell_num_order):
            self.assertEqual(item['item_id'], item_id)
        items_sell_num_order = ('I124', 'I125')
        body['sort_fields'] = ['cell_num', ]
        response = self.api_post(reverse("products-search"), data=body)
        for item, item_id in zip(response.data['records'], items_sell_num_order):
            self.assertEqual(item['item_id'], item_id)

        # if we add two sort_fields, the frist one works
        items_sell_num_order = ('I125', 'I124')
        body['sort_fields'] = ['-cell_num', '-original_place']
        response = self.api_post(reverse("products-search"), data=body)
        for item, item_id in zip(response.data['records'], items_sell_num_order):
            self.assertEqual(item['item_id'], item_id)

        # the first sort_fields with different result value works
        # make I124/I125 have the same original_place
        item = test_data1.getItems(item_ids=["I124"])[0]
        item["original_place"] = 1
        response = self.postItem(item)
        # original_place with same value will not influence the search order
        items_sell_num_order = ('I125', 'I124')
        body['sort_fields'] = ['original_place', '-cell_num']
        response = self.api_post(reverse("products-search"), data=body)
        for item, item_id in zip(response.data['records'], items_sell_num_order):
            self.assertEqual(item['item_id'], item_id)

        body['sort_fields'] = ['-original_place', '-cell_num']
        response = self.api_post(reverse("products-search"), data=body)
        for item, item_id in zip(response.data['records'], items_sell_num_order):
            self.assertEqual(item['item_id'], item_id)

        items_sell_num_order = ('I124', 'I125')
        body['sort_fields'] = ['original_place', 'cell_num']
        response = self.api_post(reverse("products-search"), data=body)
        for item, item_id in zip(response.data['records'], items_sell_num_order):
            self.assertEqual(item['item_id'], item_id)

        body['sort_fields'] = ['-original_place', 'cell_num']
        response = self.api_post(reverse("products-search"), data=body)
        for item, item_id in zip(response.data['records'], items_sell_num_order):
            self.assertEqual(item['item_id'], item_id)

    def _test_search_dosage_prescription_type(self):
        body = {"api_key": self.api_key,
                "q": "雀巢",
                }
        for ft, fv_miss, fv_hit in (('dosage', 'test-dosage', '针剂'),
                                    ('prescription_type', 4, 3)):
            body['filters'] = {ft: [fv_miss,]}
            response = self.api_post(reverse("products-search"), data=body)
            self.assertEqual(response.data["info"]["total_result_count"], 0)
            body['filters'] = {ft: [fv_hit,]}
            response = self.api_post(reverse("products-search"), data=body)
            self.assertEqual(response.data["info"]["total_result_count"], 1)
            # stock field should be included
            self.assertEqual(response.data["records"][0].has_key("dosage"), True)
            self.assertEqual(response.data["records"][0].has_key("prescription_type"), True)
        body = {"api_key": self.api_key,
                "q": "",
                }
        response = self.api_post(reverse("products-search"), data=body)
        self.assertEqual(self.sortDictList(response.data["info"]["facets"]["brand"], by_key="id"),
                         [{"count": 1, "id": "22", "label": u"雀巢", 'brand_logo': 'http://logo.com/22'},
                         {"count": 2, "id": "23", "label": u"能恩", 'brand_logo': 'http://logo.com/23'},
                         {"count": 1, "id": "24", "label": u"智多星", 'brand_logo': 'http://logo.com/24'},
                        ])
        self.assertEqual(self.sortDictList(response.data["info"]["facets"]['prescription_type'], by_key="id"),
                        [{"count": 2, "id": 3, "label": ""},
                         {"count": 1, "id": 5, "label": ""},
                         {"count": 1, "id": 6, "label": ""}
                        ])
        self.assertEqual(self.sortDictList(response.data["info"]["facets"]['dosage'], by_key="id"),
                         self.sortDictList([{"count": 2, "id": u'针剂', "label": ""},
                                            {"count": 1, "id": u'粉剂', "label": ""},
                                            {"count": 1, "id": u'片剂', "label": ""}
                                        ], by_key="id"),)
        body = {"api_key": self.api_key,
                "q": "",
                'facets': {
                    'dosage': {},
                    'prescription_type': {}
                }}
        response = self.api_post(reverse("products-search"), data=body)
        self.assertEqual(self.sortDictList(response.data["info"]["facets"]['prescription_type'], by_key="id"),
                        [{"count": 2, "id": 3, "label": ""},
                         {"count": 1, "id": 5, "label": ""},
                         {"count": 1, "id": 6, "label": ""}
                        ])
        self.assertEqual(self.sortDictList(response.data["info"]["facets"]['dosage'], by_key="id"),
                         self.sortDictList([{"count": 2, "id": u'针剂', "label": ""},
                                            {"count": 1, "id": u'粉剂', "label": ""},
                                            {"count": 1, "id": u'片剂', "label": ""}
                                        ], by_key="id"),)

    def test_search(self):
        # TODO: highlight; sort_fields
        self._test_no_such_api_key()
        self._test_by_tags()
        self._test_search_empty_string()
        self._test_search_facets_under_a_category()
        self._test_search_filters()
        self._test_search1()
        self._test_search2()
        self._test_search_pagination()
        self._test_search_other_fields()
        #self._test_result_mode()
        self._test_search_facets_selection()
        #self._test_search_facets_of_whole_sub_tree()
        self._test_item_factory_subtitle()
        self._test_sell_num_sort()
        self._test_search_dosage_prescription_type()

    def _assertKWList(self, list_type, expected):
        keywords = set([keyword_record["keyword"] for keyword_record in self.mongo_client.getSuggestKeywordList(self.TEST_SITE_ID, list_type)])
        self.assertEqual(keywords, expected)

    def test_suggestion(self):
        # TODO: no such api error

        # first, unidentified keywords check
        all_keywords = u"雀巢 智多星 故事 奶粉 超级 童话 童话故事 365 能恩".split(" ")
        from apps.apis.search.keyword_list import keyword_list
        self._assertKWList(keyword_list.WHITE_LIST, set())
        self._assertKWList(keyword_list.BLACK_LIST, set())
        self._assertKWList(keyword_list.UNIDENTIFIED_LIST, set(all_keywords))

        # suggestion should return nothing
        body = {"api_key": self.api_key,
                "q": "童"
               }
        response = self.api_post(reverse("query-suggest"), data=body)
        self.assertEqual(response.data["errors"], [])
        self.assertEqual(response.data,
                         {"errors": [],
                          "suggestions": []
                         })

        # let's move some keywords as white listed.
        keyword_list.markKeywordsAsWhiteListed(self.TEST_SITE_ID, [u"童话"])
        self.refreshSiteItemIndex(self.TEST_SITE_ID)
        self.rebuildSuggestionCache()

        # check completion
        body = {"api_key": self.api_key,
                "q": u"童"
               }
        response = self.api_post(reverse("query-suggest"), data=body)
        self.assertEqual(response.data["errors"], [])
        self.assertEqual(response.data,
                         {"errors": [],
                          "suggestions": [{"count": 1, "type": "completion", "value": u"童话"}]
                         })

        keyword_list.markKeywordsAsWhiteListed(self.TEST_SITE_ID, all_keywords)
        self.refreshSiteItemIndex(self.TEST_SITE_ID)
        self.rebuildSuggestionCache()

        body = {"api_key": self.api_key,
                "q": "能恩"
               }
        response = self.api_post(reverse("query-suggest"), data=body)
        self.assertEqual(response.data["errors"], [])
        self.assertEqual(response.data,
                         {"errors": [],
                          "suggestions": [{'count': 1, 'type': 'more_keyword', 'value': u'能恩 超级'},
                                          {'count': 1, 'type': 'more_keyword', 'value': u'能恩 奶粉'}]
                         })

        body = {"api_key": self.api_key,
                "q": "奶粉"
               }
        response = self.api_post(reverse("query-suggest"), data=body)
        self.assertEqual(response.data["errors"], [])
        self.maxDiff=None
        self.assertEqual(response.data,
                         {'errors': [],
                          'suggestions': [{'count': 1, 'facet_label': u'分类12 > 分类12-02', 'type': 'facet',
                                           'value': u'奶粉',
                                           'category_id': u'1202',
                                           'field_name': 'categories'},
                                          {'count': 1, 'type': 'more_keyword', 'value': u'奶粉 雀巢'},
                                          {'count': 1, 'type': 'more_keyword', 'value': u'奶粉 能恩'}
                                          ]}
                         )

@override_settings(CELERY_EAGER_PROPAGATES_EXCEPTIONS=True,
                   CELERY_ALWAYS_EAGER=True,
                   BROKER_BACKEND='memory',
                   MINIMAL_KEYWORD_HOT_VIEW_LENGTH=4,
                   MINIMAL_KEYWORD_HOT_VIEW_COUNT=1
                   )
class HotKeywordsTest(BaseAPITest):
    def setUp(self):
        super(HotKeywordsTest, self).setUp()
        self.postItems(test_data1, None)

    def test_keywords(self):
        # Without calculation, we would get an empty keyword list
        body = {"api_key": self.api_key, "type": "hot"}
        response = self.api_get(reverse("keywords"), data=body)
        self.assertEqual(response.data["errors"], [])
        self.assertEqual(len(response.data["keywords"]), 0)

        # Add some search event
        # 2 感冒 in null, 2 感冒 in 123; 3 牛黄 in 123, but 感冒 should be the top.
        for q, category_id in (("牛黄 奶粉", "123"),
                               ("感冒 冲剂", "null"),
                               ("感冒 牛黄", "123"),
                               ("感冒 牛黄", "123"),
                               ("感冒 冲剂", "null")):
            self.api_get(reverse("recommender-events"),
                         data={"api_key": self.api_key,
                               "event_type": "Search",
                               "user_id": "U1",
                               "q": q,
                               "category_id": category_id})

        # run the update_keyword_hot_view_list task
        update_keyword_hot_view_list.delay(self.TEST_SITE_ID)

        # Now we should get some result
        body = {"api_key": self.api_key, "type": "hot", "amount": 1}
        response = self.api_post(reverse("keywords"), data=body)
        self.assertEqual(response.data["errors"], [])
        self.assertEqual(response.data["keywords"],
                         [u"感冒"]
                         )

        body = {"api_key": self.api_key, "type": "hot", "amount": 2}
        response = self.api_post(reverse("keywords"), data=body)
        self.assertEqual(response.data["errors"], [])
        self.assertEqual(response.data["keywords"],
                         [u"感冒", u"牛黄"]
                         )

        body = {"api_key": self.api_key, "type": "hot", "amount": 4}
        response = self.api_post(reverse("keywords"), data=body)
        self.assertEqual(response.data["errors"], [])
        self.assertEqual(response.data["keywords"],
                         [u"感冒", u"牛黄", u"冲剂", u"奶粉"]
                         )

        body = {"api_key": self.api_key,
                "type": "hot",
                "amount": 3
               }
        response = self.api_post(reverse("keywords"), data=body)
        self.assertEqual(response.data["errors"], [])
        self.assertEqual(len(response.data["keywords"]), 3)

        # test result after preset keywords
        response = self.api_post(reverse("recommender-keywords"),
                                 data={"api_key": self.api_key,
                                       "type": "hot",
                                       "action": "stick",
                                       "keywords": [u'滚滚', u'长江', u'东逝水']},
                                 **{"HTTP_AUTHORIZATION": "Token %s" % self.site_token})
        body = {"api_key": self.api_key,
                "type": "hot",
                "amount": 3
               }
        response = self.api_post(reverse("keywords"), data=body)
        self.assertEqual(response.data["errors"], [])

        self.assertEqual(response.data["keywords"],
                         [u'滚滚', u'长江', u'东逝水'])
        response = self.api_post(reverse("recommender-keywords"),
                                 data={"api_key": self.api_key,
                                       "type": "hot",
                                       "action": "stick",
                                       "keywords": [u'测试', u'中文', u'热词']},
                                 **{"HTTP_AUTHORIZATION": "Token %s" % self.site_token})
        body = {"api_key": self.api_key,
                "type": "hot",
                "amount": 3
               }
        response = self.api_post(reverse("keywords"), data=body)
        self.assertEqual(response.data["errors"], [])
        self.assertEqual(response.data["keywords"],
                         [u"测试", u"中文", u"热词"]
                         )
        body = {"api_key": self.api_key,
                "type": "hot",
                "amount": 4
               }
        response = self.api_post(reverse("keywords"), data=body)
        self.assertEqual(response.data["errors"], [])
        self.assertEqual(response.data["keywords"],
                         [u"测试", u"中文", u"热词", u"感冒"]
                         )
        response = self.api_post(reverse("recommender-keywords"),
                                 data={"api_key": self.api_key,
                                       "type": "hot",
                                       "action": "stick",
                                       "keywords": [u'测试', u'感冒', u'中文']},
                                 **{"HTTP_AUTHORIZATION": "Token %s" % self.site_token})
        response = self.api_post(reverse("keywords"), data=body)
        self.assertEqual(response.data["errors"], [])
        self.assertEqual(response.data["keywords"],
                         [u"测试", u"感冒", u"中文", u"牛黄"]
                         )

        for q, category_id in (("田七 奶粉", "123"),
                               ("感冒 田七", "null"),
                               ("感冒 田七", "123"),
                               ("感冒 田七", "123"),
                               ("感冒 田七", "null")):
            self.api_get(reverse("recommender-events"),
                         data={"api_key": self.api_key,
                               "event_type": "Search",
                               "user_id": "U1",
                               "q": q,
                               "category_id": category_id})
        update_keyword_hot_view_list.delay(self.TEST_SITE_ID)
        response = self.api_post(reverse("keywords"), data=body)
        self.assertEqual(response.data["errors"], [])
        self.assertEqual(response.data["keywords"],
                         [u"测试", u"感冒", u"中文", u"田七"]
                         )
