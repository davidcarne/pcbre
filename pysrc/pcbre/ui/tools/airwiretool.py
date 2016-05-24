from pcbre.accel.vert_array import VA_xy
from pcbre.algo.geom import layer_for
from pcbre.matrix import Point2
from pcbre.model.artwork_geom import Airwire
from pcbre.ui.tools.basetool import BaseTool, BaseToolController
from qtpy import QtGui, QtCore
from pcbre.view.rendersettings import RENDER_HINT_ONCE
from pcbre.view.target_const import COL_AIRWIRE

AIRWIRE_COLOR = (0.7, 0.7, 0)
class AirwireToolOverlay(object):
    def __init__(self, ctrl):
        """

        :param ctrl:
        :type ctrl: AirwireToolController
        """
        self.ctrl = ctrl
        self.view = ctrl.view

    def render(self, surface, compositor):
        if self.ctrl.state == self.ctrl.STATE_WAIT_ADTL_POINT:
            va = VA_xy(1024)
            va.add_line(self.ctrl.pt0.x, self.ctrl.pt0.y, self.ctrl.mouse.x, self.ctrl.mouse.y)

            with compositor.get("OVERLAY"):
                self.view.hairline_renderer.render_va(self.ctrl.view.viewState.glMatrix, va, COL_AIRWIRE)

    def initializeGL(self, fake_shared):
        pass

class AirwireToolController(BaseToolController):
    STATE_IDLE = 0
    STATE_WAIT_ADTL_POINT = 1

    def __init__(self, project, view):
        """

        :type view: pcbre.ui.boardviewwidget.BoardViewWidget
        """
        super(AirwireToolController, self).__init__()
        self.project = project
        self.view = view

        self.overlay = AirwireToolOverlay(self)
        self.state = self.STATE_IDLE

        self.pt0 = None
        self.mouse = None

    def mouseMoveEvent(self, evt):
        self.mouse = self.view.viewState.tfV2W(Point2(evt.pos()))
        self.changed.emit()

    def mouseReleaseEvent(self, evt):
        pt = self.view.viewState.tfV2W(Point2(evt.pos()))


        aw = self.view.query_point(pt)
        aw_l = layer_for(aw)

        if aw is None:
            return

        if self.state == self.STATE_IDLE:
            self.pt0 = pt
            self.pt0_layer = aw_l
            self.state = self.STATE_WAIT_ADTL_POINT

        elif self.state == self.STATE_WAIT_ADTL_POINT:
            aw = Airwire(self.pt0, pt, self.pt0_layer, aw_l, None)
            self.project.artwork.merge_artwork(aw)

            # Here is where we emit the airwire
            if evt.modifiers() & QtCore.Qt.ShiftModifier:
                self.pt0 = pt
                self.pt0_layer = aw_l
            else:
                self.state = self.STATE_IDLE

        self.changed.emit()


class AirwireTool(BaseTool):
    ICON_NAME="airwire"
    NAME="Airwire"
    SHORTCUT="a"
    TOOLTIP="Airwire (a)"


    def __init__(self, project):
        super(AirwireTool, self).__init__(self)
        self.project = project

    def getToolController(self, view):
        return AirwireToolController(self.project, view)

