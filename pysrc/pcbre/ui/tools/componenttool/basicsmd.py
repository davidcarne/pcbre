from qtpy import QtGui, QtCore, QtWidgets
from pcbre.matrix import Point2, rotate, Vec2, projectPoint, translate, project_point_line
from pcbre.model.const import SIDE
from pcbre.model.smd4component import SMD4Component
from pcbre.ui.dialogs.settingsdialog import AutoSettingsWidget, LineEditable, FloatTrait, IntTrait, UnitEditable
from pcbre.ui.tools.multipoint import MultipointEditFlow, EditablePoint, OffsetDefaultPoint
from pcbre.ui.uimodel import mdlacc, GenModel
from pcbre.ui.widgets.unitedit import UNIT_GROUP_MM
import math


class BodyCornerPoint:
    def __init__(self, parent):
        self.parent = parent
        self.icon = None
        self.is_set = False
        self.enabled = True

    def set(self, val):
        r = rotate(-self.parent._cmodel.theta)
        p = projectPoint(r, val - self.parent._cmodel.center)
        self.parent._model.dim_1_body = abs(p.x) * 2
        self.parent._model.dim_2_body = abs(p.y) * 2

    def get(self):
        r = rotate(self.parent._cmodel.theta)
        cv = Vec2(-self.parent._model.dim_1_body/2, -self.parent._model.dim_2_body/2)
        return self.parent._cmodel.center + projectPoint(r, cv)

    def save(self):
        return self.parent._model.dim_1_body, self.parent._model.dim_2_body

    def restore(self, v):
        self.parent._model.dim_1_body, self.parent._model.dim_2_body = v



class BasicSMDFlow(MultipointEditFlow):
    def __init__(self, view, model, cmodel):
        self._model = model
        self._cmodel = cmodel


        self.p1_point = EditablePoint()

        def corner_offset():
            mag = self._model.pin_spacing * (self._model.side1_pins - 1)
            return Vec2.fromPolar(self._cmodel.theta, mag)

        self.p_bottom_corner = OffsetDefaultPoint(self.p1_point, corner_offset)

        def other_corner_offset():
            x = self._model.pin_spacing * ((self._model.side1_pins - 1) / 2 + (self._model.side3_pins - 1) / 2)
            y = self._model.dim_2_pincenter

            r = rotate(self._cmodel.theta)
            return projectPoint(r, Point2(x, y))

        self.p_side_3_1 = OffsetDefaultPoint(self.p1_point, other_corner_offset)

        def p2_corner_offset():
            x = self._model.pin_spacing * ((self._model.side1_pins - 1) / 2) + self._model.dim_1_pincenter/2
            y = self._model.dim_2_pincenter / 2 - (self._model.side2_pins - 1) / 2 * self._model.pin_spacing

            r = rotate(self._cmodel.theta)
            return projectPoint(r, Point2(x, y))

        def p2_corner_ena():
            return self._model.side2_pins or self._model.side4_pins

        self.p_side_2_1 = OffsetDefaultPoint(self.p1_point, p2_corner_offset, enabled=p2_corner_ena)

        self.p_body_corner = BodyCornerPoint(self)

        points = [self.p1_point, self.p_bottom_corner, self.p_side_3_1, self.p_side_2_1, self.p_body_corner]
        super(BasicSMDFlow, self).__init__(view, points, True)

        self.__update_matrix()

    def updated(self, ep):
        if self.p1_point.is_set:
            if self.p_bottom_corner.is_set:
                v = (self.p_bottom_corner.get() - self.p1_point.get())
                mag = v.mag()
                v = v.norm()
                self._cmodel.theta = v.angle()

                self._model.pin_spacing = mag / (self._model.side1_pins - 1)


            self.v_base = Vec2.fromPolar(self._cmodel.theta, 1)
            self.v_vert = Vec2(-self.v_base.y, self.v_base.x).norm()

            p_edge_center = self.v_base * self._model.pin_spacing * (self._model.side1_pins - 1) / 2


            if self.p_side_3_1.is_set:
                dv = self.p_side_3_1.get() - self.p1_point.get()

                v, _ = project_point_line(dv, Point2(0,0), self.v_vert, False)
                self._model.dim_2_pincenter = v.mag()

            self._cmodel.center = self.v_vert * self._model.dim_2_pincenter / 2 + p_edge_center + self.p1_point.get()

            if self.p_side_2_1.is_set:
                v, _ = project_point_line(self.p_side_2_1.get() - self._cmodel.center, Point2(0,0), self.v_base, False)

                self._model.dim_1_pincenter = v.mag() * 2


    @property
    def side(self):
        return self.view.current_side

    def __update_matrix(self):
        rot = rotate(self._cmodel.theta)

        self.matrix = translate(self._cmodel.center.x, self._cmodel.center.y).dot(rotate(self._cmodel.theta))


