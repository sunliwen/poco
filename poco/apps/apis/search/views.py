#encoding=utf8
#from django.shortcuts import render
import copy
import logging
import hashlib
import json
from rest_framework import renderers
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.reverse import reverse
from django.http import Http404, HttpResponse
from django.core.cache import get_cache
from django.conf import settings
from rest_framework.views import APIView
from rest_framework import status
import es_search_functions
from es_search_functions import serialize_items
from common.mongo_client import getMongoClient
from common.cached_result import cached_result
from apps.apis.recommender.property_cache import PropertyCache


mongo_client = getMongoClient()
property_cache = PropertyCache(mongo_client)



# # TODO: highlight
# # PAGINATE_BY
# # refs: http://www.django-rest-framework.org/tutorial/5-relationships-and-hyperlinked-apis
# @api_view(('GET',))
# def api_root(request, format=None):
#     return Response(reverses())


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


class BaseAPIView(APIView):
    def getSiteID(self, api_key):
        api_key2site_id = mongo_client.getApiKey2SiteID()
        return api_key2site_id.get(api_key, None)


# TODO: http://www.django-rest-framework.org/topics/documenting-your-api
class ProductsSearch(BaseAPIView):
    def _search(self, site_id, q, sort_fields, filters, highlight, facets_selector, search_config):
        s = S().indexes(es_search_functions.getESItemIndexName(site_id)).doctypes("item")

        if isinstance(q, basestring) and q.strip() != "":
            if search_config["type"] == "SEARCH_TEXT":
                query = es_search_functions.construct_query(q)

            elif search_config["type"] == "SEARCH_TERMS":
                term_field = search_config["term_field"]
                terms = q.split(" ")
                should = [{"term": {term_field: term}} for term in terms]

                if search_config["match_mode"] == "MATCH_MORE_BETTER":
                    minimum_should_match = 1
                elif search_config["match_mode"] == "MATCH_ALL":
                    minimum_should_match = len(terms)
                query = {
                    "bool": {
                        "should": should,
                        "minimum_should_match" : minimum_should_match
                    }
                }
            s = s.query_raw(query)

        order_by_stock = [{"_script": {
                                "script": "doc['stock'].value == 0?1:0",
                                "type": "number",
                                "order": "asc"
                               }}]

        if sort_fields == []:
            sort_fields = ["_score"]

        sort_fields = order_by_stock + sort_fields

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

        facets_dsl = {}
        if facets_selector.has_key("categories"):
            categories_facet_mode = facets_selector["categories"]["mode"]
            if categories_facet_mode == "DIRECT_CHILDREN":
                facets_dsl["categories"] = es_search_functions._getSubCategoriesFacets(cat_id, s)
            elif categories_facet_mode == "SUB_TREE":
                facets_dsl["categories"] = es_search_functions.addFilterToFacets(s,
                                            {'terms': {'regex': r'[^_]+', 'field': 'categories', 'size': 5000}})
        if facets_selector.has_key("brand"):
            facets_dsl["brand"] = es_search_functions.addFilterToFacets(s, {'terms': {'field': 'brand', 'size': 5000}})
        if facets_selector.has_key("origin_place"):
            facets_dsl["origin_place"] = es_search_functions.addFilterToFacets(s,
                                                    {'terms': {'field': 'origin_place',
                                                    'size': 5000}})
        facets_result = {}
        if len(facets_dsl.keys()) > 0:
            s = s.facet_raw(**facets_dsl)

            if facets_selector.has_key("categories"):
                categories_facet_mode = facets_selector["categories"]["mode"]
                facets_list = s.facet_counts().get("categories", [])
                if categories_facet_mode == "DIRECT_CHILDREN":
                    for facets in facets_list:
                        facets["term"] == facets["term"]
                facet_categories_list = [{"id": get_last_cat_id(facet["term"]),
                                          "count": facet["count"]}
                                          for facet in facets_list]
                for facet_sub_cat in facet_categories_list:
                    facet_sub_cat["label"] = property_cache.get_name(site_id, "category", facet_sub_cat["id"])
                facets_result["categories"] = facet_categories_list

            if facets_selector.has_key("brand"):
                facets_result["brand"] = [{"id": facet["term"],
                                     "label": property_cache.get_name(site_id, "brand", facet["term"]),
                                     "count": facet["count"]}
                                     for facet in s.facet_counts().get("brand", [])]

            if facets_selector.has_key("origin_place"):
                facets_result["origin_place"] = [{"id": facet["term"],
                                     "label": "",
                                     "count": facet["count"]}
                                     for facet in s.facet_counts().get("origin_place", [])]
        return s, facets_result

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

        facets = request.DATA.get("facets", {})
        if isinstance(facets, dict):
            for facets_key, facets_detail in facets.items():
                if facets_key not in self.SUPPORTED_FACETS:
                    errors.append({"code": "INVALID_PARAM",
                           "param_name": "facets",
                           "message": u"'facets' are only supported for %s"  % (",".join(self.SUPPORTED_FACETS))})
                else:
                    if not isinstance(facets_detail, dict):
                        errors.append({"code": "INVALID_PARAM",
                           "param_name": "facets",
                            "message": "details in facet '%s' is invalid." % facets_key
                            })
            #category_facets_mode = facets.get("categories", {}).get("mode", None)
            if facets.has_key("categories"):
                category_facets_mode = facets["categories"].setdefault("mode", self.DEFAULT_FACET_CATEGORY_MODE)
                if category_facets_mode not in ("DIRECT_CHILDREN", "SUB_TREE"):
                    errors.append({"code": "INVALID_PARAM",
                               "param_name": "facets",
                                "message": "mode of facet 'categories' is invalid."
                                })
        else:
            errors.append({"code": "INVALID_PARAM",
                           "param_name": "facets",
                           "message": u"'facets' must be a dict/hashtable"})

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
                            facets_categories = facets.get("categories", None)
                            if facets_categories is not None \
                                and facets_categories.get("mode", "DIRECT_CHILDREN") == "DIRECT_CHILDREN":
                                if len(filter_details) > 1:
                                    errors.append({"code": "INVALID_PARAM",
                                        "param_name": "filters",
                                        "message": u"'categories' can not contain more than 1 value, when facets of categories are in 'DIRECT_CHILDREN' model."})
                        elif filter_key == 'sku_attr.usingsex':
                            filter_details.append(u'通用')
                        elif filter_key == 'sku_attr.season':
                            filter_details.append(u'四季')
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

    DEFAULT_FACET_CATEGORY_MODE = "SUB_TREE"
    VALID_SORT_FIELDS = ("price", "market_price", "item_level", "item_comment_num", "origin_place", 'sell_num', 'discount', 'sale_price', '_score')
    FILTER_FIELD_TYPE_VALIDATORS = {
        "price": is_float,
        "market_price": is_float,
        "categories": is_string,
        "item_id": is_string,
        "available": is_boolean,
        "item_level": is_float,
        "item_comment_num": is_float,
        "origin_place": is_float,
        "brand": is_string,
        "prescription_type": is_string,
        'discount': is_float,
        'sale_price': is_float,
        'sku_attr.usingsex': is_string,
        'sku_attr.startmonth': is_float,
        'sku_attr.endmonth': is_float,
        'sku_attr.buildyear': is_float,
        'sku_attr.stylecode': is_string,
        'sku_attr.season': is_string,
        'sku_attr.color': is_string,
        'sku_attr.material': is_string,
        'sku_attr.size': is_string,
        'sku_attr.productid': is_string,
    }

    DEFAULT_FACETS = {
        "brand": {},
        "origin_place": {},
        "categories": {"mode": DEFAULT_FACET_CATEGORY_MODE}
    }

    SUPPORTED_FACETS = ["brand", "categories", "origin_place"]

    DEFAULT_FILTERS = {
        "available": [True]
    }
    PER_PAGE = 20

    SEARCH_TERM_FIELDS = ["tags"]

    def post(self, request, format=None):
        return self.get(request, format)

    def _cleanupSearchConfig(self, search_config):
        if search_config is None:
            search_config = {"type": "SEARCH_TEXT"}
        else:
            if isinstance(search_config, dict):
                type = search_config.get("type", None)
                if type not in ("SEARCH_TEXT", "SEARCH_TERMS"):
                    return False, [{"code": "INVALID_PARAM", "param_name": "search_config",
                                "message": "invalid search_config 'type'"}]
                if type == "SEARCH_TERMS":
                    match_mode = search_config.get("match_mode", None)
                    if match_mode in ("MATCH_ALL", "MATCH_MORE_BETTER"):
                        term_field = search_config.get("term_field", None)
                        if term_field not in (self.SEARCH_TERM_FIELDS):
                            return False, [{"code": "INVALIDPARAM", "param_name": "search_config",
                                            "message": "search_config 'term_field' should be one of %s" \
                                                        % ",".join(self.SEARCH_TERM_FIELDS)}]
                    else:
                        return False, [{"code": "INVALID_PARAM", "param_name": "search_config",
                                        "message": "invalid search_config 'match_mode'"}]
            else:
                return False, [{"code": "INVALID_PARAM", "param_name": "search_config",
                                "message": "invalid 'search_config'"}]
        return True, search_config

    def _getSearchCacheKey(self, site_id, search_data):
        return "search-result-cache-%s-%s" % (site_id, hashlib.md5(repr(dict(search_data))).hexdigest())

    # refs: http://www.django-rest-framework.org/api-guide/pagination
    def get(self, request, format=None):
        errors = self._validate(request)
        if errors:
            logging.debug("Search Params:%s " % request.DATA)
            return Response({"records": [], "info": {}, "errors": errors})
        # TODO: handle the api_key
        q = request.DATA.get("q", "")
        per_page = request.DATA.get("per_page", self.PER_PAGE)
        sort_fields = request.DATA.get("sort_fields", [])
        page = request.DATA.get("page", 1)
        filters = request.DATA.get("filters", {})
        highlight = request.DATA.get("highlight", False)
        facets_selector = request.DATA.get("facets", None)
        search_config = request.DATA.get("search_config", None)
        #result_mode = request.DATA.get("result_mode", "WITH_RECORDS")
        api_key = request.DATA["api_key"]

        # Apply default filters
        for filter_key , filter_content in self.DEFAULT_FILTERS.items():
            if not filters.has_key(filter_key):
                filters[filter_key] = filter_content

        # Apply default facets
        if facets_selector is None:
            facets_selector = copy.deepcopy(self.DEFAULT_FACETS)

        #if result_mode not in ("WITHOUT_RECORDS", "WITH_RECORDS"):
        #    return Response({"records": [], "info": {},
        #                     "errors": [{"code": "INVALID_PARAM",
        #                                "param_name": "result_mode",
        #                                "message": "invalid result_mode"}]})

        is_valid, result = self._cleanupSearchConfig(search_config)
        if not is_valid:
            return Response({"records": [], "info": {}, "errors": result})
        else:
            search_config = result

        try:
            per_page = int(per_page)
        except ValueError:
            return Response({"records": [], "info": {},
                             "errors": [{"code": "INVALID_PARAM",
                                        "param_name": "per_page",
                                        "message": "per_page must be a digit value."}]})

        if per_page <= 0:
            return Response({"records": [], "info": {},
                             "errors": [{"code": "INVALID_PARAM",
                                        "param_name": "per_page",
                                        "message": "per_page must be greater than 0."}]})

        site_id = self.getSiteID(api_key)

        search_cache_key = self._getSearchCacheKey(site_id, request.DATA)
        django_cache = get_cache("default")
        result_in_cache = django_cache.get(search_cache_key)
        if (result_in_cache is not None):
            #result = json.loads(result_in_cache)
            return HttpResponse(result_in_cache)
        else:
            try:
                result_set, facets_result = self._search(site_id, q, sort_fields, filters, highlight, facets_selector, search_config)
            except:
                logging.critical("Unknown exception raised!", exc_info=True)
                return Response({"records": [], "info": {},
                                 "errors": [{"code": "UNKNOWN_ERROR",
                                            "message": "Unknown error, please try later."}]})

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
                      "errors": []
                    }
            django_cache.set(search_cache_key, json.dumps(result), settings.CACHE_EXPIRY_SEARCH_RESULTS)


        return Response(result)


