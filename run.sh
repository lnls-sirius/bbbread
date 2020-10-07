#!/bin/bash

export BREAD_BASE=/root/bbbread
export RSYNC_SERVER="10.128.255.5"

echo Synchronizing bbb-function files
rsync -a --delete-after RSYNC_SERVER::bbbread BREAD_BASE

python-sirius ${BREAD_BASE}/BBBread_Client.py &
