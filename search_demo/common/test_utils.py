import json
import copy
from django.test import TestCase
from api_app import es_search_functions
from django.core.urlresolvers import reverse
import site_manage_utils
from common.mongo_client import getMongoClient

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


class Missing:
    pass


class BaseAPITest(TestCase):
    TEST_SITE_ID = "site_for_tests"

    def setUp(self):
        self.mongo_client = getMongoClient()
        self.es = es_search_functions.getESClient()
        site_record = self.initSite(self.TEST_SITE_ID)
        self.api_key = site_record["api_key"]
        self.site_token = site_record["site_token"]

        self.maxDiff = None

    def initSite(self, site_id):
        site_manage_utils.drop_site(self.mongo_client, site_id)
        site_record = site_manage_utils.create_site(self.mongo_client, site_id, site_id, 3600 * 24)
        self.mongo_client.reloadApiKey2SiteID()
        return site_record

    def assertSeveralKeys(self, dict1, dict2):
        for key in dict2.keys():
            self.assertEqual(dict1.get(key, Missing), dict2.get(key, Missing), "key: '%s' is different, dict1:%s, dict2: %s" % (key, dict1, dict2))

    def sortDictList(self, dictList, by_key):
        dictList.sort(lambda a,b: cmp(a[by_key], b[by_key]))
        return dictList

    def refreshSiteItemIndex(self, site_id):
        self.es.indices.refresh(index=es_search_functions.getESItemIndexName(site_id))

    def assertItemsCount(self, expected_count):
        c_items = self.mongo_client.getSiteDBCollection(self.TEST_SITE_ID, "items")
        self.assertEqual(c_items.count(), expected_count)
        res = self.client.post(reverse("products-search"),
                         content_type="application/json",
                         data=json.dumps({"q": "", "api_key": self.api_key}))
        self.assertEqual(res.data["errors"], [], "Invalid response: %s" % res.data)
        self.assertEqual(res.data["info"]["total_result_count"], expected_count)

    def postItem(self, item, site_token=None):
        if site_token is None:
            site_token = self.site_token
        item["api_key"] = self.api_key
        response = self.api_post(reverse("recommender-items"), data=item,
                                    **{"HTTP_AUTHORIZATION": "Token %s" % site_token})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["code"], 0, "Invalid res: %s" % response.data)
        self.refreshSiteItemIndex(self.TEST_SITE_ID)
        self.rebuildSuggestionCache()
        return response

    def rebuildSuggestionCache(self):
        from api_app.tasks import rebuild_suggestion_cache
        rebuild_suggestion_cache.delay(self.TEST_SITE_ID)

    def postItems(self, test_data_module, item_ids, site_token=None):
        self.assertItemsCount(0)
        items = test_data_module.getItems(None)
        for item in items:
            self.postItem(item, site_token)
        self.assertItemsCount(len(items))

    def api_post(self, path, content_type="application/json", data={}, expected_status_code=200, **extra):
        response = self.client.post(path, content_type=content_type, data=json.dumps(data), **extra)
        self.assertEqual(response.status_code, expected_status_code)
        return response

    def api_get(self, path, content_type="application/json", data={}, expected_status_code=200, **extra):
        response = self.client.get(path, content_type=content_type, data=data, **extra)
        self.assertEqual(response.status_code, expected_status_code)
        return response

