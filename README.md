# Perceval [![Build Status](https://travis-ci.org/grimoirelab/perceval.svg?branch=master)](https://travis-ci.org/grimoirelab/perceval) [![Coverage Status](https://img.shields.io/coveralls/grimoirelab/perceval.svg)](https://coveralls.io/r/grimoirelab/perceval?branch=master)

Send Sir Perceval on a quest to retrieve and gather data from software
repositories.

## Usage

```
usage: perceval [-c <file>] [-g] <backend> [<args>] | --help

Repositories are reached using specific backends. The most common backends
are:

    bugzilla         Fetch bugs from a Bugzilla server
    discourse        Fetch posts from Discourse site
    gerrit           Fetch reviews from a Gerrit server
    git              Fetch commits from a Git log file
    github           Fetch issues from GitHub
    jenkins          Fetch builds from a Jenkins server
    jira             Fetch issues from JIRA issue tracker
    mbox             Fetch messages from MBox files
    pipermail        Fetch messages from a Pipermail archiver
    stackexchange    Fetch questions from StackExchange sites

optional arguments:
  -h, --help            show this help message and exit
  -c FILE, --config FILE
                        set configuration file
  -g, --debug           set debug mode on

Run 'perceval <backend> --help' to get information about a specific backend.
```

## Requirements

* Python >= 3.4
* python3-dateutil >= 2.0
* python3-requests >= 2.7
* python3-bs4 (beautifulsoup4) >= 4.3

## Installation

```
$ pip install -r requirements.txt
$ python3 setup.py install
```

## Docker

A Perceval Docker image is available at [DockerHub](https://hub.docker.com/r/grimoirelab/perceval/).

Detailed information on how to run and/or build this image can be found [here](https://github.com/grimoirelab/perceval/tree/master/docker/images/).

## Documentation

Documentation is generated automagically in the [ReadTheDocs Perceval site](http://perceval.readthedocs.org/).

## Examples

### Bugzilla
```
$ perceval bugzilla 'https://bugzilla.redhat.com/' --backend-user user --backend-password pass --from-date '2016-01-01'
```

### Discourse
```
$ perceval discourse 'https://foro.mozilla-hispano.org/' --from-date '2016-01-01'
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
$ perceval gerrit --user user --url 'review.openstack.org' --from-date '2016-01-01'
```

### Git
```
$ perceval git 'https://github.com/grimoirelab/perceval.git' --from-date '2016-01-01'
```

Git backend can also work with a Git log file as input. We recommend to use the next command to get the most complete log file.

```
git log --raw --numstat --pretty=fuller --decorate=full --parents --reverse --topo-order -M -C -c --remotes=origin --all > /tmp/gitlog.log
```

Then, to run the backend, just execute the next command:

```
$ perceval git /tmp/gitlog.log
```

### GitHub
```
$ perceval github --owner elastic --repository filebeat --from-date '2016-01-01'
```

### Jenkins
```
$ perceval jenkins 'http://jenkins.cyanogenmod.com/'
```

### JIRA
```
$ perceval jira 'https://tickets.puppetlabs.com' --project PUP --from-date '2016-01-01'
```

### MBox
```
$ perceval mbox 'http://example.com' /tmp/mboxes/
```

### Pipermail
```
$ perceval pipermail 'https://mail.gnome.org/archives/libart-hackers/'
```

### StackExchange
```
$ perceval stackexchange --site stackoverflow --tagged python --from-date 2016-01-01 --token abcdabcdabcdabcd
```

## License

Licensed under GNU General Public License (GPL), version 3 or later.
