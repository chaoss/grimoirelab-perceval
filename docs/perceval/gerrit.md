# Fetching Gerrit reviews

We can use Perceval to retrieve reviews in a [Gerrit](https://www.gerritcodereview.com/)
instance. Gerrit is a popular system for supporting code review. Developers can upload
patches (proposal for changes to the source code) to it. After upload, Gerrit takes care
of running testing tools, and allows developers to comment and review patches. As a result
of the reviewing process, new versions of the changes can be requested, which will be
later uploaded, and follow the same process until they are accepted by reviewers, or
abandoned.

### Using Perceval as a program

As usual, we can start by asking Perceval for some help, now using the gerrit backend:

```bash
(perceval) $ perceval gerrit --help
[2018-04-03 01:04:23,706] - Sir Perceval is on his quest.
usage: perceval [-h] [--category CATEGORY] [--tag TAG] [--from-date FROM_DATE]
                [--archive-path ARCHIVE_PATH] [--no-archive] [--fetch-archive]
                [--archived-since ARCHIVED_SINCE] [-o OUTFILE] [--user USER]
                [--max-reviews MAX_REVIEWS]
                [--blacklist-reviews [BLACKLIST_REVIEWS [BLACKLIST_REVIEWS ...]]]
                [--disable-host-key-check] [--ssh-port PORT]
                url
...
```

From the banner it produces, we learn that the most simple usage is specifying the url for
the Gerrit instance, and the user to access it. The Perceval backend uses the Gerrit ssh
interface, and thus to use it, ssh access to Gerrit is needed. In most projects, this is
granted with not too much trouble, since it is needed to contribute patches. Look for
instructions on how to configure ssh for Gerrit, for the specific project to mine. The
actual mechanism usually involves signing in to the Gerrit web interface, and then
uploading a ssh public key using the “Settings” option in the Gerrit web interface. As an
example, see the [instructions on how to get ssh access to the OPNFV Gerrit
instance](https://gerrit.opnfv.org/gerrit/Documentation/user-upload.html#ssh).

Once you have access to the Gerrit ssh interface, you only need to specify its url (in
fact, the name of the host letting Gerrit ssh access), and the user with granted access.
Be sure to retrieve reviews only since some recent date, to avoid a unnecesary load on the
Gerrit instance. For example, for OPNFV, you can type:

```
$ perceval gerrit --user username gerrit.opnfv.org --from-date "2018-03-01"
```

If everything works as intended, the result will be similar to:

```bash
[2018-04-03 01:00:59,271] - Sir Perceval is on his quest.
X11 forwarding request failed on channel 0
X11 forwarding request failed on channel 0
{
    "backend_name": "Gerrit",
    "backend_version": "0.10.2",
    "category": "review",
    "data": {
        "branch": "master",
        "comments": [
            {
                "message": "Uploaded patch set 1.",
                "reviewer": {
                    "email": "jenkins-opnfv-ci@opnfv.org",
                    "name": "jenkins-ci",
                    "username": "jenkins-ci"
                },
                "timestamp": 1522705003
            },
            {
                "message": "Patch Set 1:\n\nBuild Started https://build.opnfv.org/ci/job/opnfv-lint-verify-master/8764/ (1/3)",
                "reviewer": {
                    "email": "jenkins-opnfv-ci@opnfv.org",
                    "name": "jenkins-ci",
                    "username": "jenkins-ci"
                },
                "timestamp": 1522705008
            },
...
[2018-04-03 01:02:07,369] - Received 500 reviews in 13.58s
X11 forwarding request failed on channel 0
...

```

As you can see, reviews are obtained by default in batches of 500. You can control this
with `--max-reviews`.

If the ssh interface to Gerrit is not in the default port (29418), you can specify it with
`--ssh-port`.

### Using Perceval as a Python module

As expected, the Perceval backend for Gerrit can be used from Python. See the following
example (also available as `perceval_gerrit_1.py`:

```py
#! /usr/bin/env python3

from datetime import datetime, timedelta
from perceval.backends.core.gerrit import Gerrit

# hostname of the Gerrit instance
hostname = 'gerrit.opnfv.org'
# user for sshing to the Gerrit instance
user = 'user'
# retrieve only reviews changed since one day ago
from_date = datetime.now() - timedelta(days=1)
# create a Gerrit object, pointing to hostname, using user for ssh access
repo = Gerrit(hostname=hostname, user=user)

# fetch all reviews as an iterator, and iterate it printing each review id
for review in repo.fetch(from_date=from_date):
    print(review['data']['number'])
```

This will retrieve all reviews that had any change during the last day, and print their id:

### A more complete example

See below a more complete example of exploiting the data retrieved from Gerrit (also
available as `perceval_gerrit_2.py`:

```py
#! /usr/bin/env python3

import datetime
from perceval.backends.core.gerrit import Gerrit

# hostname of the Gerrit instance
hostname = 'gerrit.opnfv.org'
# user for sshing to the Gerrit instance
user = 'user'
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
```

In this case, we still retrieve all reviews with some change during the last day, but now
we print some more data. For each review, its number and url will be printed, plus the ids
of their patchsets (the different versions of the change being uploaded), and all the
commments (from reviewers, from the testing system, etc.).
