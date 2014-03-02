# encoding=utf8
import pprint
from elasticsearch import Elasticsearch


def run():
    es = Elasticsearch()
    res = es.suggest("item-index", 
        {"item": {
            "text": "B&B",
            #"match": {
            #    "field": "item_name"
            #}
            "completion": {
                "field": "item_name_suggest"
            }
        }
        })
    pprint.pprint(res)
