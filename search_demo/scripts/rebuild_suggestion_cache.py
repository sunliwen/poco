from api_app.tasks import rebuild_suggestion_cache


def run(site_id):
    print "Rebuild suggestion cache for : %s" % site_id
    rebuild_suggestion_cache.apply(rebuild_suggestion_cache)
    print "Request sent."
