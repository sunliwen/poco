#encoding=utf8

import json
import copy
from django.test.utils import override_settings
from django.core.urlresolvers import reverse
from common import site_manage_utils
from common.mongo_client import getMongoClient
from api_app import es_search_functions
from common.test_utils import BaseAPITest
from common import test_data1


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
        body = {"api_key": self.api_key,
                "q": ""
                }
        response = self.api_post(reverse("products-search"), data=body)
        #import pprint; pprint.pprint(response.data)
        self.assertEqual(response.data["info"]["total_result_count"], 4)
        self.assertEqual(self.sortDictList(response.data["info"]["facets"]["brand"], by_key="id"), 
                        [{"count": 1, "id": "22", "label": u"雀巢"},
                         {"count": 2, "id": "23", "label": u"能恩"},
                         {"count": 1, "id": "24", "label": u"智多星"}
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
                        [{"count": 1, "id": "22", "label": u"雀巢"},
                         {"count": 2, "id": "23", "label": u"能恩"}
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

    def _test_search_filt_by_brand(self):
        body = {"api_key": self.api_key,
            "q": "",
            "filters": {
                "brand": ["23"]
            }
        }
        response = self.api_post(reverse("products-search"), data=body)
        print response
        self.assertEqual(response.data["info"]["total_result_count"], 2)

    def _test_search1(self):
        body = {"api_key": self.api_key,
                "q": "雀巢"
                }
        response = self.api_post(reverse("products-search"), data=body)
        self.assertEqual(response.data["info"]["total_result_count"], 1)
        response

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
                {"brand": [{"count": 1, "id": "22", "label": u"雀巢"},
                         {"count": 2, "id": "23", "label": u"能恩"},
                         {"count": 1, "id": "24", "label": u"智多星"}
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
        print response
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
        print response.data["info"]["facets"]
        self.assertEqual(response.data["info"]["facets"], 
                {"brand": [{"count": 1, "id": "22", "label": u"雀巢"},
                         {"count": 2, "id": "23", "label": u"能恩"},
                         {"count": 1, "id": "24", "label": u"智多星"}
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
                {"brand": [{"count": 1, "id": "22", "label": u"雀巢"},
                         {"count": 2, "id": "23", "label": u"能恩"},
                         {"count": 1, "id": "24", "label": u"智多星"}
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
                {"brand": [{"count": 1, "id": "22", "label": u"雀巢"},
                         {"count": 2, "id": "23", "label": u"能恩"},
                         {"count": 1, "id": "24", "label": u"智多星"}
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

    def test_search(self):
        # TODO: highlight; sort_fields
        self._test_no_such_api_key()
        self._test_by_tags()
        self._test_search_empty_string()
        self._test_search_facets_under_a_category()
        self._test_search_filt_by_brand()
        self._test_search1()
        self._test_search2()
        self._test_search_pagination()
        #self._test_result_mode()
        self._test_search_facets_selection()
        #self._test_search_facets_of_whole_sub_tree()

    def test_suggestion(self):
        # TODO: no such api error
        body = {"api_key": self.api_key,
                "q": "能恩"
               }
        response = self.api_post(reverse("query-suggest"), data=body)
        self.assertEqual(response.data["errors"], [])
        self.assertEqual(response.data, 
                         {"errors": [],
                          "suggestions": [{'count': 1, 'type': 'more_keyword', 'value': u'能恩 奶粉'}]
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
