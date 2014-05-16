#encoding=utf8
import time
from elasticsearch import Elasticsearch

import jieba
def preprocess_query_str(query_str):
    result = []
    keywords = [keyword for keyword in query_str.split(" ") if keyword.strip() != ""]
    for keyword in keywords:
        cutted_keyword = " ".join(["%s" % term for term in jieba.cut_for_search(keyword)])
        result.append(cutted_keyword)
    return result


# refs: http://www.elasticsearch.org/guide/en/elasticsearch/reference/current/query-dsl-bool-query.html
def construct_query(query_str, for_filter=False):
    splitted_keywords = " ".join(preprocess_query_str(query_str)).split(" ")
    match_phrases = []
    for keyword in splitted_keywords:
        match_phrases.append({"match_phrase": {"item_name_standard_analyzed": keyword}})

    if for_filter:
        query = {
            "bool": {
                "must": match_phrases
            }
        }
    else:
        query = {
            "bool": {
                "must": match_phrases,
                "should": [
                    {'match': {'item_name': {"boost": 2.0, 
                                             'query': splitted_keywords,
                                             'operator': "and"}}}
                ]
            }
        }

    return query


query = construct_query("雀巢奶粉")

es = Elasticsearch()
t1 = time.time()
for i in range(500):
    res = es.search(index="item-index", 
              search_type="count",
              body={"query": query, "filter": {"term": {"available": True}}})
t2 = time.time()
print t2 - t1
