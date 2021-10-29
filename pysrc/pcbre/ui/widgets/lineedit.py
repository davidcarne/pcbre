__author__ = 'davidc'
from qtpy import QtCore, QtGui, QtWidgets

from typing import Any, Optional

class PLineEdit(QtWidgets.QLineEdit):
    def __init__(self) -> None:
        super(PLineEdit, self).__init__()
        self.suppress_enter = True

    def keyPressEvent(self, evt: QtCore.QEvent) -> None:
        super(PLineEdit, self).keyPressEvent(evt)

        if (evt.key() == QtCore.Qt.Key_Return or evt.key() == QtCore.Qt.Key_Enter) and self.suppress_enter:
            evt.accept()

    def event(self, evt: QtCore.QEvent) -> bool:
        if evt.type() == QtCore.QEvent.ShortcutOverride:
            if evt == QtGui.QKeySequence.Undo or evt == QtGui.QKeySequence.Redo:
                return False

        return super(PLineEdit, self).event(evt)

