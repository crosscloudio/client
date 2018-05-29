#!/usr/bin/env bash
# bootstrap-client.sh
locale-gen
export LC_ALL=en_US.UTF-8
export LANG=en_US.UTF-8

apt-get update
apt-get install -y vim-nox
apt-get install -y python3 python3-dev python3-pip
apt-get install -y git

# Dependencies for cryptography
apt-get install -y libssl-dev libffi-dev

pip3 install --upgrade pip
pip3 install --upgrade setuptools
pip3 install --upgrade distutils

# Before installing 
mkdir -p ~/.ssh
chmod 700 ~/.ssh
ssh-keyscan -H gitlab.crosscloud.me > ~/.ssh/known_hosts
ssh -T git@gitlab.crosscloud.me

cd /crosscloud/Core
pip3 install -r requirements.txt

echo "*** Finished provisioning. Machine should be ready!"
