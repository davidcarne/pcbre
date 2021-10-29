from pcbre.accel.vert_array import VA_xy
from pcbre.algo.geom import layer_for
from pcbre.matrix import Point2
from pcbre.model.artwork_geom import Airwire
from pcbre.ui.tools.basetool import BaseTool, BaseToolController
from qtpy import QtGui, QtCore
from pcbre.ui.undo import UndoMerge
from pcbre.view.rendersettings import RENDER_HINT_ONCE
from pcbre.view.target_const import COL_AIRWIRE
from pcbre.ui.tool_action import ToolActionDescription, \
    ToolActionShortcut, EventID


class EventCode:
    Place = 0

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

    def __init__(self, project, view, submit):
        """

        :type view: pcbre.ui.boardviewwidget.BoardViewWidget
        """
        super(AirwireToolController, self).__init__()
        self.project = project
        self.view = view
        self.submit = submit

        self.overlay = AirwireToolOverlay(self)
        self.state = self.STATE_IDLE

        self.pt0 = None
        self.mouse = None

    @property
    def tool_actions(self):
        return g_ACTIONS

    def mouseMoveEvent(self, evt):
        self.mouse = evt.world_pos
        self.changed.emit()

    def event_place(self, event):
        pt = event.world_pos

        # Find artwork
        aw = self.view.query_point(pt)

        # layer for the artwork
        aw_l = layer_for(aw)

        # No layer (no artwork)
        if aw is None:
            return

        if self.state == self.STATE_IDLE:
            self.pt0 = pt
            self.pt0_layer = aw_l
            self.state = self.STATE_WAIT_ADTL_POINT

        elif self.state == self.STATE_WAIT_ADTL_POINT:
            aw = Airwire(self.pt0, pt, self.pt0_layer, aw_l, None)
            self.submit(UndoMerge(self.project, aw, "Add Airwire"))

            self.state = self.STATE_IDLE

        self.changed.emit()

    def tool_event(self, event):
        if event.code == EventCode.Place:
            self.event_place(event)


g_ACTIONS = [
    ToolActionDescription(
        ToolActionShortcut(EventID.Mouse_B1),
        EventCode.Place,
        "Place airwire endpoint"),
]

class AirwireTool(BaseTool):
    ICON_NAME="airwire"
    NAME="Airwire"
    SHORTCUT="a"
    TOOLTIP="Airwire (a)"


    def __init__(self, project):
        super(AirwireTool, self).__init__(project)
        self.project = project

    def getToolController(self, view, submit):
        return AirwireToolController(self.project, view, submit)

