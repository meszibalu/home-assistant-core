# Bali Művek Home Controller

## Running with docker compose

### Preparation

Pull docker compose YAML:

```bash
mkdir -p /opt/homeassistant/config
cd /opt/homeassistant

wget https://raw.githubusercontent.com/meszibalu/home-assistant-core/refs/heads/bmh/bmh/docker-compose.yaml
wget -O .env https://raw.githubusercontent.com/meszibalu/home-assistant-core/refs/heads/bmh/bmh/docker-compose.env
```

The `.env` file contains the default environment settings. Please edit it.

### Download/Upgrade image

The image can be downloaded or upgraded with the following command:

```bash
docker compose pull
```

### Run

It can be run with the following command:

```bash
docker compose up -d
```

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
