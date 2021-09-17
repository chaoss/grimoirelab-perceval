# Retrieving data from GitHub repositories

[GitHub](https://github.com/) is a popular service for hosting software development. It
provides git repositories associated with issues (tickets) and pull requests (proposed
patches). All this information is available via the [GitHub
API](https://docs.github.com/en). We will use Perceval GitHub backend to retrieve data
from this API for issues and pull requests. For git repositories we can use the Perceval
git backend, as we already introduced in the previous section.

### Basic usage of the GitHub backend

To begin with, let’s get some help from our friend:

```bash
(perceval) $ perceval github --help
[2021-09-17 16:31:55,682] - Sir Perceval is on his quest.
usage: perceval [-h] [--category CATEGORY] [--tag TAG] [--filter-classified] [--from-date FROM_DATE] [--to-date TO_DATE]
                [--archive-path ARCHIVE_PATH] [--no-archive] [--fetch-archive] [--archived-since ARCHIVED_SINCE]
                [--no-ssl-verify] [-o OUTFILE] [--json-line] [--enterprise-url BASE_URL] [--sleep-for-rate]
                [--min-rate-to-sleep MIN_RATE_TO_SLEEP] [-t API_TOKEN [API_TOKEN ...]] [--github-app-id GITHUB_APP_ID]
                [--github-app-pk-filepath GITHUB_APP_PK_FILEPATH] [--max-items MAX_ITEMS] [--max-retries MAX_RETRIES]
                [--sleep-time SLEEP_TIME]
                owner repository
...
```

In that help banner, we see two different ways of using it:
- with no credentials
- with a user token

### Retrieving from GitHub with `category` param

```
(perceval) $ perceval github --category issue grimoirelab perceval
...
```

You can pass category as parameter which take either of issue, pull_request or repository
when using Github Perceval backend. Note that in GitHub every pull request is an issue,
but not every issue is a pull request. Thus, the issues returned may contain pull request
information (included in the field `pull_request` within the issue).

### Retrieving from GitHub with no credentials

If you use the GitHub Perceval backend with no credentials, you’ll have basic access to
the GitHub API. The main difference with using authenticated use is the rate limit: a much
more stringent rate limit (number of requests to the GitHub API) will be applied by
GitHub. In any case, this basic access is very simple, since it requires no user, password
or token. For example, for accessing tickets and pull requests in the Perceval repository:

```bash
(perceval) $ perceval github grimoirelab perceval
[2016-10-11 00:49:33,714] - Sir Perceval is on his quest.
[2016-10-11 00:49:34,576] - Getting info for https://api.github.com/users/jgbarah
{
    "backend_name": "GitHub",
    "backend_version": "0.2.2",
    "data": {
        "assignee": null,
        "assignee_data": {},
        "assignees": [],
        "body": "Based on Sphynx, prepared for ReadTheDocs.\r\n\r\nRight now, this produces (from jgbarah/perceval repository) [this documentation in ReadTheDocs](http://perceval.readthedocs.org). Once this PR is accepted, I plan to switch ReadTheDocs to point to this repostory (master branch), so that the documentation gets rebuilt every time changes are made to the source code.\r\n\r\nThe configuration (docs/conf.py) include lines for running sphinx-apidoc, which generates automatically the docs/perceval.rst file, which is the entry point for the automatically generated documentation, produced based on the docstring comments in the source code.\r\n\r\nThe file index.rst is still a bare bones schema. It should be completed in a later patch, with more detailed information about Perceval itself.",
        "closed_at": "2016-01-04T13:51:56Z",
        "comments": 0,
        "comments_url": "https://api.github.com/repos/grimoirelab/perceval/issues/3/comments",
        "created_at": "2016-01-03T23:46:04Z",
        "events_url": "https://api.github.com/repos/grimoirelab/perceval/issues/3/events",
        "html_url": "https://github.com/grimoirelab/perceval/pull/3",
        "id": 124679251,
        "labels": [],
        "labels_url": "https://api.github.com/repos/grimoirelab/perceval/issues/3/labels{/name}",
        "locked": false,
        "milestone": null,
        "number": 3,
        "pull_request": {
            "diff_url": "https://github.com/grimoirelab/perceval/pull/3.diff",
            "html_url": "https://github.com/grimoirelab/perceval/pull/3",
            "patch_url": "https://github.com/grimoirelab/perceval/pull/3.patch",
            "url": "https://api.github.com/repos/grimoirelab/perceval/pulls/3"
        },
        "repository_url": "https://api.github.com/repos/grimoirelab/perceval",
        "state": "closed",
        "title": "Config files for a documentation, using Sphinx.",
        "updated_at": "2016-01-04T17:42:23Z",
        "url": "https://api.github.com/repos/grimoirelab/perceval/issues/3",
        "user": {
            "avatar_url": "https://avatars.githubusercontent.com/u/1039693?v=3",
            "events_url": "https://api.github.com/users/jgbarah/events{/privacy}",
            "followers_url": "https://api.github.com/users/jgbarah/followers",
            "following_url": "https://api.github.com/users/jgbarah/following{/other_user}",
            "gists_url": "https://api.github.com/users/jgbarah/gists{/gist_id}",
            "gravatar_id": "",
            "html_url": "https://github.com/jgbarah",
            "id": 1039693,
            "login": "jgbarah",
            "organizations_url": "https://api.github.com/users/jgbarah/orgs",
            "received_events_url": "https://api.github.com/users/jgbarah/received_events",
            "repos_url": "https://api.github.com/users/jgbarah/repos",
            "site_admin": false,
            "starred_url": "https://api.github.com/users/jgbarah/starred{/owner}{/repo}",
            "subscriptions_url": "https://api.github.com/users/jgbarah/subscriptions",
            "type": "User",
            "url": "https://api.github.com/users/jgbarah"
        },
        "user_data": {
            "avatar_url": "https://avatars.githubusercontent.com/u/1039693?v=3",
            "bio": null,
            "blog": "http://gsyc.es/~jgb",
            "company": null,
            "created_at": "2011-09-09T21:47:40Z",
            "email": null,
            "events_url": "https://api.github.com/users/jgbarah/events{/privacy}",
            "followers": 37,
            "followers_url": "https://api.github.com/users/jgbarah/followers",
            "following": 0,
            "following_url": "https://api.github.com/users/jgbarah/following{/other_user}",
            "gists_url": "https://api.github.com/users/jgbarah/gists{/gist_id}",
            "gravatar_id": "",
            "hireable": null,
            "html_url": "https://github.com/jgbarah",
            "id": 1039693,
            "location": null,
            "login": "jgbarah",
            "name": "Jesus M. Gonzalez-Barahona",
            "organizations": [
                {
                    "avatar_url": "https://avatars.githubusercontent.com/u/1843608?v=3",
                    "description": null,
                    "events_url": "https://api.github.com/orgs/MetricsGrimoire/events",
                    "hooks_url": "https://api.github.com/orgs/MetricsGrimoire/hooks",
                    "id": 1843608,
                    "issues_url": "https://api.github.com/orgs/MetricsGrimoire/issues",
                    "login": "MetricsGrimoire",
                    "members_url": "https://api.github.com/orgs/MetricsGrimoire/members{/member}",
                    "public_members_url": "https://api.github.com/orgs/MetricsGrimoire/public_members{/member}",
                    "repos_url": "https://api.github.com/orgs/MetricsGrimoire/repos",
                    "url": "https://api.github.com/orgs/MetricsGrimoire"
                },
...
            ],
            "organizations_url": "https://api.github.com/users/jgbarah/orgs",
            "public_gists": 0,
            "public_repos": 26,
            "received_events_url": "https://api.github.com/users/jgbarah/received_events",
            "repos_url": "https://api.github.com/users/jgbarah/repos",
            "site_admin": false,
            "starred_url": "https://api.github.com/users/jgbarah/starred{/owner}{/repo}",
            "subscriptions_url": "https://api.github.com/users/jgbarah/subscriptions",
            "type": "User",
            "updated_at": "2016-09-27T20:51:09Z",
            "url": "https://api.github.com/users/jgbarah"
        }
    },
    "origin": "https://github.com/grimoirelab/perceval",
    "perceval_version": "0.1.0",
    "timestamp": 1476139775.852378,
    "updated_on": 1451929343.0,
    "uuid": "c403532b196ed4020cc86d001feb091c009d3d26"
}
```

In the above perceval output, you can read one item obtained from the GitHub API. As in
the case of git commits, the data obtained from GitHub is in the “data” field. In this
case it is a pull request (notice the “pull_request” field in “data”) but the list of
items include both issues and pull requests, since the same GitHub API provides both.
Perceval also annotates each reference to a GitHub user with the information for that
user, which is properly obtained from the users API. Notice the message where GitHub
informs about a request to that API for obtaining the data for user “jgbarah”, in the
second line of the output above:

```
[2016-10-11 00:49:34,576] - Getting info for https://api.github.com/users/jgbarah
```

If during the retrieval of the data from the GitHub API, the API rate limit is exceeded, a
message similar to this one will be seen:

```
...
RuntimeError: GitHub rate limit exhausted. 3446 seconds for rate reset
```

The number of seconds until the rate reset will depend on your mileage (but in general,
the GitHub rate API for non-authenticated users is pretty low, 50 requests per hour).

To avoid having perceval exiting when the rate limit is exceeded, we can use the
`--sleep-for-rate` option. When this option is used, instead of exiting, when the rate timit
is reached perceval will just sit silently, waiting unting new API requests are available:

```bash
(perceval) $ perceval github grimoirelab perceval --sleep-for-rate
[2016-10-11 00:35:30,215] - Sir Perceval is on his quest.
[2016-10-11 00:35:31,066] - Getting info for https://api.github.com/users/jgbarah
[2016-10-11 00:35:31,066] - GitHub rate limit exhausted. Waiting 3066 secs for rate limit reset.
```

In the following calls, we will always use this option, so that perceval will wait until
the rate limit is reset.

In the case you persevere and run perceval once and again, it is likely that you reach the
rate limit for your IP address. In that case, the message you’ll get will be similar to:

```
requests.exceptions.HTTPError: {'documentation_url': 'https://developer.github.com/v3/#rate-limiting', 'message': "API rate limit exceeded for 79.151.31.149. (But here's the good news: Authenticated requests get a higher rate limit. Check out the documentation for more details.)"}
```

As the message itself states, you can avoid this rate limit by using authentication.

### Retrieving from GitHub with authentication

To avoid the problems due to unauthenticated access to the GitHub API, we can use the
Perceval GitHub backend with authentication using Github tokens:

```
(perceval) $ perceval github grimoirelab perceval --sleep-for-rate \
    -t XXXXX
```

Instead of “XXXXX” use your own GitHub token. You can obtain tokens via the GitHub web
interface. Once you’re authenticated with GitHub, follow the following process:

- Click on “Settings” on your personal pop-up menu (usually obtained by clicking on your avatar, on the top right corner of the web page).
- Once in “Settings”, look for “Personal access tokens”, in the “Developer settings” submenu, in the right menu.
- Once in “Personal access tokens”, click on “Generate new token” (top right).
- Once in “New personal access token”, select a name for your token (“token desription”), and select the scopes for it. If you’re going to use it only with perceval, you don’t really need permissions for any scope, so you don’t need to select any.

Regardless of the method used, perceval produces (as it did for the git backend) a JSON document for each item in stdout, and some messages in stderr. You can see both differentiated, for example, by redirecting stdout to a file:

```bash
(perceval) $ perceval github grimoirelab perceval --sleep-for-rate \
    -t XXXXX > /tmp/perceval-github.output
[2016-10-11 01:20:12,224] - Sir Perceval is on his quest.
[2016-10-11 01:20:13,067] - Getting info for https://api.github.com/users/jgbarah
[2016-10-11 01:20:14,358] - Getting info for https://api.github.com/users/acs
[2016-10-11 01:20:15,626] - Getting info for https://api.github.com/users/sduenas
[2016-10-11 01:20:16,961] - Getting info for https://api.github.com/users/lluismf
[2016-10-11 01:20:18,164] - Getting info for https://api.github.com/users/albertinisg
...
```

Of course, in this case, all items (issues and ñpull requests) will be written to `/tmp/perceval-github.output`.

### Retrieving from a Python script

As in the case of the git backend (and any other backend, for that matter) we can use a
Python script to retrieve the data, instead of the `perceval` command. For example
(`perceval_github_1.py`):

```py
#! /usr/bin/env python3

import argparse

from perceval.backends.core.github import GitHub

# Parse command line arguments
parser = argparse.ArgumentParser(
    description = "Simple parser for GitHub issues and pull requests"
    )
parser.add_argument("-t", "--token",
                    '--nargs', nargs='+',
                    help = "GitHub token")
parser.add_argument("-r", "--repo",
                    help = "GitHub repository, as 'owner/repo'")
args = parser.parse_args()

# Owner and repository names
(owner, repo) = args.repo.split('/')

# create a Git object, pointing to repo_url, using repo_dir for cloning
repo = GitHub(owner=owner, repository=repo, api_token=args.token)
# fetch all issues/pull requests as an iterator, and iterate it printing
# their number, and whether they are issues or pull requests
for item in repo.fetch():
    if 'pull_request' in item['data']:
        kind = 'Pull request'
    else:
        kind = 'Issue'
    print(item['data']['number'], ':', kind)
```

This script accepts as arguments a token and a GitHub repository, in the format
“owner/repo” (for example, “grimoirelab/perceval”). From the repository, it extracts the
owner and the repository name to later instantiate an object of the `GitHub` class. As we
did in the example for git, we get a `fetch` iterator for the object, and for each iterated
item we print its kind (issue or pull request) and its number.

- Include the token in a list, api_token=[“XXXXXX”, “XXXXXX”, …..] as it is possiblity to
  pass a list of tokens to get over rate limits. To run this script, just run (of course,
  substituting “XXXXX” for your token):

```bash
(perceval) $ python3 perceval_github_1.py --repo grimoirelab/perceval -t XXXXX XXXXX...
3 : Pull request
5 : Pull request
4 : Pull request
2 : Pull request
6 : Pull request
8 : Issue
7 : Pull request
9 : Issue
16 : Issue
...
```
