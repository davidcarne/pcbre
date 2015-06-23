from pcbre import units
from pcbre.matrix import Point2, Vec2, projectPoint, rotate, translate
from pcbre.model.const import SIDE
from pcbre.model.dipcomponent import DIPComponent
from pcbre.ui.tools.multipoint import MultipointEditFlow, EditablePoint, OffsetDefaultPoint


__author__ = 'davidc'
from PySide import QtCore
from pcbre.ui.dialogs.settingsdialog import AutoSettingsWidget, LineEditable, IntTrait, UnitEditable
from pcbre.ui.uimodel import mdlacc, GenModel
from pcbre.ui.widgets.unitedit import UNIT_GROUP_MM
import math

TR_X = math.cos(math.radians(30))
TR_Y = math.sin(math.radians(30))


class WidthProjectedPoint:
    def __init__(self, parent):
        self.is_set = False
        self.parent = parent
        self.enabled = True

    def __baseline(self):
        baseline_vec = (self.parent.p1_point.get() - self.parent.p_bottom_corner.get()).norm()
        baseline_vec_r = Point2(baseline_vec.y, -baseline_vec.x)
        return baseline_vec_r

    def set(self, v):
        baseline_vec_r = self.__baseline()
        dv = v - self.parent.p_bottom_corner.get()
        v_d = dv.dot(baseline_vec_r)

        self.parent.side = SIDE.Bottom if v_d < 0 else SIDE.Top
        self.parent._model.pin_width = abs(v_d)

    def unset(self, v):
        pass

    def get(self):
        sign = 1
        if self.parent.side == SIDE.Bottom:
            sign = -1

        baseline_vec_r = self.__baseline() * self.parent._model.pin_width * sign
        return self.parent.p_bottom_corner.get() + baseline_vec_r


    def save(self):
        return self.parent._model.pin_width

    def restore(self, v):
        self.parent._model.pin_width = v


class DIPEditFlow(MultipointEditFlow):
    def __init__(self, view, model):
        self._model = model

        self.p1_point = EditablePoint(Point2(0,0))

        self.__theta = 0
        self.__corner = Point2(0,0)

        rmat = rotate(self.theta)

        dy = -(model.pin_count / 2 - 1) * model.pin_space


        v_aligned = Vec2(0, dy)

        v_delta = projectPoint(rmat, v_aligned)

        # the pin on the end of the same row as P1
        self.p_bottom_corner = OffsetDefaultPoint(self.p1_point, v_delta)

        # Opposite corner point
        self.p_opposite = WidthProjectedPoint(self)

        points = [self.p1_point, self.p_bottom_corner, self.p_opposite]

        super(DIPEditFlow, self).__init__(view, points, True)

        if self.view.viewState.current_layer is None:
            self.side = SIDE.Top

        else:
            self.side = self.view.viewState.current_layer.side

        self.update_matrix()


    def updated(self, ep):

        if self.p_bottom_corner.is_set and self.p1_point.is_set:
            dv = self.p_bottom_corner.get() - self.p1_point.get()

            # Calculate theta from placement
            theta = math.atan2(dv.y, dv.x) + math.pi/2
            self.__theta = theta

            # Calculate pin count
            self._model.pin_count = int(round(dv.mag() / self._model.pin_space)) * 2 + 2

        self.update_matrix()

    def update_matrix(self):

        rot = rotate(self.theta)

        if self.side == SIDE.Top:
            sign = -1
        else:
            sign = 1

        center_to_corner = Vec2(sign * self._model.pin_width/2,
                                self._model.pin_space * (self._model.pin_count / 2 - 1) / 2)

        center_to_corner_w = projectPoint(rot, center_to_corner)

        self.center = self.p1_point.get() - center_to_corner_w

        self.matrix = translate(self.center.x, self.center.y).dot(rotate(self.theta))

    @property
    def theta(self):
        return self.__theta



class DIPModel(GenModel):
    def __init__(self):
        super(DIPModel, self).__init__()
        

    changed = QtCore.Signal()

    pin_count = mdlacc(14)

    pin_space = mdlacc(units.IN_10)
    pin_width = mdlacc(units.IN_10 * 3)
    pad_diameter = mdlacc(units.MM * 1.6)
    
    

class DIPEditWidget(AutoSettingsWidget):
    def __init__(self, icmdl):
        super(DIPEditWidget, self).__init__()

        self.mdl = icmdl

        # PinCount
        self.pincw = self.addEdit("Pin Count", LineEditable(self.mdl, "pin_count", IntTrait))

        self.addEdit("(e) Pin spacing (along length)", UnitEditable(self.mdl, "pin_space", UNIT_GROUP_MM))
        self.addEdit("(E) Pin spacing (across width)", UnitEditable(self.mdl, "pin_width", UNIT_GROUP_MM))

        self.addEdit("PCB Pad diameter", UnitEditable(self.mdl, "pad_diameter", UNIT_GROUP_MM))


def DIP_getComponent(mdl, ctrl, flow):
    return DIPComponent(flow.center, flow.theta, flow.side, ctrl.project,
                        mdl.pin_count, mdl.pin_space, mdl.pin_width, mdl.pad_diameter)
