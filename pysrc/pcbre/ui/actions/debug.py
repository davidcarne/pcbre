from PySide import QtGui

class ToggleDrawBBoxAction(QtGui.QAction):
    def __init__(self, mw, va):
        QtGui.QAction.__init__(self, "Draw Bounding Boxes", mw)
        self.va = va

        self.setCheckable(True)

        self.update_from_prop()
        self.triggered.connect(self.__set_prop)

    def __set_prop(self):
        self.va.debug_renderer.debug_draw_bbox = self.isChecked()

    def update_from_prop(self):
        self.setChecked(self.va.debug_renderer.debug_draw_bbox)

class ToggleDrawDebugAction(QtGui.QAction):
    def __init__(self, mw, va):
        QtGui.QAction.__init__(self, "Debug Draws", mw)
        self.va = va

        self.setCheckable(True)

        self.update_from_prop()
        self.triggered.connect(self.__set_prop)

    def __set_prop(self):
        self.va.debug_renderer.debug_draw = self.isChecked()

    def update_from_prop(self):
        self.setChecked(self.va.debug_renderer.debug_draw)