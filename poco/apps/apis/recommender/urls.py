from django.conf.urls import patterns, include, url
from rest_framework.urlpatterns import format_suffix_patterns
from apps.apis.recommender import views


urlpatterns = patterns('poco.apps.apis.recommender.views',
    # Examples:
    # url(r'^$', 'editable_pages_example.views.home', name='home'),
    # url(r'^blog/', include('blog.urls')),
    url(r'^v1.6/$', views.APIRootView.as_view(), name="api_root"),
    url(r'^v1.6/public/recommender/$', views.RecommenderAPIView.as_view(),
        name="recommender-recommender"),
    url(r'^v1.6/public/events/$', views.EventsAPIView.as_view(),
        name="recommender-events"),
    url(r'^v1.6/private/items/$', views.ItemsAPIView.as_view(),
        name="recommender-items"),
    url(r'^v1.6/public/recommender/redirect/$', views.recommended_item_redirect,
        name="recommender-redirect"),
    )


urlpatterns = format_suffix_patterns(urlpatterns)
