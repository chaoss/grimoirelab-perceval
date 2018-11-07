# Perceval [![Build Status](https://travis-ci.org/chaoss/grimoirelab-perceval.svg?branch=master)](https://travis-ci.org/chaoss/grimoirelab-perceval) [![Coverage Status](https://img.shields.io/coveralls/chaoss/grimoirelab-perceval.svg)](https://coveralls.io/r/chaoss/grimoirelab-perceval?branch=master) [![PyPI version](https://badge.fury.io/py/perceval.svg)](https://badge.fury.io/py/perceval) [![Documentation in RTD](https://readthedocs.org/projects/perceval/badge/)](http://perceval.readthedocs.io)

Send Sir Perceval on a quest to retrieve and gather data from software
repositories.

## Usage

```
usage: perceval [-c <file>] [-g] <backend> [<args>] | --help | --version

Repositories are reached using specific backends. The most common backends
are:
    askbot           Fetch questions and answers from Askbot site
    bugzilla         Fetch bugs from a Bugzilla server
    bugzillarest     Fetch bugs from a Bugzilla server (>=5.0) using its REST API
    confluence       Fetch contents from a Confluence server
    discourse        Fetch posts from Discourse site
    dockerhub        Fetch repository data from Docker Hub site
    gerrit           Fetch reviews from a Gerrit server
    git              Fetch commits from Git
    github           Fetch issues from GitHub
    gitlab           Fetch issues from GitLab
    googlehits       Fetch hits from Google API
    groupsio         Fetch messages from Groups.io
    hyperkitty       Fetch messages from a HyperKitty archiver
    jenkins          Fetch builds from a Jenkins server
    jira             Fetch issues from JIRA issue tracker
    launchpad        Fetch issues from Launchpad issue tracker
    mattermost       Fetch posts from a Mattermost server
    mbox             Fetch messages from MBox files
    mediawiki        Fetch pages and revisions from a MediaWiki site
    meetup           Fetch events from a Meetup group
    nntp             Fetch articles from a NNTP news group
    phabricator      Fetch tasks from a Phabricator site
    pipermail        Fetch messages from a Pipermail archiver
    redmine          Fetch issues from a Redmine server
    rss              Fetch entries from a RSS feed server
    slack            Fetch messages from a Slack channel
    stackexchange    Fetch questions from StackExchange sites
    supybot          Fetch messages from Supybot log files
    telegram         Fetch messages from the Telegram server
    twitter          Fetch tweets from the Twitter Search API

optional arguments:
  -h, --help            show this help message and exit
  -v, --version         show version
  -c FILE, --config FILE
                        set configuration file
  -g, --debug           set debug mode on

Run 'perceval <backend> --help' to get information about a specific backend.
```

## Requirements

* Python >= 3.4
* python3-dateutil >= 2.6
* python3-requests >= 2.7
* python3-bs4 (beautifulsoup4) >= 4.3
* python3-feedparser >= 5.1.3
* python3-dulwich >= 0.18.5
* grimoirelab-toolkit >= 0.1.4

## Installation

There are several ways for installing Perceval on your system: from packages,
from a docker image or from the source code.

### Pip

