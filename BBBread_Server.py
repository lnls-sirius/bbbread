#!/usr/bin/python-sirius

import sys

sys.path.insert(0, PATH_TO_BBBREAD_MODULE)
from BBBread import RedisServer


CONNECTED = 0
DISCONNECTED = 1
MOVED = 2

server = RedisServer()
# TODO: find a way to verify if new dhcp hash exist
while True:
    try:
        bbb_list = server.list_connected()
        for bbb in bbb_list:
            bbb_state = server.bbb_state(bbb)
    except AttributeError:
        continue

