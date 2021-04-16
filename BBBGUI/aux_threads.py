from PyQt5 import QtCore


class TableModel(QtCore.QAbstractTableModel):
    # Display model for TableView
    def __init__(self, data, all=False):
        super(TableModel, self).__init__()
        self._data = data
        self._header = ["Timestamp", "BBB", "Occurence"] if all else ["Timestamp", "Occurence"]

    def headerData(self, section, orientation, role=QtCore.Qt.DisplayRole):
        if role == QtCore.Qt.DisplayRole and orientation == QtCore.Qt.Horizontal:
            return self._header[section]

    def data(self, index, role):
        if role == QtCore.Qt.DisplayRole or role == QtCore.Qt.EditRole:
            return self._data[index.row()][index.column()]

    def get_data(self):
        return self._data

    def set_data(self, data):
        self._data = data
        self.layoutChanged.emit()

    def rowCount(self, index):
        return len(self._data)

    def columnCount(self, index):
        if self.rowCount(0) < 1:
            return 0
        return len(self._data[0])


class UpdateNodesThread(QtCore.QThread):
    finished = QtCore.pyqtSignal(tuple)

    def __init__(self, server):
        QtCore.QThread.__init__(self)
        self.server = server

    def __del__(self):
        self.wait()

    def run(self):
        nodes = self.server.list_connected()
        nodes_info = {}

        for node in nodes:
            nodes_info[node] = self.server.get_node(node)

        self.finished.emit((nodes, nodes_info))


class UpdateLogsThread(QtCore.QThread):
    finished = QtCore.pyqtSignal(list)

    def __init__(self, server, hostname=None):
        QtCore.QThread.__init__(self)
        self.server = server
        self.hostname = hostname

    def __del__(self):
        self.wait()

    def run(self):
        # If no host name is set, all logs must be retrieved
        logs = self.server.get_logs(self.hostname)
        all_logs = logs if self.hostname else []

        # Iterates through BBB logs
        if not self.hostname:
            for name in logs:
                bbb_logs = []
                bbb_logs = self.server.get_logs(name)
                for _log in bbb_logs:
                    _log.insert(1, name[4 : name.index(":Logs")])

                all_logs.extend(bbb_logs)

        # Sorts logs by most recent to least recent
        all_logs = sorted(all_logs, key=lambda x: int(x[0]), reverse=True)

        self.finished.emit(all_logs)
