from django.conf.urls import patterns, include, url

from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns('',
    # Examples:
    # url(r'^$', 'search_demo.views.home', name='home'),

    url(r'^admin/', include(admin.site.urls)),
    url(r'^', include('main_app.urls'))
)
