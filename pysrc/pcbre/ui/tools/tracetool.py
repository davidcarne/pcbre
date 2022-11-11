import enum
from collections import defaultdict
from typing import Dict

from pcbre import units
from pcbre.accel.vert_array import VA_thickline, VA_via
from pcbre.matrix import Vec2
from pcbre.model.artwork_geom import Trace, Via
from pcbre.model.stackup import Layer
from pcbre.ui.tool_action import ToolActionDescription, ToolActionShortcut, Modifier, EventID, ToolActionEvent, \
    MoveEvent
from pcbre.ui.undo import UndoMerge
from pcbre.view.target_const import COL_LAYER_MAIN
from .basetool import BaseTool, BaseToolController


from typing import TYPE_CHECKING, Any, Optional, Callable, List, Tuple

if TYPE_CHECKING:
    from pcbre.model.project import Project
    from pcbre.view.layer_render_target import CompositeManager
    from pcbre.ui.boardviewwidget import BoardViewWidget


class RoutingMode(enum.Enum):
    STRAIGHT = 0
    _45 = 1
    _90 = 2
    # Last entry, used for mod operator in carousel
    MOD = 3


class TraceEventCode(enum.Enum):
    DecreaseThickness = 0  # wheel-down
    IncreaseThickness = 1  # wheel-up
    AbortPlace = 2  # escape
    PlaceSegment = 3  # enter, click
    PlaceAll = 4  # shift-click, shift-enter
    CycleRouteMode = 5  # shift-space
    CycleRouteDir = 6  # space


class TraceToolOverlay:
    def __init__(self, ctrl: 'TraceToolController') -> None:
        """
        :type ctrl: TraceToolController
        """
        self.view = ctrl.view
        self.ctrl = ctrl

    def initializeGL(self, _: Any) -> None:
        pass

    def render(self, viewport: Any, compositor: 'CompositeManager') -> None:
        via, traces = self.ctrl.get_artwork()

        va_for_via = VA_via(1024)

        # Render by drawing the VA
        va_for_ly: Dict[Layer, VA_thickline] = \
            defaultdict(lambda: VA_thickline(1024))

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
    def __init__(self, view: 'BoardViewWidget', submit: 'Callable[[Any], None]', project: 'Project', toolsettings: 'TraceToolSettings') -> None:
        """

        :type view: pcbre.ui.boardviewwidget.BoardViewWidget
        """
        super(TraceToolController, self).__init__()

        self.view = view
        self.submit = submit
        self.project = project

        self.toolsettings = toolsettings

        self.cur_pt = Vec2(0, 0)
        self.__last_pt = None
        self.__last_layer = None

        self.overlay = TraceToolOverlay(self)

        self.routing_mode = RoutingMode.STRAIGHT
        self.routing_dir = False

    @property
    def tool_actions(self) -> 'List[ToolActionDescription]':
        return g_ACTIONS

    def get_artwork(self) -> Tuple[Optional[Via], List[Trace]]:
        if self.view.current_layer_hack() is None:
            return None, []

        layer = self.view.current_layer_hack()

        # If no last-point is set, we return a trace stub 'circle' to visualize where the trace will go
        if self.__last_pt is None:
            return None, [Trace(self.cur_pt, self.cur_pt, self.toolsettings.thickness, layer, None)]

        initial_via = None

        # If previous layer and current layer are the same, no via needed
        if self.__last_layer != layer:
            # Look for a viapair between the layer @ self.last_layer
            vp = self.project.stackup.via_pair_for_layers([self.__last_layer, layer])

            if vp is not None:
                initial_via = Via(self.__last_pt, vp, self.toolsettings.via_radius)

        # Single straight trace
        if self.routing_mode == RoutingMode.STRAIGHT:
            return initial_via, [Trace(self.__last_pt, self.cur_pt, self.toolsettings.thickness, layer, None)]

        # 90 degree bend
        elif self.routing_mode == RoutingMode._90:

            # position of bend point
            if self.routing_dir:
                pa = Vec2(self.__last_pt.x, self.cur_pt.y)
            else:
                pa = Vec2(self.cur_pt.x, self.__last_pt.y)

            return initial_via, [
                Trace(self.__last_pt, pa, self.toolsettings.thickness, layer, None),
                Trace(pa, self.cur_pt, self.toolsettings.thickness, layer, None)
            ]

        # Straight with 45
        elif self.routing_mode == RoutingMode._45:
            # Vector for the total line
            d_v = self.cur_pt - self.__last_pt

            # Calculate vector of the diagonal section
            d_nv = d_v.dup()

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

            # Vector for the rectilinear section
            d_vh = d_v - d_nv

            # Diagonal or Rectilinear first
            if self.routing_dir:
                pa = self.__last_pt + d_nv
            else:
                pa = self.__last_pt + d_vh

            return initial_via, [
                Trace(self.__last_pt, pa, self.toolsettings.thickness, layer, None),
                Trace(pa, self.cur_pt, self.toolsettings.thickness, layer, None)
            ]

    def __cycle_routing_modes(self) -> None:
        self.routing_mode = RoutingMode((self.routing_mode.value + 1) % RoutingMode.MOD.value)

    def __cycle_routing_dir(self) -> None:
        self.routing_dir = not self.routing_dir

    def showSettingsDialog(self) -> None:
        pass

    def __trace_enter_point(self, evt: 'ToolActionEvent', multi_seg=True) -> None:
        self.cur_pt = evt.world_pos

        layer = self.view.current_layer_hack()
        if layer is None:
            return

        if self.__last_pt is not None:
            via, traces = self.get_artwork()
            if not traces:
                return

            v_list = []
            if via is not None:
                v_list = [via]

            if multi_seg:
                total_list: List[Any] = []
                total_list += v_list
                total_list += list(traces)
                self.submit(UndoMerge(self.project, total_list, "Routing"))
                self.__last_pt = self.cur_pt
                self.__last_layer = layer
            else:
                total_list: List[Any] = []
                total_list += v_list
                total_list.append(traces[0])
                self.submit(UndoMerge(self.project, total_list, "Routing"))
                self.__last_pt = traces[0].p1
                self.__last_layer = layer
                self.__cycle_routing_dir()
        else:
            self.__last_pt = self.cur_pt
            self.__last_layer = layer

    def mouseMoveEvent(self, evt: MoveEvent) -> None:
        self.cur_pt = evt.world_pos

    def __event_thickness(self, step: float) -> None:
        step = step * 0.050 * units.MM
        self.toolsettings.thickness += step
        if self.toolsettings.thickness <= 100:
            self.toolsettings.thickness = 100

    def tool_event(self, event: ToolActionEvent) -> None:
        if event.code == TraceEventCode.DecreaseThickness:
            self.__event_thickness(-1 * event.amount)
        elif event.code == TraceEventCode.IncreaseThickness:
            self.__event_thickness(event.amount)
        elif event.code == TraceEventCode.AbortPlace:
            self.__last_pt = None
            self.__last_layer = None
        elif event.code == TraceEventCode.PlaceSegment:
            self.__trace_enter_point(event, False)
        elif event.code == TraceEventCode.PlaceAll:
            self.__trace_enter_point(event, True)
        elif event.code == TraceEventCode.CycleRouteMode:
            self.__cycle_routing_modes()
        elif event.code == TraceEventCode.CycleRouteDir:
            self.__cycle_routing_dir()
        else:
            print("Trace tool received unknown event:", event)


