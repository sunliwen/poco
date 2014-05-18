from django.conf.urls import patterns, include, url
from django.http import HttpResponse


def home(request):
    return HttpResponse('{"version": "1.6"}')


urlpatterns = patterns('',
    #url(r'^',           include('examples.search.urls')),
    url(r'^$', home),
    url(r'^api/',       include('apps.apis.search.urls')),
    url(r'^api/',       include('apps.apis.recommender.urls')),
    url(r'^dashboard/', include('apps.web.dashboard.urls')),
    url(r'^admin/',     include('apps.web.adminboard.urls')),
)
