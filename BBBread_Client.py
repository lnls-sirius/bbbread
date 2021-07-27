#!/usr/bin/python-sirius

from time import sleep
from BBBread import RedisClient, update_local_db

# TODO: commutable server

RedisClient()
while True:
    sleep(1000)
