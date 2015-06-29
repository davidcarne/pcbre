import enum
from .basetool import BaseTool, BaseToolController
from pcbre.model.artwork_geom import Trace
from pcbre.model.const import TFF
from pcbre.ui.boardviewwidget import QPoint_to_pair
from PySide import QtCore, QtGui
from pcbre.ui.uimodel import GenModel, mdlacc
from pcbre.ui.icon import Icon
import pkg_resources


class SelectByModes(enum.Enum):
    POINT = 0
    TOUCH_LINE = 1
    TOUCH_RECT = 2
    INSIDE_RECT = 3
    NET = 4

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
    def __init__(self, project, model, view):
        """

        :param project:
        :param view:
        :type view: pcbre.ui.boardviewwidget.BoardViewWidget
        :return:
        """
        super(SelectToolController, self).__init__()

        self.view = view
        self.project = project
        self.model = model

    def mousePressEvent(self, evt):
        pt = QPoint_to_pair(evt)
        pt_w = self.view.viewState.tfV2W(pt)

        new = set()

        if self.model.vers == SelectByModes.POINT:
            res = self.project.artwork.query_point(pt_w)
            if res is not None:
                new.add(res)

        elif self.model.vers == SelectByModes.NET:
            res = self.project.artwork.query_point(pt_w)
            if res is not None and res.TYPE_FLAGS & TFF.HAS_NET:
                net = res.net
                aw = self.project.artwork.get_geom_for_net(net)
                new.update(aw)

        current = self.view.selectionList


        if evt.modifiers() & QtCore.Qt.ControlModifier:
            if evt.modifiers() & QtCore.Qt.ShiftModifier:
                updated = current.difference(new)
            else:
                updated = current.union(new)
        else:
            updated = new

        self.view.setSelectionList(updated)

    def keyPressEvent(self, evt):
        if evt.key() == QtCore.Qt.Key_Backspace or evt.key() == QtCore.Qt.Key_Delete:
            for v in self.view.selectionList:
                self.project.artwork.remove(v)
            return True

        return False
    


        

class SelectToolModel(GenModel):
    vers = mdlacc(SelectByModes.POINT)

class SelectTool(BaseTool):
    ICON_NAME="cross"
    NAME="Select"
    SHORTCUT = 's'
    TOOLTIP = 'Select (s)'

    def __init__(self, project):
        super(SelectTool, self).__init__(project)
        self.model = SelectToolModel()

        self.model.changed.connect(self.__update_icon)


    def getToolController(self, view):
        return SelectToolController(self.project, self.model, view)

    def __update_icon(self):
        ico = Icon(select_icons[self.model.vers])
        
        self.toolButton.setIcon(ico)
        self.toolButton.setText(select_names[self.model.vers])
        self.toolButton.setShortcut(self.SHORTCUT)

    def __set_version(self, v):
        self.model.vers = v

    def setupToolButtonExtra(self):
        self.menu = QtGui.QMenu()
        self.ag = QtGui.QActionGroup(self.menu)

        for n in valid_select:
            a1 = QtGui.QAction(select_names[n], self.menu)
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
