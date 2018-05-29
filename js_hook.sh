#!/usr/bin/env bash
# This script is used by commit-hook, to check the js parts of the code.
cd electron-ui && yarn run lint && cd ..
