import re
import time
import copy
import hashlib
from elasticsearch import Elasticsearch
from django.conf import settings
from django.core.cache import get_cache
from apps.apis.recommender.property_cache import PropertyCache

import es_item_attrs

def getESItemIndexName(site_id):
    #return "item-index-v1-%s" % site_id
    # change index to v4 for #37 -- add item_spec_clean for search
    return "item-index-v5-%s" % site_id


def getESClient():
    return Elasticsearch()


def getItemById(site_id, item_id):
    es = getESClient()
    return es.get(index=getESItemIndexName(site_id), doc_type="item", id=item_id)

import jieba


def preprocess_query_str(query_str):
    return es_item_attrs.preprocess_query_str(query_str)

"""
def get_item_name(obj):
    _highlight = getattr(obj, "_highlight", None)
    if _highlight:
        item_names = _highlight.get("item_name_standard_analyzed", None)
        if item_names:
            return item_names[0]
    return obj.item_name_standard_analyzed
"""

def strip_item_spec(spec_str):
    return es_item_attrs.strip_item_spec(spec_str)

# FIXME: ItemSerializer does not work correctly currently
def serialize_items(item_list):
    result = []
    for item in item_list:
        result.append(es_item_util.serialize_item(None, item))
    return result


def update_item_brands(site_id, items, property_cache):
    """append brand info to items and the brand info stored in property_cache
    """
    brands = {}
    for item in items:
        bid = item.get('brand', '')
        if not bid:
            continue
        if brands.has_key(bid):
            binfo = brands[bid]
            item['brand'] = binfo if binfo else {'id': bid}
            continue
        binfo = property_cache.get(site_id, "brand", bid)
        # add it to dict no matter we get a None
        brands[bid] = binfo
        item['brand'] = binfo if binfo else {'id': bid}

def construct_or_query(query_str, delimiter=","):
    match_phrases = []
    for keyword in query_str.split(delimiter):
        match_phrases.append(
                {"match_phrase": {es_item_util.get_keyword_query_key(): keyword}
                })

    query = {
        "bool": {
            "should": match_phrases,
            "minimum_should_match": 1
        }
    }

    return query

def get_spec_query(query_str):
    spec = strip_item_spec(query_str)
    if len(spec) > 1:
        return {'item_spec_ng': spec}
    return None

def get_sku_query(query_str):
    keywords = [kw.strip() for kw in query_str.strip().split(" ")]
    if len(keywords) == 1:
        keyword = keywords[0]
        return {'sku': keyword}
    return None

# refs:
# http://www.elasticsearch.org/guide/en/elasticsearch/reference/current/query-dsl-bool-query.html
def construct_query(query_str, for_filter=False):
    match_phrases = []
    splitted_keywords = " ".join(preprocess_query_str(query_str)).split(" ")
    for keyword in splitted_keywords:
        match_phrases.append(
            {"multi_match": {
                "fields": es_item_util.get_search_fields(),
                "query": keyword,
                "type": "phrase"
            }}
        )

    query = {
        "bool": {
            "must": match_phrases
        }
    }

    # add spec/sku query
    should_query = [query, ]
    spec_query = get_spec_query(query_str)
    if spec_query:
        should_query.append({'match': spec_query})
    sku_query = get_sku_query(query_str)
    if sku_query:
        should_query.append({'term': sku_query})
    if spec_query or sku_query:
        query = {"bool": {"should": should_query,
                          "minimum_should_match": 1}}

    #query = {"custom_score": {
    #    "query": query,
    #    "params": {
    #        "empty_stock_penalty": 0.5
    #    },
    #    "script": "_score * (doc['stock']==0?empty_stock_penalty:1)"
    #}}


    #if for_filter:
    #    query = {
    #        "bool": {
    #            "must": match_phrases
    #        }
    #    }
    #else:
    #    query = {
    #        "bool": {
    #            "must": match_phrases,
    #            #"should": [
    #            #    {'match': {'item_name': {"boost": 2.0,
    #            #                             'query': splitted_keywords,
    #            #                             'operator': "and"}}}
    #            #]
    #        }
    #    }

    return query


