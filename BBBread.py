import logging
import os
import subprocess
import sys
import threading
import time
import socket
from logging.handlers import RotatingFileHandler

import redis

SERVER_LIST = [
    "10.0.38.59",
    "10.0.38.46",
    "10.0.38.42",
    "10.128.153.81",
    "10.128.153.82",
    "10.128.153.83",
    "10.128.153.84",
    "10.128.153.85",
    "10.128.153.86",
    "10.128.153.87",
    "10.128.153.88",
]

CONFIG_PATH = "/var/tmp/bbb.bin"
LOG_PATH_SERVER = "bbbread.log"
LOG_PATH_BBB = "/var/log/bbbread.log"

# Verifies if device is a BBB
if "armv7" in subprocess.check_output(["uname", "-a"]).decode():
    sys.path.insert(0, "/root/bbb-function/src/scripts")
    from bbb import BBB

    try:
        node = BBB(path=CONFIG_PATH, logfile=LOG_PATH_BBB)
    except ModuleNotFoundError:
        CONFIG_PATH = "/var/tmp/nonexistentpath.bin"
        node = BBB(path=CONFIG_PATH, logfile=LOG_PATH_BBB)  # Forces BBBread to use default configurations


class NoRedisServerError(Exception):
    pass


def update_local_db(local_db=None):
    """Updates local redis database with device.json info"""

    if not local_db:
        local_db = redis.StrictRedis(host="127.0.0.1", port=6379, socket_timeout=2)

    info = node.get_current_config()["n"]
    info["ping_time"] = str(time.time())

    local_db.hmset("device", info)
    return info["ip_address"], info["name"]


