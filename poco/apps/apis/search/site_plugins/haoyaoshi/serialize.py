from apps.apis.search import es_search_functions

def serialize_facets(site_id, facets_rst, facets_selector, property_cache):
    def get_last_cat_id(cat_id):
        cat_ids = cat_id.split("__")
        if len(cat_ids) > 0:
            return cat_ids[-1]
        else:
            return ""
    facets_result = {}
    if facets_selector.has_key('categories'):
        categories_facet_mode = facets_selector["categories"]["mode"]
        facets_list = facets_rst.get("categories", [])
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
        facets_result["brand"] = []
        for facet in facets_rst.get("brand", []):
            binfo = property_cache.get(site_id, "brand", facet["term"])
            brand = {"id": facet["term"],
                     "label": binfo.get('name', '') if binfo else '',
                     "brand_logo": binfo.get('brand_logo', '') if binfo else '',
                     "count": facet["count"]}
            facets_result["brand"].append(brand)

    for facet_key in ('origin_place', 'dosage', 'prescription_type'):
        if facets_selector.has_key(facet_key):
            facets_result[facet_key] = [{"id": facet["term"],
                                         "label": "",
                                         "count": facet["count"]}
                                        for facet in facets_rst.get(facet_key, [])]
    return facets_result


def serialize_items(site_id, item_list, property_cache):
    def get_item_name(obj):
        _highlight = getattr(obj, "_highlight", None)
        if _highlight:
            item_names = _highlight.get("item_name_standard_analyzed", None)
            if item_names:
                return item_names[0]
        return obj.item_name_standard_analyzed

    result = []
    for item in item_list:
        item_dict = {}
        for field in ("item_id", "price", "market_price", "image_link",
        "item_link", "available", "item_group",
        "brand", "item_level", "item_spec", "item_comment_num",
        "tags", "prescription_type", "sku", "stock", "factory",
        "sell_num", 'dosage', 'item_sub_title'):
            val = getattr(item, field, None)
            if val is not None:
                item_dict[field] = val
        item_dict["categories"] = [cat for cat in getattr(item, "categories", []) if "__" not in cat]
        item_dict["item_name"] = get_item_name(item)
        result.append(item_dict)
    # update brands
    es_search_functions.update_item_brands(site_id, result, property_cache)
    return result
