import random
import numpy

from qtpy import QtCore
from qtpy import QtGui
from qtpy import QtWidgets
from qtpy.QtCore import Qt

import pcbre.model.project
import pcbre.model.stackup

from typing import Set
from pcbre.model.stackup import Layer
from pcbre.model.imagelayer import ImageLayer


FIRST_VIEW_COL = 1
class LayerViewSetupDialog(QtWidgets.QDialog):
    def __init__(self, parent, project: pcbre.model.project.Project):
        QtWidgets.QDialog.__init__(self, parent)

        self.resize(470, 350)
        self.setWindowTitle("Layer imagery")

        self.table_model : LayerViewAdapter = LayerViewAdapter(self, project)

        self.table_view = QtWidgets.QTableView()

        self.table_view.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.table_view.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)

        self.table_view.setModel(self.table_model)
        # set font
        font = QtGui.QFont("Courier New", 10)
        self.table_view.setFont(font)
        self.table_view.resizeColumnsToContents()


        layout = QtWidgets.QHBoxLayout(self)
        layout.addWidget(self.table_view)
        l2 = QtWidgets.QVBoxLayout()

        self.cancelButton = QtWidgets.QPushButton("cancel")
        self.cancelButton.clicked.connect(self.reject)
        self.okButton = QtWidgets.QPushButton("apply")
        self.okButton.setDefault(True)
        self.okButton.clicked.connect(self.accept)

        l2.addStretch()
        l2.addWidget(self.cancelButton)
        l2.addWidget(self.okButton)

        #l2.addRow("test", None)
        layout.addLayout(l2)

        self.setLayout(layout)


        self.table_view.selectRow(0)

    def accept(self):
        self.table_model.update()
        return QtWidgets.QDialog.accept(self)


class EditableLayer:
    def __init__(self, mdl : 'LayerViewAdapter', ref: Layer, name: str, ils):
        self.name = name
        self.mdl = mdl
        self.ref = ref
        self.view_set : Set[ImageLayer] = set(ils)


class LayerViewAdapter(QtCore.QAbstractTableModel):
    def __init__(self, parent, project: pcbre.model.project.Project, *args):
        QtCore.QAbstractTableModel.__init__(self, parent, *args)
        self.p = project
        self._layers =  [
            EditableLayer(self, pl, pl.name, pl.imagelayers)
            for pl in project.stackup.layers]

        self._views = project.imagery.imagelayers

    def update(self):
        for i in self._layers:
            i.ref.imagelayers = list(i.view_set)

    def rowCount(self, parent):
        return len(self._layers)

    def columnCount(self, parent):
        return len(self._views)

    def data(self, index, role):
        if not index.isValid():
            return None

        col = index.column()
        row = index.row()

        if role == Qt.DisplayRole:
            return None

        elif role == Qt.CheckStateRole:
            layer = self._layers[row]
            view = self._views[col]
            return Qt.Checked if view in layer.view_set else Qt.Unchecked

        return None

    def setData(self, index, data, role):
        if not index.isValid():
            return None

        col = index.column()
        row = index.row()

        layer = self._layers[row]
        view = self._views[col]
        if data:
            layer.view_set.add(view)
        else:
            layer.view_set.remove(view)

        self.dataChanged.emit(index, index)

        return True

    def flags(self, index):
        if not index.isValid():
            return 0

        col = index.column()
        row = index.row()

        flags = Qt.ItemIsEnabled | Qt.ItemIsUserCheckable
        return flags

    def headerData(self, index, orientation, role):
        if orientation == Qt.Vertical and role == Qt.DisplayRole:
            return self._layers[index].name

        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            #TODO HACK
            import os.path
            return os.path.basename(self._views[index].name)
        return None


# Test harness
if __name__ == "__main__":
    app = QtWidgets.QApplication([])
    project = pcbre.model.project.Project.create()

    win = LayerViewSetupDialog(None, project)
    win.show()
    app.exec_()
