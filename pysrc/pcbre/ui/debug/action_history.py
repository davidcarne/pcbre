from qtpy import QtCore, QtGui, QtWidgets

class ActionHistoryLogger:
    def __init__(self, depth = None):
        self.log_entries = []
        self.depth = None
        self.notify = []

    def log(self, *data):
        self.log_entries.append(data)

        if self.depth is not None and len(self.log_entries) > self.depth:
            trim = len(self.log_entries) - self.depth
            self.log_entries = self.log_entries[trim:]

        for notify in self.notify:
            notify()

class ActionHistoryListModel(QtCore.QAbstractListModel):
    def __init__(self, history, parent=None):
        QtCore.QAbstractListModel.__init__(self, parent)
        self.history = history

        self.history.notify.append(self._changed)

    def _changed(self):
        self.layoutChanged.emit()

    def rowCount(self, parent=QtCore.QModelIndex()):
        return len(self.history.log_entries)

    def data(self, index, role=QtCore.Qt.DisplayRole):
        if role == QtCore.Qt.DisplayRole:
            return repr(self.history.log_entries[index.row()])
        return None
    
    def __del__(self):
        self.history.notify.remove(self._changed)


class DebugActionHistoryWidget(QtWidgets.QDockWidget):
    def __init__(self, history):
        super(DebugActionHistoryWidget, self).__init__("Action History")
        self.setAllowedAreas(QtCore.Qt.LeftDockWidgetArea | QtCore.Qt.RightDockWidgetArea)

        self.model = ActionHistoryListModel(history)

        self.history = QtWidgets.QListView(self)
        self.history.setModel(self.model)

        self.setWidget(self.history)
    


