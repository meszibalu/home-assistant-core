# Bali Művek Home Controller

## Running docker image

### Preparation

Pull BMH image first:

```bash
docker pull ghcr.io/meszibalu/raspberrypi4-64-homeassistant:stable
```

### Running

To run BMH image execute the following command:

```bash
docker run --privileged -d --restart always \
  -e TZ=Europe/Budapest \
  -v /opt/homeassistant:/config \
  -v /run/dbus:/run/dbus:ro \
  --network=host \
  ghcr.io/meszibalu/raspberrypi4-64-homeassistant:stable
```

## Upgrade docker image

### Preparation

Previous BMH container must be stopped and removed during the upgrade, because it was started with `--restart always` flag previously.

```bash
# save image id
IMAGE=$(docker ps -q --filter ancestor=ghcr.io/meszibalu/raspberrypi4-64-homeassistant:stable)

# pull
docker pull ghcr.io/meszibalu/raspberrypi4-64-homeassistant:stable

# stop and remove
docker stop $IMAGE
docker rm $IMAGE
```

### Running

The container must be started the same way as before.

### Cleanup

The old images should be removed after the upgrade otherwise we will run out of space quickly.

```bash
docker image prune
```

## Building docker image

When the build is running on a non-arm64 machine then arm64 support must be installed first:

```bash
docker run --privileged --rm tonistiigi/binfmt --install arm64
```

Building and publishing the image:

```bash
bmh/release.sh
```
