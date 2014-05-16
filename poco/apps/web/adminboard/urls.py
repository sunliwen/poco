from django.conf.urls import patterns, include, url


urlpatterns = patterns('',
    # Examples:
    # url(r'^$', 'Dashboard.views.home', name='home'),
    # url(r'^Dashboard/', include('Dashboard.foo.urls')),

    # Uncomment the admin/doc line below to enable admin documentation:
    # url(r'^admin/doc/', include('django.contrib.admindocs.urls')),

    # Uncomment the next line to enable the admin:
    # url(r'^admin/', include(admin.site.urls)),
    url(r'^$',                              'apps.web.adminboard.views.index', name='index'),
    url(r'^ajax/calcAsap$',                 'apps.web.adminboard.views.ajax_calc_asap', name='ajax_calc_asap'),
    url(r'^ajax/loadData$',                 'apps.web.adminboard.views.ajax_load_data', name='ajax_load_data'),
    url(r'^ajax/loadSiteCheckingDetails$',  'apps.web.adminboard.views.ajax_load_site_checking_details',
                                                name='ajax_load_site_checking_details'),
    #url(r'^add_site$',                     'apps.web.adminboard.views.add_site', name='add_site'),
    url(r'^edit_site$',                     'apps.web.adminboard.views.edit_site', name="edit_site"),
    url(r'^add_user$',                      'apps.web.adminboard.views.add_user', name="add_user"),
    url(r'^edit_user$',                     'apps.web.adminboard.views.edit_user', name="edit_user"),
    url(r'^user_list$',                     'apps.web.adminboard.views.user_list', name="user_list"),
    url(r'^site_checking_details$',         'apps.web.adminboard.views.site_checking_details', name="site_checking_details"),
    url(r'^login$',                         'apps.web.adminboard.views.login', name='login'),
    url(r'^logout$',                        'apps.web.adminboard.views.logout', name='logout'),
)
