# Retrieving data from Gitlab repositories

[Gitlab](https://gitlab.com/) is a platform for hosting software development. It
provides git repositories associated with issues (tickets) and merge requests (proposed
changes). Gitlab is available as a SaaS service or as a self-managed service.

Project data is available via the [Gitlab API](https://docs.gitlab.com/ee/api/). We will 
use Perceval Gitlab backend to retrieve data from this API for issues and merge requests.

For git repository data we can use the Perceval git backend, as we already introduced in 
the previous section.

### Basic usage of the Gitlab backend

To begin with, let’s get some help from our friend:

```bash
(perceval) $ perceval gitlab --help
[2022-09-30 18:09:26,725] - Sir Perceval is on his quest.
usage: perceval [-h] [--category CATEGORY] [--tag TAG] [--filter-classified] [--from-date FROM_DATE] [--blacklist-ids [BLACKLIST_IDS ...]] [-t API_TOKEN] [--archive-path ARCHIVE_PATH]
                [--no-archive] [--fetch-archive] [--archived-since ARCHIVED_SINCE] [--no-ssl-verify] [-o OUTFILE] [--json-line] [--enterprise-url BASE_URL] [--sleep-for-rate]
                [--min-rate-to-sleep MIN_RATE_TO_SLEEP] [--is-oauth-token] [--max-retries MAX_RETRIES] [--sleep-time SLEEP_TIME]
                [--extra-retry-status EXTRA_RETRY_AFTER_STATUS [EXTRA_RETRY_AFTER_STATUS ...]]
                owner repository
...
```

### Authenticating to GitLab

GitLab's API requires authentication for Perceval to operate correctly. To authenticate:

1. Log into your Gitlab instance (eg https://gitlab.com)
2. Visit "Preferences" > "Access Tokens" (`/-/profile/personal_access_tokens`)
3. Add a personal access token with scope of "read_api", naming it as you like
4. Make a record of the generated token value

In the documentation below, the token is populated by in the shell by this command:

```
export GITLAB_TOKEN=glpat-THISISNOTAVALIDTOKEN
```

### Retrieving from Gitlab

```
(perceval) $ perceval gitlab fdroid fdroiddata -t $GITLAB_TOKEN
...
```

You can pass `--category` parameter with either of issue or merge_request to retrieve data
for those item types. If left unset, the default behaviour is to retrieve issue items.

### Perceval output

Regardless of the method used, perceval produces (as it did for the git backend) a JSON document for each item in stdout, and some messages in stderr. You can see both differentiated, for example, by redirecting stdout to a file:

```bash
(perceval) $ perceval gitlab fdroid fdroiddata -t $GITLAB_TOKEN > /tmp/perceval-gitlab.output
[2016-10-11 01:20:12,224] - Sir Perceval is on his quest.
...
```

In this case, the items retrieved will be written to `/tmp/perceval-gitlab.output`, and errors will be printed to the screen.

### Retrieving from a Python script

As in the case of the git backend (and any other backend, for that matter) we can use a
Python script to retrieve the data, instead of the `perceval` command. For example
(`perceval_gitlab_1.py`):

```py
#! /usr/bin/env python3

import argparse

from perceval.backends.core.gitlab import GitLab

# Parse command line arguments
parser = argparse.ArgumentParser(
    description = "Simple parser for GitLab issues"
    )
parser.add_argument("-t", "--token",
                    help = "GitLab token")
parser.add_argument("-r", "--repo",
                    help = "GitLab repository, as 'owner/repo'")
args = parser.parse_args()

# Owner and repository names
(owner, repo) = args.repo.split('/')

# create a GitLab object, pointing to repo_url, using repo_dir for cloning
repo = GitLab(owner=owner, repository=repo, api_token=args.token)
# fetch all issues as an iterator, and iterate it printing
# their number and emojis awarded
for item in repo.fetch():
    emojis = []
    if (item['data']['award_emoji_data']):
        for emoji in item['data']['award_emoji_data']:
            emojis.append(emoji['name'])
    print(item['data']['iid'], ':', item['data']['title'], '(', ', '.join(emojis) if emojis else '', ')')
```

This script accepts as arguments a token and a GitLab repository, in the format
"owner/repo" (for example, "fdroid/fdroiddata"). From the repository, it extracts the
owner and the repository name to later instantiate an object of the `GitLab` class. As we
did in the example for git, we get a `fetch` iterator for the object, and for each iterated
item we print its title and show emojis it is awarded.

```bash
(perceval) $ python docs/perceval/perceval_gitlab_1.py -t $GITLAB_TOKEN -r fdroid/fdroiddata
12 : Remove buggy version of SatStat ( thumbsup, basketball )
16 : 2048 (game) not working on Gingerbread (  )
24 : New Conversations version available (  )
25 : aCal does not work correctly on Razr XT910 (  )
31 : Busybox is disabled (  )
32 : Status of cgeo (  )
29 : Outdated OSMAnd (  )
...
```
