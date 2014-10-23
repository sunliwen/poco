from django.conf.urls import patterns, url
from rest_framework.urlpatterns import format_suffix_patterns
from apps.apis.recommender import views
from rest_framework.reverse import reverse


def recommender_patterns():
    return format_suffix_patterns(patterns('',
                                           # TODO, should be listed in a higher level
                                           # url(r'^v1.6/$',
                                           #     views.APIRootView.as_view(),
                                           #     name="api_root"),
                                           url(r'^public/recommender/?$',
                                               views.RecommenderAPIView.as_view(
                                               ),
                                               name="recommender-recommender"),
                                           url(r'^public/events/?$',
                                               views.EventsAPIView.as_view(),
                                               name="recommender-events"),
                                           url(r'^private/items/?$',
                                               views.ItemsAPIView.as_view(),
                                               name="recommender-items"),
                                           url(r'^public/recommender/redirect/?$',
                                               views.recommended_item_redirect,
                                               name="recommender-redirect"),
                                           url(r'^private/keywords/?$',
                                               views.KeywordAPIView.as_view(),
                                               name="recommender-keywords"),
                                           url(r'^private/stick_lists/?$',
                                               views.RecommendStickListsAPIView.as_view(),
                                               name="recommender-stick_lists"),
                                           url(r'^private/recommender/custom_lists/?$',
                                               views.RecommendCustomListsAPIView.as_view(),
                                               name="recommender-custom_lists"),
                                           url(r'^private/stick_items/?$',
                                               views.StickSearchItemsAPIView.as_view(),
                                               name="search-stick_items"),
                                           ))


def reverses(request, format=None):
    return {
        'events':       reverse('recommender-events', request=request, format=format),
        'recommender':  reverse('recommender-recommender', request=request, format=format),
        'items':        reverse('recommender-items', request=request, format=format),
        'redirect':     reverse('recommender-redirect', request=request, format=format),
    }


urlpatterns = recommender_patterns()
