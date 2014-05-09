import json
import datetime
from recommender.tasks import _write_log


def run(site_id, file_path):
    answer = raw_input("Do you really want to insert raw_logs from %s to site: %s (enter 'yes' to continue)" % (file_path, site_id))
    if answer == "yes":
        cnt = 0
        f = open(file_path, "r")
        for line in f.readlines():
            line = line.strip()
            raw_log = json.loads(line)
            raw_log["created_on"] = datetime.datetime.strptime(raw_log["created_on"], "%Y-%m-%d %H:%M:%S")
            print raw_log
            _write_log(site_id, raw_log, update_visitor_cache=False)
            break
            cnt += 1
            if (cnt % 100) == 0:
                print cnt
    else:
        print "Exit without action."
        sys.exit(0)