def addFilterToFacets(s, facets):
    filter = s.build_search().get("filter", None)
    if filter:
        facets["facet_filter"] = filter
    return facets


def _getSubCategoriesFacets(cat_id, s):
    if cat_id is None:
        regex = r"null__.*"
    else:
        regex = r"%s__.*" % cat_id
    result = {'terms': {'regex': regex, 'field': 'categories', 'size': 5000}}
    #result = {'terms': {'field': 'categories', 'size': 20}}
    addFilterToFacets(s, result)
    return result


def _extractSuggestedTerms(res, name):
    suggested_keywords = res["facets"][name]
    if suggested_keywords["total"] > 0:
        hits_total = res["hits"]["total"]
        half_hits_total = hits_total / 2.0
        # Fillter out terms which does not help to further narrow down results
        terms = [term for term in suggested_keywords["terms"]
                 if term["count"] < hits_total]
        # TODO
        #terms.sort(lambda a,b: cmp(abs(a["count"] - half_hits_total), abs(b["count"] - half_hits_total)))
        return terms
    else:
        return []


class TermsCache:
    EXPIRY_TIME = 3600  # 1h

    def __init__(self, mongo_client):
        self.mongo_client = mongo_client

    def fetch(self, site_id, terms):
        sorted_terms = copy.copy(terms)
        sorted_terms.sort()
        sorted_terms = sorted_terms
        terms_key = "terms-cache-" + \
            hashlib.md5(u"|".join(sorted_terms).encode("utf8")).hexdigest()
        cache_entry = get_cache("default").get(terms_key)
        if cache_entry is None:
            _, cache_entry = self.mongo_client.fetchSearchTermsCacheEntry(
                site_id, terms)
            if cache_entry:
                del cache_entry["_id"]
                get_cache("default").set(terms_key,
                                         cache_entry, timeout=self.EXPIRY_TIME)
        return cache_entry


