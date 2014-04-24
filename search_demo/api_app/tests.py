#encoding=utf8

import json
import copy
from django.test import TestCase
from django.test.utils import override_settings
from django.core.urlresolvers import reverse
from common import site_manage_utils
from common.mongo_client import getMongoClient
from api_app import es_search_functions
import test_data1


import pprint
def my_safe_repr(object, context, maxlevels, level):
    typ = pprint._type(object)
    if typ is unicode:
        r = 'u"%s"' % (object.encode("utf8").replace('"', r'\"'))
        return (r, True, False)
    else:
        return pprint._safe_repr(object, context, maxlevels, level)

def pprint_data(data):
    printer = pprint.PrettyPrinter()
    printer.format = my_safe_repr
    return printer.pprint(data)


class BaseSearchTest(TestCase):
    TEST_SITE_ID = "site_for_tests"

    def setUp(self):
        self.mongo_client = getMongoClient()
        self.es = es_search_functions.getESClient()
        site_manage_utils.drop_site(self.mongo_client, self.TEST_SITE_ID)
        site_record = site_manage_utils.create_site(self.mongo_client, self.TEST_SITE_ID, self.TEST_SITE_ID, 3600 * 24)
        self.api_key = site_record["api_key"]
        self.mongo_client.reloadApiKey2SiteID()
        self.maxDiff = None

    def refreshSiteItemIndex(self, site_id):
        self.es.indices.refresh(index=es_search_functions.getESItemIndexName(site_id))

    def assertItemsCount(self, expected_count):
        c_items = self.mongo_client.getSiteDBCollection(self.TEST_SITE_ID, "items")
        self.assertEqual(c_items.count(), expected_count)
        res = self.client.post(reverse("products-search"),
                         content_type="application/json",
                         data=json.dumps({"q": "", "api_key": self.api_key}))
        self.assertEqual(res.data["info"]["total_result_count"], expected_count)

    def sortDictList(self, dictList, by_key):
        dictList.sort(lambda a,b: cmp(a[by_key], b[by_key]))
        return dictList

# refs: http://stackoverflow.com/questions/4055860/unit-testing-with-django-celery
# refs: http://docs.celeryproject.org/en/2.5/django/unit-testing.html
@override_settings(CELERY_EAGER_PROPAGATES_EXCEPTIONS=True,
                   CELERY_ALWAYS_EAGER=True,
                   BROKER_BACKEND='memory')
class ItemsSearchViewTest(BaseSearchTest):
    def setUp(self):
        super(ItemsSearchViewTest, self).setUp()
        self.postItems(None)

    def api_post(self, path, content_type="application/json", data={}, expected_status_code=200):
        response = self.client.post(path, content_type=content_type, data=json.dumps(data))
        self.assertEqual(response.status_code, expected_status_code)
        return response

    def postItems(self, item_ids):
        self.assertItemsCount(0)
        items = test_data1.getItems(None)
        for item in items:
            item["api_key"] = self.api_key
            response = self.api_post(reverse("recommender-items"), data=item)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data["code"], 0, "Invalid res: %s" % response.data)
        self.refreshSiteItemIndex(self.TEST_SITE_ID)
        self.assertItemsCount(len(items))
        from api_app.tasks import rebuild_suggestion_cache
        rebuild_suggestion_cache.delay(self.TEST_SITE_ID)

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
                        [{"count": 3, "id": "12", "label": u"分类12"},
                         {"count": 1, "id": "15", "label": u"分类15"},
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
                        [{"count": 2, "id": "1201", "label": u"分类12-01"},
                         {"count": 1, "id": "1202", "label": u"分类12-02"}
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
        print response
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
        self._test_search_empty_string()
        self._test_search_facets_under_a_category()
        self._test_search_filt_by_brand()
        self._test_search1()
        self._test_search2()
        self._test_search_pagination()
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
