from elasticsearch import Elasticsearch
from api_app import es_search_functions


from misc.keyword_whitelist import KEYWORD_WHITELIST
def fill_keywords(item):
    item_name = item["item_name"]
    keywords = " ".join(es_search_functions.preprocess_query_str(item_name)).split(" ")
    keywords = [keyword for keyword in keywords if keyword.encode("utf8") in KEYWORD_WHITELIST]
    item["keywords"] = keywords

INDEXED_KEYWORDS = {}
def index_keywords(es, site_id, item):
    raw_keywords = item["keywords"]
    res = es.indices.analyze(index=es_search_functions.getESItemIndexName(site_id), text=" ".join(raw_keywords),
                             analyzer="mycn_analyzer_whitespace_pinyin_first_n_full")
    for token_idx in range(len(res["tokens"])):
        token = res["tokens"][token_idx]
        raw_keyword = raw_keywords[token_idx]
        if not INDEXED_KEYWORDS.has_key(raw_keyword):
            INDEXED_KEYWORDS[raw_keyword] = True
            splitted_token = token["token"].split("||")
            first_letters = splitted_token[0]
            full_pinyin = "".join(splitted_token[1:])
            result = {"keyword_completion": {"input": [raw_keyword, full_pinyin, first_letters], "output": raw_keyword}}
            es.index(index=es_search_functions.getESItemIndexName(site_id), doc_type='keyword', body=result)


def preprocess_categories(categories):
    for_facets = ["%s__%s" % (category["parent_id"], category["id"]) for category in categories]
    return [category["id"] for category in categories] + for_facets

def es_index_item(site_id, item):
    es = Elasticsearch()
    
    fill_keywords(item)
    index_keywords(es, site_id, item)
    
    item["item_name_standard_analyzed"] = item["item_name"]
    item["item_name_no_analysis"] = item["item_name"]
    item["item_name"] = " ".join(es_search_functions.preprocess_query_str(item["item_name"]))
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

    res = es.index(index=es_search_functions.getESItemIndexName(site_id), doc_type='item', id=item["item_id"], body=item)


#def es_update_items_keywords(site_id):
#    # FIXME: there may be race condition with new items update come it
#    # TODO: get all items from mongodb
#    for item in items:
#        es_index_item(site_id, item)
