#!/usr/bin/env zsh

APP_NAME="mercari_bot"

set -e

cd $(dirname $(dirname $0))

docker build --quiet . -t ${APP_NAME}
docker run --rm ${APP_NAME}
