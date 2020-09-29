# perceval-weblate [![Build Status](https://travis-ci.org/Bitergia/grimoirelab-perceval-weblate.svg?branch=master)](https://travis-ci.org/Bitergia/grimoirelab-perceval-weblate) [![Coverage Status](https://img.shields.io/coveralls/Bitergia/grimoirelab-perceval-weblate.svg)](https://coveralls.io/r/Bitergia/grimoirelab-perceval-weblate?branch=master)


Bundle of Perceval backends for Weblate.

## Backends

The backends currently managed by this package support the next repositories:

* Weblate

## Requirements

* Python >= 3.6
* python3-requests >= 2.7
* grimoirelab-toolkit >= 0.1.12
* perceval >= 0.17.1

## Installation

To install this package you will need to clone the repository first:

```
$ git clone https://github.com/Bitergia/grimoirelab-perceval-weblate.git
```

Then you can execute the following commands:
```
$ pip3 install -r requirements.txt
$ pip3 install -e .
```

In case you are a developer, you should execute the following commands to install Perceval in your working directory (option `-e`) and the packages of requirements_tests.txt.
```
$ pip3 install -r requirements.txt
$ pip3 install -r requirements_test.txt
$ pip3 install -e .
```

## Examples

### Weblate

```
$ perceval weblate
```

## License

Licensed under GNU General Public License (GPL), version 3 or later.