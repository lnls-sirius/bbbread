"""
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
"""

SERVER_LIST = ["127.0.0.1"]

CONFIG_PATH = "/var/tmp/bbb.bin"
LOG_PATH_SERVER = "bbbread.log"
LOG_PATH_BBB = "/var/log/bbbread.log"


class Command:
    """List of available commands"""

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
