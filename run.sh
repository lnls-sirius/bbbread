#!/bin/bash
set +x
export RSYNC_LOCAL=/root/bbbread

echo Synchronizing bbbread files
rsync -a --delete-after 10.128.255.5::bbbread $RSYNC_LOCAL --contimeout=5


echo Run script
python-sirius ${RSYNC_LOCAL}/BBBread_Client.py

