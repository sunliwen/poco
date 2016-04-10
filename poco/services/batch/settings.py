work_dir = None
tac_command = "tac"
mongodb_host = "localhost"
replica_set = None
log_dir = None
cached_result_dir = None

from local_settings import *

assert work_dir != None
assert mongodb_host is not None
assert log_dir is not None
assert cached_result_dir is not None
