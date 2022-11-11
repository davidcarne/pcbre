from qtpy import QtCore, QtGui, QtWidgets
from pcbre import units
from pcbre.matrix import Point2, Vec2
from pcbre.model.const import SIDE
from pcbre.model.passivecomponent import Passive2Component, PassiveSymType, Passive2BodyType
from pcbre.ui.dialogs.settingsdialog import AutoSettingsWidget, UnitEditable, PointUnitEditable
from pcbre.ui.tools.multipoint import EditablePoint, OffsetDefaultPoint, MultipointEditFlow
from pcbre.ui.uimodel import GenModel, mdlacc
from pcbre.ui.widgets.unitedit import UNIT_GROUP_MM
from typing import Tuple, Optional, NamedTuple, Dict

__author__ = 'davidc'


_well_known_t = NamedTuple("well_known", [
    ("name", str),
    ("body_type", Passive2BodyType),
    ("pin_d", float),
    ("body_size", Vec2),
    ("pad_size", Vec2)])

# Passive SMD "chip" components come in various common sizes.
def _wkchip(name):
    n, _ = name.split('/')
    l = int(n[:2])/10 * units.MM
    w = int(n[2:4])/10 * units.MM
    return _well_known_t(name, Passive2BodyType.CHIP, l, Point2(l, w), Point2(w, w))


well_known_chip = [
    # Sourced from wikipedia
    _wkchip("0402/01005"),
    _wkchip("0603/0201"),
    _wkchip("1005/0402"),
    _wkchip("1608/0603"),
    _wkchip("2012/0805"),
    _wkchip("2520/1008"),
    _wkchip("3216/1206"),
    _wkchip("3225/1210"),
    _wkchip("4516/1806"),
    _wkchip("4532/1812"),
    _wkchip("5025/2010"),
    _wkchip("6332/2512")
]

# TODO: This model should be in one of two states:
# - a well known component is assigned (in which case all values are derived from the well known component)
# - no well known component is assigned (in which case the values are 
class PassiveModel(GenModel):
    def __init__(self):
        super(PassiveModel, self).__init__()
        self.well_known: _well_known_t = None
        self.__pin_d = 0.3 * units.IN
        self.__body_corner = Point2(0.15 * units.IN, 0.05 * units.IN)
        self.__body_type = Passive2BodyType.TH_AXIAL
        self.__pin_corner = Point2(0.05 * units.IN, 0.05 * units.IN)


    snap_well = mdlacc(True)
    
    sym_type = mdlacc(PassiveSymType.TYPE_RES)

    @property
    def body_type(self):
        if self.well_known:
            return self.well_known.body_type
        return self.__body_type

    @body_type.setter
    def body_type(self, v):
        self.__body_type = v

    @property
    def pin_d(self):
        if self.well_known:
            return self.well_known.pin_d
        return self.__pin_d

    @pin_d.setter
    def pin_d(self, v):
        self.__pin_d = v

    @property
    def body_corner_vec(self):
        if self.well_known:
            return self.well_known.body_size
        return self.__body_corner

    @body_corner_vec.setter
    def body_corner_vec(self, v):
        self.__body_corner = v

    @property
    def pin_corner_vec(self):
        if self.well_known:
            return self.well_known.pad_size
        return self.__pin_corner

    @pin_corner_vec.setter
    def pin_corner_vec(self, v):
        self.__pin_corner = v




class PassiveEditFlow(MultipointEditFlow):
    def __init__(self, view, model, cmodel):
        self.view = view
        self.model = model
        self._cmodel = cmodel
        
        self.first_point = EditablePoint(Point2(0,0))



        def other_point():
            return Vec2.from_polar(self._cmodel.theta, self.model.pin_d)

        self.second_point = OffsetDefaultPoint(self.first_point, other_point)

        super(PassiveEditFlow, self).__init__(self.view, [self.first_point, self.second_point], True)

    def updated(self, ep):
        v = (self.second_point.get() - self.first_point.get())
        self._cmodel.center = self.first_point.get() / 2 + self.second_point.get() / 2
        self._cmodel.theta = v.angle()
        self.model.pin_d = v.mag()


