from collections import defaultdict

from PySide import QtCore, QtGui

from pcbre.accel.vert_array import VA_thickline
from pcbre.view.target_const import COL_LAYER_MAIN
from .basetool import BaseTool, BaseToolController
from pcbre import units
from pcbre.matrix import Point2, translate, Vec2
from pcbre.model.artwork import Via
from pcbre.model.artwork_geom import Trace, Via
from pcbre.ui.boardviewwidget import QPoint_to_pair

from pcbre.ui.dialogs.settingsdialog import SettingsDialog
from pcbre.ui.widgets.unitedit import UnitLineEdit, UNIT_GROUP_MM
from pcbre.view.rendersettings import RENDER_OUTLINES

ROUTING_STRAIGHT = 0
ROUTING_45 = 1
ROUTING_90 = 2
ROUTING_MOD = 3


class TraceToolOverlay:
    def __init__(self, ctrl):
        """
        :type ctrl: TraceToolController
        """
        self.view = ctrl.view
        self.tpm = ctrl.toolparammodel
        self.ctrl = ctrl


    def initializeGL(self, gls):
        """
        :type gls: GLShared
        :param gls:
        :return:
        """
        self.gls = gls

    def render(self, viewport, compositor):
        traces =  self.ctrl.get_traces()
        if not traces:
            return

        # Render by drawing the VA
        va_for_ly = defaultdict(lambda: VA_thickline(1024))

        for t in traces:
            va_for_ly[t.layer].add_trace(t)

        for layer, va in va_for_ly.items():
            with self.ctrl.view.compositor.get(layer):
                self.ctrl.view.trace_renderer.render_va(
                    va,
                    self.ctrl.view.viewState.glMatrix,
                    COL_LAYER_MAIN, True)




class TraceToolController(BaseToolController):
    def __init__(self, view, project, toolparammodel):
        """

        :type view: pcbre.ui.boardviewwidget.BoardViewWidget
        """
        super(TraceToolController, self).__init__()

        self.view = view
        self.project = project

        self.toolparammodel = toolparammodel
        self.toolparammodel.changed.connect(self.__modelchanged)

        self.cur_pt = Point2(0,0)
        self.last_pt = None

        self.show = False

        self.overlay = TraceToolOverlay(self)

    def get_traces(self):
        if self.view.current_layer_hack() is None:
            return []

        sp = self.last_pt
        if sp is None:
            return []

        layer = self.view.current_layer_hack()

        # Single straight trace
        if self.toolparammodel.routing_mode == ROUTING_STRAIGHT:
            return [Trace(sp, self.cur_pt, self.toolparammodel.thickness, layer, None)]
        elif self.toolparammodel.routing_mode == ROUTING_90:

            if self.toolparammodel.routing_dir:
                pa = Point2(sp.x, self.cur_pt.y)
            else:
                pa = Point2(self.cur_pt.x, sp.y)

            return [
                Trace(sp, pa, self.toolparammodel.thickness, layer, None),
                Trace(pa, self.cur_pt, self.toolparammodel.thickness, layer, None)
            ]

        elif self.toolparammodel.routing_mode == ROUTING_45:

            d_v = self.cur_pt - sp

            d_nv = Vec2(d_v)

            if abs(d_v.y) < abs(d_v.x):
                if d_nv.x > 0:
                    d_nv.x = abs(d_v.y)
                else:
                    d_nv.x = -abs(d_v.y)
            else:
                if d_nv.y > 0:
                    d_nv.y = abs(d_v.x)
                else:
                    d_nv.y = -abs(d_v.x)


            d_vh = d_v - d_nv


            if self.toolparammodel.routing_dir:
                pa = sp + d_nv
            else:
                pa = sp + d_vh

            return [
                Trace(sp, pa, self.toolparammodel.thickness, layer, None),
                Trace(pa, self.cur_pt, self.toolparammodel.thickness, layer, None)
            ]




    def cycle_routing_modes(self):
        self.toolparammodel.routing_mode = (self.toolparammodel.routing_mode + 1) % ROUTING_MOD

    def cycle_routing_dir(self):
        self.toolparammodel.routing_dir = not self.toolparammodel.routing_dir

    def showSettingsDialog(self):
        pass


    def __modelchanged(self):
        self.changed.emit()

    def keyPressEvent(self, evt):
        if evt.key() == QtCore.Qt.Key_Escape:
            evt.accept()
            self.last_pt = None
            return True

        elif evt.key() == QtCore.Qt.Key_Space and evt.modifiers() & QtCore.Qt.ShiftModifier:
            self.cycle_routing_modes()
            evt.accept()
            return True

        elif evt.key() == QtCore.Qt.Key_Space and evt.modifiers() == 0:
            self.cycle_routing_dir()
            evt.accept()
            return True

        return False

    def mousePressEvent(self, evt):
        pos = evt.pos()
        pt = QPoint_to_pair(pos)
        end_point = Point2(self.view.viewState.tfV2W(pt))

        if self.last_pt is not None:
            traces = self.get_traces()

            if evt.modifiers() & QtCore.Qt.ShiftModifier:
                for trace in traces:
                    self.project.artwork.merge_artwork(trace)
                self.last_pt = end_point
            else:
                self.project.artwork.merge_artwork(traces[0])
                self.last_pt = traces[0].p1
                self.cycle_routing_dir()
        else:
            self.last_pt = end_point



    def mouseReleaseEvent(self, evt):
        pass

    def mouseMoveEvent(self, evt):
        self.show = True
        self.cur_pt = Point2(self.view.viewState.tfV2W(Point2(evt.pos())))
        self.changed.emit()

    def mouseWheelEvent(self, event):
        if event.modifiers() & QtCore.Qt.ShiftModifier:
            # TODO: Remove hack on step
            step = event.delta()/120.0 * 0.050 * units.MM
            self.toolparammodel.thickness += step
            if self.toolparammodel.thickness <= 100:
                self.toolparammodel.thickness = 100

class TraceToolModel(QtCore.QObject):
    def __init__(self, project):
        super(TraceToolModel, self).__init__()
        self.project = project

        self.__thickness = 1000

        self.__mode = ROUTING_STRAIGHT
        self.__dir = False

        self.__current_layer_id = 0

    changed = QtCore.Signal()

    @property
    def routing_mode(self):
        return self.__mode

    @routing_mode.setter
    def routing_mode(self, value):
        old = self.__mode
        self.__mode = value

        if old != value:
            self.changed.emit()


    @property
    def routing_dir(self):
        return self.__dir

    @routing_dir.setter
    def routing_dir(self, value):
        old = self.__dir
        self.__dir = value

        if old != value:
            self.changed.emit()

    @property
    def current_layer_id(self):
        return self.__current_layer_id

    @current_layer_id.setter
    def current_layer_id(self, value):
        old = self.__current_layer_id
        self.__current_layer_id = value

        if old != value:
            self.changed.emit()

    @property
    def thickness(self):
        return self.__thickness

    @thickness.setter
    def thickness(self, value):
        old = self.__thickness
        self.__thickness = value

        if old != value:
            self.changed.emit()

class TraceTool(BaseTool):
    ICON_NAME = "trace"
    NAME = "Trace"
    SHORTCUT = 't'
    TOOLTIP = 'Trace (t)'

    def __init__(self, project):
        super(TraceTool, self).__init__(project)
        self.project = project
        self.ext = []
        self.model = TraceToolModel(project)

    def getToolController(self, view):
        return TraceToolController(view, self.project, self.model)

