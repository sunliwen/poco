import sys
import os.path
from apps.apis.search.keyword_list import keyword_list


def run(site_id, path):
    print "Note: "
    print "   1. add '#' to a line to black list a keyword"
    print "   2. lines without '#' would be treated as white listed"
    print "   3. some lines are pre-marked as black listed. You may adjust this by removing the '#'"
    answer = raw_input("Do you really want to extract unidentified keyword file for site: %s to path: %s?(enter 'yes' to continue)" % (site_id, path))
    if answer == "yes":
        f_add_to_whitelist = open(path, "w")
        for record in keyword_list.fetchSuggestKeywordList(site_id):
            keyword = record["keyword"].encode("utf8")
            #if record["type"] == keyword_list.WHITE_LIST:
            #    f_white.write("%s\n" % keyword)
            #elif record["type"] == keyword_list.BLACK_LIST:
            #    f_black.write("%s\n" % keyword)
            if record["type"] == keyword_list.UNIDENTIFIED_LIST:
                if len(record["keyword"]) < 2 or record["count"] < 3:
                    f_add_to_whitelist.write("#%s\n" % keyword)
                else:
                    f_add_to_whitelist.write("%s\n" % keyword)
        f_add_to_whitelist.close()
        print "Finished."

    else:
        print "Exit without action."
        sys.exit(0)
