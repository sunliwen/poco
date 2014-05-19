from django.conf.urls import patterns, include, url
from rest_framework.urlpatterns import format_suffix_patterns
from apps.apis.search import views
from rest_framework.reverse import reverse


def search_patterns():
    return format_suffix_patterns(patterns('',
                                           # TODO, should be listed in a higher level
                                           # url(r'^v1.6/$',
                                           #     views.api_root,
                                           #     name="api_root"),
                                           url(r'^public/search/?$',
                                               views.ProductsSearch.as_view(),
                                               name="products-search"),
                                           url(r'^public/suggest/?$',
                                               views.QuerySuggest.as_view(),
                                               name="query-suggest"),
                                           url(r'^public/keywords/?$',
                                               views.Keywords.as_view(),
                                               name="keywords"),
                                           ))


def reverses(request, format=None):
    return {
        'search': reverse('products-search', request=request, format=format),
        'suggest': reverse('query-suggest', request=request, format=format),
        'keywords': reverse('keywords', request=request, format=format),
        #'categories': reverse('categories-list', request=request, format=format)
    }

urlpatterns = search_patterns()
