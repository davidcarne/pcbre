import enum

from pcbre.model.pad import Pad
from .basetool import BaseTool, BaseToolController
from pcbre.model.const import TFF
from qtpy import QtWidgets
from pcbre.ui.uimodel import TinySignal
from pcbre.ui.icon import Icon
from pcbre.model.project import Project
import pcbre.ui.boardviewwidget
from typing import Optional, Callable, Any
from pcbre.ui.tool_action import ToolActionDescription, ToolActionShortcut, Modifier, EventID, ToolActionEvent



class SelectEventCode(enum.Enum):
    Select = 0
    SelectUnion = 1
    SelectDifference = 2
    DeleteSelected = 3


class SelectByModes(enum.Enum):
    POINT = 0
    TOUCH_LINE = 1
    TOUCH_RECT = 2
    INSIDE_RECT = 3
    NET = 4


class CombiningMode(enum.Enum):
    NO = 0
    UNION = 1
    DIFFERENCE = 2


select_names = {
    SelectByModes.POINT: "Touching Point",
    SelectByModes.TOUCH_LINE: "Touching Line",
    SelectByModes.TOUCH_RECT: "Touching Rect",
    SelectByModes.INSIDE_RECT: "Inside Rect",
    SelectByModes.NET: "Net"
}


select_icons = {
    SelectByModes.POINT: "select_by_point",
    SelectByModes.TOUCH_LINE: "select_by_touch_line",
    SelectByModes.NET: "select_by_net"
}


valid_select = [SelectByModes.POINT, SelectByModes.NET]


class SelectToolController(BaseToolController):
    def __init__(self, project: Project,
                 model: 'SelectToolModel',
                 view: 'pcbre.ui.boardviewwidget.BoardViewWidget',
                 submit: Any):
        super(SelectToolController, self).__init__()

        self.view: pcbre.ui.boardviewwidget.BoardViewWidget = view
        self.project: Project = project
        self.model: SelectToolModel = model

    @property
    def tool_actions(self):
        return g_ACTIONS

    def eventSelect(self, evt: ToolActionEvent, combining: CombiningMode):
        new = set()

        if self.model.vers == SelectByModes.POINT:
            res = self.view.query_point(evt.world_pos)
            if res is not None:
                new.add(res)

        elif self.model.vers == SelectByModes.NET:
            res = self.view.query_point(evt.world_pos)
            if res is not None and res.TYPE_FLAGS & TFF.HAS_NET:
                net = res.net
                aw = self.project.artwork.get_geom_for_net(net)
                new.update(aw)

        current = self.view.selectionList

        if combining == CombiningMode.UNION:
            updated = current.union(new)
        elif combining == CombiningMode.DIFFERENCE:
            updated = current.difference(new)
        else:
            updated = new

        self.view.setSelectionList(updated)

    def eventDelete(self):
        for v in self.view.selectionList:
            if isinstance(v, Pad):
                continue

            self.project.artwork.remove(v)

        self.view.selectionList.clear()

    def tool_event(self, event: ToolActionEvent):
        if event.code == SelectEventCode.Select:
            self.eventSelect(event, CombiningMode.NO)
        elif event.code == SelectEventCode.SelectUnion:
            self.eventSelect(event, CombiningMode.UNION)
        elif event.code == SelectEventCode.SelectDifference:
            self.eventSelect(event, CombiningMode.DIFFERENCE)
        elif event.code == SelectEventCode.DeleteSelected:
            self.eventDelete()


class SelectToolModel:
    def __init__(self):
        self.__vers = SelectByModes.POINT
        self.changed = TinySignal()

    @property
    def vers(self) -> SelectByModes:
        return self.__vers

    @vers.setter
    def vers(self, value: SelectByModes) -> None:
        self.__vers = value


class SelectTool(BaseTool):
    ICON_NAME = "cross"
    NAME = "Select"
    SHORTCUT = 's'
    TOOLTIP = 'Select (s)'

    def __init__(self, project: Project):
        super(SelectTool, self).__init__(project)
        self.model: SelectToolModel = SelectToolModel()

        self.model.changed.connect(self.__update_icon)


    def getToolController(self,
                          view: 'pcbre.ui.boardviewwidget.BoardViewWidget',
                          submit: Any):
        return SelectToolController(self.project, self.model, view, Any)

    def __update_icon(self):
        ico = Icon(select_icons[self.model.vers])

        self.toolButton.setIcon(ico)
        self.toolButton.setText(select_names[self.model.vers])
        self.toolButton.setShortcut(self.SHORTCUT)

    def __set_version(self, v):
        self.model.vers = v

    def setupToolButtonExtra(self):
        self.menu = QtWidgets.QMenu()
        self.ag = QtWidgets.QActionGroup(self.menu)

        for n in valid_select:
            a1 = QtWidgets.QAction(select_names[n], self.menu)

            def closure(n):
                def fn():
                    self.__set_version(n)
                    self.toolButton.click()
                return fn

            a1.triggered.connect(closure(n))

            self.menu.addAction(a1)
            self.ag.addAction(a1)

        self.toolButton.setMenu(self.menu)
        self.__update_icon()


g_ACTIONS = [
    ToolActionDescription(
        [
            ToolActionShortcut(EventID.Mouse_B1),
            ToolActionShortcut(EventID.Key_Enter),
            ToolActionShortcut(EventID.Key_Return),
        ],
        SelectEventCode.Select,
        "Change selection to selected items"),
    ToolActionDescription(
        [
            ToolActionShortcut(EventID.Mouse_B1, Modifier.Ctrl),
            ToolActionShortcut(EventID.Key_Enter, Modifier.Ctrl),
            ToolActionShortcut(EventID.Key_Return, Modifier.Ctrl),
        ],
        SelectEventCode.SelectUnion,
        "Add selected items to selection"),
    ToolActionDescription(
        [
            ToolActionShortcut(EventID.Mouse_B1,
                               Modifier.Ctrl | Modifier.Shift),
            ToolActionShortcut(EventID.Key_Enter,
                               Modifier.Ctrl | Modifier.Shift),
            ToolActionShortcut(EventID.Key_Return,
                               Modifier.Ctrl | Modifier.Shift),
        ],
        SelectEventCode.SelectDifference,
        "Remove selected items from selection"),

    ToolActionDescription(
        [
            ToolActionShortcut(EventID.Key_Backspace),
            ToolActionShortcut(EventID.Key_Delete),
        ],
        SelectEventCode.SelectDifference,
        "Delete selected items")
]
