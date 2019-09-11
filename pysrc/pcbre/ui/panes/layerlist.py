from qtpy import QtCore, QtGui, QtWidgets

class LayerListModel(QtCore.QAbstractListModel):
    def __init__(self, project, parent=None):
        QtCore.QAbstractListModel.__init__(self, parent)
        self.p = project
        project.stackup.changed.connect(self._changed)

    def _changed(self, reason):
        self.layoutChanged.emit()

    def rowCount(self, parent=QtCore.QModelIndex()):
        b = len(self.p.stackup.layers)
        return b

    def data(self, index, role=QtCore.Qt.DisplayRole):
        if role == QtCore.Qt.DisplayRole:
            return self.p.stackup.layers[index.row()].name
        return None

class LayerListWidget(QtWidgets.QDockWidget):
    def __init__(self, project, viewState):
        super(LayerListWidget, self).__init__("Layer List")
        self.setAllowedAreas(QtCore.Qt.LeftDockWidgetArea | QtCore.Qt.RightDockWidgetArea)

        model = LayerListModel(project)
        customerList = QtWidgets.QListView(self)
        customerList.setModel(model)
        selm = customerList.selectionModel()
        self.p = project

        def layerSelectionChanged(index, b):
            viewState.current_layer = self.p.stackup.layers[index.indexes()[0].row()]

        selm.selectionChanged.connect(layerSelectionChanged)

        self.setWidget(customerList)
