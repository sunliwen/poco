from django.conf.urls import patterns, include, url


urlpatterns = patterns('examples.search.views',
    # Examples:
    # url(r'^$', 'editable_pages_example.views.home', name='home'),
    # url(r'^blog/', include('blog.urls')),
    url(r'^$', 'v_index', name='examples_search_v_index'),
    url(r'^ajax/auto-complete-term/$', 'v_ajax_auto_complete_term', name='examples_search_v_ajax_auto_complete_term'))
