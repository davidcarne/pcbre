import colorsys
import random
from typing import Optional, List, Any, TYPE_CHECKING, Tuple, cast

import numpy
from qtpy import QtCore, QtGui, QtWidgets

from pcbre.model.stackup import Layer, ViaPair

if TYPE_CHECKING:
    from pcbre.model.project import Project

NAME_COL = 0
FIRST_VP_COL = 1


# Header with fixed size
class HHeader(QtWidgets.QHeaderView):
    def __init__(self, orientation: QtCore.Qt.Orientation, parent: QtWidgets.QTableView) -> None:
        QtWidgets.QHeaderView.__init__(self, orientation, parent)
        self.setSectionResizeMode(self.Fixed)

    def sizeHint(self) -> QtCore.QSize:
        return QtCore.QSize(30, 0)


class StackupSetupDialog(QtWidgets.QDialog):
    def __init__(self, parent: QtWidgets.QWidget, data_list: 'Project') -> None:
        QtWidgets.QDialog.__init__(self, parent, QtCore.Qt.WindowFlags())

        self.resize(470, 350)
        self.setWindowTitle("Layer parameters")

        self.table_model = StackupAdapter(self, data_list)

        self.table_view = QtWidgets.QTableView()

        self.table_view.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.table_view.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)

        self.table_view.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.table_view.customContextMenuRequested.connect(self.handle_area_menu)

        header = self.table_view.horizontalHeader()
        header.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        header.customContextMenuRequested.connect(self.handle_header_menu)

        lb = HHeader(QtCore.Qt.Vertical, self.table_view)
        lb.sectionDoubleClicked.connect(self.select_color)
        self.table_view.setVerticalHeader(lb)

        # lbar = self.table_view.verticalHeader()
        # lbar.setMovable(True)
        # lbar.setDragEnabled(True)
        # lbar.setDragDropMode(QAbstractItemView.InternalMove)

        self.table_view.setModel(self.table_model)
        # set font
        font = QtGui.QFont("Courier New", 10)
        self.table_view.setFont(font)
        self.table_view.resizeColumnsToContents()

        layout = QtWidgets.QHBoxLayout(self)
        layout.addWidget(self.table_view)
        l2 = QtWidgets.QVBoxLayout()

        self.newButton = QtWidgets.QPushButton("add layer")
        self.newButton.clicked.connect(self.addLayer)
        self.deleteButton = QtWidgets.QPushButton("delete layer")
        self.deleteButton.clicked.connect(self.deleteLayer)

        self.upButton = QtWidgets.QPushButton("move up")
        self.upButton.clicked.connect(self.moveUpButtonPressed)
        self.downButton = QtWidgets.QPushButton("move down")
        self.downButton.clicked.connect(self.moveDownButtonPressed)

        self.cancelButton = QtWidgets.QPushButton("cancel")
        self.cancelButton.clicked.connect(self.reject)
        self.okButton = QtWidgets.QPushButton("apply")
        self.okButton.setDefault(True)
        self.okButton.clicked.connect(self.accept)

        l2.addWidget(self.newButton)
        l2.addWidget(self.deleteButton)

        l2.addWidget(self.upButton)
        l2.addWidget(self.downButton)
        lbl = QtWidgets.QLabel("right-click table header to add/remove via-pairs")
        lbl.setWordWrap(True)
        l2.addWidget(lbl)
        l2.addStretch()
        l2.addWidget(self.cancelButton)
        l2.addWidget(self.okButton)

        # l2.addRow("test", None)
        layout.addLayout(l2)

        self.setLayout(layout)

        selmdl = self.table_view.selectionModel()
        selmdl.selectionChanged.connect(self.updateSelection)

        self.table_view.selectRow(0)

    def accept(self) -> None:
        self.table_model.update()
        return QtWidgets.QDialog.accept(self)

    def moveUpButtonPressed(self) -> None:
        row = self.table_view.selectedIndexes()[0].row()
        self.table_model.move(row, -1)
        self.table_view.selectRow(row - 1)

    def moveDownButtonPressed(self) -> None:
        row = self.table_view.selectedIndexes()[0].row()
        self.table_model.move(row, 1)
        self.table_view.selectRow(row + 1)

    def addLayer(self) -> None:
        indicies = self.table_view.selectedIndexes()
        if not indicies:
            row = -1
        else:
            row = indicies[0].row()

        self.table_model.add_layer(row)
        self.table_view.selectRow(row + 1)

    def deleteLayer(self) -> None:
        indicies = self.table_view.selectedIndexes()

        if not indicies:
            return

        row = indicies[0].row()
        l = self.table_model.layer(row)

        if l is None:
            return

        # refuse to delete a layer that is the start/end of a viapair
        for vp in self.table_model.via_pairs:
            if row == vp.start_index or row == vp.end_index:
                return

        self.table_model.del_layer(row)
        self.table_view.selectRow(row - 1 if row - 1 >= 0 else 0)
        self.updateSelection()

    def updateSelection(self, *args: List[Any]) -> None:
        indicies = self.table_view.selectedIndexes()
        row = None

        if indicies and indicies[0].isValid():
            row_n = indicies[0].row()

            row = self.table_model.layer(row_n)

            if row is None:
                return
        else:
            return

        self.upButton.setEnabled(bool(row) and not row.is_first)
        self.downButton.setEnabled(bool(row) and not row.is_last)
        self.deleteButton.setEnabled(bool(row) and bool(self.table_model.layer_count()))

    def do_menu(self, row: int, col: int, is_header: bool = False) -> None:
        menu = QtWidgets.QMenu()

        layer = None
        vp: Optional['EditableVP'] = None

        if col >= FIRST_VP_COL:
            vp = self.table_model.viapair(col - FIRST_VP_COL)
        else:
            vp = None

        if row >= 0:
            layer = self.table_model.layer(row)

        act = menu.addAction('Add Via Pair')
        act.triggered.connect(self.table_model.add_via_pair)

        # Delete via pair only shown for via pair cols
        act = menu.addAction('Delete Via Pair')
        if vp is not None:
            vp_: 'EditableVP' = vp
            act.setEnabled(col >= FIRST_VP_COL)
            act.triggered.connect(
                lambda: self.table_model.del_via_pair(vp_)
            )

        if not is_header and vp is not None and layer is not None:
            # Workaround for python typing
            vp2: 'EditableVP' = vp
            layer2: 'EditableLayer' = layer
            menu.addSeparator()

            act = menu.addAction('Set Top')
            act.triggered.connect(
                lambda: self.table_model.via_pair_set_top(vp2, layer2)
            )
            act.setEnabled(vp.end_index > row)

            act = menu.addAction('Set Bottom')
            act.triggered.connect(
                lambda: self.table_model.via_pair_set_bottom(vp2, layer2)
            )
            act.setEnabled(vp.start_index < row)

        menu.exec_(QtGui.QCursor.pos())

    def handle_header_menu(self, pos: QtCore.QPoint) -> None:
        col = self.table_view.horizontalHeader().logicalIndexAt(pos)
        self.do_menu(0, col, is_header=True)

    def handle_area_menu(self, pos: QtCore.QPoint) -> None:
        index = self.table_view.indexAt(pos)
        col = index.column()
        row = index.row()

        self.do_menu(row, col)

    def select_color(self, idx: int) -> None:
        lay = self.table_model.layer(idx)
        if lay is None:
            return

        initial = QtGui.QColor(
            int(lay.color[0] * 255), 
            int(lay.color[1] * 255), 
            int(lay.color[2] * 255))

        c = QtWidgets.QColorDialog().getColor(initial)
        if c.isValid():
            r, g, b, _ = c.getRgb()
            lay.color = (r/255.0, g/255.0, b/255.0)
            self.table_model.headerDataChanged.emit(QtCore.Qt.Vertical, idx, idx)


