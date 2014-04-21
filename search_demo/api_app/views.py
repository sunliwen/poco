#encoding=utf8
#from django.shortcuts import render
from rest_framework import renderers
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.reverse import reverse
from django.http import Http404
from rest_framework.views import APIView
from rest_framework import status
import es_search_functions
from recommender.mongo_client import getMongoClient


mongo_client = getMongoClient()


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


from elasticutils import S, F
from serializers import PaginatedItemSerializer, ItemSerializer
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage


def is_float(value):
    try:
        float(value)
        return True
    except ValueError:
        return False
is_float.expected_type = "numeric"

def is_string(value):
    return isinstance(value, basestring)
is_string.expected_type = "string"

def is_boolean(value):
    return isinstance(value, bool)
is_boolean.expected_type = "boolean"

def validate_list_value_types(list, expected_type):
    for item in list:
        if expected_type == "float":
            return is_float(item)
        elif expected_type == "string":
            return isinstance(item, basestring)
        else:
            return True


def get_last_cat_id(cat_id):
    cat_ids = cat_id.split("__")
    if len(cat_ids) > 0:
        return cat_ids[-1]
    else:
        return ""


def get_item_name(obj):
    _highlight = getattr(obj, "_highlight", None)
    if _highlight:
        item_names = _highlight.get("item_name_standard_analyzed", None)
        if item_names:
            return item_names[0]
    return obj.item_name_standard_analyzed


# FIXME: ItemSerializer does not work correctly currently
def serialize_items(item_list):
    result = []
    for item in item_list:
        item_dict = {}
        for field in ("item_id", "price", "market_price", "image_link",
                      "item_link", "available", "item_group",
                      "brand", "item_level", "item_spec", "item_comment_num"):
            val = getattr(item, field, None)
            if val is not None:
                item_dict[field] = val
        item_dict["categories"] = [cat for cat in getattr(item, "categories", []) if "__" not in cat]
        item_dict["item_name"] = get_item_name(item)
        result.append(item_dict)
    return result


class BaseAPIView(APIView):
    def getSiteID(self, api_key):
        api_key2site_id = mongo_client.getApiKey2SiteID()
        return api_key2site_id.get(api_key, None)


