from django.conf.urls import patterns, url


# Uncomment the next two lines to enable the admin:
# from django.contrib import admin
# admin.autodiscover()

urlpatterns = patterns('',
    # Examples:
    # url(r'^$', 'dashboard.views.home', name='home'),
    # url(r'^dashboard/', include('dashboard.foo.urls')),

    # Uncomment the admin/doc line below to enable admin documentation:
    # url(r'^admin/doc/', include('django.contrib.admindocs.urls')),

    # Uncomment the next line to enable the admin:
    # url(r'^admin/', include(admin.site.urls)),
    url(r'^$',                              'apps.web.dashboard.views.index', name='dashboard-index'),
    #url(r'^login$',                         'apps.web.dashboard.views.login', name='dashboard-login'),
    url(r'^logout$',                        'apps.web.dashboard.views.logout', name='dashboard-logout'),
    url(r'^sites/$',                        'apps.web.dashboard.views.sites', name="dashboard-sites"),
    url(r'^apply$',                         'apps.web.dashboard.views.apply', name="dashboard-apply"),
    url(r'^site_items_list$',               'apps.web.dashboard.views.site_items_list'),
    url(r'^show_item$',                     'apps.web.dashboard.views.show_item'),
    url(r'^update_category_groups$',        'apps.web.dashboard.views.update_category_groups'),
    url(r'^report/(?P<api_key>.+)/$',       'apps.web.dashboard.views.report', name="dashboard-report"),
    url(r'^items/(?P<api_key>.+)/$',        'apps.web.dashboard.views.items', name='dashboard-items'),
    url(r'^edm/(?P<api_key>.+)/$',          'apps.web.dashboard.views.edm', name="dashboard-edm"),
    url(r'^edm_preview/(?P<api_key>.+)/(?P<emailing_user_id>.+)/$',
                                            'apps.web.dashboard.views.edm_preview', name="dashboard-edm-preview"),
    url(r'^edm_send/(?P<api_key>.+)/(?P<emailing_user_id>.+)/$',
                                            'apps.web.dashboard.views.edm_send', name="dashboard-edm-send"),
    url(r'^user/$',                         'apps.web.dashboard.views.user', name='dashboard-user'),
    url(r'^ajax/update_category_groups$',   'apps.web.dashboard.views.ajax_update_category_groups'),
    url(r'^ajax/update_category_groups2$',  'apps.web.dashboard.views.ajax_update_category_groups2'),
    url(r'^ajax/get_site_statistics$',      'apps.web.dashboard.views.ajax_get_site_statistics'),
    url(r'^ajax/toggle_black_list$',        'apps.web.dashboard.views.ajax_toggle_black_list'),
    url(r'^ajax/toggle_black_list2$',       'apps.web.dashboard.views.ajax_toggle_black_list2'),
    url(r'^ajax/get_black_list$',           'apps.web.dashboard.views.ajax_get_black_list'),
    url(r'^ajax/report$',                   'apps.web.dashboard.views.ajax_report'),
    url(r'^ajax/categroup$',                'apps.web.dashboard.views.ajax_categroup'),
    url(r'^ajax/change_password$',          'apps.web.dashboard.views.ajax_change_password'),
    url(r'^ajax/items/(?P<api_key>.+)/id/(?P<item_id>.+)$',
                                            'apps.web.dashboard.views.ajax_item'),
    url(r'^ajax/items/(?P<api_key>.+)/$',   'apps.web.dashboard.views.ajax_items'),
    url(r'^ajax/recs/(?P<api_key>.+)/id/(?P<item_id>.+)/(?P<rec_type>.+)$',
                                            'apps.web.dashboard.views.ajax_recs'),
)

#urlpatterns += staticfiles_urlpatterns()


