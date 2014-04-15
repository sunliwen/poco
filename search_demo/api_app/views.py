#encoding=utf8
#from django.shortcuts import render
from rest_framework import renderers
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.reverse import reverse
from django.http import Http404
from rest_framework.views import APIView
from rest_framework import status
from elasticsearch import Elasticsearch


# TODO: highlight
# PAGINATE_BY
# refs: http://www.django-rest-framework.org/tutorial/5-relationships-and-hyperlinked-apis
@api_view(('GET',))
def api_root(request, format=None):
    return Response({
        'search': reverse('products-search', request=request, format=format),
        'suggest': reverse('query-suggest', request=request, format=format),
        #'categories': reverse('categories-list', request=request, format=format)
    })


from main_app import views as main_app_views
from elasticutils import S, F
from serializers import PaginatedItemSerializer, ItemSerializer
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage

"""
{
        "api_key": "<分配给用户站点的api key>",
        "q": "奶粉",
        "sort_fields": ["price"],
        "page": 2,
        "filters": {
            "categories": ["200400"],
            "price": {
                "type": "range",
                "from": 3.00,
                "to": 15.00
            }
        },
        "config_key": "<本次搜索所用后台配置的key>"
     }

"""


# TODO: http://www.django-rest-framework.org/topics/documenting-your-api
class ProductsSearch(APIView):
    def _search(self, q, sort_fields, filters, highlight):
        # TODO: this is just a simplified version of search
        s = S().indexes("item-index").doctypes("item")
        query = main_app_views.construct_query(q)
        s = s.query_raw(query)
        #s = s.filter(available=True) # TODO: this should be configurable in dashboard
        s = s.order_by(*sort_fields)

        for filter_field, filter_details in filters.items():
            if isinstance(filter_details, list):
                if len(filter_details) == 1:
                    s = s.filter(**{filter_field: filter_details[0]})
                else:
                    s = s.filter(**{"%s__in" % filter_field: filter_details})
            elif isinstance(filter_details, dict):
                if filter_details.get("type") == "range":
                    from_ = filter_details["from"]
                    to_   = filter_details["to"]
                    s = s.filter(**{"%s__range" % filter_field: (from_, to_)})

        # TODO: config this
        if highlight:
            s = s.highlight("item_name_standard_analyzed")

        return s

    def _validate(self, request):
        # TODO ignore fields and warn
        # TODO category only one; facets.
        errors = []
        #if not isinstance(request.DATA.get("q", None), basestring):
        #    errors.append(

    PER_PAGE = 20
    # refs: http://www.django-rest-framework.org/api-guide/pagination
    def get(self, request, format=None):
        # TODO: validate the data
        # TODO: handle the api_key, config_key
        q = request.DATA.get("q", "")
        sort_fields = request.DATA.get("sort_fields", [])
        page = request.DATA.get("page", 1)
        filters = request.DATA.get("filters", {})
        highlight = request.DATA.get("highlight", False)

        result_set = self._search(q, sort_fields, filters, highlight)
        paginator = Paginator(result_set, self.PER_PAGE)

        try:
            items_page = paginator.page(page)
        except PageNotAnInteger:
            items_page = paginator.page(1)
            page = 1
        except EmptyPage:
            items_page = paginator.page(paginator.num_pages)
            page = paginator.num_pages

        items_list = [item for item in items_page]

        #serializer_context = {'request': request}
        #serializer = PaginatedItemSerializer(instance=items, many=True, 
        #                            context=serializer_context)
        serializer = ItemSerializer(items_list, many=True)
        # TODO: facets
        result = {"records": serializer.data,
                  "info": {
                     "current_page": page,
                     "num_pages": paginator.num_pages,
                     "per_page": self.PER_PAGE,
                     "total_result_count": paginator.count,
                     "facets": {}
                  },
                  "errors": {}
                }

        # TODO: facets and other info
        return Response(result)

    #def post(self, request, format=None):
    #    serializer = SnippetSerializer(data=request.DATA)
    #    if serializer.is_valid():
    #        serializer.save()
    #        return Response(serializer.data, status=status.HTTP_201_CREATED)
    #    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class QuerySuggest(APIView):
    def get(self, request, format=None):
        q = request.DATA.get("q", "")

        es = Elasticsearch()
        suggested_texts = main_app_views._getQuerySuggestions(es, q)
        
        return Response(suggested_texts)
