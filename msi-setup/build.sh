#!/usr/bin/env bash

CANDLE="\"/c/Program Files (x86)/WiX Toolset v3.10/bin/candle.exe\""
LIGHT="\"/c/Program Files (x86)/WiX Toolset v3.10/bin/light.exe\""
SOURCE_DIR=../electron-ui/build/dist/win-ia32-unpacked

python3.5 -m venv .venv  || python3 -m venv .venv || python -m venv .venv
if [ -d .venv/Scripts ]; then export VENV=`pwd`/.venv/Scripts; else export VENV=`pwd`/.venv/bin; fi

${VENV}/pip install semver pypiwin32
${VENV}/python generate_bundle.py ${SOURCE_DIR}

candle.exe -ext WixUtilExtension crosscloud.wxs
light.exe -ext WixUIExtension -ext WixUtilExtension crosscloud.wixobj -b ${SOURCE_DIR}
signtool sign //v //n "Crosscloud GmbH" crosscloud.msi
mv crosscloud.msi crosscloud-x64-${VERSION}.msi