class PassiveEditWidget(AutoSettingsWidget):

    def __add_wk(self, wk, name_override: Optional[str] = None):
        if name_override:
            name = name_override
        else:
            name = wk.name

        idx = self.cb_well_known.count()
        self.cb_well_known.addItem(name)
        self.__idx_to_wk[idx] = wk
        self.__wk_to_idx[wk] = idx

    def __init__(self, model: PassiveModel):
        super(PassiveEditWidget, self).__init__()
        self.__model = model

        self.__idx_to_wk : Dict[int, _well_known_t] = {}
        self.__wk_to_idx : Dict[_well_known_t, int] = {}

        self.cb_well_known = QtWidgets.QComboBox()
        self.layout.addRow("Package", self.cb_well_known)

        self.__add_wk(None, "Custom")
        self.cb_well_known.insertSeparator(self.cb_well_known.maxCount())

        for v in well_known_chip:
            self.__add_wk(v)

        self.cb_well_known.setCurrentIndex(self.__wk_to_idx[self.__model.well_known])

        self.cb_well_known.currentIndexChanged.connect(lambda _: self.update_ui())

        # Snap checkbox
        self.cb_snap = QtWidgets.QCheckBox()
        self.cb_snap.setChecked(self.__model.snap_well)
        self.cb_snap.clicked.connect(self.snap_ui_changed)
        self.layout.addRow("Snap to Well Known", self.cb_snap)

        
        
        self.gs = [
            self.addEdit("Pad Centers", UnitEditable(self.__model, "pin_d", UNIT_GROUP_MM)),
            self.addEdit("Body length", PointUnitEditable(self.__model, "body_corner_vec", "x", UNIT_GROUP_MM)),
            self.addEdit("Body width", PointUnitEditable(self.__model, "body_corner_vec", "y", UNIT_GROUP_MM)),

            self.addEdit("Pad length", PointUnitEditable(self.__model, "pin_corner_vec", "x", UNIT_GROUP_MM)),
            self.addEdit("Pad width", PointUnitEditable(self.__model, "pin_corner_vec", "y", UNIT_GROUP_MM)),
            ]


        self.pad_type_select = QtWidgets.QComboBox()
        self.pad_type_select.addItem("SMT Chip Passive", Passive2BodyType.CHIP)
        self.pad_type_select.addItem("SMT Capacitor (electrolytic)", Passive2BodyType.SMD_CAP)
        self.pad_type_select.addItem("T/H Axial", Passive2BodyType.TH_AXIAL)
        self.pad_type_select.addItem("T/H Radial", Passive2BodyType.TH_RADIAL)
        self.pad_type_select.addItem("T/H Radial side", Passive2BodyType.TH_FLIPPED_CAP)
        self.pad_type_select.currentIndexChanged.connect(self.pad_type_changed)

        self.layout.addRow("Body Type", self.pad_type_select)

        self.update_ui()

    def snap_ui_changed(self):
        en = not self.cb_snap.isChecked()

    def pad_type_changed(self, _):
        self.__model.body_type = self.pad_type_select.currentData()

    def update_ui(self):
        idx = self.cb_well_known.currentIndex()

        # Try one of the well-known components
        self.well_known = self.__idx_to_wk[idx]

        en = self.well_known is None

        for i in self.gs:
            i.widget.setEnabled(en)
        self.pad_type_select.setEnabled(en)

        idx = self.pad_type_select.findData(self.__model.body_type)
        self.pad_type_select.setCurrentIndex(idx)

        #if self.well_known is not None:
        #    pkg_type

    def save(self):
        if self.well_known is None:
            super(PassiveEditWidget, self).save()
        self.__model.well_known = self.well_known
        self.__model.snap_well = self.cb_snap.isChecked()

def Passive_getComponent(model, ctrl, flow):
    return Passive2Component(ctrl.project, flow.center, flow.theta, ctrl.view.current_side(),
                             model.sym_type, model.body_type, model.pin_d / 2,
                             model.body_corner_vec / 2, model.pin_corner_vec / 2,
                             side_layer_oracle=ctrl.project)
