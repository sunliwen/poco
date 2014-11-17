#!/usr/bin/env python

import jieba

def fill_keywords(site_id, item):
    item_name = item["item_name"]
    keywords = " ".join(preprocess_query_str(item_name)).split(" ")
    return keywords

def preprocess_query_str(query_str):
    # ignore "(", ")"
    query_str = query_str.replace("(", "").replace(")", "")
    result = []
    keywords = [keyword for keyword in query_str.split(
        " ") if keyword.strip() != ""]
    for keyword in keywords:
        cutted_keyword = " ".join(
            ["%s" % term for term in jieba.cut_for_search(keyword)])
        result.append(cutted_keyword)
    return result

def strip_item_spec(spec_str):
    if not spec_str:
        return ''
    item_white_set = set(' -()[]{}*.')
    return ''.join([i for i in spec_str if i not in item_white_set])

def preprocess_categories(categories):
    for_facets = ["%s__%s" % (category["parent_id"], category["id"]) for category in categories]
    return [category["id"] for category in categories] + for_facets

def get_item_name(obj):
    _highlight = getattr(obj, "_highlight", None)
    if _highlight:
        item_names = _highlight.get("item_name_standard_analyzed", None)
        if item_names:
            return item_names[0]
    return obj.item_name_standard_analyzed

item_attrs = {
    'available': {'index': {'type': 'boolean'},
                  'serialize': {'include': True}},
    'item_name': {'index': {"type": "string",
                            "store": "yes",
                            "analyzer": "whitespace_lower_analyzer"},
                  'serialize': {'include': True,
                                'by': lambda site_id, item: get_item_name(item)
},
                  'massage': {'by': lambda site_id, item: ' '.join(preprocess_query_str(item['item_name']))}
              },
    "item_name_standard_analyzed": {'index': {"type": "string",
                                              "store": "yes",
                                              "analyzer": "standard"
                                          },
                                    'serialize': {'include': True},
                                    'massage': {'by': lambda site_id, item: item.get('item_name', '')},
                                    'query': {'keyword': {},
                                              'search': {'weight': 1000}
                                          }
                                },
    "item_name_no_analysis": {'index': {"type": "string",
                                        "store": "yes",
                                        "analyzer": "keyword"
                                    },
                              'serialize': {'include': True},
                              'massage': {'by': lambda site_id, item: item.get('item_name', '')}},
    'description': {'index': {'type': 'string'},
                    'serialize': {'include': True},
                    'query': {'search': {}}
                },
    'factory': {'index': {'type': 'string'},
                'serialize': {'include': True}},
                  'price': {'index': {'type': 'float'},
              'serialize': {'include': True},
              'massage': {'by': lambda site_id, item: float(item.get('price', 0))}
          },
    'market_price': {'index': {'type': 'float'},
                     'serialize': {'include': True},
                     'massage': {'by': lambda site_id, item: float(item.get('price', 0))}
                 },
    'image_link': {'index': {'type': 'string'},
                   'serialize': {'include': True}},
    'item_link': {'index': {'type': 'string'},
                    'serialize': {'include': True}},
    'categories': {'index': {'type': 'string', 'index_name': 'category'},
                 'serialize': {'include': True,
                               'by': lambda site_id, item: [cat for cat in
                                                            getattr(item, "categories", [])
                                                            if "__" not in cat]
                           },
                 'massage': {'by': lambda site_id, item: preprocess_categories(item['categories'])}},
    'brand': {'index': {'type': 'string'},
              'serialize': {'include': True},
              'massage': {'by': lambda site_id, item: item['brand']['id'] if item.get('brand', None) else None}},
    'brand_name': {'index': {'type': 'string', 'analyzer': 'standard'},
                   'serialize': {'include': True},
                   'massage': {'by': lambda site_id, item: (item['brand'].get('name', '')
                                                            if item.get('brand', None)
                                                            else None)},
                   'query': {'search': {'weight': 100}}
               },
    'item_level': {'index': {'type': 'integer'},
                    'serialize': {'include': True}},
    'item_spec': {'index': {'type': 'string'},
                    'serialize': {'include': True}},
    'item_spec_ng': {'index': {'type': 'string', 'analyzer': 'ngram_analyzer'},
                     'serialize': {'include': True},
                     'massage': {'by': lambda site_id, item: strip_item_spec(item.get('item_spec', ''))}},
    'origin_place': {'index': {'type': 'integer'},
                    'serialize': {'include': True}},
    'item_comment_num': {'index': {'type': 'integer'},
                    'serialize': {'include': True}},
    'item_id': {'index': {'type': 'string'},
                'serialize': {'include': True}},
    'stock': {'serialize': {'include': True}},
    'keywords': {'index': {'type': 'string', 'analyzer': 'keyword'},
                 'serialize': {'include': True},
                 #'massage': {'by': fill_keywords}
             },
    'tags': {'index': {'type': 'string', 'analyzer': 'keyword'},
                    'serialize': {'include': True}},
    'tags_standard': {'index': {'type': 'string', 'analyzer': 'standard'},
                      'serialize': {'include': True},
                      'massage': {'by': lambda site_id, item: item.get('tags', '')},
                    'query': {'search': {'weight': 10}}},
    'sku': {'index': {'type': 'string', 'analyzer': 'keyword'},
                    'serialize': {'include': True}},
    'sell_num': {'index': {'type': 'integer'},
                    'serialize': {'include': True}},
    'dosage': {'index': {'type': 'string', 'analyzer': 'keyword'},
                    'serialize': {'include': True}},
    'prescription_type': {'index': {'type': 'integer'},
                    'serialize': {'include': True}},
    'item_sub_title': {'index': {'type': 'string'},
                    'serialize': {'include': True}},
    'created_on': {'massage': {'erase': True}},
    'updated_on': {'massage': {'erase': True}},
    '_id': {'massage': {'erase': True}},
}
