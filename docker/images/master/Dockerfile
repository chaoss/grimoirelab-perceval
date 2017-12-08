FROM python:3.4-slim

MAINTAINER Alberto Martín <alberto.martin@bitergia.com>

ENV GIT_URL_PERCEVAL https://github.com/grimoirelab/perceval.git
ENV GIT_REV_PERCEVAL master
ENV BUILD_PACKAGES build-essential

# install dependencies

RUN apt-get update && \
    apt-get install -y ${BUILD_PACKAGES} git --no-install-recommends && \
    git clone --depth 1 ${GIT_URL_PERCEVAL} -b ${GIT_REV_PERCEVAL} && \
    pip install -r perceval/requirements.txt perceval/ && \
    apt-get remove --purge -y ${BUILD_PACKAGES} && \
    apt-get clean && \
    apt-get autoremove --purge -y && \
    find /var/lib/apt/lists -type f -delete

ENTRYPOINT ["/usr/local/bin/perceval"]
