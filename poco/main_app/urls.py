from django.conf.urls import patterns, include, url


urlpatterns = patterns('main_app.views',
    # Examples:
    # url(r'^$', 'editable_pages_example.views.home', name='home'),
    # url(r'^blog/', include('blog.urls')),
    url(r'^$', 'v_index', name='main_app_v_index'),
    url(r'^ajax/auto-complete-term/$', 'v_ajax_auto_complete_term', name='main_app_v_ajax_auto_complete_term'))
