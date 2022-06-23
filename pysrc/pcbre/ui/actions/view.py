from pcbre.ui.boardviewwidget import MODE_TRACE, MODE_CAD
from pcbre.ui.icon import Icon
from pcbre.ui.panes.console import ConsoleWidgetT, ConsoleWidget
from pcbre.model.project import Project
from qtpy import QtCore, QtGui, QtWidgets
__author__ = 'davidc'

from typing import TYPE_CHECKING, Optional
if TYPE_CHECKING:
    from pcbre.ui.main_gui import MainWindow
    from pcbre.ui.boardviewwidget import BoardViewWidget
    from pcbre.view.viewport import ViewPort


class LayerJumpAction(QtWidgets.QAction):
    def __init__(self, window: 'MainWindow', layer_no: int) -> None:
        self.__layer = layer_no
        self.window = window

        QtWidgets.QAction.__init__(self, "layer %d" % layer_no, window)
        self.triggered.connect(self.__action)
        self.setShortcut(QtGui.QKeySequence("%d" % (layer_no+1)))

    def __action(self) -> None:
        if self.__layer >= len(self.window.project.stackup.layers):
            return

        # TODO: make this get copper layer
        layer = self.window.project.stackup.layers[self.__layer]

        self.window.changeViewLayer(layer)

################################ Common tool actions
class FlipXAction(QtWidgets.QAction):
    def __init__(self, window, vp: 'ViewPort'):
        self.__vp = vp

        QtWidgets.QAction.__init__(
            self, "Flip X", window)
        self.triggered.connect(self.__action)
        self.setShortcut(QtGui.QKeySequence("f"))
        self.setIcon(Icon("flipx"))
        self.setToolTip('f')

    def __action(self) -> None:
        self.__vp.flip(0)


class FlipYAction(QtWidgets.QAction):
    def __init__(self, window, vp: 'ViewPort') -> None:
        self.__vp = vp

        QtWidgets.QAction.__init__(
            self, "Flip Y", window)
        self.triggered.connect(self.__action)
        self.setShortcut(QtGui.QKeySequence("shift+f"))
        self.setIcon(Icon("flipy"))
        self.setToolTip('Shift+f')

    def __action(self) -> None:
        self.__vp.flip(1)


class RotateLAction(QtWidgets.QAction):
    def __init__(self, window, vp: 'ViewPort') -> None:
        self.__vp = vp
        QtWidgets.QAction.__init__(
            self, "Rotate 90 (CCW)", window)
        self.triggered.connect(self.__action)
        self.setShortcut(QtGui.QKeySequence("ctlr+shift+r"))
        self.setIcon(Icon("rotl"))
        self.setToolTip("Ctrl+Shift+r")

    def __action(self) -> None:
        self.__vp.rotate(-90)


class RotateRAction(QtWidgets.QAction):
    def __init__(self, window, vp: 'ViewPort') -> None:
        self.__vp = vp
        QtWidgets.QAction.__init__(
            self, "Rotate 90 (CW)", window)
        self.triggered.connect(self.__action)
        self.setShortcut(QtGui.QKeySequence("ctlr+r"))
        self.setIcon(Icon("rotr"))
        self.setToolTip("Ctrl+r")

    def __action(self) -> None:
        self.__vp.rotate(90)


class ViewLastAction(QtWidgets.QAction):
    pass

class ZoomFitAction(QtWidgets.QAction):
    def __init__(self, window, vp: 'ViewPort', bbox_call) -> None:
        QtWidgets.QAction.__init__(
            self, "Zoom to Fit",
            window)

        self.__vp = vp
        self.__bbox_call = bbox_call
        self.triggered.connect(self.__action)
        #self.setShortcut(QtGui.QKeySequence("]"))
        #self.setIcon(Icon("changeorder"))
        #self.setToolTip("]")

    def __action(self) -> None:
        r = self.__bbox_call()
        if not r:
            return
        self.__vp.fit_rect(r)

#####################3

class CycleDrawOrderAction(QtWidgets.QAction):
    def __init__(self, window: 'MainWindow') -> None:
        self.__window = window
        QtWidgets.QAction.__init__(
            self, "Cycle Image Draw Order",
            self.__window)
        self.triggered.connect(self.__action)
        self.setShortcut(QtGui.QKeySequence("]"))
        self.setIcon(Icon("changeorder"))
        self.setToolTip("]")

    def __action(self) -> None:
        self.__window.viewArea.boardViewState.permute_layer_order()



class SetModeTraceAction(QtWidgets.QAction):
    def __init__(self, mw: 'MainWindow', va: 'BoardViewState') -> None:
        QtWidgets.QAction.__init__(self, "Tracing Mode", mw)
        self.va = va

        self.setCheckable(True)

        self.update_from_prop()
        self.triggered.connect(self.__set_prop)
        self.va.changed.connect(self.update_from_prop)

    def __set_prop(self) -> None:
        self.va.render_mode = MODE_TRACE

    def update_from_prop(self) -> None:
        self.setChecked(self.va.render_mode == MODE_TRACE)


class SetModeCADAction(QtWidgets.QAction):
    def __init__(self, mw: 'MainWindow', va: 'BoardViewState') -> None:
        QtWidgets.QAction.__init__(self, "CAD Mode", mw)
        self.va = va

        self.setCheckable(True)

        self.update_from_prop()
        self.triggered.connect(self.__set_prop)
        self.va.changed.connect(self.update_from_prop)

    def __set_prop(self) -> None:
        self.va.render_mode = MODE_CAD

    def update_from_prop(self) -> None:
        self.setChecked(self.va.render_mode == MODE_CAD)


class CycleModeAction(QtWidgets.QAction):
    def __init__(self, mw: 'MainWindow', va: 'BoardViewState') -> None:
        QtWidgets.QAction.__init__(self, "Cycle view Mode", mw)
        self.setShortcut(QtGui.QKeySequence("m"))
        self.va = va

        self.triggered.connect(self.__cycle)

    def __cycle(self) -> None:
        mode = self.va.render_mode

        if mode == MODE_CAD:
            newmode = MODE_TRACE
        elif mode == MODE_TRACE:
            newmode = MODE_CAD
        else:
            assert False

        self.va.render_mode = newmode


class ShowConsoleAction(QtWidgets.QAction):
    def __init__(self, project: Project, mw: 'MainWindow') -> None:
        QtWidgets.QAction.__init__(self, "Show Console", mw)
        self.setCheckable(True)

        self.dock : 'Optional[ConsoleWidgetT]' =  None
        self.project = project
        self.mw = mw

        self.update_from_prop()

    def handle_close(self) -> None:
        self.dock = None

    def toggle(self) -> None:
        if self.docked is None:
            self.dock = new_dock = ConsoleWidget(self.project)
            self.mw.addDockWidget(QtCore.Qt.BottomDockWidgetArea, new_dock)

        self.update_from_prop()

    def update_from_prop(self) -> None:
        self.setChecked(self.dock is not None)
