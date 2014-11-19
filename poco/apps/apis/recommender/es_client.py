from elasticsearch import Elasticsearch
from apps.apis.search import plugins
from apps.apis.search import es_search_functions


def es_index_item(site_id, item):
    es = Elasticsearch()

    #plugins.es_item_util.get_index_item(site_id, item)
    plugins.get_op_from_plugin('index.get_index_item')(site_id, item)
    res = es.index(index=es_search_functions.getESItemIndexName(site_id), doc_type='item', id=item["item_id"], body=item)


#def es_update_items_keywords(site_id):
#    # FIXME: there may be race condition with new items update come it
#    # TODO: get all items from mongodb
#    for item in items:
#        es_index_item(site_id, item)
