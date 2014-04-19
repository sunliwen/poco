from elasticsearch import Elasticsearch
from elasticsearch.exceptions import NotFoundError

from api_app import es_search_functions

INDEX_SETTINGS =  {
                     "number_of_shards": 1,
                     "index" : {
                        "analysis" : {
                            "analyzer" : {
                                "whitespace_lower_analyzer": {
                                    "tokenizer": "whitespace",
                                    "filter": ["lowercase"]
                                },
                                "mycn_analyzer_whitespace_pinyin_first_n_full": {
                                    "type": "custom",
                                    "tokenizer": "whitespace",
                                    "filter": ["my_pinyin_first_n_full"]
                                },
                            },
                            "filter": {
                                "my_pinyin_first_n_full": {
                                    "type": "pinyin",
                                    "first_letter": "prefix",
                                    "padding_char": "||"
                                }
                            }
                        }
                     }
                 }


MAPPINGS = {"keyword": {
            "properties": {
            "keyword_completion": {
                "type": "completion",
                "index_analyzer": "simple",
                "search_analyzer": "simple"
                }
            }
        },
        "item": {
            "properties": {
                "available": {"type": "boolean"},
                "item_name": {
                    "type": "string",
                    "store": "yes",
                    "analyzer": "whitespace_lower_analyzer"
                },
                "item_name_standard_analyzed": {
                    "type": "string",
                    "store": "yes",
                    "analyzer": "standard"
                },
                "item_name_no_analysis": {
                    "type": "string",
                    "store": "yes",
                    "analyzer": "keyword"
                },
                "price": {"type": "float"},
                "market_price": {"type": "float"},
                "image_link": {"type": "string"},
                "item_link": {"type": "string"},
                "categories": {"type": "string", "index_name": "category"},
                "brand": {"type": "string"},
                "item_level": {"type": "integer"},
                "item_spec": {"type": "string"},
                "origin_place": {"type": "integer"},
                "item_comment_num": {"type": "integer"},
                "keywords": {"type": "string",
                             "analyzer": "keyword"},
            }
        }
    }


def resetIndex(es, site_id):
    item_index = es_search_functions.getESItemIndexName(site_id)

    try:
        es.indices.delete(item_index)
    except NotFoundError:
        pass
    try:
        es.indices.delete(keyword_index)
    except NotFoundError:
        pass

    res = es.indices.create(index=item_index, body={"mappings": MAPPINGS, "settings": INDEX_SETTINGS})


def run(site_id):
    answer = raw_input("Do you really want to reset the item index of site: '%s'?(enter 'yes' to continue)" % site_id)
    if answer == "yes":
        es = Elasticsearch()
        resetIndex(es, site_id)
    else:
        print "Exit without action."
