from apps.apis.search.keyword_list import keyword_list
from apps.apis.search import es_search_functions

def get_index_setting():
    return {
        "number_of_shards": 1,
        "index": {
            "analysis": {
                "analyzer": {
                    "whitespace_lower_analyzer": {
                        "tokenizer": "whitespace",
                        "filter": ["lowercase"]
                    },
                    "mycn_analyzer_whitespace_pinyin_first_n_full": {
                        "type": "custom",
                        "tokenizer": "whitespace",
                        "filter": ["my_pinyin_first_n_full"]
                    },
                    "ngram_analyzer": {
                        "type":      "custom",
                        "tokenizer": "ngram_tokenizer",
                        "filter": ['standard',]
                    },
                },
                "filter": {
                    "my_pinyin_first_n_full": {
                        "type": "pinyin",
                        "first_letter": "prefix",
                        "padding_char": "||"
                    }
                },
                "tokenizer": {
                    "ngram_tokenizer" : {
                        "type" : "nGram",
                        "min_gram" : "2",
                        "max_gram" : "30",
                        "token_chars": ["letter", "digit"]
                    }
                }
            }
        }}

def get_site_mapping():
    return {"keyword": {
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
                "description": {"type": "string"},
                "factory": {"type": "string"},
                "price": {"type": "float"},
                "market_price": {"type": "float"},
                "image_link": {"type": "string"},
                "item_link": {"type": "string"},
                "categories": {"type": "string", "index_name": "category"},
                "brand": {"type": "string"},
                "brand_name": {"type": "string", "analyzer": "standard"},
                "item_level": {"type": "integer"},
                "item_spec": {"type": "string"},
                "item_spec_ng": {"type": "string",  "analyzer": "ngram_analyzer"},
                "origin_place": {"type": "integer"},
                "item_comment_num": {"type": "integer"},
                "keywords": {"type": "string",
                             "analyzer": "keyword"},
                "tags": {"type": "string", "analyzer": "keyword"},
                "tags_standard": {"type": "string", "analyzer": "standard"},
                "sku": {"type": "string", "analyzer": "keyword"},
                "sell_num": {"type": "integer"},
                "dosage": {"type": "string", "analyzer": "keyword"},
                "prescription_type": {"type": "integer"},
                "item_sub_title": {"type": "string"},
            }
        }
    }


def get_index_item(site_id, item):
    def preprocess_categories(categories):
        for_facets = ["%s__%s" % (category["parent_id"], category["id"]) for category in categories]
        return [category["id"] for category in categories] + for_facets
    # keywords
    item_name = item["item_name"]
    keywords = " ".join(es_search_functions.preprocess_query_str(item_name)).split(" ")
    whitelisted_keywords = keyword_list.processKeywords(site_id, keywords)
    #item["keywords"] = whitelisted_keywords
    item["keywords"] = keywords

    item["item_name_standard_analyzed"] = item["item_name"]
    item["item_name_no_analysis"] = item["item_name"]
    item["item_name"] = " ".join(es_search_functions.preprocess_query_str(item["item_name"]))

    item["tags_standard"] = item["tags"]

    if item.has_key("price"):
        item["price"] = float(item["price"])
    if item.has_key("market_price"):
        item["market_price"] = float(item["market_price"])
    if item.has_key("_id"):
        del item["_id"]
    if item.has_key("created_on"):
        del item["created_on"]
    if item.has_key("updated_on"):
        del item["updated_on"]
    if item.has_key("item_spec") and item['item_spec']:
        item['item_spec_ng'] = es_search_functions.strip_item_spec(item['item_spec'])

    #if item.has_key("origin_place"):
    #    item["origin_place"] = str(item["origin_place"])

    item["categories"] = preprocess_categories(item["categories"])
    brand = item.get("brand", None)
    if brand:
        item["brand"] = brand["id"]
        item["brand_name"] = brand.get("name", "")
