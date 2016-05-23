from pcbre.matrix import Point2
from pcbre.model.component import Component
from pcbre.model.const import TFF
from pcbre.ui.tools.basetool import BaseToolController, BaseTool
from .net_dialog import NetDialog

__author__ = 'davidc'



class NameToolController(BaseToolController):
    def __init__(self, view, project):
        super(NameToolController, self).__init__()

        self.view = view
        self.project = project

        self.show = False

        self.overlay = None

    def showSettingsDialog(self):
        pass


    def mousePressEvent(self, evt):
        pos = evt.pos()
        pt = Point2(self.view.viewState.tfV2W(Point2(pos)))
        g = self.view.query_point(pt)

        if g:
            dlg = NetDialog(self.view.project, self.view, g)
            dlg.exec_()

    def mouseReleaseEvent(self, evt):
        pass


class NameTool(BaseTool):
    ICON_NAME = "netname"
    NAME = "Name"
    SHORTCUT = 'n'
    TOOLTIP = 'Name (n)'

    def __init__(self, project):
        super(NameTool, self).__init__(project)
        self.project = project
        self.ext = []

    def getToolController(self, view):
        return NameToolController(view, self.project)
