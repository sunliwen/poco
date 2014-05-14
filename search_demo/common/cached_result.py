from common.mongo_client import getMongoClient
from django.core.cache import get_cache


class CachedResult:
    EXPIRY_TIME = 3600

    def __init__(self, mongo_client):
        self.mongo_client = mongo_client

    def _getFullCacheKey(self, cache_type, site_id, cache_key_tuple):
        return "results-cache-%s-%s-%s" % (cache_type, site_id, "|".join(cache_key_tuple))

    def _setDjangoCache(self, cache_key, result):
        cache = get_cache("default")
        cache.set(cache_key, result, self.EXPIRY_TIME)

    def set(self, cache_type, site_id, cache_key_tuple, result):
        full_cache_key = self._getFullCacheKey(cache_type, site_id, cache_key_tuple)
        self.mongo_client.updateCachedResults(site_id, full_cache_key, result)
        self._setDjangoCache(full_cache_key, result)

    def get(self, cache_type, site_id, cache_key_tuple):
        cache = get_cache("default")
        full_cache_key = self._getFullCacheKey(cache_type, site_id, cache_key_tuple)
        cached_result = cache.get(full_cache_key)
        if cached_result is None:
            cached_result = self.mongo_client.getFromCachedResults(site_id, full_cache_key)
            if cached_result is not None:
                self._setDjangoCache(full_cache_key, cached_result)
        return cached_result


cached_result = CachedResult(getMongoClient())
