# Fetching Git data

Git is the most popular source code management system. It is usually used to track
versions of source code files. Transactions on a git repositories are called “commits”.
Each commit is an atomic change to the files in the repository. For each commit, git
maintains data for tracking what changed, and some metadata about who committed the
change, when, which files were affected, etc. Perceval retrieves this information, and
produces a JSON document (a dictionary when using it from Python) for each commit.

### Using Perceval as a program

Let’s use Perceval to retrieve metadata from the git repository for the Perceval source
code (do you appreciate the nice recursion here?). We will start by using the `perceval`
command that we used to check the installation of Perceval in the previous section.

```bash
(perceval) $ perceval git https://github.com/grimoirelab/perceval.git
[2016-10-03 00:47:46,632] - Sir Perceval is on his quest.
[2016-10-03 00:47:46,633] - Fetching commits: 'https://github.com/grimoirelab/perceval.git' git repository from 1970-01-01 00:00:00+00:00; all branches
{
    "backend_name": "Git",
    "backend_version": "0.3.0",
    "data": {
        "Author": "Santiago Due\u00f1as <sduenas@bitergia.com>",
        "AuthorDate": "Tue Aug 18 18:08:27 2015 +0200",
        "Commit": "Santiago Due\u00f1as <sduenas@bitergia.com>",
        "CommitDate": "Tue Aug 18 18:08:27 2015 +0200",
        "commit": "dc78c254e464ff334892e0448a23e4cfbfc637a3",
        "files": [
            {
                "action": "A",
                "added": "10",
                "file": ".gitignore",
                "indexes": [
                    "0000000...",
                    "ceaedd5..."
                ],
                "modes": [
                    "000000",
                    "100644"
                ],
                "removed": "0"
            },
            {
                "action": "A",
                "added": "1",
                "file": "AUTHORS",
                "indexes": [
                    "0000000...",
                    "a67f214..."
                ],
                "modes": [
                    "000000",
                    "100644"
                ],
                "removed": "0"
            },
            {
                "action": "A",
                "added": "674",
                "file": "LICENSE",
                "indexes": [
                    "0000000...",
                    "94a9ed0..."
                ],
                "modes": [
                    "000000",
                    "100644"
                ],
                "removed": "0"
            }
        ],
        "message": "Initial import",
        "parents": [],
        "refs": []
    },
    "origin": "https://github.com/grimoirelab/perceval.git",
    "perceval_version": "0.3.0",
    "timestamp": 1475448330.809561,
    "updated_on": 1439914107.0,
    "uuid": "29ddd736146e278feb5d84e9dcc1fd310ff50007"
}
...
[2016-10-03 00:47:47,861] - Fetch process completed: 356 commits fetched
[2016-10-03 00:47:47,862] - Sir Perceval completed his quest.
```

Your output will vary depending on the exact version of Perceval you have, and when you
run it. But you will get something similar to this start (with the first commit in
Perceval), followed by many more commits, and the final messages. In addition, by
redirecting `stdout` you can notice that JSON documents are actually written to `stdout`,
while progress messages are written in `stderr`. This makes it easy to get a file with all
commits (one JSON document per commit), or to pipe them to some other command. For
example:

```bash
(perceval) $ perceval git https://github.com/grimoirelab/perceval.git > /tmp/perceval.test
[2016-10-03 00:53:59,235] - Sir Perceval is on his quest.
[2016-10-03 00:53:59,236] - Fetching commits: 'https://github.com/grimoirelab/perceval.git' git repository from 1970-01-01 00:00:00+00:00; all branches
[2016-10-03 00:54:00,349] - Fetch process completed: 356 commits fetched
[2016-10-03 00:54:00,349] - Sir Perceval completed his quest.
```

This will produce the file `/tmp/perceval.test` with all the retrieved commits.

To produce this result, Perceval cloned the git repository to analyze, and got information
for all its commits by using the `git log` command under the hoods. Therefore, you need to
have git installed, but if you’re are in the business of developing software, it would be
weird if you didn’t have it.

One interesting detail of this behavior is that Perceval is cloning the git repository
once and again, to analyze it. You can tell Perceval where to store it, and reuse it the
next time. You will probably notice the difference if you use the time command:

