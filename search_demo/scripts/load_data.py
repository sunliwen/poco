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
                                                "analyzer": "pinyin_ngram_analyzer",
                                                "boost": 10
                                            },
                                            "primitive": {
                                                "type": "string",
                                                "store": "yes",
                                                #"analyzer": "keyword"
                                            }
                                          }
                                          },
                            "price": {"type": "string"},
                            "image_link": {"type": "string"},
                            "item_link": {"type": "string"},
                            "categories": {"type": "string", "index_name": "category"},
                            #"item_name_suggest": {
                            #    "type": "completion",
                            #    #"index_analyzer": "simple",
                            #    #"search_analyzer": "simple",
                            #    "term_vector": "with_positions_offsets",
                            #    "index_analyzer": "pinyin_ngram_analyzer",
                            #    "search_analyzer": "pinyin_ngram_analyzer",
                            #    "payloads": False
                            #}
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
                            "pinyin_ngram_analyzer" : {
                                "tokenizer" : ["my_pinyin"],
                                "filter" : ["standard","nGram"] # TODO: check why.
                            }
                        },
                        "tokenizer" : {
                            "my_pinyin" : {
                                "type" : "pinyin",
                                "first_letter" : "prefix",
                                "padding_char" : ""
                            }
                        }
                    }
                 }
                 },
                 "mappings": mappings
               }
               )




#import jieba
#def get_item_name_suggest(item):
#    return {"input": [term for term in jieba.cut_for_search(item["item_name"]) if len(term) > 1],
#            "output": item["item_name"]}
def get_item_name_suggest(item):
    input = []
    for start_idx in range(len(item["item_name"])):
        term = item["item_name"][start_idx:]
        if len(term) > 1 and term[0] != " ":
            input.append(term)
    return {"input": input, "output": item["item_name"]}


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
