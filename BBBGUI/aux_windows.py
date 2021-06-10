from datetime import datetime
from time import localtime, strftime
from PyQt5 import QtCore, QtWidgets, uic

from BBBGUI.aux_threads import UpdateLogsThread, TableModel
from BBBGUI.consts import room_names

Ui_MainWindow_config, QtBaseClass_config = uic.loadUiType("BBBGUI/ui_files/configBBB.ui")
Ui_MainWindow_info, QtBaseClass_info = uic.loadUiType("BBBGUI/ui_files/infoBBB.ui")
Ui_MainWindow_logs, QtBaseClass_logs = uic.loadUiType("BBBGUI/ui_files/logsBBB.ui")


class BBBConfig(QtWidgets.QWidget, Ui_MainWindow_config):
    """BBB configuration display"""

    def __init__(self, hashname, info, server):
        QtWidgets.QWidget.__init__(self)
        Ui_MainWindow_config.__init__(self)
        self.setupUi(self)

        self.server = server

        self.hashname = hashname
        self.hostname = info[b"name"].decode()
        self.ip_address = info[b"ip_address"].decode()
        ip = self.ip_address.split(".")
        self.ip_suffix = ip[-1]
        self.bbb_sector = info[b"sector"].decode()

        self.currenthostnamevalueLabel.setText(self.hostname)
        self.currentipvalueLabel.setText(self.ip_address)

        self.ip_prefix = ".".join(ip[:-1]) + "."

        if ip[1] != "128":
            self.ipComboBox.setEnabled(False)
            self.newipSpinBox.setEnabled(False)
            self.nameserver1Edit.setEnabled(False)
            self.nameserver2Edit.setEnabled(False)
            self.keepipBox.setChecked(True)
            self.keepipBox.setEnabled(False)
            self.keepnameserversBox.setChecked(True)
            self.keepnameserversBox.setEnabled(False)

        self.newipLabel.setText(self.ip_prefix)
        self.ipComboBox.currentIndexChanged.connect(self.disable_spinbox)

        self.applyButton.clicked.connect(self.apply_changes)

    def disable_spinbox(self):
        if self.ipComboBox.currentText() == "MANUAL":
            self.newipSpinBox.setEnabled(True)
        else:
            self.newipSpinBox.setEnabled(False)

    def apply_changes(self):
        # Before asking for confirmation annotates configuration parameters in order to prevent delay bugs
        self.applyButton.setEnabled(False)
        hostname_changed = False
        # DNS
        keep_dns = self.keepnameserversBox.isChecked()
        nameserver_1 = self.nameserver1Edit.text()
        nameserver_2 = self.nameserver2Edit.text()

        # Hostname
        keep_hostname = self.keephostnameBox.isChecked()
        new_hostname = self.hostnameEdit.text()

        # IP
        keep_ip = self.keepipBox.isChecked()
        ip_type = self.ipComboBox.currentText()
        new_ip_suffix = str(self.newipSpinBox.value())

        # Bools to verify if command was sent successfully
        ip_sent = False

        # Confirmation screen
        confirmation = QtWidgets.QMessageBox.question(
            self,
            "Confirmation",
            "Apply changes?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
        )
        if confirmation == QtWidgets.QMessageBox.Yes:
            # Nameservers configuration
            if not keep_dns and nameserver_1 and nameserver_2:
                dns_sent = self.server.change_nameservers(self.ip_address, nameserver_1, nameserver_2, self.hostname)
            else:
                dns_sent = True
            # Hostname configuration
            if not keep_hostname and new_hostname:
                name_sent = self.server.change_hostname(self.ip_address, new_hostname, self.hostname)
                hostname_changed = name_sent
            else:
                name_sent = True
            if not keep_ip:
                if ip_type in ["DHCP", "dhcp"]:
                    if hostname_changed and name_sent:
                        ip_sent = self.server.change_ip(self.ip_address, "dhcp", self.hostname, override=True)
                        self.hostname = new_hostname
                    else:
                        ip_sent = self.server.change_ip(self.ip_address, "dhcp", self.hostname)
                elif new_ip_suffix not in [self.ip_suffix, "0", "1", "2"]:
                    new_ip = self.ip_prefix + new_ip_suffix
                    if hostname_changed and name_sent:
                        ip_sent = self.server.change_ip(
                            self.ip_address,
                            "manual",
                            self.hostname,
                            new_ip,
                            "255.255.255.0",
                            self.ip_prefix + "1",
                            override=True,
                        )
                        self.hostname = new_hostname
                    else:
                        ip_sent = self.server.change_ip(
                            self.ip_address,
                            "manual",
                            self.hostname,
                            new_ip,
                            "255.255.255.0",
                            self.ip_prefix + "1",
                        )
            else:
                ip_sent = True
            if ip_sent and dns_sent and name_sent:
                QtWidgets.QMessageBox.information(
                    self,
                    "Success",
                    "Node configured successfully",
                    QtWidgets.QMessageBox.Close,
                )
            if not name_sent:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Error",
                    "Error in Hostname configuration",
                    QtWidgets.QMessageBox.Abort,
                )
            if not dns_sent:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Error",
                    "Error in Nameservers configuration",
                    QtWidgets.QMessageBox.Abort,
                )
            if not ip_sent:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Error",
                    "Error in IP configuration",
                    QtWidgets.QMessageBox.Abort,
                )
            self.close()
        else:
            self.applyButton.setEnabled(True)


