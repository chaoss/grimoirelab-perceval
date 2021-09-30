#! /usr/bin/env python3

from datetime import datetime, timedelta
from perceval.backends.core.gerrit import Gerrit

# hostname of the Gerrit instance
hostname = 'gerrit.opnfv.org'
# user for sshing to the Gerrit instance
user = 'jgbarah'
# retrieve only reviews changed since one day ago
from_date = datetime.now() - timedelta(days=1)
# create a Gerrit object, pointing to hostname, using user for ssh access
repo = Gerrit(hostname=hostname, user=user)

# fetch all reviews as an iterator, and iterate it printing each review id
for review in repo.fetch(from_date=from_date):
    print(review['data']['number'])
