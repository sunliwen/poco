#encoding=utf8

import json
import copy
from django.test import TestCase
from django.test.utils import override_settings
from django.core.urlresolvers import reverse
from common import site_manage_utils
from common.mongo_client import getMongoClient
from api_app import es_search_functions


PRODUCTS = [
            {
            "type": "product",
            "available": True,
            "item_id": "I123",
            "item_name": "产品1234",
            "item_link": "",
            "brand": {
                "type": "brand",
                "id": "22",
                "name": "雀巢",
            },
            "item_level": 5,
            "item_comment_num": 15,
            "origin_place": 0,
            "categories": [
                {
                    "type": "category",
                    "id": "123",
                    "name": "分类1",
                    "parent_id": "null"
                },
                {
                    "type": "category",
                    "id": "234",
                    "name": "分类2",
                    "parent_id": "123"
                }
            ]},
            {
            "type": "product",
            "item_id": "I124",
            "item_name": "能恩超级",
            "item_link": "",
            "brand": {
                "type": "brand",
                "id": "23",
                "name": "能恩",
            },
            "item_level": 3,
            "item_comment_num": 10,
            "origin_place": 1,
            "categories": [
                {
                    "type": "category",
                    "id": "123",
                    "name": "分类1",
                    "parent_id": "null"
                },
                {
                    "type": "category",
                    "id": "333",
                    "name": "分类3",
                    "parent_id": "123"
                }
            ]},
            {
            "type": "product",
            "item_id": "I124",
            "item_name": "能恩米粉",
            "item_link": "",
            "brand": {
                "type": "brand",
                "id": "23",
                "name": "能恩",
            },
            "item_level": 3,
            "item_comment_num": 10,
            "origin_place": 0,
            "categories":[
                {
                    "type": "category",
                    "id": "123",
                    "name": "分类1",
                    "parent_id": "null"
                },
                {
                    "type": "category",
                    "id": "333",
                    "name": "分类3",
                    "parent_id": "123"
                }
            ]}
            ]


# refs: http://stackoverflow.com/questions/4055860/unit-testing-with-django-celery
# refs: http://docs.celeryproject.org/en/2.5/django/unit-testing.html
@override_settings(CELERY_EAGER_PROPAGATES_EXCEPTIONS=True,
                   CELERY_ALWAYS_EAGER=True,
                   BROKER_BACKEND='memory')
class ProductsSearchViewTests(TestCase):
    TEST_SITE_ID = "site_for_tests"

    def setUp(self):
        print "SETUP"
        self.mongo_client = getMongoClient()
        self.es = es_search_functions.getESClient()
        site_manage_utils.drop_site(self.mongo_client, self.TEST_SITE_ID)
        site_record = site_manage_utils.create_site(self.mongo_client, self.TEST_SITE_ID, self.TEST_SITE_ID, 3600 * 24)
        self.api_key = site_record["api_key"]
        # FIXME  the mongo_client usage should be centalized and easy to reload
        from api_app import views
        from recommender import action_processors
        views.mongo_client.reloadApiKey2SiteID()
        action_processors.mongo_client.reloadApiKey2SiteID()

    def refreshSiteItemIndex(self, site_id):
        self.es.indices.refresh(index=es_search_functions.getESItemIndexName(site_id))

    def assertItemsCount(self, expected_count):
        c_items = self.mongo_client.getSiteDBCollection(self.TEST_SITE_ID, "items")
        self.assertEqual(c_items.count(), expected_count)
        # TODO also check ES index
        from elasticsearch import Elasticsearch
        es = Elasticsearch()
        res = self.client.post(reverse("products-search"),
                         content_type="application/json",
                         data=json.dumps({"q": "1234", "api_key": self.api_key}))
        print res
        self.assertEqual(res.data["info"]["total_result_count"], expected_count)

    def getProductRecord(self, item_id):
        for product in PRODUCTS:
            if product["item_id"] == item_id:
                return copy.deepcopy(product)
        return None

    def test_no_such_api_key(self):
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
    
    def test_search(self):
        print "API_KEY:", self.api_key
        self.assertItemsCount(0)
        product = self.getProductRecord("I123")
        product["api_key"] = self.api_key
        response = self.client.post(reverse("recommender-items"),
                                    content_type="application/json",
                                    data=json.dumps(product))
        self.refreshSiteItemIndex(self.TEST_SITE_ID)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["code"], 0, "Invalid res: %s" % response.data)
        self.assertItemsCount(1)

