from django.conf.urls import patterns, include, url
from rest_framework.urlpatterns import format_suffix_patterns
from api_app import views


urlpatterns = patterns('main_app.views',
    # Examples:
    # url(r'^$', 'editable_pages_example.views.home', name='home'),
    # url(r'^blog/', include('blog.urls')),
    url(r'^v1.6/$', views.api_root, name="api_root"),
    url(r'^v1.6/public/search/$', views.ProductsSearch.as_view(), name="products-search"),
    url(r'^v1.6/public/suggest/$', views.QuerySuggest.as_view(), name="query-suggest"),
    )


urlpatterns = format_suffix_patterns(urlpatterns)
