from collections import namedtuple
from pcbre.ui.tools.componenttool.passive import PassiveModel, PassiveEditWidget, Passive_getComponent, PassiveEditFlow
from pcbre.ui.tools.multipoint import MultipointEditRenderer, DONE_REASON
from pcbre.ui.widgets.unitedit import UNIT_GROUP_MM
from pcbre.util import Timer
from pcbre.view.rendersettings import RENDER_OUTLINES, RENDER_HINT_ONCE

__author__ = 'davidc'

from PySide import QtCore, QtGui
from pcbre.ui.tools.basetool import BaseToolController, BaseTool
from pcbre.ui.uimodel import mdlacc, GenModel

from pcbre.ui.tools.componenttool.basicsmd import BasicSMDICModel, BasicSMD_getComponent, BasicSMDFlow
from pcbre.ui.tools.componenttool.dip import DIPModel, DIPEditWidget, DIP_getComponent, DIPEditFlow

from pcbre.ui.dialogs.settingsdialog import MultiAutoSettingsDialog, UnitEditable, FloatTrait, LineEditable, \
    DegreeEditable
from .basicsmd import BasicSMDICEditWidget
from pcbre.ui.boardviewwidget import QPoint_to_pair
from pcbre.matrix import translate, rotate, Point2

MDL_TYPE_BASICSMD = 0
MDL_TYPE_DIP = 1
MDL_TYPE_PASSIVE = 2


mdl_meta_t = namedtuple("mdl_meta", ["cons", "widget_cons", "flow_cons", "get_comp", "text"])
mdl_meta = {
    MDL_TYPE_BASICSMD: mdl_meta_t(BasicSMDICModel, BasicSMDICEditWidget, BasicSMDFlow, BasicSMD_getComponent, "Basic 4-sided SMT"),
    MDL_TYPE_DIP: mdl_meta_t(DIPModel, DIPEditWidget, DIPEditFlow, DIP_getComponent, "DIP Component"),
    MDL_TYPE_PASSIVE: mdl_meta_t(PassiveModel, PassiveEditWidget, PassiveEditFlow, Passive_getComponent, "2-lead passive")
}

class ComponentSettings(MultiAutoSettingsDialog):
    def __init__(self, mdl, ctrl):
        super(ComponentSettings, self).__init__()

        self.resize(550, 700)
        self.setWindowTitle("Component Settings")

        self.mdl = mdl

        hfl = QtGui.QFormLayout()
        ct_cmb = QtGui.QComboBox()
        for _, i in sorted(mdl_meta.items(), key=lambda i: i[0]):
            ct_cmb.addItem(i.text)

        ct_cmb.setCurrentIndex(self.mdl.cmptype)

        ct_cmb.currentIndexChanged.connect(self.changeTab)

        hfl.addRow("Component Type", ct_cmb)


        self.w_x = UnitEditable(ctrl.flow, "center.x", UNIT_GROUP_MM)
        hfl.addRow("Position X:", self.w_x.widget)
        self.w_y = UnitEditable(ctrl.flow, "center.y", UNIT_GROUP_MM)
        hfl.addRow("Position Y:", self.w_y.widget)
        self.w_theta = DegreeEditable(ctrl.flow, "theta")
        hfl.addRow("Theta:", self.w_theta.widget)

        self.headerWidget.setLayout(hfl)

        for k, i in sorted(mdl_meta.items(), key=lambda i: i[0]):
            self.addAutoWidget(i.widget_cons(mdl.model_instances[k]))

        self.selectWidget(self.mdl.cmptype)

        self.ctrl = ctrl

    def changeTab(self, idx):
        self.mdl.cmptype = idx
        self.selectWidget(idx)
        self.ctrl.restartFlow()

    @QtCore.Slot()
    def accept(self):
        self.currentWidget.save()
        self.w_x.save()
        self.w_y.save()
        self.w_theta.save()
        super(ComponentSettings, self).accept()


class ComponentModel(GenModel):
    def __init__(self):
        super(ComponentModel, self).__init__()

        self.model_instances = {}
        for t, meta in mdl_meta.items():
            i = self.model_instances[t] = meta.cons()
            i.changed.connect(self.changed)

    cmptype = mdlacc(MDL_TYPE_BASICSMD)

    def get_selected_model(self):
        return self.model_instances[self.cmptype]

    def get_model_name(self):
        return mdl_meta[self.cmptype].text

    def get_mpe(self):
        return self.get_selected_model().multi_editor


class ComponentOverlay:
    def __init__(self, parent):
        """
        :type parent: ComponentController
        :param parent:
        :return:
        """
        self.parent = parent

    def initializeGL(self, gls):
        pass

    def render(self, vs):
        with Timer() as t_get:
            cmp = self.parent.get_component()

        cmp._project = self.parent.project
        with Timer() as t_cmp_render:
            self.parent.view.render_component(vs.glMatrix, cmp, RENDER_OUTLINES, RENDER_HINT_ONCE)

        with Timer() as t_mp_edit_renderer:
            pr = MultipointEditRenderer(self.parent.flow, self.parent.view)
            pr.render()


class ComponentController(BaseToolController):
    def __init__(self, mdl, project, view):
        """

        :param mdl:
        :param project:
        :param view:
        :type view: pcbre.ui.boardviewwidget.BoardViewWidget
        :return:
        """
        super(ComponentController, self).__init__()
        self.project = project
        self.view = view
        self.mdl = mdl
        self.mdl.changed.connect(self.changed)

        self.overlay = ComponentOverlay(self)

        self.restartFlow()

    def get_component(self):
        return mdl_meta[self.mdl.cmptype].get_comp(self.mdl.get_selected_model(), self, self.flow)

    def showSettingsDialog(self):
        dlg = ComponentSettings(self.mdl, self)
        dlg.exec_()

    def mouseMoveEvent(self, evt):
        self.flow.mouseMoveEvent(evt)
        self.changed.emit()

    def mousePressEvent(self, evt):
        self.flow.mousePressEvent(evt)
        self.checkDone()

    def mouseReleaseEvent(self, evt):
        self.flow.mouseReleaseEvent(evt)
        self.checkDone()

    def keyPressEvent(self, evt):
        filter = self.flow.keyPressEvent(evt)
        self.checkDone()
        return filter

    def keyReleaseEvent(self, evt):
        filter_val = self.flow.keyReleaseEvent(evt)
        self.checkDone()
        return filter_val

    def checkDone(self):
        if self.flow.done == DONE_REASON.NOT_DONE:
            return

        if self.flow.done == DONE_REASON.ACCEPT:
            cmp = self.get_component()
            self.project.artwork.merge_component(cmp)
            self.restartFlow()

    def restartFlow(self):
        self.flow = mdl_meta[self.mdl.cmptype].flow_cons(self.view, self.mdl.get_selected_model())
        self.flow.make_active(True)

    @property
    def side(self):
        return self.view.viewState.current_layer.side


class ComponentTool(BaseTool):
    NAME = 'Component'
    ICON_NAME = 'component'
    SHORTCUT = 'c'
    TOOLTIP = 'Component (c)'

    def __init__(self, project):
        super(ComponentTool, self).__init__(project)
        self.mdl = ComponentModel()

    def getToolController(self, view):
        return ComponentController(self.mdl, self.project, view)

