#! /usr/bin/env python3

import datetime

from perceval.backends.core.gerrit import Gerrit

# hostname of the Gerrit instance
hostname = 'gerrit.opnfv.org'
# user for sshing to the Gerrit instance
user = 'jgbarah'
# retrieve only reviews changed since this date
from_date = datetime.datetime.now() - datetime.timedelta(days=1)
# create a Gerrit object, pointing to hostname, using user for ssh access
repo = Gerrit(hostname=hostname, user=user)

# fetch all reviews as an iterator, and iterate it printing each review id
for review in repo.fetch(from_date=from_date):
    print("Review:", review['data']['number'], review['data']['url'], end='')
    print(review['data']['status'], review['data']['open'])
    print("  Patchsets:")
    for patch in review['data']['patchSets']:
        print("    ", patch['number'], "Draft:", patch['isDraft'], patch['kind'])
    print("  Comments:")
    for comment in review['data']['comments']:
        print("    Comment:")
        for line in comment['message'].splitlines():
            print("      ", line)
