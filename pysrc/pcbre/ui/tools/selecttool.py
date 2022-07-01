import enum

from pcbre.model.pad import Pad
from .basetool import BaseTool, BaseToolController
from pcbre.model.const import TFF
from qtpy import QtWidgets, QtCore
from pcbre.ui.uimodel import TinySignal
from pcbre.ui.icon import Icon
from pcbre.ui.undo import UndoDelete
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


class SelectionMenuAction(QtWidgets.QAction):
    def __init__(self, view, parent, name, cb, current, data, combining) -> None:
        QtWidgets.QAction.__init__(self, name, parent)

        self.data = data
        self.combining = combining
        self.cb = cb
        self.current = current
        self.view = view

        self.triggered.connect(self.__call_cb)

        self.hovered.connect(self.__hover)

    def __call_cb(self) -> None:
        self.cb(self.current, self.data, self.combining)

    def __hover(self):
        self.cb(self.current, self.data, self.combining)


class SelectToolController(BaseToolController):
    def __init__(self, project: Project,
                 model: 'SelectToolModel',
                 view: 'pcbre.ui.boardviewwidget.BoardViewWidget',
                 submit: Any):
        super(SelectToolController, self).__init__()

        self.view: pcbre.ui.boardviewwidget.BoardViewWidget = view
        self.project: Project = project
        self.model: SelectToolModel = model
        self.submit = submit


    @property
    def tool_actions(self):
        return g_ACTIONS

    def eventSelect(self, evt: ToolActionEvent, combining: CombiningMode):
        new = set()
        current = self.view.selectionList

        if self.model.vers == SelectByModes.POINT:
            res = self.view.query_point_multiple(evt.world_pos)

            # prune the selection list
            if combining == CombiningMode.UNION:
                res = res.difference(current)
            elif combining == CombiningMode.DIFFERENCE:
                res = res.intersection(current)
            else:
                updated = new


            # No items found, no selection change
            if len(res) == 0:
                new = []

            # Only one item found, no need for a user query
            elif len(res) == 1:
                new.add(res.pop())

            # More than one item found, pop a context menu
            else:
                # TODO, this is kludgy, rework
                self.ctxmenu = ctxmenu = QtWidgets.QMenu()
                for i in res:
                    # TODO - better human names
                    act = SelectionMenuAction(self.view, ctxmenu, "%s" % i, self.__finish_eventSelect, current, set([i]), combining)
                    ctxmenu.addAction(act)

                act = SelectionMenuAction(self.view, ctxmenu, "All (%d items)" % len(res), self.__finish_eventSelect, current, res, combining)
                ctxmenu.addAction(act)

                # Show at the cursor. TODO - offset?
                screen_pt = self.view.mapToGlobal(QtCore.QPoint(*evt.cursor_pos))
                ctxmenu.move(screen_pt)
                ctxmenu.show()

                def cleanup():
                    self.view.setSelectionList(current)

                ctxmenu.aboutToHide.connect(cleanup)

        elif self.model.vers == SelectByModes.NET:
            res = self.view.query_point_multiple(evt.world_pos)

            # Gather and dedup all potential nets we might be picking
            candidates = {} # Net -> set(geom)
            for i in res:
                if i.TYPE_FLAGS & TFF.HAS_NET:
                    if i.net not in candidates:
                        candidates[i.net] = self.project.artwork.get_geom_for_net(i.net)

            # Zero nets, no selection
            if len(candidates) == 0:
                new = []

            # One net, select it
            elif len(candidates) == 1:
                new = candidates.popitem()[1]

            # More than one, show popup
            else:
                # TODO, this is kludgy, rework
                self.ctxmenu = ctxmenu = QtWidgets.QMenu()
                for net, aw in candidates.items():
                    # TODO - better human names, add net names
                    act = SelectionMenuAction(self.view, ctxmenu, "%s" % net, self.__finish_eventSelect, current, aw, combining)
                    ctxmenu.addAction(act)

                # Show at the cursor. TODO - offset?
                screen_pt = self.view.mapToGlobal(QtCore.QPoint(*evt.cursor_pos))
                ctxmenu.move(screen_pt)
                ctxmenu.show()

                def cleanup():
                    self.view.setSelectionList(current)
                ctxmenu.aboutToHide.connect(cleanup)

        self.__finish_eventSelect(current, new, combining)


    def __finish_eventSelect(self, current, new, combining):

        if combining == CombiningMode.UNION:
            updated = current.union(new)
        elif combining == CombiningMode.DIFFERENCE:
            updated = current.difference(new)
        else:
            updated = new

        self.view.setSelectionList(updated)


    def eventDelete(self):
        del_list = []
        for v in self.view.selectionList:
            if isinstance(v, Pad):
                continue
            del_list.append(v)


        self.submit(UndoDelete(self.project, del_list, "Delete %d geom items" % len(del_list)))

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
        return SelectToolController(self.project, self.model, view, submit)

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

    # TODO, add drag selections

    ToolActionDescription(
        [
            ToolActionShortcut(EventID.Key_Backspace),
            ToolActionShortcut(EventID.Key_Delete),
        ],
        SelectEventCode.DeleteSelected,
        "Delete selected items")
]
