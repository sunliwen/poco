from apps.apis.search.tasks import rebuild_suggestion_cache


def run(site_id):
    print "Rebuild suggestion cache for : %s" % site_id
    rebuild_suggestion_cache.delay(site_id)
    print "Request sent."
