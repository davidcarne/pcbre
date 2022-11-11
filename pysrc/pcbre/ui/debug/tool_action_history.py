from typing import Union, List, Callable, Tuple, TYPE_CHECKING, Any, Optional, Sequence
from pcbre.ui.tool_action  import Modifier

from qtpy import QtCore, QtWidgets

if TYPE_CHECKING:
    from pcbre.ui.boardviewwidget import BoardViewWidget


class ToolActionHistoryLogger:
    def __init__(self, depth: Union[int, None] = None) -> None:
        self.log_entries: List[Sequence[Any]] = []
        self.depth = depth
        self.notify: List[Callable[[], None]] = []

    def log(self, *data: 'Sequence[Any]') -> None:
        self.log_entries.append(data)

        if self.depth is not None and len(self.log_entries) > self.depth:
            trim = len(self.log_entries) - self.depth
            self.log_entries = self.log_entries[trim:]

        self.send_notify()

    def send_notify(self) -> None:
        for notify in self.notify:
            notify()

    def clear(self) -> None:
        self.log_entries = []
        self.send_notify()


class ToolActionHistoryListModel(QtCore.QAbstractListModel):
    def __init__(self, history: ToolActionHistoryLogger, parent: Optional[QtCore.QObject] = None) -> None:
        QtCore.QAbstractListModel.__init__(self, parent)
        self.history = history

        self.history.notify.append(self._changed)

    def _changed(self) -> None:
        self.layoutChanged.emit()

    def rowCount(self, parent: QtCore.QModelIndex = QtCore.QModelIndex()) -> int:
        return len(self.history.log_entries)

    def data(self, index: QtCore.QModelIndex, role: int = QtCore.Qt.DisplayRole) -> Any:
        if role == QtCore.Qt.DisplayRole:
            return repr(self.history.log_entries[index.row()])
        return None

    def __del__(self) -> None:
        self.history.notify.remove(self._changed)


class ToolActionDispatchModel(QtCore.QAbstractTableModel):
    def __init__(self, boardview: 'BoardViewWidget'):
        super(ToolActionDispatchModel, self).__init__()
        self.boardview = boardview

        self._data: List[Tuple[str, str, str, str]] = []
        self.refresh()

    def rowCount(self, parent: Optional[QtCore.QModelIndex] = None) -> int:
        return len(self._data)

    def columnCount(self, parent: Optional[QtCore.QModelIndex] = None) -> int:
        return 4

    def data(self, idx: QtCore.QModelIndex, role: Optional[int] = None) -> Any:
        if role == QtCore.Qt.DisplayRole:
            return self._data[idx.row()][idx.column()]

        return None

    def headerData(self, p_int: int, orientation: int, role: Optional[int] = None) -> Any:
        if orientation == QtCore.Qt.Horizontal and role == QtCore.Qt.DisplayRole:
            return ["Event", "Target", "Name", "Desc"][p_int]
        return None

    def refresh(self) -> None:
        self.layoutAboutToBeChanged.emit()
        self._data = []
        for (evtid, modifier), action in self.boardview.local_actions_map.items():
            self._data.append(("%s %r" % (evtid.name, modifier), "local", "%r" % action, ""))

        for (evtid, modifier), actiondesc in self.boardview.id_actions_map.items():
            self._data.append(
                ("%s %r" % (evtid.name, modifier), "delegate", "%r" % actiondesc.event_code.name, actiondesc.description))
        self.layoutChanged.emit()


class DebugToolActionHistoryWidget(QtWidgets.QDockWidget):
    def __init__(self, boardview: 'BoardViewWidget', history: ToolActionHistoryLogger):
        super(DebugToolActionHistoryWidget, self).__init__("Action History")
        self.setAllowedAreas(QtCore.Qt.BottomDockWidgetArea)

        self.model = ToolActionHistoryListModel(history)

        self.tabs = QtWidgets.QTabWidget(self)
        self.setWidget(self.tabs)

        # Dispatch tab
        self.dispatch_tab = QtWidgets.QWidget()

        self.dispatch_table_model = ToolActionDispatchModel(boardview)

        self.dispatch_table = QtWidgets.QTableView()
        self.dispatch_table.horizontalHeader().setVisible(True)
        self.dispatch_table.setModel(self.dispatch_table_model)
        disp_tab_layout = QtWidgets.QVBoxLayout()

        disp_tab_btn_layout = QtWidgets.QHBoxLayout()
        disp_tab_btn_layout.addStretch(1)
        disp_tab_refresh_btn = QtWidgets.QPushButton("Refresh", self.dispatch_tab)
        disp_tab_refresh_btn.clicked.connect(lambda _: self.dispatch_table_model.refresh())

        disp_tab_layout.addWidget(self.dispatch_table, stretch=1)
        disp_tab_btn_layout.addWidget(disp_tab_refresh_btn)
        disp_tab_layout.addLayout(disp_tab_btn_layout)

        self.dispatch_tab.setLayout(disp_tab_layout)

        # History Tab
        self.history = QtWidgets.QListView(self)
        self.history.setModel(self.model)

        self.history_tab = QtWidgets.QWidget()
        hist_tab_layout = QtWidgets.QVBoxLayout()
        hist_tab_layout.addWidget(self.history, stretch=1)
        hist_bb = QtWidgets.QHBoxLayout()
        hist_tab_layout.addLayout(hist_bb)
        self.clear_history = QtWidgets.QPushButton("Clear", self.history_tab)

        self.clear_history.clicked.connect(lambda _: history.clear())

        hist_bb.addStretch(1)
        hist_bb.addWidget(self.clear_history)

        self.history_tab.setLayout(hist_tab_layout)

        self.tabs.addTab(self.dispatch_tab, "Event Dispatch")
        self.tabs.addTab(self.history_tab, "Event History")
