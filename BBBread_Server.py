#!/usr/bin/python-sirius

from BBBread import RedisServer
from time import sleep
import redis
import traceback

CONNECTED = 0
DISCONNECTED = 1
MOVED = 2

server = RedisServer()

while True:
    try:
        sleep(20)
        bbb_list = server.list_connected()
        for bbb in bbb_list:
            bbb_state = server.bbb_state(bbb)
    except (redis.exceptions.TimeoutError, redis.exceptions.ConnectionError):
        print("Timeout")
        continue
    except AttributeError:
        traceback.print_exc()
        continue
