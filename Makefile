run:
	python poco/manage.py runserver 0.0.0.0:9600

static:
	python poco/manage.py collectstatic

test:
	python poco/manage.py test

stest:
	@echo "TODO: How to run stest"
	python poco/scripts/stress_test.py poco/stress_test_config3

performance:
	ab -t 3600 -c 100 -n 10000 -p /tmp/SEARCH_REQUEST -T "application/json" http://poco.ehaoyao.com/api/v1.6/public/search/ 
