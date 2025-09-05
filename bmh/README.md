
# Bali Művek Home Controller

## Running docker image

BMH can run as a docker container with the following command:

```bash
docker pull ghcr.io/meszibalu/raspberrypi4-64-homeassistant:stable
docker run --privileged -d --restart always \
  -e TZ=Europe/Budapest \
  -v /opt/homeassistant:/config \
  -v /run/dbus:/run/dbus:ro \
  --network=host \
  ghcr.io/meszibalu/raspberrypi4-64-homeassistant:stable
```

## Upgrade docker image

Stop and remove previous BMH containers. The previous container must be removed, because it was started with `--restart always` flag previously.

```bash
docker stop $(docker ps -q --filter ancestor=ghcr.io/meszibalu/raspberrypi4-64-homeassistant:stable)
docker rm $(docker ps -aq --filter ancestor=ghcr.io/meszibalu/raspberrypi4-64-homeassistant:stable)
# remove images otherwise we will run out of space quickly
docker rmi $(docker images -aq)
```

Start BMH docker image.

## Building docker image

When the build is running on a non-arm64 machine then arm64 support must be installed first:

```bash
docker run --privileged --rm tonistiigi/binfmt --install arm64
```

Building and publishing the image:

```bash
bmh/release.sh
```
