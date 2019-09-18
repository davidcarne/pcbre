from qtpy import QtCore, QtGui, QtWidgets

class UndoDock(QtWidgets.QDockWidget):
    def __init__(self, undo_stack):
        super(UndoDock, self).__init__("Undo View")
        self.setAllowedAreas(QtCore.Qt.LeftDockWidgetArea | QtCore.Qt.RightDockWidgetArea)

        undoview = QtWidgets.QUndoView(undo_stack, self)
        self.setWidget(undoview)
