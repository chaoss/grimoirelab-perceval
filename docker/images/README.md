## Perceval Docker minimal image

Perceval Docker image to work in standalone mode. Available in [DockerHub](https://hub.docker.com/r/grimoirelab/perceval/).

## Image contents

- [x] `python:3.4-slim` official image available [here](https://hub.docker.com/_/python/)
- [x] Perceval

## Image build

For building your Perceval image, the only thing you need is having Docker installed in your system.
After that, building your own image is as easy as running the following command from the path `docker/images`:

```
make perceval
```

## Usage

Perceval Docker image is (until now), an image for testing purposes. Due to that, the initial approach is generate a container
for each command mapping a volume providing persistence to the cache:

```
docker run --rm -it --name perceval -v ~/.perceval:/root/.perceval grimoirelab/perceval:latest [PERCEVAL_PARAMS]
```

## User feedback

### Documentation

All the information regarding the image generation is hosted publicly in [Github](https://github.com/chaoss/grimoirelab-perceval/tree/master/docker/images).

### Issues

If you find any issue with this image, feel free to contact us via [Github issue tracking system](https://github.com/grimoirelab/perceval/issues).
