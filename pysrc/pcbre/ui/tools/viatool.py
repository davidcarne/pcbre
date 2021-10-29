from qtpy import QtCore, QtWidgets

from pcbre.accel.vert_array import VA_via
from .basetool import BaseTool, BaseToolController
from pcbre.matrix import Vec2
from pcbre.model.artwork_geom import Via

from pcbre.ui.undo import UndoMerge
from pcbre.ui.dialogs.settingsdialog import SettingsDialog
from pcbre.ui.widgets.unitedit import UnitLineEdit, UNIT_GROUP_MM

from pcbre.ui.tool_action import ToolActionDescription, ToolActionShortcut, \
    Modifier, EventID, MoveEvent, ToolActionEvent

from pcbre.model.project import Project
from pcbre.model.stackup import ViaPair
import pcbre.ui.boardviewwidget
from pcbre.view.viewport import ViewPort
import enum
from pcbre.view.layer_render_target import CompositeManager
from pcbre.ui.gl.glshared import GLShared
from typing import Callable, Optional


class ViaEventCode(enum.Enum):
    DecreaseRadius = 0
    IncreaseRadius = 1
    NextViaPair = 2
    Place = 3


class ViaSettingsDialog(SettingsDialog):
    def __init__(self, tpm: 'ViaToolModel'):
        super(ViaSettingsDialog, self).__init__()
        self.tpm = tpm

        self.radius_li = UnitLineEdit(UNIT_GROUP_MM)
        self.radius_li.setValue(self.tpm.via_radius)

        self.layout.addRow("Radius:", self.radius_li)

    @QtCore.Slot()
    def accept(self):
        self.tpm.via_radius = self.radius_li.getValue()
        QtWidgets.QDialog.accept(self)


class ViaToolOverlay:
    def __init__(self, ctrl: 'ViaToolController'):
        self.view: pcbre.ui.boardviewwidget.BoardViewWidget = ctrl.view
        self.tpm: ViaToolModel = ctrl.toolparammodel
        self.ctrl: ViaToolController = ctrl

        self.__va = VA_via(1024)

    def initializeGL(self, gls: GLShared):
        self.gls = gls

    def render(self, viewport: ViewPort, compositor: CompositeManager):
        self.__va.clear()

        if self.tpm.current_layer_pair is not None:
            if self.ctrl.pt is not None:
                self.__va.add_donut(
                    self.ctrl.pt.x, self.ctrl.pt.y, self.tpm.via_radius, 0)

        with compositor.get("OVERLAY"):
            self.view.via_renderer.render_outlines(
                viewport.glMatrix, self.__va)


class ViaToolController(BaseToolController):
    def __init__(self,
                 view: pcbre.ui.boardviewwidget.BoardViewWidget,
                 submit: Callable,
                 project: Project,
                 toolparammodel: 'ViaToolModel'):
        super(ViaToolController, self).__init__()

        self.view: pcbre.ui.boardviewwidget.BoardViewWidget = view
        self.project: Project = project
        self.submit: Callable = submit

        self.toolparammodel: ViaToolModel = toolparammodel

        self.pt: Optional[Vec2] = None
        self.show = False

        self.overlay = ViaToolOverlay(self)

    @property
    def tool_actions(self):
        return g_ACTIONS
        
    def showSettingsDialog(self):
        ViaSettingsDialog(self.toolparammodel).exec_()

    def event_place(self, evt: ToolActionEvent):
        # New object with dummy net
        if self.toolparammodel.current_layer_pair is not None:
            v = Via(evt.world_pos, self.toolparammodel.current_layer_pair,
                    self.toolparammodel.via_radius, None)
            self.submit(UndoMerge(self.project, v, "Add Via"))
        pass

    def mouseMoveEvent(self, evt: MoveEvent):
        self.pt = evt.world_pos

    def event_radius(self, amount: float):
        self.toolparammodel.via_radius += amount
        if self.toolparammodel.via_radius <= 0:
            self.toolparammodel.via_radius = 0.00001

    def tool_event(self, event: ToolActionEvent):
        if event.code == ViaEventCode.DecreaseRadius:
            self.event_radius(-1 * event.amount)
        elif event.code == ViaEventCode.IncreaseRadius:
            self.event_radius(1 * event.amount)
        elif event.code == ViaEventCode.NextViaPair:
            self.event_change_pair()
        elif event.code == ViaEventCode.Place:
            self.event_place(event)


g_ACTIONS = [
    ToolActionDescription(
        ToolActionShortcut(EventID.Mouse_WheelDown, Modifier.Shift),
        ViaEventCode.DecreaseRadius,
        "Decrease Via Radius"
        ),
    ToolActionDescription(
        ToolActionShortcut(EventID.Mouse_WheelUp, Modifier.Shift),
        ViaEventCode.IncreaseRadius,
        "Increase Via Radius"),
    ToolActionDescription(
        ToolActionShortcut(EventID.Key_Tab),
        ViaEventCode.NextViaPair,
        "Next Via Pair"),
    ToolActionDescription(
        [
            ToolActionShortcut(EventID.Key_Enter),
            ToolActionShortcut(EventID.Mouse_B1),
        ],
        ViaEventCode.Place,
        "Place Via"),
        ]


class ViaToolModel:
    __slots__ = ["via_radius", "current_layer_pair"]

    def __init__(self):
        self.via_radius : float = 1000
        self.current_layer_pair : Optional[ViaPair] = None


class ViaTool(BaseTool):
    ICON_NAME = "via"
    NAME = "Via"
    SHORTCUT = 'v'
    TOOLTIP = 'Via (v)'

    def __init__(self, project: Project):
        super(ViaTool, self).__init__(project)

        self.project = project
        self.model = ViaToolModel()

    def __changed_selected_viapair(self, vp: ViaPair):
        self.model.current_layer_pair = vp

    def __setupMenu(self):
        self.menu = QtWidgets.QMenu()
        self.menu.aboutToShow.connect(self.aboutShowMenu)
        self.toolButton.setMenu(self.menu)

    def aboutShowMenu(self):
        self.menu.clear()

        self.ag = QtWidgets.QActionGroup(self.menu)
        self.ag.setExclusive(True)

        for n, vp in enumerate(self.project.stackup.via_pairs):
            l1, l2 = vp.layers
            a1 = QtWidgets.QAction("%d-%d" % (l1.order, l2.order), self.menu)
            a1.setCheckable(True)
            a1.setChecked(vp is self.model.current_layer_pair)

            def closure(vp):
                def fn():
                    self.__changed_selected_viapair(vp)
                return fn

            a1.triggered.connect(closure(vp))

            self.menu.addAction(a1)
            self.ag.addAction(a1)

    def setupToolButtonExtra(self):
        self.__setupMenu()

    def getToolController(self,
                          view: pcbre.ui.boardviewwidget.BoardViewWidget,
                          submit: Callable):
        return ViaToolController(view, submit, self.project, self.model)
