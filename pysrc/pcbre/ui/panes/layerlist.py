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

    def index_for(self, layer):
        row = self.p.stackup._order_for_layer(layer)
        return self.index(row)

class LayerListWidget(QtWidgets.QDockWidget):
    def __init__(self, win, project, viewState):
        super(LayerListWidget, self).__init__("Layer List")
        self.setAllowedAreas(QtCore.Qt.LeftDockWidgetArea | QtCore.Qt.RightDockWidgetArea)

        self.win = win
        self.model = LayerListModel(project)

        self.layer_list = QtWidgets.QListView(self)
        self.layer_list.setModel(self.model)
        self.layer_list.selectionModel().selectionChanged.connect(self.layerSelectionChanged)

        self.win.layerChanged.connect(self.changeSelection)

        self.setWidget(self.layer_list)

        self.suppress_sel_change = False
    

    def changeSelection(self, layer):
        self.suppress_sel_change = True
        self.layer_list.selectionModel().select(
            self.model.index_for(layer),
            QtCore.QItemSelectionModel.SelectCurrent)

        self.suppress_sel_change = False

    def layerSelectionChanged(self, index, b):
        if self.suppress_sel_change:
            return

        layer_index = index.indexes()[0].row()
        self.win.changeViewLayer(self.win.project.stackup.layers[layer_index])
        
