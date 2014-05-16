from django.conf.urls import patterns, include, url

urlpatterns = patterns('',
    url(r'^',           include('examples.search.urls')),
    url(r'^api/',       include('apps.apis.search.urls')),
    url(r'^api/',       include('apps.apis.recommender.urls')),
    url(r'^dashboard/', include('apps.web.dashboard.urls')),
    url(r'^admin/',     include('apps.web.adminboard.urls')),
)
