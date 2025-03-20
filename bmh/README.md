# Bali Művek Home Controller

## Running docker image

BMH can run as a docker container with the following command:

```bash
docker run --privileged -d --restart always \
  -e TZ=Europe/Budapest \
  -v /home/pi/config:/config \
  -v /run/dbus:/run/dbus:ro \
  --network=host \
  ghcr.io/meszibalu/raspberrypi4-64-homeassistant:stable
```

## Building docker image

When the build is running on a non-arm64 machine then arm64 support must be installed first:

```bash
docker run --privileged --rm tonistiigi/binfmt --install arm64
```

Building the image from project root:

```bash
VERSION=2025.3.1
docker build --platform=linux/arm64 \
  -t ghcr.io/meszibalu/raspberrypi4-64-homeassistant:$VERSION \
  -t ghcr.io/meszibalu/raspberrypi4-64-homeassistant:stable \
  --build-arg BUILD_FROM=ghcr.io/home-assistant/aarch64-homeassistant:$VERSION \
  --build-arg BUILD_ARCH=aarch64 \
  .
```

Pushing image:
```bash
docker push ghcr.io/meszibalu/raspberrypi4-64-homeassistant:$VERSION
docker push ghcr.io/meszibalu/raspberrypi4-64-homeassistant:stable
```
