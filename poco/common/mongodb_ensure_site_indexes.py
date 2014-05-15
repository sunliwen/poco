import pymongo


class SiteIndexesEnsurer:
    def __init__(self, mongo_client, site_id):
        self.mongo_client = mongo_client
        self.site_id = site_id

    def getSiteDBCollection(self, coll_name):
        return self.mongo_client.getSiteDBCollection(self.site_id, coll_name)

    def fix_item_similarities_collections(self):
        for similarity_type in ("V", "PLO", "BuyTogether"):
            c_item_similarities = self.getSiteDBCollection(
                                    "item_similarities_%s" % similarity_type)
            c_item_similarities.drop_indexes()
            c_item_similarities.ensure_index("item_id", background=True, unique=True)

    def fix_items(self):
        c_items = self.getSiteDBCollection("items")
        c_items.drop_indexes()
        c_items.ensure_index([("item_name", 1)], background=True, unique=False)
        c_items.ensure_index("item_id", background=True, unique=True)#, drop_dups=True)
        c_items.ensure_index([("created_on", -1)], background=True, unique=False)
        c_items.ensure_index([("created_on", 1)], background=True, unique=False)
        c_items.ensure_index([("removed_on", -1)], background=True, unique=False)
        c_items.ensure_index([("removed_on", 1)], background=True, unique=False)

    def fix_purchasing_history(self):
        c_purchasing_history = self.getSiteDBCollection("purchasing_history")
        c_purchasing_history.drop_indexes()
        c_purchasing_history.ensure_index("user_id", background=True, unique=True)

    def fix_raw_logs(self):
        c_raw_logs = self.getSiteDBCollection("raw_logs")
        c_raw_logs.drop_indexes()
        c_raw_logs.ensure_index([("created_on", -1)], background=True, unique=False)
        c_raw_logs.ensure_index([("created_on", 1)], background=True, unique=False)
        c_raw_logs.ensure_index([("user_id", 1)], background=True, unique=False)
        c_raw_logs.ensure_index([("behavior", 1)], background=True, unique=False)


    def fix_statistics(self):
        c_statistics = self.getSiteDBCollection("statistics")
        c_statistics.drop_indexes()
        c_statistics.ensure_index([("date", 1)], background=True, unique=True)


    def fix_viewed_ultimately_buys(self):
        c_viewed_ultimately_buys = self.getSiteDBCollection("viewed_ultimately_buys")
        c_viewed_ultimately_buys.drop_indexes()
        c_viewed_ultimately_buys.ensure_index("item_id", background=True, unique=True)


    def fix_calculation_records(self):
        c_calculation_records = self.getSiteDBCollection("calculation_records")
        c_calculation_records.drop_indexes()
        c_calculation_records.ensure_index([("begin_datetime", -1)], background=True, unique=False)
        c_calculation_records.ensure_index([("end_datetime", -1)], background=True, unique=False)


    def fix_site_checking_daemon_logs(self):
        c_site_checking_daemon_logs = self.getSiteDBCollection("site_checking_daemon_logs")
        c_site_checking_daemon_logs.drop_indexes()
        c_site_checking_daemon_logs.ensure_index([("created_on", -1)], background=True, unique=False)
        c_site_checking_daemon_logs.ensure_index([("checking_id", 1)], background=True, unique=True)

    def fix_user_orders(self):
        c_user_orders = self.getSiteDBCollection("user_orders")
        c_user_orders.drop_indexes()
        c_user_orders.ensure_index([("user_id", 1)], background=True, unique=False)
        c_user_orders.ensure_index([("order_datetime", -1)], background=True, unique=False)

    def fix_rec_black_lists(self):
        c_rec_black_lists = self.getSiteDBCollection("rec_black_lists")
        c_rec_black_lists.drop_indexes()
        c_rec_black_lists.ensure_index([("item_id", 1)], background=True, unique=False)

    def fix_properties(self):
        c_properties = self.getSiteDBCollection("properties")
        c_properties.drop_indexes()
        c_properties.ensure_index([("id", 1)], background=True, unique=False)
        c_properties.ensure_index([("type", 1)], background=True, unique=False)

    def fix_visitors(self):
        c_visitors = self.getSiteDBCollection("visitors")
        c_visitors.drop_indexes()
        c_visitors.ensure_index([("ptm_id", 1)], background=True, unique=True)

    def fix_traffic_metrics(self):
        c_traffic_metrics = self.getSiteDBCollection("traffic_metrics")
        c_traffic_metrics.drop_indexes()
        c_traffic_metrics.ensure_index([("item_id", 1)], background=True, unique=False)

    def fix_cached_hot_view(self):
        c_cached_hot_view = self.getSiteDBCollection("cached_hot_view")
        c_cached_hot_view.drop_indexes()
        c_cached_hot_view.ensure_index("hot_index_type", background=True, unique=False)
        c_cached_hot_view.ensure_index("category_id", background=True, unique=False)
        c_cached_hot_view.ensure_index("brand", background=True, unique=False)

    def fix_search_terms_cache(self):
        c_search_terms_cache = self.getSiteDBCollection("search_terms_cache")
        c_search_terms_cache.drop_indexes()
        c_search_terms_cache.ensure_index("terms_key", background=True, unique=False)

    def fix_suggest_keyword_list(self):
        c_suggest_keyword_list = self.getSiteDBCollection("suggest_keyword_list")
        c_suggest_keyword_list.drop_indexes()
        c_suggest_keyword_list.ensure_index("keyword", background=True, unique=True)
        c_suggest_keyword_list.ensure_index("type", background=True, unique=False)

    def fix_keyword_metrics(self):
        c_keyword_metrics = self.getSiteDBCollection("keyword_metrics")
        c_keyword_metrics.drop_indexes()
        c_keyword_metrics.ensure_index([("keyword", pymongo.ASCENDING), ("category_id", pymongo.ASCENDING)], 
                        background=True, unique=True)

    def fix_cached_results(self):
        c_cached_results = self.getSiteDBCollection("cached_results")
        c_cached_results.drop_indexes()
        c_cached_results.ensure_index("cache_key", background=True, unique=True)

    def fix_all(self):
        self.fix_item_similarities_collections()
        self.fix_items()
        self.fix_purchasing_history()
        self.fix_raw_logs()
        self.fix_statistics()
        self.fix_viewed_ultimately_buys()
        self.fix_calculation_records()
        self.fix_rec_black_lists()
        self.fix_properties()
        self.fix_visitors()
        self.fix_traffic_metrics()
        self.fix_cached_hot_view()
        self.fix_search_terms_cache()
        self.fix_suggest_keyword_list()
        self.fix_keyword_metrics()
        self.fix_cached_results()


def fix_tjb_db_indexes(mongo_client):
    tjbdb = mongo_client.getTjbDb()
    tjbdb["sites"].ensure_index("site_id", 1, background=True, unique=True)
    tjbdb["sites"].ensure_index("api_key", 1, background=True, unique=True)
    tjbdb["sites"].ensure_index("site_token", 1, background=True, unique=True)
    
    tjbdb["users"].ensure_index("user_name", 1, background=True, unique=True)
    tjbdb["admin-users"].ensure_index("user_name", 1, background=True, unique=True)



