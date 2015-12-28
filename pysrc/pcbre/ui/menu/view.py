from PySide import QtGui

class ToggleShowImageryAction(QtGui.QAction):
    def __init__(self, mw, va):
        QtGui.QAction.__init__(self, "Show Imagery", mw)
        self.va = va

        self.setCheckable(True)

        self.update_from_prop()
        self.triggered.connect(self.update_from_prop)

    def __set_prop(self):
        self.va.viewState.show_images = self.isChecked()

    def update_from_prop(self):
        self.setChecked(self.va.viewState.show_images)


class ToggleDrawOtherLayersAction(QtGui.QAction):
    def __init__(self, mw, va):
        QtGui.QAction.__init__(self, "Show Other Layers artwork", mw)
        self.va = va

        self.setCheckable(True)

        self.update_from_prop()
        self.triggered.connect(self.update_from_prop)

    def __set_prop(self):
        self.va.viewState.draw_other_layers = self.isChecked()

    def update_from_prop(self):
        self.setChecked(self.va.viewState.draw_other_layers)

class ViewMenu(QtGui.QMenu):
    def __init__(self, mw):
        QtGui.QMenu.__init__(self, "&View", mw)

        self.subWindowMenu = self.addMenu("Sub-Windows")
        self.addSeparator()
        self.addAction(mw.rotate90L)
        self.addAction(mw.rotate90R)
        self.addAction(mw.flipX)
        self.addAction(mw.flipY)
        self.addAction(mw.permute)

        self.addSeparator()

        self.__toggle_show_action = ToggleShowImageryAction(mw, mw.viewArea)
        self.__toggle_draw_others = ToggleDrawOtherLayersAction(mw, mw.viewArea)
        self.addAction(self.__toggle_show_action)
        self.addAction(self.__toggle_draw_others)


        def update_sub():
            self.__toggle_show_action.update_from_prop()
            self.__toggle_draw_others.update_from_prop()

        self.aboutToShow.connect(update_sub)


