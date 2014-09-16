#!/usr/bin/env python
# -*- coding: utf-8 -*-
from django.conf import settings
from django.core.cache import get_cache

class RecommenderCache:
    CACHE_KEY_PREFIX = 'RECOMMENDER_CACHE'

    @staticmethod
    def _getFullCacheKey(cache_type, site_id, cache_key_tuple):
        return "recommender-cache-%s-%s-%s" % (cache_type, site_id, "|".join(cache_key_tuple))


    @staticmethod
    def getRecommenderCacheResult(site_id, cache_key_tuple):
        cache = get_cache("default")
        full_cache_key = RecommenderCache._getFullCacheKey(RecommenderCache.CACHE_KEY_PREFIX,
                                                           site_id,
                                                           cache_key_tuple)
        return cache.get(full_cache_key)

    @staticmethod
    def setRecommenderCacheResult(site_id, cache_key_tuple, topn):
        cache = get_cache("default")
        full_cache_key = RecommenderCache._getFullCacheKey(RecommenderCache.CACHE_KEY_PREFIX,
                                                           site_id,
                                                           cache_key_tuple)
        cache.set(full_cache_key, topn, settings.RECOMMENDER_CACHE_EXPIRY_TIME)
        return

    @staticmethod
    def delRecommenderCacheResult(site_id, cache_key_tuple):
        cache = get_cache("default")
        full_cache_key = RecommenderCache._getFullCacheKey(RecommenderCache.CACHE_KEY_PREFIX,
                                                           site_id,
                                                           cache_key_tuple)
        cache.delete(full_cache_key)
        return
