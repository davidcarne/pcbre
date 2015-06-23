from PySide import QtCore, QtGui
from pcbre import units
from pcbre.matrix import Point2, Vec2
from pcbre.model.const import SIDE
from pcbre.model.passivecomponent import PassiveComponent, PassiveSymType, PassiveBodyType
from pcbre.ui.dialogs.settingsdialog import AutoSettingsWidget, UnitEditable, PointUnitEditable
from pcbre.ui.tools.multipoint import EditablePoint, OffsetDefaultPoint, MultipointEditFlow
from pcbre.ui.uimodel import GenModel, mdlacc
from pcbre.ui.widgets.unitedit import UNIT_GROUP_MM

__author__ = 'davidc'

from collections import namedtuple

_well_known_t = namedtuple("well_known", ["name", "body_type", "pin_d", "body_size", "pad_size"])

def _wkchip(name):
    n, _ = name.split('/')
    l = int(n[:2])/10 * units.MM
    w = int(n[2:4])/10 * units.MM
    return _well_known_t(name, PassiveBodyType.CHIP, l, Point2(l, w), Point2(w, w))


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
class PassiveModel(GenModel):
    def __init__(self):
        super(PassiveModel, self).__init__()
        self.well_known = None
        self.__pin_d = 0.3 * units.IN
        self.__body_corner = Point2(0.15 * units.IN, 0.05 * units.IN)
        self.__pin_corner = Point2(0.05 * units.IN, 0.05 * units.IN)

    changed = QtCore.Signal()

    snap_well = mdlacc(True)
    
    sym_type = mdlacc(PassiveSymType.TYPE_RES)
    body_type = mdlacc(PassiveBodyType.CHIP)


    @property
    def pin_d(self):
        if self.well_known:
            return self.well_known.pin_d
        return self.__pin_d

    @pin_d.setter
    def pin_d(self, v):
        self.__pin_d = v
        self.changed.emit()

    @property
    def body_corner_vec(self):
        if self.well_known:
            return self.well_known.body_size
        return self.__body_corner

    @body_corner_vec.setter
    def body_corner_vec(self, v):
        self.__body_corner = v
        self.changed.emit()

    @property
    def pin_corner_vec(self):
        if self.well_known:
            return self.well_known.pad_size
        return self.__pin_corner

    @pin_corner_vec.setter
    def pin_corner_vec(self, v):
        self.__pin_corner = v
        self.changed.emit()




class PassiveEditFlow(MultipointEditFlow):
    def __init__(self, view, model):
        self.view = view
        self.model = model
        
        self.first_point = EditablePoint(Point2(0,0))

        self.theta = 0

        self.side = SIDE.Top

        def other_point():
            return Vec2.fromPolar(self.theta, self.model.pin_d)

        self.second_point = OffsetDefaultPoint(self.first_point, other_point)

        super(PassiveEditFlow, self).__init__(self.view, [self.first_point, self.second_point], True)

    def updated(self, ep):
        v = (self.second_point.get() - self.first_point.get())
        self.theta = v.angle()
        self.model.pin_d = v.mag()

    @property
    def center(self):
        return self.first_point.get() / 2 + self.second_point.get() / 2

class PassiveEditWidget(AutoSettingsWidget):

    def __add_wk(self, wk, name_override = None):
        if name_override:
            name = name_override
        else:
            name = wk.name

        idx = self.cb_well_known.count()
        self.cb_well_known.addItem(name)
        self.__idx_to_wk[idx] = wk
        self.__wk_to_idx[wk] = idx

    def __init__(self, model):
        super(PassiveEditWidget, self).__init__()
        self.__model = model

        self.__idx_to_wk = {}
        self.__wk_to_idx = {}

        self.cb_well_known = QtGui.QComboBox()
        self.layout.addRow("Package", self.cb_well_known)

        self.__add_wk(None, "Custom")
        self.cb_well_known.insertSeparator(self.cb_well_known.maxCount())

        for v in well_known_chip:
            self.__add_wk(v)

        self.cb_well_known.currentIndexChanged.connect(self.pkg_changed)
        self.cb_well_known.setCurrentIndex(self.__wk_to_idx[self.__model.well_known])
        self.pkg_changed(self.cb_well_known.currentIndex())

        # Snap checkbox
        self.cb_snap = QtGui.QCheckBox()
        self.cb_snap.setChecked(self.__model.snap_well)
        self.layout.addRow("Snap to Well Known", self.cb_snap)

        self.gs = [
            self.addEdit("Pad Centers", UnitEditable(self.__model, "pin_d", UNIT_GROUP_MM)),
            self.addEdit("Body length", PointUnitEditable(self.__model, "body_corner_vec", "x", UNIT_GROUP_MM)),
            self.addEdit("Body width", PointUnitEditable(self.__model, "body_corner_vec", "y", UNIT_GROUP_MM)),

            self.addEdit("Pad length", PointUnitEditable(self.__model, "pin_corner_vec", "x", UNIT_GROUP_MM)),
            self.addEdit("Pad width", PointUnitEditable(self.__model, "pin_corner_vec", "y", UNIT_GROUP_MM)),
            ]

    def snap_ui_changed(self):
        en =False
        for i in self.gs:
            self.gs.setEnabled(en)

    def pkg_changed(self, idx):
        self.well_known= self.__idx_to_wk[idx]

    def save(self):
        if self.well_known is None:
            super(PassiveEditWidget, self).save()
        self.__model.well_known = self.well_known
        self.__model.snap_well = self.cb_snap.isChecked()

def Passive_getComponent(model, ctrl, flow):
    return PassiveComponent(flow.center, flow.theta, flow.side,
                            model.sym_type, model.body_type, model.pin_d/2,
                            model.body_corner_vec/2, model.pin_corner_vec/2,
                            side_layer_oracle=ctrl.project)
