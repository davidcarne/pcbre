from qtpy import QtWidgets
from pcbre.ui.debug.tool_action_history import ToolActionHistoryLogger, DebugToolActionHistoryWidget

import pcbre.ui.boardviewwidget
from typing import Optional

class ToggleActionInformation(QtWidgets.QAction):
    def __init__(self, mw: QtWidgets.QMainWindow, va: 'pcbre.ui.boardviewwidget.BoardViewWidget') -> None:
        QtWidgets.QAction.__init__(self, "Action routing", mw)
        self.va = va

        self.setCheckable(True)
        self.update_from_prop()
        self.triggered.connect(self.__set_prop)

        # Logger is persistent, but don't connect right away (to avoid overhead)
        self.history_logger = ToolActionHistoryLogger()
        self.widget : Optional['DebugToolActionHistoryWidget'] = None

        # Trigger local notification when the actions are changed on the boardview
        self.va.notify_changed_actions.append(self._actions_changed)

    def __del__(self) -> None:
        self.va.notify_changed_actions.remove(self._actions_changed)

    def _actions_changed(self) -> None:
        if self.widget is not None:
            self.widget.dispatch_table_model.refresh()

    def update_from_prop(self) -> None:
        self.setChecked(self.va.action_log_cb is not None)

    def __set_prop(self) -> None:
        if self.isChecked():
            self.va.action_log_cb = self.history_logger.log
            self.widget = DebugToolActionHistoryWidget(self.va, self.history_logger)
            self.widget.show()
        else:
            if self.widget is not None:
                self.widget.close()
                self.widget = None
            self.va.action_log_cb = None


class ToggleDrawBBoxAction(QtWidgets.QAction):
    def __init__(self, mw: QtWidgets.QMainWindow, va: 'pcbre.ui.boardviewwidget.BoardViewWidget') -> None:
        QtWidgets.QAction.__init__(self, "Draw Bounding Boxes", mw)
        self.va = va

        self.setCheckable(True)

        self.update_from_prop()
        self.triggered.connect(self.__set_prop)

    def __set_prop(self) -> None:
        self.va.debug_renderer.debug_draw_bbox = self.isChecked()

    def update_from_prop(self) -> None:
        self.setChecked(self.va.debug_renderer.debug_draw_bbox)

class ToggleDrawDebugAction(QtWidgets.QAction):
    def __init__(self, mw: QtWidgets.QMainWindow, va: 'pcbre.ui.boardviewwidget.BoardViewWidget') -> None:
        QtWidgets.QAction.__init__(self, "Debug Draws", mw)
        self.va = va

        self.setCheckable(True)

        self.update_from_prop()
        self.triggered.connect(self.__set_prop)

    def __set_prop(self) -> None:
        self.va.debug_renderer.debug_draw = self.isChecked()

    def update_from_prop(self) -> None:
        self.setChecked(self.va.debug_renderer.debug_draw)
