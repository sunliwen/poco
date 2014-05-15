from django.conf.urls import patterns, include, url


urlpatterns = patterns('',
    # Examples:
    # url(r'^$', 'Dashboard.views.home', name='home'),
    # url(r'^Dashboard/', include('Dashboard.foo.urls')),

    # Uncomment the admin/doc line below to enable admin documentation:
    # url(r'^admin/doc/', include('django.contrib.admindocs.urls')),

    # Uncomment the next line to enable the admin:
    # url(r'^admin/', include(admin.site.urls)),
    url(r'^$', 'adminboard.views.index', name='index'),
    url(r'^ajax/calcAsap$', 'adminboard.views.ajax_calc_asap', name='ajax_calc_asap'),
    url(r'^ajax/loadData$', 'adminboard.views.ajax_load_data', name='ajax_load_data'),
    url(r'^ajax/loadSiteCheckingDetails$', 'adminboard.views.ajax_load_site_checking_details',
                                                name='ajax_load_site_checking_details'),
    #url(r'^add_site$', 'adminboard.views.add_site', name='add_site'),
    url(r'^edit_site$','adminboard.views.edit_site', name="edit_site"),
    url(r'^add_user$', 'adminboard.views.add_user', name="add_user"),
    url(r'^edit_user$', 'adminboard.views.edit_user', name="edit_user"),
    url(r'^user_list$', 'adminboard.views.user_list', name="user_list"),
    url(r'^site_checking_details$', 'adminboard.views.site_checking_details', name="site_checking_details"),
    url(r'^login$', 'adminboard.views.login', name='login'),
    url(r'^logout$', 'adminboard.views.logout', name='logout'),
    #url(r'^s/jquery-1.6.1.min.js$', 'adminboard.views.serve_jquery'),
    #(r'^static/(?P<path>.*)$', 'django.views.static.serve',
    #  {'document_root': os.path.join(os.path.dirname(__file__), 'static').replace('\\','/')})
    )
