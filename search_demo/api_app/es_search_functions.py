import re
from elasticsearch import Elasticsearch


def getESItemIndexName(site_id):
    return "item-index-%s" % site_id


import jieba
def preprocess_query_str(query_str):
    result = []
    keywords = [keyword for keyword in query_str.split(" ") if keyword.strip() != ""]
    for keyword in keywords:
        cutted_keyword = " ".join(["%s" % term for term in jieba.cut_for_search(keyword)])
        result.append(cutted_keyword)
    return result


# refs: http://www.elasticsearch.org/guide/en/elasticsearch/reference/current/query-dsl-bool-query.html
def construct_query(query_str, for_filter=False):
    splitted_keywords = " ".join(preprocess_query_str(query_str)).split(" ")
    match_phrases = []
    for keyword in splitted_keywords:
        match_phrases.append({"match_phrase": {"item_name_standard_analyzed": keyword}})

    if for_filter:
        query = {
            "bool": {
                "must": match_phrases
            }
        }
    else:
        query = {
            "bool": {
                "must": match_phrases,
                "should": [
                    {'match': {'item_name': {"boost": 2.0, 
                                             'query': splitted_keywords,
                                             'operator': "and"}}}
                ]
            }
        }

    return query

def addFilterToFacets(s, facets):
    filter = s._build_query().get("filter", None)
    if filter:
        facets["facet_filter"] = filter
    return filter

def _getSubCategoriesFacets(cat_id, s):
    if cat_id is None:
        regex = r"null__.*"
    else:
        regex = r"%s__.*" % cat_id
    result = {'terms': {'regex': regex, 'field': 'categories', 'size': 20}}
    #result = {'terms': {'field': 'categories', 'size': 20}}
    addFilterToFacets(s, result)
    return result


def _extractSuggestedTerms(res, name):
    suggested_keywords = res["facets"][name]
    if suggested_keywords["total"] > 0:
        hits_total = res["hits"]["total"]
        half_hits_total = hits_total / 2.0
        # Fillter out terms which does not help to further narrow down results
        terms = [term for term in suggested_keywords["terms"] if term["count"]  < hits_total]
        #TODO
        #terms.sort(lambda a,b: cmp(abs(a["count"] - half_hits_total), abs(b["count"] - half_hits_total)))
        return terms
    else:
        return []


class Suggester:
    def __init__(self, site_id):
        self.es = Elasticsearch()
        self.site_id = site_id

    def getItemIndex(self):
        return getESItemIndexName(self.site_id)

    def _getMoreSuggestions(self, query_str):
        splitted_keywords = " ".join(preprocess_query_str(query_str))
        query = construct_query(query_str)
        filter = {"term": {"available": True}}
        facets = {'keywords': {'terms': {'field': 'keywords',
                                          'size': 10},
                               "facet_filter": filter},
                  'categories': {'terms': {'regex': r'\d{4}', 'field': 'categories', 'size': 5},
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
        res = self.es.suggest(index=self.getItemIndex(), 
                    body={"kw": {"text": kw_prefix, "completion": {"field": "keyword_completion"}}})
        options = res["kw"][0]["options"]
        suggested_texts = [option["text"] for option in options]
        return suggested_texts

    def getQuerySuggestions(self, query_str):
        split_by_wspace = [kw.strip() for kw in query_str.split(" ") if kw.strip()]
        if len(split_by_wspace) > 0:
            kw_prefix = split_by_wspace[-1]
            possible_last_keywords = self._tryAutoComplete(kw_prefix)
            completed_forms = []
            # TODO: use msearch
            for kw in possible_last_keywords:
                completed_form = (" ".join(split_by_wspace[:-1]) + " " + kw).strip()
                query = construct_query(completed_form, for_filter=True)
                res = self.es.search(index=self.getItemIndex(),
                                        search_type="count",
                                        body={"query": query,
                                        "filter": {"term": {"available": True}}})
                count = res["hits"]["total"]
                if count > 0:
                    completed_forms.append({"type": "completion",
                                            "value": u"%s" % completed_form,
                                            "count": count})

            # also suggest more keywords
            if re.match(r"[a-zA-Z0-9]{1}", kw_prefix) is None: # not suggest for last keyword with only one letter/digit
                suggested_keywords, suggested_categories = self._getMoreSuggestions(query_str)

                completed_forms_categories = []
                for suggested_term in suggested_categories:
                    category_id = suggested_term["term"]
                    #category = CATEGORY_MAP_BY_ID.get(category_id, None)
                    # FIXME
                    category = None
                    if category:
                        breadcrumbs = get_breadcrumbs(category)[1:]
                        breadcrumbs_str = " > ".join([cat["category"]["name"] for cat in breadcrumbs])
                        completed_forms_categories.append({"type": "facet", 
                                                "field_name": "categories",
                                                "facet_label": breadcrumbs_str,
                                                "value": query_str,
                                                "category_id": category_id,
                                                "count": suggested_term["count"]
                                                })

                completed_forms = completed_forms_categories + completed_forms

                for suggested_term in suggested_keywords:
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
            return completed_forms
        else:
            return []



