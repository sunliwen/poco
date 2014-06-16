from recommender import es_client
from common.mongo_client import getMongoClient
from apps.apis.search.keyword_list import keyword_list


def run(site_id):
    #print "This script ignore descript field currently!"
    answer = raw_input("Do you really want to reindex items of site: %s (enter 'yes' to continue)" % site_id)
    if answer == "yes":
        mongo_client = getMongoClient()
        c_items = mongo_client.getSiteDBCollection(site_id, "items")
        total = c_items.count()
        cnt = 0
        for item in c_items.find():
            del item["_id"]
            #if item.has_key("description"):
            #    del item["description"]
            #item["categories"] = []
            es_client.es_index_item(site_id, item)
            cnt += 1
            if (cnt % 50) == 0:
                print "%s/%s" % (cnt, total)

        # also fill whitelisted keywords
        for record in keyword_list.fetchSuggestKeywordList(site_id):
            if record["type"] == keyword_list.WHITE_LIST:
                keyword_list.markKeywordsAsWhiteListed(site_id, [record["keyword"]])

    else:
        print "Exit without action."
        sys.exit(0)
