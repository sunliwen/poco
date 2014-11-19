import importlib
from django.conf import settings

actions = {}

def get_op_from_plugin(action=''):
    """
    """
    global actions
    ess_action = ('index.get_index_setting',             # es index setting
                  'index.get_site_mapping',              # es mapping
                  'index.get_index_item',                # massage item before index
                  'search.construct_facets',             # construct facets before search
                  'search.construct_query',              # construct query before search
                  'search.construct_highlight',          # construct highlight before search
                  'search.construct_sortby',             # construct sortby before search
                  'search.construct_filters',            # construct filters before search
                  'serialize.serialize_items',           # serialize items after search
                  'serialize.serialize_facets'           # serialize facets after search
    )
    if not actions:
        for a in ess_action:
            m, f = ('%s.%s' % (settings.SITE_PLUGIN_PATH, a)).rsplit('.', 1)
            af = getattr(importlib.import_module(m), f)
            actions[a] = af
    if actions.has_key(action):
        return actions[action]
    raise SyntaxError("unknown action: %s" % action)
