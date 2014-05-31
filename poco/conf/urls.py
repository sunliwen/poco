from django.conf.urls import patterns, include, url
from django.http import HttpResponse
from rest_framework.views import APIView
from rest_framework.response import Response

def home(request):
    return HttpResponse('{"version": "1.6"}')


## TODO, should add to urlpatterns automatically, when the module is enabled.

from apps.apis.recommender.urls import recommender_patterns, reverses as recommender_reverses
from apps.apis.search.urls import search_patterns, reverses as search_reverses


poco_patterns = recommender_patterns() + search_patterns()


class APIRootView(APIView):
    def get(self, request, format=None):
        return Response(dict(
            (
            recommender_reverses(request, format).items() +
            search_reverses(request, format).items()
            )
        ))

urlpatterns = patterns('',
    #url(r'^',           include('examples.search.urls')),
    url(r'^$', home),
    url(r'^api/v1.6/$', APIRootView.as_view(), name="api_root"),
    url(r'^api/v1.6/',  include(poco_patterns)),

    url(r'^dashboard/', include('apps.web.dashboard.urls')),
    url(r'^admin/',     include('apps.web.adminboard.urls')),
    url(r'^example/search/',   include('examples.search.urls'))
)
