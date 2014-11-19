from apps.apis.search import es_search_functions

def construct_filters(filters):
    default_filters = {
        "available": [True]
    }

    for fk, fc in default_filters.items():
        if not filters.has_key(fk):
            filters[fk] = fc
    result = {}
    for filter_field, filter_details in filters.items():
        if isinstance(filter_details, list):
            if len(filter_details) == 1:
                result[filter_field] = filter_details[0]
            else:
                result["%s__in" % filter_field] = filter_details
        elif isinstance(filter_details, dict):
            if filter_details.get("type") == "range":
                from_ = filter_details["from"]
                to_   = filter_details["to"]
                result["%s__range" % filter_field] = (from_, to_)
    return result

def construct_sortby(sort_fields):
    order_by_stock = [{"_script": {
                            "script": "doc['stock'].value == 0?1:0",
                            "type": "number",
                            "order": "asc"
                           }}]

    if sort_fields == []:
        sort_fields = ["_score"]

    sort_fields = order_by_stock + sort_fields
    return sort_fields

def construct_highlight():
    return 'item_name_standard_analyzed'

def construct_query(query_str):
    def strip_item_spec(spec_str):
        if not spec_str:
            return ''
        item_white_set = set(' -()[]{}*.')
        return ''.join([i for i in spec_str if i not in item_white_set])

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

    match_phrases = []
    splitted_keywords = " ".join(es_search_functions.preprocess_query_str(query_str)).split(" ")
    for keyword in splitted_keywords:
        match_phrases.append(
            {"multi_match": {
                "fields": ["item_name_standard_analyzed^1000", "brand_name^100", "tags_standard^10", "description"],
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

    # spec query
    spec_query = get_spec_query(query_str)
    if spec_query:
        should_query.append({'match': spec_query})
    sku_query = get_sku_query(query_str)
    if sku_query:
        should_query.append({'term': sku_query})
    if spec_query or sku_query:
        query = {"bool": {"should": should_query,
                          "minimum_should_match": 1}}

    return query

def construct_facets(s, facets_selector, filters):
    def get_default_facets_selector():
        return {
            "brand": {},
            "origin_place": {},
            "categories": {"mode": "SUB_TREE"},
            'dosage': {},
            'prescription_type': {}
        }


    facets_dsl = {}
    categories = filters.get("categories", [])
    if categories:
        cat_id = categories[0]
    else:
        cat_id = None
    facets_selector = (get_default_facets_selector()
                       if facets_selector is None
                       else facets_selector)

    if facets_selector.has_key("categories"):
        categories_facet_mode = facets_selector["categories"]["mode"]
        if categories_facet_mode == "DIRECT_CHILDREN":
            facets_dsl["categories"] = es_search_functions._getSubCategoriesFacets(cat_id, s)
        elif categories_facet_mode == "SUB_TREE":
            facets_dsl["categories"] = es_search_functions.addFilterToFacets(s,
                                        {'terms': {'regex': r'[^_]+', 'field': 'categories', 'size': 5000}})
    for facet_key in ('brand', 'origin_place', 'dosage', 'prescription_type'):
        if facets_selector.has_key(facet_key):
            facets_dsl[facet_key] = es_search_functions.addFilterToFacets(
                s,
                {'terms': {'field': facet_key, 'size': 5000}})


    return facets_dsl, facets_selector
