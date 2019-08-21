__author__ = 'davidc'
from PySide2 import QtCore, QtGui, QtWidgets

class PLineEdit(QtWidgets.QLineEdit):
    def __init__(self, *args, **kwargs):
        super(PLineEdit, self).__init__(*args, **kwargs)
        self.suppress_enter = True

        #for a in self.actions():

    def keyPressEvent(self, evt):
        super(PLineEdit, self).keyPressEvent(evt)

        if (evt.key() == QtCore.Qt.Key_Return or evt.key() == QtCore.Qt.Key_Enter) and self.suppress_enter:
            evt.accept()

    def event(self, evt):
        if evt.type() == QtCore.QEvent.ShortcutOverride:
            if evt == QtGui.QKeySequence.Undo or evt == QtGui.QKeySequence.Redo:
                return False

        return super(PLineEdit, self).event(evt)

    def createStandardContextMenu(self, *args, **kwargs):
        pass

