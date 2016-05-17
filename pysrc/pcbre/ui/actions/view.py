from pcbre.ui.boardviewwidget import MODE_TRACE, MODE_CAD
from pcbre.ui.icon import Icon

__author__ = 'davidc'

from PySide import QtGui

class LayerJumpAction(QtGui.QAction):
    def __init__(self, window, layer_no):
        self.__layer = layer_no
        self.window = window

        QtGui.QAction.__init__(self, "layer %d" % layer_no, window, triggered=self.__action)
        self.setShortcut(QtGui.QKeySequence("%d" % (layer_no+1)))

    def __action(self):
        if self.__layer >= len(self.window.project.stackup.layers):
            return

        self.window.viewArea.viewState.current_layer = self.window.project.stackup.layers[self.__layer]


class FlipXAction(QtGui.QAction):
    def __init__(self, window):
        self.__window = window

        QtGui.QAction.__init__(self, "Flip X", self.__window, triggered=self.__action)
        self.setShortcut(QtGui.QKeySequence("f"))
        self.setIcon(Icon("flipx"))
        self.setToolTip('f')

    def __action(self):
        self.__window.viewArea.viewState.flip(0)

class FlipYAction(QtGui.QAction):
    def __init__(self, window):
        self.__window = window

        QtGui.QAction.__init__(self, "Flip Y", self.__window, triggered=self.__action)
        self.setShortcut(QtGui.QKeySequence("shift+f"))
        self.setIcon(Icon("flipy"))
        self.setToolTip('Shift+f')

    def __action(self):
        self.__window.viewArea.viewState.flip(1)


class RotateLAction(QtGui.QAction):
    def __init__(self, window):
        self.__window = window
        QtGui.QAction.__init__(self, "Rotate 90 (CCW)", self.__window, triggered=self.__action)
        self.setShortcut(QtGui.QKeySequence("ctlr+shift+r"))
        self.setIcon(Icon("rotl"))
        self.setToolTip("Ctrl+Shift+r")


    def __action(self):
        self.__window.viewArea.viewState.rotate(-90)


class RotateRAction(QtGui.QAction):
    def __init__(self, window):
        self.__window = window
        QtGui.QAction.__init__(self, "Rotate 90 (CW)", self.__window, triggered=self.__action)
        self.setShortcut(QtGui.QKeySequence("ctlr+r"))
        self.setIcon(Icon("rotr"))
        self.setToolTip("Ctrl+r")


    def __action(self):
        self.__window.viewArea.viewState.rotate(90)

class CycleDrawOrderAction(QtGui.QAction):
    def __init__(self, window):
        self.__window = window
        QtGui.QAction.__init__(self, "Cycle Image Draw Order", self.__window, triggered=self.__action)
        self.setShortcut(QtGui.QKeySequence("]"))
        self.setIcon(Icon("changeorder"))
        self.setToolTip("]")

    def __action(self):
        self.__window.viewArea.viewState.permute_layer_order()


class SetModeTraceAction(QtGui.QAction):
    def __init__(self, mw, va):
        QtGui.QAction.__init__(self, "Tracing Mode", mw)
        self.va = va

        self.setCheckable(True)

        self.update_from_prop()
        self.triggered.connect(self.__set_prop)

    def __set_prop(self):
        self.va.render_mode = MODE_TRACE

    def update_from_prop(self):
        self.setChecked(self.va.render_mode == MODE_TRACE)


class SetModeCADAction(QtGui.QAction):
    def __init__(self, mw, va):
        QtGui.QAction.__init__(self, "CAD Mode", mw)
        self.va = va

        self.setCheckable(True)

        self.update_from_prop()
        self.triggered.connect(self.__set_prop)

    def __set_prop(self):
        self.va.render_mode = MODE_CAD

    def update_from_prop(self):
        self.setChecked(self.va.render_mode == MODE_CAD)

class CycleModeAction(QtGui.QAction):
    def __init__(self, mw, va):
        QtGui.QAction.__init__(self, "Cycle view Mode", mw)
        self.setShortcut(QtGui.QKeySequence("m"))
        self.va = va

        self.triggered.connect(self.__cycle)

    def __cycle(self):
        print("Trigger")
        mode = self.va.render_mode

        if mode == MODE_CAD:
            newmode = MODE_TRACE
        elif mode == MODE_TRACE:
            newmode = MODE_CAD

        self.va.render_mode = newmode

