# Bali Művek Home Controller

## Running docker image

BMH can run as a docker container with the following command:

```bash
docker pull ghcr.io/meszibalu/raspberrypi4-64-homeassistant:stable
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

Building and publishing the image:

```bash
bmh/release.sh
```
