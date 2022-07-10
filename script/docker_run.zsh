#!/usr/bin/env zsh

APP_NAME="mercari_bot"

set -e

cd $(dirname $(dirname $0))

docker build --quiet . -t ${APP_NAME}
docker run \
       --mount type=bind,source=$(dirname $(cd $(dirname $0); pwd))/chrome_data,target=/opt/${APP_NAME}/chrome_data \
       --mount type=bind,source=$(dirname $(cd $(dirname $0); pwd))/log,target=/opt/${APP_NAME}/log \
       --mount type=bind,source=$(dirname $(cd $(dirname $0); pwd))/debug,target=/opt/${APP_NAME}/debug \
       --name ${APP_NAME}-$(head -c 10 /dev/urandom | base64 | tr -dc 'a-zA-Z0-9' | cut -c 1-4) \
       --rm ${APP_NAME}
