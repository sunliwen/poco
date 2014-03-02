from django.shortcuts import render, render_to_response
from django.template import RequestContext
from elasticutils import S, F
from django.core.paginator import Paginator


def v_index(request):
    print "0.1"
    query_str = request.GET.get("q", None)
    page_num = request.GET.get("p", "1")
    try:
        page_num = int(page_num)
    except TypeError:
        page_num = 1
    print "0.21"
    if query_str:
        #query_str = unicode(query_str
        print 1
        s = S().indexes("item-index").doctypes("item")
        query = {"multi_match": {"query": query_str, "operator": "or", 
                             "fields": ["item_name"]}}
        s = s.query_raw(query)
        page = Paginator(s, 12).page(page_num)
        print 2
    else:
        page = None
    # TODO: url encode in the template
    return render_to_response("index.html", {"page": page, "query_str": query_str}, RequestContext(request))
