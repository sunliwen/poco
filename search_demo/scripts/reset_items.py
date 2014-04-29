import sys
from common.site_manage_utils import reset_items


def run(site_id):
    print "This script is outdated. Try create_site instead."
    sys.exit(1)
    answer = raw_input("Do you really want to reset items of site(All items would lost!): '%s'?(enter 'yes' to continue)" % site_id)
    if answer == "yes":
        reset_items(site_id)
    else:
        print "Exit without action."
