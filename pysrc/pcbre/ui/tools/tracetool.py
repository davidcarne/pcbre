from PySide import QtCore, QtGui
from .basetool import BaseTool, BaseToolController
from pcbre import units
from pcbre.matrix import Point2, translate
from pcbre.model.artwork import Via
from pcbre.model.artwork_geom import Trace, Via
from pcbre.ui.boardviewwidget import QPoint_to_pair

from pcbre.ui.dialogs.settingsdialog import SettingsDialog
from pcbre.ui.widgets.unitedit import UnitLineEdit, UNIT_GROUP_MM
from pcbre.view.rendersettings import RENDER_OUTLINES


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

    def render(self, viewport):
        self.view.trace_renderer.render(viewport.glMatrix, self.ctrl.get_trace(), RENDER_OUTLINES)




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

    def get_trace(self):
        sp = self.last_pt
        if sp is None:
            sp = self.cur_pt

        return Trace(sp, self.cur_pt, self.toolparammodel.thickness, self.view.current_layer_hack(), None)



    def showSettingsDialog(self):
        pass


    def __modelchanged(self):
        self.changed.emit()

    def mousePressEvent(self, evt):
        pos = evt.pos()
        pt = QPoint_to_pair(pos)
        end_point = Point2(self.view.viewState.tfV2W(pt))

        if self.last_pt is not None:
            t = Trace(self.last_pt, end_point, self.toolparammodel.thickness,
                      self.view.current_layer_hack(),
                      None)
            self.project.artwork.merge_artwork(t)

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

        self.__current_layer_id = 0

    changed = QtCore.Signal()

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

