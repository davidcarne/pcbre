from pcbre import units
from pcbre.matrix import Point2, Vec2, projectPoint, rotate, translate
from pcbre.model.const import SIDE
from pcbre.model.dipcomponent import DIPComponent, SIPComponent
from pcbre.ui.tools.multipoint import MultipointEditFlow, EditablePoint, OffsetDefaultPoint


__author__ = 'davidc'
from PySide import QtCore
from pcbre.ui.dialogs.settingsdialog import AutoSettingsWidget, LineEditable, IntTrait, UnitEditable
from pcbre.ui.uimodel import mdlacc, GenModel
from pcbre.ui.widgets.unitedit import UNIT_GROUP_MM
import math


class SIPEditFlow(MultipointEditFlow):
    def __init__(self, view, model, cmodel):
        self._model = model
        self._cmodel = cmodel

        self.p1_point = EditablePoint(Point2(0,0))


        rmat = rotate(self._cmodel.theta)

        dy = -(model.pin_count / 2 - 1) * model.pin_space


        v_aligned = Vec2(0, dy)

        v_delta = projectPoint(rmat, v_aligned)

        # the pin on the end of the same row as P1
        self.p_bottom_corner = OffsetDefaultPoint(self.p1_point, v_delta)

        points = [self.p1_point, self.p_bottom_corner]

        super(SIPEditFlow, self).__init__(view, points, True)


        self.update_matrix()


    def updated(self, ep):

        if self.p_bottom_corner.is_set and self.p1_point.is_set:
            dv = self.p_bottom_corner.get() - self.p1_point.get()

            # Calculate theta from placement
            theta = math.atan2(dv.y, dv.x) + math.pi/2
            self._cmodel.theta = theta

            # Calculate pin count
            self._model.pin_count = int(round(dv.mag() / self._model.pin_space)) + 1

        self.update_matrix()

    def update_matrix(self):

        rot = rotate(self._cmodel.theta)

        center_to_corner = Vec2(0, self._model.pin_space * (self._model.pin_count - 1) / 2)

        center_to_corner_w = projectPoint(rot, center_to_corner)

        self._cmodel.center = self.p1_point.get() - center_to_corner_w

        self.matrix = translate(self._cmodel.center.x, self._cmodel.center.y).dot(rotate(self._cmodel.theta))




class SIPModel(GenModel):
    def __init__(self):
        super(SIPModel, self).__init__()


    changed = QtCore.Signal()

    pin_count = mdlacc(14)
    pin_space = mdlacc(units.IN_10)
    pad_diameter = mdlacc(units.MM * 1.6)



class SIPEditWidget(AutoSettingsWidget):
    def __init__(self, icmdl):
        super(SIPEditWidget, self).__init__()

        self.mdl = icmdl

        # PinCount
        self.pincw = self.addEdit("Pin Count", LineEditable(self.mdl, "pin_count", IntTrait))

        self.addEdit("(e) Pin spacing (along length)", UnitEditable(self.mdl, "pin_space", UNIT_GROUP_MM))
        self.addEdit("PCB Pad diameter", UnitEditable(self.mdl, "pad_diameter", UNIT_GROUP_MM))


def SIP_getComponent(mdl, ctrl, flow):
    ctrl.flow.update_matrix()
    return SIPComponent(flow.center, flow.theta, ctrl.view.current_side(), ctrl.view.project,
                        mdl.pin_count, mdl.pin_space, mdl.pad_diameter)
