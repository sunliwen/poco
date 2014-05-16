from apps.apis.search.keyword_list import keyword_list


def run(site_id, path):
    answer = raw_input("Do you really want to upload identified keyword file '%s' to site: %s?(enter 'yes' to continue)" % (path, site_id))
    if answer == "yes":
        f_list_to_upload = open(path, "r")
        count = 0
        for line in f_list_to_upload.readlines():
            count += 1
            if (count % 100) == 0:
                print "Count:", count
            line = line.strip()
            if line.startswith("#"):
                list_type = keyword_list.BLACK_LIST
                keyword = line[1:]
            else:
                list_type = keyword_list.WHITE_LIST
                keyword = line
            keyword = unicode(keyword, "utf8")
            if list_type == keyword_list.WHITE_LIST:
                keyword_list.markKeywordsAsWhiteListed(site_id, [keyword])
            elif list_type == keyword_list.BLACK_LIST:
                keyword_list.markKeywordsAsBlackListed(site_id, [keyword])
        f_list_to_upload.close()
        print "Finished."
    else:
        print "Exit without action."
        sys.exit(0)