SYM_4_SQUARE = 0
SYM_4_RECT = 1
SYM_2 = 2
SYM_ARB = 3


def text_for_sym(sym):
    return {
        SYM_4_SQUARE: "4 sides, square",
        SYM_4_RECT: "4 sides, rectangular",
        SYM_2: "2 sides",
        SYM_ARB: "arbitrary pin layout"
    }[sym]


def guess_sym(s1, s2, s3, s4):
    """
    Figure out the possible IC symmetry based on edge pincounts

    :param s1: Side 1 pincount
    :param s2: Side 2 pincount
    :param s3: Side 3 pincount
    :param s4: Side 4 pincount
    :return: SYM_4_SQUARE | SYM_4_RECT | SYM_2 | SYM_ARB
    """
    if s1 == s2 == s3 == s4 >= 1:
        return SYM_4_SQUARE
    if s1 == s3 >= 1 and s2 == s4 >= 1:
        return SYM_4_RECT
    if s1 == s3 >= 1 and s2 == s4 == 0:
        return SYM_2
    return SYM_ARB

class BasicSMDICEditWidget(AutoSettingsWidget):
    def __init__(self, icmdl):
        super(BasicSMDICEditWidget, self).__init__()

        self.mdl = icmdl
        # Symmetry
        self.symw = QtWidgets.QComboBox()
        syms = [SYM_4_SQUARE, SYM_4_RECT, SYM_2, SYM_ARB]
        for s in syms:
            self.symw.addItem(text_for_sym(s), s)

        self.sym = guess_sym(self.mdl.side1_pins, self.mdl.side2_pins, self.mdl.side3_pins, self.mdl.side4_pins)
        self.symw.setCurrentIndex(self.sym)

        self.layout.addRow("Symmetry", self.symw)
        self.symw.currentIndexChanged.connect(self.sym_changed)

        # PinCount
        self.pin_count = 0
        self.pincw = self.addEdit("Pin Count", LineEditable(self, "pin_count", IntTrait))
        self.pincw.widget.editingFinished.connect(lambda: self.sym_value_changed(True))

        self.s1pw = self.addEdit("Side 1 Pins", LineEditable(self.mdl, "side1_pins", IntTrait))
        self.s1pw.widget.editingFinished.connect(lambda: self.sym_value_changed(False))
        self.s2pw = self.addEdit("Side 2 Pins", LineEditable(self.mdl, "side2_pins", IntTrait))
        self.s2pw.widget.editingFinished.connect(lambda: self.sym_value_changed(False))
        self.s3pw = self.addEdit("Side 3 Pins", LineEditable(self.mdl, "side3_pins", IntTrait))
        self.s3pw.widget.editingFinished.connect(lambda: self.sym_value_changed(False))
        self.s4pw = self.addEdit("Side 4 Pins", LineEditable(self.mdl, "side4_pins", IntTrait))
        self.s4pw.widget.editingFinished.connect(lambda: self.sym_value_changed(False))

        self.addEdit("(D1) Dimension 1 Body", UnitEditable(self.mdl, "dim_1_body", UNIT_GROUP_MM))
        self.addEdit("(D) Dimension 1 Pin Center-to-Center", UnitEditable(self.mdl, "dim_1_pincenter", UNIT_GROUP_MM))
        self.addEdit("(E1) Dimension 2 Body", UnitEditable(self.mdl, "dim_2_body", UNIT_GROUP_MM))
        self.addEdit("(E) Dimension 2 Pin Center-to-Center", UnitEditable(self.mdl, "dim_2_pincenter", UNIT_GROUP_MM))

        self.layout.addWidget(QtWidgets.QLabel("Dimension 1 is along pin 1 edge"))

        self.addEdit("(e) Pin Spacing", UnitEditable(self.mdl, "pin_spacing", UNIT_GROUP_MM))
        self.addEdit("(L) Pin PCB contact length", UnitEditable(self.mdl, "pin_contact_length", UNIT_GROUP_MM))
        self.addEdit("(b) Pin PCB contact width", UnitEditable(self.mdl, "pin_contact_width", UNIT_GROUP_MM))

        self.update_sym_ena()
        self.sym_value_changed(False)

    def sym_changed(self, idx):
        self.sym = idx
        self.update_sym_ena()
        self.sym_value_changed(False)

    def update_sym_ena(self):
        self.pincw.widget.setEnabled(self.sym in [SYM_2, SYM_4_SQUARE])
        self.s1pw.widget.setEnabled(True)
        self.s2pw.widget.setEnabled(self.sym in [SYM_4_RECT, SYM_ARB])
        self.s3pw.widget.setEnabled(self.sym in [SYM_ARB])
        self.s4pw.widget.setEnabled(self.sym in [SYM_ARB])

    def sym_value_changed(self, is_pinc=False):
        """
        Recalculate the pin-count values on user input
        :param is_pinc: user input was to the overall pincount box, sets which fields are recalculated
        :return:
        """
        if is_pinc and self.sym in [SYM_4_SQUARE, SYM_2]:
            mod = {SYM_4_SQUARE: 4, SYM_2: 2}[self.sym]
            if self.pincw.value % mod != 0:
                raise ValueError("Invalid pin count")

        if self.sym == SYM_4_SQUARE:
            if is_pinc:
                self.s1pw.value = self.s2pw.value = self.s3pw.value = self.s4pw.value = self.pincw.value / 4
            else:
                self.s4pw.value = self.s3pw.value = self.s2pw.value = self.s1pw.value
                self.pincw.value = self.s1pw.value * 4
        elif self.sym == SYM_4_RECT:
            assert not is_pinc
            self.s4pw.value = self.s2pw.value
            self.s3pw.value = self.s1pw.value
            self.pincw.value = (self.s2pw.value + self.s1pw.value) * 2
        elif self.sym == SYM_2:
            self.s2pw.value = self.s4pw.value = 0
            if is_pinc:
                self.s1pw.value = self.s3pw.value = self.pincw.value / 2
            else:
                self.s3pw.value = self.s1pw.value
                self.pincw.value = self.s1pw.value * 2
        elif self.sym == SYM_ARB:
            assert not is_pinc
            self.pincw.value = self.s1pw.value + self.s2pw.value + self.s3pw.value + self.s4pw.value


class BasicSMDICModel(GenModel):
    def __init__(self):
        super(BasicSMDICModel, self).__init__()

    changed = QtCore.Signal()

    side1_pins = mdlacc(25)
    side2_pins = mdlacc(25)
    side3_pins = mdlacc(25)
    side4_pins = mdlacc(25)

    dim_1_body = mdlacc(14000)
    dim_1_pincenter = mdlacc(16000)
    dim_2_body = mdlacc(14000)
    dim_2_pincenter = mdlacc(16000)

    pin_contact_length = mdlacc(600)
    pin_contact_width = mdlacc(220)
    pin_spacing = mdlacc(500)


def BasicSMD_getComponent(mdl, ctrl, flow):
    return SMD4Component(flow.center, flow.theta + math.pi/2, ctrl.view.current_side, ctrl.project,
                       mdl.side1_pins, mdl.side2_pins, mdl.side3_pins, mdl.side4_pins,
                       mdl.dim_1_body, mdl.dim_1_pincenter, mdl.dim_2_body, mdl.dim_2_pincenter,
                       mdl.pin_contact_length, mdl. pin_contact_width, mdl.pin_spacing)

