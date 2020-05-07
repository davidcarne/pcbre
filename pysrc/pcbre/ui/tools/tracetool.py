from collections import defaultdict


from pcbre.accel.vert_array import VA_thickline, VA_via
from pcbre.view.target_const import COL_LAYER_MAIN
from .basetool import BaseTool, BaseToolController
from pcbre import units
from pcbre.matrix import Point2, translate, Vec2
from pcbre.model.artwork import Via
from pcbre.model.artwork_geom import Trace, Via
from pcbre.ui.boardviewwidget import QPoint_to_pair
from pcbre.ui.undo import UndoMerge

from pcbre.ui.action import ActionDescription, ActionShortcut, Modifier, EventID

from pcbre.ui.widgets.unitedit import UnitLineEdit, UNIT_GROUP_MM
from pcbre.view.rendersettings import RENDER_OUTLINES

import enum

ROUTING_STRAIGHT = 0
ROUTING_45 = 1
ROUTING_90 = 2
ROUTING_MOD = 3


class TraceEventCode(enum.Enum):
    DecreaseThickness = 0   # wheel-down
    IncreaseThickness = 1   # wheel-up
    AbortPlace = 2      # escape
    PlaceSegment = 3         # enter, click
    PlaceAll = 4      # shift-click, shift-enter
    CycleRouteMode = 5  # shift-space
    CycleRouteDir = 6   # space

class TraceToolOverlay:
    def __init__(self, ctrl):
        """
        :type ctrl: TraceToolController
        """
        self.view = ctrl.view
        self.ctrl = ctrl

    def initializeGL(self, _):
        pass

    def render(self, viewport, compositor):
        via, traces =  self.ctrl.get_artwork()

        va_for_via = VA_via(1024)

        # Render by drawing the VA
        va_for_ly = defaultdict(lambda: VA_thickline(1024))

        if via:
            va_for_via.add_donut(via.pt.x, via.pt.y, via.r)

            with compositor.get("OVERLAY"):
                self.view.via_renderer.render_outlines(
                    self.ctrl.view.viewState.glMatrix,
                    va_for_via)

        if traces:
            for t in traces:
                va_for_ly[t.layer].add_trace(t)

            for layer, va in va_for_ly.items():
                with self.ctrl.view.compositor.get(layer):
                    self.ctrl.view.trace_renderer.render_va(
                        va,
                        self.ctrl.view.viewState.glMatrix,
                        COL_LAYER_MAIN, True)