class Command:
    (
        PING,
        REBOOT,
        EXIT,
        END,
        TYPE,
        APPEND_TYPE,
        REMOVE_TYPE,
        NODE,
        APPEND_NODE,
        REMOVE_NODE,
        SWITCH,
        GET_TYPES,
        GET_UNREG_NODES_SECTOR,
        GET_REG_NODES_SECTOR,
        GET_REG_NODE_BY_IP,
        OK,
        FAILURE,
        SET_IP,
        SET_HOSTNAME,
        SET_NAMESERVERS,
        RESTART_SERVICE,
        STOP_SERVICE,
    ) = range(22)


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

    def get_logs(self, hashname=None):
        if hashname:
            return [
                [key.decode("utf-8"), value.decode("utf-8")] for key, value in self.local_db.hgetall(hashname).items()
            ]
        return [name.decode("utf-8") for name in self.local_db.keys("BBB:*:Logs")]

    def list_connected(self, ip="", hostname=""):
        """Returns a list of all BeagleBone Blacks connected to Redis database
        If IP or hostname is specified lists only the ones with the exact specified parameter"""
        command_instances = []
        log_instances = []
        all_connected = []

        if ip and hostname:
            all_instances = self.local_db.keys("BBB:{}:{}".format(ip, hostname))
        elif ip and not hostname:
            all_instances = self.local_db.keys("BBB:{}:*".format(ip))
            command_instances = self.local_db.keys("BBB:{}:*:Command".format(ip))
            log_instances = self.local_db.keys("BBB:{}:*:Logs".format(ip))
        elif not ip and hostname:
            all_instances = self.local_db.keys("BBB:*:{}".format(hostname))
        else:
            all_instances = self.local_db.keys("BBB:*")
            command_instances = self.local_db.keys("BBB:*:Command")
            log_instances = self.local_db.keys("BBB:*:Logs")

        for node in all_instances:
            if node in command_instances or node in log_instances:
                continue
            all_connected.append(node.decode())
        return all_connected

    def get_node(self, hashname):
        """Returns a BBB info, if an error occurs returns False"""
        try:
            info = self.local_db.hgetall(hashname)
            return info
        except Exception as e:
            self.logger.error("Failed to return nodes info due to error:\n{}".format(e))
            return False

    def send_command(self, ip: str, command, hostname="", override=False):
        """Sends a command to a BeagleBone Black
        Returns False if it fails to send command"""
        try:
            bbb_hashname = self.list_connected(ip, hostname)

            if override and hostname:
                bbb_hashname = ["BBB:{}:{}".format(ip, hostname)]
            if len(bbb_hashname) == 1:
                bbb_state = self.local_db.hget(bbb_hashname[0], "state_string").decode()
                if bbb_state != "Connected":
                    self.logger.error("failed to send command, node is inactive")
                    return False
                bbb_command_listname = "{}:Command".format(bbb_hashname[0])
                check = self.local_db.rpush(bbb_command_listname, command)
                return bool(check)
            if len(bbb_hashname) < 1:
                self.logger.error("no node found with the specified IP and hostname:" + ip + hostname)
            else:
                self.logger.error("two or more nodes found with the specified ip, please specify a hostname")
            return False
        except Exception as e:
            self.logger.error("A fatal error occurred while sending the command:\n{}".format(e))
            return False

    def bbb_state(self, hashname: str):
        """Verifies if node is active. Ping time inferior to 15 seconds
        Zero if active node, One if disconnected and Two if moved to other hash"""
        now = time.time()

        last_ping = float(self.local_db.hget(hashname, "ping_time").decode())
        time_since_ping = now - last_ping
        node_state = self.local_db.hget(hashname, "state_string").decode()
        logs = [
            x[1] for x in sorted(self.local_db.hgetall(hashname + ":Logs").items(), key=lambda x: x[0], reverse=True)
        ]
        if node_state[:3] == "BBB":
            return 2

        if time_since_ping >= 15:
            if node_state != "Disconnected":
                self.local_db.hset(hashname, "state_string", "Disconnected")
                if logs:
                    if "Disconnected" not in logs[0].decode():
                        self.log_remote(f"{hashname}:Logs", f"Disconnected (timestamp {last_ping})", int(now) - 10800)
                        self.local_db.sadd("DisconnectedWarn", hashname)
                else:
                    self.log_remote(f"{hashname}:Logs", f"Disconnected (timestamp {last_ping})", int(now) - 10800)
                    self.local_db.sadd("DisconnectedWarn", hashname)

            """
            else:
                addr = ":".join(hashname.split(":")[:2])
                if addr != "BBB:0.0.0.0":
                    homonyms = [h.decode() for h in self.local_db.keys(addr+"*") if b"Logs" not in h]
                    if len(homonyms) > 1:
                        for h in homonyms:
                            if self.local_db.hget(h, "state_string").decode() == "Connected":
                                pass"""
            return 1
        if logs:
            known_status = logs[0].decode()
            if known_status != "Reconnected" and "Disconnected" in known_status:
                self.log_remote(hashname + ":Logs", "Reconnected", int(now) - 10800)
        return 0

    def delete_bbb(self, hashname: str):
        """Removes a hash from redis database"""
        self.local_db.delete(hashname)

    def change_hostname(self, ip: str, new_hostname: str, current_hostname="", override=False):
        """Changes a BeagleBone Black hostname
        Returns false if an error occurs while sending the command or BBB isn't connected to Redis"""
        command = "{};{}".format(Command.SET_HOSTNAME, new_hostname)
        check = self.send_command(ip, command, current_hostname, override)
        # If command is sent successfully logs hostname change
        if check:
            self.logger.info("{} NEW HOSTNAME - {}".format(ip, new_hostname))
        return check

    def change_nameservers(self, ip: str, nameserver_1: str, nameserver_2: str, hostname="", override=False):
        """Changes a BeagleBone Black nameservers
        Returns false if an error occurs while sending the command or BBB isn't connected to Redis"""
        command = "{};{};{}".format(Command.SET_NAMESERVERS, nameserver_1, nameserver_2)
        check = self.send_command(ip, command, hostname, override)
        # If command is sent successfully logs hostname change
        if check:
            self.logger.debug("{} NEW NAMESERVERS - {}  {}".format(ip, nameserver_1, nameserver_2))
        return check

    def change_ip(
        self,
        current_ip: str,
        ip_type: str,
        hostname="",
        new_ip="",
        new_mask="",
        new_gateway="",
        override=False,
    ):
        """Changes a BeagleBone Black IP address (DHCP or manual)
        Returns false if an error occurs while sending the command or BBB isn't connected to Redis"""
        command = "{};{}".format(Command.SET_IP, ip_type)
        if ip_type == "manual":
            # Verifies if new_ip is possible
            check_integrity = new_ip.split(".")
            if len(check_integrity) != 4:
                self.logger.warning("{} NEW IP NOT FORMATTED CORRECTLY")
                return False
            # Verifies if specified IP is available
            ip_available = os.system('ping "-c" 1 -w2 "10.0.6.6" > /dev/null 2>&1')
            if ip_available:
                command += ";{};{};{}".format(new_ip, new_mask, new_gateway)
            else:
                self.logger.warning("{} IP NOT AVAILABLE")
                return False
        check = self.send_command(current_ip, command, hostname, override)
        if check:
            self.logger.info(
                "{} NEW IP - type:{} - new ip: {} - mask: {} - gateway: {}".format(
                    current_ip, ip_type, new_ip, new_mask, new_gateway
                )
            )
        return check

    def reboot_node(self, ip: str, hostname="", override=False):
        """Reboots the specified BeagleBone Black
        Returns false if an error occurs while sending the command or BBB isn't connected to Redis"""
        check = self.send_command(ip, Command.REBOOT, hostname, override)
        if check:
            self.logger.info("{} REBOOT".format(ip))
        return check

    def stop_service(self, ip: str, service: str, hostname="", override=False):
        """Stops the specified service on the given BBB"""
        command = "{};{}".format(Command.STOP_SERVICE, service)
        check = self.send_command(ip, command, hostname, override)
        if check:
            self.logger.info("{} SERVICE STOPPED - {}".format(ip, service))
        return check

    def restart_service(self, ip: str, service: str, hostname="", override=False):
        """Restarts the specified service on the given BBB"""
        command = "{};{}".format(Command.RESTART_SERVICE, service)
        check = self.send_command(ip, command, hostname, override)
        if check:
            self.logger.info("{} SERVICE RESTARTED - {}".format(ip, service))
        return check

    def log_remote(self, bbb, message, date):
        self.local_db.hset(bbb, date, message)

    def log_cleanup(self):
        age_limit = time.time() - 904000

        for hash in self.local_db.keys("BBB:*:Logs"):
            for field in self.local_db.hgetall(hash):
                if float(field) < age_limit:
                    self.local_db.hdel(hash, field)

        time.sleep(7200)


