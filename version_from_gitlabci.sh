#!/bin/env bash

# this scripts uses the gitlab variables to build a VERSION env variable
# if this is a tag starting with a v the rest of the CI_BUILD_TAG is used as version
# if there is no tag, it is called yyyy.mm.${CI_BUILD_ID}-dev


if [ -n "$CI_BUILD_TAG" ]; then
    # Strip the "v" from the build tag and add the commit's short ref.
    export VERSION=${CI_BUILD_TAG:1}
else
    export VERSION="0.$((CI_BUILD_ID / 65536)).$((CI_BUILD_ID % 65536))-dev"
fi 

echo '*********************************************************'
echo "                 Build: ${VERSION}"
echo '*********************************************************'
