#!/usr/bin/env bash

set -ex

git checkout master
git pull
git checkout bmh
git merge master --no-edit

if [ -z "$VERSION" ]; then
	VERSION=$(git tag -l | egrep "^[0-9]{4}\.[0-9]+\.[0-9]+$" | sort -V | tail -1)
fi

echo "Latest version: $VERSION"
read -p "Press ENTER to continue"

ARCH=$(uname -m)

echo "Running on arch: $ARCH"

if [ "$ARCH" != "aarch64" ]; then
	echo "Adding binfmt..."
	docker run --privileged --rm tonistiigi/binfmt --install arm64
fi

docker build --platform=linux/arm64 \
  -t ghcr.io/meszibalu/raspberrypi4-64-homeassistant:$VERSION \
  -t ghcr.io/meszibalu/raspberrypi4-64-homeassistant:stable \
  --build-arg BUILD_FROM=ghcr.io/home-assistant/aarch64-homeassistant:$VERSION \
  --build-arg BUILD_ARCH=aarch64 \
  .

echo "Pushing image and tagging git"
read -p "Press ENTER to continue"

docker push ghcr.io/meszibalu/raspberrypi4-64-homeassistant:$VERSION
docker push ghcr.io/meszibalu/raspberrypi4-64-homeassistant:stable

git push mb
git tag bmh-$VERSION
git push mb bmh-$VERSION