class RedisClient:
    """
    A class to write BBB information on a REDIS server
    """

    def __init__(
        self,
        path=CONFIG_PATH,
        log_path=LOG_PATH_BBB,
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

        update_local_db(self.local_db)
        self.bbb_ip, self.bbb_hostname = self.local_db.hmget("device", "ip_address", "name")
        self.bbb_ip = self.bbb_ip.decode()
        self.bbb_hostname = self.bbb_hostname.decode()
        self.hashname = f"BBB:{self.bbb_ip}:{self.bbb_hostname}"
        self.command_listname = f"{self.hashname}:Command"
        self.l_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

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

    def find_active(self):
        while True:
            for server in SERVER_LIST:
                try:
                    remote_db = redis.StrictRedis(host=server, port=6379, socket_timeout=4)
                    remote_db.ping()
                    self.logger.info(f"Connected to {server} Redis Server")
                    return remote_db
                except redis.exceptions.ConnectionError:
                    self.logger.warning(f"{server} Redis server is disconnected")
                except redis.exceptions.ResponseError:
                    self.logger.warning(f"Could not connect to {server}, a response error has ocurred")
                    time.sleep(30)
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
                self.force_update()
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
                if self.remote_db.lrange(self.command_listname, 0, 1):
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

            elif command[0] >= Command.STOP_SERVICE and len(command) == 2:
                action = "stop" if command[0] == Command.STOP_SERVICE else "restart"
                service_name = command[1]
                self.log_remote(f"{service_name} service {action}", now, self.logger.info)
                subprocess.check_output(["systemctl", action, service_name])

    def log_remote(self, message, date, log_level):
        try:
            log_level(message)
            self.remote_db.hset(self.logs_name, date, message)
        except Exception as e:
            self.logger.error(f"Failed to send remote log information: {e}")

    def force_update(self):
        """Updates local and remote database"""
        update_local_db(self.local_db)

        self.l_socket.connect(('10.255.255.255', 1))
        new_ip = self.l_socket.getsockname()[0]
        new_hostname = socket.gethostname()

        info = self.local_db.hgetall("device")
        # Formats remote hash name as "BBB:IP_ADDRESS"
        if new_ip != self.bbb_ip or new_hostname != self.bbb_hostname:
            self.hashname = f"BBB:{new_ip}:{new_hostname}"
            old_hashname = f"BBB:{self.bbb_ip}:{self.bbb_hostname}"
            old_info = info.copy()
            old_info[b"state_string"] = self.hashname
            old_info[b"name"] = self.bbb_hostname
            old_info[b"ip_address"] = self.bbb_ip
            if self.remote_db.keys(f"{old_hashname}:Command"):
                self.remote_db.rename(f"{old_hashname}:Command", f"{self.hashname}:Command")
            if self.remote_db.keys(f"{old_hashname}:Logs"):
                self.remote_db.rename(f"{old_hashname}:Logs", f"{self.hashname}:Logs")

            self.logger.info(
                f"old ip: {self.bbb_ip}, new ip: {new_ip}, old hostname: {self.bbb_hostname}, new hostname: {new_hostname}"  # noqa: E501
            )
            self.remote_db.hmset(old_hashname, old_info)
            self.listening = True

            self.bbb_ip, self.bbb_hostname = (new_ip, new_hostname)
            self.logs_name = f"{self.hashname}:Logs"

        # Updates remote hash
        self.remote_db.hmset(self.hashname, info)


if __name__ == "__main__":
    sys.exit()

