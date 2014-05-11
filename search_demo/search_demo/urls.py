from django.conf import settings
from django.conf.urls import patterns, include, url

from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns('',
    # Examples:
    # url(r'^$', 'search_demo.views.home', name='home'),
    url(r'^admin/', include(admin.site.urls)),
    url(r'^', include('main_app.urls')),
    url(r'^api/', include('api_app.urls')),
    url(r'^api/', include('recommender.urls')),
    url(r'^dashboard/', include('dashboard.urls')),
)


#if settings.DEBUG:
#    urlpatterns += patterns('',
#        url(r'^my/', include('dashboard.urls')),
#    )
