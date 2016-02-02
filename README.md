# Perceval

Send Sir Perceval on a quest to retrieve and gather data from software
repositories.

## Usage

```
usage: perceval [-c <file>] [-g] <backend> [<args>] | --help

Repositories are reached using specific backends. The most common backends
are:

    bugzilla         Fetch bugs from a Bugzilla server
    gerrit           Fetch reviews from a Gerrit server
    git              Fetch commits from a Git log file
    github           Fetch issues from GitHub

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
$ python3 setup.py install
```
## Documentation

Documentation is generated automagically in the [ReadTheDocs Perceval site](http://perceval.readthedocs.org/).

## Examples

### Bugzilla
```
$ perceval bugzilla https://bugzilla.redhat.com --from-date '2016-01-01'
```

### Git
Git backend requieres as input a Git log file. We recommend to use the next command to get the most complete log file.

```
git log --raw --numstat --pretty=fuller --decorate=full --parents --topo-order -M -C -c --remotes=origin --all > /tmp/gitlog.log
```

Then, to run the backend, just execute the next command:

```
$ perceval git /tmp/gitlog.log
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
$ perceval gerrit --user user --url review.openstack.org --from-date '2016-01-01'
```

### GitHub
```
$ perceval github --owner elastic --repository filebeat --from-date '2016-01-01' --token abcdabcdabcdabcd
```

## License

Licensed under GNU General Public License (GPL), version 3 or later.
