#!/bin/bash
set +x
export RSYNC_LOCAL=/root/bbbread

echo Synchronizing bbbread files
rsync -a --delete-after 10.128.114.161::bbbread $RSYNC_LOCAL --contimeout=5


echo Run script
python-sirius ${RSYNC_LOCAL}/client.py

