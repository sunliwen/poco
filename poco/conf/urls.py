from django.conf import settings
from django.conf.urls import patterns, include, url

from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns('',
    # Examples:
    # url(r'^$', 'poco.views.home', name='home'),
    #url(r'^admin/', include(admin.site.urls)),
    url(r'^',           include('examples.search.urls')),
    url(r'^api/',       include('apps.apis.search.urls')),
    url(r'^api/',       include('apps.apis.recommender.urls')),
    url(r'^dashboard/', include('apps.web.dashboard.urls')),
    url(r'^admin/',     include('apps.web.adminboard.urls')),
)
