from pcbre.ui.widgets.lineedit import PLineEdit

__author__ = 'davidc'
from collections import OrderedDict
from qtpy import QtCore, QtWidgets

class UnitGroup(object):
    def __init__(self, items, default_index=0):
        self.units = OrderedDict(items)
        self.by_name = dict(reversed(i) for i in enumerate(self.units.keys()))
        self.by_scalefactor = dict(reversed(i) for i in enumerate(self.units.values()))
        self.__default_index = default_index

    def idx_by_name(self, name):
        return self.by_name[name]

    def idx_by_scale(self, scale):
        return self.by_scale[scale]

    def get_scale(self, idx):
        return list(self.units.values())[idx]

    def get_name(self, idx):
        return list(self.units.keys())[idx]

    @property
    def names(self):
        return list(self.units.keys())

    @property
    def default_index(self):
        return self.__default_index


UNIT_GROUP_MM = UnitGroup([("\u00B5m", 1), ("mm", 1000), ("in", 25400)], 1)
UNIT_GROUP_PX = UnitGroup([("px", 1)])

class UnitLineEdit(QtWidgets.QWidget):
    edited = QtCore.Signal()

    def __init__(self, unitGroup, field_type=int):
        super(UnitLineEdit, self).__init__()
        self.unit_idx = 0
        self._value = 0
        self._field_type = float

        self.layout = QtWidgets.QHBoxLayout()
        self.layout.setContentsMargins(0,0,0,0)

        self.__lineEdit = PLineEdit()
        self.__lineEdit.editingFinished.connect(self.text_changed)

        self.__unitDropDown = QtWidgets.QComboBox()
        self.__unitDropDown.currentIndexChanged.connect(self.indexChanged)

        self._placeholder_value = None

        self.setLayout(self.layout)
        self.layout.addWidget(self.__lineEdit, 0)
        self.layout.addWidget(self.__unitDropDown, 1)

        self.setUnitGroup(unitGroup)

    def setPlaceholderText(self, text):
        self.__lineEdit.setPlaceholderText(text)

    def setPlaceholderValue(self, value):
        self._placeholder_value = value
        self.update_field_value()

    def resize(self, w, h):
        super(UnitLineEdit, self).resize(w, h)

    def setUnitGroup(self, ug):
        self.__unitGroup = ug
        self.__unitDropDown.clear()
        for k in ug.names:
            self.__unitDropDown.addItem(k)

        self.__unitDropDown.setCurrentIndex(ug.default_index)

    def indexChanged(self, idx):
        self.unit_idx = idx
        self.update_field_value()

    def setUnitName(self, unitname):
        pass

    def getUnitName(self):
        pass

    def setEnabled(self, enabled):
        self.__unitDropDown.setEnabled(enabled)
        self.__lineEdit.setEnabled(enabled)

    def setValue(self, value):
        self._value = value
        self.update_field_value()

    def update_field_value(self):
        scale = self.__unitGroup.get_scale(self.unit_idx)
        if self._value is None:
            self.__lineEdit.setText("")
        else:
            self.__lineEdit.setText("%s" % (self._value / float(scale)))

        if self._placeholder_value is None:
            self.__lineEdit.setPlaceholderText("")
        else:
            self.__lineEdit.setPlaceholderText("%s" % (self._placeholder_value / float(scale)))

    def text_changed(self):
        v = self.__lineEdit.text()
        scale = self.__unitGroup.get_scale(self.unit_idx)

        if v == "":
            newvalue = None
        else:
            newvalue = float(v) * scale

        if newvalue != self._value:
            self._value = newvalue
            self.edited.emit()

    def getValue(self):
        return self._value

    @property
    def suppress_enter(self):
        return self.__lineEdit.suppress_enter

    @suppress_enter.setter
    def suppress_enter(self, v):
        self.__lineEdit.suppress_enter = v

