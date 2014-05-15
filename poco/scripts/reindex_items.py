from recommender import es_client
from common.mongo_client import getMongoClient


def run(site_id):
    answer = raw_input("Do you really want to reindex items of site: %s (enter 'yes' to continue)" % site_id)
    if answer == "yes":
        mongo_client = getMongoClient()
        c_items = mongo_client.getSiteDBCollection(site_id, "items")
        total = c_items.count()
        cnt = 0
        for item in c_items.find():
            del item["_id"]
            #item["categories"] = []
            es_client.es_index_item(site_id, item)
            cnt += 1
            if (cnt % 50) == 0:
                print "%s/%s" % (cnt, total)
    else:
        print "Exit without action."
        sys.exit(0)
