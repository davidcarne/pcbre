from abc import abstractmethod
from qtpy import QtCore, QtWidgets
from pcbre.ui.icon import Icon
import pcbre.model.project
from typing import Union, List
from pcbre.ui.tool_action import MoveEvent, ToolActionEvent, ToolActionDescription
import pcbre.ui.boardviewwidget
from typing import Callable
from pcbre.ui.uimodel import TinySignal


class BaseToolController(QtCore.QObject):

    def __init__(self) -> None:
        super(BaseToolController, self).__init__()
        self.overlay = None
        changed = TinySignal()

    def mouseMoveEvent(self, evt: MoveEvent) -> None:
        pass

    def initialize(self) -> None:
        pass

    def finalize(self) -> None:
        pass

    def focusOutEvent(self, evt: None) -> None:
        pass

    def showSettingsDialog(self) -> None:
        pass

    @property
    @abstractmethod
    def tool_actions(self) -> List[ToolActionDescription]:
        pass

    @abstractmethod
    def tool_event(self, event: ToolActionEvent) -> None:
        pass


class BaseTool(object):
    SHORTCUT: Union[str, None] = None
    TOOLTIP: Union[str, None] = None
    ICON_NAME: str = ""
    NAME: str = ""

    def __init__(self, project: pcbre.model.project.Project):
        self.toolButton: QtWidgets.QToolButton = None
        self.project = project

    def setupToolButton(self, icon_name: str, name: str):
        ico = Icon(icon_name)

        self.toolButton = QtWidgets.QToolButton(None)
        self.toolButton.setIcon(ico)
        self.toolButton.setText(name)

        if self.SHORTCUT is not None:
            self.toolButton.setShortcut(self.SHORTCUT)

        if self.TOOLTIP is not None:
            self.toolButton.setToolTip(self.TOOLTIP)

    def setupToolButtonExtra(self):
        pass

    def getToolButton(self):
        if self.toolButton is not None:
            return self.toolButton

        self.setupToolButton(self.ICON_NAME, self.NAME)
        self.setupToolButtonExtra()

        return self.toolButton

    def getToolController(self, 
                          view: 'pcbre.ui.boardviewwidget.BoardViewWidget', 
                          submit: Callable):
        return BaseToolController()
