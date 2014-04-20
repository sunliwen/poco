#encoding=utf8
import json
import time
#from recommender import es_client
from recommender.action_processors import UpdateItemProcessor
from main_app import views as main_views
from common.api_client import APIClient


def load_items(items_path):
    f = open(items_path, "r")
    for line in f.readlines():
        item = json.loads(line)
        yield item
    f.close()


def tweak_item(item):
    categories = []
    for category_id in item["categories"]:
        category_data = main_views.CATEGORY_MAP_BY_ID.get(category_id, None)
        if category_data:
            category = {"type": "category", 
                        "id": category_data["id"], 
                        "parent_id": category_data["parent_id"],
                        "name": category_data["name"]}
            if category["parent_id"] is None:
                category["parent_id"] = "null"
            categories.append(category)
    item["categories"] = categories
    del item["_id"]
    del item["created_on"]
    if item.has_key("updated_on"):
        del item["updated_on"]
    if item.has_key("removed_on"):
        del item["removed_on"]
    item["type"] = "product"
    #print item
    return item


def run(site_id, items_path):
    print "DATA SET:", items_path
    answer = raw_input("Do you really want to load leyou data into site: %s? (yes to continue)" % site_id)
    api_prefix = raw_input("api_prefix:")
    api_key = raw_input("api_key:")
    if answer == "yes":
        items = load_items(items_path)
        t1 = time.time()
        count = 0
        #updp = UpdateItemProcessor()
        api_client = APIClient(api_prefix)
        for item in items:
            item = tweak_item(item)
            count += 1
            if (count % 50) == 0:
                t2 = time.time()
                print count, count/(t2-t1)
            #es_client.es_index_item(site_id, item)
            #updp._updateItem(site_id, item)
            item["api_key"] = api_key
            res = api_client("private/items/", {}, body=item)
            if res["code"] != 0:
                print res
    else:
        print "Action cancelled."
