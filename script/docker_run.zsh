#!/usr/bin/env zsh

APP_NAME="mercari_bot"

set -e

cd $(dirname $(dirname $0))

docker build --quiet . -t ${APP_NAME}
docker run \
       --mount type=bind,source=$(dirname $(cd $(dirname $0); pwd))/chrome_data,target=/opt/mercari_bot/chrome_data \
       --mount type=bind,source=$(dirname $(cd $(dirname $0); pwd))/log,target=/opt/mercari_bot/log \
       --mount type=bind,source=$(dirname $(cd $(dirname $0); pwd))/debug,target=/opt/mercari_bot/debug \
       --rm ${APP_NAME}
