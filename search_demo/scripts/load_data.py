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


# refs: https://github.com/medcl/elasticsearch-analysis-pinyin
def createIndex(es):
    try:
        es.indices.delete("item-index")
    except NotFoundError:
        pass
    # pinying + ngram
    # TODO: check alternative options
    # TODO: check this http://bbs.elasticsearch.cn/discussion/245/elasticsearch-analysis-pinyin%E6%8F%92%E4%BB%B6%E4%BD%BF%E7%94%A8%E9%97%AE%E9%A2%98/p1
    # TODO: about pinying plugin's different options http://log.medcl.net/item/2012/06/release-elasticsearch-analysis-pinyin/
    # TODO: check elasticsearch.yml
    mappings =   {
                    "item": {
                        "properties": {
                            "available": {"type": "boolean"},
                            "item_name": {"type": "multi_field",
                                          "fields": {
                                            "item_name": {
                                                "type": "string",
                                                "store": "no",
                                                "term_vector": "with_positions_offsets",
                                                #"analyzer": "pinyin_ngram_analyzer",
                                                #"analyzer": "mycn_analyzer_wt_ngram",
                                                #"analyzer": "mycn_analyzer_mmseg",
                                                #"analyzer": "mycn_analyzer_jieba_index",
                                                "analyzer": "whitespace_pinyin_analyzer",
                                                "boost": 10
                                            },
                                            "primitive": {
                                                "type": "string",
                                                "store": "yes",
                                                "analyzer": "whitespace"
                                                #"analyzer": "keyword"
                                            }
                                          }
                                          },
                            "price": {"type": "string"},
                            "image_link": {"type": "string"},
                            "item_link": {"type": "string"},
                            "categories": {"type": "string", "index_name": "category"},
                            "item_name_suggest": {
                                "type": "completion",
                                "index_analyzer": "simple",
                                #"search_analyzer": "simple",
                                "search_analyzer": "mycn_analyzer_pinyin_fully",
                                #"term_vector": "with_positions_offsets",
                                #"index_analyzer": "pinyin_ngram_analyzer",
                                #"search_analyzer": "pinyin_ngram_analyzer",
                                "payloads": False
                            }
                        }
                    }
                }


    res = es.indices.create(index="item-index", 
               #doc_type="item", 
               body={
                "settings": {
                    "number_of_shards": 1,
                 "index" : {
                    "analysis" : {
                        "analyzer" : {
                            "whitespace_pinyin_analyzer": {
                                "tokenizer": "whitespace",
                                "filter": ["my_pinyin_f"]
                            },
                            #"pinyin_ngram_analyzer" : {
                            #    "tokenizer" : ["my_pinyin"],
                            #    "filter" : ["standard","nGram"] # TODO: check why.
                            #},
                            "mycn_analyzer_pinyin_fully": {
                                "type": "custom",
                                "tokenizer": "keyword",
                                "filter": ["my_pinyin_f"]
                            },
                            "mycn_analyzer_pinyin_first_only": {
                                "type": "custom",
                                "tokenizer": "keyword",
                                "filter": ["my_pinyin_first_only"]
                            },
                            "mycn_analyzer_wt_ngram": {
                                "type": "custom",
                                "tokenizer": "keyword",
                                "filter": ["my_pinyin_f", "ngram_1_to_2"]
                            },
                            #"mycn_analyzer_jieba_index": {
                            #    "type": "jieba",
                            #    #"tokenizer": "my_jieba_index",
                            #    "filter": ["my_pinyin_f"]
                            #},
                            #"mycn_analyzer_jieba_search": {
                            #    "type": "jieba",
                            #    #"tokenizer": "my_jieba_search",
                            #    "filter": ["my_pinyin_f"]
                            #},
                            #"mycn_analyzer_mmseg": {
                            #    "type": "custom",
                            #    "tokenizer": "mmseg_maxword",
                            #    "filter": ["my_pinyin_f"]
                            #},
                        },
                        "tokenizer" : {
                            "my_pinyin" : {
                                "type" : "pinyin",
                                "first_letter" : "prefix",
                                "padding_char" : ""
                            },
                            #"my_jieba_index": {
                            #    "type": "jieba",
                            #    "seg_mode": "index",
                            #    "stop": "true"
                            #},
                            #"my_jieba_search": {
                            #    "type": "jieba",
                            #    "seg_mode": "search",
                            #    "stop": "true"
                            #},
                            #"mmseg_maxword": {
                            #    "type": "mmseg",
                            #    "seg_type": "max_word" # complex, simple
                            #}
                        },
                        "filter": {
                            "ngram_1_to_2": {
                                "type": "nGram",
                                "min_gram": 1,
                                "max_gram": 2
                            },
                            #"my_jieba_other": {
                            #    "type": "jieba",
                            #    "seg_mode": "other",
                            #    "stop": "true"
                            #},
                            "my_pinyin_f": {
                                "type": "pinyin",
                                "first_letter": "none",
                                "padding_char": ""
                            },
                            "my_pinyin_first_only": {
                                "type": "pinyin",
                                "first_letter": "only",
                                "padding_char": ""
                            },
                        }
                    }
                 }
                 },
                 "mappings": mappings
               }
               )


#def get_item_name_suggest(es, item):
#    item_name = item["item_name"]
#    res = es.indices.analyze(index="item-index", text=item_name, analyzer="mycn_analyzer_wo_ngram")
#    converted_item_name = "".join([token["token"] for token in res["tokens"]])
#    #print "CIN:", item_name, converted_item_name
#    input = []
#    for start_idx in range(len(converted_item_name)):
#        term = converted_item_name[start_idx:]
#        if len(term) > 1 and term[0] != " ":
#            input.append(term)
#    #print {"input": input, "output": item["item_name"]}
#    #import sys; sys.exit(1)
#    return {"input": input, "output": item["item_name"]}


def get_item_name_suggest(es, item):
    item_name = item["item_name"]
    res = es.indices.analyze(index="item-index", text=item_name, analyzer="mycn_analyzer_pinyin_fully")
    converted_item_name = "".join([token["token"] for token in res["tokens"]])
    res = es.indices.analyze(index="item-index", text=item_name, analyzer="mycn_analyzer_pinyin_first_only")
    converted_first_only = "".join([token["token"] for token in res["tokens"]])
    return {"input": [converted_item_name, converted_first_only], "output": item["item_name"]}


import jieba
def preprocess_query_str(query_str):
    result = []
    keywords = [keyword for keyword in query_str.split(" ") if keyword.strip() != ""]
    for keyword in keywords:
        cutted_keyword = " ".join(["%s" % term for term in jieba.cut_for_search(keyword)])
        result.append(cutted_keyword)
    return result

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
        item["item_name_suggest"] = get_item_name_suggest(es, item)
        del item["_id"]
        item["categories"] = " ".join(item["categories"])
        item["item_name"] = " ".join(preprocess_query_str(item["item_name"]))
        #print item["item_name"]
        #sys.exit(1)
        res = es.index(index='item-index', doc_type='item', id=item["item_id"], body=item)
        #print item
    es.indices.refresh(index='item-index')
    print "Finish Loading"
