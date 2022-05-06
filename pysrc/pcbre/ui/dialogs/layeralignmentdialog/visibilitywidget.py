from pcbre.ui.uimodel import GenModel
from qtpy import QtGui, QtCore, QtWidgets
import enum
__author__ = 'davidc'
from typing import Any, List, Optional, List, Dict


try:
    from typing_extensions import Protocol
    class VisibilityNode(Protocol):
        @property
        def name(self) -> str:
            ...

        @property
        def root_node(self) -> 'Optional[VisibilityModelRoot]':
            ...

        @root_node.setter
        def root_node(self, value: 'VisibilityModelRoot') -> None:
            ...

        @property
        def children(self) -> 'List[VisibilityNode]':
            ...
        
        @property
        def visible(self) -> 'Visible':
            ...
        
        def setVisible(self, visible: 'Visible') -> None:
            ...

        @property
        def obj(self) -> Any:
            ...

except ImportError:
    pass


class Visible(enum.Enum):
    """MAYBE enum type indicates that some children are visible. 
        Only returned for non-leaf nodes"""
    NO = 0
    MAYBE = 1
    YES = 2

    def as_qt_vis(self) -> 'QtCore.Qt.CheckState':
        if self == Visible.NO:
            return QtCore.Qt.Unchecked
        elif self == Visible.YES:
            return QtCore.Qt.Checked
        else:
            return QtCore.Qt.PartiallyChecked

    @staticmethod
    def from_qt_state(s: 'QtCore.Qt.CheckState') -> 'Visible':
        if s == QtCore.Qt.Unchecked:
            return Visible.NO
        elif s == QtCore.Qt.Checked:
            return Visible.YES
        elif s == QtCore.Qt.PartiallyChecked:
            return Visible.MAYBE
        else:
            raise ValueError("Invalid argument %s" % s)



class VisibilityModelLeaf:
    def __init__(self, name: str, obj: Any = None) -> None:
        super(VisibilityModelLeaf, self).__init__()
        self.__name: str = name
        self._visible: Visible = Visible.YES
        self.obj = obj
        self.__root_node : Optional[VisibilityModelRoot] = None


    @property
    def root_node(self) -> 'Optional[VisibilityModelRoot]':
        return self.__root_node

    @root_node.setter
    def root_node(self, value: 'VisibilityModelRoot') -> None:
        self.__root_node = value

    @property
    def name(self) -> str:
        return self.__name

    @property
    def children(self) -> 'frozenset[Any]':
        return frozenset()

    @property
    def visible(self) -> Visible:
        return self._visible

    def setVisible(self, visible: Visible) -> None:
        self._visible = visible
        if self.root_node is not None:
            self.root_node.change()

class VisibilityModelGroup:
    def __init__(self, name: str):
        super(VisibilityModelGroup, self).__init__()
        self.__children : 'List[VisibilityNode]' = []
        self.__name = name
        self.__root_node: Optional[VisibilityModelRoot] = None
        self.obj: Any = None

    @property
    def root_node(self) -> 'Optional[VisibilityModelRoot]':
        return self.__root_node

    @root_node.setter
    def root_node(self, value: 'VisibilityModelRoot') -> None:
        self.__root_node = value

    @property
    def name(self) -> str:
        return self.__name

    def addChild(self, child: 'VisibilityNode') -> None:
        self.__children.append(child)

    @property
    def children(self) -> 'List[VisibilityNode]':
        return list(self.__children)

    @property
    def visible(self) -> 'Visible':
        child_vis = [i.visible for i in self.children]
        if all(i == Visible.YES for i in child_vis):
            return Visible.YES
        if all(i == Visible.NO for i in child_vis):
            return Visible.NO

        return Visible.MAYBE

    def setVisible(self, visible: Visible) -> None:
        if self.root_node is not None:
            with self.root_node.edit():
                for i in self.children:
                    i.setVisible(visible)


class VisibilityModelRoot(GenModel):
    def __init__(self) -> None:
        super(VisibilityModelRoot, self).__init__()
        self.__children : 'List[VisibilityNode]' = []

    @property
    def name(self) -> str:
        return ""

    def addChild(self, child: 'VisibilityNode') -> None:
        self.__children.append(child)

    # this is a very strange way of phrasing it. review?
    def propagate_root(self, child: 'Optional[VisibilityNode]'=None) -> None:
        _child: VisibilityNode
        if child is None:
            _child = self
        else:
            _child = child

        for i in _child.children:
            i.root_node = self
            self.propagate_root(i)

    @property
    def children(self) -> 'List[VisibilityNode]':
        return list(self.__children)

    @property
    def root_node(self) -> 'Optional[VisibilityModelRoot]':
        return self

    @root_node.setter
    def root_node(self, v: 'VisibilityModelRoot') -> None:
        pass

    @property
    def visible(self) -> 'Visible':
        return Visible.MAYBE

    def setVisible(self, visible: 'Visible') -> None:
        pass

    @property
    def obj(self) -> Any:
        None


