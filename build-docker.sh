#!/usr/bin/env bash

cd $PYTHONPATH
VERSION=`./suzieq/version.py`
poetry build
if [ $# -eq 0 ]; then
    BUILD_TAG=$VERSION
else
    BUILD_TAG=$VERSION-$1
fi
poetry export -f requirements.txt --without-hashes > /tmp/requirements.txt
diff -q build/requirements.txt /tmp/requirements.txt > /dev/null
if [ $? -ne 0 ]; then
    echo "Building image suzieq-base:$VERSION"
    poetry export -f requirements.txt --without-hashes > ./build/requirements.txt
    docker build -t suzieq-base:$VERSION -f Dockerfile-sqbase .
fi
BASE_EXISTS=`docker images -q suzieq-base:$VERSION`
if [ -z "$BASE_EXISTS" ]; then
    echo "Building image suzieq-base:$VERSION"
    docker build -t suzieq-base:$VERSION -f Dockerfile-sqbase .
fi
echo "Building image ddutt/suzieq:$BUILD_TAG"
if [ $# -eq 0 ]; then
    docker build --build-arg version=$VERSION -t ddutt/suzieq:$BUILD_TAG -t ddutt/suzieq:latest -t netenglabs/suzieq:$BUILD_TAG -t netenglabs/suzieq:latest .
else
    docker build --build-arg version=$VERSION -t ddutt/suzieq:$BUILD_TAG -t netenglabs/suzieq:$BUILD_TAG .
fi
