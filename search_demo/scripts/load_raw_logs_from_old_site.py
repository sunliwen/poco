import datetime
import time
import json
from django.test import Client
from django.test.utils import override_settings
from common.mongo_client import getMongoClient


def as_datetime(datetime_str):
    return datetime.datetime.strptime(datetime_str, "%Y-%m-%d %H:%M:%S")


@override_settings(CELERY_EAGER_PROPAGATES_EXCEPTIONS=True,
                   CELERY_ALWAYS_EAGER=True,
                   BROKER_BACKEND='memory')
def run(from_site_id, from_datetime, to_datetime, to_site_id, to_site_from_datetime):
    from_datetime = as_datetime(from_datetime)
    to_datetime = as_datetime(to_datetime)
    to_site_from_datetime = as_datetime(to_site_from_datetime)
    time_delta = to_site_from_datetime - from_datetime
    print "TIME DELTA:", time_delta
    mongo_client = getMongoClient()
    from_c_raw_logs = mongo_client.getSiteDBCollection(from_site_id, "raw_logs")
    to_c_raw_logs = mongo_client.getSiteDBCollection(to_site_id, "raw_logs")
    result_set = from_c_raw_logs.find({"created_on": {"$gte": from_datetime, "$lte": to_datetime}})
    print "map date range: %s, %s to %s, %s" % (from_datetime, to_datetime, to_site_from_datetime, to_site_from_datetime + (to_datetime - from_datetime))
    print from_c_raw_logs, to_c_raw_logs
    print "Total logs:", result_set.count()
    answer = raw_input("Do you want to load raw_logs from %s to %s ?(enter 'yes' to continue)" % (from_site_id, to_site_id))
    if answer == "yes":
        client = Client()
        for raw_log in result_set:
            del raw_log["_id"]
            raw_log["created_on"] = raw_log["created_on"] + time_delta
            #to_c_raw_logs.insert(raw_log)
            post_data = {"api_key": "5a552549"}
            if raw_log["behavior"] in ("V", "AF", "RF", "UNLIKE", "RI", "ASC", "RSC"):
                post_data["item_id"] = raw_log["item_id"]
                post_data["user_id"] = raw_log["user_id"]
            if raw_log["behavior"] == "PLO":
                post_data["user_id"] = raw_log["user_id"]
                post_data["order_id"] = raw_log.get("order_id", None)
                post_data["order_content"] = "|".join(["%(item_id)s,%(price)s,%(amount)s" % order_item for order_item in raw_log["order_content"]])
            if raw_log["behavior"] in ("RI",):
                post_data["score"] = raw_log["score"] 
            BH2EventType = {
                "V": "ViewItem",
                "AF": "AddFavorite",
                "RF": "RemoveFavorite",
                "UNLIKE": "Unlike",
                "RI": "RateItem",
                "ASC": "AddOrderItem",
                "RSC": "RemoveOrderItem",
                "PLO": "PlaceOrder"
            }
            post_data["event_type"] = BH2EventType[raw_log["behavior"]]
            client.cookies["__ptmid"] = raw_log["tjbid"]
            before_count = to_c_raw_logs.count()
            response = client.get("/api/v1.6/public/events/", post_data)
            if response.status_code != 200 or response.data["code"] != 0:
                print response, response.data
            else:
                after_count = to_c_raw_logs.count()
                while after_count <= before_count:
                    print "waiting raw_log being inserted. %s,%s" % (before_count, after_count)
                    time.sleep(0.1)
                    after_count = to_c_raw_logs.count()
                last_raw_log = [rl for rl in to_c_raw_logs.find().sort([("$natural", -1)]).limit(1)][0]
                last_raw_log["created_on"] = raw_log["created_on"]
                to_c_raw_logs.save(last_raw_log)
    else:
        print "Exit without action."
