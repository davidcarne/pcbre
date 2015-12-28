__author__ = 'davidc'

from PySide import QtGui, QtCore

def _nudge(dx, dy):
    pos = QtGui.QCursor.pos()
    QtGui.QCursor.setPos(pos.x() + dx, pos.y() + dy)


class NudgeLeftAction(QtGui.QAction):
    def __init__(self, window):
        QtGui.QAction.__init__(self, "nudge left", window, triggered=lambda: _nudge(-1, 0))
        self.setShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Left))

class NudgeRightAction(QtGui.QAction):
    def __init__(self, window):
        QtGui.QAction.__init__(self, "nudge right", window, triggered=lambda: _nudge(1, 0))
        self.setShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Right))

class NudgeUpAction(QtGui.QAction):
    def __init__(self, window):
        QtGui.QAction.__init__(self, "nudge up", window, triggered=lambda: _nudge(0, -1))
        self.setShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Up))

class NudgeDownAction(QtGui.QAction):
    def __init__(self, window):
        QtGui.QAction.__init__(self, "nudge up", window, triggered=lambda: _nudge(0, 1))
        self.setShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Down))

class ShowToolSettingsAction(QtGui.QAction):
    def __init__(self, window):
        QtGui.QAction.__init__(self, "Show tool settings", window, triggered=self.showToolSettings)
        self.setShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Tab))

        self.window = window

    def showToolSettings(self):
        if self.window.current_controller:
            self.window.current_controller.showSettingsDialog()