class VisibilityAdaptor(QtCore.QAbstractItemModel):
    def __recursive_stuff_parent(self, parent: 'VisibilityNode') -> None:
        for i in parent.children:
            self.__adapter_parents[i] = parent
            self.__recursive_stuff_parent(i)

    def __init__(self, model: VisibilityModelRoot) -> None:
        super(VisibilityAdaptor, self).__init__()
        self.model = model

        self.__adapter_parents: 'Dict[Any, Any]' = dict()
        self.__adapter_parents[self.model] = None

        # Build parent links
        self.__recursive_stuff_parent(self.model)

    def index_get_node(self, index: 'QtCore.QModelIndex') -> 'VisibilityNode':
        if not index.isValid():
            obj = self.model
        else:
            obj = index.internalPointer()
        return obj

    def index(self, row: int, col: int, parent: QtCore.QModelIndex) -> QtCore.QModelIndex:
        obj = self.index_get_node(parent)

        assert 0 <= col < 2
        assert 0 <= row < len(obj.children)

        child = obj.children[row]

        idx = self.createIndex(row, col, child)
        return idx

    def node_row(self, node: 'VisibilityNode') -> int:
        # parent of the parent to get the row

        parent = self.__adapter_parents[node]
        if parent is None:
            row = 0
        else:
            row = parent.children.index(node)
        return row

    def parent(self, index: 'QtCore.QModelIndex') -> 'QtCore.QModelIndex':
        node = self.index_get_node(index)
        p_obj = self.__adapter_parents[node]

        if p_obj is None:
            return QtCore.QModelIndex()

        row = self.node_row(p_obj)

        return self.createIndex(row, 0, p_obj)

    def columnCount(self, index: Any) -> int:
        return 2

    def rowCount(self, index: Any) -> int:
        obj = self.index_get_node(index)
        return len(obj.children)

    def data(self, index: 'QtCore.QModelIndex', role: int) -> Any:
        node = self.index_get_node(index)

        col = index.column()
        if role == QtCore.Qt.DisplayRole:
            if col == 0:
                return node.name
            return ""

        elif role == QtCore.Qt.CheckStateRole:
            if col == 1:
                return node.visible.as_qt_vis()

    def flags(self, index: QtCore.QModelIndex) -> QtCore.Qt.ItemFlags:
        node = self.index_get_node(index)

        flags: int = QtCore.Qt.ItemIsEnabled

        if index.column() == 1:
            flags |= QtCore.Qt.ItemIsUserCheckable

        return flags # type: ignore

    def __recursive_emit_changed(self, node: 'VisibilityNode') -> None:
        if not node.children:
            return

        tl = self.createIndex(0, 1, node.children[0])
        br = self.createIndex(len(node.children) - 1, 1, node.children[-1])
        self.dataChanged.emit(tl, br)

        for i in node.children:
            self.__recursive_emit_changed(i)

    def setData(self, index: QtCore.QModelIndex, data: Any, role: int) -> bool:
        node = self.index_get_node(index)
        if index.column() == 1 and role == QtCore.Qt.CheckStateRole:
            node.setVisible(Visible.from_qt_state(data))

            # Update hierarchy above
            n_i = node
            while n_i is not None:
                ci = self.createIndex(self.node_row(n_i), 1, n_i)
                self.dataChanged.emit(ci, ci)
                n_i = self.__adapter_parents[n_i]

            # Update hierarchy below
            self.__recursive_emit_changed(node)

            return True

        return False


class VisibilityTree(QtWidgets.QTreeView):
    def __init__(self, model: VisibilityModelRoot) -> None:
        super(VisibilityTree, self).__init__()
        self.__model = model
        self.adaptor = VisibilityAdaptor(model)

        self.setModel(self.adaptor)
        header = self.header()
        header.setStretchLastSection(False)

        header.setSectionResizeMode(0,QtWidgets.QHeaderView.Stretch)
        header.setSectionResizeMode(1,QtWidgets.QHeaderView.ResizeToContents)
        header.hide()
