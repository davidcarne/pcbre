__author__ = 'davidc'

from PySide2 import QtCore, QtGui, QtWidgets


class InfoWidget(QtWidgets.QDockWidget):
    def __init__(self, project):
        super(InfoWidget, self).__init__("Object Information")
        self.setAllowedAreas(QtCore.Qt.LeftDockWidgetArea | QtCore.Qt.RightDockWidgetArea)

