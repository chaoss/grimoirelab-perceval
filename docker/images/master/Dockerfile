FROM python:3.4-slim

MAINTAINER Alberto Martín <alberto.martin@bitergia.com>

ENV GIT_URL_PERCEVAL https://github.com/grimoirelab/perceval.git
ENV GIT_REV_PERCEVAL master

# install dependencies

RUN apt-get update && \
    apt-get install -y git --no-install-recommends && \
    pip install python-dateutil requests beautifulsoup4 git+${GIT_URL_PERCEVAL}@${GIT_REV_PERCEVAL} && \
    apt-get clean && \
    apt-get purge -y git && \
    apt-get autoremove --purge -y && \
    find /var/lib/apt/lists -type f -delete

ENTRYPOINT ["/usr/local/bin/perceval"]
