from qtpy import QtWidgets

class ToggleLogActions(QtWidgets.QAction):
    def __init__(self, mw, va):
        from pcbre.ui.debug.action_history import ActionHistoryLogger
        QtWidgets.QAction.__init__(self, "Log actions and shortcuts", mw)
        self.va = va

        self.setCheckable(True)
        self.update_from_prop()
        self.triggered.connect(self.__set_prop)

        self.history_logger = ActionHistoryLogger()
        self.widget = None


    def update_from_prop(self):
        self.setChecked(self.va.action_log_cb is not None)

    def __set_prop(self):
        from pcbre.ui.debug.action_history import DebugActionHistoryWidget
        if self.isChecked():
            self.va.action_log_cb = self.history_logger.log
            self.widget = DebugActionHistoryWidget(self.history_logger)
            self.widget.show()
        else:
            if self.widget is not None:
                self.widget.close()
                self.widget = None
            self.va.action_log_vb = None


class ToggleDrawBBoxAction(QtWidgets.QAction):
    def __init__(self, mw, va):
        QtWidgets.QAction.__init__(self, "Draw Bounding Boxes", mw)
        self.va = va

        self.setCheckable(True)

        self.update_from_prop()
        self.triggered.connect(self.__set_prop)

    def __set_prop(self):
        self.va.debug_renderer.debug_draw_bbox = self.isChecked()

    def update_from_prop(self):
        self.setChecked(self.va.debug_renderer.debug_draw_bbox)

class ToggleDrawDebugAction(QtWidgets.QAction):
    def __init__(self, mw, va):
        QtWidgets.QAction.__init__(self, "Debug Draws", mw)
        self.va = va

        self.setCheckable(True)

        self.update_from_prop()
        self.triggered.connect(self.__set_prop)

    def __set_prop(self):
        self.va.debug_renderer.debug_draw = self.isChecked()

    def update_from_prop(self):
        self.setChecked(self.va.debug_renderer.debug_draw)