class Keywords(BaseAPIView):
    def _validate(self, args):
        errors = []
        category_id = args.get("category_id", None)
        if category_id is not None and not isinstance(category_id, basestring):
            errors.append({"code": "INVALID_PARAM", "field_name": "category_id",
                           "message": "category_id must be a string."})

        if args.get("type", None) != "hot":
            errors.append({"code": "INVALID_PARAM", "field_name": "type",
                           "message": "Only type='hot' are supported. "})

        try:
            int(args.get("amount", "5"))
        except ValueError:
            errors.append({"code": "INVALID_PARAM", "field_name": "amount",
                           "message": "value of 'amount' is invalid."})

        api_key = args.get("api_key", None)
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
        if len(request.DATA) != 0:
            args = request.DATA
        else:
            args = request.GET


        errors = self._validate(args)
        if errors:
            return Response({"keywords": [], "errors": errors})

        category_id = args.get("category_id", "null")
        amount = args.get("amount", 5)
        site_id = self.getSiteID(args["api_key"])
        keywords = cached_result.get("KeywordHotView",
                                     site_id,
                                     (category_id, ))
        if keywords is None:
            keywords = []
            # 1. get from manual hot keywords
            hotwords_record = mongo_client.getStickedKeywordList(site_id,
                                                                 'hot_%s' % category_id)
            if hotwords_record:
                keywords = hotwords_record['keywords']
            # 2. if we didn't get enough keywords
            # get from the auto keyword hot view list
            keywords_set = set(keywords)
            cached_keywords = cached_result.get("AutoKeywordHotView",
                                                site_id,
                                                (category_id, ))
            for keyword in cached_keywords and cached_keywords or []:
                if not keyword in keywords_set:
                    keywords.append(keyword)
            # update cache
            if keywords:
                cached_result.set("KeywordHotView",
                                  site_id,
                                  (category_id, ),
                                  keywords)
        return Response({"keywords": keywords[:amount], "errors": []})


class QuerySuggest(BaseAPIView):
    def _validate(self, args):
        errors = []
        if not isinstance(args.get("q", None), basestring):
            errors.append({"code": "PARAM_REQUIRED", "field_name": "q",
                           "message": "'q' is required and must be a string."})

        api_key = args.get("api_key", None)
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
        if len(request.DATA) != 0:
            args = request.DATA
        else:
            args = request.GET

        errors = self._validate(args)
        if errors:
            return Response({"suggestions": [], "errors": errors})

        q = args.get("q", "")
        api_key = args.get("api_key", "")

        site_id = self.getSiteID(api_key)

        try:
            suggester = es_search_functions.Suggester(mongo_client, site_id)
            suggested_texts = suggester.getQuerySuggestions(q)
        except:
            logging.critical("Unknown exception raised!", exc_info=True)
            return Response({"records": [], "info": {},
                             "errors": [{"code": "UNKNOWN_ERROR",
                                        "message": "Unknown error, please try later."}]})
        return Response({"suggestions": suggested_texts, "errors": []})
