import os
import time
from datetime import datetime
from datetime import timedelta
import logging
import tempfile
from common import utils
import json


class BackFiller:

    """ TODO: should be __init__(self, connection, site_id, begin_dt, end_dt, output_file_path)

            begin_dt, end_dt is the time range of records

     OR should be __init__(self, connection, site_id, last_dt, hours, output_file_path)

            last_dt is the time point to start calculation
            hours is the max hours older then last_dt of the records
    """
    def __init__(self, connection, site_id, last_ts, output_file_path, cached_result_path):
        self.connection = connection
        self.site_id = site_id
        self.raw_logs = utils.getSiteDBCollection(
            connection, site_id, "raw_logs")
        self.c_tmp_user_identified_logs_plo = utils.getSiteDBCollection(
            connection, site_id, "tmp_user_identified_logs_plo")
        self.last_ts = last_ts
        self.output_file_path = output_file_path
        self.cached_result_path = cached_result_path
        self.ptm_id2user = {}

    def dateTimeAsFloat(self, datetime):
        return time.mktime(datetime.timetuple()) + datetime.microsecond / 1000000.0

    def _updateFilledUserId(self, log_doc, new_value):
        if log_doc.has_key("filled_user_id") \
            and log_doc["filled_user_id"].startswith("ANO_") \
                and not new_value.startswith("ANO_"):
            if log_doc["behavior"] == "PLO":
                self.c_tmp_user_identified_logs_plo.insert(
                    {"log_id": log_doc["_id"]})
        log_doc["filled_user_id"] = new_value

    # TODO: maybe use atomic update later?
    def workOnDoc(self, log_doc, is_old_region):
        if log_doc.has_key("ptm_id"):
            user_id = log_doc.get("user_id", "null")
            if not is_old_region and user_id != "null":
                self.ptm_id2user[log_doc["ptm_id"]] = user_id
            if log_doc.get("filled_user_id", None) is None \
                    or log_doc["filled_user_id"].startswith("ANO_"):
                if user_id == "null":
                    if self.ptm_id2user.has_key(log_doc["ptm_id"]):
                        self._updateFilledUserId(
                            log_doc, self.ptm_id2user[log_doc["ptm_id"]])
                    else:
                        self._updateFilledUserId(
                            log_doc, "ANO_" + log_doc["ptm_id"])
                else:
                    self._updateFilledUserId(log_doc, user_id)
                if log_doc.has_key('_id'):
                    self.raw_logs.save(log_doc)
            if log_doc.has_key('_id'):
                del log_doc["_id"]
            log_doc["created_on"] = self.dateTimeAsFloat(log_doc["created_on"])
            rst = "%s\n" % json.dumps(log_doc)
            self.f_output.write(rst)
            self.f_output.flush()
            return rst

    def doc_generator(self, begin, end):
        """
        yield the doc and raw log line
        """

        # 1. get the latest data in cache
        cf = None
        begin_ts = time.mktime(begin.utctimetuple())
        end_ts = time.mktime(begin.utctimetuple())
        latest_line = None
        latest_doc = None
        if os.path.isfile(self.cached_result_path):
            cf = open(self.cached_result_path)
            latest_line = cf.readline()
            try:
                latest_doc = json.loads(latest_line)
                begin_ts = latest_doc['created_on']
            except:
                pass
        begin = datetime.fromtimestamp(begin_ts)

        # 2. yield the new data in mongo
        cursor = self.raw_logs.find({'created_on': {'$gt': begin, '$lt': end}}, timeout=False).sort("created_on", -1)
        for log_doc in cursor:
            yield log_doc
        del cursor
        # 3. yield valid data in cache
        if cf and latest_doc:
            latest_doc['created_on'] = datetime.fromtimestamp(latest_doc['created_on'])
            yield latest_doc
            for ln in cf.readlines():
                try:
                    ln_doc = json.loads(ln)
                    if ln_doc['created_on'] > end_ts:
                        ln_doc['created_on'] = datetime.fromtimestamp(ln_doc['created_on'])
                        yield ln_doc
                    else:
                        break
                except:
                    pass
        if cf:
            cf.close()


    # TODO: start a cursor every 200000 entries?
    # We use find(timeout=False) here and use "del cursor" to close it.
    # see
    # http://stackoverflow.com/questions/5392318/how-to-close-cursor-in-mongokit
    def start(self):
        logger = logging.getLogger("Backfiller")
        self.f_output = open(self.output_file_path, "w")
        latest_ts_this_time = None
        is_old_region = False
        t0 = time.time()
        count = 0
        # TODO: avoid load data repeatly, how about archive it somewhere
        # ASSUMING to calculate on [2013-10-01, 2013-10-08]
        # In mongo shell
        # begin = ISODate("2012-09-20T00:00:00.0Z")
        # end = ISODate("2012-11-01T00:00:00.0Z")
        # db.raw_logs.find({created_on: {$gte: begin, $lt: end}}).count()  # 644607

        # In python with pymongo
        # begin = datetime.strptime('2013-10-22T00:00:00.0Z', '%Y-%m-%dT%H:%M:%S.0Z')
        # end = datetime.strptime('2013-12-01T00:00:00.0Z', '%Y-%m-%dT%H:%M:%S.0Z')
        # cursor = self.raw_logs.find({'created_on': {'$gte': begin, '$lt': end}}, timeout=False).sort("created_on", -1).limit(10000000)

        # I found the online log server isn't using utc
        # end = datetime.utcnow()
        end = datetime.now()
        begin = end - timedelta(days=30)  # should be configurable

        cached_dir = os.path.dirname(self.cached_result_path)
        tmp_file = tempfile.NamedTemporaryFile(dir=cached_dir, delete=False)

        try:
            for log_doc in self.doc_generator(begin, end):
                count += 1
                if count % 10000 == 0:
                    logger.info("Count: %s, %s rows/sec" %
                                (count, count / (time.time() - t0)))

                # TODO use log_doc["created_on"] == last_ts or  >=
                if self.last_ts is not None and log_doc["created_on"] == last_ts:
                    is_old_region = True
                if latest_ts_this_time is None:
                    latest_ts_this_time = log_doc["created_on"]
                log = self.workOnDoc(log_doc, is_old_region)
                tmp_file.write(log)
            if latest_ts_this_time is not None:
                return latest_ts_this_time
            else:
                return self.last_ts
        finally:
            self.f_output.close()
            tmp_file_path = tmp_file.name
            tmp_file.close()
            if os.path.isfile(self.cached_result_path):
                os.remove(self.cached_result_path)
            os.rename(tmp_file_path, self.cached_result_path)
