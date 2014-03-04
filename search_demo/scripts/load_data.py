import json
import pprint
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import NotFoundError


#items_path = "/Users/jacobfan/projects/ElasticSearchDemo/data/201312/items.json"


def load_items(items_path):
    f = open(items_path, "r")
    for line in f.readlines():
        item = json.loads(line)
        yield item
    f.close()


def createIndex(es):
    try:
        es.indices.delete("item-index")
    except NotFoundError:
        pass
    res = es.indices.create(index="item-index", 
               #doc_type="item", 
               body={
                "settings": {
                    "number_of_shards": 1
                 },
                "mappings": {
                    "item": {
                        "properties": {
                            "available": {"type": "boolean"},
                            "item_name": {"type": "string"},
                            "price": {"type": "string"},
                            "image_link": {"type": "string"},
                            "item_link": {"type": "string"},
                            "categories": {"type": "string", "index_name": "category"},
                            "item_name_suggest": {
                                "type": "completion",
                                "index_analyzer": "simple",
                                "search_analyzer": "simple",
                                "payloads": False
                            }
                        }
                    }
                }
               }
               )


import jieba
def get_item_name_suggest(item):
    return {"input": [term for term in jieba.cut_for_search(item["item_name"]) if len(term) > 1],
            "output": item["item_name"]}


# TODO: handling elasticsearch.exceptions.ConnectionError
# TODO: check elasticsearch array search problem
def run(items_path):
    count = 0
    print "Begin Loading ..."
    items = load_items(items_path)
    es = Elasticsearch()
    createIndex(es)

    # TODO: use bulk
    for item in items:
        count += 1
        if (count % 50) == 0:
            print count
        item["item_name_suggest"] = get_item_name_suggest(item)
        del item["_id"]
        item["categories"] = " ".join(item["categories"])
        #pprint.pprint(item)
        res = es.index(index='item-index', doc_type='item', id=item["item_id"], body=item)
        #print item
    es.indices.refresh(index='item-index')
    print "Finish Loading"
