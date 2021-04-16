import sys
from datetime import datetime
from time import sleep
from PyQt5 import QtCore, QtGui, QtWidgets, uic

from BBBread import RedisServer
from BBBGUI.aux_windows import BBBConfig, BBBInfo, BBBLogs
from BBBGUI.aux_threads import UpdateLogsThread, UpdateNodesThread, TableModel
from BBBGUI.consts import BASIC_TAB, ADVANCED_TAB, SERVICE_TAB, LOGS_TAB, COLORS, room_names

Ui_MainWindow, QtBaseClass = uic.loadUiType("BBBGUI/ui_files/monitor.ui")


class BBBreadMainWindow(QtWidgets.QWidget, Ui_MainWindow):
    """BeagleBone Black Redis Activity Display"""

    def __init__(self):
        QtWidgets.QWidget.__init__(self)
        Ui_MainWindow.__init__(self)
        self.setupUi(self)

        # Configures redis Server
        self.server = RedisServer()

        # Table models
        self.logs_model = TableModel([[]], all=True)
        self.logsTable.setModel(self.logs_model)

        # Lists
        self.nodes = []
        self.nodes_info = {}
        self.data = None
        self.basicList.setSortingEnabled(True)
        self.basicList.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.advancedList.setSortingEnabled(True)
        self.advancedList.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.serviceList.setSortingEnabled(True)
        self.serviceList.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)

        # List Update Timer
        self.autoUpdate_timer = QtCore.QTimer(self)
        self.autoUpdate_timer.timeout.connect(self.update_nodes)
        self.autoUpdate_timer.setSingleShot(False)
        self.autoUpdate_timer.start(1000)

        # Buttons
        self.basicList.itemSelectionChanged.connect(self.enable_buttons)
        self.advancedList.itemSelectionChanged.connect(self.enable_buttons)
        self.serviceList.itemSelectionChanged.connect(self.enable_buttons)
        self.logsTable.selectionModel().selectionChanged.connect(self.enable_buttons)
        self.tabWidget.currentChanged.connect(self.enable_buttons)
        self.deleteButton.clicked.connect(self.delete_nodes)
        self.rebootButton.clicked.connect(self.reboot_nodes)
        self.configButton.clicked.connect(self.config_node)
        self.infoButton.clicked.connect(self.show_node_info)
        self.applyserviceButton.clicked.connect(self.service_application)
        self.logsButton.clicked.connect(self.display_logs)
        self.threadCheckBox.stateChanged.connect(self.update_filters)
        self.commandsCheckBox.stateChanged.connect(self.update_filters)

        # Threading
        self.nodes_thread = UpdateNodesThread(self.server)
        self.nodes_thread.finished.connect(self.update_node_list)
        self.logs_thread = UpdateLogsThread(self.server)
        self.logs_thread.finished.connect(self.update_table)

        # Log Filters
        self.toTimeEdit.dateTimeChanged.connect(self.update_filters)
        self.fromTimeEdit.dateTimeChanged.connect(self.update_filters)
        self.filterEdit.textChanged.connect(self.update_log_text)

        # Loads loading indicators
        self.loading_icon = QtGui.QPixmap("BBBGUI/img/led-red.png").scaledToHeight(20)
        self.idle_icon = QtGui.QPixmap("BBBGUI/img/led-green.png").scaledToHeight(20)

    def update_nodes(self):
        """Updates list of BBBs shown"""
        # Stores every BBB information
        self.status_icon.setPixmap(self.loading_icon)
        if not self.nodes_thread.isRunning():
            self.nodes_thread.start()

        # Updates logs
        if not self.logs_thread.isRunning():
            self.logs_thread.start()

    def update_log_text(self):
        """ Sets table values and converts timestamp, deep copies logs """
        if self.tabWidget.currentIndex() == LOGS_TAB:
            self.update_filters()

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
            data = [r for r in data if search in r[2] or search in r[1]]

        self.update_table(data, update=False)

    def update_table(self, logs, update=True):
        """Updates content of logs table"""
        if update:
            self.data = logs
            self.update_filters()
            return

        # Formats timestamp in human readable form
        data = [
            [
                datetime.utcfromtimestamp(int(_log[0])).strftime("%d/%m/%Y %H:%M:%S"),
                _log[1],
                _log[2],
            ]
            for _log in logs
        ]

        # Filters out thread statuses and commands (if boxes aren't checked)
        if self.threadCheckBox.isChecked():
            if not self.commandsCheckBox.isChecked():
                data = [
                    _log
                    for _log in data
                    if "connected" in _log[2].lower()
                    or "hostname" in _log[2].lower()
                    or "thread died" in _log[2].lower()
                ]
        else:
            if not self.commandsCheckBox.isChecked():
                data = [_log for _log in data if "connected" in _log[2].lower() or "hostname" in _log[2].lower()]
            data = [_log for _log in data if "thread died" not in _log[2].lower()]

        self.logs_model.set_data(data)

    def update_node_list(self, nodes):
        """Gets updated node list and applies it to all lists"""
        self.nodes, self.nodes_info = nodes
        connected_number = 0

        current_tab = self.tabWidget.currentIndex()

        if current_tab == LOGS_TAB:
            self.connectedLabel.hide()
            self.listedLabel.hide()
        else:
            self.connectedLabel.show()
            self.listedLabel.show()

        if current_tab == ADVANCED_TAB:
            state_filter = {
                "Connected": self.connectedAdvancedBox.isChecked(),
                "Disconnected": self.disconnectedAdvancedBox.isChecked(),
                "Moved": self.movedAdvancedBox.isChecked(),
            }
            list_name = self.advancedList
        elif current_tab == BASIC_TAB:
            state_filter = {
                "Connected": self.connectedCheckBox.isChecked(),
                "Disconnected": self.disconnectedCheckBox.isChecked(),
                "Moved": self.movedCheckBox.isChecked(),
            }
            list_name = self.basicList
        else:
            state_filter = {"Connected": True, "Disconnected": False, "Moved": False}
            list_name = self.serviceList

        # Advanced Tab filters
        ip_filter = {
            "manual": self.staticipAdvancedBox.isChecked(),
            "dhcp": self.dhcpAdvancedBox.isChecked(),
            "Undefined": self.undeterminedAdvancedBox.isChecked(),
            "StaticIP": self.staticipAdvancedBox.isChecked(),
        }
        equipment_filter = {
            "MKS": self.mksAdvancedBox.isChecked(),
            "4UHV": self.uhvAdvancedBox.isChecked(),
            "MBTEMP": self.mbtempAdvancedBox.isChecked(),
            "THERMO": self.thermoAdvancedBox.isChecked(),
            "COUNTING": self.countingpruAdvancedBox.isChecked(),
            "POWER": self.powersupplyAdvancedBox.isChecked(),
            "SPIXCONV": self.spixconvAdvancedBox.isChecked(),
            "RACK_MON": self.rackmonitorAdvancedBox.isChecked(),
            "Searching": self.nodevAdvancedBox.isChecked(),
            "": self.nodevAdvancedBox.isChecked(),
        }
        self.Lock = True
        for node, info in self.nodes_info.items():
            if node not in self.nodes:
                continue
            try:
                # Organizes node information
                node_ip = info[b"ip_address"].decode()
                node_ip_type = info[b"ip_type"].decode()
                node_name = info[b"name"].decode()
                node_sector = info[b"sector"].decode()
                node_state = info[b"state_string"].decode()
                node_details = info[b"details"].decode()
                node_string = "{} - {}".format(node_ip, node_name)
            except Exception:
                continue
            # Increments Connected Number of BBBs if beagle is connected
            if node_state == "Connected":
                connected_number += 1
            # Filters by name and displays node in list
            if (self.filterEdit.text() == "" or self.filterEdit.text() in node_string) and room_names[
                self.roomBox.currentText()
            ] in [node_sector, ""]:
                item = QtWidgets.QListWidgetItem(node_string)
                equipment_len = len(equipment_filter)
                current_equipment = 0
                for equipment, efilter in equipment_filter.items():
                    current_equipment += 1
                    # Filters by equipment if advanced tab is selected
                    if (
                        equipment in node_details and efilter and (ip_filter[node_ip_type] or ip_filter["Undefined"])
                    ) or current_tab in [BASIC_TAB, SERVICE_TAB]:
                        # Verifies if the node is already on the list
                        is_moved = node_state[:3] == "BBB"
                        if node_state in ["Connected", "Disconnected"] or is_moved:
                            if state_filter[node_state] or (state_filter["Moved"] and is_moved):
                                qlistitem = list_name.findItems(node_string, QtCore.Qt.MatchExactly)

                                if not qlistitem:
                                    list_name.addItem(item)
                                    item_index = list_name.row(item)
                                else:
                                    self.remove_faulty(node_string, list_name, False)
                                    item_index = list_name.row(qlistitem[0])

                                # Follows the color conventions set in consts
                                list_name.item(item_index).setBackground(QtGui.QColor(COLORS[node_state[:3]]))
                            else:
                                self.remove_faulty(node_string, list_name)
                        break

                    # If not in any of the selected equipments, removes node
                    if current_equipment == equipment_len:
                        self.remove_faulty(node_string, list_name)

            # Removing duplicates
            self.remove_faulty(node_string, list_name, False)

        self.Lock = False
        # Updates the number of connected and listed nodes
        self.connectedLabel.setText("Connected nodes: {}".format(connected_number))
        self.listedLabel.setText("Listed: {}".format(list_name.count()))
        self.status_icon.setPixmap(self.idle_icon)

    @staticmethod
    def remove_faulty(node_string, list_name: QtWidgets.QListWidget, all_elements=True):
        """Removes duplicates and nodes that shouldn't be on the list"""
        qlistitem = list_name.findItems(node_string, QtCore.Qt.MatchExactly)
        if qlistitem:
            if all_elements:
                for node in qlistitem:
                    list_name.takeItem(list_name.row(node))
            elif len(qlistitem) > 1:
                qlistitem.reverse()
                list_name.takeItem(list_name.row(qlistitem[0]))

    def enable_buttons(self):
        """Enables Buttons when one or more boards are selected"""
        current_tab = self.tabWidget.currentIndex()
        if current_tab == BASIC_TAB:
            selected_items = self.basicList.selectedItems()
        elif current_tab == ADVANCED_TAB:
            selected_items = self.advancedList.selectedItems()
        elif current_tab == SERVICE_TAB:
            selected_items = self.serviceList.selectedItems()
        else:
            selected_items = self.logsTable.selectionModel().selectedRows()
        if selected_items:
            self.rebootButton.setEnabled(True)
            self.deleteButton.setEnabled(True)
            if len(selected_items) == 1:
                self.configButton.setEnabled(True)
                self.infoButton.setEnabled(True)
                self.logsButton.setEnabled(True)
            else:
                self.configButton.setEnabled(False)
                self.infoButton.setEnabled(False)
                self.logsButton.setEnabled(False)
            if current_tab == SERVICE_TAB:
                self.applyserviceButton.setEnabled(True)
            else:
                self.applyserviceButton.setEnabled(False)
        else:
            self.logsButton.setEnabled(False)
            self.rebootButton.setEnabled(False)
            self.deleteButton.setEnabled(False)
            self.configButton.setEnabled(False)
            self.infoButton.setEnabled(False)
            self.applyserviceButton.setEnabled(False)

    def reboot_nodes(self):
        """Reboots the selected nodes"""
        confirmation = QtWidgets.QMessageBox.question(
            self,
            "Confirmation",
            "Are you sure about rebooting these nodes?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
        )
        if confirmation == QtWidgets.QMessageBox.Yes:
            current_list = self.tabWidget.currentIndex()
            if current_list == BASIC_TAB:
                selected_bbbs = self.basicList.selectedItems()
            elif current_list == ADVANCED_TAB:
                selected_bbbs = self.advancedList.selectedItems()
            elif current_list == SERVICE_TAB:
                selected_bbbs = self.serviceList.selectedItems()
            else:
                selected_bbbs = self.logsTable.selectionModel().selectedRows()
            for bbb in selected_bbbs:
                if current_list == LOGS_TAB:
                    bbb_ip, bbb_hostname = bbb.sibling(bbb.row(), 1).data().split(":")
                else:
                    bbb_ip, bbb_hostname = bbb.text().split(" - ")
                self.server.reboot_node(bbb_ip, bbb_hostname)

    def delete_nodes(self):
        """Deletes hashs from Redis Database"""
        confirmation = QtWidgets.QMessageBox.question(
            self,
            "Confirmation",
            "Are you sure about deleting these nodes from Redis Database?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
        )
        if confirmation == QtWidgets.QMessageBox.Yes:
            current_index = self.tabWidget.currentIndex()
            if current_index == BASIC_TAB:
                selected_bbbs = self.basicList.selectedItems()
            elif current_index == ADVANCED_TAB:
                selected_bbbs = self.advancedList.selectedItems()
            elif current_index == SERVICE_TAB:
                selected_bbbs = self.serviceList.selectedItems()
            else:
                selected_bbbs = self.logsTable.selectionModel().selectedRows()
            errors = []
            for bbb in selected_bbbs:
                if current_index == LOGS_TAB:
                    bbb_ip, bbb_hostname = bbb.sibling(bbb.row(), 1).data().split(":")
                else:
                    bbb_ip, bbb_hostname = bbb.text().split(" - ")
                bbb_hashname = "BBB:{}:{}".format(bbb_ip, bbb_hostname)
                try:
                    self.server.delete_bbb(bbb_hashname)
                    while self.Lock:
                        sleep(0.1)
                    self.nodes_info.pop(bbb_hashname)
                    
                    for i in selected_bbbs:
                        self.basicList.takeItem(self.basicList.row(i))
                        self.advancedList.takeItem(self.advancedList.row(i))
                        self.serviceList.takeItem(self.serviceList.row(i))
                        
                except KeyError:
                    errors.append(bbb_hashname)
                    continue
            if errors:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Warning",
                    "The following nodes weren't found in the Redis Database:\n{}".format("\n".join(errors)),
                    QtWidgets.QMessageBox.Abort,
                )

    def display_logs(self):
        """Shows selected BBB's logs"""
        current_list = self.tabWidget.currentIndex()
        if current_list == BASIC_TAB:
            bbb = self.basicList.selectedItems()[0].text()
        elif current_list == ADVANCED_TAB:
            bbb = self.advancedList.selectedItems()[0].text()
        elif current_list == SERVICE_TAB:
            bbb = self.serviceList.selectedItems()[0].text()
        else:
            index = self.logsTable.selectionModel().selectedRows()[0]
            bbb = index.sibling(index.row(), 1).data()
        bbb_ip, bbb_hostname = bbb.split(" - " if current_list != LOGS_TAB else ":")
        hashname = "BBB:{}:{}:Logs".format(bbb_ip, bbb_hostname)
        try:
            self.window = BBBLogs(self.server, hashname)
            self.window.show()
        except KeyError:
            QtWidgets.QMessageBox.warning(
                self,
                "Warning",
                "The node you are trying to get information isn't connected",
                QtWidgets.QMessageBox.Abort,
            )

    def show_node_info(self):
        """Shows selected BBB's information"""
        current_list = self.tabWidget.currentIndex()
        if current_list == BASIC_TAB:
            bbb = self.basicList.selectedItems()[0].text()
        elif current_list == ADVANCED_TAB:
            bbb = self.advancedList.selectedItems()[0].text()
        elif current_list == SERVICE_TAB:
            bbb = self.serviceList.selectedItems()[0].text()
        else:
            index = self.logsTable.selectionModel().selectedRows()[0]
            bbb = index.sibling(index.row(), 1).data()
        bbb_ip, bbb_hostname = bbb.split(" - " if current_list != LOGS_TAB else ":")
        hashname = "BBB:{}:{}".format(bbb_ip, bbb_hostname)
        try:
            info = self.nodes_info[hashname]
            self.window = BBBInfo(info)
            self.window.show()
        except KeyError:
            QtWidgets.QMessageBox.warning(
                self,
                "Warning",
                "The node you are trying to get information isn't connected",
                QtWidgets.QMessageBox.Abort,
            )

    def config_node(self):
        """Opens configuration the selected BBB's configuration window"""
        current_list = self.tabWidget.currentIndex()
        if current_list == BASIC_TAB:
            bbb = self.basicList.selectedItems()[0].text()
        elif current_list == ADVANCED_TAB:
            bbb = self.advancedList.selectedItems()[0].text()
        elif current_list == SERVICE_TAB:
            bbb = self.serviceList.selectedItems()[0].text()
        else:
            index = self.logsTable.selectionModel().selectedRows()[0]
            bbb = index.sibling(index.row(), 1).data()
        bbb_ip, bbb_hostname = bbb.split(" - " if current_list != LOGS_TAB else ":")
        hashname = "BBB:{}:{}".format(bbb_ip, bbb_hostname)
        info = self.nodes_info[hashname]
        if info[b"state_string"].decode() == "Connected":
            self.window = BBBConfig(hashname, info, self.server)
            self.window.show()
        else:
            QtWidgets.QMessageBox.warning(
                self,
                "Warning",
                "The node you are trying to configure isn't connected",
                QtWidgets.QMessageBox.Abort,
            )

    def service_application(self):
        """Applies services modification"""
        confirmation = QtWidgets.QMessageBox.question(
            self,
            "Confirmation",
            "Are you sure applying these changes?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
        )
        if confirmation == QtWidgets.QMessageBox.Yes:
            selected_operation = self.operationcomboBox.currentText()
            if selected_operation == "Restart":
                operation = self.server.restart_service
            else:
                operation = self.server.stop_service
            selected_bbbs = self.serviceList.selectedItems()
            for bbb in selected_bbbs:
                bbb_ip, bbb_hostname = bbb.text().split(" - ")
                if self.bbbreadBox.isChecked():
                    operation(bbb_ip, "bbbread", bbb_hostname)
                if self.bbbfunctionBox.isChecked():
                    operation(bbb_ip, "bbb-function", bbb_hostname)


if __name__ == "__main__":
    # Fixes poor scaling on 4k monitors
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)

    app = QtWidgets.QApplication(sys.argv)
    window = BBBreadMainWindow()
    window.show()
    sys.exit(app.exec_())
