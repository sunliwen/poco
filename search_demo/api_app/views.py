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

        if highlight:
            s = s.highlight("item_name_standard_analyzed")

        # TODO: check performance issue
        categories = filters.get("categories", [])
        if categories:
            cat_id = categories[0]
        else:
            cat_id = None
        sub_categories_facets = main_app_views._getSubCategoriesFacets(cat_id, s)
        if sub_categories_facets:
            s = s.facet_raw(sub_categories=sub_categories_facets)
            sub_categories_list = [{"id": facet["term"],
                                    "label": main_app_views.CATEGORY_MAP_BY_ID[facet["term"]]["name"], 
                                    "count": facet["count"]} 
                                    for facet in s.facet_counts().get("sub_categories", [])]
        else:
            sub_categories_list = []

        return s, sub_categories_list

    def _validate(self, request):
        # TODO ignore fields and warn
        # TODO category only one; facets.
        errors = []
        if not isinstance(request.DATA.get("q", None), basestring):
            errors.append({"code": "PARAM_REQUIRED", "field_name": "q", 
                           "message": u"'q' is required and must be of string type."})

        page = request.DATA.get("page", None)
        if page is not None and not page.isdigit():
            errors.append({"code": "INVALID_PARAM", 
                           "param_name": "page",
                           "message": u"'page' must be of int type."})


        sort_fields = request.DATA.get("sort_fields", [])
        if isinstance(sort_fields, list):
            invalid_sort_fields = [sort_field for sort_field in sort_fields
                                   if not sort_field.strip("-") in self.VALID_SORT_FIELDS]
            if invalid_sort_fields:
                errors.append({"code": "INVALID_PARAM", 
                               "param_name": "sort_fields",
                               "message": u"'sort_fields' contains invalid field names: %s" % (",".join(invalid_sort_fields))})
        else:
            errors.append({"code": "INVALID_PARAM",
                           "param_name": "sort_fields",
                           "message": u"'sort_fields' must be a list"})

        if not isinstance(request.DATA.get("highlight", False), bool):
            errors.append({"code": "INVALID_PARAM",
                           "param_name": "highlight",
                           "message": u"'highlight' must be a boolean value."})

        filters = request.DATA.get("filters", {})
        if isinstance(filters, dict):
            invalid_name_filters = []
            invalid_details_filters = []
            for filter_key in filters.keys():
                print filter_key, ":", not filter_key in self.VALID_FILTER_FIELDS
                if not filter_key in self.VALID_FILTER_FIELDS:
                    invalid_name_filters.append(filter_key)
                else:
                    filter_details = filters[filter_key]
                    if isinstance(filter_details, list):
                        if filter_key == "categories":
                            if len(filter_details) > 1:
                                errors.append({"code": "INVALID_PARAM", 
                                    "param_name": "filters",
                                    "message": u"'categories' can not contain more than 1 value."})
                            else:
                                for cat_id in filter_details:
                                    if not isinstance(cat_id, basestring):
                                        errors.append({"code": "INVALID_PARAM", 
                                            "param_name": "filters",
                                            "message": u"'categories' should contain string values."})

                    elif isinstance(filter_details, dict):
                        if not (filter_details.has_key("type") 
                            and filter_details["type"] == "range"
                            and filter_details.has_key("from")
                            and filter_details.has_key("to")):
                            invalid_details_filters.append(filter_key)
                    else:
                        invalid_details_filters.append(filter_key)
            if invalid_name_filters:
                errors.append({"code": "INVALID_PARAM", 
                               "param_name": "filters",
                               "message": u"'filters' contains invalid field names: %s" % (",".join(invalid_name_filters))})
            if invalid_details_filters:
                errors.append({"code": "INVALID_PARAM", 
                               "param_name": "filters",
                               "message": u"'filters' contains fields with invalid content: %s" % (",".join(invalid_details_filters))})
        else:
            errors.append({"code": "INVALID_PARAM",
                           "param_name": "filters",
                           "message": u"'filters' must be a dict/hashtable"})

        api_key = request.DATA.get("api_key", None)
        if api_key is None:
            errors.append({"code": "PARAM_REQUIRED", "field_name": "api_key", 
                           "message": "'api_key' is required."})
        elif not isinstance(api_key, basestring):
            errors.append({"code": "INVALID_PARAM", 
                           "param_name": "api_key",
                           "message": u"'api_key' must be a string."})

        return errors

    VALID_SORT_FIELDS = ("price", "market_price")
    VALID_FILTER_FIELDS = ("price", "market_price", "categories", "item_id", "available")
    DEFAULT_FILTERS = {
        "available": [True]
    }
    PER_PAGE = 20

    def post(self, request, format=None):
	return self.get(request, format)

    # refs: http://www.django-rest-framework.org/api-guide/pagination
    def get(self, request, format=None):
        errors = self._validate(request)
        if errors:
            return Response({"records": {}, "info": {}, "errors": errors})
        # TODO: handle the api_key
        q = request.DATA.get("q", "")
	per_page = request.DATA.get("per_page", self.PER_PAGE)
        sort_fields = request.DATA.get("sort_fields", [])
        page = request.DATA.get("page", 1)
        filters = request.DATA.get("filters", {})
        highlight = request.DATA.get("highlight", False)

        # Apply default filters
        for filter_key , filter_content in self.DEFAULT_FILTERS.items():
            if not filters.has_key(filter_key):
                filters[filter_key] = filter_content

        result_set, sub_categories_list = self._search(q, sort_fields, filters, highlight)
        paginator = Paginator(result_set, per_page)

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
                     "per_page": per_page,
                     "total_result_count": paginator.count,
                     "facets": {"categories": sub_categories_list}
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
    def _validate(self, request):
        errors = []
        if not isinstance(request.DATA.get("q", None), basestring):
            errors.append({"code": "PARAM_REQUIRED", "field_name": "q", 
                           "message": "'q' is required and must be a string."})

        api_key = request.DATA.get("api_key", None)
        if api_key is None:
            errors.append({"code": "PARAM_REQUIRED", "field_name": "api_key", 
                           "message": "'api_key' is required."})
        elif not isinstance(api_key, basestring):
            errors.append({"code": "INVALID_PARAM", 
                           "param_name": "api_key",
                           "message": "'api_key' must be a string."})

        return errors


    def post(self, request, format=None):
	return self.get(request, format=None)

    def get(self, request, format=None):
        errors = self._validate(request)
        if errors:
            return Response({"suggestions": [], "errors": errors})

        q = request.DATA.get("q", "")

        es = Elasticsearch()
        suggested_texts = main_app_views._getQuerySuggestions(es, q)
        
        return Response({"suggestions": suggested_texts, "errors": {}})
