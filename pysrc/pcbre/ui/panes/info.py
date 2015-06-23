__author__ = 'davidc'

from PySide import QtCore, QtGui


class InfoWidget(QtGui.QDockWidget):
    def __init__(self, project):
        super(InfoWidget, self).__init__("Object Information")
        self.setAllowedAreas(QtCore.Qt.LeftDockWidgetArea | QtCore.Qt.RightDockWidgetArea)

