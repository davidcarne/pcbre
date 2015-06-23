from pcbre.ui.uimodel import GenModel

__author__ = 'davidc'


from PySide import QtGui, QtCore

VISIBLE_NO = 0
VISIBLE_MAYBE = 1
VISIBLE_YES = 2

class VisibilityModelLeaf(object):
    def __init__(self, name):
        super(VisibilityModelLeaf, self).__init__()
        self.name = name
        self._visible = VISIBLE_YES
        self.model = None

    @property
    def children(self):
        return frozenset()

    @property
    def visible(self):
        if self._visible:
            return VISIBLE_YES
        return VISIBLE_NO

    def setVisible(self, visible):
        self._visible = visible
        self.model.change()

class VisibilityModelGroup(object):
    def __init__(self, name):
        super(VisibilityModelGroup, self).__init__()
        self.__children = []
        self.name = name

    def addChild(self, child):
        self.__children.append(child)

    @property
    def children(self):
        return list(self.__children)

    @property
    def visible(self):
        child_vis = [i.visible for i in self.children]
        if all(i == VISIBLE_YES for i in child_vis):
            return VISIBLE_YES
        if all(i == VISIBLE_NO for i in child_vis):
            return VISIBLE_NO

        return VISIBLE_MAYBE

    def setVisible(self, visible):
        with self.model.edit():
            for i in self.children:
                i.setVisible(visible)



class VisibilityModel(GenModel):
    def __init__(self):
        super(VisibilityModel, self).__init__()
        self.__children = []

    def addChild(self, child):
        self.__children.append(child)

    def propagate_model(self, node=None):
        if node is None:
            node = self

        for i in node.children:
            i.model = self
            self.propagate_model(i)

    @property
    def children(self):
        return list(self.__children)

class VisibilityAdaptor(QtCore.QAbstractItemModel):

    @staticmethod
    def recursive_stuff_parent(parent):
        for i in parent.children:
            i.__adaptor_parent = parent
            VisibilityAdaptor.recursive_stuff_parent(i)

    def __init__(self, model):
        super(VisibilityAdaptor, self).__init__()
        self.model = model

        # Build parent links
        self.recursive_stuff_parent(self.model)
        self.model.__adaptor_parent = None

    def index_get_node(self, index):
        if not index.isValid():
            obj = self.model
        else:
            obj = index.internalPointer()
        return obj

    def index(self, row, col, parent):
        obj = self.index_get_node(parent)

        assert 0 <= col < 2
        assert 0 <= row < len(obj.children)

        child = obj.children[row]

        idx = self.createIndex(row, col, child)
        return idx

    def node_row(self, node):
        # parent of the parent to get the row
        parent = node.__adaptor_parent
        if parent is None:
            row = 0
        else:
            row = parent.children.index(node)
        return row

    def parent(self, index):
        node = self.index_get_node(index)
        p_obj = node.__adaptor_parent

        if p_obj is None:
            return QtCore.QModelIndex()

        row = self.node_row(p_obj)

        return self.createIndex(row, 0, p_obj)

    def columnCount(self, index):
        return 2

    def rowCount(self, index):
        obj = self.index_get_node(index)
        return len(obj.children)

    def data(self, index, role):
        node = self.index_get_node(index)

        col = index.column()
        if role == QtCore.Qt.DisplayRole:
            if col == 0:
                return node.name

            return ""

        elif role == QtCore.Qt.CheckStateRole:
            if col == 1:
                vis = node.visible
                if vis == VISIBLE_NO:
                    return QtCore.Qt.Unchecked
                elif vis == VISIBLE_YES:
                    return QtCore.Qt.Checked
                else:
                    return QtCore.Qt.PartiallyChecked

    def flags(self, index):
        node = self.index_get_node(index)

        flags = QtCore.Qt.ItemIsEnabled

        if index.column() == 1:
            flags |= QtCore.Qt.ItemIsUserCheckable

        return flags

    def __recursive_emit_changed(self, node):
        if not node.children:
            return

        tl = self.createIndex(0, 1, node.children[0])
        br = self.createIndex(len(node.children) - 1, 1, node.children[-1])
        self.dataChanged.emit(tl, br)

        for i in node.children:
            self.__recursive_emit_changed(i)

    def setData(self, index, data, role):
        node = self.index_get_node(index)
        if index.column() == 1 and role == QtCore.Qt.CheckStateRole:
            node.setVisible(data)

            # Update heirarchy above
            n_i = node
            while n_i is not None:
                ci = self.createIndex(self.node_row(n_i), 1, n_i)
                self.dataChanged.emit(ci, ci)
                n_i = n_i.__adaptor_parent

            # Update heirarchy below
            self.__recursive_emit_changed(node)

            return True

        return False





class VisibilityTree(QtGui.QTreeView):
    def __init__(self, model):
        super(VisibilityTree, self).__init__()
        self.model = model
        self.adaptor = VisibilityAdaptor(model)

        self.setModel(self.adaptor)
        header = self.header()
        header.setStretchLastSection(False)

        header.setResizeMode(0,QtGui.QHeaderView.Stretch)
        header.setResizeMode(1,QtGui.QHeaderView.ResizeToContents)
        header.hide()



if __name__ == "__main__":
    app = QtGui.QApplication([])

    model = VisibilityModel()
    child1 = VisibilityModelLeaf("test1")
    model.addChild(child1)

    group1 = VisibilityModelGroup("group-level-1")
    model.addChild(group1)

    group2 = VisibilityModelGroup("group-level-1")
    child2 = VisibilityModelLeaf("leaf2")
    group2.addChild(child2)
    group1.addChild(group2)

    child3 = VisibilityModelLeaf("leaf1")
    group1.addChild(child3)
    model.propagate_model()


    widg = VisibilityTree(model)
    widg.show()
    widg.resize(100,500)

    app.exec_()