class TraceToolController(BaseToolController):
    def __init__(self, view, submit, project, toolsettings):
        """

        :type view: pcbre.ui.boardviewwidget.BoardViewWidget
        """
        super(TraceToolController, self).__init__()

        self.view = view
        self.submit = submit
        self.project = project

        self.toolsettings = toolsettings

        self.cur_pt = Point2(0,0)
        self.last_pt = None
        self.last_layer = None

        self.overlay = TraceToolOverlay(self)

        # TODO: HACK
        self.actions = g_ACTIONS

        self.routing_mode = ROUTING_STRAIGHT
        self.routing_dir = False

    def get_artwork(self):
        if self.view.current_layer_hack() is None:
            return None, []

        layer = self.view.current_layer_hack()

        # If no last-point is set, we return a trace stub 'circle' to visualize where the trace will go
        if self.last_pt is None:
            return None, [Trace(self.cur_pt, self.cur_pt, self.toolsettings.thickness, layer, None)]

        initial_via = None

        # If previous layer and current layer are the same, no via needed
        if self.last_layer != layer:
            # Look for a viapair between the layer @ self.last_layer
            vp = self.project.stackup.via_pair_for_layers([self.last_layer, layer])

            if vp is not None:
                initial_via = Via(self.last_pt, vp, self.toolsettings.via_radius)

        # Single straight trace
        if self.routing_mode == ROUTING_STRAIGHT:
            return initial_via, [Trace(self.last_pt, self.cur_pt, self.toolsettings.thickness, layer, None)]
        
        # 90 degree bend
        elif self.routing_mode == ROUTING_90:

            # position of bend point
            if self.routing_dir:
                pa = Point2(self.last_pt.x, self.cur_pt.y)
            else:
                pa = Point2(self.cur_pt.x, self.last_pt.y)

            return initial_via, [
                Trace(self.last_pt, pa, self.toolsettings.thickness, layer, None),
                Trace(pa, self.cur_pt, self.toolsettings.thickness, layer, None)
            ]

        elif self.routing_mode == ROUTING_45:

            d_v = self.cur_pt - self.last_pt

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


            if self.routing_dir:
                pa = self.last_pt + d_nv
            else:
                pa = self.last_pt + d_vh

            return initial_via, [
                Trace(self.last_pt, pa, self.toolsettings.thickness, layer, None),
                Trace(pa, self.cur_pt, self.toolsettings.thickness, layer, None)
            ]


    def cycle_routing_modes(self):
        self.routing_mode = (self.routing_mode + 1) % ROUTING_MOD

    def cycle_routing_dir(self):
        self.routing_dir = not self.routing_dir

    def showSettingsDialog(self):
        pass

    def traceEnterPoint(self, evt, multi_seg=True):
        self.cur_pt = evt.world_pos

        layer = self.view.current_layer_hack()
        if layer is None:
            return

        if self.last_pt is not None:
            via, traces = self.get_artwork()
            if not traces:
                return

            v_list = []
            if via is not None:
                v_list = [via]

            if multi_seg:
                self.submit(UndoMerge(self.project, v_list + list(traces), "Routing"))
                self.last_pt = self.cur_pt
                self.last_layer = layer
            else:
                self.submit(UndoMerge(self.project, v_list + [traces[0]], "Routing"))
                self.last_pt = traces[0].p1
                self.last_layer = layer
                self.cycle_routing_dir()
        else:
            self.last_pt = self.cur_pt
            self.last_layer = layer


    def mouseMoveEvent(self, evt):
        self.cur_pt = evt.world_pos

    def eventThickness(self, step):
        step = step * 0.050 * units.MM
        self.toolsettings.thickness += step
        if self.toolsettings.thickness <= 100:
            self.toolsettings.thickness = 100

    def event(self, event):
        if event.code == TraceEventCode.DecreaseThickness:
            self.event_thickness(-1 * event.amount)
        elif event.code == TraceEventCode.IncreaseThickness:
            self.event_thickness(event.amount)
        elif event.code == TraceEventCode.AbortPlace:
            self.last_pt = None
            self.last_layer = None
        elif event.code == TraceEventCode.PlaceSegment:
            self.traceEnterPoint(event, False)
        elif event.code == TraceEventCode.PlaceAll:
            self.traceEnterPoint(event, True)
        elif event.code == TraceEventCode.CycleRouteMode:
            self.cycle_routing_modes()
        elif event.code == TraceEventCode.CycleRouteDir:
            self.cycle_routing_dir()
        else:
            raise ValueError("Trace tool received unknown event: %s" % event)


g_ACTIONS = [
    ActionDescription(
        ActionShortcut(EventID.Mouse_WheelDown, Modifier.Shift),
        TraceEventCode.DecreaseThickness,
        "Decrease Trace Thickness"),
    ActionDescription(
        ActionShortcut(EventID.Mouse_WheelUp, Modifier.Shift),
        TraceEventCode.IncreaseThickness,
        "Increase Trace Thickness"),
    ActionDescription(
        ActionShortcut(EventID.Key_Escape),
        TraceEventCode.AbortPlace,
        "Abort Placement"),
    ActionDescription(
        [
            ActionShortcut(EventID.Key_Enter), 
            ActionShortcut(EventID.Key_Return), 
            ActionShortcut(EventID.Mouse_B1)
            ],
        TraceEventCode.PlaceSegment,
        "Place track segment"),
    ActionDescription(
        [
            ActionShortcut(EventID.Key_Enter, Modifier.Shift),
            ActionShortcut(EventID.Key_Return, Modifier.Shift), 
            ActionShortcut(EventID.Mouse_B1, Modifier.Shift)
            ],
        TraceEventCode.PlaceAll,
        "Place all segments"),

    ActionDescription(
        ActionShortcut(EventID.Key_Space, Modifier.Shift),
        TraceEventCode.CycleRouteMode,
        "Cycle routing mode"),

    ActionDescription(
        ActionShortcut(EventID.Key_Space),
        TraceEventCode.CycleRouteDir,
        "Cycle routing direction"),
]

class TraceToolSettings(object):
    __slots__ = ["thickness", "via_radius"]

    def __init__(self):
        self.thickness = 1000
        self.via_radius = 500


class TraceTool(BaseTool):
    ICON_NAME = "trace"
    NAME = "Trace"
    SHORTCUT = 't'
    TOOLTIP = 'Trace (t)'
    ACTIONS = g_ACTIONS

    def __init__(self, project):
        super(TraceTool, self).__init__(project)
        self.project = project
        self.ext = []
        self.model = TraceToolSettings()

    def getToolController(self, view, submit):
        return TraceToolController(view, submit, self.project, self.model)

