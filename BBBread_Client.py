#!/usr/bin/python-sirius

import time
import sys

# sys.path.insert(0, '/root/bbb-function')

# from src.scripts.BBBread.BBBread import RedisClient, update_local_db
from BBBread import RedisClient, update_local_db

# TODO: commutable server


update_local_db()
teste = RedisClient()
while True:
    time.sleep(10)

