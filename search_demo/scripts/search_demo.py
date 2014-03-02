# encoding=utf8
import pprint
from elasticsearch import Elasticsearch


# TODO:
#   Pagination (DONE)
#   typeahead
#   分词

def _run():
    es = Elasticsearch()

    query_str = u"碧呵"
    query = {"multi_match": {"query": query_str, "operator": "or", 
                             "fields": ["item_name"]}}
    res = es.search(index="item-index", 
                body={#"explain": False,
                      #"from": 0, "size": 2,
                      "query": query
                      })
    hits = res["hits"]
    if hits["total"] != 0:
        print "%d Items Found" % hits["total"]
        for hit in hits["hits"]:
            _source = hit["_source"]
            print hit["_score"], _source["item_id"], _source["item_name"], "%(market_price)s/%(price)s" % _source
    else:
        print "No search result."


from elasticutils import S, F
from django.core.paginator import Paginator
def run():
    s = S().indexes("item-index").doctypes("item")
    query_str = u"碧呵 婴儿"
    query = {"multi_match": {"query": query_str, "operator": "or", 
                             "fields": ["item_name"]}}
    s = s.query_raw(query)
    #for result in s:
    #    print result["item_id"], result["item_name"]
    p = Paginator(s, 5)
    print "Total", p.count
    page_range = p.page_range[:20]
    print "Pages:", page_range
    print "======================"
    for page_num in page_range:
        print "Page:", page_num
        page = p.page(page_num)
        for item in page.object_list:
            print item._score, item["item_id"], item["item_name"]
        print "------------------"
