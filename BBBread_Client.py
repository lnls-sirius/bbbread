#!/usr/bin/python-sirius

import time

from BBBread import RedisClient, update_local_db

# TODO: commutable server


update_local_db()
client = RedisClient()
while True:
    time.sleep(10)
