import json
from django.test import TestCase
from django.core.urlresolvers import reverse
from common.site_manage_utils import reset_items


class ProductsSearchViewTests(TestCase):
    #def setUp(self):
    #    reset_items("")

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
    
