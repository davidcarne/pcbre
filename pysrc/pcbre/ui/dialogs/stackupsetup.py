import random
import colorsys
import numpy

from PySide.QtCore import *
from PySide.QtGui import *

import pcbre.model.project
import pcbre.model.stackup

NAME_COL = 0
FIRST_VP_COL = 1

# Header with fixed size
class HHeader(QHeaderView):
    def __init__(self, *args, **kwargs):
        QHeaderView.__init__(self, *args, **kwargs)
        self.setResizeMode(self.Fixed)

    def sizeHint(self):
        return QSize(30, 0)

class StackupSetupDialog(QDialog):
    def __init__(self, parent, data_list, *args):
        QDialog.__init__(self, parent, *args)

        self.resize(470, 350)
        self.setWindowTitle("Layer parameters")

        self.table_model = MyTableModel(self, data_list)


        self.table_view = QTableView()

        self.table_view.setSelectionMode(QAbstractItemView.SingleSelection) 
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectRows)

        self.table_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table_view.customContextMenuRequested.connect(self.handleAreaMenu)


        header = self.table_view.horizontalHeader()
        header.setContextMenuPolicy(Qt.CustomContextMenu)
        header.customContextMenuRequested.connect(self.handleHeaderMenu) 

        lb = HHeader(Qt.Vertical, self.table_view) 
        lb.sectionDoubleClicked.connect(self.selectColor)
        self.table_view.setVerticalHeader(lb)
        lbar = self.table_view.verticalHeader()

        #lbar.setMovable(True)
        #lbar.setDragEnabled(True)
        #lbar.setDragDropMode(QAbstractItemView.InternalMove)

        self.table_view.setModel(self.table_model)
        # set font
        font = QFont("Courier New", 10)
        self.table_view.setFont(font)
        self.table_view.resizeColumnsToContents()


        layout = QHBoxLayout(self)
        layout.addWidget(self.table_view)
        l2 = QVBoxLayout()

        self.newButton = QPushButton("add layer")
        self.newButton.clicked.connect(self.addLayer)
        self.deleteButton = QPushButton("delete layer")
        self.deleteButton.clicked.connect(self.deleteLayer)

        self.upButton = QPushButton("move up")
        self.upButton.clicked.connect(self.moveUpButtonPressed)
        self.downButton = QPushButton("move down")
        self.downButton.clicked.connect(self.moveDownButtonPressed)

        self.cancelButton = QPushButton("cancel")
        self.cancelButton.clicked.connect(self.reject)
        self.okButton = QPushButton("apply")
        self.okButton.setDefault(True)
        self.okButton.clicked.connect(self.accept)

        l2.addWidget(self.newButton)
        l2.addWidget(self.deleteButton)

        l2.addWidget(self.upButton)
        l2.addWidget(self.downButton)
        l2.addStretch()
        l2.addWidget(self.cancelButton)
        l2.addWidget(self.okButton)

        #l2.addRow("test", None)
        layout.addLayout(l2)

        self.setLayout(layout)

        selmdl = self.table_view.selectionModel()
        selmdl.selectionChanged.connect(self.updateSelection)

        self.table_view.selectRow(0)


    def accept(self):
        self.table_model.update()
        return QDialog.accept(self)

    def moveUpButtonPressed(self):
        row = self.table_view.selectedIndexes()[0].row()
        self.table_model.move(row, -1)
        self.table_view.selectRow(row-1)

    def moveDownButtonPressed(self):
        row = self.table_view.selectedIndexes()[0].row()
        self.table_model.move(row, 1)
        self.table_view.selectRow(row+1)

    def addLayer(self):
        indicies = self.table_view.selectedIndexes()
        if not indicies:
            row = -1
        else:
            row = indicies[0].row()

        self.table_model.addLayer(row)
        self.table_view.selectRow(row+1)

    def deleteLayer(self):
        indicies = self.table_view.selectedIndexes()

        if not indicies:
            return

        row = indicies[0].row()
        l = self.table_model.layer(row)

        # refuse to delete a layer that is the start/end of a viapair
        for vp in self.table_model._via_pairs:
            if row == vp.startIndex or row == vp.endIndex:
                return

        self.table_model.delLayer(row)
        self.table_view.selectRow(row - 1 if row -1 >= 0 else 0)
        self.updateSelection()

    def updateSelection(self, *args):
        indicies = self.table_view.selectedIndexes()
        row = None

        if indicies and indicies[0].isValid():
            row_n = indicies[0].row()
            row = self.table_model.layer(row_n)

        self.upButton.setEnabled(bool(row) and not row.isFirst)
        self.downButton.setEnabled(bool(row) and not row.isLast)
        self.deleteButton.setEnabled(bool(row) and bool(self.table_model.layerCount()))


    def doMenu(self, row, col, is_header=False):
        menu = QMenu()

        layer = None
        vp = None

        if col >= FIRST_VP_COL:
            vp = self.table_model.viapair(col - FIRST_VP_COL)
        if row >= 0:
            layer = self.table_model.layer(row)

        act = menu.addAction('Add Via Pair')
        act.triggered.connect(self.table_model.addViaPair)

        # Delete via pair only shown for via pair cols
        act = menu.addAction('Delete Via Pair')
        act.setEnabled(col >= FIRST_VP_COL)
        act.triggered.connect(
            lambda: self.table_model.delViaPair(vp)
        )


        if not is_header and col >= FIRST_VP_COL:
            menu.addSeparator()

            act = menu.addAction('Set Top')
            act.triggered.connect(
                lambda: self.table_model.viaPairSetTop(vp, layer)
            )
            act.setEnabled(vp.endIndex > row)

            act = menu.addAction('Set Bottom')
            act.triggered.connect(
                lambda: self.table_model.viaPairSetBottom(vp, layer)
            )
            act.setEnabled(vp.startIndex < row)

        menu.exec_(QCursor.pos())

    def handleHeaderMenu(self, pos):
        col = self.table_view.horizontalHeader().logicalIndexAt(pos)
        self.doMenu(0, col, is_header=True)

    def handleAreaMenu(self, pos):
        index = self.table_view.indexAt(pos)
        col = index.column()
        row = index.row()

        self.doMenu(row, col)

    def selectColor(self, idx):
        cur = numpy.array(self.table_model.layer(idx).color) * 255
        initial = QColor(*cur)
        c = QColorDialog.getColor(initial)
        if c.isValid():
            r,g,b,_ = c.getRgb()
            self.table_model.layer(idx).color = numpy.array([r,g,b])/255.0
            self.table_model.headerDataChanged.emit(Qt.Vertical, idx, idx)

