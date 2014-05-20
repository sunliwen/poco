import sys
import os
import json


if len(sys.argv) < 2:
    print "Usage: stress_test.py configuration_file"
    sys.exit(1)


class StressTest:
    def __init__(self, config_file):
        config ={}
        execfile(config_file, config, config)
        self.config = config

    def run_test(self, merged_config):
        command = 'ab -c %(CONCURRENCY)s -n %(REQUEST_NUM)s -p /tmp/STRESS_TEST_POSTFILE -T "application/json" %(API_ROOT)s/api/v1.6/public%(api_path)s' 
        full_command = command % merged_config
        post_data = merged_config["body"]
        post_data["api_key"] = merged_config["API_KEY"]
        f = open("/tmp/STRESS_TEST_POSTFILE", "w")
        f.write(json.dumps(post_data))
        f.close()
        print full_command
        print post_data
        os.system(full_command)

    def run_tests(self):
        for test_name, test_config in self.config["POST_DATA_MAP"].items():
            merged_config = {}
            merged_config.update(self.config)
            merged_config.update(test_config)
            self.run_test(merged_config)

stress_test = StressTest(sys.argv[1])
stress_test.run_tests()
