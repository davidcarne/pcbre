from qtpy import QtCore, QtWidgets

__author__ = 'davidc'

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    import pcbre.model.project


class InfoWidget(QtWidgets.QDockWidget):
    def __init__(self, project: "pcbre.model.project.Project") -> None:
        super(InfoWidget, self).__init__("Object Information")

        self.setAllowedAreas(QtCore.Qt.LeftDockWidgetArea | QtCore.Qt.RightDockWidgetArea) # type:ignore
