import uuid
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import NotFoundError
from apps.apis.search import es_search_functions
from common import mongodb_ensure_site_indexes
from common.mongo_client import getMongoClient


# TODO: move these into per site configurations
INDEX_SETTINGS = {
    "number_of_shards": 1,
    "index": {
        "analysis": {
            "analyzer": {
                "whitespace_lower_analyzer": {
                    "tokenizer": "whitespace",
                    "filter": ["lowercase"]
                },
                "mycn_analyzer_whitespace_pinyin_first_n_full": {
                    "type": "custom",
                    "tokenizer": "whitespace",
                    "filter": ["my_pinyin_first_n_full"]
                },
                "ngram_analyzer": {
                    "type":      "custom",
                    "tokenizer": "ngram_tokenizer",
                    "filter": ['standard',]
                },
            },
            "filter": {
                "my_pinyin_first_n_full": {
                    "type": "pinyin",
                    "first_letter": "prefix",
                    "padding_char": "||"
                }
            },
            "tokenizer": {
                "ngram_tokenizer" : {
                    "type" : "nGram",
                    "min_gram" : "2",
                    "max_gram" : "30",
                    "token_chars": ["letter", "digit"]
                }
            }
        }
    }
}


MAPPINGS = {"keyword": {
            "properties": {
                "keyword_completion": {
                    "type": "completion",
                    "index_analyzer": "simple",
                    "search_analyzer": "simple"
                }
            }
            },
            "item": {
                "properties": {
                    "available": {"type": "boolean"},
                    "item_name": {
                        "type": "string",
                        "store": "yes",
                        "analyzer": "whitespace_lower_analyzer"
                    },
                    "item_name_standard_analyzed": {
                        "type": "string",
                        "store": "yes",
                        "analyzer": "standard"
                    },
                    "item_name_no_analysis": {
                        "type": "string",
                        "store": "yes",
                        "analyzer": "keyword"
                    },
                    "description": {"type": "string"},
                    "factory": {"type": "string"},
                    "price": {"type": "float"},
                    "market_price": {"type": "float"},
                    "image_link": {"type": "string"},
                    "item_link": {"type": "string"},
                    "categories": {"type": "string", "index_name": "category"},
                    "brand": {"type": "string"},
                    "brand_name": {"type": "string", "analyzer": "standard"},
                    "item_level": {"type": "integer"},
                    "item_spec": {"type": "string"},
                    "item_spec_ng": {"type": "string",  "analyzer": "ngram_analyzer"},
                    "origin_place": {"type": "integer"},
                    "item_comment_num": {"type": "integer"},
                    "keywords": {"type": "string",
                                 "analyzer": "keyword"},
                    "tags": {"type": "string", "analyzer": "keyword"},
                    "tags_standard": {"type": "string", "analyzer": "standard"},
                    "sku": {"type": "string", "analyzer": "keyword"},
                    "sell_num": {"type": "integer"},
                    "dosage": {"type": "string", "analyzer": "keyword"},
                    "prescription_type": {"type": "integer"},
                }
            }
            }


def drop_es_item_index(es, site_id):
    item_index = es_search_functions.getESItemIndexName(site_id)
    try:
        es.indices.delete(item_index)
    except NotFoundError:
        pass


def create_es_item_index(es, site_id):
    item_index = es_search_functions.getESItemIndexName(site_id)
    res = es.indices.create(
        index=item_index, body={"mappings": MAPPINGS, "settings": INDEX_SETTINGS})


# TODO: move all scripts.fix_db_indexes here.
def mongodb_initialize_c_items(mongo_client, site_id):
    c_items = mongo_client.getSiteDBCollection(site_id, "items")
    c_items.drop_indexes()
    c_items.ensure_index([("item_name", 1)], background=True, unique=False)
    # , drop_dups=True)
    c_items.ensure_index([("item_id", 1)], background=True, unique=True)
    c_items.ensure_index([("created_on", -1)], background=True, unique=False)
    c_items.ensure_index([("created_on", 1)], background=True, unique=False)
    c_items.ensure_index([("removed_on", -1)], background=True, unique=False)
    c_items.ensure_index([("removed_on", 1)], background=True, unique=False)


def mongodb_drop_items(mongo_client, site_id):
    mongo_client.getSiteDBCollection(site_id, "items").drop()


def update_site_in_mongodb(mongo_client, site_id, site_name, calc_interval, api_prefix="test-"):
    site_record = mongo_client.updateSite(site_id, site_name, calc_interval, api_prefix)
    mongodb_initialize_c_items(mongo_client, site_id)
    return site_record


def drop_site_in_mongodb(mongo_client, site_id):
    mongo_client.dropSiteRecord(site_id)
    mongo_client.dropSiteDB(site_id)


class SiteNotExistsError(Exception):
    pass


class SiteAlreadyExistsError(Exception):
    pass


# This function reset both the "items" collection in db and item-index in ES.
def reset_items(site_id):
    mongo_client = getMongoClient()
    if mongo_client.siteExists(site_id, use_cache=False):
        mongo_client.cleanupItems(site_id)
        reset_item_index(site_id)
    else:
        raise SiteNotExistsError()

# This function reset item-index in ES.
def reset_item_index(site_id):
    es = Elasticsearch()
    drop_es_item_index(es, site_id)
    create_es_item_index(es, site_id)

def create_site(mongo_client, site_id, site_name, calc_interval, api_prefix="test-"):
    if mongo_client.siteExists(site_id, use_cache=False):
        raise SiteAlreadyExistsError()
    site_record = update_site_in_mongodb(
        mongo_client, site_id, site_name, calc_interval, api_prefix)
    regenerate_site_token(mongo_client, site_id)
    # ensure mongodb indexes of site collections
    site_indexes_ensurer = mongodb_ensure_site_indexes.SiteIndexesEnsurer(
        mongo_client, site_id)
    site_indexes_ensurer.fix_all()
    es = Elasticsearch()
    create_es_item_index(es, site_id)
    mongo_client.reloadApiKey2SiteID()
    return mongo_client.getSite(site_id)


def drop_site(mongo_client, site_id):
    drop_site_in_mongodb(mongo_client, site_id)
    es = Elasticsearch()
    drop_es_item_index(es, site_id)
    mongo_client.reloadApiKey2SiteID()


class SiteUserAlreadyExistsError:
    pass


def regenerate_site_token(mongo_client, site_id):
    site = mongo_client.getSite(site_id)
    if site:
        token = str(uuid.uuid4())
        site["site_token"] = token
        c_sites = mongo_client.getTjbDb()["sites"]
        c_sites.save(site)
        return token
    else:
        raise SiteNotExistsError()


def regenerate_metrics_collections(mongo_client, site_id):
    c_traffic_metrics = mongo_client.getSiteDBCollection(site_id, "traffic_metrics")
    c_keyword_metrics = mongo_client.getSiteDBCollection(site_id, "keyword_metrics")
    c_traffic_metrics.remove({})
    c_keyword_metrics.remove({})
    c_raw_logs = mongo_client.getSiteDBCollection(site_id, "raw_logs")
    for raw_log in c_raw_logs.find({}):
        mongo_client.updateTrafficMetricsFromLog(site_id, raw_log)
        mongo_client.updateKeywordMetricsFromLog(site_id, raw_log)
