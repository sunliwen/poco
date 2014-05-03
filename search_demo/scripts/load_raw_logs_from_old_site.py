import datetime
from common.mongo_client import getMongoClient


def as_datetime(datetime_str):
    return datetime.datetime.strptime(datetime_str, "%Y-%m-%d %H:%M:%S")


def run(from_site_id, from_datetime, to_datetime, to_site_id, to_site_from_datetime):
    from_datetime = as_datetime(from_datetime)
    to_datetime = as_datetime(to_datetime)
    to_site_from_datetime = as_datetime(to_site_from_datetime)
    time_delta = to_site_from_datetime - from_datetime
    mongo_client = getMongoClient()
    from_c_raw_logs = mongo_client.getSiteDBCollection(from_site_id, "raw_logs")
    to_c_raw_logs = mongo_client.getSiteDBCollection(to_site_id, "raw_logs")
    print "map date range: %s, %s to %s, %s" % (from_datetime, to_datetime, to_site_from_datetime, to_site_from_datetime + time_delta)
    print from_c_raw_logs, to_c_raw_logs
    answer = raw_input("Do you want to load raw_logs from %s to %s ?(enter 'yes' to continue)" % (from_site_id, to_site_id))
    if answer == "yes":

        for raw_log in from_c_raw_logs.find({"created_on": {"$gte": from_datetime, "$lte": to_datetime}}):
            del raw_log["_id"]
            raw_log["created_on"] = raw_log["created_on"] + time_delta
            to_c_raw_logs.insert(raw_log)
    else:
        print "Exit without action."
