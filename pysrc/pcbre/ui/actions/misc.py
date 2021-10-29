__author__ = 'davidc'

from qtpy import QtGui, QtCore, QtWidgets


def _nudge(dx: int, dy: int) -> None:
    pos = QtGui.QCursor.pos()
    QtGui.QCursor.setPos(pos.x() + dx, pos.y() + dy)


class NudgeLeftAction(QtWidgets.QAction):
    def __init__(self, window: QtWidgets.QWidget) -> None:
        QtWidgets.QAction.__init__(self, "nudge left", window)
        self.triggered.connect(lambda: _nudge(-1, 0))
        self.setShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Left))


class NudgeRightAction(QtWidgets.QAction):
    def __init__(self, window: QtWidgets.QWidget) -> None:
        QtWidgets.QAction.__init__(self, "nudge right", window)
        self.triggered.connect(lambda: _nudge(1, 0))
        self.setShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Right))


class NudgeUpAction(QtWidgets.QAction):
    def __init__(self, window: QtWidgets.QWidget) -> None:
        QtWidgets.QAction.__init__(self, "nudge up", window)
        self.triggered.connect(lambda: _nudge(0, -1))
        self.setShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Up))


class NudgeDownAction(QtWidgets.QAction):
    def __init__(self, window: QtWidgets.QWidget) -> None:
        QtWidgets.QAction.__init__(self, "nudge up", window)
        self.triggered.connect(lambda: _nudge(0, 1))
        self.setShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Down))


class ShowToolSettingsAction(QtWidgets.QAction):
    def __init__(self, window: QtWidgets.QWidget) -> None:
        QtWidgets.QAction.__init__(self, "Show tool settings", window)
        self.triggered.connect(self.showToolSettings)
        self.setShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Tab))

        self.window = window

    def showToolSettings(self) -> None:
        if self.window.current_controller:
            self.window.current_controller.showSettingsDialog()
