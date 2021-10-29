from pcbre.ui.widgets.lineedit import PLineEdit

from collections import OrderedDict
from qtpy import QtCore, QtWidgets
from typing import Dict, Optional, List, Iterable, Tuple

class UnitGroup:
    def __init__(self, items: Iterable[Tuple[str, int]], default_index: int=0) -> None:
        self.units : Dict[str, int] = OrderedDict(items)

        # Maps from name/scalefactor to unit index
        self.by_name : Dict[str, int]  = dict((i[1], i[0]) for i in enumerate(self.units.keys()))
        self.by_scalefactor: Dict[int, int] = dict((i[1], i[0]) for i in enumerate(self.units.values()))
        self.__default_index = default_index

    def idx_by_name(self, name: str) -> int:
        return self.by_name[name]

    def idx_by_scale(self, scale: int) -> float:
        return self.by_scalefactor[scale]

    def get_scale(self, idx: int) -> int:
        return list(self.units.values())[idx]

    def get_name(self, idx: int) -> str:
        return list(self.units.keys())[idx]

    @property
    def names(self) -> List[str]:
        return list(self.units.keys())

    @property
    def default_index(self) -> int:
        return self.__default_index


UNIT_GROUP_MM = UnitGroup([("\u00B5m", 1), ("mm", 1000), ("in", 25400)], 1)
UNIT_GROUP_PX = UnitGroup([("px", 1)])

class UnitLineEdit(QtWidgets.QWidget):
    edited = QtCore.Signal()

    def __init__(self, unitGroup: UnitGroup) -> None:
        super(UnitLineEdit, self).__init__()
        self.unit_idx : int = 0
        self._value : Optional[float] = 0

        self._layout = QtWidgets.QHBoxLayout()
        self._layout.setContentsMargins(0,0,0,0)

        self.__lineEdit = PLineEdit()

        # Skipping typing - slots don't seem to work
        self.__lineEdit.editingFinished.connect(self.text_changed)

        self.__unitDropDown = QtWidgets.QComboBox()
        self.__unitDropDown.currentIndexChanged.connect(self.indexChanged)

        self._placeholder_value : Optional[float] = None

        self.setLayout(self._layout)
        self._layout.addWidget(self.__lineEdit, 0)
        self._layout.addWidget(self.__unitDropDown, 1)

        self.setUnitGroup(unitGroup)

    def setPlaceholderText(self, text: str) -> None:
        self.__lineEdit.setPlaceholderText(text)

    def setPlaceholderValue(self, value: float) -> None:
        self._placeholder_value = value
        self.update_field_value()

    def setUnitGroup(self, ug: UnitGroup) -> None:
        self.__unitGroup = ug
        self.__unitDropDown.clear()
        for k in ug.names:
            self.__unitDropDown.addItem(k)

        self.__unitDropDown.setCurrentIndex(ug.default_index)

    def indexChanged(self, idx: int) -> None:
        self.unit_idx = idx
        self.update_field_value()

    def setUnitName(self, unitname: str) -> None:
        pass

    def getUnitName(self) -> None:
        pass

    def setEnabled(self, enabled: bool) -> None:
        self.__unitDropDown.setEnabled(enabled)
        self.__lineEdit.setEnabled(enabled)

    def setValue(self, value: Optional[float]) -> None:
        self._value = value
        self.update_field_value()

    def update_field_value(self) -> None:
        scale = self.__unitGroup.get_scale(self.unit_idx)
        if self._value is None:
            self.__lineEdit.setText("")
        else:
            self.__lineEdit.setText("%s" % (self._value / float(scale)))

        if self._placeholder_value is None:
            self.__lineEdit.setPlaceholderText("")
        else:
            self.__lineEdit.setPlaceholderText("%s" % (self._placeholder_value / float(scale)))

    def text_changed(self) -> None:
        v = self.__lineEdit.text()
        scale = self.__unitGroup.get_scale(self.unit_idx)

        newvalue : Optional[float]
        if v == "":
            newvalue = None
        else:
            newvalue = float(v) * scale

        if newvalue != self._value:
            self._value = newvalue

            self.edited.emit()

    def getValue(self) -> Optional[float]:
        if self._value is not None:
            return self._value
        return self._placeholder_value

    def getValueRaw(self) -> Optional[float]:
        return self._value

    @property
    def suppress_enter(self) -> bool:
        return self.__lineEdit.suppress_enter

    @suppress_enter.setter
    def suppress_enter(self, v: bool) -> None:
        self.__lineEdit.suppress_enter = v