```bash
(perceval) $ time perceval git https://github.com/grimoirelab/perceval.git \
  --git-path /tmp/perceval.git > /tmp/perceval.test
[2016-10-03 01:01:55,360] - Sir Perceval is on his quest.
[2016-10-03 01:01:55,361] - Fetching commits: 'https://github.com/grimoirelab/perceval.git' git repository from 1970-01-01 00:00:00+00:00; all branches
[2016-10-03 01:01:58,195] - Fetch process completed: 356 commits fetched
[2016-10-03 01:01:58,195] - Sir Perceval completed his quest.

real    0m2.991s
user    0m0.544s
sys    0m0.100s

(perceval) $ time perceval git https://github.com/grimoirelab/perceval.git \
  --git-path /tmp/perceval.git > /tmp/perceval.test
[2016-10-03 01:02:00,319] - Sir Perceval is on his quest.
[2016-10-03 01:02:00,321] - Fetching commits: 'https://github.com/grimoirelab/perceval.git' git repository from 1970-01-01 00:00:00+00:00; all branches
[2016-10-03 01:02:01,323] - Fetch process completed: 356 commits fetched
[2016-10-03 01:02:01,323] - Sir Perceval completed his quest.

real    0m1.151s
user    0m0.432s
sys    0m0.032s
```

Of course, differences will be longer for larger repositories.

### Using Perceval as a Python module

But we know that Perceval is a Python library. So, let’s use it as a Python library, from
a Python script `perceval_git_1.py`:

```py
#! /usr/bin/env python3

from perceval.backends.core.git import Git

# url for the git repo to analyze
repo_url = 'http://github.com/grimoirelab/perceval.git'
# directory for letting Perceval clone the git repo
repo_dir = '/tmp/perceval.git'

# create a Git object, pointing to repo_url, using repo_dir for cloning
repo = Git(uri=repo_url, gitpath=repo_dir)
# fetch all commits as an iterator, and iterate it printing each hash
for commit in repo.fetch():
    print(commit['data']['commit'])
```

This code imports the `perceval.backends` module, and then produces an object of the
`perceval.backends.git.Git` class. All classes of this kind include a method for fetching
the items retrieved by the Perceval backend, as an iterator: `fetch()`. In the last two
lines of the script, we iterate through that iterator, printing the hash for all commmits
fetched. The output of the script looks like:

```
(perceval) $ python3 perceval_git_1.py 
...
26bad088db3df0701f095c7cd45f89e2d9948a7a
bfe38f2e61d2f9743ad5f648880c493085f485b8
18e639396a7fb9a01c4d374baa473fdf7f8b1e10
fdf511b0144cb7707cae1a6b8905e83004cf003b
dd0aec7170367160766a1e155b37db5fa2ae61d9
cedc42d8d897d1bf64e999b91fb9ce34464440c9
d7bef8060648f96000a575b1c2af6bc63f9a0ad3
```

### Fetch commits from private Git repositories

If you want to fetch commits from a private github repository, you must pass the
credentials (`username` and `password`/`api-token`) directly in the URL.

```
$ perceval git https://<username>:<api-token>@github.com/chaoss/grimoirelab-perceval
```

### An example: counting commits in a repository

After the first example of using Perceval to get data from git repositories, we can write
a slightly useful Python script: one that counts commits in a git repository. The complete
script is described in the Tools and Tips chapter, and the code can be accessed as
`perceval_git_counter.py`. Its skeleton is as follows:

```py
import argparse
from perceval.backends.core.git import Git

parser = argparse.ArgumentParser(description = "Count commits in a git repo")
parser.add_argument("repo", help = "Repository url")
parser.add_argument("dir", help = "Directory for cloning the repository")
parser.add_argument("--print", action='store_true', help = "Print hashes")
args = parser.parse_args()

repo = Git(uri=args.repo, gitpath=args.dir)
count = 0
for commit in repo.fetch():
    if args.print:
        print(commit['data']['commit'])
    count += 1
print("Number of commmits: %d." % count)
```

The script includes a simple parser that will read the repository url and the directory to
clone it from the command line, and another one (optional) to print commit hashes. The
last lines of the script are quite similar to the previous example: get all the commits
from the generator provided by the Git class, count them, and print the total count.

To run it, just provide those two command line arguments: repository url and directory to clone:

```
$ python3 perceval_git_counter.py https://github.com/grimoirelab/perceval.git /tmp/clonedir
```
