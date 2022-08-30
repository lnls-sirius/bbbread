#!/usr/bin/python-sirius

from time import sleep
import traceback
import logging
import sys
import threading
import time
from consts import SERVER_LIST

import redis


class NoRedisServerError(Exception):
    """General error for no available servers"""


class RedisServer:
    """Runs on Control System's Server"""

    def __init__(self):
        # Configuring logging
        self.logger = logging.getLogger("bbbreadServer")

        formatter = logging.Formatter("%(levelname)s:%(asctime)s:%(name)s:%(message)s")
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(formatter)

        self.logger.setLevel(logging.DEBUG)
        self.logger.addHandler(handler)

        self.logger.debug("Starting up BBBread Server")

        connected = False
        for server in SERVER_LIST[:3]:
            self.local_db = redis.StrictRedis(host=server, port=6379, socket_timeout=3)
            try:
                self.local_db.ping()
                self.logger.debug("Connected to {} Redis Server".format(server))
                connected = True
                break
            except redis.exceptions.ConnectionError:
                self.logger.debug("{} Redis server is unavailable. Trying out next server".format(server))
                continue

        if not connected:
            raise NoRedisServerError

        self.log_thread = threading.Thread(target=self.log_cleanup, daemon=True)
        self.log_thread.start()

    def list_connected(self) -> list:
        """Returns a list of all BeagleBone Blacks connected to Redis database"""
        return [
            x.decode() for x in self.local_db.keys("BBB:*") if not any(s in x.decode() for s in ["Logs", "Command"])
        ]

    def bbb_state(self, hashname: str) -> int:
        """Verifies if node is active. Ping time inferior to 15 seconds
        Zero if active node, One if disconnected and Two if moved to other hash"""
        node_state = self.local_db.hget(hashname, "state_string")
        if node_state:
            node_state = node_state.decode()
        else:
            self.local_db.hset(hashname, "state_string", "Connected")
            return 0

        if node_state[:5] == "Moved":
            return 2

        if node_state[:3] == "BBB":
            self.local_db.hset(hashname, "state_string", f"Moved - {node_state}")
            return 2

        logs = [
            x[1] for x in sorted(self.local_db.hgetall(hashname + ":Logs").items(), key=lambda x: x[0], reverse=True)
        ]

        now = int(time.time())

        if self.local_db.hdel(hashname, "heartbeat"):
            self.local_db.hset(hashname, mapping={"state_string": "Connected", "ping_time": now})
            if (logs and logs[0].decode() != "Reconnected") and "BBB-SIMAR-Mini" not in hashname:
                self.log_remote(f"{hashname}:Logs", "Reconnected", now)
            return 0

        if (not logs or "Disconnected" != logs[0].decode()) and "BBB-SIMAR-Mini" not in hashname:
            self.log_remote(f"{hashname}:Logs", "Disconnected", now)
            self.local_db.sadd("DisconnectedWarn", hashname)

        self.local_db.hset(hashname, "state_string", "Disconnected")
        return 1

    def log_remote(self, bbb: str, message: str, date: float):
        """Pushes logs to remote server"""
        self.local_db.hset(bbb, date, message)

    def log_cleanup(self):
        """Cleans up old logs"""
        age_limit = time.time() - 904000

        for log_hash in self.local_db.keys("BBB:*:Logs"):
            for field in self.local_db.hgetall(log_hash):
                if float(field) < age_limit:
                    self.local_db.hdel(log_hash, field)

        time.sleep(7200)


if __name__ == "__main__":
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
