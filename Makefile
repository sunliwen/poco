run:
	python poco/manage.py runserver 0.0.0.0:9600

static:
	python poco/manage.py collectstatic
