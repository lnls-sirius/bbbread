PREFIX ?= /usr/local

BREAD_SERVICE_NAME = bbbread
BREAD_SRC_SERVICE_FILE = ${BREAD_SERVICE_NAME}.service

SERVICE_FILE_DEST = /etc/systemd/system

.PHONY: all install uninstall dependencies clean

all:

install:
	# Services
	cp --preserve=mode ${BREAD_SRC_SERVICE_FILE} ${SERVICE_FILE_DEST}

	pip3.6 install redis

	systemctl daemon-reload

	systemctl start ${BREAD_SERVICE_NAME}
	systemctl enable ${BREAD_SERVICE_NAME}

uninstall:
	systemctl stop ${BREAD_SERVICE_NAME}

	rm -f ${SERVICE_FILE_DEST}/${BREAD_SRC_SERVICE_FILE}

	systemctl daemon-reload

clean:
	find . -name '*.pyc' -exec rm --force {} +
	find . -name '*.pyo' -exec rm --force {} +
	find . -name '*~'    -exec rm --force {} +
	find . -name '__pycache__'  -exec rm -rd --force {} +

