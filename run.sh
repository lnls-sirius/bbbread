#!/bin/bash
set +x
export BREAD_BASE=/root/bbbread

echo Synchronizing bbbread files
rsync -a --delete-after 10.128.255.5::bbbread BREAD_BASE


echo Run script
python-sirius ${BREAD_BASE}/BBBread_Client.py