class Suggester:

    def __init__(self, mongo_client, site_id):
        self.es = Elasticsearch()
        self.mongo_client = mongo_client
        self.site_id = site_id
        self.terms_cache = TermsCache(mongo_client)
        self.property_cache = PropertyCache(mongo_client)

    def getItemIndex(self):
        return getESItemIndexName(self.site_id)

    def _getMoreSuggestions(self, query_str):
        splitted_keywords = " ".join(preprocess_query_str(query_str))
        query = construct_query(query_str)
        filter = {"term": {"available": True}}
        facets = {'keywords': {'terms': {'field': 'keywords',
                                         'size': 10},
                               "facet_filter": filter},
                  'categories': {'terms': {'field': 'categories', 'size': 5},
                                 "facet_filter": filter}
                  }
        res = self.es.search(index=self.getItemIndex(),
                             search_type="count",
                             body={"query": query,
                                   "facets": facets,
                                   "filter": filter})
        suggested_categories = _extractSuggestedTerms(res, "categories")
        suggested_categories = suggested_categories[:2]
        return _extractSuggestedTerms(res, "keywords"), suggested_categories

    def _tryAutoComplete(self, kw_prefix):
        t1 = time.time()
        res = self.es.suggest(index=self.getItemIndex(),
                              body={"kw": {"text": kw_prefix, "completion": {"field": "keyword_completion"}}})
        options = res["kw"][0]["options"]
        suggested_texts = [option["text"]
                           for option in options if kw_prefix != option["text"]]
        t = time.time() - t1
        return suggested_texts, t

    def getBreadCrumbs(self, category_id):
        names = []
        ids = [category_id]
        #prop = self.mongo_client.getProperty(self.site_id, "category", category_id)
        prop = self.property_cache.get(self.site_id, "category", category_id)
        while prop:
            names.append(prop["name"])
            parent_id = prop["parent_id"]
            if parent_id != "null" and not (parent_id in ids):
                ids.append(parent_id)
                #prop = self.mongo_client.getProperty(self.site_id, "category", parent_id)
                prop = self.property_cache.get(
                    self.site_id, "category", parent_id)
            else:
                break
        names.reverse()
        return names

    def getQuerySuggestions(self, query_str):
        #import time
        #t1 = time.time()
        split_by_wspace = [kw.strip()
                           for kw in query_str.split(" ") if kw.strip()]
        if len(split_by_wspace) > 0:
            kw_prefix = split_by_wspace[-1]
            possible_last_keywords, time_elapsed = self._tryAutoComplete(
                kw_prefix)
            completed_forms = []
            for completed_keyword in possible_last_keywords:
                terms = split_by_wspace[:-1] + [completed_keyword]
                terms_info = self.terms_cache.fetch(self.site_id, terms)
                if terms_info:
                    completed_form = {"type": "completion",
                                      "value": " ".join(terms),
                                      "count": terms_info["count"]}
                    completed_forms.append(completed_form)

            # also suggest more keywords
            # not suggest for last keyword with only one letter/digit
            if re.match(r"[a-zA-Z0-9]{1}", kw_prefix) is None:
                terms_info = self.terms_cache.fetch(
                    self.site_id, split_by_wspace)

                if terms_info:
                    completed_forms_categories = []

                    for suggested_category in terms_info["categories"]:
                        category_id = suggested_category["category_id"]
                        breadcrumbs = self.getBreadCrumbs(category_id)
                        if breadcrumbs:
                            breadcrumbs_str = " > ".join(breadcrumbs)
                            completed_forms_categories.append({"type": "facet",
                                                               "field_name": "categories",
                                                               "facet_label": breadcrumbs_str,
                                                               "value": query_str,
                                                               "category_id": category_id,
                                                               "count": suggested_category["count"]
                                                               })
                    completed_forms = completed_forms_categories + \
                        completed_forms

                    for suggested_term in terms_info["more_terms"][:6]:
                        skip = False
                        for sk in split_by_wspace:
                            if sk in suggested_term["term"] or suggested_term["term"] in sk:
                                skip = True
                                break
                        if skip:
                            continue
                        query = query_str + " " + suggested_term["term"]
                        completed_forms.append({"type": "more_keyword",
                                                "value": u"%s" % query,
                                                "count": suggested_term["count"]
                                                })
            #t2 =time.time()
            # print t2-t1
            return completed_forms
        else:
            return []

class es_item_util:
    @staticmethod
    def get_item_mapping():
        return {'properties': dict([(key, cfg['index'])
                                    for key, cfg in es_item_attrs.item_attrs.iteritems()
                                    if cfg.get('index', {})])}

    @staticmethod
    def get_index_item(site_id, item):
        rst = item.copy()
        for key, cfg in es_item_attrs.item_attrs.iteritems():
            massage = cfg.get('massage', {})
            if massage.has_key('by'):
                operator = massage['by']
                rst[key] = operator(site_id, item)
            elif massage.get('erase', False):
                if rst.has_key(key):
                    del rst[key]
        return rst

    @staticmethod
    def serialize_item(site_id, item):
        keys = [k for k, cfg in es_item_attrs.item_attrs.iteritems()
                if cfg.get('serialize', {}).get('include', False)]

        item_dict = {}
        for k in keys:
            handler = es_item_attrs.item_attrs[k]['serialize'].get('by', None)
            if handler:
                val = handler(site_id, item)
            else:
                val = getattr(item, k, None)

            if val:
                item_dict[k] = val
        return item_dict

    @staticmethod
    def get_keyword_query_key():
        for k, cfg in es_item_attrs.item_attrs.iteritems():
            if not(cfg.get('query', {}).get('keyword', None) is None):
                return k
        assert 'keyword query item should exist' is None

    @staticmethod
    def get_search_fields():
        rst = []
        for k, cfg in es_item_attrs.item_attrs.iteritems():
            if not(cfg.get('query', {}).get('search', None) is None):
                rst.append('%s^%d' % (k, cfg['query']['search']['weight'])\
                                      if cfg['query']['search'].get('weight', 0) else k)
        return rst
