from django.core.cache import get_cache



class BrowsingHistoryCache:
    EXPIRY_TIME = 3600

    def __init__(self, mongo_client):
        self.mongo_client = mongo_client

    def get_cache_key(self, site_id, ptm_id):
        return "browsing-history-cache-%s-%s" % (site_id, ptm_id)

    def update_cache(self, site_id, ptm_id, cache_entry):
        cache_key = self.get_cache_key(site_id, ptm_id)
        django_cache = get_cache("default")
        django_cache.set(cache_key, cache_entry, self.EXPIRY_TIME)

    def get_from_cache(self, site_id, ptm_id, no_result_as_none=False):
        cache_key = self.get_cache_key(site_id, ptm_id)
        django_cache = get_cache("default")
        cache_entry = django_cache.get(cache_key)
        #print "SITE_ID:%s | PTM_ID: %s -> %s" % (site_id, ptm_id, cache_entry)
        if cache_entry is None and not no_result_as_none:
            return []
        return cache_entry

    def get(self, site_id, ptm_id):
        cache_entry = self.get_from_cache(site_id, ptm_id, no_result_as_none=True)
        if cache_entry is None:
            browsing_history = self.mongo_client.getBrowsingHistory(site_id, ptm_id)
            if browsing_history:
                self.update_cache(site_id, ptm_id, browsing_history)
                return browsing_history
            else:
                return []
        else:
            return cache_entry

    def clear(self):
        django_cache = get_cache("default")
        django_cache.clear()

