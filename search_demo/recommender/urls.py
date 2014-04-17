from django.conf.urls import patterns, include, url
from rest_framework.urlpatterns import format_suffix_patterns
from recommender import views


urlpatterns = patterns('main_app.views',
    # Examples:
    # url(r'^$', 'editable_pages_example.views.home', name='home'),
    # url(r'^blog/', include('blog.urls')),
    url(r'^v1.6/$', views.APIRootView.as_view(), name="api_root"),
    url(r'^v1.6/events/$', views.EventsAPIView.as_view(), 
        name="recommender-events"),
    url(r'^v1.6/items/$', views.ItemsAPIView.as_view(), 
        name="recommender-items"),
    )


urlpatterns = format_suffix_patterns(urlpatterns)
