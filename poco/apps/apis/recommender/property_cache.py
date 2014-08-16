from django.core.cache import get_cache

from common.utils import CacheUtil


class PropertyCache:
    EXPIRY_TIME = 3600

    def __init__(self, mongo_client):
        self.mongo_client = mongo_client

    def get_cache_key(self, site_id, property_type, id):
        return CacheUtil.get_property_key(site_id,
                                          property_type,
                                          id)

    def get_name(self, site_id, property_type, id):
        prop = self.get(site_id, property_type, id)
        if prop is None:
            return ""
        else:
            return prop.get("name", "")

    def get(self, site_id, property_type, id):
        cache_key = self.get_cache_key(site_id, property_type, id)
        django_cache = get_cache("default")
        cache_entry = django_cache.get(cache_key)
        if cache_entry == "NO_RESULT":
            cache_entry = None
        else:
            if cache_entry is None:
                cache_entry = self.mongo_client.getProperty(site_id, property_type, id)
                if cache_entry is not None:
                    del cache_entry["_id"]
                    django_cache.set(cache_key, cache_entry, self.EXPIRY_TIME)
                else:
                    cache_entry = None
                    django_cache.set(cache_key, "NO_RESULT", self.EXPIRY_TIME)
        return cache_entry
