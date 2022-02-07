#!/usr/bin/python-sirius

from BBBread import RedisServer
from time import sleep
import redis
import traceback

server = RedisServer()

while True:
    try:
        sleep(20)
        for bbb in server.list_connected():
            server.bbb_state(bbb)
    except (redis.exceptions.TimeoutError, redis.exceptions.ConnectionError):
        print("Timeout")
        continue
    except AttributeError:
        traceback.print_exc()
        continue
