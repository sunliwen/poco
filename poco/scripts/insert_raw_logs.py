import json
import datetime
import time
from pymongo.errors import ConnectionFailure
from recommender.tasks import _write_log


def run(site_id, file_path):
    answer = raw_input("Do you really want to insert raw_logs from %s to site: %s (enter 'yes' to continue)" % (file_path, site_id))
    if answer == "yes":
        cnt = 0
        f = open(file_path, "r")
        for line in f.readlines():
            #if cnt < 38137:
            #    cnt += 1
            #    continue
            line = line.strip()
            try:
                raw_log = json.loads(line)
            except ValueError:
                print "Invalid raw_log line:", line
                import sys; sys.exit(0)
            #print raw_log; sys.exit(0)
            raw_log["created_on"] = datetime.datetime.strptime(raw_log["created_on"], "%Y-%m-%d %H:%M:%S")
            try:
                _write_log(site_id, raw_log, is_update_visitor_cache=False)
            except ConnectionFailure:
                print "Failed to insert:", raw_log
                print cnt
                import sys; sys.exit(0)
            cnt += 1
            if (cnt % 100) == 0:
                print cnt
                time.sleep(0.2)
    else:
        print "Exit without action."
        sys.exit(0)