class BBBInfo(QtWidgets.QWidget, Ui_MainWindow_info):
    """BBB info display"""

    def __init__(self, info):
        QtWidgets.QWidget.__init__(self)
        Ui_MainWindow_info.__init__(self)
        self.setupUi(self)

        if info:
            node_ip = info[b"ip_address"].decode()
            node_ip_type = info[b"ip_type"].decode()
            node_name = info[b"name"].decode()
            node_sector = info[b"sector"].decode()
            ping_time = float(info[b"ping_time"].decode())
            for room, number in room_names.items():
                if number == node_sector:
                    node_sector = room
                    break
            node_state = info[b"state_string"].decode()
            node_details = info[b"details"].decode()
            node_config_time = info[b"config_time"].decode()
            nameservers = info[b"nameservers"].decode()
            self.nameLabel.setText(node_name)
            self.ipLabel.setText(node_ip)
            self.stateLabel.setText(node_state)
            self.iptypeLabel.setText(node_ip_type)
            self.configtimevalueLabel.setText(node_config_time)
            self.equipmentvalueLabel.setText(node_details)
            self.nameserversvalueLabel.setText(nameservers)
            self.sectorvalueLabel.setText(node_sector)
            self.lastseenvalueLabel.setText(strftime("%a, %d %b %Y   %H:%M:%S", localtime(ping_time)))


class BBBLogs(QtWidgets.QWidget, Ui_MainWindow_logs):
    # BBB Logs Display
    def __init__(self, server, hashname):
        QtWidgets.QWidget.__init__(self)
        Ui_MainWindow_logs.__init__(self)
        self.setupUi(self)

        self.logs_thread = UpdateLogsThread(server, hashname)
        self.logs_thread.finished.connect(self.update_table)

        self.model = TableModel([[]])
        self.logsTable.setModel(self.model)

        self.fromTimeEdit.dateTimeChanged.connect(self.update_filters)
        self.toTimeEdit.dateTimeChanged.connect(self.update_filters)

        self.filterEdit.textChanged.connect(self.update_filters)

        self.autoUpdate_timer = QtCore.QTimer(self)
        self.autoUpdate_timer.timeout.connect(self.logs_thread.start)
        self.autoUpdate_timer.setSingleShot(False)
        self.autoUpdate_timer.start(1000)

    def update_table(self, logs, update=True):
        """ Sets table values and converts timestamp, deep copies logs """
        if update:
            self.data = logs
            self.update_filters()
            return

        data = [
            [
                datetime.utcfromtimestamp(int(_log[0])).strftime("%d/%m/%Y %H:%M:%S"),
                _log[1],
            ]
            for _log in logs
        ]

        self.model.set_data(data)

    def update_filters(self):
        """ Updates log table with filters set by user """
        if not self.data:
            return

        search = self.filterEdit.text()

        max_date = self.toTimeEdit.dateTime().toPyDateTime().timestamp()
        min_date = self.fromTimeEdit.dateTime().toPyDateTime().timestamp()

        if min_date > max_date:
            self.fromTimeEdit.setDateTime(self.toTimeEdit.dateTime())

        if min_date == max_date:
            self.update_table(self.data)

        length = len(self.data)
        min_index, max_index = length, 0

        # Compares Unix timestamp for logs and filter, stops when a log satisfies the filter
        for index, r in enumerate(self.data):
            if int(r[0]) < min_date:
                min_index = index
                break

        for index, r in enumerate(self.data[::-1]):
            if int(r[0]) > max_date:
                max_index = length - index
                break

        data = self.data[max_index:min_index]

        # If the user has set a string filter, all logs without a mention of the filter are removed
        if search:
            data = [r for r in data if search in r[1]]

        self.update_table(data, update=False)
