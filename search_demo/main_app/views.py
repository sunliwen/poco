import json
from django.shortcuts import render, render_to_response
from django.template import RequestContext
from django.http import HttpResponse
from elasticutils import S, F
from django.core.paginator import Paginator


def v_index(request):
    query_str = request.GET.get("q", None)
    page_num = request.GET.get("p", "1")
    try:
        page_num = int(page_num)
    except TypeError:
        page_num = 1
    if query_str:
        #query_str = unicode(query_str
        s = S().indexes("item-index").doctypes("item")
        query = {"multi_match": {"query": query_str, "operator": "or",
                             "fields": ["item_name"]}}
        s = s.query_raw(query)
        s = s.filter(available=True)
        page = Paginator(s, 12).page(page_num)
    else:
        page = None
    # TODO: url encode in the template
    return render_to_response("index.html", {"page": page, "query_str": query_str}, RequestContext(request))


terms = ["This is a good",
         "ABC",
         "ABDEF",
         "ABDKK"]
def v_ajax_auto_complete_term(request):
    term_prefix = request.GET.get("term", None)
    if term_prefix.strip() == "":
        term_prefix = None
    return HttpResponse(json.dumps([term for term in terms if term.startswith(term_prefix)]))