class EditableLayer(object):
    def __init__(self, mdl: 'StackupAdapter',
                 ref: 'Optional[Layer]',
                 name: str,
                 col: 'Tuple[float, float, float]') -> None:
        self.mdl = mdl
        self.name = name
        self.ref = ref
        self.color = col

    @property
    def is_first(self) -> bool:
        return self.mdl.layers[0] is self

    @property
    def is_last(self) -> bool:
        return self.mdl.layers[-1] is self

    @property
    def index(self) -> int:
        return self.mdl.layers.index(self)


class EditableVP:
    def __init__(self, mdl: 'StackupAdapter', ref: 'Optional[ViaPair]', start: 'EditableLayer',
                 end: 'EditableLayer'):
        self.mdl = mdl
        self.startLayer = start
        self.endLayer = end
        self.ref = ref

    @property
    def index(self) -> int:
        return self.mdl.via_pairs.index(self)

    @property
    def end_index(self) -> int:
        return self.endLayer.index

    @end_index.setter
    def end_index(self, value: int) -> None:
        self.endLayer = self.mdl.layers[value]

    @property
    def start_index(self) -> int:
        return self.startLayer.index

    @start_index.setter
    def start_index(self, value: int) -> None:
        self.startLayer = self.mdl.layers[value]


class StackupAdapter(QtCore.QAbstractTableModel):
    def __init__(self, parent: 'QtWidgets.QWidget', prj: 'Project') -> None:
        QtCore.QAbstractTableModel.__init__(self, parent)
        self.p = prj
        self.layers: List[EditableLayer] = [
            EditableLayer(self, orig_layer, orig_layer.name, orig_layer.color) for orig_layer in
            self.p.stackup.layers]

        def find_layer_ref(orig_layer: Layer) -> EditableLayer:
            for i in self.layers:
                if i.ref == orig_layer:
                    return i
            assert False

        self.via_pairs: List[EditableVP] = []

        for _vp in self.p.stackup.via_pairs:
            _la, _lb = _vp.layers
            la = find_layer_ref(_la)
            lb = find_layer_ref(_lb)
            self.via_pairs.append(EditableVP(self, _vp, la, lb))

    def update(self) -> None:
        to_remove = set(self.p.stackup.layers)

        for i in self.layers:
            # If there's an existing layer
            if i.ref is not None:
                # Then we don't remove it
                to_remove.remove(i.ref)
            else:
                # Otherwise add a new layer
                i.ref = Layer(self.p, name=i.name, color=i.color)
                self.p.stackup.add_layer(i.ref)

            i.ref.name = i.name
            i.ref.color = i.color

        # Remove all the layers we didn't find
        for i_ in to_remove:
            self.p.stackup.remove_layer(i_)

        # now, walking from first to last layer, update the layer ordering
        # re-enumerate to ensure order is gapless
        for n, j in enumerate(sorted(self.layers, key=lambda x: x.index)):
            assert j.ref is not None
            self.p.stackup.set_layer_order(j.ref, n)

        # Now update all the viapairs
        to_remove_vp = set(self.p.stackup.via_pairs)
        for vp in self.via_pairs:
            if vp.ref is None:
                assert vp.startLayer.ref is not None
                assert vp.endLayer.ref is not None
                new_layer = ViaPair(self.p, vp.startLayer.ref, vp.endLayer.ref)
                self.p.stackup.add_via_pair(new_layer)
            else:
                assert vp.startLayer.ref is not None
                assert vp.endLayer.ref is not None
                vp.ref.layers = vp.startLayer.ref, vp.endLayer.ref
                to_remove_vp.remove(vp.ref)

        for l in to_remove_vp:
            self.p.stackup.remove_via_pair(l)

    def move(self, index: int, direction: int) -> None:
        a = self.layers[index]

        self.layers[index] = self.layers[index + direction]
        self.layers[index + direction] = a

        first_row = min(index, index + direction)
        second_row = max(index, index + direction)

        self.dataChanged.emit(self.index(first_row, 0),
                              self.index(second_row, self.columnCount(None)))

    def layer(self, n: int) -> 'Optional[EditableLayer]':
        if n >= len(self.layers):
            return None

        return self.layers[n]

    def viapair(self, n: int) -> 'Optional[EditableVP]':
        if n >= len(self.via_pairs):
            return None
        return self.via_pairs[n]

    def add_layer(self, idx: int) -> None:
        self.layoutAboutToBeChanged.emit()

        col = colorsys.hsv_to_rgb(random.random(), 1, 1)

        l = EditableLayer(self, None, "New Layer", col)
        self.layers.insert(idx, l)
        self.layoutChanged.emit()

    def del_layer(self, idx: int) -> None:
        self.layoutAboutToBeChanged.emit()
        del self.layers[idx]
        self.layoutChanged.emit()

    def layer_count(self) -> int:
        return len(self.layers)

    def add_via_pair(self) -> bool:
        if len(self.layers) >= 2:
            self.layoutAboutToBeChanged.emit()
            self.via_pairs.append(EditableVP(self, None, self.layers[0], self.layers[-1]))
            self.layoutChanged.emit()
            return True
        else:
            return False

    #def layerChanged(self, layer: 'EditableLayer') -> None:
    #    ra = self.index(layer.index, 0)
    #    rb = self.index(layer.index, len(self.via_pairs) + FIRST_VP_COL)
    #    self.dataChanged.emit(ra, rb)

    def via_pair_changed(self, vp: 'EditableVP') -> None:
        va = self.index(0, vp.index + FIRST_VP_COL)
        vb = self.index(len(self.layers), vp.index + FIRST_VP_COL)
        self.dataChanged.emit(va, vb)

    def via_pair_set_top(self, vp: 'EditableVP', layer: 'EditableLayer') -> None:
        vp.startLayer = layer
        self.via_pair_changed(vp)

    def via_pair_set_bottom(self, vp: 'EditableVP', layer: 'EditableLayer') -> None:
        vp.endLayer = layer
        self.via_pair_changed(vp)

    def del_via_pair(self, vp: 'EditableVP') -> None:
        self.layoutAboutToBeChanged.emit()

        del self.via_pairs[self.via_pairs.index(vp)]

        self.layoutChanged.emit()

    def rowCount(self, parent: QtCore.QModelIndex) -> int:
        return len(self.layers)

    def columnCount(self, parent: Optional[QtCore.QModelIndex]) -> int:
        return FIRST_VP_COL + len(self.via_pairs)

    def data(self, index: QtCore.QModelIndex, role: int) -> Any:
        if not index.isValid():
            return None

        col = index.column()
        row = index.row()

        if role == QtCore.Qt.DisplayRole:
            if col == 0:
                return self.layers[row].name

            return None

        elif role == QtCore.Qt.BackgroundRole:
            if col == NAME_COL:
                return None

            elif col >= FIRST_VP_COL:
                vp = self.via_pairs[col - FIRST_VP_COL]
                if vp.start_index <= row <= vp.end_index:
                    return QtGui.QBrush(QtGui.QColor(0, 0, 0))
                return None

        return None

    def setData(self, index: QtCore.QModelIndex, data: Any, role: int) -> bool:

        if len(data) > 0:
            self.set_layer_name(index.row(), data)
            return True

        return False

    def set_layer_name(self, row: int, data: str) -> None:
        self.layers[row].name = data
        self.dataChanged.emit(self.index(row, 0), self.index(row, 0))

    def flags(self, index: QtCore.QModelIndex) -> QtCore.Qt.ItemFlags:
        col = index.column()
        row = index.row()

        flags = QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable

        if col == 0:
            flags |= QtCore.Qt.ItemIsEditable
            flags |= QtCore.Qt.ItemIsDragEnabled | QtCore.Qt.ItemIsDropEnabled

        return cast(QtCore.Qt.ItemFlags, flags)

    def headerData(self, index: int, orientation: QtCore.Qt.Orientation, role: int) -> Any:
        if orientation == QtCore.Qt.Horizontal and role == QtCore.Qt.DisplayRole:
            if index == 0:
                return "Layer Name"
            else:
                return "Via pair"
        elif orientation == QtCore.Qt.Vertical and role == QtCore.Qt.BackgroundRole:
            colors = [int(i * 255) for i in self.layers[index].color]
            return QtGui.QBrush(QtGui.QColor(*colors))

        return None