g_ACTIONS = [
    ToolActionDescription(
        ToolActionShortcut(EventID.Mouse_WheelDown, Modifier.Shift),
        TraceEventCode.DecreaseThickness,
        "Decrease Trace Thickness"),
    ToolActionDescription(
        ToolActionShortcut(EventID.Mouse_WheelUp, Modifier.Shift),
        TraceEventCode.IncreaseThickness,
        "Increase Trace Thickness"),
    ToolActionDescription(
        [ ToolActionShortcut(EventID.Key_Escape), ToolActionShortcut(EventID.Mouse_B2)],
        TraceEventCode.AbortPlace,
        "Abort Placement"),
    ToolActionDescription(
        [
            ToolActionShortcut(EventID.Key_Enter),
            ToolActionShortcut(EventID.Key_Return),
            ToolActionShortcut(EventID.Mouse_B1)
        ],
        TraceEventCode.PlaceSegment,
        "Place track segment"),
    ToolActionDescription(
        [
            ToolActionShortcut(EventID.Key_Enter, Modifier.Shift),
            ToolActionShortcut(EventID.Key_Return, Modifier.Shift),
            ToolActionShortcut(EventID.Mouse_B1, Modifier.Shift)
        ],
        TraceEventCode.PlaceAll,
        "Place all segments"),

    ToolActionDescription(
        ToolActionShortcut(EventID.Key_Space, Modifier.Shift),
        TraceEventCode.CycleRouteMode,
        "Cycle routing mode"),

    ToolActionDescription(
        ToolActionShortcut(EventID.Key_Space),
        TraceEventCode.CycleRouteDir,
        "Cycle routing direction"),
]


class TraceToolSettings:
    __slots__ = ["thickness", "via_radius"]

    def __init__(self) -> None:
        self.thickness = 1000
        self.via_radius = 500


class TraceTool(BaseTool):
    ICON_NAME = "trace"
    NAME = "Trace"
    SHORTCUT = 't'
    TOOLTIP = 'Trace (t)'
    ACTIONS = g_ACTIONS

    def __init__(self, project: 'Project') -> None:
        super(TraceTool, self).__init__(project)
        self.project = project
        self.ext = []
        self.model = TraceToolSettings()

    def getToolController(self, view: 'BoardViewWidget', submit: Callable[[Any], None]) -> 'TraceToolController':
        return TraceToolController(view, submit, self.project, self.model)
