#!/bin/bash

set -e
set -x
script_dir=$(dirname $0)

ENV_PARAMS="--env=FUNSIZE_CELERY_CONFIG=funsize.backend.config.dev"
ENV_PARAMS="$ENV_PARAMS --env=GUNCORN_CONF=/app/configs/gunicorn-dev-conf.py"

if [ "$FUNSIZE_S3_UPLOAD_BUCKET" != "" ]; then
    ENV_PARAMS="$ENV_PARAMS \
    --env=AWS_ACCESS_KEY_ID=$FUNSIZE_AWS_ACCESS_KEY_ID \
    --env=AWS_SECRET_ACCESS_KEY=$FUNSIZE_AWS_SECRET_ACCESS_KEY \
    --env=FUNSIZE_S3_UPLOAD_BUCKET=$FUNSIZE_S3_UPLOAD_BUCKET"
else
    ENV_PARAMS="$ENV_PARAMS --env=FUNSIZE_LOCAL_CACHE_DIR=/tmp/funnycache"
fi

cd $script_dir/..
docker build -t funsize .
docker build -t rabbitmq tests/rabbitmq
docker rm -f funsize || :
docker rm -f rabbitmq || :
docker run -d  -P -p 56725:56725 -p 5555:5555 --name rabbitmq rabbitmq


sleep 2
docker run -v $(pwd):/app \
    -v $(pwd)/logs:/var/log/funsize \
    --link rabbitmq:rabbitmq \
    -p 5000:5000 -P --rm \
    $ENV_PARAMS \
    --env=BROKER_URL=amqp://guest@rabbitmq// \
    --env=MBSDIFF_HOOK="/app/funsize/backend/mbsdiff_hook.sh -A http://127.0.0.1:5000/cache -c /var/cache/funsize" \
    --env=FUNSIZE_DEBUG=1 \
    -i -t --name funsize funsize $@

trap "docker stop rabbitmq" EXIT
