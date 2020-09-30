#!/usr/bin/python-sirius

from BBBread import RedisServer
from time import sleep

CONNECTED = 0
DISCONNECTED = 1
MOVED = 2

server = RedisServer()
# TODO: find a way to verify if new dhcp hash exist
while True:
    try:
        sleep(1)
        bbb_list = server.list_connected()
        for bbb in bbb_list:
            bbb_state = server.bbb_state(bbb)
    except AttributeError:
        continue

