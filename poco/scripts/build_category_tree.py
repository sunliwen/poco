import json
import os.path
import hashlib
import urllib
import pprint
from bs4 import BeautifulSoup


items_path = "/Users/jacobfan/projects/ElasticSearchDemo/data/201312/items.json"


def load_items(items_path):
    f = open(items_path, "r")
    for line in f.readlines():
        item = json.loads(line)
        yield item
    f.close()


def scrape_category(category_id):
    full_url = "http://www.leyou.com.cn/product/category_i/%s" % category_id
    local_path = "CACHE/" + hashlib.md5(full_url).hexdigest()
    if os.path.isfile(local_path):
        content = open(local_path).read()
    else:
        content = urllib.urlopen(full_url).read()
        f = open(local_path, "w")
        f.write(content)
        f.close()
    soup = BeautifulSoup(content)
    return [a_elem.string for a_elem in soup.find("div", id="breadcrumb").find_all("a")][-1]

category_tree = {}
categories = {}
def run():
    #scrape_category("2210")
    #return
    count = 0
    for item in load_items(items_path):
        count += 1
        if (count % 10) == 0:
            print count, "|", len(categories)
        curr_node = category_tree
        level = 0
        for category in item["categories"]:
            level += 1
            if level > 2:
                break
            if categories.has_key(category):
                category_name = categories[category]
            else:
                category_name = scrape_category(category)
                categories[category] = category_name
            curr_node = curr_node.setdefault(category, {"name": category_name})
    pprint.pprint(category_tree)
    #categories = set(categories)
    #print len(categories)