Perceval can be installed using [pip](https://pip.pypa.io/en/stable/), a tool
for installing Python packages. To do it, run the next command:

```
$ pip3 install perceval
```

### Docker

A Perceval Docker image is available at [DockerHub](https://hub.docker.com/r/grimoirelab/perceval/).

Detailed information on how to run and/or build this image can be found [here](https://github.com/chaoss/grimoirelab-perceval/tree/master/docker/images/).

### Source code

To install from the source code you will need to clone the repository first:

```
$ git clone https://github.com/chaoss/grimoirelab-perceval.git
```

Then you can execute the following commands:
```
$ pip3 install -r requirements.txt
$ pip3 install .
```

In case you are a developer, you should execute the following commands to install Perceval in your working directory (option `-e`) and the packages of requirements_tests.txt.
```
$ pip3 install -r requirements.txt
$ pip3 install -r requirements_tests.txt
$ pip3 install -e .
```

## Documentation

Documentation is generated automagically in the [ReadTheDocs Perceval site](http://perceval.readthedocs.org/).

## References

If you use Perceval in your research papers, please refer to [Perceval: software project data at your will](https://dl.acm.org/citation.cfm?id=3183475) -- [Pre-print](https://www.researchgate.net/profile/Valerio_Cosentino/publication/325334393_Perceval_Software_Project_Data_at_Your_Will/links/5b066c9fa6fdcc8c2522b07c/Perceval-Software-Project-Data-at-Your-Will.pdf):

### APA style

```
Dueñas, S., Cosentino, V., Robles, G., & Gonzalez-Barahona, J. M. (2018, May). Perceval: software project data at your will. In Proceedings of the 40th International Conference on Software Engineering: Companion Proceeedings (pp. 1-4). ACM.
```

### BibTeX

```
@inproceedings{duenas2018perceval,
  title={Perceval: software project data at your will},
  author={Due{\~n}as, Santiago and Cosentino, Valerio and Robles, Gregorio and Gonzalez-Barahona, Jesus M},
  booktitle={Proceedings of the 40th International Conference on Software Engineering: Companion Proceeedings},
  pages={1--4},
  year={2018},
  organization={ACM}
}
```


## Examples

### Askbot
```
$ perceval askbot 'http://askbot.org/' --from-date '2016-01-01'
```

### Bugzilla
To fetch bugs from Bugzilla, you have two options:

a) Use the traditional backend

```
$ perceval bugzilla 'https://bugzilla.redhat.com/' --backend-user user --backend-password pass --from-date '2016-01-01'
```

b) Use the REST API backend for Buzilla 5.0 (or higher) servers. We strongly recommend
this backend when data is fetched from version servers >=5.0 because the retrieval
process is much faster.

```
$ perceval bugzillarest 'https://bugzilla.mozilla.org/' --backend-user user --backend-password pass --from-date '2016-01-01'
```

### Confluence
```
$ perceval confluence 'https://wiki.opnfv.org/' --from-date '2016-01-01'
```

### Discourse
```
$ perceval discourse 'https://foro.mozilla-hispano.org/' --from-date '2016-01-01'
```

### Docker Hub
```
$ perceval dockerhub grimoirelab perceval
```

### Gerrit
To run gerrit, you will need an authorized SSH private key:

```
$ eval `ssh-agent -s`
$ ssh-add ~/.ssh/id_rsa
Identity added: /home/user/.ssh/id_rsa (/home/user/.ssh/id_rsa)
```

To run the backend, execute the next command:

```
$ perceval gerrit --user user 'review.openstack.org' --from-date '2016-01-01'
```

### Git

To run this backend execute the next command. Take into account that to run
this backend Git program has to be installed on your system.

```
$ perceval git 'https://github.com/chaoss/grimoirelab-perceval.git' --from-date '2016-01-01'
```

Git backend can also work with a Git log file as input. We recommend to use the next command to get the most complete log file.

```
git log --raw --numstat --pretty=fuller --decorate=full --parents --reverse --topo-order -M -C -c --remotes=origin --all > /tmp/gitlog.log
```

Then, to run the backend, just execute any of the next commands:

```
$ perceval git --git-log '/tmp/gitlog.log' 'file:///myrepo.git'
```

or

```
$ perceval git '/tmp/gitlog.log'
```

### GitHub
```
$ perceval github elastic logstash --from-date '2016-01-01'
```

### GitLab
```
$ perceval gitlab elastic logstash --from-date '2016-01-01'
```

### GoogleHits
```
$ perceval googlehits "bitergia grimoirelab"
```

### Groups.io
```
$ perceval groupsio 'updates' -t 'abcdefghijk' --from-date '2016-01-01'
```

### HyperKitty
```
$ perceval hyperkitty 'https://lists.mailman3.org/archives/list/mailman-users@mailman3.org' --from-date 2017-01-01
```

### Jenkins
```
$ perceval jenkins 'https://build.opnfv.org/ci/'
```

### JIRA
```
$ perceval jira 'https://tickets.puppetlabs.com' --project PUP --from-date '2016-01-01'
```

### Launchpad
```
$ perceval launchpad ubuntu --from-date '2016-01-01'
```

### Mattermost
```
$ perceval mattermost 'http://mattermost.example.com' jgw7jdmjkjf19ffkwnw59i5f9e --from-date '2016-01-01' -t 'abcdefghijk'
```

### MBox
```
$ perceval mbox 'http://example.com' /tmp/mboxes/
```

### MediaWiki
```
$ perceval mediawiki 'https://wiki.mozilla.org' --from-date '2016-06-30'
```

### Meetup
```
$ perceval meetup 'Software-Development-Analytics' --from-date '2016-06-01' -t abcdefghijk
```

### NNTP
```
$ perceval nntp 'news.mozilla.org' 'mozilla.dev.project-link' --offset 10
```

### Phabricator
```
$ perceval phabricator 'https://secure.phabricator.com/' -t 123456789abcefe
```

### Pipermail
```
$ perceval pipermail 'https://mail.gnome.org/archives/libart-hackers/'
```

Pipermail also is able to fetch data from Apache's `mod_box` interface:
```
$ perceval pipermail 'http://mail-archives.apache.org/mod_mbox/httpd-dev/'
```

### Redmine
```
$ perceval redmine 'https://www.redmine.org/' --from-date '2016-01-01' -t abcdefghijk
```

### RSS
```
$ perceval rss 'https://blog.bitergia.com/feed/'
```

### Slack
```
$ perceval slack C0001 --from-date 2016-01-12 -t abcedefghijk
```

### StackExchange
```
$ perceval stackexchange --site stackoverflow --tagged python --from-date '2016-01-01' -t abcdabcdabcdabcd
```

### Supybot
```
$ perceval supybot 'http://channel.example.com' /tmp/supybot/
```

### Telegram

Telegram backend needs an API token to authenticate the bot. In addition and
in order to fetch messages from a group or channel, privacy settings must be
disabled. To know how to create a bot, to obtain its token and to configure it
please read the [Telegram Bots docs pages](https://core.telegram.org/bots).

```
$ perceval telegram mybot -t 12345678abcdefgh --chats 1 2 -10
```

### Twitter

Twitter backend needs a bearer token to authenticate the requests. It can be obtained
using the code available on GistGitHub:
https://gist.github.com/valeriocos/7d4d28f72f53fbce49f1512ba77ef5f6

```
$ perceval twitter grimoirelab -t 12345678abcdefgh
```

## Running tests

Perceval comes with a comprehensive list of unit tests.
To run them, in addition to the dependencies installed with Perceval,
you need version 0.8.6 of  `httpretty`.
Currently, latest version in pypi is 0.8.14,
which seems to have a bug exposed by some Perceval tests.
So, ensure you install 0.8.6, which is known to work with them:

```
$ pip install httpretty==0.8.6
$ cd tests
$ python3 run_tests.py
```

## License

Licensed under GNU General Public License (GPL), version 3 or later.
