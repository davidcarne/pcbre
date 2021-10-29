from qtpy import QtCore, QtWidgets


class UndoDock(QtWidgets.QDockWidget):
    def __init__(self, undo_stack: "QtWidgets.QUndoStack") -> None:
        super(UndoDock, self).__init__("Undo View")

        # ignore typing because the area union does not properly do typing
        self.setAllowedAreas(QtCore.Qt.LeftDockWidgetArea | QtCore.Qt.RightDockWidgetArea) # type: ignore

        undoview = QtWidgets.QUndoView(undo_stack, self)
        self.setWidget(undoview)