class EditableLayer(object):
    def __init__(self, mdl, ref, name, col):
        self.mdl = mdl
        self.name = name
        self.ref = ref
        self.color = col

    @property
    def isFirst(self):
        return self.mdl._layers[0] is self

    @property
    def isLast(self):
        return self.mdl._layers[-1] is self

    @property
    def index(self):
        return self.mdl._layers.index(self)

class EditableVP(object):
    def __init__(self, mdl, ref, start, end):
        self.mdl = mdl
        self.startLayer = start
        self.endLayer = end
        self.ref = ref

    @property
    def index(self):
        return self.mdl._via_pairs.index(self)

    @property 
    def endIndex(self):
        return self.endLayer.index

    @endIndex.setter
    def endIndex(self, value):
        self.endLayer = self.mdl._layers[value]

    @property 
    def startIndex(self):
        return self.startLayer.index

    @startIndex.setter
    def startIndex(self, value):
        self.startLayer = self.mdl._layers[value]
   

class MyTableModel(QAbstractTableModel):
    def __init__(self, parent, project, *args):
        QAbstractTableModel.__init__(self, parent, *args)
        self.p = project
        self._layers = [EditableLayer(self, l, l.name, l.color) for l in
                        self.p.stackup.layers]

        def find_layer_ref(l):
            for i in self._layers:
                if i.ref == l:
                    return i
            assert False

        self._via_pairs = []

        for _vp in self.p.stackup.via_pairs:
            _la, _lb = _vp.layers
            la = find_layer_ref(_la)
            lb = find_layer_ref(_lb)
            self._via_pairs.append(EditableVP(self, _vp, la, lb))


    def update(self):
        to_remove = set(self.p.stackup.layers)

        for i in self._layers:
            # If there's an existing layer
            if i.ref is not None:
                # Then we don't remove it
                to_remove.remove(i.ref)
            else:
                # Otherwise add a new layer
                i.ref = pcbre.model.stackup.Layer(name=i.name, color=i.color)
                self.p.stackup.add_layer(i.ref)

            i.ref.name = i.name
            i.ref.color = i.color

        # Remove all the layers we didn't find
        for i in to_remove:
            self.p.stackup.remove_layer(i)

        # now, walking from first to last layer, update the layer ordering
        # re-enumerate to ensure order is gapless
        for n, i in enumerate(sorted(self._layers, key=lambda x: x.index)):
            self.p.stackup.set_layer_order(i.ref, n)

        # Now update all the viapairs
        to_remove = set(self.p.stackup.via_pairs)
        for i in self._via_pairs:
            if i.ref == None:
                new_layer = pcbre.model.stackup.ViaPair(i.startLayer.ref, i.endLayer.ref)
                self.p.stackup.add_via_pair(new_layer)
            else:
                i.ref.layers = i.startLayer.ref, i.endLayer.ref
                to_remove.remove(i.ref)

        for l in to_remove:
            self.p.stackup.remove_via_pair(l)

    def move(self, index, direction):
        a = self._layers[index]

        self._layers[index] = self._layers[index + direction]
        self._layers[index + direction] = a

        first_row = min(index, index+direction)
        second_row = max(index, index+direction)

        self.dataChanged.emit(self.index(first_row, 0),
                              self.index(second_row,self.columnCount(None)))

    def layer(self, n):
        return self._layers[n]

    def viapair(self, n):
        return self._via_pairs[n]

    def addLayer(self, idx):
        self.emit(SIGNAL("layoutAboutToBeChanged()"))

        col = numpy.array(colorsys.hsv_to_rgb(random.random(), 1, 1))

        l = EditableLayer(self, None, "New Layer", col)
        self._layers.insert(idx, l)
        self.emit(SIGNAL("layoutChanged()"))

    def delLayer(self, idx):
        self.emit(SIGNAL("layoutAboutToBeChanged()"))
        del self._layers[idx]
        self.emit(SIGNAL("layoutChanged()"))

    def layerCount(self):
        return len(self._layers)

    def addViaPair(self):
        if len(self._layers) >= 2:
            self.emit(SIGNAL("layoutAboutToBeChanged()"))
            self._via_pairs.append(EditableVP(self, None, self._layers[0], self._layers[-1]))
            self.emit(SIGNAL("layoutChanged()"))
            return True
        else:
            return False

    def layerChanged(self, layer):
        ra = self.index(layer.index, 0)
        rb = self.index(layer.index, len(self._via_pairs) + FIRST_VP_COL)
        self.dataChanged.emit(ra, rb)

    def vpChanged(self, vp):
        va = self.index(0, vp.index + FIRST_VP_COL)
        vb = self.index(len(self._layers), vp.index + FIRST_VP_COL)
        self.dataChanged.emit(va, vb)

    def viaPairSetTop(self, vp, layer):
        vp.startLayer = layer
        self.vpChanged(vp)

    def viaPairSetBottom(self, vp, layer):
        vp.endLayer = layer
        self.vpChanged(vp)

    def delViaPair(self, vp):
        self.emit(SIGNAL("layoutAboutToBeChanged()"))

        del self._via_pairs[self._via_pairs.index(vp)]

        self.emit(SIGNAL("layoutChanged()"))

    def rowCount(self, parent):
        return len(self._layers)

    def columnCount(self, parent):
        return FIRST_VP_COL + len(self._via_pairs)

    def data(self, index, role):
        if not index.isValid():
            return None

        col = index.column()
        row = index.row()

        if role == Qt.DisplayRole:
            if col == 0:
                return self._layers[row].name

            return None

        elif role == Qt.BackgroundRole:
            if col == NAME_COL:
                return None

            elif col >= FIRST_VP_COL:
                vp = self._via_pairs[col-FIRST_VP_COL]
                if vp.startIndex <= row <= vp.endIndex:
                    return QBrush(QColor(0,0,0))
                return None

        return None

    def setData(self, index, data, role):

        if len(data) > 0:
            self.setLayerName(index.row(), data)
            return True

        return False

    def setLayerName(self, row, data):
        self._layers[row].name = data
        self.dataChanged.emit(self.index(row, 0), self.index(row, 0))

    def flags(self, index):
        col = index.column()
        row = index.row()


        flags = Qt.ItemIsEnabled | Qt.ItemIsSelectable

        if col == 0:
            flags |= Qt.ItemIsEditable 
            flags |= Qt.ItemIsDragEnabled | Qt.ItemIsDropEnabled
        

        return flags

    def headerData(self, index, orientation, role):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            if index == 0:
                return "Layer Name"
            else:
                return "Via pair"
        elif orientation == Qt.Vertical and role == Qt.BackgroundRole:
            colors = [i * 255 for i in self._layers[index].color]
            return QBrush(QColor(*colors))

        return None

# Test harness
if __name__ == "__main__":
    app = QApplication([])
    import os.path
    PATH = '/tmp/test.pcbre'
    if os.path.exists(PATH):
        project = pcbre.model.project.Project.open(PATH)
    else:
        project = pcbre.model.project.Project.create(PATH)

    win = StackupSetupDialog(project)
    win.show()
    app.exec_()