# TODO: http://www.django-rest-framework.org/topics/documenting-your-api
class ProductsSearch(BaseAPIView):
    def _search(self, site_id, q, sort_fields, filters, highlight):
        # TODO: this is just a simplified version of search
        s = S().indexes(es_search_functions.getESItemIndexName(site_id)).doctypes("item")
        if q.strip():
            query = es_search_functions.construct_query(q)
            s = s.query_raw(query)
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
        sub_categories_facets = es_search_functions._getSubCategoriesFacets(cat_id, s)
        if sub_categories_facets:
            s = s.facet_raw(sub_categories=sub_categories_facets,
                            brand={'terms': {'field': 'brand', 'size': 20}},
                            origin_place={'terms': {'field': 'origin_place', 
                                                    'size': 20}})
            facet_sub_categories_list = [{"id": get_last_cat_id(facet["term"]),
                                    "count": facet["count"]}
                                    for facet in s.facet_counts().get("sub_categories", [])]
            for facet_sub_cat in facet_sub_categories_list:
                facet_sub_cat["label"] = mongo_client.getPropertyName(site_id, "category", facet_sub_cat["id"])
            facet_brand_list = [{"id": facet["term"],
                                 "label": mongo_client.getPropertyName(site_id, "brand", facet["term"]),
                                 "count": facet["count"]}
                                 for facet in s.facet_counts().get("brand", [])]
            facet_origin_place_list = [{"id": facet["term"],
                                 "label": "",
                                 "count": facet["count"]}
                                 for facet in s.facet_counts().get("origin_place", [])]
        else:
            facet_sub_categories_list = []
            facet_brand_list = []

        return s, {"categories": facet_sub_categories_list, "brand": facet_brand_list, 
                   "origin_place": facet_origin_place_list}

    def _validate(self, request):
        # TODO ignore fields and warn
        # TODO category only one; facets.
        errors = []
        if not isinstance(request.DATA.get("q", None), basestring):
            errors.append({"code": "PARAM_REQUIRED", "field_name": "q",
                           "message": u"'q' is required and must be of string type."})

        page = request.DATA.get("page", None)
        if page is not None and not str(page).isdigit():
            errors.append({"code": "INVALID_PARAM",
                           "param_name": "page",
                           "message": u"'page' must be a number."})


        sort_fields = request.DATA.get("sort_fields", [])
        if isinstance(sort_fields, list):
            invalid_sort_fields = [sort_field for sort_field in sort_fields
                                   if (not isinstance(sort_field, basestring))
                                       or (not sort_field.strip("-") in self.VALID_SORT_FIELDS)]
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
                filter_validator = self.FILTER_FIELD_TYPE_VALIDATORS.get(filter_key, None)
                if filter_validator is None:
                    invalid_name_filters.append(filter_key)
                else:
                    filter_details = filters[filter_key]
                    if isinstance(filter_details, list):
                        if filter_key == "categories":
                            if len(filter_details) > 1:
                                errors.append({"code": "INVALID_PARAM",
                                    "param_name": "filters",
                                    "message": u"'categories' can not contain more than 1 value."})
                        for filter_details_item in filter_details:
                            if not filter_validator(filter_details_item):
                                errors.append({"code": "INVALID_PARAM",
                                            "param_name": "filters",
                                            "message": u"'%s' should contain %s values." \
                                                       % (filter_key, filter_validator.expected_type)})
                                break
                    elif isinstance(filter_details, dict):
                        if not (filter_details.has_key("type")
                            and filter_details["type"] == "range"
                            and filter_details.has_key("from")
                            and filter_details.has_key("to")):
                            invalid_details_filters.append(filter_key)
                        elif filter_key in ("price", "market_price") and \
                                not (is_float(filter_details["from"]) and is_float(filter_details["to"])):
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
        elif self.getSiteID(api_key) is None:
            errors.append({"code": "INVALID_PARAM", "param_name": "api_key",
                           "message": "no such api_key"})

        return errors


    VALID_SORT_FIELDS = ("price", "market_price", "item_level", "item_comment_num", "origin_place")
    #VALID_FILTER_FIELDS = ("price", "market_price", "categories", "item_id", "available")
    FILTER_FIELD_TYPE_VALIDATORS = {
        "price": is_float,
        "market_price": is_float,
        "categories": is_string,
        "item_id": is_string,
        "available": is_boolean,
        "item_level": is_float,
        "item_comment_num": is_float,
        "origin_place": is_float
    }
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
        api_key = request.DATA["api_key"]

        # Apply default filters
        for filter_key , filter_content in self.DEFAULT_FILTERS.items():
            if not filters.has_key(filter_key):
                filters[filter_key] = filter_content

        site_id = self.getSiteID(api_key)
        result_set, facets_result = self._search(site_id, q, sort_fields, filters, highlight)
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

        #serializer = ItemSerializer(items_list, many=True)
        result = {"records": serialize_items(items_list),
                  "info": {
                     "current_page": page,
                     "num_pages": paginator.num_pages,
                     "per_page": per_page,
                     "total_result_count": paginator.count,
                     "facets": facets_result
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


class QuerySuggest(BaseAPIView):
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
        elif self.getSiteID(api_key) is None:
            errors.append({"code": "INVALID_PARAM", "param_name": "api_key",
                           "message": "no such api_key"})

        return errors


    def post(self, request, format=None):
        return self.get(request, format=None)

    def get(self, request, format=None):
        errors = self._validate(request)
        if errors:
            return Response({"suggestions": [], "errors": errors})

        q = request.DATA.get("q", "")
        api_key = request.DATA.get("api_key", "")
        site_id = self.getSiteID(api_key)

        suggester = es_search_functions.Suggester(site_id)
        suggested_texts = suggester.getQuerySuggestions(q)

        return Response({"suggestions": suggested_texts, "errors": {}})
