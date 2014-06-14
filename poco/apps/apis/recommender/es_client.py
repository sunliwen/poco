from elasticsearch import Elasticsearch
from apps.apis.search import es_search_functions
from apps.apis.search.keyword_list import keyword_list

#from misc.keyword_whitelist import KEYWORD_WHITELIST
def fill_keywords(site_id, item):
    item_name = item["item_name"]
    keywords = " ".join(es_search_functions.preprocess_query_str(item_name)).split(" ")
    whitelisted_keywords = keyword_list.processKeywords(site_id, keywords)
    #item["keywords"] = whitelisted_keywords
    item["keywords"] = keywords


def preprocess_categories(categories):
    for_facets = ["%s__%s" % (category["parent_id"], category["id"]) for category in categories]
    return [category["id"] for category in categories] + for_facets


def es_index_item(site_id, item):
    es = Elasticsearch()
    
    fill_keywords(site_id, item)
    
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

    #if item.has_key("origin_place"):
    #    item["origin_place"] = str(item["origin_place"])

    item["categories"] = preprocess_categories(item["categories"])
    brand = item.get("brand", None)
    if brand:
        item["brand"] = brand["id"]
        item["brand_name"] = brand.get("name", "")

    res = es.index(index=es_search_functions.getESItemIndexName(site_id), doc_type='item', id=item["item_id"], body=item)


#def es_update_items_keywords(site_id):
#    # FIXME: there may be race condition with new items update come it
#    # TODO: get all items from mongodb
#    for item in items:
#        es_index_item(site_id, item)
