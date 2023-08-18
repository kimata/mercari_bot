File Edit Options Buffers Tools Sh-Script Help
#!/usr/bin/env zsh

set -x # コマンドの内容を表示
set -e # エラーが発生したらそこで終了

NAME=bot_mercari_inventory_control
REGISTRY=registry.green-rabbit.net/library

NAME=mercari_bot
GROUP=kimata
REGISTRY=registry.green-rabbit.net:5000
TAG=latest

docker build . -t ${NAME}
docker tag ${NAME} ${REGISTRY}/${GROUP}/${NAME}:${TAG}
docker push ${REGISTRY}/${GROUP}/${NAME}:${TAG}

echo "finish: ${REGISTRY}/${GROUP}/${NAME}:${TAG}"
