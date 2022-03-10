#!/usr/bin/python-sirius

import logging
import subprocess
import sys
import threading
import time
import socket
from logging.handlers import RotatingFileHandler
from typing import Callable
import redis

from consts import CONFIG_PATH, LOG_PATH_BBB, Command, SERVER_LIST

sys.path.insert(0, "/root/bbb-function/src/scripts")
from bbb import BBB  # noqa: E402

try:
    node = BBB(path=CONFIG_PATH, logfile=LOG_PATH_BBB)
except ModuleNotFoundError:
    CONFIG_PATH = "/var/tmp/nonexistentpath.bin"
    node = BBB(path=CONFIG_PATH, logfile=LOG_PATH_BBB)  # Forces BBBread to use default configurations


class RedisClient:
    """
    A class to write BBB information on a REDIS server
    """

    def __init__(
        self,
        path: str = CONFIG_PATH,
        log_path: str = LOG_PATH_BBB,
    ):
        # Configuring logging
        self.logger = logging.getLogger("bbbread")
        self.logger.setLevel(logging.INFO)
        formatter = logging.Formatter("%(levelname)s:%(asctime)s:%(name)s:%(message)s")
        file_handler = RotatingFileHandler(log_path, maxBytes=15000000, backupCount=5)
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)

        self.logger.info("Starting BBBread up")

        # Defining local and remote database
        self.local_db = redis.StrictRedis(host="127.0.0.1", port=6379, socket_timeout=4)

        self.logger.info("Searching for active database")
        self.remote_db = self.find_active()

        # Defining BBB object and formatting remote hash name as "BBB:IP_ADDRESS:HOSTNAME"
        if CONFIG_PATH != path or LOG_PATH_BBB != log_path:
            self.bbb = BBB(path=path, logfile=log_path)
        else:
            self.bbb = node

        for service in subprocess.check_output(["connmanctl", "services"]).decode().split("\n")[:-1]:
            if "Wired" in service:
                self.nw_service = service.split(16 * " ")[1]
                break
            else:
                self.nw_service = None

        if not self.nw_service:
            raise ConnectionError

        self.bbb_ip_type, self.bbb_ip, self.bbb_nameservers = self.get_network_specs()
        self.bbb_hostname = socket.gethostname()

        self.local_db.hmset(
            "device",
            {
                "sector": self.bbb.node.sector,
                "details": self.bbb.node.details,
                "state_string": self.bbb.node.state_string,
                "state": self.bbb.node.state,
                "ip_type": self.bbb_ip_type,
                "ip_address": self.bbb_ip,
                "nameservers": self.bbb_nameservers,
            },
        )

        self.hashname = f"BBB:{self.bbb_ip}:{self.bbb_hostname}"
        self.command_listname = f"{self.hashname}:Command"
        self.remote_db.hmset(self.hashname, self.local_db.hgetall("device"))

        # Pinging thread
        self.ping_thread = threading.Thread(target=self.ping_remote, daemon=True)
        self.ping_thread.start()
        self.logger.info("Pinging thread started")

        # Listening thread
        self.listening = True
        self.logger.info("Listening thread started")
        self.logger.info("BBBread startup completed")
        self.logs_name = f"{self.hashname}:Logs"

        self.listen()

    def get_network_specs(self):
        nameservers = "0.0.0.0"
        ip_type = "0.0.0.0"
        ip_address = "0.0.0.0"

        command_out = subprocess.check_output(["connmanctl", "services", self.nw_service]).decode().split("\n")[:-1]

        if command_out:
            for line in command_out:
                # Address line
                if "IPv4 = " in line:
                    try:
                        ip_type = line[18 : line.index(",")]
                        ip_address = line[line.index("Address=") + 8 : line.index("Netmask") - 2]
                    except Exception:
                        continue
                # Nameservers line
                if "Nameservers = " in line:
                    try:
                        nameservers = line[line.index("=") + 4 : -2]
                    except Exception:
                        continue
        return ip_type, ip_address, nameservers

    def find_active(self):
        """Find available server and replace old one"""
        while True:
            for server in SERVER_LIST:
                try:
                    remote_db = redis.StrictRedis(host=server, port=6379, socket_timeout=4)
                    remote_db.ping()
                    self.logger.info(f"Connected to {server} Redis Server")
                    return remote_db
                except redis.exceptions.ConnectionError:
                    self.logger.warning(f"{server} Redis server is disconnected")
                except Exception as e:
                    self.logger.warning(f"Could not connect to {server}: {e}")
                    time.sleep(50)
                continue

            self.logger.info("Server not found. Retrying to connect in 10 seconds...")
            time.sleep(10)

    def ping_remote(self):
        """Thread that updates remote database every 10s, if pinging is enabled"""
        while True:
            try:
                new_ip_type, new_ip, new_nameservers = self.get_network_specs()
                new_hostname = socket.gethostname()

                self.remote_db.hset(self.hashname, "heartbeat", 1)
                # Formats remote hash name as "BBB:IP_ADDRESS"
                if (
                    new_ip != self.bbb_ip
                    or new_hostname != self.bbb_hostname
                    or new_ip_type != self.bbb_ip_type
                    or new_nameservers != self.bbb_nameservers
                ):
                    info = self.local_db.hgetall("device")

                    self.hashname = f"BBB:{new_ip}:{new_hostname}"
                    old_hashname = f"BBB:{self.bbb_ip}:{self.bbb_hostname}"

                    old_info = info.copy()
                    old_info.update(
                        {
                            b"state_string": self.hashname,
                            b"name": self.bbb_hostname,
                            b"ip_address": self.bbb_ip,
                            b"ip_type": self.bbb_ip_type,
                            b"nameservers": self.bbb_nameservers,
                        }
                    )

                    try:
                        self.remote_db.rename(f"{old_hashname}:Command", f"{self.hashname}:Command")
                        self.remote_db.rename(f"{old_hashname}:Logs", f"{self.hashname}:Logs")
                    except redis.exceptions.ResponseError:
                        pass

                    self.logger.info(old_info)
                    self.remote_db.hmset(old_hashname, old_info)
                    self.listening = True

                    self.bbb_ip, self.bbb_hostname, self.bbb_ip_type, self.bbb_nameservers = (
                        new_ip,
                        new_hostname,
                        new_ip_type,
                        new_nameservers,
                    )
                    self.logs_name = f"{self.hashname}:Logs"
                    self.command_listname = f"{self.hashname}:Command"

                    info.update(
                        {
                            b"name": new_hostname,
                            b"ip_address": new_ip,
                            b"ip_type": new_ip_type,
                            b"nameservers": new_nameservers,
                        }
                    )

                    self.remote_db.hmset(self.hashname, info)
                time.sleep(10)
            except Exception as e:
                now = int(time.time()) - 10800
                self.log_remote(f"Pinging thread found an exception: {e}", now, self.logger.error)
                time.sleep(10)
                self.find_active()

    def listen(self):
        """Thread to process server's commands"""
        while True:
            time.sleep(3)
            if not self.listening:
                time.sleep(2)
                continue
            if not self.ping_thread.is_alive():
                break

            try:
                if self.remote_db.exists(self.command_listname):
                    now = int(time.time()) - 10800
                    command = self.remote_db.lpop(self.command_listname).decode()
                    command = command.split(";")
                    command[0] = int(command[0])
                else:
                    continue
            except redis.exceptions.TimeoutError:
                self.logger.error("Reconnecting to Redis server")
                time.sleep(1)
                continue
            except ValueError:
                self.logger.error("Failed to convert first part of the command to integer")
                continue
            except Exception as e:
                now = int(time.time()) - 10800
                self.log_remote(f"Listening thread found an exception: {e}", now, self.logger.error)
                time.sleep(3)
                continue

            self.logger.info(f"Command received {command}")
            if command[0] == Command.REBOOT:
                self.log_remote("Reboot command received", now, self.logger.info)
                self.bbb.reboot()

            elif command[0] == Command.SET_HOSTNAME and len(command) == 2:
                new_hostname = command[1]
                self.bbb.update_hostname(new_hostname)
                # Updates variable names
                self.log_remote(f"Hostname changed to {new_hostname}", now, self.logger.info)
                self.listening = False

            elif command[0] == Command.SET_IP:
                ip_type = command[1]
                # Verifies if IP is to be set manually
                if ip_type == "manual" and len(command) == 5:
                    new_ip, new_mask, new_gateway = command[2:]
                    self.bbb.update_ip_address(ip_type, new_ip, new_mask, new_gateway)
                    # Updates variable names
                    info = f"IP manually changed to {new_ip}, netmask {new_mask}, gateway {new_gateway}"
                    self.log_remote(info, now, self.logger.info)
                    self.listening = False

                # Verifies if IP is DHCP
                elif ip_type == "dhcp":
                    self.bbb.update_ip_address(ip_type)
                    # Updates variable names
                    time.sleep(1)
                    self.log_remote("IP changed to DHCP", now, self.logger.info)
                    self.listening = False

            elif command[0] == Command.SET_NAMESERVERS and len(command) == 3:
                nameserver_1, nameserver_2 = command[1:]
                self.log_remote(f"Nameservers changed: {nameserver_1}, {nameserver_2}", now, self.logger.info)
                self.bbb.update_nameservers(nameserver_1, nameserver_2)

            elif command[0] >= Command.RESTART_SERVICE and len(command) == 2:
                action = "stop" if command[0] == Command.STOP_SERVICE else "restart"
                service_name = command[1]
                self.log_remote(f"{service_name} service {action}", now, self.logger.info)
                subprocess.check_output(["systemctl", action, service_name])

    def log_remote(self, message: str, date: float, log_level: Callable):
        """Pushes logs to remote server"""
        try:
            log_level(message)
            self.remote_db.hset(self.logs_name, date, message)
        except Exception as e:
            self.logger.error(f"Failed to send remote log information: {e}")


if __name__ == "__main__":
    RedisClient()