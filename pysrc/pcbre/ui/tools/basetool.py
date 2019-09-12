from qtpy import QtGui, QtCore, QtWidgets
from pcbre.ui.icon import Icon
import pkg_resources

class BaseToolController(QtCore.QObject):
    changed = QtCore.Signal()

    def __init__(self):
        super(BaseToolController, self).__init__()
        self.overlay = None

    def mouseReleaseEvent(self, evt):
        pass

    def mousePressEvent(self, evt):
        pass

    def mouseMoveEvent(self, evt):
        pass

    """
        called as part of the event filter, must return False unless handling
    """
    def keyPressEvent(self, evt):
        return False

    def keyReleaseEvent(self, evt):
        return False

    def mouseWheelEvent(self, evt):
        pass

    def initialize(self):
        pass

    def finalize(self):
        pass

    def focusOutEvent(self, evt):
        pass

    def showSettingsDialog(self):
        pass

class BaseTool(object):
    SHORTCUT=None
    TOOLTIP=None

    def __init__(self, project):
        self.toolButton = None
        self.project = project

    def setupToolButton(self, icon_name, name):
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

    def getToolController(self, view):
        return BaseToolController()

