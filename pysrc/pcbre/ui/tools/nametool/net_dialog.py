from pcbre.model.const import TFF
from pcbre.model.pad import Pad

__author__ = 'davidc'

from qtpy import QtCore, QtGui, QtWidgets

class NetDialog(QtWidgets.QDialog):
    def __init__(self, project, parent, obj):
        super(NetDialog, self).__init__(parent)

        self.project = project

        buttonBox = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel,
                                           QtCore.Qt.Horizontal, self)
        buttonBox.accepted.connect(self.accept)
        buttonBox.rejected.connect(self.reject)

        self.mainLayout = QtGui.QVBoxLayout()
        self.setLayout(self.mainLayout)


        self.obj = obj
        self.mainLayout.setSizeConstraint(QtGui.QLayout.SetMinAndMaxSize)

        if self.obj.TYPE_FLAGS & TFF.HAS_NET:
            self.net_name_input = QtGui.QLineEdit(self)
            self.net_name_input.setText(obj.net.name)

            name_label = QtGui.QLabel("Net Name")
            name_label.setBuddy(self.net_name_input)

            self.class_input = QtGui.QLineEdit(self)
            self.class_input.setText(obj.net.net_class)

            class_label = QtGui.QLabel("Net Class")
            class_label.setBuddy(self.class_input)

            self.mainLayout.addWidget(name_label)
            self.mainLayout.addWidget(self.net_name_input)
            self.mainLayout.addWidget(class_label)
            self.mainLayout.addWidget(self.class_input)

        self.cmp = None

        if isinstance(obj, Pad):
            # Pad Name
            self.pad_name_input = QtGui.QLineEdit(self)
            self.pad_name_input.setText(obj.pad_name)

            pad_name_label = QtGui.QLabel("Pad (%s) Name" % obj.pad_no)
            pad_name_label.setBuddy(self.pad_name_input)

            self.mainLayout.addWidget(pad_name_label)
            self.mainLayout.addWidget(self.pad_name_input)

            self.cmp = obj.parent

        elif obj.TYPE_FLAGS & TFF.HAS_INST_INFO:
            self.cmp = obj

        if self.cmp:
            self.refdes_input = QtGui.QLineEdit(self)
            self.refdes_input.setText(self.cmp.refdes)
            refdes_label = QtGui.QLabel("Component Reference Designator")
            refdes_label.setBuddy(self.refdes_input)

            self.partname_input = QtGui.QLineEdit(self)
            self.partname_input.setText(self.cmp.partno)
            partname_label = QtGui.QLabel("Component Part Number")
            partname_label.setBuddy(self.partname_input)

            self.mainLayout.addWidget(refdes_label)
            self.mainLayout.addWidget(self.refdes_input)
            self.mainLayout.addWidget(partname_label)
            self.mainLayout.addWidget(self.partname_input)

        self.mainLayout.addWidget(buttonBox)


    def accept(self):
        super(NetDialog, self).accept()

        if self.obj.TYPE_FLAGS & TFF.HAS_NET:
            self.obj.net.name = str(self.net_name_input.text())
            self.obj.net.net_class = str(self.class_input.text())

        if isinstance(self.obj, Pad):
            self.obj.pad_name = str(self.pad_name_input.text())

            # Bump the components generation to force a component redraw
            self.project.artwork.components_generation += 1

        if self.cmp:
            self.cmp.refdes = str(self.refdes_input.text())
            self.cmp.partno = str(self.partname_input.text())

            # Bump the components generation to force a component redraw
            self.project.artwork.components_generation += 1



