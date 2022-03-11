#!/bin/bash
set +x
export RSYNC_LOCAL=/root/bbbread

echo Synchronizing bbbread files
rsync -a --delete-after 10.128.114.161::bbbread $RSYNC_LOCAL --contimeout=5
if [ "$?" -eq "0" ]
then
    echo "Rsync succesful"
else
    echo "Rsync failed, resorting to git pull"
    git pull
fi

echo Run script
python-sirius ${RSYNC_LOCAL}/src/client.py

