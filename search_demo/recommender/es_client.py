from elasticsearch import Elasticsearch


from misc.keyword_whitelist import KEYWORD_WHITELIST
def fill_keywords(item):
    item_name = item["item_name"]
    keywords = " ".join(preprocess_query_str(item_name)).split(" ")
    #print "KW0:", " ".join(keywords)
    #for keyword in keywords:
    #    print keyword, keyword.encode("utf8") in KEYWORD_WHITELIST, keyword in KEYWORD_WHITELIST
    keywords = [keyword for keyword in keywords if keyword.encode("utf8") in KEYWORD_WHITELIST]
    item["keywords"] = keywords
    #print "KWS:", keywords

INDEXED_KEYWORDS = {}
def index_keywords(es, item):
    raw_keywords = item["keywords"]
    res = es.indices.analyze(index="item-index", text=" ".join(raw_keywords),
                             analyzer="mycn_analyzer_whitespace_pinyin_first_n_full")
    for token_idx in range(len(res["tokens"])):
        token = res["tokens"][token_idx]
        raw_keyword = raw_keywords[token_idx]
        if not INDEXED_KEYWORDS.has_key(raw_keyword):
            #print "RKK:", raw_keyword
            INDEXED_KEYWORDS[raw_keyword] = True
            splitted_token = token["token"].split("||")
            first_letters = splitted_token[0]
            full_pinyin = "".join(splitted_token[1:])
            result = {"keyword_completion": {"input": [raw_keyword, full_pinyin, first_letters], "output": raw_keyword}}
            es.index(index='item-index', doc_type='keyword', body=result)

import jieba
def preprocess_query_str(query_str):
    result = []
    keywords = [keyword for keyword in query_str.split(" ") if keyword.strip() != ""]
    for keyword in keywords:
        cutted_keyword = " ".join(["%s" % term for term in jieba.cut_for_search(keyword)])
        result.append(cutted_keyword)
    return result

def es_index_item(item):
    es = Elasticsearch()
    fill_keywords(item)
    index_keywords(es, item)
    item["item_name_standard_analyzed"] = item["item_name"]
    item["item_name_no_analysis"] = item["item_name"]
    item["item_name"] = " ".join(preprocess_query_str(item["item_name"]))
    if item.has_key("price"):
        item["price"] = float(item["price"])
    if item.has_key("market_price"):
        item["market_price"] = float(item["market_price"])
    del item["_id"]
    del item["created_on"]
    del item["updated_on"]
    print "ITEM:", item
    res = es.index(index='item-index', doc_type='item', id=item["item_id"], body=item)

