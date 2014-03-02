from elasticsearch import Elasticsearch
from elasticsearch.client import IndicesClient


# refs: http://www.elasticsearch.org/guide/en/elasticsearch/reference/1.x/mapping-array-type.html
# use this one: http://www.elasticsearch.org/blog/you-complete-me/
def run():
    es = Elasticsearch()
    res = es.indices.put_mapping(index="item-index", doc_type="item", 
                   body={
                    "item": {
                        "properties": {
                            "available": {"type": "boolean"},
                            "item_name": {"type": "string"},
                            "price": {"type": "string"},
                            "image_link": {"type": "string"},
                            "item_link": {"type": "string"},
                            "categories": {"type": "string"},
                            "item_name_suggest": {
                                "type": "completion",
                                "index_analyzer": "simple",
                                "search_analyzer": "simple",
                                "payloads": False
                            }
                        }
                    }
                   })
    print res
    es.indices.refresh(index='item-index')
